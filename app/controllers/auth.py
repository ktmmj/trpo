from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import RegisterIn, LoginIn, TokenOut, UserOut
from app.service.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    user, _raw_password = AuthService(db).register_client(
        data.email, data.full_name, data.department
    )
    return user


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    token = AuthService(db).login(data.email, data.password)
    return TokenOut(access_token=token)
