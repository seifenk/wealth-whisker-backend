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
    __table_args__ = {'comment': '用户表 - 存储用户基础信息'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='用户ID')
    email = Column(String(255), unique=True, nullable=False, index=True, comment='邮箱地址')
    password_hash = Column(String(255), nullable=False, comment='密码哈希值')
    nickname = Column(String(100), nullable=True, comment='用户昵称')
    avatar_url = Column(String(500), nullable=True, comment='头像URL')
    risk_preference = Column(String(20), default="balanced", comment='风险偏好: conservative保守/balanced平衡/aggressive激进')
    is_active = Column(Boolean, default=True, comment='是否激活')
    disclaimer_accepted = Column(Boolean, default=False, comment='是否已确认免责声明')
    disclaimer_accepted_at = Column(DateTime(timezone=True), nullable=True, comment='免责声明确认时间')

    # 关系
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    achievements = relationship("UserAchievement", back_populates="user")
    paper_accounts = relationship("PaperAccount", back_populates="user")
    strategies = relationship("UserStrategy", back_populates="user")
    backtest_jobs = relationship("BacktestJob", back_populates="user")


class UserSettings(Base, TimestampMixin):
    """用户设置表"""

    __tablename__ = "user_settings"
    __table_args__ = {'comment': '用户设置表 - 存储用户个性化配置'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='设置ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, comment='用户ID')
    theme = Column(String(20), default="light", comment='界面主题: light/dark')
    notification_enabled = Column(Boolean, default=True, comment='是否启用通知')
    daily_report_enabled = Column(Boolean, default=False, comment='是否启用日报')
    language = Column(String(10), default="zh-CN", comment='界面语言')

    # 关系
    user = relationship("User", back_populates="settings")


class Achievement(Base, TimestampMixin):
    """成就定义表"""

    __tablename__ = "achievements"
    __table_args__ = {'comment': '成就定义表 - 存储成就类型和规则'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='成就ID')
    code = Column(String(50), unique=True, nullable=False, comment='成就代码: first_backtest首次回测/first_trade首次交易')
    name = Column(String(100), nullable=False, comment='成就名称')
    description = Column(Text, nullable=True, comment='成就描述')
    icon_url = Column(String(500), nullable=True, comment='成就图标URL')
    category = Column(String(50), nullable=True, comment='成就类别: trading交易/learning学习/social社交')
    points = Column(Integer, default=0, comment='成就积分')

    # 关系
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """用户成就记录表"""

    __tablename__ = "user_achievements"
    __table_args__ = {'comment': '用户成就记录表 - 记录用户解锁的成就'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='记录ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), comment='用户ID')
    achievement_id = Column(PG_UUID(as_uuid=True), ForeignKey("achievements.id"), comment='成就ID')
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now(), comment='解锁时间')

    # 关系
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")