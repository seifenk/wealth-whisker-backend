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
    __table_args__ = {'comment': '资产表 - 存储黄金/基金/股票/加密货币等资产元信息'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='资产ID')
    symbol = Column(String(20), unique=True, nullable=False, index=True, comment='资产代码: BTC/GOLD/000001.SZ')
    name = Column(String(100), nullable=False, comment='资产名称')
    asset_type = Column(String(20), nullable=False, comment='资产类型: crypto加密货币/gold黄金/stock股票/fund基金')
    exchange = Column(String(50), nullable=True, comment='交易所: binance/shfe/sse')
    currency = Column(String(10), default="USD", comment='计价货币')
    min_lot = Column(Numeric(20, 8), nullable=True, comment='最小交易单位')
    tick_size = Column(Numeric(20, 8), nullable=True, comment='价格最小变动单位')
    is_active = Column(Boolean, default=True, comment='是否启用')
    asset_metadata = Column('metadata', JSONB, nullable=True, comment='扩展元数据')

    # 关系
    ohlcv_data = relationship("OHLCV", back_populates="asset")
    metrics = relationship("AssetMetric", back_populates="asset")
    research_cards = relationship("ResearchCard", back_populates="asset")
    predictions = relationship("ModelPrediction", back_populates="asset")
    calibration_logs = relationship("ModelCalibrationLog", back_populates="asset")
    positions = relationship("Position", back_populates="asset")


class OHLCV(Base):
    """K线数据表 (TimescaleDB hypertable)"""

    __tablename__ = "ohlcv"
    __table_args__ = {'comment': 'K线数据表 - 存储开高低收成交量数据(TimescaleDB时序表)'}

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False, comment='K线时间')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True, comment='资产ID')
    interval = Column(String(10), primary_key=True, nullable=False, comment='K线周期: 15m/1H/4H/1D/1W/1M')
    open = Column(Numeric(20, 8), nullable=False, comment='开盘价')
    high = Column(Numeric(20, 8), nullable=False, comment='最高价')
    low = Column(Numeric(20, 8), nullable=False, comment='最低价')
    close = Column(Numeric(20, 8), nullable=False, comment='收盘价')
    volume = Column(Numeric(30, 8), nullable=False, comment='成交量')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')

    # 关系
    asset = relationship("Asset", back_populates="ohlcv_data")


class AssetMetric(Base):
    """资产指标快照表"""

    __tablename__ = "asset_metrics"
    __table_args__ = {'comment': '资产指标快照表 - 存储计算后的技术指标和风险指标'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='指标ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), comment='计算时间')
    price = Column(Numeric(20, 8), nullable=True, comment='当前价格')
    change_24h = Column(Numeric(10, 4), nullable=True, comment='24小时涨跌幅(%)')
    change_7d = Column(Numeric(10, 4), nullable=True, comment='7天涨跌幅(%)')
    volatility_30d = Column(Numeric(10, 4), nullable=True, comment='30天波动率(%)')
    sharpe_ratio = Column(Numeric(10, 4), nullable=True, comment='夏普比率')
    risk_level = Column(String(20), nullable=True, comment='风险等级: low低/medium中/high高')
    trend_signal = Column(String(20), nullable=True, comment='趋势信号: bullish看涨/bearish看跌/neutral中性')
    confidence_score = Column(Numeric(5, 4), nullable=True, comment='模型预测置信度(0-1)')
    extra_data = Column('metadata', JSONB, nullable=True, comment='扩展指标数据')

    # 关系
    asset = relationship("Asset", back_populates="metrics")