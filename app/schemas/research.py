"""
研究结论与模型校准相关Schema定义
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============ 研究结论卡片 ============

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
    risk_level: Optional[str] = None
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
    prediction_type: str
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
    prediction_type: str = Field(default="price", description="预测类型: price, trend, volatility")
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
    calibration_type: Optional[str] = None
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