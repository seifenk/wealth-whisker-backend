"""
新闻数据同步任务

定时获取新闻数据并进行LLM情感分析
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import asyncio

from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import task_session_maker as async_session_maker
from app.core.config import settings
from app.models.asset import Asset
from app.models.news import NewsArticle, SentimentSnapshot
from app.data.connectors.news_connector import init_news_aggregator, get_news_aggregator
from app.services.llm_service import llm_service


def _to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    统一为naive UTC时间

    NewsArticle.published_at/collected_at 是 DateTime(timestamp without timezone)列，
    RSS/页面解析出的时间可能带tzinfo(aware)。asyncpg 对 naive/aware 混用会报
    "can't subtract offset-naive and offset-aware datetimes"，入库前必须统一。
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@celery_app.task(bind=True, name="sync_news_data")
def sync_news_data_task(self, asset_type: Optional[str] = None):
    """
    同步新闻数据

    Args:
        asset_type: 资产类型过滤（crypto/stock/gold/fund），None表示同步全部

    Returns:
        dict: 同步结果统计
    """
    logger.info(f"Starting news sync task: {self.request.id}")

    async def _sync():
        async with async_session_maker() as session:
            # 初始化新闻聚合器
            aggregator = init_news_aggregator(
                cryptopanic_key=settings.CRYPTOPANIC_API_KEY,
                newsapi_key=settings.NEWSAPI_KEY,
                alphavantage_key=settings.ALPHA_VANTAGE_API_KEY,
            )

            # 查询活跃资产
            query = select(Asset).where(Asset.is_active == True)
            if asset_type:
                query = query.where(Asset.asset_type == asset_type)

            result = await session.execute(query)
            assets = result.scalars().all()

            if not assets:
                logger.warning("No active assets found for news sync")
                return {"status": "completed", "articles_collected": 0}

            total_articles = 0
            analyzed_articles = 0
            error_count = 0

            for asset in assets:
                try:
                    # 获取新闻
                    articles = await aggregator.fetch_news_for_asset(
                        asset_type=asset.asset_type,
                        asset_symbol=asset.symbol,
                        limit=settings.MACRO_NEWS_LIMIT,
                    )

                    # 存储新闻并分析情感
                    for article_data in articles:
                        # 检查是否已存在（按标题+URL去重）
                        existing = await session.execute(
                            select(NewsArticle)
                            .where(and_(
                                NewsArticle.title == article_data["title"],
                                NewsArticle.url == article_data["url"]
                            ))
                        )
                        if existing.scalar_one_or_none():
                            continue

                        # LLM情感分析（如果启用）
                        if settings.LLM_ENABLED and article_data.get("content"):
                            sentiment_result = await llm_service.analyze_sentiment(
                                title=article_data.get("title", ""),
                                content=article_data.get("content", "")[:500],
                            )
                            article_data["sentiment"] = sentiment_result.get("sentiment", "neutral")
                            article_data["sentiment_score"] = sentiment_result.get("sentiment_score", 0.5)
                            analyzed_articles += 1

                        # 存储新闻文章
                        news_article = NewsArticle(
                            asset_id=asset.id,
                            title=article_data["title"],
                            content=article_data.get("content", ""),
                            source=article_data.get("source", "unknown"),
                            source_name=article_data.get("source_name", ""),
                            url=article_data.get("url", ""),
                            published_at=_to_naive_utc(article_data.get("published_at")),
                            collected_at=datetime.utcnow(),
                            sentiment=article_data.get("sentiment", "neutral"),
                            sentiment_score=article_data.get("sentiment_score", 0.5),
                            is_processed=True,
                        )
                        session.add(news_article)
                        total_articles += 1

                except Exception as e:
                    logger.error(f"News sync failed for {asset.symbol}: {e}")
                    error_count += 1
                    continue

            await session.commit()
            logger.info(
                f"News sync completed: collected={total_articles}, "
                f"analyzed={analyzed_articles}, errors={error_count}"
            )

            return {
                "status": "completed",
                "articles_collected": total_articles,
                "articles_analyzed": analyzed_articles,
                "error_count": error_count,
            }

    return asyncio.run(_sync())


@celery_app.task(bind=True, name="aggregate_sentiment_snapshot")
def aggregate_sentiment_snapshot_task(self):
    """
    聚合情感快照

    为每个资产生成当日情感快照汇总
    """
    logger.info(f"Starting sentiment aggregation task: {self.request.id}")

    async def _aggregate():
        async with async_session_maker() as session:
            # 获取今日新闻
            today = datetime.utcnow().date()
            today_start = datetime.combine(today, datetime.min.time())

            # 查询有新闻的资产
            assets_with_news = await session.execute(
                select(Asset)
                .join(NewsArticle)
                .where(NewsArticle.collected_at >= today_start)
                .distinct()
            )
            assets = assets_with_news.scalars().all()

            if not assets:
                logger.info("No news collected today")
                return {"status": "completed", "snapshots_created": 0}

            snapshots_created = 0

            for asset in assets:
                # 获取该资产今日新闻
                news_articles = await session.execute(
                    select(NewsArticle)
                    .where(and_(
                        NewsArticle.asset_id == asset.id,
                        NewsArticle.collected_at >= today_start
                    ))
                    .order_by(desc(NewsArticle.published_at))
                )
                articles = news_articles.scalars().all()

                if not articles:
                    continue

                # 计算聚合情感
                positive_count = sum(1 for a in articles if a.sentiment == "positive")
                negative_count = sum(1 for a in articles if a.sentiment == "negative")
                neutral_count = sum(1 for a in articles if a.sentiment == "neutral")

                # 计算综合情感分数
                total = len(articles)
                avg_score = sum(float(a.sentiment_score or 0.5) for a in articles) / total if total > 0 else 0.5

                # 确定整体情感
                if positive_count > negative_count * 1.5:
                    overall_sentiment = "positive"
                elif negative_count > positive_count * 1.5:
                    overall_sentiment = "negative"
                else:
                    overall_sentiment = "neutral"

                # 计算星级（基于情感强度和数量）
                if total >= 5 and (positive_count >= 3 or negative_count >= 3):
                    stars = 4
                elif total >= 3 and avg_score > 0.6 or avg_score < 0.4:
                    stars = 3
                elif total >= 1:
                    stars = 2
                else:
                    stars = 1

                # 提取关键事件
                key_events = []
                for article in articles[:5]:
                    if article.title:
                        event = {
                            "event": article.title[:100],
                            "impact": article.sentiment,
                            "source": article.source_name,
                            "time": article.published_at.isoformat() if article.published_at else None,
                        }
                        key_events.append(event)

                # 创建快照
                snapshot = SentimentSnapshot(
                    asset_id=asset.id,
                    snapshot_date=today,
                    total_articles=total,
                    positive_count=positive_count,
                    negative_count=negative_count,
                    neutral_count=neutral_count,
                    overall_sentiment=overall_sentiment,
                    overall_score=avg_score,
                    news_impact_stars=stars,
                    key_events=key_events,
                )
                session.add(snapshot)
                snapshots_created += 1

            await session.commit()
            logger.info(f"Sentiment aggregation completed: {snapshots_created} snapshots")

            return {
                "status": "completed",
                "snapshots_created": snapshots_created,
                "assets_processed": len(assets),
            }

    return asyncio.run(_aggregate())


@celery_app.task(name="sync_macro_news")
def sync_macro_news_task():
    """
    同步宏观经济新闻

    每日同步宏观经济新闻，用于整体市场分析
    """
    logger.info("Starting macro news sync task")

    async def _sync_macro():
        async with async_session_maker() as session:
            aggregator = init_news_aggregator(
                cryptopanic_key=settings.CRYPTOPANIC_API_KEY,
                newsapi_key=settings.NEWSAPI_KEY,
                alphavantage_key=settings.ALPHA_VANTAGE_API_KEY,
            )

            # 获取宏观经济新闻
            articles = await aggregator.fetch_macro_news(limit=settings.NEWS_SYNC_LIMIT)

            # 存储（不关联特定资产）
            stored_count = 0
            for article_data in articles:
                # 检查重复
                existing = await session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.url == article_data.get("url"))
                )
                if existing.scalar_one_or_none():
                    continue

                # LLM分析（如果启用）
                if settings.LLM_ENABLED:
                    sentiment_result = await llm_service.analyze_sentiment(
                        title=article_data.get("title", ""),
                        content=article_data.get("content", "")[:500],
                    )
                    article_data["sentiment"] = sentiment_result.get("sentiment", "neutral")
                    article_data["sentiment_score"] = sentiment_result.get("sentiment_score", 0.5)

                news_article = NewsArticle(
                    asset_id=None,  # 宏观新闻不关联特定资产
                    title=article_data["title"],
                    content=article_data.get("content", ""),
                    source=article_data.get("source", "unknown"),
                    source_name=article_data.get("source_name", ""),
                    url=article_data.get("url", ""),
                    published_at=_to_naive_utc(article_data.get("published_at")),
                    collected_at=datetime.utcnow(),
                    sentiment=article_data.get("sentiment", "neutral"),
                    sentiment_score=article_data.get("sentiment_score", 0.5),
                    is_processed=True,
                )
                session.add(news_article)
                stored_count += 1

            await session.commit()
            logger.info(f"Macro news sync completed: {stored_count} articles")

            return {"status": "completed", "articles_collected": stored_count}

    return asyncio.run(_sync_macro())


# ============ 定时调度包装任务 ============

@celery_app.task(name="scheduled_crypto_news_sync")
def scheduled_crypto_news_sync():
    """加密货币新闻定时同步（每4小时）"""
    logger.info("Executing scheduled crypto news sync")
    return sync_news_data_task(asset_type="crypto")


@celery_app.task(name="scheduled_stock_news_sync")
def scheduled_stock_news_sync():
    """股票新闻定时同步（每日盘后）"""
    logger.info("Executing scheduled stock news sync")
    return sync_news_data_task(asset_type="stock")


@celery_app.task(name="scheduled_gold_news_sync")
def scheduled_gold_news_sync():
    """黄金新闻定时同步（每日）"""
    logger.info("Executing scheduled gold news sync")
    return sync_news_data_task(asset_type="gold")


@celery_app.task(name="scheduled_fund_news_sync")
def scheduled_fund_news_sync():
    """基金新闻定时同步（每日）"""
    logger.info("Executing scheduled fund news sync")
    return sync_news_data_task(asset_type="fund")


@celery_app.task(name="scheduled_sentiment_aggregation")
def scheduled_sentiment_aggregation():
    """情感快照定时聚合（每日）"""
    logger.info("Executing scheduled sentiment aggregation")
    return aggregate_sentiment_snapshot_task()


@celery_app.task(name="scheduled_macro_news_sync")
def scheduled_macro_news_sync():
    """宏观经济新闻定时同步（每日）"""
    logger.info("Executing scheduled macro news sync")
    return sync_macro_news_task()
