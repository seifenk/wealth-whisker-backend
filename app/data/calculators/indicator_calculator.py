"""
指标计算器模块

计算资产技术指标、风险指标、趋势信号等
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
import math


class IndicatorCalculator:
    """技术指标计算器"""

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> Optional[float]:
        """简单移动平均"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """指数移动平均"""
        if len(prices) < period:
            return None

        # 初始EMA用SMA
        ema = sum(prices[:period]) / period
        multiplier = 2 / (period + 1)

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """相对强弱指数"""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return None

        # 计算平均涨跌
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        MACD指标

        Returns:
            (macd_line, signal_line, histogram)
        """
        if len(prices) < slow_period + signal_period:
            return None, None, None

        ema_fast = IndicatorCalculator.calculate_ema(prices, fast_period)
        ema_slow = IndicatorCalculator.calculate_ema(prices, slow_period)

        if ema_fast is None or ema_slow is None:
            return None, None, None

        macd_line = ema_fast - ema_slow

        # 计算MACD的EMA作为signal line
        # 简化：直接计算macd序列的EMA
        macd_values = []
        for i in range(slow_period, len(prices) + 1):
            fast = IndicatorCalculator.calculate_ema(prices[:i], fast_period)
            slow = IndicatorCalculator.calculate_ema(prices[:i], slow_period)
            if fast and slow:
                macd_values.append(fast - slow)

        if len(macd_values) < signal_period:
            return macd_line, None, None

        signal_line = IndicatorCalculator.calculate_ema(macd_values, signal_period)
        histogram = macd_line - signal_line if signal_line else None

        return round(macd_line, 4), round(signal_line, 4) if signal_line else None, round(histogram, 4) if histogram else None

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        布林带

        Returns:
            (middle_band, upper_band, lower_band)
        """
        if len(prices) < period:
            return None, None, None

        # 中轨 = SMA
        middle = sum(prices[-period:]) / period

        # 标准差
        variance = sum((p - middle) ** 2 for p in prices[-period:]) / period
        std = math.sqrt(variance)

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return round(middle, 4), round(upper, 4), round(lower, 4)


class RiskCalculator:
    """风险指标计算器"""

    @staticmethod
    def calculate_volatility(
        prices: List[float],
        annualize: bool = True,
        trading_days: int = 252,
    ) -> Optional[float]:
        """
        计算波动率（基于收益率）

        Args:
            prices: 价格序列
            annualize: 是否年化
            trading_days: 年化交易日数

        Returns:
            波动率（百分比）
        """
        if len(prices) < 2:
            return None

        # 计算日收益率
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        if not returns:
            return None

        # 计算收益率标准差
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        daily_volatility = math.sqrt(variance)

        # 年化
        if annualize:
            annualized_volatility = daily_volatility * math.sqrt(trading_days) * 100
            return round(annualized_volatility, 2)

        return round(daily_volatility * 100, 2)

    @staticmethod
    def calculate_max_drawdown(prices: List[float]) -> Optional[float]:
        """
        最大回撤

        Returns:
            最大回撤百分比
        """
        if len(prices) < 2:
            return None

        max_price = prices[0]
        max_drawdown = 0.0

        for price in prices:
            if price > max_price:
                max_price = price
            drawdown = (max_price - price) / max_price * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return round(max_drawdown, 2)

    @staticmethod
    def calculate_sharpe_ratio(
        returns: List[float],
        risk_free_rate: float = 3.0,
        annualize: bool = True,
    ) -> Optional[float]:
        """
        夏普比率

        Args:
            returns: 日收益率序列（百分比）
            risk_free_rate: 无风险利率（年化百分比）
            annualize: 是否年化

        Returns:
            夏普比率
        """
        if len(returns) < 2:
            return None

        # 平均收益率
        avg_return = sum(returns) / len(returns)

        # 收益率标准差
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_return = math.sqrt(variance)

        if std_return == 0:
            return 0.0

        # 年化平均收益率
        if annualize:
            annual_return = avg_return * 252
            annual_std = std_return * math.sqrt(252)
        else:
            annual_return = avg_return
            annual_std = std_return

        sharpe = (annual_return - risk_free_rate) / (annual_std * 100) if annual_std > 0 else 0

        return round(sharpe, 2)

    @staticmethod
    def calculate_risk_level(
        volatility: Optional[float],
        max_drawdown: Optional[float],
    ) -> str:
        """
        风险等级判定

        Args:
            volatility: 年化波动率（百分比）
            max_drawdown: 最大回撤（百分比）

        Returns:
            'low', 'medium', 'high'
        """
        if volatility is None:
            return "medium"

        # 基于波动率的主要判断
        if volatility > 40:
            return "high"
        elif volatility < 20:
            return "low"

        # 结合最大回撤调整
        if max_drawdown and max_drawdown > 30:
            return "high"

        return "medium"


class TrendSignalCalculator:
    """趋势信号计算器"""

    @staticmethod
    def calculate_trend_signal(
        prices: List[float],
        change_24h: Optional[float] = None,
    ) -> str:
        """
        综合趋势信号

        结合多个技术指标判断趋势

        Args:
            prices: 价格序列（最近30天日K）
            change_24h: 24小时涨跌幅（百分比）

        Returns:
            'bullish' (看涨), 'bearish' (看跌), 'neutral' (中性)
        """
        if len(prices) < 20:
            # 数据不足，仅用24h涨跌幅判断
            if change_24h:
                if change_24h > 2:
                    return "bullish"
                elif change_24h < -2:
                    return "bearish"
            return "neutral"

        signals = []

        # 1. MA趋势信号（权重最高）
        sma_5 = IndicatorCalculator.calculate_sma(prices, 5)
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        current_price = prices[-1]

        if sma_5 and sma_20:
            # 短期均线在长期均线之上 -> 看涨
            if sma_5 > sma_20:
                signals.append(1)  # bullish
            else:
                signals.append(-1)  # bearish

            # 价格在均线之上
            if current_price > sma_20:
                signals.append(0.5)
            else:
                signals.append(-0.5)

        # 2. RSI信号
        rsi = IndicatorCalculator.calculate_rsi(prices, 14)
        if rsi:
            if rsi > 70:
                signals.append(-0.5)  # 超买，可能回调
            elif rsi < 30:
                signals.append(0.5)  # 超卖，可能反弹
            elif rsi > 50:
                signals.append(0.3)  # 偏强
            else:
                signals.append(-0.3)  # 偏弱

        # 3. MACD信号
        macd, signal, hist = IndicatorCalculator.calculate_macd(prices)
        if macd and hist:
            if hist > 0:
                signals.append(0.5)  # 金叉/上升
            else:
                signals.append(-0.5)  # 死叉/下降

        # 4. 布林带位置
        middle, upper, lower = IndicatorCalculator.calculate_bollinger_bands(prices)
        if middle and upper and lower:
            if current_price > middle:
                signals.append(0.3)
            else:
                signals.append(-0.3)

            # 接近上轨 -> 看涨但可能回调
            if current_price > upper * 0.95:
                signals.append(-0.2)  # 超买预警
            # 接近下轨 -> 看跌但可能反弹
            elif current_price < lower * 1.05:
                signals.append(0.2)  # 超卖反弹机会

        # 5. 24h涨跌幅（作为辅助）
        if change_24h:
            if change_24h > 5:
                signals.append(0.5)
            elif change_24h > 2:
                signals.append(0.2)
            elif change_24h < -5:
                signals.append(-0.5)
            elif change_24h < -2:
                signals.append(-0.2)

        # 综合判断
        if not signals:
            return "neutral"

        total_signal = sum(signals)

        if total_signal > 1.0:
            return "bullish"
        elif total_signal < -1.0:
            return "bearish"
        else:
            return "neutral"

    @staticmethod
    def calculate_confidence_score(
        prices: List[float],
        trend_signal: str,
    ) -> float:
        """
        置信度计算

        基于多个因子的一致性判断置信度

        Args:
            prices: 价格序列
            trend_signal: 趋势信号

        Returns:
            置信度（0-1之间）
        """
        if len(prices) < 20:
            return 0.3  # 数据不足，低置信度

        # 计算多个指标
        indicators_alignment = 0
        total_indicators = 0

        # 1. MA一致性
        sma_5 = IndicatorCalculator.calculate_sma(prices, 5)
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        if sma_5 and sma_20:
            total_indicators += 1
            if trend_signal == "bullish" and sma_5 > sma_20:
                indicators_alignment += 1
            elif trend_signal == "bearish" and sma_5 < sma_20:
                indicators_alignment += 1

        # 2. RSI一致性
        rsi = IndicatorCalculator.calculate_rsi(prices)
        if rsi:
            total_indicators += 1
            if trend_signal == "bullish" and rsi > 50:
                indicators_alignment += 1
            elif trend_signal == "bearish" and rsi < 50:
                indicators_alignment += 1

        # 3. MACD一致性
        macd, signal, hist = IndicatorCalculator.calculate_macd(prices)
        if hist:
            total_indicators += 1
            if trend_signal == "bullish" and hist > 0:
                indicators_alignment += 1
            elif trend_signal == "bearish" and hist < 0:
                indicators_alignment += 1

        # 4. 趋势强度（基于价格位置）
        total_indicators += 1
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        if sma_20:
            price_ratio = prices[-1] / sma_20
            if trend_signal == "bullish" and price_ratio > 1.02:
                indicators_alignment += 1
            elif trend_signal == "bearish" and price_ratio < 0.98:
                indicators_alignment += 1

        if total_indicators == 0:
            return 0.3

        # 基础置信度 = 指标一致性比例
        base_confidence = indicators_alignment / total_indicators

        # 根据数据量调整置信度（数据越多置信度越高）
        data_factor = min(len(prices) / 30, 1.0)

        # 最终置信度
        confidence = base_confidence * 0.7 + data_factor * 0.3

        return round(min(confidence, 0.95), 2)  # 最高不超过0.95


class MetricsCalculator:
    """综合指标计算器"""

    @staticmethod
    def calculate_all_metrics(prices: List[float], days: int = 30) -> dict:
        """
        计算所有指标

        Args:
            prices: 价格序列
            days: 计算周期

        Returns:
            指标字典
        """
        if len(prices) < 2:
            return {}

        metrics = {}

        # 涨跌幅
        metrics["change_24h"] = (prices[-1] - prices[-2]) / prices[-2] * 100 if len(prices) >= 2 else None

        if len(prices) >= 7:
            metrics["change_7d"] = (prices[-1] - prices[-7]) / prices[-7] * 100

        # 波动率
        metrics["volatility_30d"] = RiskCalculator.calculate_volatility(prices)

        # 最大回撤
        metrics["max_drawdown"] = RiskCalculator.calculate_max_drawdown(prices)

        # 风险等级
        metrics["risk_level"] = RiskCalculator.calculate_risk_level(
            metrics["volatility_30d"],
            metrics["max_drawdown"],
        )

        # 趋势信号
        metrics["trend_signal"] = TrendSignalCalculator.calculate_trend_signal(
            prices,
            metrics["change_24h"],
        )

        # 置信度
        metrics["confidence_score"] = TrendSignalCalculator.calculate_confidence_score(
            prices,
            metrics["trend_signal"],
        )

        # 夏普比率
        if len(prices) >= days:
            returns = []
            for i in range(1, len(prices)):
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1] * 100)
            metrics["sharpe_ratio"] = RiskCalculator.calculate_sharpe_ratio(returns)

        # 技术指标
        metrics["sma_20"] = IndicatorCalculator.calculate_sma(prices, 20)
        metrics["ema_20"] = IndicatorCalculator.calculate_ema(prices, 20)
        metrics["rsi_14"] = IndicatorCalculator.calculate_rsi(prices, 14)

        macd, signal, hist = IndicatorCalculator.calculate_macd(prices)
        metrics["macd"] = macd
        metrics["macd_signal"] = signal
        metrics["macd_histogram"] = hist

        middle, upper, lower = IndicatorCalculator.calculate_bollinger_bands(prices)
        metrics["bollinger_middle"] = middle
        metrics["bollinger_upper"] = upper
        metrics["bollinger_lower"] = lower

        # 格式化（保留精度，处理None）
        for key, value in metrics.items():
            if isinstance(value, float):
                metrics[key] = round(value, 4)
            elif value is None and key in ["change_24h", "change_7d", "volatility_30d", "sharpe_ratio"]:
                metrics[key] = None

        return metrics