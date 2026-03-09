"""Authentication and authorization service."""

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Session
from config.settings import settings


logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and authorization service."""
    
    SECRET_KEY = os.getenv("JWT_SECRET_KEY") or settings.jwt_secret_key
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days

    if not SECRET_KEY:
        SECRET_KEY = uuid.uuid4().hex
        logger.warning("JWT_SECRET_KEY not configured: using ephemeral in-memory secret")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_id: str, email: str, role: str) -> str:
        """Create JWT access token."""
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=AuthService.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM)
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create JWT refresh token."""
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=AuthService.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                AuthService.SECRET_KEY,
                algorithms=[AuthService.ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def validate_token(token: str, db: AsyncSession) -> User:
        """Validate token and return user."""
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")
        
        # Check if session exists and is valid
        result = await db.execute(
            select(Session).where(
                Session.token_jti == payload.get("jti"),
                Session.expires_at > datetime.utcnow(),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
