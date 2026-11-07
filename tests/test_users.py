from tests.conftest import auth


def test_client_forbidden(client, client_token):
    assert client.get("/users", headers=auth(client_token)).status_code == 403


def test_admin_lists_users(client, admin_token):
    r = client.get("/users", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) >= 4


def test_admin_deactivates(client, admin_token, db):
    r = client.delete("/users/4", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is False
