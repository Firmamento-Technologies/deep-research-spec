"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import User
from services.auth_service import AuthService

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    return await AuthService.validate_token(token, db)


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return user


def require_role(required_role: str):
    """Dependency factory for role-based access control.
    
    Role hierarchy: viewer < user < admin
    """
    async def _check_role(user: User = Depends(get_current_user)) -> User:
        role_hierarchy = {"viewer": 1, "user": 2, "admin": 3}
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 999)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher"
            )
        return user
    
    return _check_role


# Convenience dependencies
require_admin = require_role("admin")
require_user = require_role("user")
require_viewer = require_role("viewer")
