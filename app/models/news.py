"""
新闻与消息面数据模型
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import Column, String, Text, DateTime, Date, Boolean, Integer, Numeric, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, generate_uuid
import enum


class SentimentType(enum.Enum):
    """情感类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class NewsSource(enum.Enum):
    """新闻来源"""
    OFFICIAL = "official"      # 官方公告
    MEDIA = "media"            # 主流媒体
    SOCIAL = "social"          # 社交媒体
    RESEARCH = "research"      # 研报分析
    OTHER = "other"            # 其他


class NewsArticle(Base):
    """新闻文章表"""
    __tablename__ = "news_articles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="cascade"), nullable=True, index=True, comment='关联资产ID（可选）')

    # 基本信息
    title = Column(String(500), nullable=False, comment='新闻标题')
    content = Column(Text, nullable=True, comment='新闻内容')
    source = Column(String(50), default="media", comment='新闻来源类型')
    source_name = Column(String(100), nullable=True, comment='来源名称（如Reuters、财新）')
    url = Column(String(500), nullable=True, comment='原文链接')

    # 时间信息
    published_at = Column(DateTime, nullable=True, comment='发布时间')
    collected_at = Column(DateTime, default=datetime.utcnow, comment='采集时间')

    # LLM分析结果
    sentiment = Column(String(20), default="neutral", comment='情感倾向：positive/negative/neutral')
    sentiment_score = Column(Numeric(5, 4), default=Decimal("0.5"), comment='情感分数（0-1）')
    impact_type = Column(String(20), default="中性", comment='影响类型：利好/利空/中性')
    key_points = Column(JSONB, nullable=True, comment='关键要点JSON数组')
    llm_summary = Column(Text, nullable=True, comment='LLM生成的分析摘要')
    reasoning = Column(Text, nullable=True, comment='分析推理过程')

    # 重要性评分
    importance_score = Column(Integer, default=3, comment='重要性评分（1-5）')
    relevance_score = Column(Numeric(5, 4), default=Decimal("0.5"), comment='相关性分数（0-1）')

    # 状态
    is_processed = Column(Boolean, default=False, comment='是否已处理')
    is_active = Column(Boolean, default=True, comment='是否有效')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    asset = relationship("Asset", backref="news_articles")


class SentimentSnapshot(Base):
    """情感快照表（资产维度聚合）"""
    __tablename__ = "sentiment_snapshots"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=generate_uuid)
    asset_id = Column(PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="cascade"), nullable=False, index=True, comment='资产ID')

    # 聚合数据
    snapshot_date = Column(Date, nullable=False, index=True, comment='快照日期')
    total_articles = Column(Integer, default=0, comment='文章总数')
    positive_count = Column(Integer, default=0, comment='正面文章数')
    negative_count = Column(Integer, default=0, comment='负面文章数')
    neutral_count = Column(Integer, default=0, comment='中性文章数')

    # 综合情感
    overall_sentiment = Column(String(20), default="neutral", comment='综合情感倾向')
    overall_score = Column(Numeric(5, 4), default=Decimal("0.5"), comment='综合情感分数')
    sentiment_trend = Column(String(20), default="stable", comment='情感趋势：improving/declining/stable')

    # 评分
    news_impact_stars = Column(Integer, default=3, comment='消息面影响力星级（1-5）')

    # 元数据
    key_events = Column(JSONB, nullable=True, comment='关键事件列表')
    summary = Column(Text, nullable=True, comment='消息面摘要')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    asset = relationship("Asset", backref="sentiment_snapshots")


class MacroIndicator(Base):
    """宏观经济指标表"""
    __tablename__ = "macro_indicators"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=generate_uuid)

    # 指标信息
    indicator_type = Column(String(50), nullable=False, index=True, comment='指标类型：GDP/CPI/FED_RATE/UNEMPLOYMENT等')
    indicator_name = Column(String(100), nullable=False, comment='指标名称')
    country = Column(String(50), default="US", comment='国家/地区')

    # 数值
    value = Column(Numeric(20, 8), nullable=True, comment='指标数值')
    unit = Column(String(20), nullable=True, comment='单位：%/Billion等')
    change = Column(Numeric(10, 4), nullable=True, comment='变化值')
    change_percent = Column(Numeric(10, 4), nullable=True, comment='变化百分比')

    # 时间
    report_date = Column(Date, nullable=False, index=True, comment='报告日期')
    release_date = Column(DateTime, nullable=True, comment='发布时间')

    # 影响
    market_impact = Column(String(20), default="neutral", comment='市场影响预期：positive/negative/neutral')
    impact_score = Column(Integer, default=3, comment='影响程度（1-5）')

    # 来源
    source = Column(String(100), nullable=True, comment='数据来源')
    source_url = Column(String(500), nullable=True, comment='来源链接')

    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')