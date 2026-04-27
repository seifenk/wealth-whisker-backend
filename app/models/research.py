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
    __table_args__ = {'comment': '研究结论卡片表 - 存储AI生成的研究结论和投资建议'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='卡片ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    title = Column(String(200), nullable=False, comment='结论标题')
    conclusion = Column(Text, nullable=False, comment='研究结论')
    confidence_score = Column(Numeric(5, 4), nullable=True, comment='置信度分数(0-1)')
    risk_level = Column(String(20), nullable=True, comment='风险等级: low低/medium中/high高')
    indicators = Column(JSONB, nullable=True, comment='指标依据JSON')
    reasoning = Column(Text, nullable=True, comment='推理过程')
    suitable_for = Column(JSONB, nullable=True, comment='适合人群标签JSON')
    valid_from = Column(DateTime(timezone=True), nullable=True, comment='生效开始时间')
    valid_until = Column(DateTime(timezone=True), nullable=True, comment='生效结束时间')
    is_active = Column(Boolean, default=True, comment='是否生效')

    # 关系
    asset = relationship("Asset", back_populates="research_cards")


class ModelPrediction(Base):
    """模型预测记录表"""

    __tablename__ = "model_predictions"
    __table_args__ = {'comment': '模型预测记录表 - 存储AI模型的预测结果和实际值对比'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='预测ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    model_version = Column(String(50), nullable=False, comment='模型版本号')
    prediction_type = Column(String(50), nullable=False, comment='预测类型: price价格/trend趋势/volatility波动率')
    predicted_at = Column(DateTime(timezone=True), server_default=func.now(), comment='预测时间')
    target_date = Column(Date, nullable=False, comment='预测目标日期')
    predicted_value = Column(Numeric(20, 8), nullable=True, comment='预测值')
    confidence_score = Column(Numeric(5, 4), nullable=True, comment='预测置信度(0-1)')
    actual_value = Column(Numeric(20, 8), nullable=True, comment='实际值(校准后填入)')
    deviation = Column(Numeric(10, 4), nullable=True, comment='偏差率(%)')
    calibration_triggered = Column(Boolean, default=False, comment='是否触发了模型校准')
    calibration_reason = Column(Text, nullable=True, comment='校准原因')
    prediction_metadata = Column('metadata', JSONB, nullable=True, comment='预测元数据JSON')

    # 关系
    asset = relationship("Asset", back_populates="predictions")


class ModelCalibrationLog(Base):
    """模型校准日志表"""

    __tablename__ = "model_calibration_logs"
    __table_args__ = {'comment': '模型校准日志表 - 记录AI模型的校准过程和参数变化'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='日志ID')
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id"), comment='资产ID')
    model_type = Column(String(50), nullable=False, comment='模型类型')
    calibration_type = Column(String(50), nullable=True, comment='校准类型: scheduled定时/deviation_triggered偏差触发')
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), comment='触发时间')
    completed_at = Column(DateTime(timezone=True), nullable=True, comment='完成时间')
    before_params = Column(JSONB, nullable=True, comment='校准前参数JSON')
    after_params = Column(JSONB, nullable=True, comment='校准后参数JSON')
    performance_before = Column(JSONB, nullable=True, comment='校准前性能JSON')
    performance_after = Column(JSONB, nullable=True, comment='校准后性能JSON')
    notes = Column(Text, nullable=True, comment='备注说明')


class DisclaimerVersion(Base, TimestampMixin):
    """免责声明版本表"""

    __tablename__ = "disclaimer_versions"
    __table_args__ = {'comment': '免责声明版本表 - 存储各版本的免责声明内容'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='声明ID')
    version = Column(String(20), unique=True, nullable=False, comment='版本号')
    content = Column(Text, nullable=False, comment='免责声明内容')
    is_active = Column(Boolean, default=True, comment='是否当前版本')


class UserDisclaimerAcceptance(Base):
    """用户免责声明确认表"""

    __tablename__ = "user_disclaimer_acceptances"
    __table_args__ = {'comment': '用户免责声明确认表 - 记录用户对免责声明的确认'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='记录ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), comment='用户ID')
    disclaimer_id = Column(PG_UUID(as_uuid=True), ForeignKey("disclaimer_versions.id"), comment='免责声明ID')
    accepted_at = Column(DateTime(timezone=True), server_default=func.now(), comment='确认时间')
    ip_address = Column(String(50), nullable=True, comment='IP地址')
    user_agent = Column(Text, nullable=True, comment='用户代理')


class RiskDisclosureLog(Base):
    """风险提示展示记录表"""

    __tablename__ = "risk_disclosure_logs"
    __table_args__ = {'comment': '风险提示展示记录表 - 记录风险提示的展示情况'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid, comment='记录ID')
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment='用户ID')
    page = Column(String(100), nullable=False, comment='页面路径')
    disclosure_type = Column(String(50), nullable=False, comment='提示类型')
    shown_at = Column(DateTime(timezone=True), server_default=func.now(), comment='展示时间')
    acknowledged = Column(Boolean, default=False, comment='用户是否已确认')