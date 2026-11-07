from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Status
from app.repository.interfaces import IStatusRepository


class OrmStatusRepository(IStatusRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, status_id: int) -> Status | None:
        return self.db.get(Status, status_id)

    def list(self):
        return list(self.db.scalars(select(Status).order_by(Status.id)))
