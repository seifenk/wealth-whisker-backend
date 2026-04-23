"""
用户服务层
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, UnauthorizedException, NotFoundException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.models.user import User, UserSettings
from app.schemas.auth import UserCreate, UserUpdate, PasswordChange


class UserService:
    """用户服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """根据ID获取用户"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_settings(self, user_id: UUID) -> Optional[User]:
        """根据ID获取用户（包含设置）"""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.settings))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """创建用户"""
        # 检查邮箱是否已存在
        existing_user = await self.get_by_email(user_data.email)
        if existing_user:
            raise ConflictException("该邮箱已被注册")

        # 创建用户
        user = User(
            email=user_data.email.lower(),
            password_hash=get_password_hash(user_data.password),
            nickname=user_data.nickname or user_data.email.split("@")[0],
        )
        self.db.add(user)
        await self.db.flush()

        # 创建用户设置
        user_settings = UserSettings(user_id=user.id)
        self.db.add(user_settings)
        await self.db.flush()

        return user

    async def authenticate(self, email: str, password: str) -> User:
        """验证用户登录"""
        user = await self.get_by_email(email)
        if not user:
            raise UnauthorizedException("邮箱或密码错误")
        if not user.is_active:
            raise UnauthorizedException("账户已被禁用")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedException("邮箱或密码错误")
        return user

    async def login(self, email: str, password: str) -> dict:
        """用户登录，返回 tokens"""
        user = await self.authenticate(email, password)

        # 生成 tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 30 * 60,  # 30 minutes in seconds
        }

    async def refresh_tokens(self, refresh_token: str) -> dict:
        """刷新 tokens"""
        user_id = verify_token(refresh_token, token_type="refresh")
        if not user_id:
            raise UnauthorizedException("无效的刷新令牌")

        user = await self.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedException("用户不存在或已被禁用")

        # 生成新的 tokens
        new_access_token = create_access_token(subject=str(user.id))
        new_refresh_token = create_refresh_token(subject=str(user.id))

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 30 * 60,
        }

    async def update_user(self, user_id: UUID, update_data: UserUpdate) -> User:
        """更新用户信息"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")

        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(user, field, value)

        await self.db.flush()
        return user

    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str
    ) -> None:
        """修改密码"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")

        if not verify_password(old_password, user.password_hash):
            raise UnauthorizedException("旧密码错误")

        user.password_hash = get_password_hash(new_password)
        await self.db.flush()

    async def accept_disclaimer(self, user_id: UUID) -> User:
        """确认免责声明"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")

        user.disclaimer_accepted = True
        user.disclaimer_accepted_at = datetime.utcnow()
        await self.db.flush()
        return user

    async def deactivate_user(self, user_id: UUID) -> None:
        """停用用户"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户不存在")

        user.is_active = False
        await self.db.flush()