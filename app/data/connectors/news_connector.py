"""
新闻数据源连接器

支持多数据源新闻获取：
- CryptoPanic API：加密货币专用新闻聚合器
- NewsAPI.org：通用新闻API
- RSS订阅：财经媒体RSS源
- Alpha Vantage：经济新闻+情感分析
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
import httpx
import feedparser
from abc import ABC, abstractmethod

from app.core.config import settings


class NewsConnectorBase(ABC):
    """新闻连接器基类"""

    @abstractmethod
    async def fetch_news(
        self,
        keywords: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """获取新闻列表"""
        pass

    def _normalize_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """标准化新闻文章格式"""
        return {
            "title": article.get("title", ""),
            "content": article.get("content") or article.get("description") or article.get("summary", ""),
            "source": article.get("source", "unknown"),
            "source_name": article.get("source_name", ""),
            "url": article.get("url", ""),
            "published_at": article.get("published_at"),
            "collected_at": datetime.utcnow(),
            "category": article.get("category", "general"),
        }


class CryptoPanicConnector(NewsConnectorBase):
    """
    CryptoPanic API连接器

    加密货币新闻聚合器，免费API
    文档：https://cryptopanic.com/developers/api/
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.api_url = settings.CRYPTOPANIC_API_URL

    async def fetch_news(
        self,
        keywords: Optional[List[str]] = None,
        currencies: Optional[List[str]] = None,  # 如 ["BTC", "ETH"]
        filter_type: str = "rising",  # rising/hot/bullish/bearish/important
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        获取加密货币新闻

        Args:
            keywords: 搜索关键词
            currencies: 币种过滤（如BTC、ETH）
            filter_type: 过滤类型：rising/hot/bullish/bearish/important
            limit: 返回数量
        """
        params = {
            "filter": filter_type,
            "limit": limit,
        }

        # 添加API密钥（可选，有密钥可获取更多数据）
        if self.api_key:
            params["api_token"] = self.api_key

        # 添加币种过滤
        if currencies:
            params["currencies"] = ",".join(currencies)

        # 添加关键词搜索
        if keywords:
            params["q"] = " ".join(keywords)

        try:
            async with httpx.AsyncClient(timeout=settings.NEWS_API_TIMEOUT) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()

            articles = []
            for post in data.get("results", []):
                article = {
                    "title": post.get("title", ""),
                    "content": post.get("description", ""),
                    "source": "cryptopanic",
                    "source_name": post.get("source", {}).get("domain", ""),
                    "url": post.get("url", ""),
                    "published_at": datetime.fromisoformat(post.get("created_at", "").replace("Z", "+00:00")) if post.get("created_at") else None,
                    "category": post.get("kind", "news"),
                    "currencies": [c.get("code") for c in post.get("currencies", [])],
                    "votes": post.get("votes", {}),  # 社区投票信号
                }
                articles.append(self._normalize_article(article))

            logger.info(f"CryptoPanic fetched {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"CryptoPanic fetch failed: {e}")
            return []


class NewsAPIConnector(NewsConnectorBase):
    """
    NewsAPI.org连接器

    通用新闻API，每日100篇免费额度
    文档：https://newsapi.org/docs
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = f"{settings.NEWSAPI_URL}/everything"

    async def fetch_news(
        self,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,  # 如 ["reuters", "bloomberg"]
        category: Optional[str] = None,  # business/technology
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        获取通用新闻

        Args:
            keywords: 搜索关键词
            sources: 新闻来源过滤
            category: 分类过滤
            from_date: 开始日期
            to_date: 结束日期
            limit: 返回数量
        """
        if not self.api_key:
            logger.warning("NewsAPI requires API key")
            return []

        # 默认搜索最近7天
        if not from_date:
            from_date = datetime.utcnow() - timedelta(days=7)
        if not to_date:
            to_date = datetime.utcnow()

        params = {
            "apiKey": self.api_key,
            "pageSize": limit,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "sortBy": "relevancy",
            "language": "en",
        }

        if keywords:
            params["q"] = " ".join(keywords)

        if sources:
            params["sources"] = ",".join(sources)

        try:
            async with httpx.AsyncClient(timeout=settings.NEWS_API_TIMEOUT) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()

            articles = []
            for article in data.get("articles", []):
                normalized = {
                    "title": article.get("title", ""),
                    "content": article.get("content") or article.get("description", ""),
                    "source": "newsapi",
                    "source_name": article.get("source", {}).get("name", ""),
                    "url": article.get("url", ""),
                    "published_at": datetime.fromisoformat(article.get("publishedAt", "").replace("Z", "+00:00")) if article.get("publishedAt") else None,
                    "image_url": article.get("urlToImage"),
                }
                articles.append(self._normalize_article(normalized))

            logger.info(f"NewsAPI fetched {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
            return []

    async def fetch_top_headlines(
        self,
        category: str = "business",
        country: str = "us",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取头条新闻"""
        url = f"{settings.NEWSAPI_URL}/top-headlines"
        params = {
            "apiKey": self.api_key,
            "category": category,
            "country": country,
            "pageSize": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.NEWS_API_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            articles = []
            for article in data.get("articles", []):
                normalized = {
                    "title": article.get("title", ""),
                    "content": article.get("description", ""),
                    "source": "newsapi_headlines",
                    "source_name": article.get("source", {}).get("name", ""),
                    "url": article.get("url", ""),
                    "published_at": datetime.fromisoformat(article.get("publishedAt", "").replace("Z", "+00:00")) if article.get("publishedAt") else None,
                }
                articles.append(self._normalize_article(normalized))

            return articles

        except Exception as e:
            logger.error(f"NewsAPI headlines fetch failed: {e}")
            return []


class RSSConnector(NewsConnectorBase):
    """
    RSS订阅连接器

    订阅财经媒体RSS源，免费稳定
    """

    # 预设RSS源
    RSS_SOURCES = {
        # 国际财经媒体
        "reuters_business": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
        "bloomberg_markets": "https://www.bloomberg.com/feed/podcast/bloomberg-markets.xml",
        "wsj_markets": "https://feeds.a.dj.com/RSSMarketsMain.xml",

        # 加密货币媒体
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "decrypt": "https://decrypt.co/feed",

        # 中文财经媒体
        "caixin_finance": "https://www.caixin.com/rss_finance.xml",
        "eastmoney_news": "http://news.cnstock.com/rss.xml",

        # 官方公告源
        "federal_reserve": "https://www.federalreserve.gov/feeds/press_releases.xml",
        "sec_news": "https://www.sec.gov/cgi-bin/browse.cgi?action=getnews&type=newsreleases&company=&count=50&output=atom",
    }

    def __init__(self, custom_sources: Optional[Dict[str, str]] = None):
        """可添加自定义RSS源"""
        self.sources = {**self.RSS_SOURCES, **(custom_sources or {})}

    async def fetch_news(
        self,
        source_names: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        从RSS源获取新闻

        Args:
            source_names: 要获取的RSS源名称列表（默认获取全部）
            keywords: 关键词过滤（可选）
            limit: 每个源返回数量上限
        """
        if source_names:
            sources_to_fetch = {k: v for k, v in self.sources.items() if k in source_names}
        else:
            sources_to_fetch = self.sources

        articles = []

        for source_name, rss_url in sources_to_fetch.items():
            try:
                source_articles = await self._fetch_single_rss(
                    source_name, rss_url, keywords, limit
                )
                articles.extend(source_articles)
            except Exception as e:
                logger.warning(f"RSS {source_name} fetch failed: {e}")
                continue

        logger.info(f"RSS fetched {len(articles)} articles from {len(sources_to_fetch)} sources")
        return articles

    async def _fetch_single_rss(
        self,
        source_name: str,
        rss_url: str,
        keywords: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取单个RSS源"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(rss_url)
                response.raise_for_status()

            # 解析RSS
            feed = feedparser.parse(response.text)

            articles = []
            for entry in feed.entries[:limit]:
                # 关键词过滤
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")

                if keywords:
                    text = f"{title} {summary}".lower()
                    if not any(kw.lower() in text for kw in keywords):
                        continue

                # 解析发布时间
                published_at = None
                if entry.get("published_parsed"):
                    published_at = datetime(*entry.published_parsed[:6])
                elif entry.get("updated_parsed"):
                    published_at = datetime(*entry.updated_parsed[:6])

                article = {
                    "title": title,
                    "content": summary,
                    "source": "rss",
                    "source_name": source_name,
                    "url": entry.get("link", ""),
                    "published_at": published_at,
                    "category": feed.feed.get("title", "general"),
                }
                articles.append(self._normalize_article(article))

            return articles

        except Exception as e:
            logger.error(f"RSS {source_name} parse failed: {e}")
            return []


class AlphaVantageNewsConnector(NewsConnectorBase):
    """
    Alpha Vantage News & Sentiment API连接器

    提供经济新闻和情感分析，有免费额度
    文档：https://www.alphavantage.co/documentation/#news-sentiment
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = settings.ALPHA_VANTAGE_API_URL

    async def fetch_news(
        self,
        keywords: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,  # 如 ["BTC", "AAPL"]
        topics: Optional[List[str]] = None,  # 如 ["technology", "earnings"]
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        获取新闻和情感分析

        Alpha Vantage自带情感分析分数

        Args:
            keywords: 搜索关键词
            tickers: 股票/加密货币代码
            topics: 主题过滤
            limit: 返回数量
        """
        if not self.api_key:
            logger.warning("Alpha Vantage requires API key")
            return []

        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "limit": limit,
        }

        if keywords:
            params["keywords"] = " ".join(keywords)

        if tickers:
            params["tickers"] = ",".join(tickers)

        if topics:
            params["topics"] = ",".join(topics)

        try:
            async with httpx.AsyncClient(timeout=settings.NEWS_API_TIMEOUT) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()

            articles = []
            for feed in data.get("feed", []):
                article = {
                    "title": feed.get("title", ""),
                    "content": feed.get("summary", ""),
                    "source": "alphavantage",
                    "source_name": feed.get("source", ""),
                    "url": feed.get("url", ""),
                    "published_at": datetime.fromisoformat(feed.get("time_published", "").replace("Z", "+00:00")) if feed.get("time_published") else None,
                    # Alpha Vantage自带的情感分析
                    "sentiment_score": float(feed.get("overall_sentiment_score", 0.5)),
                    "sentiment_label": feed.get("overall_sentiment_label", "Neutral"),
                    "ticker_sentiment": feed.get("ticker_sentiment", []),
                }
                articles.append(self._normalize_article(article))

            logger.info(f"Alpha Vantage fetched {len(articles)} articles")
            return articles

        except Exception as e:
            logger.error(f"Alpha Vantage fetch failed: {e}")
            return []


class NewsAggregator:
    """
    新闻聚合器

    统一管理多个数据源，按资产类型智能选择数据源
    """

    def __init__(
        self,
        cryptopanic_key: Optional[str] = None,
        newsapi_key: Optional[str] = None,
        alphavantage_key: Optional[str] = None,
        rss_sources: Optional[Dict[str, str]] = None,
    ):
        self.cryptopanic = CryptoPanicConnector(cryptopanic_key) if cryptopanic_key else None
        self.newsapi = NewsAPIConnector(newsapi_key) if newsapi_key else None
        self.rss = RSSConnector(rss_sources)
        self.alphavantage = AlphaVantageNewsConnector(alphavantage_key) if alphavantage_key else None

    async def fetch_news_for_asset(
        self,
        asset_type: str,
        asset_symbol: str,
        keywords: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        根据资产类型智能选择数据源获取新闻

        Args:
            asset_type: 资产类型（crypto/stock/gold/fund）
            asset_symbol: 资产代码
            keywords: 搜索关键词
            limit: 返回数量
        """
        articles = []

        # 加密货币：优先CryptoPanic + 加密货币RSS
        if asset_type == "crypto":
            if self.cryptopanic:
                crypto_news = await self.cryptopanic.fetch_news(
                    currencies=[asset_symbol],
                    keywords=keywords,
                    limit=limit,
                )
                articles.extend(crypto_news)

            # 补充加密货币RSS源
            rss_news = await self.rss.fetch_news(
                source_names=["coindesk", "cointelegraph", "decrypt"],
                keywords=[asset_symbol] + (keywords or []),
                limit=10,
            )
            articles.extend(rss_news)

        # 股票/黄金：NewsAPI + 财经RSS + Alpha Vantage
        elif asset_type in ["stock", "gold"]:
            if self.newsapi:
                stock_news = await self.newsapi.fetch_news(
                    keywords=[asset_symbol] + (keywords or []),
                    category="business",
                    limit=limit,
                )
                articles.extend(stock_news)

            if self.alphavantage:
                av_news = await self.alphavantage.fetch_news(
                    tickers=[asset_symbol],
                    limit=10,
                )
                articles.extend(av_news)

            # 财经RSS补充
            rss_news = await self.rss.fetch_news(
                source_names=["reuters_business", "wsj_markets", "caixin_finance"],
                keywords=[asset_symbol] + (keywords or []),
                limit=10,
            )
            articles.extend(rss_news)

        # 基金：财经RSS + NewsAPI
        elif asset_type == "fund":
            if self.newsapi:
                fund_news = await self.newsapi.fetch_news(
                    keywords=[asset_symbol] + (keywords or []),
                    category="business",
                    limit=limit,
                )
                articles.extend(fund_news)

            rss_news = await self.rss.fetch_news(
                source_names=["caixin_finance", "eastmoney_news"],
                keywords=[asset_symbol] + (keywords or []),
                limit=10,
            )
            articles.extend(rss_news)

        # 按时间排序并去重
        articles = self._deduplicate_and_sort(articles, limit)

        logger.info(f"Fetched {len(articles)} articles for {asset_symbol}")
        return articles

    async def fetch_macro_news(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        获取宏观经济新闻

        用于Dashboard综合分析
        """
        articles = []

        # 官方公告RSS
        rss_news = await self.rss.fetch_news(
            source_names=["federal_reserve", "sec_news"],
            limit=10,
        )
        articles.extend(rss_news)

        # Alpha Vantage经济新闻
        if self.alphavantage:
            av_news = await self.alphavantage.fetch_news(
                topics=["macro", "earnings"],
                limit=10,
            )
            articles.extend(av_news)

        # NewsAPI财经头条
        if self.newsapi:
            headlines = await self.newsapi.fetch_top_headlines(
                category="business",
                limit=10,
            )
            articles.extend(headlines)

        return self._deduplicate_and_sort(articles, limit)

    def _deduplicate_and_sort(
        self,
        articles: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """去重并按时间排序"""
        # 按标题去重
        seen_titles = set()
        unique_articles = []
        for article in articles:
            title = article.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_articles.append(article)

        # 按发布时间排序（最新的在前）
        unique_articles.sort(
            key=lambda x: x.get("published_at") or datetime.min,
            reverse=True,
        )

        return unique_articles[:limit]


# 单例实例（需要配置API密钥）
news_aggregator: Optional[NewsAggregator] = None


def init_news_aggregator(
    cryptopanic_key: Optional[str] = None,
    newsapi_key: Optional[str] = None,
    alphavantage_key: Optional[str] = None,
) -> NewsAggregator:
    """初始化新闻聚合器"""
    global news_aggregator
    news_aggregator = NewsAggregator(
        cryptopanic_key=cryptopanic_key,
        newsapi_key=newsapi_key,
        alphavantage_key=alphavantage_key,
    )
    return news_aggregator


def get_news_aggregator() -> Optional[NewsAggregator]:
    """获取新闻聚合器实例"""
    return news_aggregator