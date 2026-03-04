"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

from database.connection import get_db
from database.models import User, Session
from services.auth_service import AuthService
from api.dependencies import get_current_user, security

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Request/Response Models

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user
    user = User(
        email=data.email,
        username=data.username,
        password_hash=AuthService.hash_password(data.password),
        full_name=data.full_name,
        role="user",
    )
    db.add(user)
    await db.flush()
    
    # Create tokens
    access_token = AuthService.create_access_token(user.id, user.email, user.role)
    refresh_token = AuthService.create_refresh_token(user.id)
    
    # Create session
    payload = AuthService.decode_token(access_token)
    session = Session(
        user_id=user.id,
        token_jti=payload["jti"],
        refresh_token=refresh_token,
        expires_at=datetime.fromtimestamp(payload["exp"]),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    await db.commit()
    await db.refresh(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.from_orm(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password."""
    # Get user
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user or not AuthService.verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    
    # Create tokens
    access_token = AuthService.create_access_token(user.id, user.email, user.role)
    refresh_token = AuthService.create_refresh_token(user.id)
    
    # Create session
    payload = AuthService.decode_token(access_token)
    session = Session(
        user_id=user.id,
        token_jti=payload["jti"],
        refresh_token=refresh_token,
        expires_at=datetime.fromtimestamp(payload["exp"]),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.from_orm(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout (invalidate current session)."""
    token = credentials.credentials
    payload = AuthService.decode_token(token)
    
    # Delete session
    await db.execute(
        delete(Session).where(Session.token_jti == payload["jti"])
    )
    await db.commit()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    payload = AuthService.decode_token(refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = AuthService.create_access_token(user.id, user.email, user.role)
    new_refresh_token = AuthService.create_refresh_token(user.id)
    
    # Update session
    new_payload = AuthService.decode_token(access_token)
    await db.execute(
        update(Session)
        .where(Session.token_jti == payload["jti"])
        .values(
            token_jti=new_payload["jti"],
            refresh_token=new_refresh_token,
            expires_at=datetime.fromtimestamp(new_payload["exp"]),
        )
    )
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.from_orm(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse.from_orm(user)
