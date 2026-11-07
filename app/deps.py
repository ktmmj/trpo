from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.exceptions import ForbiddenError, NotFoundError
from app.models.entities import User
from app.security import parse_token
from app.repository.impl.orm_user import OrmUserRepository

OPERATOR_ROLES = {"agent", "support_agent", "moderator", "admin"}
MODERATOR_ROLES = {"moderator", "admin"}
ADMIN_ROLES = {"admin"}


def get_current_user(
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ForbiddenError("Требуется авторизация")
    token = authorization.split(" ", 1)[1]
    user_id = parse_token(token)
    if user_id is None:
        raise ForbiddenError("Недействительный токен")
    user = OrmUserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise NotFoundError("Пользователь не найден или заблокирован")
    return user


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


def require_operator(user: User = Depends(get_current_user)) -> User:
    if _role_name(user) not in OPERATOR_ROLES:
        raise ForbiddenError("Действие доступно оператору")
    return user


def require_moderator(user: User = Depends(get_current_user)) -> User:
    if _role_name(user) not in MODERATOR_ROLES:
        raise ForbiddenError("Действие доступно модератору")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if _role_name(user) not in ADMIN_ROLES:
        raise ForbiddenError("Действие доступно администратору")
    return user
