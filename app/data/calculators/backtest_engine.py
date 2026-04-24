"""
回测引擎核心

实现四种策略的回测逻辑：
1. 均线突破 (MA Cross)
2. 动量轮动 (Momentum Rotation)
3. 定投策略 (DCA)
4. 风险平价 (Risk Parity)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import math

from loguru import logger


class BacktestEngine:
    """回测引擎基类"""

    def __init__(
        self,
        initial_capital: Decimal = Decimal("10000"),
        commission_rate: Decimal = Decimal("0.001"),  # 0.1%
        slippage_rate: Decimal = Decimal("0.0005"),   # 0.05%
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

    def calculate_commission(self, value: Decimal) -> Decimal:
        """计算手续费"""
        return value * self.commission_rate

    def apply_slippage(self, price: Decimal, is_buy: bool) -> Decimal:
        """应用滑点"""
        if is_buy:
            return price * (1 + self.slippage_rate)
        else:
            return price * (1 - self.slippage_rate)

    def calculate_metrics(self, equity_curve: List[Decimal]) -> Dict:
        """
        计算回测指标

        Args:
            equity_curve: 每日净值曲线

        Returns:
            指标字典
        """
        if len(equity_curve) < 2:
            return {}

        # 总收益
        total_return = float((equity_curve[-1] - equity_curve[0]) / equity_curve[0] * 100)

        # 年化收益（假设数据为日线）
        days = len(equity_curve)
        annualized_return = total_return / days * 365 if days > 0 else 0

        # 日收益率
        daily_returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i - 1] > 0:
                daily_returns.append(float((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]))

        # 波动率（年化）
        if daily_returns:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
            daily_volatility = math.sqrt(variance)
            annualized_volatility = daily_volatility * math.sqrt(252) * 100
        else:
            annualized_volatility = 0

        # 最大回撤
        max_equity = equity_curve[0]
        max_drawdown = 0.0
        for equity in equity_curve:
            if equity > max_equity:
                max_equity = equity
            drawdown = float((max_equity - equity) / max_equity * 100)
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 夏普比率
        if annualized_volatility > 0:
            sharpe_ratio = (annualized_return - 3) / annualized_volatility  # 假设无风险利率3%
        else:
            sharpe_ratio = 0

        return {
            "total_return": round(total_return, 2),
            "annualized_return": round(annualized_return, 2),
            "volatility": round(annualized_volatility, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
        }


class MACrossStrategy(BacktestEngine):
    """均线突破策略"""

    def run(
        self,
        prices: List[Dict],  # [{time, open, high, low, close, volume}]
        parameters: Dict,
    ) -> Dict:
        """
        运行均线突破策略回测

        Args:
            prices: 价格数据列表
            parameters: 策略参数
                - fast_period: 快线周期
                - slow_period: 慢线周期
                - ma_type: SMA 或 EMA

        Returns:
            回测结果
        """
        fast_period = parameters.get("fast_period", 5)
        slow_period = parameters.get("slow_period", 20)
        ma_type = parameters.get("ma_type", "SMA")

        if len(prices) < slow_period:
            return {"error": "数据不足以计算均线"}

        closes = [float(p["close"]) for p in prices]

        # 计算均线
        def calculate_ma(data: List[float], period: int, is_ema: bool) -> List[float]:
            mas = []
            for i in range(len(data)):
                if i < period - 1:
                    mas.append(None)
                else:
                    if is_ema:
                        # EMA计算
                        if i == period - 1:
                            ma = sum(data[:period]) / period
                        else:
                            multiplier = 2 / (period + 1)
                            ma = (data[i] - mas[i-1]) * multiplier + mas[i-1]
                    else:
                        # SMA计算
                        ma = sum(data[i-period+1:i+1]) / period
                    mas.append(ma)
            return mas

        is_ema = ma_type == "EMA"
        fast_ma = calculate_ma(closes, fast_period, is_ema)
        slow_ma = calculate_ma(closes, slow_period, is_ema)

        # 交易逻辑
        cash = self.initial_capital
        position = Decimal("0")  # 持仓数量
        equity_curve = []
        trades = []

        for i in range(slow_period, len(prices)):
            price = Decimal(str(closes[i]))
            fast = fast_ma[i]
            slow = slow_ma[i]

            prev_fast = fast_ma[i-1]
            prev_slow = slow_ma[i-1]

            # 检测交叉
            if fast and slow and prev_fast and prev_slow:
                # 金叉：快线突破慢线向上
                if prev_fast <= prev_slow and fast > slow:
                    if cash > 0:
                        # 买入
                        buy_price = self.apply_slippage(price, True)
                        max_shares = cash / buy_price
                        commission = self.calculate_commission(cash)
                        shares = max_shares - commission / buy_price

                        position = shares
                        cash = Decimal("0")

                        trades.append({
                            "time": prices[i]["time"],
                            "action": "buy",
                            "price": float(buy_price),
                            "quantity": float(shares),
                            "value": float(shares * buy_price),
                        })

                # 死叉：快线突破慢线向下
                elif prev_fast >= prev_slow and fast < slow:
                    if position > 0:
                        # 卖出
                        sell_price = self.apply_slippage(price, False)
                        value = position * sell_price
                        commission = self.calculate_commission(value)
                        cash = value - commission
                        position = Decimal("0")

                        trades.append({
                            "time": prices[i]["time"],
                            "action": "sell",
                            "price": float(sell_price),
                            "quantity": float(position),
                            "value": float(value),
                        })

            # 计算当日净值
            equity = cash + position * price
            equity_curve.append(equity)

        # 最后如果还有持仓，按最后价格清仓
        if position > 0:
            final_price = Decimal(str(closes[-1]))
            equity = cash + position * final_price
            equity_curve[-1] = equity

        # 计算指标
        metrics = self.calculate_metrics(equity_curve)

        return {
            **metrics,
            "total_trades": len(trades),
            "profit_trades": sum(1 for t in trades if t["action"] == "sell" and t.get("profit", 0) > 0),
            "loss_trades": sum(1 for t in trades if t["action"] == "sell" and t.get("profit", 0) <= 0),
            "equity_curve": [{"time": prices[i]["time"], "equity": float(e)} for i, e in enumerate(equity_curve)],
            "trades": trades,
        }


class MomentumStrategy(BacktestEngine):
    """动量轮动策略"""

    def run(
        self,
        assets_prices: Dict[str, List[Dict]],  # {asset_id: [{time, close}]}
        parameters: Dict,
    ) -> Dict:
        """
        运行动量轮动策略回测

        Args:
            assets_prices: 多资产价格数据
            parameters: 策略参数
                - lookback_period: 动量计算周期
                - top_n: 选择表现最好的N个资产
                - rebalance_frequency: 调仓频率

        Returns:
            回测结果
        """
        lookback = parameters.get("lookback_period", 20)
        top_n = parameters.get("top_n", 3)
        rebalance_freq = parameters.get("rebalance_frequency", "weekly")

        # 确定调仓间隔
        if rebalance_freq == "daily":
            rebalance_days = 1
        elif rebalance_freq == "weekly":
            rebalance_days = 7
        else:
            rebalance_days = 30

        # 检查数据
        for asset_id, prices in assets_prices.items():
            if len(prices) < lookback:
                return {"error": f"资产 {asset_id} 数据不足以计算动量"}

        # 获取所有资产的时间序列（假设同步）
        first_asset_prices = list(assets_prices.values())[0]
        total_days = len(first_asset_prices)

        cash = self.initial_capital
        positions: Dict[str, Decimal] = {}  # {asset_id: quantity}
        equity_curve = []
        trades = []
        last_rebalance = -rebalance_days

        for i in range(lookback, total_days):
            current_time = first_asset_prices[i]["time"]

            # 检查是否需要调仓
            if i - last_rebalance >= rebalance_days:
                # 计算各资产动量（收益率）
                momentum_scores = {}
                for asset_id, prices in assets_prices.items():
                    start_price = float(prices[i - lookback]["close"])
                    end_price = float(prices[i]["close"])
                    momentum = (end_price - start_price) / start_price * 100
                    momentum_scores[asset_id] = momentum

                # 选择动量最高的top_n资产
                sorted_assets = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
                selected_assets = [a[0] for a in sorted_assets[:top_n]]

                # 清仓不持有的资产
                for asset_id in list(positions.keys()):
                    if asset_id not in selected_assets and positions[asset_id] > 0:
                        price = Decimal(str(assets_prices[asset_id][i]["close"]))
                        sell_price = self.apply_slippage(price, False)
                        value = positions[asset_id] * sell_price
                        commission = self.calculate_commission(value)
                        cash += value - commission

                        trades.append({
                            "time": current_time,
                            "asset_id": asset_id,
                            "action": "sell",
                            "price": float(sell_price),
                            "quantity": float(positions[asset_id]),
                            "value": float(value),
                        })
                        positions[asset_id] = Decimal("0")

                # 等权买入选中的资产
                if cash > 0 and selected_assets:
                    allocation_per_asset = cash / len(selected_assets)

                    for asset_id in selected_assets:
                        price = Decimal(str(assets_prices[asset_id][i]["close"]))
                        buy_price = self.apply_slippage(price, True)
                        commission = self.calculate_commission(allocation_per_asset)
                        invest_amount = allocation_per_asset - commission
                        shares = invest_amount / buy_price

                        positions[asset_id] = positions.get(asset_id, Decimal("0")) + shares
                        cash -= allocation_per_asset

                        trades.append({
                            "time": current_time,
                            "asset_id": asset_id,
                            "action": "buy",
                            "price": float(buy_price),
                            "quantity": float(shares),
                            "value": float(allocation_per_asset),
                        })

                last_rebalance = i

            # 计算当日净值
            equity = cash
            for asset_id, qty in positions.items():
                if qty > 0:
                    price = Decimal(str(assets_prices[asset_id][i]["close"]))
                    equity += qty * price

            equity_curve.append(equity)

        # 计算指标
        metrics = self.calculate_metrics(equity_curve)

        return {
            **metrics,
            "total_trades": len(trades),
            "equity_curve": [{"time": first_asset_prices[i+lookback]["time"], "equity": float(e)} for i, e in enumerate(equity_curve)],
            "trades": trades,
        }


class DCAStrategy(BacktestEngine):
    """定投策略"""

    def run(
        self,
        prices: List[Dict],
        parameters: Dict,
    ) -> Dict:
        """
        运行定投策略回测

        Args:
            prices: 价格数据
            parameters: 策略参数
                - investment_amount: 每次投资金额
                - frequency: 投资频率
                - start_delay: 开始延迟天数

        Returns:
            回测结果
        """
        amount = Decimal(str(parameters.get("investment_amount", 1000)))
        frequency = parameters.get("frequency", "monthly")
        start_delay = parameters.get("start_delay", 0)

        # 确定投资间隔
        if frequency == "daily":
            invest_days = 1
        elif frequency == "weekly":
            invest_days = 7
        else:
            invest_days = 30

        cash = self.initial_capital
        position = Decimal("0")
        total_invested = Decimal("0")
        equity_curve = []
        trades = []

        for i in range(start_delay, len(prices)):
            current_time = prices[i]["time"]

            # 检查是否是投资日
            if (i - start_delay) % invest_days == 0 and cash >= amount:
                price = Decimal(str(prices[i]["close"]))
                buy_price = self.apply_slippage(price, True)
                commission = self.calculate_commission(amount)
                invest_amount = amount - commission
                shares = invest_amount / buy_price

                position += shares
                cash -= amount
                total_invested += amount

                trades.append({
                    "time": current_time,
                    "action": "buy",
                    "price": float(buy_price),
                    "quantity": float(shares),
                    "value": float(amount),
                })

            # 计算当日净值
            if i >= start_delay:
                price = Decimal(str(prices[i]["close"]))
                equity = cash + position * price
                equity_curve.append(equity)

        # 计算指标
        metrics = self.calculate_metrics(equity_curve)

        # 定投策略的收益 = (最终净值 - 总投入) / 总投入
        if total_invested > 0:
            actual_return = float((equity_curve[-1] - total_invested) / total_invested * 100)
            metrics["actual_return"] = round(actual_return, 2)

        return {
            **metrics,
            "total_trades": len(trades),
            "total_invested": float(total_invested),
            "equity_curve": [{"time": prices[i+start_delay]["time"], "equity": float(e)} for i, e in enumerate(equity_curve)],
            "trades": trades,
        }


class RiskParityStrategy(BacktestEngine):
    """风险平价策略"""

    def run(
        self,
        assets_prices: Dict[str, List[Dict]],
        parameters: Dict,
    ) -> Dict:
        """
        运行风险平价策略回测

        Args:
            assets_prices: 多资产价格数据
            parameters: 策略参数
                - target_volatility: 目标波动率
                - lookback_period: 波动率计算周期
                - rebalance_frequency: 调仓频率

        Returns:
            回测结果
        """
        target_vol = parameters.get("target_volatility", 15) / 100  # 转换为比例
        lookback = parameters.get("lookback_period", 60)
        rebalance_freq = parameters.get("rebalance_frequency", "monthly")

        # 确定调仓间隔
        if rebalance_freq == "daily":
            rebalance_days = 1
        elif rebalance_freq == "weekly":
            rebalance_days = 7
        else:
            rebalance_days = 30

        # 检查数据
        for asset_id, prices in assets_prices.items():
            if len(prices) < lookback:
                return {"error": f"资产 {asset_id} 数据不足以计算波动率"}

        first_asset_prices = list(assets_prices.values())[0]
        total_days = len(first_asset_prices)

        cash = self.initial_capital
        positions: Dict[str, Decimal] = {}
        equity_curve = []
        trades = []
        last_rebalance = -rebalance_days

        def calculate_volatility(prices: List[Dict], start: int, period: int) -> float:
            """计算历史波动率"""
            closes = [float(p["close"]) for p in prices[start-period:start]]
            if len(closes) < 2:
                return 0.3  # 默认30%

            returns = []
            for i in range(1, len(closes)):
                if closes[i-1] > 0:
                    returns.append((closes[i] - closes[i-1]) / closes[i-1])

            if not returns:
                return 0.3

            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
            daily_vol = math.sqrt(variance)
            return daily_vol * math.sqrt(252)  # 年化

        for i in range(lookback, total_days):
            current_time = first_asset_prices[i]["time"]

            # 检查是否需要调仓
            if i - last_rebalance >= rebalance_days:
                # 计算各资产波动率
                volatilities = {}
                for asset_id, prices in assets_prices.items():
                    vol = calculate_volatility(prices, i, lookback)
                    volatilities[asset_id] = vol if vol > 0 else 0.3

                # 风险平价权重：1/波动率归一化
                inv_vols = {aid: 1/vol for aid, vol in volatilities.items()}
                total_inv_vol = sum(inv_vols.values())
                weights = {aid: inv_vol/total_inv_vol for aid, inv_vol in inv_vols.items()}

                # 清仓并重新分配
                total_equity = cash
                for asset_id, qty in positions.items():
                    if qty > 0:
                        price = Decimal(str(assets_prices[asset_id][i]["close"]))
                        total_equity += qty * price

                # 清仓
                for asset_id, qty in positions.items():
                    if qty > 0:
                        price = Decimal(str(assets_prices[asset_id][i]["close"]))
                        sell_price = self.apply_slippage(price, False)
                        value = qty * sell_price
                        commission = self.calculate_commission(value)
                        cash += value - commission
                        trades.append({
                            "time": current_time,
                            "asset_id": asset_id,
                            "action": "sell",
                            "price": float(sell_price),
                            "quantity": float(qty),
                            "value": float(value),
                        })

                positions = {}

                # 按权重买入
                for asset_id, weight in weights.items():
                    allocation = total_equity * Decimal(str(weight))
                    price = Decimal(str(assets_prices[asset_id][i]["close"]))
                    buy_price = self.apply_slippage(price, True)
                    commission = self.calculate_commission(allocation)
                    invest = allocation - commission
                    shares = invest / buy_price

                    positions[asset_id] = shares
                    cash -= allocation

                    trades.append({
                        "time": current_time,
                        "asset_id": asset_id,
                        "action": "buy",
                        "price": float(buy_price),
                        "quantity": float(shares),
                        "value": float(allocation),
                    })

                last_rebalance = i

            # 计算当日净值
            equity = cash
            for asset_id, qty in positions.items():
                if qty > 0:
                    price = Decimal(str(assets_prices[asset_id][i]["close"]))
                    equity += qty * price

            equity_curve.append(equity)

        # 计算指标
        metrics = self.calculate_metrics(equity_curve)

        return {
            **metrics,
            "total_trades": len(trades),
            "equity_curve": [{"time": first_asset_prices[i+lookback]["time"], "equity": float(e)} for i, e in enumerate(equity_curve)],
            "trades": trades,
        }