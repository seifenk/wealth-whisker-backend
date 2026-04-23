"""
FastAPI 依赖项
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import verify_token
from app.models.user import User
from app.services.user_service import UserService

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前用户（必需认证）
    """
    if not credentials:
        raise UnauthorizedException("未提供认证令牌")

    token = credentials.credentials
    user_id = verify_token(token, token_type="access")

    if not user_id:
        raise UnauthorizedException("无效或过期的访问令牌")

    user_service = UserService(db)
    user = await user_service.get_by_id(UUID(user_id))

    if not user:
        raise UnauthorizedException("用户不存在")

    if not user.is_active:
        raise UnauthorizedException("账户已被禁用")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    获取当前用户（可选认证）
    """
    if not credentials:
        return None

    token = credentials.credentials
    user_id = verify_token(token, token_type="access")

    if not user_id:
        return None

    user_service = UserService(db)
    user = await user_service.get_by_id(UUID(user_id))

    if not user or not user.is_active:
        return None

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户（必需认证且账户活跃）
    """
    if not current_user.is_active:
        raise UnauthorizedException("账户已被禁用")
    return current_user


async def get_user_from_refresh_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从刷新令牌获取用户
    """
    if not credentials:
        raise UnauthorizedException("未提供刷新令牌")

    token = credentials.credentials
    user_id = verify_token(token, token_type="refresh")

    if not user_id:
        raise UnauthorizedException("无效的刷新令牌")

    user_service = UserService(db)
    user = await user_service.get_by_id(UUID(user_id))

    if not user:
        raise UnauthorizedException("用户不存在")

    if not user.is_active:
        raise UnauthorizedException("账户已被禁用")

    return user