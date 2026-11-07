import secrets
from sqlalchemy.orm import Session
from app.exceptions import ConflictError, ValidationError, ForbiddenError
from app.models.entities import User
from app.repository.impl.orm_user import OrmUserRepository
from app.security import hash_password, verify_password, create_token

DEFAULT_CLIENT_ROLE_ID = 3  # 'employee' из seed.sql


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = OrmUserRepository(db)

    def register_client(self, email: str, full_name: str, department: str | None) -> tuple[User, str]:
        if self.users.get_by_email(email):
            raise ConflictError("Пользователь с таким email уже зарегистрирован")

        # Пароль генерируется и «отправляется на почту».
        raw_password = secrets.token_urlsafe(8)
        user = User(
            email=email,
            full_name=full_name,
            department=department,
            is_active=True,
            user_role=DEFAULT_CLIENT_ROLE_ID,
            password_hash=hash_password(raw_password),
        )
        user = self.users.add(user)
        self.db.commit()
        # здесь была бы отправка письма с raw_password
        return user, raw_password

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ForbiddenError("Неверный email или пароль")
        if not user.is_active:
            raise ForbiddenError("Учётная запись заблокирована")
        return create_token(user.id)
