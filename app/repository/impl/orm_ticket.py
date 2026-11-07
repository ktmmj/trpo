from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session, aliased

from app.models.entities import Ticket, Status
from app.repository.interfaces import ITicketRepository


def _build_conditions(
        q: str | None,
        author_id: int | None,
        assignee_id: int | None,
        status_id: int | None,
        category_id: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
):
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(Ticket.title.ilike(like), Ticket.description.ilike(like)))
    if author_id is not None:
        conds.append(Ticket.author_id == author_id)
    if assignee_id is not None:
        conds.append(Ticket.assignee_id == assignee_id)
    if status_id is not None:
        conds.append(Ticket.status_id == status_id)
    if category_id is not None:
        conds.append(Ticket.category_id == category_id)
    if date_from is not None:
        conds.append(Ticket.created_at >= date_from)
    if date_to is not None:
        conds.append(Ticket.created_at <= date_to)
    return conds


class OrmTicketRepository(ITicketRepository):
    def __init__(self, db: Session):
        self.db = db

    # ... get_by_id, add, save, list_by_author — без изменений ...

    def _order_clause(self, sort_by: str, sort_order: str):
        col = {
            "created_at": Ticket.created_at,
            "updated_at": Ticket.updated_at,
            "priority": Ticket.priority,
            "status": Status.name,
        }[sort_by]
        return col.asc() if sort_order == "asc" else col.desc()

    def search(
            self,
            q, author_id, assignee_id, status_id, category_id,
            date_from, date_to, sort_by, sort_order, limit, offset,
    ):
        conds = _build_conditions(
            q, author_id, assignee_id, status_id, category_id, date_from, date_to
        )
        stmt = (
            select(Ticket, Status.name.label("status_name"))
            .join(Status, Status.id == Ticket.status_id)
        )
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = (
            stmt.order_by(self._order_clause(sort_by, sort_order))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).all())

    def count_search(
            self, q, author_id, assignee_id, status_id, category_id, date_from, date_to,
    ) -> int:
        conds = _build_conditions(
            q, author_id, assignee_id, status_id, category_id, date_from, date_to
        )
        stmt = select(func.count(Ticket.id))
        if conds:
            stmt = stmt.where(and_(*conds))
        return int(self.db.scalar(stmt) or 0)
