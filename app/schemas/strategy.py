"""
策略与回测相关Schema定义
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ 策略模板 ============

class StrategyTemplateBase(BaseModel):
    """策略模板基础"""
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class StrategyTemplateResponse(StrategyTemplateBase):
    """策略模板响应"""
    id: str
    parameters: Dict[str, Any]  # 参数定义 schema
    is_public: bool

    class Config:
        from_attributes = True


class StrategyTemplateListResponse(BaseModel):
    """策略模板列表响应"""
    items: List[StrategyTemplateResponse]
    total: int


# ============ 用户策略 ============

class UserStrategyCreate(BaseModel):
    """创建用户策略"""
    template_id: str
    name: str = Field(..., min_length=1, max_length=100)
    parameters: Dict[str, Any]  # 用户配置的参数值


class UserStrategyUpdate(BaseModel):
    """更新用户策略"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parameters: Optional[Dict[str, Any]] = None


class UserStrategyResponse(BaseModel):
    """用户策略响应"""
    id: str
    template_id: str
    template_code: Optional[str] = None
    template_name: Optional[str] = None
    name: str
    parameters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserStrategyListResponse(BaseModel):
    """用户策略列表响应"""
    items: List[UserStrategyResponse]
    total: int


# ============ 回测任务 ============

class BacktestJobCreate(BaseModel):
    """创建回测任务"""
    strategy_id: str
    asset_ids: List[str] = Field(..., min_length=1, max_length=10)
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal = Field(default=Decimal("10000"), ge=100)
    rebalance_frequency: str = Field(default="daily", description="调仓频率: daily, weekly, monthly")


class BacktestJobResponse(BaseModel):
    """回测任务响应"""
    id: str
    strategy_id: str
    strategy_name: Optional[str] = None
    status: str  # pending, running, completed, failed
    config: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BacktestJobListResponse(BaseModel):
    """回测任务列表响应"""
    items: List[BacktestJobResponse]
    total: int


# ============ 回测结果 ============

class TradeRecord(BaseModel):
    """交易记录"""
    time: datetime
    asset_id: str
    asset_symbol: str
    action: str  # buy, sell
    quantity: Decimal
    price: Decimal
    value: Decimal


class EquityPoint(BaseModel):
    """资金曲线点"""
    time: datetime
    equity: Decimal
    cash: Decimal
    positions_value: Decimal


class BacktestResultResponse(BaseModel):
    """回测结果响应"""
    job_id: str
    # 收益指标
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    # 风险指标
    max_drawdown: Optional[float] = None
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    # 交易统计
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    profit_trades: Optional[int] = None
    loss_trades: Optional[int] = None
    # 详细数据
    equity_curve: Optional[List[Dict[str, Any]]] = None
    trades: Optional[List[Dict[str, Any]]] = None
    # 其他
    metrics: Optional[Dict[str, Any]] = None


# ============ 策略参数定义 ============

# 均线突破策略参数
MA_CROSS_PARAMS = {
    "fast_period": {
        "type": "integer",
        "default": 5,
        "min": 2,
        "max": 50,
        "description": "快线周期"
    },
    "slow_period": {
        "type": "integer",
        "default": 20,
        "min": 5,
        "max": 200,
        "description": "慢线周期"
    },
    "ma_type": {
        "type": "string",
        "default": "SMA",
        "options": ["SMA", "EMA"],
        "description": "均线类型"
    }
}

# 动量轮动策略参数
MOMENTUM_PARAMS = {
    "lookback_period": {
        "type": "integer",
        "default": 20,
        "min": 5,
        "max": 60,
        "description": "动量计算周期"
    },
    "top_n": {
        "type": "integer",
        "default": 3,
        "min": 1,
        "max": 5,
        "description": "选择表现最好的N个资产"
    },
    "rebalance_frequency": {
        "type": "string",
        "default": "weekly",
        "options": ["daily", "weekly", "monthly"],
        "description": "调仓频率"
    }
}

# 定投策略参数
DCA_PARAMS = {
    "investment_amount": {
        "type": "number",
        "default": 1000,
        "min": 100,
        "max": 100000,
        "description": "每次投资金额"
    },
    "frequency": {
        "type": "string",
        "default": "monthly",
        "options": ["daily", "weekly", "monthly"],
        "description": "投资频率"
    },
    "start_delay": {
        "type": "integer",
        "default": 0,
        "min": 0,
        "max": 30,
        "description": "开始延迟天数"
    }
}

# 风险平价策略参数
RISK_PARITY_PARAMS = {
    "target_volatility": {
        "type": "number",
        "default": 15,
        "min": 5,
        "max": 30,
        "description": "目标波动率(%)"
    },
    "lookback_period": {
        "type": "integer",
        "default": 60,
        "min": 20,
        "max": 120,
        "description": "波动率计算周期"
    },
    "rebalance_frequency": {
        "type": "string",
        "default": "monthly",
        "options": ["daily", "weekly", "monthly"],
        "description": "调仓频率"
    }
}