import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.entities import User, UserRole, Status
from app.security import hash_password

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = TestingSession()

    # базовые роли
    session.add_all([
        UserRole(id=1, name="admin"),
        UserRole(id=2, name="agent"),
        UserRole(id=3, name="employee"),
    ])
    # базовые статусы (как в seed.sql)
    session.add_all([
        Status(id=1, name="open", is_closed=False),
        Status(id=2, name="in_progress", is_closed=False),
        Status(id=3, name="pending", is_closed=False),
        Status(id=4, name="resolved", is_closed=True),
        Status(id=5, name="closed", is_closed=True),
    ])
    # пользователи
    session.add_all([
        User(id=1, email="client@t.ru", full_name="Клиент", is_active=True,
             user_role=3, password_hash=hash_password("client")),
        User(id=2, email="op@t.ru", full_name="Оператор", is_active=True,
             user_role=2, password_hash=hash_password("operator")),
        User(id=3, email="admin@t.ru", full_name="Админ", is_active=True,
             user_role=1, password_hash=hash_password("admin")),
        User(id=4, email="blocked@t.ru", full_name="Блок", is_active=False,
             user_role=3, password_hash=hash_password("x")),
    ])
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def client_token(client):
    return _token(client, "client@t.ru", "client")


@pytest.fixture
def op_token(client):
    return _token(client, "op@t.ru", "operator")


@pytest.fixture
def admin_token(client):
    return _token(client, "admin@t.ru", "admin")


def auth(token):
    return {"Authorization": f"Bearer {token}"}
