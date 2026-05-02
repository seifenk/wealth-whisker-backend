"""
消息面评分计算器
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any


class NewsImpactCalculator:
    """消息面影响力计算器"""

    # 来源权重（权威来源权重更高）
    SOURCE_WEIGHTS = {
        "official": 1.0,    # 官方公告
        "media": 0.8,       # 主流媒体
        "research": 0.7,    # 研报
        "social": 0.3,      # 社交媒体
        "other": 0.5,       # 其他
    }

    # 时间衰减系数（天数）
    TIME_DECAY_DAYS = 7  # 7天后完全衰减

    @staticmethod
    def calculate_news_impact_score(
        news_articles: List[Dict[str, Any]],
        weights: Optional[Dict[str, float]] = None,
    ) -> int:
        """
        计算消息面影响力星级（1-5）

        Args:
            news_articles: 新闻文章列表
            weights: 来源权重覆盖

        Returns:
            1-5星评级
        """
        if not news_articles:
            return 3  # 无数据时默认3星

        weights = weights or NewsImpactCalculator.SOURCE_WEIGHTS
        now = datetime.utcnow()

        total_score = Decimal("0")

        for article in news_articles:
            # 情感分数（正面>0.5，负面<0.5）
            sentiment_score = Decimal(str(article.get("sentiment_score", 0.5)))
            # 转换为影响力分数：正面和负面都有影响力，中性影响较小
            if sentiment_score > 0.6:  # 正面
                impact_score = sentiment_score * Decimal("0.8")
            elif sentiment_score < 0.4:  # 负面
                impact_score = (Decimal("1") - sentiment_score) * Decimal("0.8")
            else:  # 中性
                impact_score = Decimal("0.3")

            # 来源权重
            source = article.get("source", "other")
            source_weight = Decimal(str(weights.get(source, 0.5)))

            # 时间衰减
            published_at = article.get("published_at")
            if published_at:
                if isinstance(published_at, str):
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                days_old = (now - published_at).days
                time_decay = max(Decimal("0"), Decimal("1") - Decimal(str(days_old)) / Decimal(str(NewsImpactCalculator.TIME_DECAY_DAYS)))
            else:
                time_decay = Decimal("1")  # 无时间信息不衰减

            # 重要性评分权重
            importance = article.get("importance_score", 3)
            importance_weight = Decimal(str(importance)) / Decimal("5")

            # 单条新闻贡献
            article_score = impact_score * source_weight * time_decay * importance_weight
            total_score += article_score

        # 映射到1-5星
        # 标准化：假设每条新闻最大贡献约0.5，取平均
        avg_score = total_score / len(news_articles) if news_articles else Decimal("0.3")

        if avg_score >= 0.6:
            return 5
        elif avg_score >= 0.45:
            return 4
        elif avg_score >= 0.35:
            return 3
        elif avg_score >= 0.25:
            return 2
        else:
            return 1

    @staticmethod
    def aggregate_sentiment_score(
        news_articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        聚合情感分数

        Args:
            news_articles: 新闻文章列表

        Returns:
            聚合情感结果
        """
        if not news_articles:
            return {
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "key_events": [],
            }

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        key_events = []

        total_score = Decimal("0")
        weighted_score = Decimal("0")

        for article in news_articles:
            sentiment = article.get("sentiment", "neutral")
            score = Decimal(str(article.get("sentiment_score", 0.5)))
            importance = article.get("importance_score", 3)

            if sentiment == "positive":
                positive_count += 1
            elif sentiment == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            # 加权分数（按重要性）
            weighted_score += score * Decimal(str(importance))
            total_score += Decimal(str(importance))

            # 收集关键事件
            if article.get("key_points"):
                key_events.extend(article.get("key_points", []))

        # 计算加权平均
        if total_score > 0:
            avg_score = float(weighted_score / total_score)
        else:
            avg_score = 0.5

        # 判断整体情感
        if positive_count > negative_count * 1.5:
            overall_sentiment = "positive"
        elif negative_count > positive_count * 1.5:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"

        return {
            "sentiment": overall_sentiment,
            "sentiment_score": round(avg_score, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "key_events": key_events[:5],  # 最多保留5个关键事件
        }

    @staticmethod
    def calculate_sentiment_trend(
        recent_scores: List[float],
    ) -> str:
        """
        计算情感趋势

        Args:
            recent_scores: 最近几天的情感分数列表（按时间顺序）

        Returns:
            improving/declining/stable
        """
        if len(recent_scores) < 2:
            return "stable"

        # 计算趋势（简单线性）
        mid = len(recent_scores) // 2
        first_half = sum(recent_scores[:mid]) / mid if mid > 0 else 0.5
        second_half = sum(recent_scores[mid:]) / (len(recent_scores) - mid) if len(recent_scores) - mid > 0 else 0.5

        diff = second_half - first_half

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    @staticmethod
    def build_news_score(
        news_articles: List[Dict[str, Any]],
        sentiment_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        构建消息面评分对象（用于前端展示）

        Args:
            news_articles: 新闻文章列表
            sentiment_data: 聚合情感数据（可选，若提供则复用）

        Returns:
            NewsScore格式的字典
        """
        # 聚合情感
        if sentiment_data is None:
            sentiment_data = NewsImpactCalculator.aggregate_sentiment_score(news_articles)

        # 计算星级
        stars = NewsImpactCalculator.calculate_news_impact_score(news_articles)

        # 构建关键事件列表
        key_events = []
        for article in news_articles[:5]:
            if article.get("title"):
                event = {
                    "event": article.get("title"),
                    "impact": article.get("sentiment", "neutral"),
                    "source": article.get("source_name"),
                    "time": article.get("published_at").isoformat() if article.get("published_at") else None,
                }
                key_events.append(event)

        return {
            "stars": stars,
            "sentiment": sentiment_data.get("sentiment", "neutral"),
            "key_events": key_events if key_events else None,
        }