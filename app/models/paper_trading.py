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

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    initial_capital = Column(Numeric(20, 8), nullable=False)
    current_capital = Column(Numeric(20, 8), nullable=False)
    cash_balance = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), default="USD")

    # 关系
    user = relationship("User", back_populates="paper_accounts")
    positions = relationship("Position", back_populates="account")
    orders = relationship("Order", back_populates="account")
    transactions = relationship("Transaction", back_populates="account")
    snapshots = relationship("AccountSnapshot", back_populates="account")


class Position(Base, TimestampMixin):
    """持仓表"""

    __tablename__ = "positions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_cost = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=True)
    market_value = Column(Numeric(20, 8), nullable=True)
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    unrealized_pnl_pct = Column(Numeric(10, 4), nullable=True)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    account = relationship("PaperAccount", back_populates="positions")
    asset = relationship("Asset", back_populates="positions")


class Order(Base, TimestampMixin):
    """订单表"""

    __tablename__ = "orders"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    order_type = Column(String(20), nullable=False)  # 'market', 'limit'
    side = Column(String(10), nullable=False)  # 'buy', 'sell'
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=True)  # 限价单价格
    status = Column(String(20), default="pending")  # 'pending', 'filled', 'cancelled'
    filled_quantity = Column(Numeric(20, 8), nullable=True)
    filled_price = Column(Numeric(20, 8), nullable=True)
    commission = Column(Numeric(20, 8), default=0)
    filled_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    account = relationship("PaperAccount", back_populates="orders")
    transactions = relationship("Transaction", back_populates="order")


class Transaction(Base):
    """交易记录表"""

    __tablename__ = "transactions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    order_id = Column(PG_UUID(as_uuid=True), ForeignKey("orders.id"))
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    side = Column(String(10), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    total_amount = Column(Numeric(20, 8), nullable=False)
    commission = Column(Numeric(20, 8), default=0)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    account = relationship("PaperAccount", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")


class AccountSnapshot(Base):
    """账户快照表 (TimescaleDB hypertable)"""

    __tablename__ = "account_snapshots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    account_id = Column(PG_UUID(as_uuid=True), ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    snapshot_at = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    total_value = Column(Numeric(20, 8), nullable=False)
    cash_balance = Column(Numeric(20, 8), nullable=False)
    position_value = Column(Numeric(20, 8), nullable=False)
    daily_pnl = Column(Numeric(20, 8), nullable=True)
    daily_pnl_pct = Column(Numeric(10, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    account = relationship("PaperAccount", back_populates="snapshots")