from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["health"])
settings = get_settings()

_started_at = datetime.now(timezone.utc)


@router.get("/health")
def health():
    """
    Liveness: приложение запущено и отвечает на HTTP.
    Никогда не трогает БД — чтобы не падать при её временной недоступности.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "uptime_seconds": int((datetime.now(timezone.utc) - _started_at).total_seconds()),
    }


@router.get("/health/ready")
def readiness(response: Response, db: Session = Depends(get_db)):
    """
    Readiness: приложение готово принимать трафик — БД отвечает.
    Возвращает 200, если всё ок, 503 — если зависимость недоступна.
    """
    db_ok = True
    db_error: str | None = None

    if settings.health_check_db:
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            db_ok = False
            db_error = str(exc)

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "checks": {
            "database": {"ok": db_ok, "error": db_error},
        },
    }
