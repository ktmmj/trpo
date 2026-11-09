"""
Контроллеры заявок.

Порядок объявления роутов важен: статические пути (/client, /search,
/search/own) должны идти ДО динамических (/{ticket_id}), иначе FastAPI
сматчит /tickets/search как /tickets/{ticket_id} и вернёт 404.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_operator
from app.exceptions import ForbiddenError
from app.models.entities import User
from app.schemas import (
    ClientTicketCreateIn,
    SortField,
    SortOrder,
    TicketAssigneeIn,
    TicketCreateIn,
    TicketSearchIn,
    TicketSearchPage,
    TicketStatusIn,
    TicketUpdateIn,
)
from app.service.ticket_service import TicketService, _role_name

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ---------------------------------------------------------------------------
# общий парсер query-параметров поиска
# ---------------------------------------------------------------------------
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
        q=q,
        author_id=author_id,
        assignee_id=assignee_id,
        status_id=status_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


# ===========================================================================
# СТАТИЧЕСКИЕ ПУТИ — объявлены ПЕРВЫМИ
# ===========================================================================

# ---------------------------------------------------------------------------
# создание заявки клиентом
# ---------------------------------------------------------------------------
@router.post("/client", status_code=status.HTTP_201_CREATED)
def create_ticket_by_client(
    data: ClientTicketCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создание заявки клиентом.
    Доступно только активному пользователю с ролью 'employee'.
    Клиент задаёт тему, тело и приоритет; категорию ставит оператор.
    """
    return TicketService(db).create_by_client(user, data)


# ---------------------------------------------------------------------------
# поиск оператора по всему каталогу
# ---------------------------------------------------------------------------
@router.get("/search", response_model=TicketSearchPage)
def search_tickets(
    params: TicketSearchIn = Depends(_parse_search),
    user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Поиск по всему каталогу заявок. Только оператор/модератор/админ."""
    return TicketService(db).search(user, params)


# ---------------------------------------------------------------------------
# поиск клиента по своим заявкам
# ---------------------------------------------------------------------------
@router.get("/search/own", response_model=TicketSearchPage)
def search_own_tickets(
    params: TicketSearchIn = Depends(_parse_search),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Поиск среди своих заявок. Доступен любому авторизованному пользователю;
    author_id принудительно перезаписывается на id текущего пользователя.
    """
    return TicketService(db).search_own(user, params)


# ---------------------------------------------------------------------------
# создание заявки — внутренний сценарий (совместимость)
# ---------------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Внутренний метод создания заявки с расширенными полями.
    Ограничен ролью 'employee', чтобы не обходил клиентские проверки.
    Для клиентского сценария используйте POST /tickets/client.
    """
    if _role_name(user) != "employee":
        raise ForbiddenError(
            "Используйте /tickets/client для клиентского сценария"
        )
    return TicketService(db).create(user, data)


# ---------------------------------------------------------------------------
# история заявок текущего пользователя
# ---------------------------------------------------------------------------
@router.get("")
def list_tickets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    История заявок текущего пользователя.
    - клиент видит только свои;
    - оператор/модератор/админ — весь каталог (первые 100).
    """
    return TicketService(db).list_for_user(user)


# ===========================================================================
# ДИНАМИЧЕСКИЕ ПУТИ — объявлены ПОСЛЕ статических
# ===========================================================================

# ---------------------------------------------------------------------------
# карточка заявки
# ---------------------------------------------------------------------------
@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TicketService(db).get(ticket_id, user)


# ---------------------------------------------------------------------------
# редактирование заявки (тема, тело, приоритет, категория)
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    data: TicketUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TicketService(db).update(ticket_id, user, data)


# ---------------------------------------------------------------------------
# смена статуса (оператор)
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}/status")
def change_status(
    ticket_id: int,
    data: TicketStatusIn,
    user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    return TicketService(db).change_status(
        ticket_id, user, data.status_id, data.note
    )


# ---------------------------------------------------------------------------
# переназначение оператора
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}/assignee")
def change_ticket_assignee(
    ticket_id: int,
    data: TicketAssigneeIn,
    user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """
    Переназначение оператора на заявку.
    - оператор: только взять заявку себе (assignee_id = свой id);
    - модератор/админ: назначить любого активного оператора или снять (null).
    """
    return TicketService(db).change_assignee(
        ticket_id, user, data.assignee_id, data.note
    )