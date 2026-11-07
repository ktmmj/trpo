from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.schemas import TicketAssigneeIn
from app.database import get_db
from app.deps import get_current_user, require_operator
from app.models.entities import User
from app.schemas import (
    TicketCreateIn, TicketUpdateIn, TicketStatusIn, TicketSearchIn,
)
from app.service.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
        data: TicketCreateIn,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return TicketService(db).create(user, data)


@router.get("")
def list_tickets(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return TicketService(db).list_for_user(user)


@router.get("/search")
def search_tickets(
        q: str | None = Query(default=None, max_length=255),
        author_id: int | None = None,
        assignee_id: int | None = None,
        status_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        user: User = Depends(require_operator),
        db: Session = Depends(get_db),
):
    params = TicketSearchIn(
        q=q, author_id=author_id, assignee_id=assignee_id,
        status_id=status_id,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return TicketService(db).search(user, params)


@router.get("/{ticket_id}")
def get_ticket(
        ticket_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return TicketService(db).get(ticket_id, user)


@router.patch("/{ticket_id}")
def update_ticket(
        ticket_id: int,
        data: TicketUpdateIn,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return TicketService(db).update(ticket_id, user, data)


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
    - модератор/админ: назначить любого активного оператора или снять (assignee_id = null).
    """
    return TicketService(db).change_assignee(
        ticket_id, user, data.assignee_id, data.note
    )
