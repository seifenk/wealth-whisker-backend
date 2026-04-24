"""
资产服务模块

负责资产数据的查询和指标计算
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, OHLCV, AssetMetric


class AssetService:
    """资产服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_assets(
        self,
        asset_type: Optional[str] = None,
        is_active: Optional[bool] = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Asset]:
        """
        获取资产列表

        Args:
            asset_type: 资产类型过滤
            is_active: 是否只返回活跃资产
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            资产列表
        """
        query = select(Asset)

        if asset_type:
            query = query.where(Asset.asset_type == asset_type)
        if is_active is not None:
            query = query.where(Asset.is_active == is_active)

        query = query.order_by(Asset.symbol).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_asset_by_id(self, asset_id: UUID) -> Optional[Asset]:
        """
        根据ID获取资产
        """
        result = await self.session.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        return result.scalar_one_or_none()

    async def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """
        根据符号获取资产
        """
        result = await self.session.execute(
            select(Asset).where(Asset.symbol == symbol)
        )
        return result.scalar_one_or_none()

    async def get_ohlcv(
        self,
        asset_id: UUID,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[OHLCV]:
        """
        获取K线数据

        Args:
            asset_id: 资产ID
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        query = select(OHLCV).where(
            and_(
                OHLCV.asset_id == asset_id,
                OHLCV.interval == interval,
            )
        )

        if start_time:
            query = query.where(OHLCV.time >= start_time)
        if end_time:
            query = query.where(OHLCV.time <= end_time)

        query = query.order_by(desc(OHLCV.time)).limit(limit)

        result = await self.session.execute(query)
        ohlcv_list = list(result.scalars().all())

        # 返回正序数据（时间从早到晚）
        ohlcv_list.reverse()
        return ohlcv_list

    async def get_latest_metric(self, asset_id: UUID) -> Optional[AssetMetric]:
        """
        获取资产最新指标
        """
        result = await self.session.execute(
            select(AssetMetric)
            .where(AssetMetric.asset_id == asset_id)
            .order_by(desc(AssetMetric.calculated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_dashboard_data(
        self,
        asset_type: Optional[str] = None,
    ) -> List[dict]:
        """
        获取决策看板数据

        Args:
            asset_type: 资产类型过滤

        Returns:
            看板数据列表（包含资产信息、最新价格、指标等）
        """
        # 查询活跃资产
        query = select(Asset).where(Asset.is_active == True)
        if asset_type:
            query = query.where(Asset.asset_type == asset_type)

        result = await self.session.execute(query)
        assets = list(result.scalars().all())

        dashboard_data = []
        for asset in assets:
            metric = await self.get_latest_metric(asset.id)

            data = {
                "id": str(asset.id),
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "exchange": asset.exchange,
                "currency": asset.currency,
            }

            if metric:
                data.update({
                    "price": float(metric.price) if metric.price else None,
                    "change_24h": float(metric.change_24h) if metric.change_24h else None,
                    "change_7d": float(metric.change_7d) if metric.change_7d else None,
                    "volatility_30d": float(metric.volatility_30d) if metric.volatility_30d else None,
                    "sharpe_ratio": float(metric.sharpe_ratio) if metric.sharpe_ratio else None,
                    "risk_level": metric.risk_level,
                    "trend_signal": metric.trend_signal,
                    "confidence_score": float(metric.confidence_score) if metric.confidence_score else None,
                    "updated_at": metric.calculated_at.isoformat() if metric.calculated_at else None,
                })

            dashboard_data.append(data)

        return dashboard_data

    async def get_price_history(
        self,
        asset_id: UUID,
        days: int = 30,
        interval: str = "1h",
    ) -> List[Tuple[datetime, Decimal]]:
        """
        获取价格历史数据

        Args:
            asset_id: 走产ID
            days: 历史天数
            interval: K线周期

        Returns:
            (时间, 价格) 元组列表
        """
        start_time = datetime.now(timezone.utc) - timedelta(days=days)

        ohlcv_list = await self.get_ohlcv(
            asset_id=asset_id,
            interval=interval,
            start_time=start_time,
        )

        return [(ohlcv.time, ohlcv.close) for ohlcv in ohlcv_list]

    async def calculate_performance_metrics(
        self,
        asset_id: UUID,
        days: int = 30,
    ) -> dict:
        """
        计算资产绩效指标

        Args:
            asset_id: 资产ID
            days: 计算周期天数

        Returns:
            指标字典
        """
        ohlcv_list = await self.get_ohlcv(
            asset_id=asset_id,
            interval="1d",
            start_time=datetime.now(timezone.utc) - timedelta(days=days),
        )

        if not ohlcv_list or len(ohlcv_list) < 2:
            return {}

        prices = [float(o.close) for o in ohlcv_list]

        # 累计收益
        total_return = (prices[-1] - prices[0]) / prices[0] * 100

        # 日收益率
        daily_returns = []
        for i in range(1, len(prices)):
            daily_returns.append((prices[i] - prices[i-1]) / prices[i-1])

        # 波动率（标准差）
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        volatility = variance ** 0.5 * 100

        # 最大回撤
        max_price = prices[0]
        max_drawdown = 0
        for price in prices:
            if price > max_price:
                max_price = price
            drawdown = (max_price - price) / max_price * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 夏普比率（简化计算，假设无风险利率为3%年化）
        annual_return = total_return / days * 365
        annual_volatility = volatility * (365 ** 0.5)
        sharpe_ratio = (annual_return - 3) / annual_volatility if annual_volatility > 0 else 0

        return {
            "total_return": round(total_return, 2),
            "annualized_return": round(annual_return, 2),
            "volatility": round(volatility, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "data_points": len(prices),
        }