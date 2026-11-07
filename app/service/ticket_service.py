from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    ForbiddenError, NotFoundError, ValidationError, ConflictError
)
from app.models.entities import Ticket, User, Status, TicketStatusHistory
from app.repository.impl.orm_ticket import OrmTicketRepository
from app.repository.impl.orm_user import OrmUserRepository
from app.repository.impl.orm_status import OrmStatusRepository
from app.repository.impl.orm_history import OrmHistoryRepository
from app.schemas import TicketCreateIn, TicketUpdateIn, TicketSearchIn
from app.schemas import TicketSearchIn, TicketSearchPage, TicketListOut
from app.exceptions import NotFoundError

OPEN_STATUS_NAME = "open"
OPERATOR_ROLE_NAMES = {"agent", "support_agent"}
INTERNAL_ROLES = {"agent", "support_agent", "moderator", "admin"}
ASSIGNABLE_ROLE_NAMES = {"agent", "support_agent"}


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


class TicketService:
    def __init__(self, db: Session):
        self.db = db
        self.tickets = OrmTicketRepository(db)
        self.users = OrmUserRepository(db)
        self.statuses = OrmStatusRepository(db)
        self.history = OrmHistoryRepository(db)

    # ---------- helpers ----------
    def _get_status_by_name(self, name: str) -> Status:
        stmt = select(Status).where(Status.name == name)
        status = self.db.scalar(stmt)
        if not status:
            raise ValidationError(f"Статус '{name}' не сконфигурирован")
        return status

    def _pick_operator(self) -> User | None:
        """Выбирает активного оператора с наименьшей текущей нагрузкой."""
        stmt = (
            select(User)
            .where(User.is_active == True)  # noqa: E712
        )
        operators = [
            u for u in self.db.scalars(stmt)
            if _role_name(u) in OPERATOR_ROLE_NAMES
        ]
        if not operators:
            return None

        # наименьшая нагрузка по открытым заявкам
        def load(op: User) -> int:
            stmt = select(Ticket).where(
                Ticket.assignee_id == op.id,
                Ticket.closed_at.is_(None),
            )
            return len(list(self.db.scalars(stmt)))

        return min(operators, key=load)

    def _notify(self, ticket: Ticket, event: str) -> None:
        """Заглушка отправки email клиенту и закреплённому оператору."""
        # В реальной системе здесь письмо через SMTP/очередь.
        recipients = [ticket.author_id, ticket.assignee_id]
        recipients = [r for r in recipients if r is not None]
        _ = (ticket.id, event, recipients)  # точка расширения

    def _log_status_change(self, ticket: Ticket, status: Status, changed_by: User, note: str | None):
        self.history.add(TicketStatusHistory(
            ticket_id=ticket.id,
            status_id=status.id,
            changed_by=changed_by.id,
            changed_at=datetime.utcnow(),
            note=note,
        ))

    def _assert_can_view(self, ticket: Ticket, user: User) -> None:
        if ticket.author_id == user.id:
            return
        if _role_name(user) in INTERNAL_ROLES:
            return
        raise ForbiddenError("Нет доступа к этой заявке")

    def _assert_can_edit(self, ticket: Ticket, user: User) -> None:
        role = _role_name(user)
        if ticket.author_id == user.id and ticket.closed_at is None:
            return
        if role in INTERNAL_ROLES:
            return
        raise ForbiddenError("Нет прав на редактирование заявки")

    # ---------- create ----------
    def create(self, user: User, data: TicketCreateIn) -> Ticket:
        if not user.is_active:
            raise ForbiddenError("Заблокированный пользователь не может создавать заявки")

        open_status = self._get_status_by_name(OPEN_STATUS_NAME)
        operator = self._pick_operator()

        ticket = Ticket(
            title=data.title,
            description=data.description,
            author_id=user.id,
            assignee_id=operator.id if operator else None,
            category_id=data.category_id,
            status_id=open_status.id,
            priority=data.priority.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        ticket = self.tickets.add(ticket)
        self._log_status_change(ticket, open_status, user, "Заявка создана")
        self.db.commit()
        self.db.refresh(ticket)
        self._notify(ticket, "created")
        return ticket

    # ---------- read ----------
    def list_for_user(self, user: User):
        role = _role_name(user)
        if role in INTERNAL_ROLES:
            # операторам/модераторам доступен весь каталог
            return self.tickets.search(None, None, None, None, None, None, 100, 0)
        return self.tickets.list_by_author(user.id)

    def get(self, ticket_id: int, user: User) -> Ticket:
        ticket = self.tickets.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Заявка не найдена")
        self._assert_can_view(ticket, user)
        return ticket

    # ---------- update ----------
    def update(self, ticket_id: int, user: User, data: TicketUpdateIn) -> Ticket:
        ticket = self.get(ticket_id, user)
        self._assert_can_edit(ticket, user)

        changed = False
        if data.title is not None:
            if not data.title.strip():
                raise ValidationError("Тема не может быть пустой")
            ticket.title = data.title.strip()
            changed = True
        if data.description is not None:
            ticket.description = data.description
            changed = True
        if data.priority is not None:
            ticket.priority = data.priority.value
            changed = True
        if data.category_id is not None:
            ticket.category_id = data.category_id
            changed = True

        if not changed:
            raise ValidationError("Нет данных для обновления")

        ticket.updated_at = datetime.utcnow()
        self.tickets.save(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        self._notify(ticket, "updated")
        return ticket

    # ---------- status ----------
    def change_status(self, ticket_id: int, user: User, status_id: int, note: str | None) -> Ticket:
        role = _role_name(user)
        if role not in INTERNAL_ROLES:
            raise ForbiddenError("Изменение статуса доступно только оператору")

        ticket = self.tickets.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Заявка не найдена")

        new_status = self.statuses.get_by_id(status_id)
        if not new_status:
            raise ValidationError("Статус не существует")

        if ticket.status_id == new_status.id:
            raise ConflictError("Заявка уже в этом статусе")

        old_is_closed = ticket.closed_at is not None
        ticket.status_id = new_status.id
        ticket.updated_at = datetime.utcnow()

        if new_status.is_closed:
            ticket.closed_at = datetime.utcnow()
        else:
            # переоткрытие
            ticket.closed_at = None

        # если закрываем без оператора — не блокируем (оператор уже назначен при создании)
        if not ticket.assignee_id:
            operator = self._pick_operator()
            if operator:
                ticket.assignee_id = operator.id

        self.tickets.save(ticket)
        self._log_status_change(ticket, new_status, user, note)
        self.db.commit()
        self.db.refresh(ticket)
        self._notify(ticket, f"status:{new_status.name}")
        return ticket

    # ---------- search ----------
    def search(self, user: User, params: TicketSearchIn):
        role = _role_name(user)
        if role not in INTERNAL_ROLES:
            # клиент ищет только среди своих
            return self.tickets.search(
                params.q, user.id, None, params.status_id,
                params.date_from, params.date_to,
                params.limit, params.offset,
            )
        return self.tickets.search(
            params.q, params.author_id, params.assignee_id, params.status_id,
            params.date_from, params.date_to, params.limit, params.offset,
        )

    def change_assignee(
            self,
            ticket_id: int,
            actor: User,
            new_assignee_id: int | None,
            note: str | None = None,
    ) -> Ticket:
        """
        Переназначение оператора на заявку.

        - actor с ролью admin/moderator — может назначить любого активного оператора
          либо снять оператора (new_assignee_id=None).
        - actor с ролью agent/support_agent — может только взять заявку себе
          (new_assignee_id должен совпадать с actor.id или быть None, если заявка уже его).
        """
        actor_role = _role_name(actor)
        if actor_role not in INTERNAL_ROLES:
            raise ForbiddenError("Переназначение доступно только поддержке")

        ticket = self.tickets.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Заявка не найдена")

        # --- запрет на изменение закрытой заявки ---
        if ticket.closed_at is not None:
            raise ForbiddenError("Нельзя переназначить оператора по закрытой заявке")

        # --- права ---
        is_manager = actor_role in {"moderator", "admin"}

        if not is_manager:
            # оператор может только взять себе / оставить как есть
            if new_assignee_id is None:
                # снять оператора может только менеджер
                raise ForbiddenError(
                    "Снять оператора с заявки может только модератор или администратор"
                )
            if new_assignee_id != actor.id:
                raise ForbiddenError(
                    "Оператор может назначить на заявку только себя"
                )

        # --- валидация нового исполнителя ---
        if new_assignee_id is not None:
            if new_assignee_id == ticket.author_id:
                raise ValidationError("Автор заявки не может быть её исполнителем")
            new_assignee = self.users.get_by_id(new_assignee_id)
            if not new_assignee:
                raise NotFoundError("Пользователь-исполнитель не найден")
            if not new_assignee.is_active:
                raise ValidationError("Нельзя назначить заблокированного пользователя")
            if _role_name(new_assignee) not in ASSIGNABLE_ROLE_NAMES:
                raise ValidationError(
                    "Исполнителем может быть только пользователь с ролью оператора"
                )

        # --- идемпотентность ---
        if ticket.assignee_id == new_assignee_id:
            raise ConflictError("Заявка уже закреплена за этим исполнителем")

        old_assignee_id = ticket.assignee_id

        # --- проверка нагрузки (для менеджера — предупреждение, не запрет) ---
        # Намеренно не ограничиваем: бизнес допускает ручное перераспределение.

        ticket.assignee_id = new_assignee_id
        ticket.updated_at = datetime.utcnow()

        self.tickets.save(ticket)
        self._log_assignee_change(ticket, actor, old_assignee_id, new_assignee_id, note)
        self.db.commit()
        self.db.refresh(ticket)
        self._notify(ticket, "assignee:changed")
        return ticket

    # ---------- новый helper ----------
    def _log_assignee_change(
            self,
            ticket: Ticket,
            actor: User,
            old_id: int | None,
            new_id: int | None,
            note: str | None,
    ) -> None:
        """
        Пишет событие переназначения в журнал (ticket_status_history).
        Статус заявки не меняется — фиксируем текущий status_id,
        чтобы не нарушать FK и сохранить хронологию.
        """
        old_user = self.users.get_by_id(old_id) if old_id else None
        new_user = self.users.get_by_id(new_id) if new_id else None

        old_name = old_user.full_name if old_user else "—"
        new_name = new_user.full_name if new_user else "—"

        summary = f"Исполнитель: {old_name} → {new_name}"
        if note:
            summary = f"{summary}. {note.strip()}"

        self.history.add(TicketStatusHistory(
            ticket_id=ticket.id,
            status_id=ticket.status_id,  # статус не меняем
            changed_by=actor.id,
            changed_at=datetime.utcnow(),
            note=summary,
        ))

    # ---------- search: operator ----------
    def search(self, user: User, params: TicketSearchIn) -> TicketSearchPage:
        role = _role_name(user)
        if role not in INTERNAL_ROLES:
            raise ForbiddenError("Поиск по каталогу доступен только поддержке")
        return self._run_search(params)

    # ---------- search: client (только свои) ----------
    def search_own(self, user: User, params: TicketSearchIn) -> TicketSearchPage:
        # принудительно ограничиваем author_id текущим пользователем
        scoped = params.model_copy(update={"author_id": user.id})
        return self._run_search(scoped)

    # ---------- common ----------
    def _run_search(self, params: TicketSearchIn) -> TicketSearchPage:
        rows = self.tickets.search(
            params.q, params.author_id, params.assignee_id, params.status_id,
            params.category_id, params.date_from, params.date_to,
            params.sort_by.value, params.sort_order.value,
            params.limit, params.offset,
        )
        total = self.tickets.count_search(
            params.q, params.author_id, params.assignee_id, params.status_id,
            params.category_id, params.date_from, params.date_to,
        )
        items = [
            TicketListOut(
                id=t.id,
                title=t.title,
                status_id=t.status_id,
                status_name=status_name,
                category_id=t.category_id,
                author_id=t.author_id,
                assignee_id=t.assignee_id,
                priority=t.priority,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t, status_name in rows
        ]
        return TicketSearchPage(
            total=total, limit=params.limit, offset=params.offset, items=items
        )
