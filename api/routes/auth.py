# api/routes/auth.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select
import bcrypt
import jwt

from config import settings
from models.db import User
from api.dependencies import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    email: str

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

@router.post("/register", response_model=Token)
def register(user_data: UserRegister, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == user_data.email)).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = _hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed_password)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": new_user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer", email=new_user.email)

@router.post("/login", response_model=Token)
def login(user_data: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == user_data.email)).first()
    if not user or not _verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer", email=user.email)
