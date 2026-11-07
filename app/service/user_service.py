from sqlalchemy.orm import Session
from app.exceptions import NotFoundError, ConflictError, ValidationError
from app.models.entities import User
from app.repository.impl.orm_user import OrmUserRepository
from app.schemas import UserUpdateIn


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.users = OrmUserRepository(db)

    def get(self, user_id: int) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("Пользователь не найден")
        return user

    def list(self, limit: int, offset: int):
        return self.users.list(limit=limit, offset=offset)

    def update(self, user_id: int, data: UserUpdateIn) -> User:
        user = self.get(user_id)
        if data.full_name is not None:
            if not data.full_name.strip():
                raise ValidationError("ФИО не может быть пустым")
            user.full_name = data.full_name.strip()
        if data.department is not None:
            user.department = data.department
        if data.user_role is not None:
            user.user_role = data.user_role
        if data.is_active is not None:
            user.is_active = data.is_active
        self.users.save(user)
        self.db.commit()
        return user

    def deactivate(self, user_id: int) -> User:
        user = self.get(user_id)
        user.is_active = False
        self.users.save(user)
        self.db.commit()
        return user
