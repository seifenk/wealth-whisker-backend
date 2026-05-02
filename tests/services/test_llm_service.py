"""
LLM服务测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.services.llm_service import LLMService, SENTIMENT_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT


class TestLLMService:
    """LLM服务测试"""

    def test_init_with_config(self):
        """测试初始化配置"""
        service = LLMService()
        assert service.enabled == True
        assert service.api_base is not None
        assert service.api_key is not None
        assert service.model.startswith("openai/")
        assert service.timeout == 30
        assert service.max_tokens == 1000
        assert service.temperature == 0.7

    def test_normalize_api_base(self):
        """测试API base规范化"""
        service = LLMService()

        # 测试去掉chat/completions后缀
        result = service._normalize_api_base("http://localhost:8317/v1/chat/completions")
        assert result == "http://localhost:8317/v1"

        # 测试没有后缀的URL
        result = service._normalize_api_base("http://localhost:8317/v1")
        assert result == "http://localhost:8317/v1"

        # 测试空值
        result = service._normalize_api_base(None)
        assert result is None

    def test_normalize_model(self):
        """测试模型名称规范化"""
        service = LLMService()

        # 自定义API需要openai/前缀
        result = service._normalize_model("qwen3.5-plus")
        assert result == "openai/qwen3.5-plus"

        # 已有前缀不重复添加
        result = service._normalize_model("openai/gpt-4")
        assert result == "openai/gpt-4"

    def test_check_enabled_true(self):
        """测试启用检查（启用状态）"""
        service = LLMService()
        result = service._check_enabled()
        assert result == True

    def test_build_sentiment_prompt(self):
        """测试情感分析prompt构建"""
        service = LLMService()

        prompt = service._build_sentiment_prompt(
            title="比特币突破新高",
            content="比特币今日价格突破10万美元"
        )

        assert "比特币突破新高" in prompt
        assert "比特币今日价格突破10万美元" in prompt
        assert "JSON格式" in prompt
        assert "sentiment" in prompt

    def test_parse_sentiment_response_valid_json(self):
        """测试情感分析响应解析（有效JSON）"""
        service = LLMService()

        response_text = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.85,
            "impact_type": "利好",
            "key_points": ["价格突破新高"],
            "reasoning": "市场情绪乐观"
        })

        result = service._parse_sentiment_response(response_text)

        assert result["sentiment"] == "positive"
        assert result["sentiment_score"] == 0.85
        assert result["impact_type"] == "利好"
        assert len(result["key_points"]) == 1
        assert result["reasoning"] == "市场情绪乐观"

    def test_parse_sentiment_response_invalid_json(self):
        """测试情感分析响应解析（无效JSON）"""
        service = LLMService()

        result = service._parse_sentiment_response("invalid json text")

        # 返回默认值
        assert result["sentiment"] == "neutral"
        assert result["sentiment_score"] == 0.5

    def test_default_sentiment_result(self):
        """测试默认情感分析结果"""
        service = LLMService()

        result = service._default_sentiment_result()

        assert result["sentiment"] == "neutral"
        assert result["sentiment_score"] == 0.5
        assert result["impact_type"] == "中性"
        assert result["key_points"] == []
        assert "LLM分析未启用" in result["reasoning"]

    def test_format_technical_metrics(self):
        """测试技术指标格式化"""
        service = LLMService()

        # 有数据的情况
        metrics = {
            "trend_signal": "bullish",
            "technical_strength": 4,
            "rsi_14": 65.5,
            "volatility_30d": 25.3
        }
        result = service._format_technical_metrics(metrics)
        assert "趋势信号：bullish" in result
        assert "技术强度：4星" in result
        assert "RSI：65.5" in result

        # 无数据的情况
        result = service._format_technical_metrics({})
        assert result == "数据不足"

    def test_format_sentiment_summary(self):
        """测试情感摘要格式化"""
        service = LLMService()

        # 有情感数据
        summary = {
            "sentiment": "positive",
            "sentiment_score": 0.85
        }
        result = service._format_sentiment_summary(summary)
        assert "整体情绪：positive" in result
        assert "0.85" in result

        # 无情感数据
        result = service._format_sentiment_summary(None)
        assert "暂无消息面数据" in result

    def test_default_conclusion(self):
        """测试默认研究结论"""
        service = LLMService()

        result = service._default_conclusion("比特币")

        assert "比特币" in result
        assert "技术分析" in result
        assert "风险" in result

    @pytest.mark.asyncio
    async def test_analyze_sentiment_disabled(self):
        """测试情感分析（LLM未启用）"""
        service = LLMService()
        service.enabled = False

        result = await service.analyze_sentiment(
            title="测试新闻",
            content="测试内容"
        )

        assert result["sentiment"] == "neutral"
        assert "LLM分析未启用" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_analyze_news_batch(self):
        """测试批量新闻分析"""
        service = LLMService()

        articles = [
            {"title": "新闻1", "content": "内容1"},
            {"title": "新闻2", "content": "内容2"}
        ]

        # Mock analyze_sentiment
        service.analyze_sentiment = AsyncMock(return_value={
            "sentiment": "positive",
            "sentiment_score": 0.8
        })

        results = await service.analyze_news_batch(articles)

        assert len(results) == 2
        assert results[0]["sentiment"] == "positive"

    @pytest.mark.asyncio
    async def test_generate_research_summary_disabled(self):
        """测试研究结论生成（LLM未启用）"""
        service = LLMService()
        service.enabled = False

        result = await service.generate_research_summary(
            asset_name="比特币",
            asset_symbol="BTC",
            technical_metrics={"rsi": 65}
        )

        assert "比特币" in result
        assert "技术分析" in result


class TestPromptTemplates:
    """Prompt模板测试"""

    def test_sentiment_system_prompt(self):
        """测试情感分析系统prompt"""
        assert "金融分析师" in SENTIMENT_SYSTEM_PROMPT
        assert "客观中立" in SENTIMENT_SYSTEM_PROMPT

    def test_summary_system_prompt(self):
        """测试研究结论系统prompt"""
        assert "合规" in SUMMARY_SYSTEM_PROMPT
        assert "绝对性词汇" in SUMMARY_SYSTEM_PROMPT
        assert "风险提示" in SUMMARY_SYSTEM_PROMPT
        assert "不构成直接投资建议" in SUMMARY_SYSTEM_PROMPT