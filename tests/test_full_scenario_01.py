"""
Полный сквозной сценарий по ТЗ ServiceDesk.

1. Создать оператора
2. Создать клиента
3. Авторизоваться за клиента
4. Создать заявку от имени клиента
4a. Оператор назначает заявку САМ СЕБЕ   (PATCH /tickets/{id}/assignee)
5. Добавить в заявку комментарий (клиент)
6. Авторизоваться за оператора
7. Установить категорию заявки (оператор)
8. Ответить на комментарий клиента (оператор)

Тест самодостаточен: использует фикстуры conftest.py
(db, client, admin_token). Автозакрепление при создании заявки
намеренно не проверяется — оператор берёт заявку явно.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.entities import (
    User, Ticket, Comment, Category, TicketStatusHistory,
)
from app.security import hash_password


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return r.json()["access_token"]


def _set_password(db, user_id: int, password: str) -> None:
    """Каркас не отдаёт пароль после регистрации — фиксируем его в БД."""
    db.execute(
        User.__table__.update()
        .where(User.id == user_id)
        .values(password_hash=hash_password(password))
    )
    db.commit()


# ---------------------------------------------------------------------------
# Основной сценарий
# ---------------------------------------------------------------------------
def test_full_lifecycle_operator_takes_ticket(client, db, admin_token):
    """
    Клиент создаёт заявку → оператор берёт её себе →
    клиент комментирует → оператор назначает категорию и отвечает.
    """

    # ------------------------------------------------------------------
    # Шаг 0: категория, которую оператор назначит на шаге 7.
    # ------------------------------------------------------------------
    category = Category(name="Тестовая категория")
    db.add(category)
    db.commit()
    db.refresh(category)
    category_id = category.id

    # ------------------------------------------------------------------
    # Шаг 1: Создать оператора
    # Роль 2 = 'agent' — именно её видит _pick_operator,
    # и именно её требует change_assignee (ASSIGNABLE_ROLE_NAMES).
    # ------------------------------------------------------------------
    operator_email = "operator.full@t.ru"
    operator_password = "op-secret-42"

    op = User(
        email=operator_email,
        full_name="Оператор Полный",
        department="Support",
        is_active=True,
        user_role=2,                       # agent
        password_hash=hash_password(operator_password),
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    operator_id = op.id

    r = client.get(f"/users/{operator_id}", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["user_role"] == 2
    assert r.json()["is_active"] is True

    # ------------------------------------------------------------------
    # Шаг 2: Создать клиента
    # ------------------------------------------------------------------
    client_email = "client.full@t.ru"
    client_password = "cl-secret-42"

    r = client.post(
        "/auth/register",
        json={
            "email": client_email,
            "full_name": "Клиент Полный",
            "department": "Sales",
        },
    )
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]
    assert r.json()["user_role"] == 3      # employee
    assert r.json()["is_active"] is True

    _set_password(db, client_id, client_password)

    # ------------------------------------------------------------------
    # Шаг 3: Авторизоваться за клиента
    # ------------------------------------------------------------------
    client_token = _login(client, client_email, client_password)
    assert client_token

    # ------------------------------------------------------------------
    # Шаг 4: Создать заявку от имени клиента
    # На этом шаге НЕ проверяем assignee_id: он зависит от того,
    # какие операторы уже есть в БД (в conftest может быть op@t.ru).
    # Нас интересует, что заявка создана и имеет статус 'open'.
    # ------------------------------------------------------------------
    ticket_payload = {
        "title": "Не открывается 1С после обновления",
        "description": "После обновления ОС 1С падает с ошибкой 0x80070005.",
        "priority": "high",
    }
    r = client.post("/tickets", json=ticket_payload, headers=_auth(client_token))
    assert r.status_code == 201, r.text
    ticket = r.json()

    assert ticket["title"] == ticket_payload["title"]
    assert ticket["author_id"] == client_id
    assert ticket["status_id"] == 1                          # open
    assert ticket["category_id"] is None
    assert ticket["closed_at"] is None

    ticket_id = ticket["id"]
    initial_assignee_id = ticket["assignee_id"]              # может быть кем угодно (или None)

    # ------------------------------------------------------------------
    # Шаг 4a: Оператор назначает заявку САМ СЕБЕ
    # Оператор логинится здесь же, чтобы отделить «взятие заявки»
    # от последующей работы (шаги 6–8).
    # ------------------------------------------------------------------
    operator_token_early = _login(client, operator_email, operator_password)

    r = client.patch(
        f"/tickets/{ticket_id}/assignee",
        json={"assignee_id": operator_id, "note": "Беру заявку в работу"},
        headers=_auth(operator_token_early),
    )
    assert r.status_code == 200, r.text
    after_assign = r.json()
    assert after_assign["assignee_id"] == operator_id, (
        f"ожидали assignee_id={operator_id}, получили {after_assign['assignee_id']}"
    )
    assert after_assign["status_id"] == 1                    # статус не изменился
    assert after_assign["category_id"] is None               # категорию ещё не ставили

    # В БД зафиксировано назначение и есть запись в журнале
    db_ticket = db.get(Ticket, ticket_id)
    assert db_ticket.assignee_id == operator_id

    hist = db.execute(
        select(TicketStatusHistory)
        .where(TicketStatusHistory.ticket_id == ticket_id)
        .order_by(TicketStatusHistory.id)
    ).scalars().all()
    # минимум: 'Заявка создана' + 'Исполнитель: ... → Оператор Полный. Беру заявку в работу'
    assert any(
        (h.note or "").startswith("Исполнитель:")
        and "Оператор Полный" in (h.note or "")
        and "Беру заявку в работу" in (h.note or "")
        for h in hist
    ), f"в истории нет события переназначения: {[h.note for h in hist]}"

    # ------------------------------------------------------------------
    # Шаг 5: Клиент добавляет комментарий
    # ------------------------------------------------------------------
    client_comment_body = "Уточняю: ошибка возникает только у нового сотрудника."
    r = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": client_comment_body, "is_internal": False},
        headers=_auth(client_token),
    )
    assert r.status_code == 201, r.text
    client_comment = r.json()
    assert client_comment["ticket_id"] == ticket_id
    assert client_comment["author_id"] == client_id
    assert client_comment["body"] == client_comment_body
    assert client_comment["is_internal"] is False
    client_comment_id = client_comment["id"]

    # Клиент видит свой комментарий
    r = client.get(f"/tickets/{ticket_id}/comments", headers=_auth(client_token))
    assert r.status_code == 200
    assert any(c["id"] == client_comment_id for c in r.json())

    # ------------------------------------------------------------------
    # Шаг 6: Авторизоваться за оператора
    # (уже логинились на шаге 4a — перелогин, чтобы явно пройти шаг 6)
    # ------------------------------------------------------------------
    operator_token = _login(client, operator_email, operator_password)
    assert operator_token

    # Оператор видит заявку и назначен на неё
    r = client.get(f"/tickets/{ticket_id}", headers=_auth(operator_token))
    assert r.status_code == 200, r.text
    assert r.json()["author_id"] == client_id
    assert r.json()["assignee_id"] == operator_id

    # Оператор видит публичный комментарий клиента
    r = client.get(f"/tickets/{ticket_id}/comments", headers=_auth(operator_token))
    assert r.status_code == 200
    assert any(c["id"] == client_comment_id for c in r.json())

    # ------------------------------------------------------------------
    # Шаг 7: Установить категорию заявки (оператор)
    # ------------------------------------------------------------------
    r = client.patch(
        f"/tickets/{ticket_id}",
        json={"category_id": category_id},
        headers=_auth(operator_token),
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["category_id"] == category_id
    assert updated["status_id"] == 1                         # статус не тронут
    assert updated["assignee_id"] == operator_id             # исполнитель не сменился

    db_ticket = db.get(Ticket, ticket_id)
    assert db_ticket.category_id == category_id

    # ------------------------------------------------------------------
    # Шаг 8: Ответить на комментарий клиента (оператор)
    # ------------------------------------------------------------------
    operator_reply_body = (
        "Проверил: проблема в правах доступа к каталогу 1С. "
        "Выдал права новому сотруднику, попросите перезайти."
    )
    r = client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": operator_reply_body, "is_internal": False},
        headers=_auth(operator_token),
    )
    assert r.status_code == 201, r.text
    operator_comment = r.json()
    assert operator_comment["ticket_id"] == ticket_id
    assert operator_comment["author_id"] == operator_id
    assert operator_comment["body"] == operator_reply_body
    assert operator_comment["is_internal"] is False

    # ------------------------------------------------------------------
    # Финальные проверки: обе стороны видят диалог, порядок правильный
    # ------------------------------------------------------------------
    for token, who in [(client_token, "client"), (operator_token, "operator")]:
        r = client.get(f"/tickets/{ticket_id}/comments", headers=_auth(token))
        assert r.status_code == 200, r.text
        bodies = [c["body"] for c in r.json()]
        assert client_comment_body in bodies, f"{who} не видит комментарий клиента"
        assert operator_reply_body in bodies, f"{who} не видит ответ оператора"
        assert bodies.index(client_comment_body) < bodies.index(operator_reply_body), (
            f"{who}: порядок комментариев нарушен"
        )

    rows = db.execute(
        select(Comment).where(Comment.ticket_id == ticket_id)
    ).scalars().all()
    assert len(rows) == 2
    assert {c.author_id for c in rows} == {client_id, operator_id}

    # Итоговое состояние заявки в БД
    db_ticket = db.get(Ticket, ticket_id)
    assert db_ticket.assignee_id == operator_id
    assert db_ticket.category_id == category_id
    assert db_ticket.status_id == 1
    assert db_ticket.closed_at is None


# ---------------------------------------------------------------------------
# Дополнительные кейсы вокруг «взятия заявки себе»
# ---------------------------------------------------------------------------
def test_operator_cannot_take_someone_elses_ticket(client, db, admin_token):
    """Оператор не может назначить заявку на ДРУГОГО оператора."""
    op1_email, op1_pw = "op1.full@t.ru", "pw1"
    op2_email, op2_pw = "op2.full@t.ru", "pw2"

    for email, pw in [(op1_email, op1_pw), (op2_email, op2_pw)]:
        u = User(email=email, full_name=email, is_active=True,
                 user_role=2, password_hash=hash_password(pw))
        db.add(u)
    db.commit()
    op2 = db.scalar(select(User).where(User.email == op2_email))

    # клиент и его заявка
    cemail, cpw = "c-x@t.ru", "cw"
    r = client.post("/auth/register", json={"email": cemail, "full_name": "Client 01"})
    cid = r.json()["id"]
    _set_password(db, cid, cpw)
    ctok = _login(client, cemail, cpw)
    tid = client.post("/tickets", json={"title": "Чужая заявка"},
                      headers=_auth(ctok)).json()["id"]

    op1_tok = _login(client, op1_email, op1_pw)
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op2.id},
                     headers=_auth(op1_tok))
    assert r.status_code == 403, r.text


def test_operator_take_same_ticket_twice_conflict(client, db, admin_token):
    """Повторное назначение себя тем же оператором → 409 (идемпотентности нет)."""
    op_email, op_pw = "self-conf@t.ru", "pw"
    db.add(User(email=op_email, full_name="Self", is_active=True,
                user_role=2, password_hash=hash_password(op_pw)))
    db.commit()
    op = db.scalar(select(User).where(User.email == op_email))

    cemail, cpw = "c-conf@t.ru", "cw"
    cid = client.post("/auth/register", json={"email": cemail, "full_name": "Client 02"}).json()["id"]
    _set_password(db, cid, cpw)
    ctok = _login(client, cemail, cpw)
    tid = client.post("/tickets", json={"title": "Двойное взятие"},
                      headers=_auth(ctok)).json()["id"]

    op_tok = _login(client, op_email, op_pw)

    r1 = client.patch(f"/tickets/{tid}/assignee",
                      json={"assignee_id": op.id}, headers=_auth(op_tok))
    assert r1.status_code == 200
    r2 = client.patch(f"/tickets/{tid}/assignee",
                      json={"assignee_id": op.id}, headers=_auth(op_tok))
    assert r2.status_code == 409, r2.text


def test_operator_cannot_take_closed_ticket(client, db, admin_token):
    """Нельзя взять закрытую заявку."""
    op_email, op_pw = "closed-op@t.ru", "pw"
    db.add(User(email=op_email, full_name="Closed", is_active=True,
                user_role=2, password_hash=hash_password(op_pw)))
    db.commit()
    op = db.scalar(select(User).where(User.email == op_email))

    cemail, cpw = "c-closed@t.ru", "cw"
    cid = client.post("/auth/register", json={"email": cemail, "full_name": "Client 03"}).json()["id"]
    _set_password(db, cid, cpw)
    ctok = _login(client, cemail, cpw)
    tid = client.post("/tickets", json={"title": "Закрытая"},
                      headers=_auth(ctok)).json()["id"]

    # закрываем от имени админа
    r = client.patch(f"/tickets/{tid}/status",
                     json={"status_id": 5}, headers=_auth(admin_token))
    assert r.status_code == 200

    op_tok = _login(client, op_email, op_pw)
    r = client.patch(f"/tickets/{tid}/assignee",
                     json={"assignee_id": op.id}, headers=_auth(op_tok))
    assert r.status_code == 403, r.text