"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('nickname', sa.String(100), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('risk_preference', sa.String(20), server_default='balanced'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('disclaimer_accepted', sa.Boolean, server_default='false'),
        sa.Column('disclaimer_accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # User settings table
    op.create_table(
        'user_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True),
        sa.Column('theme', sa.String(20), server_default='light'),
        sa.Column('notification_enabled', sa.Boolean, server_default='true'),
        sa.Column('daily_report_enabled', sa.Boolean, server_default='false'),
        sa.Column('language', sa.String(10), server_default='zh-CN'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Achievements table
    op.create_table(
        'achievements',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icon_url', sa.String(500), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('points', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # User achievements table
    op.create_table(
        'user_achievements',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('achievement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('achievements.id')),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_user_achievement', 'user_achievements', ['user_id', 'achievement_id'])

    # Assets table
    op.create_table(
        'assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('symbol', sa.String(20), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('asset_type', sa.String(20), nullable=False),
        sa.Column('exchange', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('min_lot', sa.Numeric(20, 8), nullable=True),
        sa.Column('tick_size', sa.Numeric(20, 8), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_assets_symbol', 'assets', ['symbol'])

    # OHLCV table
    op.create_table(
        'ohlcv',
        sa.Column('time', sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id'), primary_key=True),
        sa.Column('interval', sa.String(10), primary_key=True, nullable=False),
        sa.Column('open', sa.Numeric(20, 8), nullable=False),
        sa.Column('high', sa.Numeric(20, 8), nullable=False),
        sa.Column('low', sa.Numeric(20, 8), nullable=False),
        sa.Column('close', sa.Numeric(20, 8), nullable=False),
        sa.Column('volume', sa.Numeric(30, 8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_ohlcv_asset_interval', 'ohlcv', ['asset_id', 'interval', sa.text('time DESC')])
    # Create TimescaleDB hypertable
    op.execute("SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);")

    # Asset metrics table
    op.create_table(
        'asset_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('price', sa.Numeric(20, 8), nullable=True),
        sa.Column('change_24h', sa.Numeric(10, 4), nullable=True),
        sa.Column('change_7d', sa.Numeric(10, 4), nullable=True),
        sa.Column('volatility_30d', sa.Numeric(10, 4), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(10, 4), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('trend_signal', sa.String(20), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )

    # Strategy templates table
    op.create_table(
        'strategy_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('parameters', postgresql.JSONB, nullable=False),
        sa.Column('is_public', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # User strategies table
    op.create_table(
        'user_strategies',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategy_templates.id')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('parameters', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Backtest jobs table
    op.create_table(
        'backtest_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_strategies.id')),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('config', postgresql.JSONB, nullable=False),
        sa.Column('result', postgresql.JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Backtest results table
    op.create_table(
        'backtest_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('backtest_jobs.id', ondelete='CASCADE')),
        sa.Column('total_return', sa.Numeric(10, 4), nullable=True),
        sa.Column('annualized_return', sa.Numeric(10, 4), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(10, 4), nullable=True),
        sa.Column('volatility', sa.Numeric(10, 4), nullable=True),
        sa.Column('sharpe_ratio', sa.Numeric(10, 4), nullable=True),
        sa.Column('win_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('total_trades', sa.Integer, nullable=True),
        sa.Column('profit_trades', sa.Integer, nullable=True),
        sa.Column('loss_trades', sa.Integer, nullable=True),
        sa.Column('metrics', postgresql.JSONB, nullable=True),
        sa.Column('equity_curve', postgresql.JSONB, nullable=True),
        sa.Column('trades', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Paper accounts table
    op.create_table(
        'paper_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('initial_capital', sa.Numeric(20, 8), nullable=False),
        sa.Column('current_capital', sa.Numeric(20, 8), nullable=False),
        sa.Column('cash_balance', sa.Numeric(20, 8), nullable=False),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Positions table
    op.create_table(
        'positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('paper_accounts.id', ondelete='CASCADE')),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('avg_cost', sa.Numeric(20, 8), nullable=False),
        sa.Column('current_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('market_value', sa.Numeric(20, 8), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('unrealized_pnl_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_unique_constraint('uq_position_account_asset', 'positions', ['account_id', 'asset_id'])

    # Orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('paper_accounts.id', ondelete='CASCADE')),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('price', sa.Numeric(20, 8), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('filled_quantity', sa.Numeric(20, 8), nullable=True),
        sa.Column('filled_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('commission', sa.Numeric(20, 8), server_default='0'),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Transactions table
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('paper_accounts.id', ondelete='CASCADE')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id')),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('price', sa.Numeric(20, 8), nullable=False),
        sa.Column('total_amount', sa.Numeric(20, 8), nullable=False),
        sa.Column('commission', sa.Numeric(20, 8), server_default='0'),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Account snapshots table
    op.create_table(
        'account_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('paper_accounts.id', ondelete='CASCADE')),
        sa.Column('snapshot_at', sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column('total_value', sa.Numeric(20, 8), nullable=False),
        sa.Column('cash_balance', sa.Numeric(20, 8), nullable=False),
        sa.Column('position_value', sa.Numeric(20, 8), nullable=False),
        sa.Column('daily_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('daily_pnl_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    # Create TimescaleDB hypertable
    op.execute("SELECT create_hypertable('account_snapshots', 'snapshot_at', if_not_exists => TRUE);")

    # Research cards table
    op.create_table(
        'research_cards',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('conclusion', sa.Text, nullable=False),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('indicators', postgresql.JSONB, nullable=True),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('suitable_for', postgresql.JSONB, nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # Model predictions table
    op.create_table(
        'model_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('prediction_type', sa.String(50), nullable=False),
        sa.Column('predicted_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('target_date', sa.Date, nullable=False),
        sa.Column('predicted_value', sa.Numeric(20, 8), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('actual_value', sa.Numeric(20, 8), nullable=True),
        sa.Column('deviation', sa.Numeric(10, 4), nullable=True),
        sa.Column('calibration_triggered', sa.Boolean, server_default='false'),
        sa.Column('calibration_reason', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )

    # Model calibration logs table
    op.create_table(
        'model_calibration_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id')),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('calibration_type', sa.String(50), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('before_params', postgresql.JSONB, nullable=True),
        sa.Column('after_params', postgresql.JSONB, nullable=True),
        sa.Column('performance_before', postgresql.JSONB, nullable=True),
        sa.Column('performance_after', postgresql.JSONB, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )

    # Disclaimer versions table
    op.create_table(
        'disclaimer_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('version', sa.String(20), unique=True, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # User disclaimer acceptances table
    op.create_table(
        'user_disclaimer_acceptances',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('disclaimer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('disclaimer_versions.id')),
        sa.Column('accepted_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
    )
    op.create_unique_constraint('uq_user_disclaimer', 'user_disclaimer_acceptances', ['user_id', 'disclaimer_id'])

    # Risk disclosure logs table
    op.create_table(
        'risk_disclosure_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('page', sa.String(100), nullable=False),
        sa.Column('disclosure_type', sa.String(50), nullable=False),
        sa.Column('shown_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('acknowledged', sa.Boolean, server_default='false'),
    )


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('risk_disclosure_logs')
    op.drop_table('user_disclaimer_acceptances')
    op.drop_table('disclaimer_versions')
    op.drop_table('model_calibration_logs')
    op.drop_table('model_predictions')
    op.drop_table('research_cards')
    op.drop_table('account_snapshots')
    op.drop_table('transactions')
    op.drop_table('orders')
    op.drop_table('positions')
    op.drop_table('paper_accounts')
    op.drop_table('backtest_results')
    op.drop_table('backtest_jobs')
    op.drop_table('user_strategies')
    op.drop_table('strategy_templates')
    op.drop_table('asset_metrics')
    op.drop_table('ohlcv')
    op.drop_table('assets')
    op.drop_table('user_achievements')
    op.drop_table('achievements')
    op.drop_table('user_settings')
    op.drop_table('users')
    # Drop TimescaleDB extension
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")