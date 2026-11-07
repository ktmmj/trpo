class DomainError(Exception):
    status_code = 400
    message = "Ошибка"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotFoundError(DomainError):
    status_code = 404
    message = "Объект не найден"


class ForbiddenError(DomainError):
    status_code = 403
    message = "Недостаточно прав"


class ConflictError(DomainError):
    status_code = 409
    message = "Конфликт данных"


class ValidationError(DomainError):
    status_code = 422
    message = "Некорректные данные"
