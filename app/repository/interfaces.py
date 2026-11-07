from abc import ABC, abstractmethod
from typing import Sequence
from datetime import datetime
from app.models.entities import User, Ticket, Comment, Status, TicketStatusHistory


class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def list(self, limit: int = 50, offset: int = 0) -> Sequence[User]: ...

    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def save(self, user: User) -> User: ...


class ITicketRepository(ABC):
    @abstractmethod
    def get_by_id(self, ticket_id: int) -> Ticket | None: ...

    @abstractmethod
    def add(self, ticket: Ticket) -> Ticket: ...

    @abstractmethod
    def save(self, ticket: Ticket) -> Ticket: ...

    @abstractmethod
    def list_by_author(self, author_id: int) -> Sequence[Ticket]: ...

    @abstractmethod
    def search(
            self,
            q: str | None,
            author_id: int | None,
            assignee_id: int | None,
            status_id: int | None,
            date_from: datetime | None,
            date_to: datetime | None,
            limit: int,
            offset: int,
    ) -> Sequence[Ticket]: ...


class ICommentRepository(ABC):
    @abstractmethod
    def add(self, comment: Comment) -> Comment: ...

    @abstractmethod
    def list_by_ticket(self, ticket_id: int) -> Sequence[Comment]: ...


class IStatusRepository(ABC):
    @abstractmethod
    def get_by_id(self, status_id: int) -> Status | None: ...

    @abstractmethod
    def list(self) -> Sequence[Status]: ...


class IHistoryRepository(ABC):
    @abstractmethod
    def add(self, entry: TicketStatusHistory) -> TicketStatusHistory: ...

    @abstractmethod
    def list_by_ticket(self, ticket_id: int) -> Sequence[TicketStatusHistory]: ...

    @abstractmethod
    def list_all(self, limit: int = 1000) -> Sequence[TicketStatusHistory]: ...
