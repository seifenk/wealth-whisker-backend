"""
研究结论与模型校准相关Schema定义
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import (
    RiskLevel, PredictionType, CalibrationType,
    InvestmentAction, ConsistencyStatus, ReasoningSource,
    SuitableForTag, SentimentType, TrendSignal, RSIStatus, VolumeTrend
)


# ============ 研究结论卡片（新格式） ============

class ReasoningItem(BaseModel):
    """依据项"""
    content: str = Field(..., description="依据内容")
    source: ReasoningSource = Field(..., description="依据来源")
    strength: Optional[int] = Field(None, ge=1, le=5, description="强度星级（1-5）")
    detail: Optional[str] = Field(None, description="详细说明（点击展开）")


class TechnicalSignal(BaseModel):
    """技术信号详情"""
    ma_trend: Optional[TrendSignal] = Field(None, description="MA趋势信号")
    rsi_status: Optional[RSIStatus] = Field(None, description="RSI状态")
    rsi_value: Optional[float] = Field(None, description="RSI数值")
    macd_signal: Optional[TrendSignal] = Field(None, description="MACD信号")
    volume_trend: Optional[VolumeTrend] = Field(None, description="成交量趋势")
    pattern: Optional[str] = Field(None, description="技术形态识别")


class TechnicalScore(BaseModel):
    """技术面评分"""
    stars: int = Field(..., ge=1, le=5, description="技术面强度星级")
    signals: TechnicalSignal = Field(..., description="技术信号详情")


class KeyEvent(BaseModel):
    """关键事件"""
    event: str = Field(..., description="事件内容")
    impact: SentimentType = Field(..., description="影响类型")
    source: Optional[str] = Field(None, description="信息来源")
    time: Optional[str] = Field(None, description="事件时间")


class NewsScore(BaseModel):
    """消息面评分"""
    stars: int = Field(..., ge=1, le=5, description="消息面影响力星级")
    sentiment: SentimentType = Field(..., description="整体情绪")
    key_events: Optional[List[KeyEvent]] = Field(None, description="关键事件列表")


class RiskItem(BaseModel):
    """风险项"""
    content: str = Field(..., description="风险内容")
    level: RiskLevel = Field(..., description="风险等级")


class InvestmentDecision(BaseModel):
    """投资决策"""
    action: InvestmentAction = Field(..., description="决策建议")
    confidence: float = Field(..., ge=0, le=100, description="决策置信度")
    reasons: List[str] = Field(..., description="决策理由")


class Scores(BaseModel):
    """双维度评分"""
    technical: TechnicalScore = Field(..., description="技术面评分")
    news: NewsScore = Field(..., description="消息面评分")
    consistency: ConsistencyStatus = Field(..., description="维度一致性")


class ValidPeriod(BaseModel):
    """有效期"""
    from_time: datetime = Field(..., alias="from", description="生效时间")
    to_time: datetime = Field(..., alias="to", description="失效时间")

    class Config:
        populate_by_name = True


class ResearchCardResponse(BaseModel):
    """研究结论卡片响应"""
    id: str = Field(..., description="卡片ID")
    asset_id: str = Field(..., description="资产ID")
    asset_symbol: str = Field(..., description="资产代码")
    asset_name: str = Field(..., description="资产名称")

    title: str = Field(..., description="结论标题")
    conclusion: str = Field(..., description="研究结论")
    confidence_score: float = Field(..., ge=0, le=100, description="综合置信度")

    reasoning: List[ReasoningItem] = Field(default_factory=list, description="混合依据列表")
    scores: Optional[Scores] = Field(None, description="双维度评分")
    decision: Optional[InvestmentDecision] = Field(None, description="明确决策建议")

    risks: List[RiskItem] = Field(default_factory=list, description="风险提示列表")
    suitable_for: List[SuitableForTag] = Field(default_factory=list, description="适合人群标签")

    valid_period: ValidPeriod = Field(..., description="有效期")
    is_active: bool = Field(..., description="是否生效")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class ResearchCardListResponse(BaseModel):
    """研究结论卡片列表响应"""
    items: List[ResearchCardResponse]
    total: int

class ResearchCardBase(BaseModel):
    """研究结论卡片基础"""
    title: str = Field(..., min_length=1, max_length=200)
    conclusion: str = Field(..., min_length=1)


class ResearchCardResponse(BaseModel):
    """研究结论卡片响应"""
    id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    title: str
    conclusion: str
    confidence_score: Optional[Decimal] = None
    risk_level: Optional[RiskLevel] = None
    indicators: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    suitable_for: Optional[List[str]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResearchCardListResponse(BaseModel):
    """研究结论卡片列表响应"""
    items: List[ResearchCardResponse]
    total: int


class RiskDisclaimer(BaseModel):
    """风险免责声明"""
    content: str
    version: str
    accepted: bool = False


# ============ 模型预测 ============

class ModelPredictionResponse(BaseModel):
    """模型预测响应"""
    id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    model_version: str
    prediction_type: PredictionType
    predicted_at: datetime
    target_date: date
    predicted_value: Optional[Decimal] = None
    confidence_score: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    deviation: Optional[Decimal] = None
    calibration_triggered: bool
    calibration_reason: Optional[str] = None

    class Config:
        from_attributes = True


class PredictionListResponse(BaseModel):
    """预测列表响应"""
    items: List[ModelPredictionResponse]
    total: int


class PredictionAccuracy(BaseModel):
    """预测准确性统计"""
    total_predictions: int
    accurate_predictions: int
    accuracy_rate: float
    avg_deviation: float
    max_deviation: float


class PredictionCreate(BaseModel):
    """创建预测"""
    asset_id: str
    prediction_type: PredictionType = Field(default=PredictionType.PRICE, description="预测类型")
    target_date: date
    model_version: str = Field(default="v1.0")


# ============ 模型校准日志 ============

class CalibrationLogResponse(BaseModel):
    """校准日志响应"""
    id: UUID
    asset_id: UUID
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    model_type: str
    calibration_type: Optional[CalibrationType] = None
    triggered_at: datetime
    completed_at: Optional[datetime] = None
    before_params: Optional[Dict[str, Any]] = None
    after_params: Optional[Dict[str, Any]] = None
    performance_before: Optional[Dict[str, Any]] = None
    performance_after: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class CalibrationLogListResponse(BaseModel):
    """校准日志列表响应"""
    items: List[CalibrationLogResponse]
    total: int


# ============ 模型版本管理 ============

class ModelVersionInfo(BaseModel):
    """模型版本信息"""
    version: str
    model_type: str
    created_at: datetime
    is_active: bool
    performance_metrics: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class ModelVersionListResponse(BaseModel):
    """模型版本列表响应"""
    items: List[ModelVersionInfo]
    total: int


# ============ 综合分析 ============

class AssetAnalysisResponse(BaseModel):
    """资产综合分析响应"""
    asset_id: str
    asset_symbol: str
    asset_name: str
    current_price: Optional[Decimal] = None
    research_card: Optional[ResearchCardResponse] = None
    latest_prediction: Optional[ModelPredictionResponse] = None
    prediction_accuracy: Optional[PredictionAccuracy] = None
    disclaimer: RiskDisclaimer