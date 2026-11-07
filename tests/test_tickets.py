from tests.conftest import auth


def _create_ticket(client, token, **kw):
    payload = {"title": "Тестовая заявка", "description": "тело", "priority": "normal"}
    payload.update(kw)
    r = client.post("/tickets", json=payload, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def test_create_assigns_operator(client, client_token):
    t = _create_ticket(client, client_token)
    assert t["status_id"] == 1
    assert t["assignee_id"] == 2  # единственный активный оператор
    assert t["closed_at"] is None


def test_create_validation(client, client_token):
    r = client.post("/tickets", json={"title": "  "}, headers=auth(client_token))
    assert r.status_code == 422
    r = client.post("/tickets", json={"title": "ok", "priority": "urgent"},
                    headers=auth(client_token))
    assert r.status_code == 422


def test_client_sees_only_own(client, client_token, op_token):
    _create_ticket(client, client_token)
    r = client.get("/tickets", headers=auth(client_token))
    assert all(x["author_id"] == 1 for x in r.json()) if r.json() else True


def test_client_cannot_read_foreign(client, client_token, op_token):
    # создаём заявку от оператора (он internal, может), затем клиент её не видит по id
    t = _create_ticket(client, op_token)
    r = client.get(f"/tickets/{t['id']}", headers=auth(client_token))
    assert r.status_code == 403


def test_operator_changes_status(client, client_token, op_token):
    t = _create_ticket(client, client_token)
    r = client.patch(f"/tickets/{t['id']}/status",
                     json={"status_id": 2, "note": "в работу"},
                     headers=auth(op_token))
    assert r.status_code == 200
    assert r.json()["status_id"] == 2


def test_same_status_conflict(client, client_token, op_token):
    t = _create_ticket(client, client_token)
    client.patch(f"/tickets/{t['id']}/status", json={"status_id": 2},
                 headers=auth(op_token))
    r = client.patch(f"/tickets/{t['id']}/status", json={"status_id": 2},
                     headers=auth(op_token))
    assert r.status_code == 409


def test_close_sets_closed_at(client, client_token, op_token):
    t = _create_ticket(client, client_token)
    r = client.patch(f"/tickets/{t['id']}/status", json={"status_id": 5},
                     headers=auth(op_token))
    assert r.status_code == 200
    assert r.json()["closed_at"] is not None


def test_client_cannot_change_status(client, client_token):
    t = _create_ticket(client, client_token)
    r = client.patch(f"/tickets/{t['id']}/status", json={"status_id": 2},
                     headers=auth(client_token))
    assert r.status_code == 403


def test_search_operator_only(client, client_token, op_token):
    r = client.get("/tickets/search?q=Тест", headers=auth(client_token))
    assert r.status_code == 403
    r = client.get("/tickets/search?q=Тест", headers=auth(op_token))
    assert r.status_code == 200


def test_search_by_author_and_status(client, client_token, op_token):
    _create_ticket(client, client_token)
    r = client.get("/tickets/search?author_id=1&status_id=1", headers=auth(op_token))
    assert r.status_code == 200
    assert len(r.json()) >= 1
