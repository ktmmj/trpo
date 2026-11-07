from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Comment
from app.repository.interfaces import ICommentRepository


class OrmCommentRepository(ICommentRepository):
    def __init__(self, db: Session):
        self.db = db

    def add(self, comment: Comment) -> Comment:
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_by_ticket(self, ticket_id: int):
        stmt = (
            select(Comment)
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.created_at.asc())
        )
        return list(self.db.scalars(stmt))
