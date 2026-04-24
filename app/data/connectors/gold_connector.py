"""
黄金数据连接器

使用Yahoo Finance获取黄金ETF和期货数据
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from app.data.connectors.yahoo_connector import YahooFinanceConnector
from app.data.connectors.base import OHLCVData, TickerData


# 黄金相关资产符号
GOLD_SYMBOLS = [
    ("GLD", "SPDR Gold Shares ETF", "gold_etf"),
    ("IAU", "iShares Gold Trust ETF", "gold_etf"),
    ("GC=F", "Gold Futures", "gold_futures"),
    ("XAUUSD=X", "Gold/USD Exchange Rate", "gold_spot"),
]


class GoldConnector(YahooFinanceConnector):
    """
    黄金数据连接器

    通过Yahoo Finance获取黄金ETF、期货、现货价格数据
    """

    async def get_gold_price(self, symbol: str = "GLD") -> TickerData:
        """
        获取黄金价格

        Args:
            symbol: 黄金资产符号 (GLD, IAU, GC=F, XAUUSD=X)

        Returns:
            黄金行情数据
        """
        return await self.get_ticker(symbol)

    async def get_gold_ohlcv(self, symbol: str = "GLD", interval: str = "1d",
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit: int = 100) -> List[OHLCVData]:
        """
        获取黄金K线数据

        Args:
            symbol: 黄金资产符号
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        return await self.get_ohlcv(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def get_all_gold_tickers(self) -> List[TickerData]:
        """
        获取所有黄金资产行情

        Returns:
            黄金行情数据列表
        """
        symbols = [s[0] for s in GOLD_SYMBOLS]
        return await self.get_tickers(symbols)

    async def get_supported_gold_symbols(self) -> List[str]:
        """
        获取支持的黄金资产符号

        Returns:
            黄金资产符号列表
        """
        return [s[0] for s in GOLD_SYMBOLS]

    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        try:
            await self.get_ticker("GLD")
            return True
        except Exception:
            return False