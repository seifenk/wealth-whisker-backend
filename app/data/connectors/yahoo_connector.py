"""
Yahoo Finance数据连接器

使用yfinance官方库获取股票、ETF、指数数据
支持自动数据格式化和错误处理

yfinance文档: https://github.com/ranaroussi/yfinance
"""
import os
import yfinance as yf
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

import requests
from loguru import logger

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData


# yfinance K线周期映射
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
    Yahoo Finance数据连接器（使用yfinance）

    支持股票、ETF、指数、基金等资产数据获取
    """

    def __init__(self):
        super().__init__(
            api_url="https://query1.finance.yahoo.com",
            api_key=None,
            api_secret=None,
        )
        # 配置requests会话使用代理
        self._setup_proxy_session()

    def _setup_proxy_session(self):
        """配置代理会话和User-Agent"""
        http_proxy = os.environ.get('HTTP_PROXY')
        https_proxy = os.environ.get('HTTPS_PROXY')

        # 创建requests会话
        self._session = requests.Session()

        # 设置User-Agent（Yahoo Finance需要）
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })

        if https_proxy or http_proxy:
            # 配置代理
            self._session.proxies = {
                'http': http_proxy,
                'https': https_proxy,
            }
            logger.info(f"Yahoo connector using proxy: {https_proxy or http_proxy}")

        # 设置yfinance使用这个会话
        yf.Ticker.session = self._session

    async def get_ohlcv(self, symbol: str, interval: str = "1d",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取K线数据

        yfinance接口: Ticker.history

        Args:
            symbol: 股票/ETF符号 (如 AAPL, GLD, ^GSPC)
            interval: K线周期
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

        try:
            # yfinance使用同步API，在异步环境中直接调用
            ticker = yf.Ticker(symbol)

            # 获取历史数据
            hist = ticker.history(
                start=start_time.strftime('%Y-%m-%d'),
                end=end_time.strftime('%Y-%m-%d'),
                interval=yf_interval,
                auto_adjust=True,  # 自动调整价格（分红、拆股）
                prepost=False,  # 不包含盘前盘后数据
            )

            if hist.empty:
                return []

            result = []
            for index, row in hist.iterrows():
                # yfinance返回的索引是DatetimeIndex
                if hasattr(index, 'to_pydatetime'):
                    time = index.to_pydatetime()
                    if time.tzinfo is None:
                        time = time.replace(tzinfo=timezone.utc)
                else:
                    time = datetime.now(timezone.utc)

                ohlcv = OHLCVData(
                    time=time,
                    open=Decimal(str(row['Open'])),
                    high=Decimal(str(row['High'])),
                    low=Decimal(str(row['Low'])),
                    close=Decimal(str(row['Close'])),
                    volume=Decimal(str(row['Volume'])),
                )
                result.append(ohlcv)

            # 返回最近limit条数据
            return result[-limit:] if len(result) > limit else result

        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise Exception(f"获取数据错误: {str(e)}")

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        直接使用requests调用Yahoo Finance API（比yfinance更稳定）

        Args:
            symbol: 股票符号

        Returns:
            行情数据
        """
        try:
            # 使用chart API获取价格（更稳定）
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d'

            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            result = data.get('chart', {}).get('result', [])

            if not result:
                raise Exception(f"No data for {symbol}")

            meta = result[0].get('meta', {})
            last_price = meta.get('regularMarketPrice', 0)

            return TickerData(
                symbol=symbol,
                last_price=Decimal(str(last_price)),
                bid_price=None,
                ask_price=None,
                high_24h=Decimal(str(meta.get('regularMarketDayHigh', 0) or 0)),
                low_24h=Decimal(str(meta.get('regularMarketDayLow', 0) or 0)),
                volume_24h=Decimal(str(meta.get('regularMarketVolume', 0) or 0)),
                timestamp=datetime.now(timezone.utc),
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching ticker for {symbol}: {e}")
            raise Exception(f"获取行情错误: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise Exception(f"获取行情错误: {str(e)}")

    async def get_tickers(self, symbols: List[str]) -> List[TickerData]:
        """
        获取批量行情数据

        yfinance支持批量下载

        Args:
            symbols: 股票符号列表

        Returns:
            行情数据列表
        """
        if not symbols:
            return []

        try:
            # 使用yfinance批量下载
            tickers = yf.Tickers(' '.join(symbols))

            result = []
            for symbol in symbols:
                try:
                    ticker_obj = tickers.tickers.get(symbol)
                    if ticker_obj is None:
                        continue

                    info = ticker_obj.info
                    if not info:
                        continue

                    last_price = info.get('currentPrice') or info.get('regularMarketPrice') or 0

                    ticker_data = TickerData(
                        symbol=symbol,
                        last_price=Decimal(str(last_price)),
                        bid_price=Decimal(str(info.get('bid', 0) or 0)),
                        ask_price=Decimal(str(info.get('ask', 0) or 0)),
                        high_24h=Decimal(str(info.get('dayHigh', 0) or 0)),
                        low_24h=Decimal(str(info.get('dayLow', 0) or 0)),
                        volume_24h=Decimal(str(info.get('volume', 0) or 0)),
                        timestamp=datetime.now(timezone.utc),
                    )
                    result.append(ticker_data)
                except Exception as e:
                    logger.warning(f"Error getting ticker for {symbol}: {e}")
                    continue

            return result

        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            raise Exception(f"获取行情错误: {str(e)}")

    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的股票符号列表

        返回预定义的主流股票列表

        Returns:
            股票符号列表
        """
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
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            return bool(info)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self):
        """
        关闭连接（yfinance无需显式关闭）
        """
        pass

    # ==================== 扩展信息接口 ====================

    async def get_company_info(self, symbol: str) -> dict:
        """
        获取公司详细信息

        Args:
            symbol: 股票符号

        Returns:
            公司信息字典
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                'symbol': symbol,
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'beta': info.get('beta', 0),
                'description': info.get('longBusinessSummary', ''),
            }
        except Exception as e:
            logger.error(f"Error getting company info for {symbol}: {e}")
            return {}

    async def get_dividends(self, symbol: str) -> List[dict]:
        """
        获取分红历史

        Args:
            symbol: 股票符号

        Returns:
            分红记录列表
        """
        try:
            ticker = yf.Ticker(symbol)
            dividends = ticker.dividends

            if dividends.empty:
                return []

            result = []
            for index, value in dividends.items():
                if hasattr(index, 'to_pydatetime'):
                    time = index.to_pydatetime()
                else:
                    time = datetime.now(timezone.utc)

                result.append({
                    'date': time.strftime('%Y-%m-%d'),
                    'amount': float(value),
                })

            return result
        except Exception as e:
            logger.error(f"Error getting dividends for {symbol}: {e}")
            return []

    async def get_splits(self, symbol: str) -> List[dict]:
        """
        获取拆股历史

        Args:
            symbol: 股票符号

        Returns:
            拆股记录列表
        """
        try:
            ticker = yf.Ticker(symbol)
            splits = ticker.splits

            if splits.empty:
                return []

            result = []
            for index, value in splits.items():
                if hasattr(index, 'to_pydatetime'):
                    time = index.to_pydatetime()
                else:
                    time = datetime.now(timezone.utc)

                result.append({
                    'date': time.strftime('%Y-%m-%d'),
                    'ratio': float(value),
                })

            return result
        except Exception as e:
            logger.error(f"Error getting splits for {symbol}: {e}")
            return []