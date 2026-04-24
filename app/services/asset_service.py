"""
资产服务模块

负责资产数据的查询和指标计算
三层缓存架构：Redis（短期）→ PostgreSQL（长期）→ 数据源API（实时）
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.asset import Asset, OHLCV, AssetMetric
from app.data.connectors import OKXConnector, YahooFinanceConnector, GoldConnector, EastMoneyConnector
from app.services.cache_service import CacheService, get_cache_service
from app.data.constants import normalize_interval, is_valid_interval
from app.data.calculators import MetricsCalculator


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
    # 黄金（GC=F是黄金期货，价格接近现货）
    "XAU": "GC=F",  # 黄金现货（用期货代替）
    "GOLD": "GC=F", # 黄金现货
    "GLD": "GLD",   # 黄金ETF（约1/10盎司）
    "IAU": "IAU",   # 黄金ETF
    "GOLD_FUT": "GC=F", # 黄金期货
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
    """资产服务类 - 三层缓存架构"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._connectors = {}  # 连接器实例缓存

    async def _get_cache(self) -> CacheService:
        """获取缓存服务"""
        return await get_cache_service()

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
            interval: K线周期（OKX格式：小写m=分钟，大写H/D/W/M=小时/天/周/月）
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            force_refresh: 是否强制从数据源刷新

        Returns:
            K线数据列表
        """
        # 标准化interval为OKX格式
        interval = normalize_interval(interval)

        # 验证interval是否有效
        if not is_valid_interval(interval):
            logger.warning(f"Invalid interval '{interval}', using default 1H")
            interval = "1H"
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
        获取资产最新指标（三层缓存）

        1. Redis缓存（5分钟） - 最快
        2. 数据库指标（1小时内） - 中等
        3. 数据源API实时获取 - 最慢

        Args:
            asset_id: 资产ID
            force_refresh: 是否强制刷新

        Returns:
            资产指标
        """
        cache = await self._get_cache()
        cache_key = CacheService.metric_key(str(asset_id))

        # 1. 先查Redis缓存
        if not force_refresh:
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(f"Metric cache hit for {asset_id}")
                # 从缓存重建metric对象（不写数据库）
                return AssetMetric(
                    asset_id=asset_id,
                    price=Decimal(str(cached.get('price', 0))),
                    change_24h=Decimal(str(cached.get('change_24h'))) if cached.get('change_24h') else None,
                    change_7d=Decimal(str(cached.get('change_7d'))) if cached.get('change_7d') else None,
                    volatility_30d=Decimal(str(cached.get('volatility_30d'))) if cached.get('volatility_30d') else None,
                    sharpe_ratio=Decimal(str(cached.get('sharpe_ratio'))) if cached.get('sharpe_ratio') else None,
                    trend_signal=cached.get('trend_signal'),
                    risk_level=cached.get('risk_level'),
                    confidence_score=Decimal(str(cached.get('confidence_score'))) if cached.get('confidence_score') else None,
                    calculated_at=datetime.fromisoformat(cached.get('calculated_at')) if cached.get('calculated_at') else None,
                )

        # 2. 查数据库
        if not force_refresh:
            result = await self.session.execute(
                select(AssetMetric)
                .where(AssetMetric.asset_id == asset_id)
                .order_by(desc(AssetMetric.calculated_at))
                .limit(1)
            )
            metric = result.scalar_one_or_none()

            # 如果指标是最近的（1小时内），缓存并返回
            if metric and metric.calculated_at:
                age = datetime.now(timezone.utc) - metric.calculated_at
                if age < timedelta(hours=1):
                    # 写入Redis缓存
                    await cache.set(cache_key, {
                        'price': float(metric.price or 0),
                        'change_24h': float(metric.change_24h or 0),
                        'change_7d': float(metric.change_7d or 0),
                        'volatility_30d': float(metric.volatility_30d or 0),
                        'sharpe_ratio': float(metric.sharpe_ratio or 0),
                        'trend_signal': metric.trend_signal,
                        'risk_level': metric.risk_level,
                        'confidence_score': float(metric.confidence_score or 0),
                        'calculated_at': metric.calculated_at.isoformat(),
                    }, settings.CACHE_METRIC_TTL)
                    return metric

        # 3. 实时获取行情数据
        asset = await self.get_asset_by_id(asset_id)
        if not asset:
            return None

        connector = await self._get_connector(asset.asset_type)
        if not connector:
            return None

        try:
            ds_symbol = SYMBOL_MAP.get(asset.symbol, asset.symbol)
            ticker = await connector.get_ticker(ds_symbol)

            price = ticker.last_price
            # 获取足够的历史数据进行计算（需要至少30天）
            ohlcv_list = await self.get_ohlcv(asset_id, interval="1d", limit=60)

            # 使用专业计算器计算指标
            if ohlcv_list and len(ohlcv_list) >= 2:
                closes = [float(o.close) for o in ohlcv_list]

                # 使用MetricsCalculator计算所有指标
                calculated = MetricsCalculator.calculate_all_metrics(closes)

                change_24h = Decimal(str(calculated.get("change_24h"))) if calculated.get("change_24h") else None
                change_7d = Decimal(str(calculated.get("change_7d"))) if calculated.get("change_7d") else None
                volatility_30d = Decimal(str(calculated.get("volatility_30d"))) if calculated.get("volatility_30d") else None
                sharpe_ratio = Decimal(str(calculated.get("sharpe_ratio"))) if calculated.get("sharpe_ratio") else None
                trend_signal = calculated.get("trend_signal", "neutral")
                risk_level = calculated.get("risk_level", "medium")
                confidence_score = Decimal(str(calculated.get("confidence_score"))) if calculated.get("confidence_score") else None
            else:
                # 数据不足，使用基础判断
                change_24h = Decimal(str(float(ticker.change_24h))) if ticker.change_24h else None
                change_7d = None
                volatility_30d = None
                sharpe_ratio = None
                trend_signal = "neutral"
                risk_level = "medium"
                confidence_score = Decimal("0.3")

            metric = AssetMetric(
                asset_id=asset_id,
                price=price,
                change_24h=change_24h,
                change_7d=change_7d,
                volatility_30d=volatility_30d,
                sharpe_ratio=sharpe_ratio,
                trend_signal=trend_signal,
                risk_level=risk_level,
                confidence_score=confidence_score,
            )
            self.session.add(metric)

            # 写入Redis缓存
            await cache.set(cache_key, {
                'price': float(price),
                'change_24h': float(change_24h or 0),
                'change_7d': float(change_7d or 0),
                'volatility_30d': float(volatility_30d or 0),
                'sharpe_ratio': float(sharpe_ratio or 0),
                'trend_signal': trend_signal,
                'risk_level': risk_level,
                'confidence_score': float(confidence_score or 0),
                'calculated_at': datetime.now(timezone.utc).isoformat(),
            }, settings.CACHE_METRIC_TTL)

            return metric

        except Exception as e:
            logger.error(f"获取资产指标失败 {asset.symbol}: {e}")
            return None

    async def get_dashboard_data(
        self,
        asset_type: Optional[str] = None,
        force_refresh: bool = False,
        risk_preference: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> Tuple[List[dict], dict]:
        """
        获取决策看板数据（带缓存）

        Args:
            asset_type: 资产类型过滤
            force_refresh: 是否强制刷新
            risk_preference: 风险偏好 ('conservative', 'balanced', 'aggressive')
            sort_by: 排序字段 ('change_24h', 'change_7d', 'sharpe_ratio', 'volatility', 'recommendation')

        Returns:
            (看板数据列表, 查询参数)
        """
        cache = await self._get_cache()
        cache_key = CacheService.dashboard_key(asset_type)

        # 1. 先查Redis缓存
        if not force_refresh:
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(f"Dashboard cache hit for {asset_type or 'all'}")
                # 应用过滤和排序
                filtered_data = self._apply_filters_and_sort(
                    cached,
                    risk_preference,
                    sort_by,
                )
                return filtered_data, {
                    "asset_type_filter": asset_type,
                    "risk_preference": risk_preference,
                    "sort_by": sort_by,
                }

        # 2. 查数据库并组装数据
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

                # 计算推荐分数
                data["recommendation_score"] = self._calculate_recommendation_score(
                    data,
                    risk_preference or "balanced",
                )

            dashboard_data.append(data)

        # 3. 写入Redis缓存（原始数据）
        await cache.set(cache_key, dashboard_data, settings.CACHE_DASHBOARD_TTL)

        # 应用过滤和排序
        filtered_data = self._apply_filters_and_sort(
            dashboard_data,
            risk_preference,
            sort_by,
        )

        return filtered_data, {
            "asset_type_filter": asset_type,
            "risk_preference": risk_preference,
            "sort_by": sort_by,
        }

    def _calculate_recommendation_score(
        self,
        data: dict,
        risk_preference: str,
    ) -> float:
        """
        计算推荐分数（综合评分）

        根据风险偏好调整评分权重

        Args:
            data: 资产数据
            risk_preference: 风险偏好

        Returns:
            推荐分数（0-100）
        """
        score = 0.0

        # 基础分数
        change_24h = data.get("change_24h") or 0
        sharpe_ratio = data.get("sharpe_ratio") or 0
        volatility = data.get("volatility_30d") or 30  # 默认中等波动
        risk_level = data.get("risk_level") or "medium"
        trend_signal = data.get("trend_signal") or "neutral"
        confidence = data.get("confidence_score") or 0.5

        # 根据风险偏好调整权重
        if risk_preference == "conservative":
            # 保守型：重视低波动、低风险、稳定性
            # 波动率评分（低波动高分）
            volatility_score = max(0, 100 - volatility)  # 波动率越低分数越高

            # 风险等级评分
            risk_score = {"low": 40, "medium": 20, "high": 0}.get(risk_level, 20)

            # 夏普比率评分（稳健收益）
            sharpe_score = min(sharpe_ratio * 10, 30)

            # 趋势信号（保守型偏好稳定）
            trend_score = {"neutral": 15, "bullish": 10, "bearish": -5}.get(trend_signal, 0)

            score = volatility_score * 0.4 + risk_score + sharpe_score + trend_score + confidence * 15

        elif risk_preference == "aggressive":
            # 激进型：重视高收益、趋势强度
            # 涨跌幅评分
            change_score = min(abs(change_24h) * 5, 40)  # 涨跌都可以，重要的是幅度
            if change_24h > 0:
                change_score = min(change_24h * 5, 50)  # 涨幅加分

            # 趋势信号（激进型偏好明确趋势）
            trend_score = {"bullish": 30, "bearish": 10, "neutral": 5}.get(trend_signal, 5)

            # 夏普比率（高收益）
            sharpe_score = min(sharpe_ratio * 15, 20)

            # 波动容忍（高波动不扣分）
            volatility_score = 10

            score = change_score + trend_score + sharpe_score + volatility_score + confidence * 20

        else:  # balanced
            # 平衡型：综合考量
            # 涨跌幅
            change_score = change_24h * 2 if change_24h > 0 else abs(change_24h) * 1

            # 夏普比率
            sharpe_score = min(sharpe_ratio * 12, 30)

            # 波动率（适度波动）
            volatility_score = max(0, 50 - volatility * 0.5)

            # 趋势信号
            trend_score = {"bullish": 20, "neutral": 10, "bearish": 0}.get(trend_signal, 10)

            # 风险等级
            risk_score = {"low": 10, "medium": 5, "high": -5}.get(risk_level, 5)

            score = change_score + sharpe_score + volatility_score * 0.3 + trend_score + risk_score + confidence * 15

        return round(min(max(score, 0), 100), 2)

    def _apply_filters_and_sort(
        self,
        data: List[dict],
        risk_preference: Optional[str],
        sort_by: Optional[str],
    ) -> List[dict]:
        """
        应用过滤和排序

        Args:
            data: 原始数据
            risk_preference: 风险偏好过滤
            sort_by: 排序字段

        Returns:
            处理后的数据
        """
        # 风险偏好过滤
        if risk_preference == "conservative":
            # 保守型：只显示低风险资产
            data = [d for d in data if d.get("risk_level") in ["low", "medium"]]
        elif risk_preference == "aggressive":
            # 激进型：显示所有资产，但按趋势强度排序
            pass  # 不过滤

        # 重新计算推荐分数（根据风险偏好）
        for d in data:
            d["recommendation_score"] = self._calculate_recommendation_score(
                d,
                risk_preference or "balanced",
            )

        # 排序
        if sort_by:
            reverse = True  # 默认降序

            if sort_by == "change_24h":
                data.sort(key=lambda x: x.get("change_24h") or 0, reverse=reverse)
            elif sort_by == "change_7d":
                data.sort(key=lambda x: x.get("change_7d") or 0, reverse=reverse)
            elif sort_by == "sharpe_ratio":
                data.sort(key=lambda x: x.get("sharpe_ratio") or 0, reverse=reverse)
            elif sort_by == "volatility":
                reverse = False  # 波动率升序（低波动优先）
                data.sort(key=lambda x: x.get("volatility_30d") or 999, reverse=reverse)
            elif sort_by == "recommendation":
                data.sort(key=lambda x: x.get("recommendation_score") or 0, reverse=True)
        else:
            # 默认按推荐分数排序
            data.sort(key=lambda x: x.get("recommendation_score") or 0, reverse=True)

        return data

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

        # 波动率（年化）
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        daily_volatility = variance ** 0.5
        annualized_volatility = daily_volatility * (252 ** 0.5) * 100

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
        sharpe_ratio = (annual_return - 3) / annualized_volatility if annualized_volatility > 0 else 0

        return {
            "total_return": round(total_return, 2),
            "annualized_return": round(annual_return, 2),
            "volatility": round(annualized_volatility, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "data_points": len(prices),
        }

    async def get_realtime_price(self, symbol: str, asset_type: str = None) -> Optional[Decimal]:
        """
        直接获取实时价格（三层缓存）

        1. Redis缓存（60秒） - 最快
        2. 数据库指标（1小时内） - 中等
        3. 数据源API实时获取 - 最慢

        Args:
            symbol: 资产符号
            asset_type: 资产类型（可选，用于选择连接器）

        Returns:
            当前价格
        """
        # 1. 先查Redis缓存（60秒有效期）
        cache = await self._get_cache()
        cache_key = CacheService.realtime_price_key(symbol)
        cached = await cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for {symbol}")
            return Decimal(str(cached['price']))

        # 2. 查数据库最近的指标（1小时内）
        asset = await self.get_asset_by_symbol(symbol)
        if asset:
            metric = await self.get_latest_metric(str(asset.id))
            if metric and metric.calculated_at:
                age = datetime.now(timezone.utc) - metric.calculated_at
                if age < timedelta(hours=1) and metric.price:
                    # 写入Redis缓存供下次使用
                    await cache.set(cache_key, {'price': float(metric.price)}, settings.CACHE_REALTIME_PRICE_TTL)
                    return metric.price

        # 3. 实时从数据源获取
        if not asset_type:
            if asset:
                asset_type = asset.asset_type

        # 根据符号推断类型
        if not asset_type:
            if symbol in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
                asset_type = "crypto"
            elif symbol in ["AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "TSLA", "BABA", "JD", "NIO", "SPY", "QQQ"]:
                asset_type = "stock"
            elif symbol in ["XAU", "GOLD", "GLD", "IAU", "GOLD_FUT"]:
                asset_type = "gold"
            elif symbol.isdigit():
                asset_type = "fund"

        connector = await self._get_connector(asset_type)
        if not connector:
            return None

        try:
            ds_symbol = SYMBOL_MAP.get(symbol, symbol)
            ticker = await connector.get_ticker(ds_symbol)
            price = ticker.last_price

            # 写入Redis缓存
            await cache.set(cache_key, {'price': float(price)}, settings.CACHE_REALTIME_PRICE_TTL)
            logger.debug(f"Cache set for {symbol}: {price}")

            return price
        except Exception as e:
            logger.error(f"获取实时价格失败 {symbol}: {e}")
            return None