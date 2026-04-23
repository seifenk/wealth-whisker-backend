"""Initialize seed data

Revision ID: 002_seed_data
Revises: 001_initial
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_seed_data'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seed default disclaimer version
    op.execute("""
        INSERT INTO disclaimer_versions (version, content, is_active)
        VALUES (
            '1.0',
            '财智猫理财平台免责声明

本平台提供的所有信息、数据、分析和预测结果仅供研究和学习参考，不构成任何投资建议或投资决策依据。

用户须知：
1. 本平台定位为"研究工具"，而非"投资建议平台"。
2. 所有策略回测结果均基于历史数据模拟，历史表现不代表未来收益。
3. 模拟交易与真实交易存在差异，模拟收益不等于真实投资收益。
4. 加密货币等高风险资产仅作为研究对象，不提供真实交易服务。
5. 本平台的AI模型会根据市场真实数据持续进行动态校准优化，早期预测可能因突发行情发生调整。

风险提示：
- 投资有风险，入市需谨慎
- 请根据自身风险承受能力做出决策
- 建议咨询专业投资顾问

使用本平台即表示您已阅读并同意以上声明。',
            true
        );
    """)

    # Seed achievements
    op.execute("""
        INSERT INTO achievements (code, name, description, category, points) VALUES
        ('first_register', '招财猫新手', '完成注册，开启理财之旅', 'learning', 10),
        ('first_backtest', '策略探索者', '完成首次策略回测', 'learning', 20),
        ('first_paper_account', '模拟投资家', '创建首个模拟账户', 'trading', 30),
        ('first_trade', '交易新手', '完成首次模拟交易', 'trading', 20),
        ('profit_first_trade', '盈利达人', '首次模拟交易盈利', 'trading', 50),
        ('week_streak_7', '坚持达人', '连续7天使用平台', 'learning', 100),
        ('month_streak_30', '理财专家', '连续30天使用平台', 'learning', 300),
        ('backtest_count_10', '回测研究员', '完成10次策略回测', 'learning', 50),
        ('backtest_count_50', '量化大师', '完成50次策略回测', 'learning', 200),
        ('diversified_portfolio', '组合投资家', '持仓超过3种不同资产', 'trading', 100);
    """)

    # Seed strategy templates
    op.execute("""
        INSERT INTO strategy_templates (code, name, description, category, parameters, is_public) VALUES
        ('ma_cross', '均线突破策略', '利用均线交叉信号进行交易决策', 'trend',
         '{"short_period": {"type": "integer", "default": 5, "min": 2, "max": 30, "description": "短期均线周期"}, "long_period": {"type": "integer", "default": 20, "min": 5, "max": 60, "description": "长期均线周期"}, "ma_type": {"type": "string", "default": "SMA", "options": ["SMA", "EMA"], "description": "均线类型"}}',
         true),
        ('momentum', '动量轮动策略', '基于动量指标进行资产轮动', 'trend',
         '{"lookback_period": {"type": "integer", "default": 20, "min": 5, "max": 60, "description": "回看周期"}, "top_n": {"type": "integer", "default": 3, "min": 1, "max": 10, "description": "选择动量最强的N个资产"}, "rebalance_freq": {"type": "string", "default": "weekly", "options": ["daily", "weekly", "monthly"], "description": "调仓频率"}}',
         true),
        ('dca', '定投再平衡策略', '定期定额投资并定期再平衡', 'portfolio',
         '{"invest_amount": {"type": "number", "default": 1000, "min": 100, "description": "每次投资金额"}, "invest_freq": {"type": "string", "default": "monthly", "options": ["weekly", "monthly", "quarterly"], "description": "投资频率"}, "rebalance_freq": {"type": "string", "default": "quarterly", "options": ["monthly", "quarterly", "yearly"], "description": "再平衡频率"}, "target_weights": {"type": "object", "default": {"stocks": 0.4, "gold": 0.3, "crypto": 0.2, "cash": 0.1}, "description": "目标资产配置权重"}}',
         true),
        ('risk_parity', '风险平价策略', '基于风险贡献进行资产配置', 'portfolio',
         '{"target_risk": {"type": "number", "default": 0.1, "min": 0.05, "max": 0.3, "description": "目标组合波动率"}, "rebalance_freq": {"type": "string", "default": "monthly", "options": ["weekly", "monthly", "quarterly"], "description": "调仓频率"}, "use_leverage": {"type": "boolean", "default": false, "description": "是否使用杠杆"}}',
         true);
    """)

    # Seed assets
    op.execute("""
        INSERT INTO assets (symbol, name, asset_type, exchange, currency, min_lot, tick_size, is_active, metadata) VALUES
        ('BTC', 'Bitcoin', 'crypto', 'binance', 'USD', 0.0001, 1, true, '{"description": "比特币，市值最大的加密货币"}'),
        ('ETH', 'Ethereum', 'crypto', 'binance', 'USD', 0.001, 0.01, true, '{"description": "以太坊，第二大加密货币，支持智能合约"}'),
        ('GOLD', 'Gold Spot', 'gold', 'LBMA', 'USD', 0.01, 0.01, true, '{"description": "黄金现货价格"}'),
        ('SPY', 'SPDR S&P 500 ETF', 'stock', 'NYSE', 'USD', 1, 0.01, true, '{"description": "标普500指数ETF"}'),
        ('AAPL', 'Apple Inc.', 'stock', 'NASDAQ', 'USD', 1, 0.01, true, '{"description": "苹果公司股票"}'),
        ('QQQ', 'Invesco QQQ Trust', 'stock', 'NASDAQ', 'USD', 1, 0.01, true, '{"description": "纳斯达克100指数ETF"}');
    """)


def downgrade() -> None:
    # Delete seed data
    op.execute("DELETE FROM assets WHERE symbol IN ('BTC', 'ETH', 'GOLD', 'SPY', 'AAPL', 'QQQ');")
    op.execute("DELETE FROM strategy_templates WHERE code IN ('ma_cross', 'momentum', 'dca', 'risk_parity');")
    op.execute("DELETE FROM achievements;")
    op.execute("DELETE FROM disclaimer_versions WHERE version = '1.0';")