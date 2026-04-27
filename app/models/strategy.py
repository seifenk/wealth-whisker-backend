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
    __table_args__ = {'comment': '策略模板表 - 存储预定义的策略模板(均线突破/动量轮动/定投/风险平价)'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='模板ID')
    code = Column(String(50), unique=True, nullable=False, comment='策略代码: ma_cross均线突破/momentum动量轮动/dca定投/risk_parity风险平价')
    name = Column(String(100), nullable=False, comment='策略名称')
    description = Column(Text, nullable=True, comment='策略描述')
    category = Column(String(50), nullable=True, comment='策略类别: trend趋势/mean_reversion均值回归/portfolio组合')
    parameters = Column(JSONB, nullable=False, comment='参数定义JSON')
    is_public = Column(Boolean, default=True, comment='是否公开')

    # 关系
    user_strategies = relationship("UserStrategy", back_populates="template")


class UserStrategy(Base, TimestampMixin):
    """用户策略配置表"""

    __tablename__ = "user_strategies"
    __table_args__ = {'comment': '用户策略配置表 - 存储用户自定义的策略参数配置'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='策略配置ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), comment='用户ID')
    template_id = Column(PG_UUID(as_uuid=True), ForeignKey("strategy_templates.id"), comment='模板ID')
    name = Column(String(100), nullable=False, comment='策略名称')
    parameters = Column(JSONB, nullable=False, comment='用户配置的参数值JSON')

    # 关系
    user = relationship("User", back_populates="strategies")
    template = relationship("StrategyTemplate", back_populates="user_strategies")
    backtest_jobs = relationship("BacktestJob", back_populates="strategy")


class BacktestJob(Base, TimestampMixin):
    """回测任务表"""

    __tablename__ = "backtest_jobs"
    __table_args__ = {'comment': '回测任务表 - 存储回测任务状态和配置'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='任务ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), comment='用户ID')
    strategy_id = Column(PG_UUID(as_uuid=True), ForeignKey("user_strategies.id"), comment='策略配置ID')
    status = Column(String(20), default="pending", comment='任务状态: pending待执行/running执行中/completed完成/failed失败')
    config = Column(JSONB, nullable=False, comment='回测配置: 资产/时间范围/初始资金等')
    result = Column(JSONB, nullable=True, comment='回测结果摘要JSON')
    error_message = Column(Text, nullable=True, comment='错误信息')
    started_at = Column(DateTime(timezone=True), nullable=True, comment='开始时间')
    completed_at = Column(DateTime(timezone=True), nullable=True, comment='完成时间')

    # 关系
    user = relationship("User", back_populates="backtest_jobs")
    strategy = relationship("UserStrategy", back_populates="backtest_jobs")
    result_detail = relationship("BacktestResult", back_populates="job", uselist=False)


class BacktestResult(Base, TimestampMixin):
    """回测结果详细表"""

    __tablename__ = "backtest_results"
    __table_args__ = {'comment': '回测结果详细表 - 存储回测的详细绩效指标和交易记录'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='结果ID')
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("backtest_jobs.id", ondelete="CASCADE"), comment='任务ID')
    total_return = Column(Numeric(10, 4), nullable=True, comment='累计收益率(%)')
    annualized_return = Column(Numeric(10, 4), nullable=True, comment='年化收益率(%)')
    max_drawdown = Column(Numeric(10, 4), nullable=True, comment='最大回撤(%)')
    volatility = Column(Numeric(10, 4), nullable=True, comment='波动率(%)')
    sharpe_ratio = Column(Numeric(10, 4), nullable=True, comment='夏普比率')
    win_rate = Column(Numeric(10, 4), nullable=True, comment='胜率(%)')
    total_trades = Column(Integer, nullable=True, comment='总交易次数')
    profit_trades = Column(Integer, nullable=True, comment='盈利交易次数')
    loss_trades = Column(Integer, nullable=True, comment='亏损交易次数')
    metrics = Column(JSONB, nullable=True, comment='其他指标JSON')
    equity_curve = Column(JSONB, nullable=True, comment='资金曲线数据点JSON')
    trades = Column(JSONB, nullable=True, comment='交易记录JSON')

    # 关系
    job = relationship("BacktestJob", back_populates="result_detail")