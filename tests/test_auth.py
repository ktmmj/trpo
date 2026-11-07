from tests.conftest import auth


def test_login_ok(client):
    r = client.post("/auth/login", json={"email": "client@t.ru", "password": "client"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_bad_password(client):
    r = client.post("/auth/login", json={"email": "client@t.ru", "password": "wrong"})
    assert r.status_code == 403


def test_login_blocked(client):
    r = client.post("/auth/login", json={"email": "blocked@t.ru", "password": "x"})
    assert r.status_code == 403


def test_register_duplicate(client):
    client.post("/auth/register", json={"email": "some_client@t.ru", "full_name": "some client"})
    r = client.post("/auth/register", json={"email": "some_client@t.ru", "full_name": "some client"})
    print(r.json())
    assert r.status_code == 409


def test_register_invalid_email(client):
    r = client.post("/auth/register", json={"email": "bad", "full_name": "X"})
    assert r.status_code == 422


def test_password_is_hashed(client, db):
    client.post("/auth/register", json={"email": "n@t.ru", "full_name": "no name"})
    client.post("/auth/register", json={"email": "n@t.ru", "full_name": "no name"})
    from app.models.entities import User
    u = db.query(User).filter_by(email="n@t.ru").one()
    assert u.password_hash.startswith("pbkdf2_sha256$")
    assert "n@t.ru" not in (u.password_hash or "")
