from __future__ import annotations
import pytest
from sqlalchemy import select

from app.models.entities import User, Ticket, TicketStatusHistory
from app.security import hash_password
from tests.test_full_scenario_01 import _auth, _login  # переиспользуем хелперы


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _make_operator(db, email: str, role_name_id: int = 2) -> User:
    u = User(
        email=email, full_name=email.split("@")[0],
        is_active=True, user_role=role_name_id,
        password_hash=hash_password("op-pw"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_client_and_ticket(client, db, operator_id: int | None = None) -> tuple[int, int, str]:
    """Создаёт клиента и его заявку. Возвращает (client_id, ticket_id, client_token)."""
    email, pwd = "c-assign@t.ru", "cl-pw"
    r = client.post("/auth/register", json={"email": email, "full_name": "Клиент A"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    db.execute(User.__table__.update().where(User.id == cid)
               .values(password_hash=hash_password(pwd)))
    db.commit()
    token = _login(client, email, pwd)

    r = client.post("/tickets", json={"title": "Заявка для переназначения"},
                    headers=_auth(token))
    assert r.status_code == 201, r.text
    return cid, r.json()["id"], token


# ---------------------------------------------------------------------------
# позитивные сценарии
# ---------------------------------------------------------------------------
def test_operator_takes_ticket_himself(client, db, admin_token):
    op = _make_operator(db, "op-self@t.ru")
    _, tid, _ = _make_client_and_ticket(client, db)
    op_token = _login(client, "op-self@t.ru", "op-pw")

    # сначала назначаем оператора на заявку (через менеджера), чтобы было что менять
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op.id},
                     headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] == op.id

    # оператор берёт себе (идемпотентность → 409)
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op.id},
                     headers=_auth(op_token))
    assert r.status_code == 409


def test_operator_cannot_assign_someone_else(client, db, admin_token):
    op1 = _make_operator(db, "op1@t.ru")
    op2 = _make_operator(db, "op2@t.ru")
    _, tid, _ = _make_client_and_ticket(client, db)
    op1_token = _login(client, "op1@t.ru", "op-pw")

    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op2.id},
                     headers=_auth(op1_token))
    assert r.status_code == 403, r.text


def test_admin_reassigns_and_unassigns(client, db, admin_token):
    op1 = _make_operator(db, "a1@t.ru")
    op2 = _make_operator(db, "a2@t.ru")
    _, tid, _ = _make_client_and_ticket(client, db, operator_id=op1.id)

    # назначаем op1
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op1.id, "note": "первичное назначение"},
                     headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["assignee_id"] == op1.id

    # переназначаем на op2
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op2.id, "note": "передача смены"},
                     headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["assignee_id"] == op2.id

    # снимаем оператора
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": None, "note": "снято"},
                     headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["assignee_id"] is None

    # журнал: три записи о смене исполнителя
    rows = db.execute(
        select(TicketStatusHistory).where(TicketStatusHistory.ticket_id == tid)
    ).scalars().all()
    notes = [h.note for h in rows]
    assert sum("Исполнитель" in (n or "") for n in notes) == 3
    assert any("передача смены" in (n or "") for n in notes)


