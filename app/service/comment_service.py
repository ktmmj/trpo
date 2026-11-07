from datetime import datetime
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, NotFoundError
from app.models.entities import Comment, User, Ticket
from app.repository.impl.orm_comment import OrmCommentRepository
from app.repository.impl.orm_ticket import OrmTicketRepository
from app.repository.impl.orm_user import OrmUserRepository

INTERNAL_ROLES = {"agent", "support_agent", "moderator", "admin"}


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


class CommentService:
    def __init__(self, db: Session):
        self.db = db
        self.comments = OrmCommentRepository(db)
        self.tickets = OrmTicketRepository(db)

    def list(self, ticket_id: int, user: User):
        ticket = self.tickets.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Заявка не найдена")
        if ticket.author_id != user.id and _role_name(user) not in INTERNAL_ROLES:
            raise ForbiddenError("Нет доступа к заявке")

        result = self.comments.list_by_ticket(ticket_id)
        # внутренние комментарии не показываем клиенту
        if _role_name(user) not in INTERNAL_ROLES:
            result = [c for c in result if not c.is_internal]
        return result

    def add(self, ticket_id: int, user: User, body: str, is_internal: bool) -> Comment:
        ticket = self.tickets.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Заявка не найдена")

        role = _role_name(user)
        if ticket.author_id != user.id and role not in INTERNAL_ROLES:
            raise ForbiddenError("Нет доступа к заявке")

        if is_internal and role not in INTERNAL_ROLES:
            raise ForbiddenError("Внутренние комментарии доступны только поддержке")

        if ticket.closed_at is not None:
            raise ForbiddenError("Нельзя комментировать закрытую заявку")

        comment = Comment(
            ticket_id=ticket_id,
            author_id=user.id,
            body=body.strip(),
            created_at=datetime.utcnow(),
            is_internal=is_internal,
        )
        comment = self.comments.add(comment)
        # комментарий считается изменением заявки
        ticket.updated_at = datetime.utcnow()
        self.tickets.save(ticket)
        self.db.commit()
        self.db.refresh(comment)
        # уведомление участникам
        return comment
