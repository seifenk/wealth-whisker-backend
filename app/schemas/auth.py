"""
认证相关 Pydantic 模型
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.enums import RiskPreference


class UserCreate(BaseModel):
    """用户注册请求"""

    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    nickname: Optional[str] = Field(None, max_length=100, description="昵称")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度"""
        if not any(c.isupper() for c in v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not any(c.islower() for c in v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""

    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户信息响应"""

    id: UUID
    email: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    risk_preference: RiskPreference = RiskPreference.BALANCED
    is_active: bool = True
    disclaimer_accepted: bool = False
    disclaimer_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Token 响应"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间(秒)")


class TokenRefresh(BaseModel):
    """Token 刷新请求"""

    refresh_token: str = Field(..., description="刷新令牌")


class TokenPayload(BaseModel):
    """Token 载荷"""

    sub: str = Field(..., description="用户ID")
    exp: int = Field(..., description="过期时间戳")
    type: str = Field(..., description="令牌类型")


class UserUpdate(BaseModel):
    """用户信息更新请求"""

    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像URL")
    risk_preference: Optional[RiskPreference] = Field(None, description="风险偏好")


class PasswordChange(BaseModel):
    """密码修改请求"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度"""
        if not any(c.isupper() for c in v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not any(c.islower() for c in v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        return v


class DisclaimerAccept(BaseModel):
    """免责声明确认请求"""

    accepted: bool = Field(..., description="是否确认免责声明")