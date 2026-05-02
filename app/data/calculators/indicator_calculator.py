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
    def calculate_kdj(
        prices: List[float],
        period: int = 9,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        KDJ随机指标

        Args:
            prices: 价格序列（需要包含high和low，简化版用close近似）
            period: 计算周期（默认9）

        Returns:
            (k_value, d_value, j_value)
            K值：快速指标，反应灵敏
            D值：慢速指标，K的平滑
            J值：J=3K-2D，超前指标
        """
        if len(prices) < period:
            return None, None, None

        # 简化版：使用收盘价近似计算
        # 实际应用中应使用 (close, low, high) 三元组
        # 这里假设 prices 就是 close 价格序列
        # 用 close 近似 high/low（实际场景应有完整OHLC数据）

        rsv_values = []
        for i in range(period - 1, len(prices)):
            # 计算最近period个周期的最高最低价
            window = prices[i - period + 1:i + 1]
            highest = max(window)
            lowest = min(window)
            current = prices[i]

            # RSV = (Close - Lowest) / (Highest - Lowest) * 100
            if highest == lowest:
                rsv = 50.0  # 无波动时取中值
            else:
                rsv = (current - lowest) / (highest - lowest) * 100
            rsv_values.append(rsv)

        if not rsv_values:
            return None, None, None

        # 计算K值（首次用50）
        k_values = [50.0]
        for rsv in rsv_values[1:]:
            k = k_values[-1] * 2 / 3 + rsv * 1 / 3
            k_values.append(k)

        # 计算D值（首次用50）
        d_values = [50.0]
        for k in k_values[1:]:
            d = d_values[-1] * 2 / 3 + k * 1 / 3
            d_values.append(d)

        # 计算J值
        j_values = [3 * k - 2 * d for k, d in zip(k_values, d_values)]

        # 返回最新值
        return round(k_values[-1], 2), round(d_values[-1], 2), round(j_values[-1], 2)

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


class SupportResistanceCalculator:
    """支撑阻力位计算器"""

    @staticmethod
    def find_support_levels(
        prices: List[float],
        window: int = 20,
        min_touches: int = 2,
    ) -> List[dict]:
        """
        识别支撑位

        Args:
            prices: 价格序列
            window: 搜索窗口大小
            min_touches: 最少触及次数（有效性要求）

        Returns:
            支撑位列表，每个元素包含 {price, strength, touches}
        """
        if len(prices) < window:
            return []

        support_levels = []

        # 识别局部最小值作为潜在支撑位
        for i in range(window, len(prices) - window):
            # 检查是否为局部最小值
            left_window = prices[i - window:i]
            right_window = prices[i:i + window]
            current = prices[i]

            if current <= min(left_window) and current <= min(right_window):
                # 这是一个局部最小值
                support_price = current

                # 计算触及次数（价格接近该支撑位的次数）
                tolerance = support_price * 0.02  # 2%容差
                touches = sum(1 for p in prices if abs(p - support_price) <= tolerance)

                if touches >= min_touches:
                    # 计算强度（触及次数越多越强）
                    strength = min(touches, 5)

                    support_levels.append({
                        "price": round(support_price, 4),
                        "strength": strength,
                        "touches": touches
                    })

        # 按强度排序，保留前5个最强支撑位
        support_levels.sort(key=lambda x: x["strength"], reverse=True)
        return support_levels[:5]

    @staticmethod
    def find_resistance_levels(
        prices: List[float],
        window: int = 20,
        min_touches: int = 2,
    ) -> List[dict]:
        """
        识别阻力位

        Args:
            prices: 价格序列
            window: 搜索窗口大小
            min_touches: 最少触及次数

        Returns:
            阻力位列表，每个元素包含 {price, strength, touches}
        """
        if len(prices) < window:
            return []

        resistance_levels = []

        # 识别局部最大值作为潜在阻力位
        for i in range(window, len(prices) - window):
            left_window = prices[i - window:i]
            right_window = prices[i:i + window]
            current = prices[i]

            if current >= max(left_window) and current >= max(right_window):
                resistance_price = current

                # 计算触及次数
                tolerance = resistance_price * 0.02
                touches = sum(1 for p in prices if abs(p - resistance_price) <= tolerance)

                if touches >= min_touches:
                    strength = min(touches, 5)

                    resistance_levels.append({
                        "price": round(resistance_price, 4),
                        "strength": strength,
                        "touches": touches
                    })

        # 按强度排序
        resistance_levels.sort(key=lambda x: x["strength"], reverse=True)
        return resistance_levels[:5]

    @staticmethod
    def calculate_break_probability(
        current_price: float,
        target_level: float,
        volatility: float,
        days: int = 5,
    ) -> float:
        """
        计算突破/跌破概率

        基于波动率和距离估算突破概率

        Args:
            current_price: 当前价格
            target_level: 目标支撑/阻力位价格
            volatility: 年化波动率（百分比）
            days: 预测天数

        Returns:
            突破概率（0-100）
        """
        if volatility <= 0 or days <= 0:
            return 0.0

        # 计算距离（百分比）
        distance = abs(target_level - current_price) / current_price * 100

        # 日波动率
        daily_volatility = volatility / math.sqrt(252)

        # 预测期内预期波动范围
        expected_range = daily_volatility * math.sqrt(days) * 100

        # 简化概率估算：距离越小，波动率越大，突破概率越高
        if expected_range <= 0:
            return 0.0

        # 使用正态分布近似
        # Z-score = 距离 / 预期波动范围
        z_score = distance / expected_range

        # 突破概率 = 1 - P(价格在范围内)
        # 简化：假设正态分布，使用Z值估算
        # Z < 1: 高概率(>30%), Z < 2: 中概率(>5%), Z > 2: 低概率
        if z_score < 0.5:
            probability = 60.0
        elif z_score < 1.0:
            probability = 40.0
        elif z_score < 1.5:
            probability = 25.0
        elif z_score < 2.0:
            probability = 10.0
        else:
            probability = 5.0

        return round(probability, 1)

    @staticmethod
    def get_current_position(
        current_price: float,
        support_levels: List[dict],
        resistance_levels: List[dict],
    ) -> str:
        """
        判断当前价格相对于支撑阻力位的位置

        Args:
            current_price: 当前价格
            support_levels: 支撑位列表
            resistance_levels: 阻力位列表

        Returns:
            'above_resistance' | 'below_support' | 'near_support' | 'near_resistance' | 'normal'
        """
        if not support_levels and not resistance_levels:
            return "normal"

        # 获取最近的支撑位
        nearest_support = None
        for level in support_levels:
            if level["price"] < current_price:
                nearest_support = level["price"]
                break

        # 获取最近的阻力位
        nearest_resistance = None
        for level in resistance_levels:
            if level["price"] > current_price:
                nearest_resistance = level["price"]
                break

        tolerance = current_price * 0.02  # 2%容差

        # 判断位置
        if nearest_resistance and current_price >= nearest_resistance:
            return "above_resistance"
        elif nearest_support and current_price <= nearest_support:
            return "below_support"
        elif nearest_resistance and abs(current_price - nearest_resistance) <= tolerance:
            return "near_resistance"
        elif nearest_support and abs(current_price - nearest_support) <= tolerance:
            return "near_support"
        else:
            return "normal"


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


class TechnicalStrengthCalculator:
    """技术面强度评分器"""

    @staticmethod
    def calculate_technical_strength(
        prices: List[float],
        metrics: Optional[dict] = None,
    ) -> int:
        """
        计算技术面强度评分（1-5星）

        评分维度：
        - MA趋势强度（权重30%）
        - RSI/MACD/KDJ一致性（权重30%）
        - 价格位置（布林带）（权重20%）
        - 趋势信号强度（权重20%）

        Args:
            prices: 价格序列
            metrics: 已计算的指标字典（可选，若提供则复用）

        Returns:
            1-5星评级
        """
        if len(prices) < 20:
            return 1  # 数据不足，最低评分

        # 计算或复用指标
        if metrics is None:
            metrics = MetricsCalculator.calculate_all_metrics(prices)

        score = 0.0

        # 1. MA趋势强度（30%权重）
        sma_5 = IndicatorCalculator.calculate_sma(prices, 5)
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        current_price = prices[-1]

        if sma_5 and sma_20:
            # MA多头排列加分
            if sma_5 > sma_20:
                ma_strength = (sma_5 - sma_20) / sma_20 * 100
                if ma_strength > 2:
                    score += 30
                elif ma_strength > 1:
                    score += 25
                else:
                    score += 15
            elif sma_5 < sma_20:
                ma_strength = (sma_20 - sma_5) / sma_20 * 100
                if ma_strength > 2:
                    score += 5  # 强空头排列，低分
                else:
                    score += 10
            else:
                score += 15

            # 价格在MA之上加分
            if current_price > sma_20:
                score += 10
            elif current_price > sma_5:
                score += 5

        # 2. RSI/MACD/KDJ一致性（30%权重）
        rsi = metrics.get("rsi_14") or IndicatorCalculator.calculate_rsi(prices)
        macd, signal, hist = metrics.get("macd"), metrics.get("macd_signal"), metrics.get("macd_histogram")
        if macd is None:
            macd, signal, hist = IndicatorCalculator.calculate_macd(prices)
        k, d, j = IndicatorCalculator.calculate_kdj(prices)

        consistent_signals = 0
        total_signals = 0

        # RSI信号
        if rsi:
            total_signals += 1
            if rsi > 50:
                consistent_signals += 1  # 偏强
            elif rsi < 30:
                consistent_signals += 0.5  # 超卖可能反弹

        # MACD信号
        if hist:
            total_signals += 1
            if hist > 0:
                consistent_signals += 1  # 金叉/上升

        # KDJ信号
        if k and d:
            total_signals += 1
            if k > d and j > k:
                consistent_signals += 1  # J线领先，强势
            elif k > d:
                consistent_signals += 0.5

        if total_signals > 0:
            consistency_ratio = consistent_signals / total_signals
            score += consistency_ratio * 30

        # 3. 布林带位置（20%权重）
        middle, upper, lower = metrics.get("bollinger_middle"), metrics.get("bollinger_upper"), metrics.get("bollinger_lower")
        if middle is None:
            middle, upper, lower = IndicatorCalculator.calculate_bollinger_bands(prices)

        if middle and upper and lower:
            # 价格在中轨之上
            if current_price > middle:
                position_score = (current_price - middle) / (upper - middle) * 10
                score += min(position_score, 15)
            else:
                position_score = (middle - current_price) / (middle - lower) * 5
                score += max(5 - position_score, 2)

        # 4. 趋势信号强度（20%权重）
        trend_signal = metrics.get("trend_signal") or TrendSignalCalculator.calculate_trend_signal(prices)
        if trend_signal == "bullish":
            score += 20
        elif trend_signal == "neutral":
            score += 10
        else:
            score += 5

        # 映射到1-5星
        if score >= 80:
            return 5
        elif score >= 65:
            return 4
        elif score >= 50:
            return 3
        elif score >= 35:
            return 2
        else:
            return 1

    @staticmethod
    def calculate_signal_consistency(
        prices: List[float],
        metrics: Optional[dict] = None,
    ) -> float:
        """
        计算信号一致性百分比

        检查多个技术指标是否指向同一方向

        Args:
            prices: 价格序列
            metrics: 已计算的指标字典

        Returns:
            一致性百分比（0-100）
        """
        if len(prices) < 20:
            return 30.0

        if metrics is None:
            metrics = MetricsCalculator.calculate_all_metrics(prices)

        # 获取趋势信号作为基准方向
        trend_signal = metrics.get("trend_signal") or TrendSignalCalculator.calculate_trend_signal(prices)

        # 判断各指标与趋势的一致性
        signals = []

        # MA趋势
        sma_5 = IndicatorCalculator.calculate_sma(prices, 5)
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        if sma_5 and sma_20:
            if sma_5 > sma_20:
                signals.append("bullish")
            elif sma_5 < sma_20:
                signals.append("bearish")
            else:
                signals.append("neutral")

        # RSI
        rsi = metrics.get("rsi_14") or IndicatorCalculator.calculate_rsi(prices)
        if rsi:
            if rsi > 60:
                signals.append("bullish")
            elif rsi < 40:
                signals.append("bearish")
            else:
                signals.append("neutral")

        # MACD
        macd, signal_line, hist = metrics.get("macd"), metrics.get("macd_signal"), metrics.get("macd_histogram")
        if hist:
            if hist > 0:
                signals.append("bullish")
            elif hist < 0:
                signals.append("bearish")
            else:
                signals.append("neutral")

        # KDJ
        k, d, j = IndicatorCalculator.calculate_kdj(prices)
        if k and d and j:
            if j > k and k > d:
                signals.append("bullish")
            elif j < k and k < d:
                signals.append("bearish")
            else:
                signals.append("neutral")

        # 布林带位置
        current_price = prices[-1]
        middle = metrics.get("bollinger_middle")
        if middle:
            if current_price > middle:
                signals.append("bullish")
            elif current_price < middle:
                signals.append("bearish")
            else:
                signals.append("neutral")

        if not signals:
            return 30.0

        # 计算一致性
        bullish_count = sum(1 for s in signals if s == "bullish")
        bearish_count = sum(1 for s in signals if s == "bearish")
        neutral_count = sum(1 for s in signals if s == "neutral")

        total = len(signals)

        # 一致性 = 主导方向的占比
        if trend_signal == "bullish":
            consistency = (bullish_count / total) * 100
        elif trend_signal == "bearish":
            consistency = (bearish_count / total) * 100
        else:
            consistency = (neutral_count / total) * 100 + 30  # 中性时加分

        return round(min(consistency, 95), 1)  # 最高不超过95%

    @staticmethod
    def get_technical_signals_detail(
        prices: List[float],
        metrics: Optional[dict] = None,
    ) -> dict:
        """
        获取技术信号详情（用于前端展示）

        Args:
            prices: 价格序列
            metrics: 已计算的指标字典

        Returns:
            技术信号详情字典
        """
        if len(prices) < 20:
            return {}

        if metrics is None:
            metrics = MetricsCalculator.calculate_all_metrics(prices)

        # MA趋势
        sma_5 = IndicatorCalculator.calculate_sma(prices, 5)
        sma_20 = IndicatorCalculator.calculate_sma(prices, 20)
        ma_trend = "neutral"
        if sma_5 and sma_20:
            if sma_5 > sma_20 * 1.01:  # 1%阈值
                ma_trend = "bullish"
            elif sma_5 < sma_20 * 0.99:
                ma_trend = "bearish"

        # RSI状态
        rsi = metrics.get("rsi_14") or IndicatorCalculator.calculate_rsi(prices)
        rsi_status = "normal"
        if rsi:
            if rsi > 70:
                rsi_status = "overbought"
            elif rsi < 30:
                rsi_status = "oversold"

        # MACD信号
        macd, signal_line, hist = metrics.get("macd"), metrics.get("macd_signal"), metrics.get("macd_histogram")
        if hist is None:
            macd, signal_line, hist = IndicatorCalculator.calculate_macd(prices)
        macd_signal = "neutral"
        if hist:
            if hist > 0:
                macd_signal = "bullish"
            elif hist < 0:
                macd_signal = "bearish"

        # 成交量趋势（简化：用价格波动代替）
        volatility = metrics.get("volatility_30d")
        volume_trend = "stable"
        if volatility:
            if volatility > 40:
                volume_trend = "increasing"
            elif volatility < 15:
                volume_trend = "decreasing"

        return {
            "ma_trend": ma_trend,
            "rsi_status": rsi_status,
            "rsi_value": rsi,
            "macd_signal": macd_signal,
            "volume_trend": volume_trend,
        }


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

        # KDJ指标
        k, d, j = IndicatorCalculator.calculate_kdj(prices)
        metrics["kdj_k"] = k
        metrics["kdj_d"] = d
        metrics["kdj_j"] = j

        # 支撑阻力位
        support_levels = SupportResistanceCalculator.find_support_levels(prices)
        resistance_levels = SupportResistanceCalculator.find_resistance_levels(prices)
        metrics["support_levels"] = [level["price"] for level in support_levels]
        metrics["resistance_levels"] = [level["price"] for level in resistance_levels]
        metrics["support_levels_detail"] = support_levels
        metrics["resistance_levels_detail"] = resistance_levels

        # 技术面强度评分
        metrics["technical_strength"] = TechnicalStrengthCalculator.calculate_technical_strength(prices, metrics)
        metrics["signal_consistency"] = TechnicalStrengthCalculator.calculate_signal_consistency(prices, metrics)

        # 技术信号详情
        metrics["technical_signals"] = TechnicalStrengthCalculator.get_technical_signals_detail(prices, metrics)

        # 当前价格相对于支撑阻力位的位置
        current_price = prices[-1]
        metrics["sr_position"] = SupportResistanceCalculator.get_current_position(
            current_price, support_levels, resistance_levels
        )

        # 格式化（保留精度，处理None）
        for key, value in metrics.items():
            if isinstance(value, float):
                metrics[key] = round(value, 4)
            elif value is None and key in ["change_24h", "change_7d", "volatility_30d", "sharpe_ratio"]:
                metrics[key] = None

        return metrics