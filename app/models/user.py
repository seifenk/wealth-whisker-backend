"""
用户相关数据模型
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    risk_preference = Column(String(20), default="balanced")  # conservative/balanced/aggressive
    is_active = Column(Boolean, default=True)
    disclaimer_accepted = Column(Boolean, default=False)
    disclaimer_accepted_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    achievements = relationship("UserAchievement", back_populates="user")
    paper_accounts = relationship("PaperAccount", back_populates="user")
    strategies = relationship("UserStrategy", back_populates="user")
    backtest_jobs = relationship("BacktestJob", back_populates="user")


class UserSettings(Base, TimestampMixin):
    """用户设置表"""

    __tablename__ = "user_settings"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    theme = Column(String(20), default="light")
    notification_enabled = Column(Boolean, default=True)
    daily_report_enabled = Column(Boolean, default=False)
    language = Column(String(10), default="zh-CN")

    # 关系
    user = relationship("User", back_populates="settings")


class Achievement(Base, TimestampMixin):
    """成就定义表"""

    __tablename__ = "achievements"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    code = Column(String(50), unique=True, nullable=False)  # 'first_backtest', 'first_trade'
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)
    category = Column(String(50), nullable=True)  # 'trading', 'learning', 'social'
    points = Column(Integer, default=0)

    # 关系
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """用户成就记录表"""

    __tablename__ = "user_achievements"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    achievement_id = Column(PG_UUID(as_uuid=True), ForeignKey("achievements.id"))
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")