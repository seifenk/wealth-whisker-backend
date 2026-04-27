"""
模拟交易相关Schema定义
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============ 模拟账户 ============

class PaperAccountCreate(BaseModel):
    """创建模拟账户"""
    name: str = Field(..., min_length=1, max_length=100, description="账户名称")
    initial_capital: Decimal = Field(default=Decimal("100000"), ge=1000, le=10000000, description="初始资金")
    currency: str = Field(default="USD", description="货币类型")


class PaperAccountUpdate(BaseModel):
    """更新模拟账户"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class PaperAccountResponse(BaseModel):
    """模拟账户响应"""
    id: UUID
    user_id: UUID
    name: str
    initial_capital: Decimal
    current_capital: Decimal
    cash_balance: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperAccountListResponse(BaseModel):
    """模拟账户列表响应"""
    items: List[PaperAccountResponse]
    total: int


class AccountSummaryResponse(BaseModel):
    """账户摘要响应"""
    account: PaperAccountResponse
    total_position_value: Decimal
    total_value: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal
    positions_count: int


# ============ 持仓 ============

class PositionResponse(BaseModel):
    """持仓响应"""
    id: UUID
    account_id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    quantity: Decimal
    avg_cost: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[Decimal] = None
    opened_at: datetime

    class Config:
        from_attributes = True


class PositionListResponse(BaseModel):
    """持仓列表响应"""
    items: List[PositionResponse]
    total: int


# ============ 订单 ============

class OrderCreate(BaseModel):
    """创建订单"""
    asset_id: str = Field(..., description="资产ID")
    order_type: str = Field(default="market", description="订单类型: market, limit")
    side: str = Field(..., description="方向: buy, sell")
    quantity: Decimal = Field(..., gt=0, description="数量")
    price: Optional[Decimal] = Field(None, gt=0, description="限价单价格")


class OrderResponse(BaseModel):
    """订单响应"""
    id: UUID
    account_id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    order_type: str
    side: str
    quantity: Decimal
    price: Optional[Decimal] = None
    status: str
    filled_quantity: Optional[Decimal] = None
    filled_price: Optional[Decimal] = None
    commission: Decimal
    created_at: datetime
    filled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """订单列表响应"""
    items: List[OrderResponse]
    total: int


# ============ 交易记录 ============

class TransactionResponse(BaseModel):
    """交易记录响应"""
    id: UUID
    account_id: UUID
    order_id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    side: str
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    commission: Decimal
    executed_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """交易记录列表响应"""
    items: List[TransactionResponse]
    total: int


# ============ 绩效分析 ============

class PerformanceOverview(BaseModel):
    """绩效概览"""
    total_value: Decimal
    total_return: Decimal
    total_return_pct: Decimal
    daily_pnl: Optional[Decimal] = None
    daily_pnl_pct: Optional[Decimal] = None


class PerformanceMetrics(BaseModel):
    """绩效指标"""
    total_return: float
    annualized_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profit_trades: int
    loss_trades: int
    avg_profit: float
    avg_loss: float


class EquityCurvePoint(BaseModel):
    """资金曲线点"""
    time: datetime
    total_value: Decimal
    cash_balance: Decimal
    position_value: Decimal
    daily_pnl: Optional[Decimal] = None


class PerformanceResponse(BaseModel):
    """绩效分析响应"""
    overview: PerformanceOverview
    metrics: Optional[PerformanceMetrics] = None
    equity_curve: Optional[List[EquityCurvePoint]] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# ============ 账户快照 ============

class AccountSnapshotResponse(BaseModel):
    """账户快照响应"""
    id: UUID
    account_id: UUID
    snapshot_at: datetime
    total_value: Decimal
    cash_balance: Decimal
    position_value: Decimal
    daily_pnl: Optional[Decimal] = None
    daily_pnl_pct: Optional[Decimal] = None

    class Config:
        from_attributes = True


class SnapshotListResponse(BaseModel):
    """快照列表响应"""
    items: List[AccountSnapshotResponse]
    total: int