"""
数据库连接与会话管理

说明:
- `async_session_maker`: 供 FastAPI 请求使用,保留连接池(默认 QueuePool)
- `task_session_maker`: 供 Celery 任务使用,采用 NullPool(每次新建连接、用后即关)
  避免在 prefork + 多个 asyncio.run() 事件循环的场景下,连接池连接被跨事件循环复用，
  从而引发 asyncpg `InterfaceError: cannot perform operation: another operation is in progress`
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# 创建异步引擎(FastAPI 使用,保留连接池)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# 创建异步会话工厂
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 创建 Celery 任务专用引擎(NullPool: 不使用连接池,规避跨事件循环复用)
task_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,
)

# 创建 Celery 任务会话工厂
task_session_maker = sessionmaker(
    task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（自动commit）"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()  # 成功完成后自动commit
        except Exception:
            await session.rollback()
            raise