def test_client_cannot_reassign(client, db):
    _, tid, client_token = _make_client_and_ticket(client, db)
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": 2},
                     headers=_auth(client_token))
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# негативные сценарии
# ---------------------------------------------------------------------------
def test_cannot_assign_inactive_operator(client, db, admin_token):
    """
    Нельзя назначить исполнителем заблокированного пользователя.

    Ключевые моменты, чтобы SQLite/SQLAlchemy не падали:
    - оператор создаётся СРАЗУ с is_active=False, без промежуточного
      активного состояния (иначе объект в identity map «протухает»
      после коммитов внутри _make_client_and_ticket и может дать
      DetachedInstanceError/InvalidRequestError при повторном flush);
    - за заблокированного оператора НЕ логинимся (AuthService.login
      корректно вернёт 403, но нам это здесь не нужно);
    - проверяем именно 422 от сервиса (ValidationError), а не 500/SQLite.
    """
    # --- создаём оператора сразу неактивным, без промежуточного коммита ---
    op = User(
        email="blocked-op@t.ru",
        full_name="Заблокированный Оператор",
        department="Support",
        is_active=False,                 # <-- сразу неактивен
        user_role=2,                     # agent (иначе будет 422 по роли)
        password_hash=hash_password("blocked-pw"),
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    operator_id = op.id
    assert operator_id is not None

    # sanity: пользователь реально заблокирован в БД
    db.expire_all()                      # сбрасываем identity map после коммитов сервиса
    persisted = db.get(User, operator_id)
    assert persisted is not None
    assert persisted.is_active is False

    # --- клиент и его заявка (без оператора: _pick_operator не найдёт активных) ---
    _, ticket_id, _ = _make_client_and_ticket(client, db)

    # --- админ пытается назначить заблокированного оператора ---
    r = client.patch(
        f"/tickets/{ticket_id}/assignee",
        json={"assignee_id": operator_id},
        headers=_auth(admin_token),
    )
    # Сервис должен вернуть 422 (ValidationError «Нельзя назначить
    # заблокированного пользователя»), а не 500 от SQLite.
    assert r.status_code == 422, r.text
    assert "заблокирован" in r.text.lower() or "blocked" in r.text.lower()

    # --- заявка не изменилась: assignee_id остался прежним (или None) ---
    db.expire_all()
    db_ticket = db.get(Ticket, ticket_id)
    assert db_ticket.assignee_id != operator_id

def test_cannot_assign_client_as_assignee(client, db, admin_token):
    _, tid, _ = _make_client_and_ticket(client, db)  # клиент = employee (role 3)
    client_id = db.get(Ticket, tid).author_id

    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": client_id},
                     headers=_auth(admin_token))
    assert r.status_code == 422, r.text


def test_cannot_assign_author_as_assignee(client, db, admin_token):
    # автор с ролью оператора — редкий, но возможный кейс
    email, pwd = "op-author@t.ru", "op-pw"
    u = User(email=email, full_name="Оп-автор", is_active=True,
             user_role=2, password_hash=hash_password(pwd))
    db.add(u)
    db.commit()
    db.refresh(u)

    token = _login(client, email, pwd)
    r = client.post("/tickets", json={"title": "Заявка от оператора"},
                    headers=_auth(token))
    assert r.status_code == 201
    tid = r.json()["id"]
    assert r.json()["author_id"] == u.id

    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": u.id},
                     headers=_auth(admin_token))
    assert r.status_code == 422, r.text


def test_cannot_reassign_closed_ticket(client, db, admin_token):
    op = _make_operator(db, "op-close@t.ru")
    _, tid, _ = _make_client_and_ticket(client, db)

    # закрываем заявку
    r = client.patch(f"/tickets/{tid}/status",
                     json={"status_id": 5},  # closed
                     headers=_auth(admin_token))
    assert r.status_code == 200

    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op.id},
                     headers=_auth(admin_token))
    assert r.status_code == 403, r.text


def test_assignee_nonexistent_user(client, db, admin_token):
    _, tid, _ = _make_client_and_ticket(client, db)
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": 999_999},
                     headers=_auth(admin_token))
    assert r.status_code == 404, r.text


def test_assignee_requires_operator_role(client, db, admin_token):
    # создаём пользователя с ролью employee (3) и пытаемся назначить
    u = User(email="emp@t.ru", full_name="Сотрудник", is_active=True,
             user_role=3, password_hash=hash_password("x"))
    db.add(u)
    db.commit()
    _, tid, _ = _make_client_and_ticket(client, db)

    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": u.id},
                     headers=_auth(admin_token))
    assert r.status_code == 422, r.text
