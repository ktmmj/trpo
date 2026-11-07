from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import TicketStatusHistory
from app.repository.interfaces import IHistoryRepository


class OrmHistoryRepository(IHistoryRepository):
    def __init__(self, db: Session):
        self.db = db

    def add(self, entry: TicketStatusHistory) -> TicketStatusHistory:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_by_ticket(self, ticket_id: int):
        stmt = (
            select(TicketStatusHistory)
            .where(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.changed_at.asc())
        )
        return list(self.db.scalars(stmt))

    def list_all(self, limit: int = 1000):
        stmt = (
            select(TicketStatusHistory)
            .order_by(TicketStatusHistory.changed_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
