"""
资产相关Schema定义
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class AssetBase(BaseModel):
    """资产基础信息"""
    symbol: str
    name: str
    asset_type: str
    exchange: Optional[str] = None
    currency: str = "USD"


class AssetResponse(BaseModel):
    """资产响应"""
    id: str
    symbol: str
    name: str
    asset_type: str
    exchange: Optional[str] = None
    currency: str
    is_active: bool
    min_lot: Optional[Decimal] = None
    tick_size: Optional[Decimal] = None

    class Config:
        from_attributes = True


class OHLCVResponse(BaseModel):
    """K线数据响应"""
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    class Config:
        from_attributes = True


class AssetMetricResponse(BaseModel):
    """资产指标响应"""
    price: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_7d: Optional[Decimal] = None
    volatility_30d: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    risk_level: Optional[str] = None
    trend_signal: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    calculated_at: Optional[datetime] = None


class AssetDetailResponse(BaseModel):
    """资产详情响应"""
    asset: AssetResponse
    latest_metric: Optional[AssetMetricResponse] = None
    latest_price: Optional[Decimal] = None


class DashboardItemResponse(BaseModel):
    """看板单项响应"""
    id: str
    symbol: str
    name: str
    asset_type: str
    exchange: Optional[str] = None
    currency: str
    price: Optional[float] = None
    change_24h: Optional[float] = None
    change_7d: Optional[float] = None
    volatility_30d: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    risk_level: Optional[str] = None
    trend_signal: Optional[str] = None
    confidence_score: Optional[float] = None
    updated_at: Optional[str] = None


class DashboardResponse(BaseModel):
    """看板响应"""
    items: List[DashboardItemResponse]
    total: int
    asset_type_filter: Optional[str] = None


class PerformanceMetricsResponse(BaseModel):
    """绩效指标响应"""
    total_return: float
    annualized_return: float
    volatility: float
    max_drawdown: float
    sharpe_ratio: float
    data_points: int


class OHLCVQueryParams(BaseModel):
    """K线查询参数"""
    interval: str = Field(default="1h", description="K线周期: 1m, 5m, 15m, 30m, 1h, 4h, 1d")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    limit: int = Field(default=100, ge=1, le=1000, description="返回数量限制")