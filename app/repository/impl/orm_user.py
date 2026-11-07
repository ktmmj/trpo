from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import User
from app.repository.interfaces import IUserRepository


class OrmUserRepository(IUserRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def list(self, limit: int = 50, offset: int = 0):
        return list(self.db.scalars(select(User).order_by(User.id).limit(limit).offset(offset)))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
