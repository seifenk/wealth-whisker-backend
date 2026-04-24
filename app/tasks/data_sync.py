"""
数据同步任务模块

负责从各数据源同步资产数据到数据库
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_maker
from app.data.connectors.okx_connector import OKXConnector
from app.models.asset import Asset, OHLCV, AssetMetric


# 加密货币交易对配置
CRYPTO_SYMBOLS = [
    ("BTC-USDT", "BTC", "Bitcoin", "crypto"),
    ("ETH-USDT", "ETH", "Ethereum", "crypto"),
    ("SOL-USDT", "SOL", "Solana", "crypto"),
    ("XRP-USDT", "XRP", "Ripple", "crypto"),
    ("DOGE-USDT", "DOGE", "Dogecoin", "crypto"),
]


async def get_or_create_asset(
    session: AsyncSession,
    symbol: str,
    display_symbol: str,
    name: str,
    asset_type: str,
    exchange: str = "OKX",
) -> Asset:
    """
    获取或创建资产记录
    """
    result = await session.execute(
        select(Asset).where(Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        asset = Asset(
            symbol=symbol,
            name=name,
            asset_type=asset_type,
            exchange=exchange,
            currency="USDT",
            is_active=True,
        )
        session.add(asset)
        await session.flush()
        logger.info(f"Created new asset: {symbol}")

    return asset


async def save_ohlcv_data(
    session: AsyncSession,
    asset_id: UUID,
    ohlcv_list: List,
    interval: str = "1h",
) -> int:
    """
    保存K线数据到数据库

    Returns:
        新增数据数量
    """
    if not ohlcv_list:
        return 0

    added_count = 0
    for ohlcv in ohlcv_list:
        # 检查是否已存在
        existing = await session.execute(
            select(OHLCV).where(
                and_(
                    OHLCV.asset_id == asset_id,
                    OHLCV.time == ohlcv.time,
                    OHLCV.interval == interval,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

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
        session.add(new_ohlcv)
        added_count += 1

    return added_count


async def update_asset_metric(
    session: AsyncSession,
    asset_id: UUID,
    ticker_data,
    ohlcv_data: List,
) -> AssetMetric:
    """
    计算并更新资产指标
    """
    # 计算基础指标
    price = ticker_data.last_price

    # 计算涨跌幅（如果有历史数据）
    change_24h = None
    change_7d = None
    volatility_30d = None

    if len(ohlcv_data) >= 24:
        # 24小时涨跌幅
        prev_close = ohlcv_data[-24].close if len(ohlcv_data) >= 24 else None
        if prev_close and prev_close > 0:
            change_24h = (price - prev_close) / prev_close * 100

    if len(ohlcv_data) >= 168:  # 7天 * 24小时
        prev_close_7d = ohlcv_data[-168].close
        if prev_close_7d and prev_close_7d > 0:
            change_7d = (price - prev_close_7d) / prev_close_7d * 100

    # 计算波动率（简单标准差）
    if len(ohlcv_data) >= 720:  # 30天 * 24小时
        closes = [float(o.close) for o in ohlcv_data[-720:]]
        mean = sum(closes) / len(closes)
        variance = sum((c - mean) ** 2 for c in closes) / len(closes)
        volatility_30d = Decimal(str((variance ** 0.5) / mean * 100))

    # 判断趋势信号
    trend_signal = "neutral"
    if change_24h:
        if change_24h > 2:
            trend_signal = "bullish"
        elif change_24h < -2:
            trend_signal = "bearish"

    # 判断风险等级
    risk_level = "medium"
    if volatility_30d:
        if volatility_30d > 50:
            risk_level = "high"
        elif volatility_30d < 20:
            risk_level = "low"

    metric = AssetMetric(
        asset_id=asset_id,
        price=price,
        change_24h=change_24h,
        change_7d=change_7d,
        volatility_30d=volatility_30d,
        trend_signal=trend_signal,
        risk_level=risk_level,
    )
    session.add(metric)
    return metric


@celery_app.task(bind=True, name="sync_crypto_data")
def sync_crypto_data_task(self, symbols: Optional[List[str]] = None):
    """
    同步加密货币数据任务

    Args:
        symbols: 要同步的交易对列表，None表示同步全部配置的交易对
    """
    logger.info(f"Starting crypto data sync task: {self.request.id}")

    import asyncio

    async def _sync():
        connector = OKXConnector()

        try:
            async with async_session_maker() as session:
                # 获取要同步的交易对
                sync_symbols = symbols or CRYPTO_SYMBOLS
                total_added = 0

                for inst_id, display_sym, name, asset_type in sync_symbols:
                    try:
                        # 1. 获取或创建资产
                        asset = await get_or_create_asset(
                            session, display_sym, display_sym, name, asset_type
                        )

                        # 2. 获取K线数据（最近7天的小时数据）
                        end_time = datetime.now(timezone.utc)
                        start_time = end_time - timedelta(days=7)

                        ohlcv_data = await connector.get_ohlcv(
                            symbol=inst_id,
                            interval="1h",
                            start_time=start_time,
                            end_time=end_time,
                            limit=168,
                        )

                        # 3. 保存K线数据
                        added = await save_ohlcv_data(
                            session, asset.id, ohlcv_data, "1h"
                        )
                        total_added += added
                        logger.info(f"Synced {inst_id}: {added} new OHLCV records")

                        # 4. 获取实时行情
                        ticker = await connector.get_ticker(inst_id)

                        # 5. 更新资产指标
                        await update_asset_metric(
                            session, asset.id, ticker, ohlcv_data
                        )

                    except Exception as e:
                        logger.error(f"Failed to sync {inst_id}: {e}")
                        continue

                await session.commit()
                logger.info(f"Crypto sync completed. Total new records: {total_added}")

        finally:
            await connector.close()

    # 运行异步任务
    asyncio.run(_sync())

    return {"status": "completed", "synced_symbols": len(sync_symbols or CRYPTO_SYMBOLS)}


@celery_app.task(bind=True, name="sync_crypto_tickers")
def sync_crypto_tickers_task(self):
    """
    同步加密货币实时行情任务（高频更新）
    """
    logger.info(f"Starting crypto tickers sync task: {self.request.id}")

    import asyncio

    async def _sync():
        connector = OKXConnector()

        try:
            async with async_session_maker() as session:
                # 获取所有加密货币资产
                result = await session.execute(
                    select(Asset).where(Asset.asset_type == "crypto", Asset.is_active == True)
                )
                assets = result.scalars().all()

                for asset in assets:
                    # 构建OKX交易对符号
                    inst_id = f"{asset.symbol}-USDT"

                    try:
                        ticker = await connector.get_ticker(inst_id)

                        # 更新指标
                        await update_asset_metric(session, asset.id, ticker, [])

                    except Exception as e:
                        logger.warning(f"Failed to get ticker for {inst_id}: {e}")

                await session.commit()
                logger.info(f"Tickers sync completed. Updated {len(assets)} assets")

        finally:
            await connector.close()

    asyncio.run(_sync())

    return {"status": "completed", "updated_count": len(assets)}


@celery_app.task(name="scheduled_crypto_sync")
def scheduled_crypto_sync():
    """
    定时同步加密货币数据（每小时触发）
    """
    return sync_crypto_data_task()


@celery_app.task(name="scheduled_crypto_tickers_sync")
def scheduled_crypto_tickers_sync():
    """
    定时同步加密货币行情（每15分钟触发）
    """
    return sync_crypto_tickers_task()