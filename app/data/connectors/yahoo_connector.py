"""
Yahoo Finance数据连接器

用于获取股票、ETF、基金等资产数据
免费API，无需密钥

Yahoo Finance API文档:
- https://query1.finance.yahoo.com/v8/finance/chart/{symbol}
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import httpx

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData


# Yahoo Finance K线周期映射
YF_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "1d": "1d",
    "1w": "1wk",
    "1M": "1mo",
}


class YahooFinanceConnector(BaseConnector):
    """
    Yahoo Finance数据连接器

    支持股票、ETF、指数、基金等资产数据获取
    """

    def __init__(self):
        super().__init__(
            api_url="https://query1.finance.yahoo.com",
            api_key=None,
            api_secret=None,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
        return self._client

    async def _request(self, path: str, params: dict) -> dict:
        """
        发送API请求

        Args:
            path: API路径
            params: 查询参数

        Returns:
            API响应数据
        """
        client = await self._get_client()

        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"Request error: {str(e)}")

    async def get_ohlcv(self, symbol: str, interval: str = "1d",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取K线数据

        Yahoo Finance API: /v8/finance/chart/{symbol}

        Args:
            symbol: 股票/ETF符号 (如 AAPL, GLD, ^GSPC)
            interval: K线周期 (1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo)
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            K线数据列表 (按时间正序)
        """
        yf_interval = YF_INTERVAL_MAP.get(interval, interval)

        # 默认时间范围
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        params = {
            "symbol": symbol,
            "interval": yf_interval,
            "period1": int(start_time.timestamp()),
            "period2": int(end_time.timestamp()),
            "includePrePost": "false",
            "lang": "zh-CN",
            "region": "US",
        }

        data = await self._request("/v8/finance/chart/" + symbol, params)

        result = data.get("chart", {}).get("result", [])
        if not result:
            return []

        chart_data = result[0]
        timestamps = chart_data.get("timestamp", [])
        indicators = chart_data.get("indicators", {}).get("quote", [])

        if not indicators:
            return []

        quote_data = indicators[0]
        opens = quote_data.get("open", [])
        highs = quote_data.get("high", [])
        lows = quote_data.get("low", [])
        closes = quote_data.get("close", [])
        volumes = quote_data.get("volume", [])

        ohlcv_list = []
        for i, ts in enumerate(timestamps):
            # 跳过None值（Yahoo Finance有时会有空数据）
            if opens[i] is None or closes[i] is None:
                continue

            ohlcv = OHLCVData(
                time=datetime.fromtimestamp(ts, tz=timezone.utc),
                open=Decimal(str(opens[i])),
                high=Decimal(str(highs[i] or opens[i])),
                low=Decimal(str(lows[i] or closes[i])),
                close=Decimal(str(closes[i])),
                volume=Decimal(str(volumes[i] or 0)),
            )
            ohlcv_list.append(ohlcv)

        # 返回最近limit条数据
        return ohlcv_list[-limit:] if len(ohlcv_list) > limit else ohlcv_list

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        Yahoo Finance API: /v6/finance/quote

        Args:
            symbol: 股票符号

        Returns:
            行情数据
        """
        params = {
            "symbols": symbol,
            "lang": "zh-CN",
            "region": "US",
        }

        data = await self._request("/v6/finance/quote", params)

        quote_response = data.get("quoteResponse", {})
        results = quote_response.get("result", [])

        if not results:
            raise Exception(f"No ticker data for {symbol}")

        quote = results[0]

        return TickerData(
            symbol=symbol,
            last_price=Decimal(str(quote.get("regularMarketPrice", 0))),
            bid_price=Decimal(str(quote.get("bid", 0) or 0)),
            ask_price=Decimal(str(quote.get("ask", 0) or 0)),
            high_24h=Decimal(str(quote.get("regularMarketDayHigh", 0) or 0)),
            low_24h=Decimal(str(quote.get("regularMarketDayLow", 0) or 0)),
            volume_24h=Decimal(str(quote.get("regularMarketVolume", 0) or 0)),
            change_24h=Decimal(str(quote.get("regularMarketChangePercent", 0) or 0)),
            timestamp=datetime.fromtimestamp(quote.get("regularMarketTime", 0), tz=timezone.utc),
        )

    async def get_tickers(self, symbols: List[str]) -> List[TickerData]:
        """
        获取批量行情数据

        Args:
            symbols: 股票符号列表

        Returns:
            行情数据列表
        """
        if not symbols:
            return []

        params = {
            "symbols": ",".join(symbols),
            "lang": "zh-CN",
            "region": "US",
        }

        data = await self._request("/v6/finance/quote", params)

        quote_response = data.get("quoteResponse", {})
        results = quote_response.get("result", [])

        tickers = []
        for quote in results:
            try:
                ticker = TickerData(
                    symbol=quote.get("symbol", ""),
                    last_price=Decimal(str(quote.get("regularMarketPrice", 0))),
                    bid_price=Decimal(str(quote.get("bid", 0) or 0)),
                    ask_price=Decimal(str(quote.get("ask", 0) or 0)),
                    high_24h=Decimal(str(quote.get("regularMarketDayHigh", 0) or 0)),
                    low_24h=Decimal(str(quote.get("regularMarketDayLow", 0) or 0)),
                    volume_24h=Decimal(str(quote.get("regularMarketVolume", 0) or 0)),
                    change_24h=Decimal(str(quote.get("regularMarketChangePercent", 0) or 0)),
                    timestamp=datetime.fromtimestamp(quote.get("regularMarketTime", 0), tz=timezone.utc),
                )
                tickers.append(ticker)
            except (ValueError, KeyError) as e:
                continue

        return tickers

    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的股票符号列表

        Yahoo Finance不提供此API，返回预定义列表

        Returns:
            预定义的股票符号列表
        """
        # 返回预定义的主流股票列表
        return [
            # 美股科技巨头
            "AAPL",  # Apple
            "GOOGL", # Google
            "MSFT",  # Microsoft
            "AMZN",  # Amazon
            "META",  # Meta/Facebook
            "NVDA",  # NVIDIA
            "TSLA",  # Tesla
            # 中国股票
            "BABA",  # Alibaba
            "JD",    # JD.com
            "PDD",   # PDD Holdings
            "NIO",   # NIO
            # 指数ETF
            "SPY",   # S&P 500 ETF
            "QQQ",   # Nasdaq 100 ETF
            "DIA",   # Dow Jones ETF
            # 其他
            "V",     # Visa
            "JPM",   # JPMorgan
            "WMT",   # Walmart
        ]

    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        try:
            await self.get_ticker("AAPL")
            return True
        except Exception:
            return False

    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()