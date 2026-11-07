from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, engine
from app.exceptions import DomainError
from app.controllers import auth, comments, health, tickets, users

settings = get_settings()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(comments.router)
app.include_router(users.router)
