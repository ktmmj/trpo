from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.entities import User
from app.schemas import CommentCreateIn, CommentOut
from app.service.comment_service import CommentService

router = APIRouter(prefix="/tickets/{ticket_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentOut])
def list_comments(
        ticket_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return CommentService(db).list(ticket_id, user)


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
        ticket_id: int,
        data: CommentCreateIn,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return CommentService(db).add(ticket_id, user, data.body, data.is_internal)
