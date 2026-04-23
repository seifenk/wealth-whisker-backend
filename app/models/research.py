"""
研究结论与模型预测相关数据模型
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class ResearchCard(Base, TimestampMixin):
    """研究结论卡片表"""

    __tablename__ = "research_cards"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    title = Column(String(200), nullable=False)
    conclusion = Column(Text, nullable=False)
    confidence_score = Column(Numeric(5, 4), nullable=True)  # 0-1 置信度
    risk_level = Column(String(20), nullable=True)
    indicators = Column(JSONB, nullable=True)  # 指标依据
    reasoning = Column(Text, nullable=True)  # 推理过程
    suitable_for = Column(JSONB, nullable=True)  # 适合人群标签
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # 关系
    asset = relationship("Asset", back_populates="research_cards")


class ModelPrediction(Base):
    """模型预测记录表"""

    __tablename__ = "model_predictions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    model_version = Column(String(50), nullable=False)
    prediction_type = Column(String(50), nullable=False)  # 'price', 'trend', 'volatility'
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())
    target_date = Column(Date, nullable=False)
    predicted_value = Column(Numeric(20, 8), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    actual_value = Column(Numeric(20, 8), nullable=True)  # 实际值（校准后填入）
    deviation = Column(Numeric(10, 4), nullable=True)  # 偏差率
    calibration_triggered = Column(Boolean, default=False)  # 是否触发了校准
    calibration_reason = Column(Text, nullable=True)
    prediction_metadata = Column('metadata', JSONB, nullable=True)

    # 关系
    asset = relationship("Asset", back_populates="predictions")


class ModelCalibrationLog(Base):
    """模型校准日志表"""

    __tablename__ = "model_calibration_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"))
    model_type = Column(String(50), nullable=False)
    calibration_type = Column(String(50), nullable=True)  # 'scheduled', 'deviation_triggered'
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    before_params = Column(JSONB, nullable=True)
    after_params = Column(JSONB, nullable=True)
    performance_before = Column(JSONB, nullable=True)
    performance_after = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)


class DisclaimerVersion(Base, TimestampMixin):
    """免责声明版本表"""

    __tablename__ = "disclaimer_versions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    version = Column(String(20), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)


class UserDisclaimerAcceptance(Base):
    """用户免责声明确认表"""

    __tablename__ = "user_disclaimer_acceptances"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    disclaimer_id = Column(PG_UUID(as_uuid=True), ForeignKey("disclaimer_versions.id"))
    accepted_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)


class RiskDisclosureLog(Base):
    """风险提示展示记录表"""

    __tablename__ = "risk_disclosure_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    page = Column(String(100), nullable=False)
    disclosure_type = Column(String(50), nullable=False)
    shown_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged = Column(Boolean, default=False)