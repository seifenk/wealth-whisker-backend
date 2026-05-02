"""添加新闻数据表

Revision ID: 003_news_tables
Revises: d657df7fa98b
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '003_news_tables'
down_revision = 'd657df7fa98b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建新闻文章表
    op.create_table(
        'news_articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id', ondelete='cascade'), nullable=True, index=True, comment='关联资产ID（可选）'),
        sa.Column('title', sa.String(500), nullable=False, comment='新闻标题'),
        sa.Column('content', sa.Text, nullable=True, comment='新闻内容'),
        sa.Column('source', sa.String(50), default='media', comment='新闻来源类型'),
        sa.Column('source_name', sa.String(100), nullable=True, comment='来源名称'),
        sa.Column('url', sa.String(500), nullable=True, comment='原文链接'),
        sa.Column('published_at', sa.DateTime, nullable=True, comment='发布时间'),
        sa.Column('collected_at', sa.DateTime, default=sa.func.now(), comment='采集时间'),
        sa.Column('sentiment', sa.String(20), default='neutral', comment='情感倾向'),
        sa.Column('sentiment_score', sa.Numeric(5, 4), default=0.5, comment='情感分数(0-1)'),
        sa.Column('impact_type', sa.String(20), default='中性', comment='影响类型'),
        sa.Column('key_points', postgresql.JSONB, nullable=True, comment='关键要点'),
        sa.Column('llm_summary', sa.Text, nullable=True, comment='LLM分析摘要'),
        sa.Column('reasoning', sa.Text, nullable=True, comment='分析推理'),
        sa.Column('importance_score', sa.Integer, default=3, comment='重要性评分(1-5)'),
        sa.Column('relevance_score', sa.Numeric(5, 4), default=0.5, comment='相关性分数'),
        sa.Column('is_processed', sa.Boolean, default=False, comment='是否已处理'),
        sa.Column('is_active', sa.Boolean, default=True, comment='是否有效'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    op.create_index('ix_news_articles_asset_id', 'news_articles', ['asset_id'])
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'])
    op.create_index('ix_news_articles_sentiment', 'news_articles', ['sentiment'])

    # 创建情感快照表
    op.create_table(
        'sentiment_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id', ondelete='cascade'), nullable=False, index=True, comment='资产ID'),
        sa.Column('snapshot_date', sa.Date, nullable=False, index=True, comment='快照日期'),
        sa.Column('total_articles', sa.Integer, default=0, comment='文章总数'),
        sa.Column('positive_count', sa.Integer, default=0, comment='正面文章数'),
        sa.Column('negative_count', sa.Integer, default=0, comment='负面文章数'),
        sa.Column('neutral_count', sa.Integer, default=0, comment='中性文章数'),
        sa.Column('overall_sentiment', sa.String(20), default='neutral', comment='综合情感倾向'),
        sa.Column('overall_score', sa.Numeric(5, 4), default=0.5, comment='综合情感分数'),
        sa.Column('sentiment_trend', sa.String(20), default='stable', comment='情感趋势'),
        sa.Column('news_impact_stars', sa.Integer, default=3, comment='消息面影响力星级'),
        sa.Column('key_events', postgresql.JSONB, nullable=True, comment='关键事件列表'),
        sa.Column('summary', sa.Text, nullable=True, comment='消息面摘要'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    op.create_index('ix_sentiment_snapshots_asset_id', 'sentiment_snapshots', ['asset_id'])
    op.create_index('ix_sentiment_snapshots_snapshot_date', 'sentiment_snapshots', ['snapshot_date'])
    op.create_unique_constraint('uq_sentiment_snapshots_asset_date', 'sentiment_snapshots', ['asset_id', 'snapshot_date'])

    # 创建宏观经济指标表
    op.create_table(
        'macro_indicators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()),
        sa.Column('indicator_type', sa.String(50), nullable=False, index=True, comment='指标类型'),
        sa.Column('indicator_name', sa.String(100), nullable=False, comment='指标名称'),
        sa.Column('country', sa.String(50), default='US', comment='国家/地区'),
        sa.Column('value', sa.Numeric(20, 8), nullable=True, comment='指标数值'),
        sa.Column('unit', sa.String(20), nullable=True, comment='单位'),
        sa.Column('change', sa.Numeric(10, 4), nullable=True, comment='变化值'),
        sa.Column('change_percent', sa.Numeric(10, 4), nullable=True, comment='变化百分比'),
        sa.Column('report_date', sa.Date, nullable=False, index=True, comment='报告日期'),
        sa.Column('release_date', sa.DateTime, nullable=True, comment='发布时间'),
        sa.Column('market_impact', sa.String(20), default='neutral', comment='市场影响预期'),
        sa.Column('impact_score', sa.Integer, default=3, comment='影响程度'),
        sa.Column('source', sa.String(100), nullable=True, comment='数据来源'),
        sa.Column('source_url', sa.String(500), nullable=True, comment='来源链接'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    op.create_index('ix_macro_indicators_indicator_type', 'macro_indicators', ['indicator_type'])
    op.create_index('ix_macro_indicators_report_date', 'macro_indicators', ['report_date'])


def downgrade() -> None:
    op.drop_table('macro_indicators')
    op.drop_table('sentiment_snapshots')
    op.drop_table('news_articles')