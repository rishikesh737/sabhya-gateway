import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.database import get_db
from app.models import User

log = structlog.get_logger()
router = APIRouter()


# --- Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# --- Endpoints ---


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # 1. Check if email exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        role="user",
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        log.info("user_registered", user_id=new_user.id, email=new_user.email)
        return new_user
    except Exception as e:
        log.error("registration_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Log in to get a JWT token."""
    # 1. Find user
    user = db.query(User).filter(User.email == form_data.username).first()

    # 2. Verify password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Create Token
    access_token = create_access_token(
        data={"sub": user.email, "roles": [user.role]},
    )

    log.info("user_logged_in", email=user.email)
    return {"access_token": access_token, "token_type": "bearer"}
