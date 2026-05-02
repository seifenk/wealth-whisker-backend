"""
测试配置和fixtures

提供测试所需的：
- 数据库测试fixture（隔离测试数据库）
- Redis测试fixture
- 测试用户fixture
- 测试客户端fixture
"""
import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.main import app
from app.models.base import Base
from app.models.user import User, UserSettings
from app.models.asset import Asset, OHLCV, AssetMetric
from app.models.strategy import StrategyTemplate, UserStrategy, BacktestJob, BacktestResult
from app.models.paper_trading import PaperAccount, Position, Order, Transaction, AccountSnapshot
from app.models.research import ResearchCard, ModelPrediction, ModelCalibrationLog, DisclaimerVersion
from app.models.news import NewsArticle, SentimentSnapshot, MacroIndicator
from app.services.cache_service import CacheService


# 测试数据库配置（使用独立测试数据库）
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/wealthwhisker_test"
)

# 创建测试引擎（使用NullPool避免连接池问题）
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,  # 测试环境使用NullPool避免连接池问题
)

# 创建测试会话工厂
test_async_session_maker = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    创建事件循环，整个测试session共享
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    创建测试数据库会话
    - 每个测试函数独立的数据库会话
    - 测试前清理所有数据
    - 测试后回滚所有更改
    """
    # 先清理所有表（确保测试环境干净）
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # 再创建所有表
        await conn.run_sync(Base.metadata.create_all)

    # 创建会话
    async with test_async_session_maker() as session:
        # 开始事务
        await session.begin()

        yield session

        # 测试结束后回滚（清理数据）
        await session.rollback()

    # 清理所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[CacheService, None]:
    """
    创建Redis测试客户端
    - 使用独立的Redis测试数据库（DB 15）
    - 测试后清理所有缓存数据
    """
    # 创建Redis客户端（使用DB 15作为测试数据库）
    cache_service = CacheService(redis_url="redis://localhost:6379/15")

    yield cache_service

    # 测试结束后清理所有缓存
    await cache_service.clear_all()
    await cache_service.close()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """
    创建测试用户
    - 每个测试函数独立的测试用户
    - 自动创建UserSettings
    """
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("Test123456"),
        nickname="测试用户",
        risk_preference="balanced",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # 创建用户设置
    user_settings = UserSettings(user_id=user.id)
    db_session.add(user_settings)
    await db_session.flush()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope="function")
async def test_superuser(db_session: AsyncSession) -> User:
    """
    创建测试超级用户
    """
    user = User(
        email="admin@example.com",
        password_hash=get_password_hash("Admin123456"),
        nickname="管理员",
        risk_preference="aggressive",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # 创建用户设置
    user_settings = UserSettings(user_id=user.id)
    db_session.add(user_settings)
    await db_session.flush()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    创建测试客户端（无需认证）
    - 用于测试游客访问模式
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """
    创建已认证的测试客户端
    - 自动登录测试用户并附加JWT token
    """
    from app.core.security import create_access_token

    # 生成access token（subject应该是user_id）
    access_token = create_access_token(subject=str(test_user.id))

    # 创建带认证头的客户端
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"}
    ) as ac:
        yield ac


@pytest.fixture
def test_user_data() -> dict:
    """
    测试用户注册数据
    """
    return {
        "email": "newuser@example.com",
        "password": "NewUser123456",
        "nickname": "新用户",
        "risk_preference": "conservative",
    }


@pytest.fixture
def test_login_data() -> dict:
    """
    测试登录数据
    """
    return {
        "email": "test@example.com",
        "password": "Test123456",
    }


# 覆盖依赖注入的fixture
@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session: AsyncSession):
    """
    覆盖get_db依赖，使用测试数据库会话
    """
    from app.core.database import get_db

    async def _get_db_override():
        yield db_session

    # 保存原有的覆盖
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db_override
    yield
    # 恢复原有的覆盖，而不是清除所有
    app.dependency_overrides = original_overrides


@pytest_asyncio.fixture(scope="function")
async def override_cache_service(redis_client: CacheService):
    """
    覆盖cache_service依赖，使用测试Redis客户端
    """
    from app.services.asset_service import get_cache_service

    def _get_cache_service_override():
        return redis_client

    # 保存原有的覆盖
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_cache_service] = _get_cache_service_override
    yield
    # 恢复原有的覆盖，而不是清除所有
    app.dependency_overrides = original_overrides


# 工具函数
def assert_response_code(response_data: dict, expected_code: int = 200):
    """
    验证响应code字段
    """
    assert response_data.get("code") == expected_code, \
        f"Expected code {expected_code}, got {response_data.get('code')}"


def assert_response_has_data(response_data: dict):
    """
    验证响应包含data字段
    """
    assert "data" in response_data, "Response missing 'data' field"
    assert response_data["data"] is not None, "Response 'data' field is None"