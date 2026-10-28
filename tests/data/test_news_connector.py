from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.data.connectors import news_connector
from app.data.connectors.news_connector import (
    NewsAggregator,
    RSSConnector,
    SECFilingsConnector,
)
from app.services.llm_service import llm_service
from app.services.research_service import ResearchService


@pytest.mark.asyncio
async def test_stock_news_uses_sec_fallback_before_rss():
    aggregator = NewsAggregator()
    sec_article = {
        "title": "AAPL SEC 8-K filing",
        "content": "Apple filed an 8-K.",
        "source": "sec",
        "published_at": datetime.now(timezone.utc),
    }
    aggregator.sec.fetch_news = AsyncMock(return_value=[sec_article])
    aggregator.rss.fetch_news = AsyncMock(return_value=[])

    articles = await aggregator.fetch_news_for_asset(
        asset_type="stock",
        asset_symbol="AAPL",
        keywords=["AAPL"],
        limit=5,
    )

    aggregator.sec.fetch_news.assert_awaited_once_with(tickers=["AAPL"], limit=5)
    aggregator.rss.fetch_news.assert_not_awaited()
    assert articles == [sec_article]


@pytest.mark.asyncio
async def test_sec_connector_normalizes_recent_filings(monkeypatch):
    monkeypatch.setattr(SECFilingsConnector, "_ticker_map_cache", None)
    connector = SECFilingsConnector(user_agent="test-agent")
    connector._get_json = AsyncMock(
        side_effect=[
            {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[320193, "APPLE INC", "AAPL", "Nasdaq"]],
            },
            {
                "filings": {
                    "recent": {
                        "form": ["8-K", "4"],
                        "filingDate": ["2026-07-30", "2026-07-29"],
                        "reportDate": ["2026-07-27", ""],
                        "accessionNumber": [
                            "0000320193-26-000018",
                            "0000320193-26-000017",
                        ],
                        "primaryDocument": ["aapl-20260730.htm", "form4.xml"],
                        "items": ["1.01, 9.01", ""],
                        "primaryDocDescription": ["Current report", ""],
                    }
                }
            },
        ]
    )

    articles = await connector.fetch_news(tickers=["AAPL"], limit=5)

    assert len(articles) == 1
    assert articles[0]["source"] == "sec"
    assert articles[0]["filing_form"] == "8-K"
    assert articles[0]["published_at"].isoformat() == "2026-07-30T00:00:00+00:00"
    assert articles[0]["url"].endswith("/000032019326000018/aapl-20260730.htm")


def test_retired_rss_sources_are_not_part_of_default_catalog():
    assert "reuters_business" not in RSSConnector.RSS_SOURCES
    assert "wsj_markets" not in RSSConnector.RSS_SOURCES
    assert "caixin_finance" not in RSSConnector.RSS_SOURCES


@pytest.mark.asyncio
async def test_research_news_sentiment_uses_news_aggregator(monkeypatch):
    fake_aggregator = SimpleNamespace(
        fetch_news_for_asset=AsyncMock(
            return_value=[
                {
                    "title": "Apple announces results",
                    "content": "Revenue increased.",
                    "source": "sec",
                    "published_at": datetime.now(timezone.utc),
                }
            ]
        )
    )
    fake_rss = SimpleNamespace(fetch_news=AsyncMock(return_value=[]))
    sentiment = {"sentiment": "positive", "score": 0.8, "confidence": 0.9}

    monkeypatch.setattr(
        news_connector,
        "NewsAggregator",
        lambda **kwargs: fake_aggregator,
    )
    monkeypatch.setattr(news_connector, "RSSConnector", lambda: fake_rss)
    monkeypatch.setattr(
        llm_service,
        "analyze_sentiment",
        AsyncMock(return_value=sentiment),
    )

    asset = SimpleNamespace(
        asset_type="stock",
        symbol="AAPL",
        name="Apple Inc.",
    )
    result = await ResearchService._fetch_news_sentiment(asset)

    fake_aggregator.fetch_news_for_asset.assert_awaited_once()
    assert result["article_count"] == 1
    assert result["sentiment"] == "positive"
