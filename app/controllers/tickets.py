from fastapi import APIRouter, Depends, Query
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_operator
from app.models.entities import User
from app.schemas import TicketSearchIn, TicketSearchPage, SortField, SortOrder
from app.service.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _parse_search(
        q: str | None = Query(default=None, max_length=255),
        author_id: int | None = None,
        assignee_id: int | None = None,
        status_id: int | None = None,
        category_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: SortField = SortField.created_at,
        sort_order: SortOrder = SortOrder.desc,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
) -> TicketSearchIn:
    return TicketSearchIn(
        q=q, author_id=author_id, assignee_id=assignee_id, status_id=status_id,
        category_id=category_id, date_from=date_from, date_to=date_to,
        sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset,
    )


@router.get("/search", response_model=TicketSearchPage)
def search_tickets(
        params: TicketSearchIn = Depends(_parse_search),
        user: User = Depends(require_operator),
        db: Session = Depends(get_db),
):
    """Поиск по всему каталогу заявок. Только оператор/модератор/админ."""
    return TicketService(db).search(user, params)


@router.get("/search/own", response_model=TicketSearchPage)
def search_own_tickets(
        params: TicketSearchIn = Depends(_parse_search),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    """Поиск среди своих заявок. Доступен любому авторизованному; author_id игнорируется."""
    return TicketService(db).search_own(user, params)
