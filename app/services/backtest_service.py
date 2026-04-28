"""
回测服务模块

协调回测引擎执行和数据获取
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import BacktestJob, BacktestResult, StrategyTemplate
from app.models.asset import Asset, OHLCV
from app.data.calculators import MACrossStrategy, MomentumStrategy, DCAStrategy, RiskParityStrategy
from app.services.strategy_service import StrategyService
from app.services.asset_service import AssetService


class BacktestService:
    """回测服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.strategy_service = StrategyService(session)
        self.asset_service = AssetService(session)

    async def run_backtest(self, job_id: UUID) -> Optional[BacktestResult]:
        """
        执行回测任务

        Args:
            job_id: 回测任务ID

        Returns:
            回测结果
        """
        # 获取任务
        job = await self.session.execute(
            select(BacktestJob).where(BacktestJob.id == job_id)
        )
        job = job.scalar_one_or_none()

        if not job:
            logger.error(f"回测任务不存在: {job_id}")
            return None

        # 更新状态
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await self.session.flush()

        try:
            # 获取策略配置
            strategy = await self.strategy_service.get_user_strategy_by_id(
                job.strategy_id, job.user_id
            )
            if not strategy:
                raise ValueError("策略不存在")

            # 获取模板
            template = await self.strategy_service.get_template_by_id(strategy.template_id)
            if not template:
                raise ValueError("策略模板不存在")

            # 合并参数：模板默认值 + 用户配置
            params = strategy.parameters

            # 获取配置
            config = job.config
            asset_ids = [UUID(aid) for aid in config.get("asset_ids", [])]

            # 解析时间（字符串转datetime）
            start_date_str = config.get("start_date")
            end_date_str = config.get("end_date")

            if isinstance(start_date_str, str):
                # 处理ISO格式字符串（去掉Z后缀）
                start_date_str = start_date_str.replace("Z", "+00:00")
                start_date = datetime.fromisoformat(start_date_str)
            else:
                start_date = start_date_str

            if isinstance(end_date_str, str):
                end_date_str = end_date_str.replace("Z", "+00:00")
                end_date = datetime.fromisoformat(end_date_str)
            else:
                end_date = end_date_str

            initial_capital = Decimal(str(config.get("initial_capital", 10000)))

            # 获取价格数据
            assets_data = {}
            for asset_id in asset_ids:
                ohlcv_list = await self.asset_service.get_ohlcv(
                    asset_id=asset_id,
                    interval="1d",
                    start_time=start_date,
                    end_time=end_date,
                    limit=500,
                )

                if not ohlcv_list:
                    raise ValueError(f"资产 {asset_id} 无历史数据")

                asset = await self.asset_service.get_asset_by_id(asset_id)
                # 传递完整的OHLCV数据
                assets_data[str(asset_id)] = {
                    "symbol": asset.symbol if asset else "unknown",
                    "prices": [
                        {
                            "time": o.time,
                            "open": o.open,
                            "high": o.high,
                            "low": o.low,
                            "close": o.close,
                            "volume": o.volume,
                        }
                        for o in ohlcv_list
                    ],
                }

            # 执行回测
            result_data = await self._execute_strategy(
                template.code,
                assets_data,
                params,
                initial_capital,
            )

            # 处理结果中的datetime对象（JSONB需要字符串）
            def serialize_datetime(obj):
                """将datetime转换为ISO字符串"""
                if isinstance(obj, dict):
                    return {k: serialize_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_datetime(item) for item in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                return obj

            # 序列化结果数据用于JSON存储
            serializable_result = serialize_datetime(result_data)

            # 辅助函数：安全转换为Decimal
            def safe_decimal(value, default="0"):
                """安全将值转换为Decimal，处理None和异常值"""
                if value is None:
                    return Decimal(default)
                try:
                    return Decimal(str(value))
                except:
                    return Decimal(default)

            # 保存结果
            result = BacktestResult(
                job_id=job_id,
                total_return=safe_decimal(result_data.get("total_return")),
                annualized_return=safe_decimal(result_data.get("annualized_return")),
                max_drawdown=safe_decimal(result_data.get("max_drawdown")),
                volatility=safe_decimal(result_data.get("volatility")),
                sharpe_ratio=safe_decimal(result_data.get("sharpe_ratio")),
                win_rate=safe_decimal(result_data.get("win_rate")),
                total_trades=result_data.get("total_trades", 0),
                profit_trades=result_data.get("profit_trades", 0),
                loss_trades=result_data.get("loss_trades", 0),
                equity_curve=serializable_result.get("equity_curve"),
                trades=serializable_result.get("trades"),
                metrics=serializable_result,
            )
            self.session.add(result)

            # 更新任务状态
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.result = serializable_result

            await self.session.flush()
            logger.info(f"回测完成: {job_id}")

            return result

        except Exception as e:
            logger.error(f"回测失败 {job_id}: {e}")
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
            return None

    async def _execute_strategy(
        self,
        template_code: str,
        assets_data: Dict,
        parameters: Dict,
        initial_capital: Decimal,
    ) -> Dict:
        """
        根据策略模板执行回测

        Args:
            template_code: 策略模板代码
            assets_data: 资产价格数据
            parameters: 策略参数
            initial_capital: 初始资金

        Returns:
            回测结果
        """
        if template_code == "ma_cross":
            # 均线突破：单资产
            engine = MACrossStrategy(initial_capital=initial_capital)

            # 使用第一个资产的数据（已包含完整OHLCV）
            first_asset = list(assets_data.values())[0]
            prices = first_asset["prices"]

            return engine.run(prices, parameters)

        elif template_code == "momentum":
            # 动量轮动：多资产
            engine = MomentumStrategy(initial_capital=initial_capital)

            # 构建多资产价格字典
            multi_prices = {}
            for asset_id, data in assets_data.items():
                multi_prices[asset_id] = data["prices"]

            return engine.run(multi_prices, parameters)

        elif template_code == "dca":
            # 定投：单资产
            engine = DCAStrategy(initial_capital=initial_capital)

            first_asset = list(assets_data.values())[0]
            prices = first_asset["prices"]

            return engine.run(prices, parameters)

        elif template_code == "risk_parity":
            # 风险平价：多资产
            engine = RiskParityStrategy(initial_capital=initial_capital)

            multi_prices = {}
            for asset_id, data in assets_data.items():
                multi_prices[asset_id] = data["prices"]

            return engine.run(multi_prices, parameters)

        else:
            return {"error": f"未知的策略模板: {template_code}"}