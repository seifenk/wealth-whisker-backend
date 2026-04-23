"""
资产相关数据模型
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Asset(Base, TimestampMixin):
    """资产表"""

    __tablename__ = "assets"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), unique=True, nullable=False, index=True)  # 'BTC', 'GOLD', '000001.SZ'
    name = Column(String(100), nullable=False)
    asset_type = Column(String(20), nullable=False)  # 'crypto', 'gold', 'stock', 'fund'
    exchange = Column(String(50), nullable=True)  # 'binance', 'shfe', 'sse'
    currency = Column(String(10), default="USD")
    min_lot = Column(Numeric(20, 8), nullable=True)
    tick_size = Column(Numeric(20, 8), nullable=True)
    is_active = Column(Boolean, default=True)
    asset_metadata = Column('metadata', JSONB, nullable=True)

    # 关系
    ohlcv_data = relationship("OHLCV", back_populates="asset")
    metrics = relationship("AssetMetric", back_populates="asset")
    research_cards = relationship("ResearchCard", back_populates="asset")
    predictions = relationship("ModelPrediction", back_populates="asset")
    positions = relationship("Position", back_populates="asset")


class OHLCV(Base):
    """K线数据表 (TimescaleDB hypertable)"""

    __tablename__ = "ohlcv"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True)
    interval = Column(String(10), primary_key=True, nullable=False)  # '1m', '5m', '1h', '1d'
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(30, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    asset = relationship("Asset", back_populates="ohlcv_data")


class AssetMetric(Base):
    """资产指标快照表"""

    __tablename__ = "asset_metrics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    price = Column(Numeric(20, 8), nullable=True)
    change_24h = Column(Numeric(10, 4), nullable=True)
    change_7d = Column(Numeric(10, 4), nullable=True)
    volatility_30d = Column(Numeric(10, 4), nullable=True)
    sharpe_ratio = Column(Numeric(10, 4), nullable=True)
    risk_level = Column(String(20), nullable=True)  # 'low', 'medium', 'high'
    trend_signal = Column(String(20), nullable=True)  # 'bullish', 'bearish', 'neutral'
    confidence_score = Column(Numeric(5, 4), nullable=True)  # 模型预测置信度
    extra_data = Column('metadata', JSONB, nullable=True)

    # 关系
    asset = relationship("Asset", back_populates="metrics")