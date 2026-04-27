"""
模拟交易相关数据模型
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class PaperAccount(Base, TimestampMixin):
    """模拟账户表"""

    __tablename__ = "paper_accounts"
    __table_args__ = {'comment': '模拟账户表 - 存储用户模拟交易账户信息'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='账户ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), comment='用户ID')
    name = Column(String(100), nullable=False, comment='账户名称')
    initial_capital = Column(Numeric(20, 8), nullable=False, comment='初始资金')
    current_capital = Column(Numeric(20, 8), nullable=False, comment='当前资金')
    cash_balance = Column(Numeric(20, 8), nullable=False, comment='现金余额')
    currency = Column(String(10), default="USD", comment='账户币种')

    # 关系
    user = relationship("User", back_populates="paper_accounts")
    positions = relationship("Position", back_populates="account")
    orders = relationship("Order", back_populates="account")
    transactions = relationship("Transaction", back_populates="account")
    snapshots = relationship("AccountSnapshot", back_populates="account")


class Position(Base, TimestampMixin):
    """持仓表"""

    __tablename__ = "positions"
    __table_args__ = {'comment': '持仓表 - 存储模拟账户的持仓信息'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='持仓ID')
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"), comment='账户ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    quantity = Column(Numeric(20, 8), nullable=False, comment='持仓数量')
    avg_cost = Column(Numeric(20, 8), nullable=False, comment='平均成本')
    current_price = Column(Numeric(20, 8), nullable=True, comment='当前价格')
    market_value = Column(Numeric(20, 8), nullable=True, comment='市值')
    unrealized_pnl = Column(Numeric(20, 8), nullable=True, comment='未实现盈亏')
    unrealized_pnl_pct = Column(Numeric(10, 4), nullable=True, comment='未实现盈亏比例(%)')
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), comment='开仓时间')

    # 关系
    account = relationship("PaperAccount", back_populates="positions")
    asset = relationship("Asset", back_populates="positions")


class Order(Base, TimestampMixin):
    """订单表"""

    __tablename__ = "orders"
    __table_args__ = {'comment': '订单表 - 存储模拟交易订单信息'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='订单ID')
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"), comment='账户ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    order_type = Column(String(20), nullable=False, comment='订单类型: market市价/limit限价')
    side = Column(String(10), nullable=False, comment='交易方向: buy买入/sell卖出')
    quantity = Column(Numeric(20, 8), nullable=False, comment='委托数量')
    price = Column(Numeric(20, 8), nullable=True, comment='限价单价格')
    status = Column(String(20), default="pending", comment='订单状态: pending待成交/filled已成交/cancelled已取消')
    filled_quantity = Column(Numeric(20, 8), nullable=True, comment='成交数量')
    filled_price = Column(Numeric(20, 8), nullable=True, comment='成交价格')
    commission = Column(Numeric(20, 8), default=0, comment='手续费')
    filled_at = Column(DateTime(timezone=True), nullable=True, comment='成交时间')

    # 关系
    account = relationship("PaperAccount", back_populates="orders")
    transactions = relationship("Transaction", back_populates="order")


class Transaction(Base):
    """交易记录表"""

    __tablename__ = "transactions"
    __table_args__ = {'comment': '交易记录表 - 存储已成交的交易记录'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='交易ID')
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"), comment='账户ID')
    order_id = Column(PG_UUID(as_uuid=True), ForeignKey("orders.id"), comment='订单ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    side = Column(String(10), nullable=False, comment='交易方向: buy买入/sell卖出')
    quantity = Column(Numeric(20, 8), nullable=False, comment='交易数量')
    price = Column(Numeric(20, 8), nullable=False, comment='交易价格')
    total_amount = Column(Numeric(20, 8), nullable=False, comment='交易金额')
    commission = Column(Numeric(20, 8), default=0, comment='手续费')
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), comment='交易时间')

    # 关系
    account = relationship("PaperAccount", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")


class AccountSnapshot(Base):
    """账户快照表 (TimescaleDB hypertable)"""

    __tablename__ = "account_snapshots"
    __table_args__ = {'comment': '账户快照表 - 存储账户每日快照用于生成收益曲线(TimescaleDB时序表)'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='快照ID')
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"), comment='账户ID')
    snapshot_at = Column(DateTime(timezone=True), primary_key=True, nullable=False, comment='快照时间')
    total_value = Column(Numeric(20, 8), nullable=False, comment='总资产价值')
    cash_balance = Column(Numeric(20, 8), nullable=False, comment='现金余额')
    position_value = Column(Numeric(20, 8), nullable=False, comment='持仓市值')
    daily_pnl = Column(Numeric(20, 8), nullable=True, comment='当日盈亏')
    daily_pnl_pct = Column(Numeric(10, 4), nullable=True, comment='当日盈亏比例(%)')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')

    # 关系
    account = relationship("PaperAccount", back_populates="snapshots")