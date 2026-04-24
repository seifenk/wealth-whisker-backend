"""
资产服务模块

负责资产数据的查询和指标计算
优先查数据库缓存，无数据时实时调用数据源
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, OHLCV, AssetMetric
from app.data.connectors import OKXConnector, YahooFinanceConnector, GoldConnector, EastMoneyConnector


# 资产类型到连接器的映射
CONNECTOR_MAP = {
    "crypto": OKXConnector,
    "stock": YahooFinanceConnector,
    "gold": GoldConnector,
    "fund": EastMoneyConnector,
}

# 资产符号到数据源符号的映射
SYMBOL_MAP = {
    # 加密货币 (ccxt格式)
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "DOGE": "DOGE/USDT",
    # 股票/ETF (Yahoo格式)
    "AAPL": "AAPL",
    "GOOGL": "GOOGL",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "META": "META",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "BABA": "BABA",
    "JD": "JD",
    "NIO": "NIO",
    "SPY": "SPY",
    "QQQ": "QQQ",
    # 黄金
    "GLD": "GLD",
    "IAU": "IAU",
    "GOLD_FUT": "GC=F",
    # 基金 (东方财富代码)
    "000001": "000001",
    "000011": "000011",
    "110022": "110022",
    "161725": "161725",
    "519674": "519674",
    "510300": "510300",
    "510050": "510050",
}


class AssetService:
    """资产服务类 - 支持实时数据获取"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._connectors = {}  # 连接器实例缓存

    async def _get_connector(self, asset_type: str):
        """获取数据源连接器"""
        if asset_type not in self._connectors:
            connector_class = CONNECTOR_MAP.get(asset_type)
            if connector_class:
                self._connectors[asset_type] = connector_class()
        return self._connectors.get(asset_type)

    async def close_connectors(self):
        """关闭所有连接器"""
        for connector in self._connectors.values():
            if hasattr(connector, 'close'):
                await connector.close()
        self._connectors.clear()

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
        """根据ID获取资产"""
        result = await self.session.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        return result.scalar_one_or_none()

    async def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """根据符号获取资产"""
        result = await self.session.execute(
            select(Asset).where(Asset.symbol == symbol)
        )
        return result.scalar_one_or_none()

    async def get_or_create_asset(
        self,
        symbol: str,
        name: str,
        asset_type: str,
        exchange: str = None,
        currency: str = "USD",
    ) -> Asset:
        """获取或创建资产记录"""
        asset = await self.get_asset_by_symbol(symbol)
        if not asset:
            asset = Asset(
                symbol=symbol,
                name=name,
                asset_type=asset_type,
                exchange=exchange,
                currency=currency,
                is_active=True,
            )
            self.session.add(asset)
            await self.session.flush()
        return asset

    async def get_ohlcv(
        self,
        asset_id: UUID,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        force_refresh: bool = False,
    ) -> List[OHLCV]:
        """
        获取K线数据

        Args:
            asset_id: 资产ID
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            force_refresh: 是否强制从数据源刷新

        Returns:
            K线数据列表
        """
        # 1. 先查数据库
        if not force_refresh:
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

            if ohlcv_list:
                ohlcv_list.reverse()
                return ohlcv_list

        # 2. 数据库无数据，实时获取
        asset = await self.get_asset_by_id(asset_id)
        if not asset:
            return []

        connector = await self._get_connector(asset.asset_type)
        if not connector:
            return []

        try:
            # 获取数据源符号
            ds_symbol = SYMBOL_MAP.get(asset.symbol, asset.symbol)

            ohlcv_data = await connector.get_ohlcv(
                symbol=ds_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )

            # 3. 入库缓存（可选）
            for ohlcv in ohlcv_data:
                existing = await self.session.execute(
                    select(OHLCV).where(
                        and_(
                            OHLCV.asset_id == asset_id,
                            OHLCV.time == ohlcv.time,
                            OHLCV.interval == interval,
                        )
                    )
                )
                if not existing.scalar_one_or_none():
                    new_ohlcv = OHLCV(
                        time=ohlcv.time,
                        asset_id=asset_id,
                        interval=interval,
                        open=ohlcv.open,
                        high=ohlcv.high,
                        low=ohlcv.low,
                        close=ohlcv.close,
                        volume=ohlcv.volume,
                    )
                    self.session.add(new_ohlcv)

            return ohlcv_data

        except Exception as e:
            logger.error(f"获取K线数据失败 {asset.symbol}: {e}")
            return []

    async def get_latest_metric(
        self,
        asset_id: UUID,
        force_refresh: bool = False,
    ) -> Optional[AssetMetric]:
        """
        获取资产最新指标

        Args:
            asset_id: 资产ID
            force_refresh: 是否强制刷新

        Returns:
            资产指标
        """
        # 1. 先查数据库
        if not force_refresh:
            result = await self.session.execute(
                select(AssetMetric)
                .where(AssetMetric.asset_id == asset_id)
                .order_by(desc(AssetMetric.calculated_at))
                .limit(1)
            )
            metric = result.scalar_one_or_none()

            # 如果指标是最近的（1小时内），直接返回
            if metric and metric.calculated_at:
                age = datetime.now(timezone.utc) - metric.calculated_at
                if age < timedelta(hours=1):
                    return metric

        # 2. 实时获取行情数据
        asset = await self.get_asset_by_id(asset_id)
        if not asset:
            return None

        connector = await self._get_connector(asset.asset_type)
        if not connector:
            return None

        try:
            ds_symbol = SYMBOL_MAP.get(asset.symbol, asset.symbol)
            ticker = await connector.get_ticker(ds_symbol)

            # 计算指标
            price = ticker.last_price

            # 获取K线数据计算更多指标
            ohlcv_list = await self.get_ohlcv(asset_id, interval="1d", limit=30)

            change_24h = float(ticker.change_24h) if ticker.change_24h else None
            volatility_30d = None
            trend_signal = "neutral"
            risk_level = "medium"

            if ohlcv_list and len(ohlcv_list) >= 2:
                # 计算波动率
                closes = [float(o.close) for o in ohlcv_list]
                mean = sum(closes) / len(closes)
                variance = sum((c - mean) ** 2 for c in closes) / len(closes)
                volatility_30d = Decimal(str((variance ** 0.5) / mean * 100)) if mean > 0 else None

                # 判断趋势
                if change_24h:
                    if change_24h > 2:
                        trend_signal = "bullish"
                    elif change_24h < -2:
                        trend_signal = "bearish"

                # 判断风险等级
                if volatility_30d:
                    if volatility_30d > 50:
                        risk_level = "high"
                    elif volatility_30d < 20:
                        risk_level = "low"

            # 创建新指标记录
            metric = AssetMetric(
                asset_id=asset_id,
                price=price,
                change_24h=Decimal(str(change_24h)) if change_24h else None,
                volatility_30d=volatility_30d,
                trend_signal=trend_signal,
                risk_level=risk_level,
            )
            self.session.add(metric)

            return metric

        except Exception as e:
            logger.error(f"获取资产指标失败 {asset.symbol}: {e}")
            return None

    async def get_dashboard_data(
        self,
        asset_type: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[dict]:
        """
        获取决策看板数据

        Args:
            asset_type: 资产类型过滤
            force_refresh: 是否强制刷新

        Returns:
            看板数据列表
        """
        # 获取资产列表
        query = select(Asset).where(Asset.is_active == True)
        if asset_type:
            query = query.where(Asset.asset_type == asset_type)

        result = await self.session.execute(query)
        assets = list(result.scalars().all())

        dashboard_data = []
        for asset in assets:
            metric = await self.get_latest_metric(asset.id, force_refresh=force_refresh)

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
        start_time = datetime.now(timezone.utc) - timedelta(days=days)

        ohlcv_list = await self.get_ohlcv(
            asset_id=asset_id,
            interval="1d",
            start_time=start_time,
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

    async def get_realtime_price(self, symbol: str, asset_type: str = None) -> Optional[Decimal]:
        """
        直接获取实时价格（不依赖数据库）

        Args:
            symbol: 资产符号
            asset_type: 资产类型（可选，用于选择连接器）

        Returns:
            当前价格
        """
        # 尝试从数据库获取资产类型
        if not asset_type:
            asset = await self.get_asset_by_symbol(symbol)
            if asset:
                asset_type = asset.asset_type

        # 根据符号推断类型
        if not asset_type:
            if symbol in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
                asset_type = "crypto"
            elif symbol in ["AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "TSLA"]:
                asset_type = "stock"
            elif symbol in ["GLD", "IAU", "GOLD_FUT"]:
                asset_type = "gold"
            elif symbol.isdigit():
                asset_type = "fund"

        connector = await self._get_connector(asset_type)
        if not connector:
            return None

        try:
            ds_symbol = SYMBOL_MAP.get(symbol, symbol)
            ticker = await connector.get_ticker(ds_symbol)
            return ticker.last_price
        except Exception as e:
            logger.error(f"获取实时价格失败 {symbol}: {e}")
            return None