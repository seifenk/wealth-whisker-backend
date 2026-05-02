"""
枚举类型定义
用于API文档展示可选值
"""
from enum import Enum


class AssetType(str, Enum):
    """资产类型"""
    CRYPTO = "crypto"      # 加密货币
    GOLD = "gold"          # 黄金
    STOCK = "stock"        # 股票
    FUND = "fund"          # 基金


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"      # 市价单
    LIMIT = "limit"        # 限价单


class OrderSide(str, Enum):
    """交易方向"""
    BUY = "buy"            # 买入
    SELL = "sell"          # 卖出


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"      # 待成交
    FILLED = "filled"       # 已成交
    CANCELLED = "cancelled"  # 已取消
    PARTIAL = "partial"      # 部分成交


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"            # 低风险
    MEDIUM = "medium"       # 中风险
    HIGH = "high"           # 高风险


class TrendSignal(str, Enum):
    """趋势信号"""
    BULLISH = "bullish"    # 看涨
    BEARISH = "bearish"     # 看跌
    NEUTRAL = "neutral"     # 中性


class BacktestJobStatus(str, Enum):
    """回测任务状态"""
    PENDING = "pending"     # 待执行
    RUNNING = "running"     # 执行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败


class RiskPreference(str, Enum):
    """风险偏好"""
    CONSERVATIVE = "conservative"  # 保守型
    BALANCED = "balanced"           # 平衡型
    AGGRESSIVE = "aggressive"       # 激进型


class Interval(str, Enum):
    """K线周期"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class RebalanceFrequency(str, Enum):
    """调仓频率"""
    DAILY = "daily"     # 每日
    WEEKLY = "weekly"   # 每周
    MONTHLY = "monthly" # 每月


class Currency(str, Enum):
    """货币类型"""
    USD = "USD"
    CNY = "CNY"
    EUR = "EUR"


class MAType(str, Enum):
    """均线类型"""
    SMA = "SMA"  # 简单移动平均
    EMA = "EMA"  # 指数移动平均


class PredictionType(str, Enum):
    """预测类型"""
    PRICE = "price"              # 价格预测
    PRICE_SHORT = "price_short"  # 短期价格预测
    PRICE_MID = "price_mid"      # 中期价格预测
    TREND = "trend"              # 趋势预测
    VOLATILITY = "volatility"    # 波动率预测


class CalibrationType(str, Enum):
    """校准类型"""
    SCHEDULED = "scheduled"          # 定时校准
    DEVIATION_TRIGGERED = "deviation_triggered"  # 偏差触发校准


class InvestmentAction(str, Enum):
    """投资决策"""
    STRONG_BUY = "strong_buy"    # 强烈买入
    BUY = "buy"                  # 买入
    HOLD = "hold"                # 观望
    SELL = "sell"                # 卖出
    STRONG_SELL = "strong_sell"  # 强烈卖出


class ConsistencyStatus(str, Enum):
    """维度一致性状态"""
    ALIGNED = "aligned"      # 一致（同向）
    DIVERGED = "diverged"    # 背离（反向）
    NEUTRAL = "neutral"      # 中性


class ReasoningSource(str, Enum):
    """依据来源"""
    TECHNICAL = "technical"      # 技术面
    NEWS = "news"                # 消息面
    FUNDAMENTAL = "fundamental"  # 基本面


class SuitableForTag(str, Enum):
    """适合人群标签"""
    CONSERVATIVE = "conservative"   # 保守型
    BALANCED = "balanced"           # 平衡型
    AGGRESSIVE = "aggressive"       # 激进型
    NOVICE = "novice"               # 新手
    INTERMEDIATE = "intermediate"   # 中级
    EXPERT = "expert"               # 专家


class SentimentType(str, Enum):
    """情感类型"""
    POSITIVE = "positive"   # 正面/利好
    NEGATIVE = "negative"   # 负面/利空
    NEUTRAL = "neutral"     # 中性


class RSIStatus(str, Enum):
    """RSI状态"""
    OVERBOUGHT = "overbought"  # 超买
    OVERSOLD = "oversold"      # 超卖
    NORMAL = "normal"          # 正常


class VolumeTrend(str, Enum):
    """成交量趋势"""
    INCREASING = "increasing"  # 放大
    DECREASING = "decreasing"  # 缩小
    STABLE = "stable"          # 稳定


class ImpactType(str, Enum):
    """影响类型"""
    POSITIVE = "positive"   # 正面影响
    NEGATIVE = "negative"   # 负面影响
    NEUTRAL = "neutral"     # 中性影响