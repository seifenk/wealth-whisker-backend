"""
LLM调用服务

使用litellm库统一调用不同LLM API（支持OpenAI/Claude格式）
"""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from loguru import logger

from app.core.config import settings


class LLMService:
    """LLM调用服务"""

    def __init__(self):
        self.enabled = settings.LLM_ENABLED
        self.api_base = self._normalize_api_base(settings.LLM_API_BASE)
        self.api_key = settings.LLM_API_KEY
        self.model = self._normalize_model(settings.LLM_MODEL)
        self.timeout = settings.LLM_TIMEOUT
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    def _normalize_api_base(self, api_base: Optional[str]) -> Optional[str]:
        """规范化API base URL（去掉/chat/completions后缀）"""
        if not api_base:
            return None
        # litellm需要基础URL，不是完整endpoint
        if api_base.endswith("/chat/completions"):
            return api_base.rsplit("/chat/completions", 1)[0]
        return api_base

    def _normalize_model(self, model: str) -> str:
        """规范化model名称（添加openai/前缀用于自定义API）"""
        # 对于自定义API base，litellm需要openai/前缀
        if self.api_base and not model.startswith("openai/"):
            return f"openai/{model}"
        return model

    def _check_enabled(self) -> bool:
        """检查LLM是否启用"""
        if not self.enabled:
            logger.warning("LLM功能未启用，请在.env中配置LLM_ENABLED=True")
            return False
        if not self.api_key:
            logger.warning("LLM API密钥未配置，请设置LLM_API_KEY")
            return False
        return True

    async def analyze_sentiment(
        self,
        title: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        分析金融新闻情感倾向

        Args:
            title: 新闻标题
            content: 新闻内容

        Returns:
            情感分析结果字典
        """
        if not self._check_enabled():
            return self._default_sentiment_result()

        try:
            import litellm

            prompt = self._build_sentiment_prompt(title, content)

            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # 解析响应
            result_text = response.choices[0].message.content
            result = self._parse_sentiment_response(result_text)

            logger.info(f"Sentiment analysis completed: {result.get('sentiment')}")
            return result

        except Exception as e:
            logger.error(f"LLM sentiment analysis failed: {e}")
            return self._default_sentiment_result()

    async def analyze_news_batch(
        self,
        news_items: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        批量分析新闻情感

        Args:
            news_items: 新闻列表，每项包含title和content

        Returns:
            情感分析结果列表
        """
        results = []
        for item in news_items:
            result = await self.analyze_sentiment(
                title=item.get("title", ""),
                content=item.get("content", "")
            )
            result["original_title"] = item.get("title")
            results.append(result)
        return results

    async def generate_research_summary(
        self,
        asset_name: str,
        asset_symbol: str,
        technical_metrics: Dict[str, Any],
        sentiment_summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        生成研究结论摘要（合规话术）

        Args:
            asset_name: 资产名称
            asset_symbol: 资产代码
            technical_metrics: 技术指标数据
            sentiment_summary: 消息面摘要

        Returns:
            生成的结论文本（不超过200字）
        """
        if not self._check_enabled():
            return self._default_conclusion(asset_name)

        try:
            import litellm

            prompt = self._build_summary_prompt(
                asset_name, asset_symbol, technical_metrics, sentiment_summary
            )

            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
                temperature=0.5,  # 降低温度以保证合规性
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Research summary generated for {asset_symbol}")
            return summary

        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return self._default_conclusion(asset_name)

    def _build_sentiment_prompt(self, title: str, content: str) -> str:
        """构建情感分析Prompt"""
        return f"""分析以下金融新闻的情感倾向和投资影响：

---
标题：{title}
内容：{content[:500]}
---

请输出JSON格式：
{{
  "sentiment": "positive/neutral/negative",
  "sentiment_score": 0.8,
  "impact_type": "利好/利空/中性",
  "key_points": ["关键点1", "关键点2"],
  "reasoning": "简短分析原因"
}}"""

    def _build_summary_prompt(
        self,
        asset_name: str,
        asset_symbol: str,
        technical_metrics: Dict[str, Any],
        sentiment_summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建研究结论Prompt"""
        tech_summary = self._format_technical_metrics(technical_metrics)
        news_summary = self._format_sentiment_summary(sentiment_summary)

        return f"""基于以下分析数据，生成投资研究结论摘要：

---
资产：{asset_name} ({asset_symbol})
技术指标：{tech_summary}
消息面分析：{news_summary}
---

请生成自然语言结论（不超过200字），要求：
1. 不使用"肯定"、"必定"、"一定"等绝对性词汇
2. 使用"基于当前分析"、"显示潜力"、"呈现趋势"等合规表述
3. 包含风险提示
4. 语言简洁专业"""

    def _format_technical_metrics(self, metrics: Dict[str, Any]) -> str:
        """格式化技术指标为文本"""
        parts = []
        if metrics.get("trend_signal"):
            parts.append(f"趋势信号：{metrics['trend_signal']}")
        if metrics.get("technical_strength"):
            parts.append(f"技术强度：{metrics['technical_strength']}星")
        if metrics.get("rsi_14"):
            parts.append(f"RSI：{metrics['rsi_14']:.1f}")
        if metrics.get("volatility_30d"):
            parts.append(f"波动率：{metrics['volatility_30d']:.1f}%")
        return ", ".join(parts) if parts else "数据不足"

    def _format_sentiment_summary(self, summary: Optional[Dict[str, Any]]) -> str:
        """格式化消息面摘要为文本"""
        if not summary:
            return "暂无消息面数据"
        sentiment = summary.get("sentiment", "neutral")
        score = summary.get("sentiment_score", 0.5)
        return f"整体情绪：{sentiment}（分数：{score:.2f})"

    def _parse_sentiment_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM情感分析响应"""
        try:
            # 尝试提取JSON部分
            if "{" in response_text and "}" in response_text:
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                json_str = response_text[start:end]
                result = json.loads(json_str)
                # 验证必要字段
                if "sentiment" in result:
                    return {
                        "sentiment": result.get("sentiment", "neutral"),
                        "sentiment_score": float(result.get("sentiment_score", 0.5)),
                        "impact_type": result.get("impact_type", "中性"),
                        "key_points": result.get("key_points", []),
                        "reasoning": result.get("reasoning", ""),
                    }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return self._default_sentiment_result()

    def _default_sentiment_result(self) -> Dict[str, Any]:
        """默认情感分析结果（LLM未启用或失败时）"""
        return {
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "impact_type": "中性",
            "key_points": [],
            "reasoning": "LLM分析未启用",
        }

    def _default_conclusion(self, asset_name: str) -> str:
        """默认结论（LLM未启用或失败时）"""
        return f"基于当前技术分析，{asset_name}走势信号需综合判断。建议投资者根据自身风险偏好谨慎决策，注意控制仓位风险。"


# ============ Prompt模板 ============

SENTIMENT_SYSTEM_PROMPT = """你是一位专业的金融分析师，擅长分析财经新闻对投资市场的影响。
请根据新闻内容判断其对相关资产的影响方向和程度。
注意：你的分析应客观中立，避免过度乐观或悲观。"""

SUMMARY_SYSTEM_PROMPT = """你是一位合规的金融研究分析师，负责生成投资研究结论。
你的结论必须符合以下合规要求：
1. 不使用任何绝对性词汇（如"肯定"、"必定"、"一定"等）
2. 使用概率性表述（如"基于当前分析"、"显示潜力"、"可能呈现"等）
3. 必须包含风险提示
4. 结论应简洁专业，不超过200字
5. 不构成直接投资建议，仅供研究参考"""


# 单例实例
llm_service = LLMService()