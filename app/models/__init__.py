"""
数据模型索引
"""
from app.models.user import User, UserSettings, Achievement, UserAchievement
from app.models.asset import Asset, OHLCV, AssetMetric
from app.models.strategy import StrategyTemplate, UserStrategy, BacktestJob, BacktestResult
from app.models.paper_trading import PaperAccount, Position, Order, Transaction, AccountSnapshot
from app.models.research import (
    ResearchCard,
    ModelPrediction,
    ModelCalibrationLog,
    DisclaimerVersion,
    UserDisclaimerAcceptance,
    RiskDisclosureLog,
)

__all__ = [
    # User models
    "User",
    "UserSettings",
    "Achievement",
    "UserAchievement",
    # Asset models
    "Asset",
    "OHLCV",
    "AssetMetric",
    # Strategy models
    "StrategyTemplate",
    "UserStrategy",
    "BacktestJob",
    "BacktestResult",
    # Paper trading models
    "PaperAccount",
    "Position",
    "Order",
    "Transaction",
    "AccountSnapshot",
    # Research models
    "ResearchCard",
    "ModelPrediction",
    "ModelCalibrationLog",
    "DisclaimerVersion",
    "UserDisclaimerAcceptance",
    "RiskDisclosureLog",
]