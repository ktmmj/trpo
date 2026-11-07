from datetime import datetime
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from app.models.entities import Ticket
from app.repository.interfaces import ITicketRepository


class OrmTicketRepository(ITicketRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, ticket_id: int) -> Ticket | None:
        return self.db.get(Ticket, ticket_id)

    def add(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def save(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def list_by_author(self, author_id: int):
        stmt = (
            select(Ticket)
            .where(Ticket.author_id == author_id)
            .order_by(Ticket.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def search(
            self,
            q: str | None,
            author_id: int | None,
            assignee_id: int | None,
            status_id: int | None,
            date_from: datetime | None,
            date_to: datetime | None,
            limit: int,
            offset: int,
    ):
        conditions = []
        if q:
            like = f"%{q}%"
            conditions.append(or_(Ticket.title.ilike(like), Ticket.description.ilike(like)))
        if author_id is not None:
            conditions.append(Ticket.author_id == author_id)
        if assignee_id is not None:
            conditions.append(Ticket.assignee_id == assignee_id)
        if status_id is not None:
            conditions.append(Ticket.status_id == status_id)
        if date_from is not None:
            conditions.append(Ticket.created_at >= date_from)
        if date_to is not None:
            conditions.append(Ticket.created_at <= date_to)

        stmt = select(Ticket)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))
