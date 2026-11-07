from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_moderator
from app.models.entities import User
from app.schemas import UserOut, UserUpdateIn
from app.service.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        _: User = Depends(require_moderator),
        db: Session = Depends(get_db),
):
    return UserService(db).list(limit, offset)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
        user_id: int,
        _: User = Depends(require_moderator),
        db: Session = Depends(get_db),
):
    return UserService(db).get(user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
        user_id: int,
        data: UserUpdateIn,
        _: User = Depends(require_moderator),
        db: Session = Depends(get_db),
):
    return UserService(db).update(user_id, data)


@router.delete("/{user_id}", response_model=UserOut)
def deactivate_user(
        user_id: int,
        _: User = Depends(require_moderator),
        db: Session = Depends(get_db),
):
    return UserService(db).deactivate(user_id)
