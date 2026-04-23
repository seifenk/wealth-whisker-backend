"""
SQLAlchemy 基础模型
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明式基类"""

    pass


class TimestampMixin:
    """时间戳混入类"""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


def generate_uuid() -> UUID:
    """生成UUID"""
    from uuid import uuid4
    return uuid4()