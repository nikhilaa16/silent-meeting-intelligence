"""
JWT Authentication Module
==========================

Implements full JWT-based authentication with:
  - User registration (POST /auth/register)
  - User login      (POST /auth/login)  → returns JWT access token
  - Protected routes via get_current_user() dependency
  - Role-based access: "admin" and "viewer" roles

Why JWT over simple API Key?
  - JWT is stateless: no session storage needed on the server
  - JWT carries user identity (user_id, email, role) inside the token
  - Tokens expire automatically (configurable via JWT_EXPIRE_MINUTES)
  - Industry standard for modern REST APIs

Token Flow:
  1. User calls POST /auth/login with email + password
  2. Server validates credentials, generates a signed JWT token
  3. Client stores the token and sends it as: Authorization: Bearer <token>
  4. Every protected endpoint calls get_current_user() which decodes the token
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, get_db

# ─────────────────────────────────────────────
# Password Hashing
# ─────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─────────────────────────────────────────────
# User Database Model
# ─────────────────────────────────────────────

class UserDB(Base):
    """Users table — stores registered user accounts."""
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email         = Column(String, unique=True, nullable=False, index=True)
    full_name     = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role          = Column(String, default="viewer")   # "admin" or "viewer"
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "viewer"   # "admin" or "viewer"

class UserLoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds
    user_id: str
    email: str
    role: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# JWT Token Functions
# ─────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    """
    Create a signed JWT access token.

    The token payload contains:
      - sub: user email (subject)
      - user_id: user's UUID
      - role: "admin" or "viewer"
      - exp: expiry timestamp (auto-checked by jose on decode)
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises HTTPException 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────
# FastAPI Security Dependency
# ─────────────────────────────────────────────

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserDB:
    """
    FastAPI dependency — validates JWT token and returns the current user.

    Usage on any protected endpoint:
        @app.get("/protected")
        def my_route(current_user: UserDB = Depends(get_current_user)):
            return {"hello": current_user.email}
    """
    payload = decode_token(credentials.credentials)
    email: str = payload.get("sub")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identity.",
        )

    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Please register.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )
    return user


def require_admin(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """
    FastAPI dependency — requires the current user to have the 'admin' role.

    Usage:
        @app.delete("/meetings/{id}")
        def delete(current_user: UserDB = Depends(require_admin)):
            ...
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This action requires admin privileges.",
        )
    return current_user


# ─────────────────────────────────────────────
# Auth Route Handlers (registered in main.py)
# ─────────────────────────────────────────────

def register_user(request: UserRegisterRequest, db: Session) -> UserResponse:
    """Register a new user. Raises 409 if email already exists."""
    existing = db.query(UserDB).filter(UserDB.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{request.email}' already exists.",
        )

    user = UserDB(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hash_password(request.password),
        role=request.role if request.role in ["admin", "viewer"] else "viewer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(request: UserLoginRequest, db: Session) -> TokenResponse:
    """Authenticate user and return a JWT access token."""
    user = db.query(UserDB).filter(UserDB.email == request.email).first()

    # Use constant-time comparison to prevent timing attacks
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id,
        "role": user.role,
    })

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )
