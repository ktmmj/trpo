from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


# ---------- Auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- User ----------
class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    department: str | None
    is_active: bool
    user_role: int | None

    model_config = {"from_attributes": True}


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    user_role: int | None = None


# ---------- Ticket ----------
class TicketCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority = Priority.normal
    category_id: int | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Тема заявки не может быть пустой")
        return v.strip()


class TicketUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority | None = None
    category_id: int | None = None


class TicketStatusIn(BaseModel):
    status_id: int
    note: str | None = Field(default=None, max_length=1000)


class TicketDetailOut(BaseModel):
    id: int
    title: str
    description: str | None
    author_id: int
    assignee_id: int | None
    category_id: int | None
    status_id: int
    status_name: str
    priority: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TicketAssigneeIn(BaseModel):
    """Назначение/снятие оператора. assignee_id=None — снять оператора."""
    assignee_id: int | None = None
    note: str | None = Field(default=None, max_length=1000)


# ---------- Comment ----------
class CommentCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    is_internal: bool = False


class CommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    body: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Search ----------
class SortField(str, Enum):
    created_at = "created_at"
    updated_at = "updated_at"
    priority = "priority"
    status = "status"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class TicketSearchIn(BaseModel):
    q: str | None = Field(default=None, max_length=255)  # тема/тело
    author_id: int | None = None
    assignee_id: int | None = None
    status_id: int | None = None
    category_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_by: SortField = SortField.created_at
    sort_order: SortOrder = SortOrder.desc
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class TicketListOut(BaseModel):
    id: int
    title: str
    status_id: int
    status_name: str
    category_id: int | None
    author_id: int
    assignee_id: int | None
    priority: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketSearchPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TicketListOut]
