"""
认证 API 路由
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    DisclaimerAccept,
    PasswordChange,
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="创建新用户账户",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """用户注册"""
    user_service = UserService(db)
    user = await user_service.create(user_data)
    await db.commit()
    await db.refresh(user)  # 刷新对象确保属性可用
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="用户登录",
    description="使用邮箱和密码登录，获取访问令牌",
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """用户登录"""
    user_service = UserService(db)
    tokens = await user_service.login(login_data.email, login_data.password)
    return tokens


@router.post(
    "/refresh",
    response_model=Token,
    summary="刷新令牌",
    description="使用刷新令牌获取新的访问令牌",
)
async def refresh_token(
    refresh_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """刷新令牌"""
    user_service = UserService(db)
    tokens = await user_service.refresh_tokens(refresh_data.refresh_token)
    return tokens


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
    description="获取当前登录用户的详细信息",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """获取当前用户信息"""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="更新用户信息",
    description="更新当前用户的个人信息",
)
async def update_user_info(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """更新用户信息"""
    user_service = UserService(db)
    user = await user_service.update_user(current_user.id, update_data)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="修改密码",
    description="修改当前用户的密码",
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """修改密码"""
    user_service = UserService(db)
    await user_service.change_password(
        current_user.id,
        password_data.old_password,
        password_data.new_password,
    )
    await db.commit()


@router.post(
    "/me/disclaimer",
    response_model=UserResponse,
    summary="确认免责声明",
    description="用户确认接受平台的免责声明",
)
async def accept_disclaimer(
    disclaimer_data: DisclaimerAccept,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """确认免责声明"""
    if not disclaimer_data.accepted:
        return current_user

    user_service = UserService(db)
    user = await user_service.accept_disclaimer(current_user.id)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="用户登出",
    description="用户登出（客户端应清除令牌）",
)
async def logout(
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    用户登出

    注意：JWT 令牌无法在服务端撤销，客户端需要自行清除令牌。
    如需实现真正的登出，可考虑使用 Redis 存储令牌黑名单。
    """
    # JWT 无法服务端撤销，客户端自行清除即可
    pass