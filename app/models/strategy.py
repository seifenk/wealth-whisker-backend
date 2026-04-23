"""
策略与回测相关数据模型
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class StrategyTemplate(Base, TimestampMixin):
    """策略模板表"""

    __tablename__ = "strategy_templates"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    code = Column(String(50), unique=True, nullable=False)  # 'ma_cross', 'momentum', 'dca'
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # 'trend', 'mean_reversion', 'portfolio'
    parameters = Column(JSONB, nullable=False)  # 参数定义
    is_public = Column(Boolean, default=True)

    # 关系
    user_strategies = relationship("UserStrategy", back_populates="template")


class UserStrategy(Base, TimestampMixin):
    """用户策略配置表"""

    __tablename__ = "user_strategies"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    template_id = Column(PG_UUID(as_uuid=True), ForeignKey("strategy_templates.id"))
    name = Column(String(100), nullable=False)
    parameters = Column(JSONB, nullable=False)  # 用户配置的参数值

    # 关系
    user = relationship("User", back_populates="strategies")
    template = relationship("StrategyTemplate", back_populates="user_strategies")
    backtest_jobs = relationship("BacktestJob", back_populates="strategy")


class BacktestJob(Base, TimestampMixin):
    """回测任务表"""

    __tablename__ = "backtest_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    strategy_id = Column(PG_UUID(as_uuid=True), ForeignKey("user_strategies.id"))
    status = Column(String(20), default="pending")  # 'pending', 'running', 'completed', 'failed'
    config = Column(JSONB, nullable=False)  # 资产、时间范围、初始资金等
    result = Column(JSONB, nullable=True)  # 回测结果
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    user = relationship("User", back_populates="backtest_jobs")
    strategy = relationship("UserStrategy", back_populates="backtest_jobs")
    result_detail = relationship("BacktestResult", back_populates="job", uselist=False)


class BacktestResult(Base, TimestampMixin):
    """回测结果详细表"""

    __tablename__ = "backtest_results"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("backtest_jobs.id", ondelete="CASCADE"))
    total_return = Column(Numeric(10, 4), nullable=True)
    annualized_return = Column(Numeric(10, 4), nullable=True)
    max_drawdown = Column(Numeric(10, 4), nullable=True)
    volatility = Column(Numeric(10, 4), nullable=True)
    sharpe_ratio = Column(Numeric(10, 4), nullable=True)
    win_rate = Column(Numeric(10, 4), nullable=True)
    total_trades = Column(Integer, nullable=True)
    profit_trades = Column(Integer, nullable=True)
    loss_trades = Column(Integer, nullable=True)
    metrics = Column(JSONB, nullable=True)  # 其他指标
    equity_curve = Column(JSONB, nullable=True)  # 资金曲线数据点
    trades = Column(JSONB, nullable=True)  # 交易记录

    # 关系
    job = relationship("BacktestJob", back_populates="result_detail")