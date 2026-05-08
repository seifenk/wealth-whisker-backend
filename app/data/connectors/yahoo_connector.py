"""
Yahoo Finance数据连接器

使用requests直接调用Yahoo Finance API获取股票、ETF、指数数据
支持自动数据格式化和错误处理

Yahoo Finance API文档: https://query1.finance.yahoo.com/v8/finance/chart/
"""
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

import requests
from loguru import logger

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData
from app.data.constants import to_yfinance_interval, is_valid_interval


class YahooFinanceConnector(BaseConnector):
    """
    Yahoo Finance数据连接器（使用yfinance）

    支持股票、ETF、指数、基金等资产数据获取
    """

    def __init__(self):
        super().__init__(
            api_url=settings.YAHOO_FINANCE_API_URL,
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

    async def get_ohlcv(self, symbol: str, interval: str = "1d",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 300) -> List[OHLCVData]:
        """
        获取K线数据

        分页逻辑：
        - 不传时间参数：返回最近 limit 条数据
        - 只传 end_time：从 end_time 往前获取 limit 条（分页加载）
        - 传 start_time/end_time：获取时间范围内的数据

        Args:
            symbol: 股票/ETF符号 (如 AAPL, GLD)
            interval: K线周期
            start_time: 开始时间（可选）
            end_time: 结束时间（可选，用于分页）
            limit: 返回数量限制（默认300）

        Returns:
            K线数据列表 (按时间正序：从旧到新)
        """
        yf_interval = to_yfinance_interval(interval)

        if not is_valid_interval(interval):
            logger.warning(f"Invalid interval '{interval}', using default 1d")
            yf_interval = '1d'

        # Yahoo API 使用 period1/period2 时间戳参数
        # period1: 开始时间戳（秒）
        # period2: 结束时间戳（秒）

        try:
            # 场景1：只传 end_time（分页加载）
            # 从 end_time 往前获取足够的历史数据
            if end_time and not start_time:
                logger.info(f"Yahoo OHLCV pagination: interval={yf_interval}, "
                           f"end_time={end_time}, limit={limit}")

                # 计算需要的时间跨度
                # Yahoo 不同 interval 的每条数据对应的时间跨度
                interval_days_map = {
                    '1m': 1, '5m': 1, '15m': 1, '30m': 1,
                    '1h': 1, '1d': 1, '1wk': 7, '1mo': 30,
                }
                days_per_bar = interval_days_map.get(yf_interval, 1)
                # 需要的天数 = limit * 每条数据的天数
                needed_days = limit * days_per_bar + 30  # 加30天缓冲

                # period1 = end_time - needed_days
                period1 = int((end_time - timedelta(days=needed_days)).timestamp())
                period2 = int(end_time.timestamp())

                url = f'{settings.YAHOO_FINANCE_API_URL}/v8/finance/chart/{symbol}?interval={yf_interval}&period1={period1}&period2={period2}'

            # 场景2：传 start_time 和 end_time（时间范围查询）
            elif start_time and end_time:
                logger.info(f"Yahoo OHLCV range query: interval={yf_interval}, "
                           f"start={start_time}, end={end_time}")

                period1 = int(start_time.timestamp())
                period2 = int(end_time.timestamp())

                url = f'{settings.YAHOO_FINANCE_API_URL}/v8/finance/chart/{symbol}?interval={yf_interval}&period1={period1}&period2={period2}'

            # 场景3：不传时间参数（首次加载）
            else:
                logger.info(f"Yahoo OHLCV initial load: interval={yf_interval}, limit={limit}")

                # 使用 range=max 获取所有历史数据，然后取最近 limit 条
                # 或者根据 limit 计算需要的 range
                interval_days_map = {
                    '1m': 1, '5m': 1, '15m': 1, '30m': 1,
                    '1h': 1, '1d': 1, '1wk': 7, '1mo': 30,
                }
                days_per_bar = interval_days_map.get(yf_interval, 1)
                needed_days = limit * days_per_bar + 30

                # Yahoo range 参数: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
                if needed_days <= 1:
                    range_param = '1d'
                elif needed_days <= 5:
                    range_param = '5d'
                elif needed_days <= 30:
                    range_param = '1mo'
                elif needed_days <= 90:
                    range_param = '3mo'
                elif needed_days <= 180:
                    range_param = '6mo'
                elif needed_days <= 365:
                    range_param = '1y'
                elif needed_days <= 730:
                    range_param = '2y'
                elif needed_days <= 1825:
                    range_param = '5y'
                else:
                    range_param = 'max'

                url = f'{settings.YAHOO_FINANCE_API_URL}/v8/finance/chart/{symbol}?interval={yf_interval}&range={range_param}'

            resp = self._session.get(url, timeout=settings.API_REQUEST_TIMEOUT)
            resp.raise_for_status()

            data = resp.json()
            result = data.get('chart', {}).get('result', [])

            if not result:
                logger.warning(f"No OHLCV data for {symbol}")
                return []

            # 解析时间戳
            timestamps = result[0].get('timestamp', [])
            if not timestamps:
                return []

            # 解析价格数据
            indicators = result[0].get('indicators', {})
            quote = indicators.get('quote', [])

            if not quote:
                return []

            quote_data = quote[0]
            opens = quote_data.get('open', [])
            highs = quote_data.get('high', [])
            lows = quote_data.get('low', [])
            closes = quote_data.get('close', [])
            volumes = quote_data.get('volume', [])

            ohlcv_list = []

            for i in range(len(timestamps)):
                # 跳过None值（Yahoo可能有缺失数据）
                if opens[i] is None or closes[i] is None:
                    continue

                timestamp = timestamps[i]
                time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

                # 时间过滤
                if start_time and time < start_time:
                    continue
                if end_time and time >= end_time:  # 分页时排除 end_time 本身
                    continue

                ohlcv = OHLCVData(
                    time=time,
                    open=Decimal(str(opens[i] or closes[i])),
                    high=Decimal(str(highs[i] or closes[i])),
                    low=Decimal(str(lows[i] or closes[i])),
                    close=Decimal(str(closes[i])),
                    volume=Decimal(str(volumes[i] or 0)),
                )
                ohlcv_list.append(ohlcv)

            # 按时间正序排列
            ohlcv_list.sort(key=lambda x: x.time)

            # 分页加载时，取最后 limit 条（最接近 end_time 的旧数据）
            if end_time and not start_time and len(ohlcv_list) > limit:
                ohlcv_list = ohlcv_list[-limit:]
            # 首次加载时，取最后 limit 条（最近的数据）
            elif not start_time and not end_time and len(ohlcv_list) > limit:
                ohlcv_list = ohlcv_list[-limit:]

            logger.info(f"Yahoo OHLCV returned: {len(ohlcv_list)} candles")
            return ohlcv_list

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching OHLCV for {symbol}: {e}")
            raise Exception(f"获取K线错误: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise Exception(f"获取K线错误: {str(e)}")

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        直接使用requests调用Yahoo Finance API（比yfinance更稳定）
        从最近2天的K线数据计算24小时涨跌幅

        Args:
            symbol: 股票符号

        Returns:
            行情数据
        """
        try:
            # 使用chart API获取价格和涨跌幅（更稳定）
            # 获取最近2天数据以计算24小时涨跌幅
            url = f'{settings.YAHOO_FINANCE_API_URL}/v8/finance/chart/{symbol}?interval=1d&range=2d'

            resp = self._session.get(url, timeout=settings.API_REQUEST_TIMEOUT)
            resp.raise_for_status()

            data = resp.json()
            result = data.get('chart', {}).get('result', [])

            if not result:
                raise Exception(f"No data for {symbol}")

            meta = result[0].get('meta', {})
            last_price = meta.get('regularMarketPrice', 0)

            # 计算24小时涨跌幅
            # 从最近2天的收盘价计算
            change_24h = None

            indicators = result[0].get('indicators', {})
            quote = indicators.get('quote', [])

            if quote:
                quote_data = quote[0]
                closes = quote_data.get('close', [])

                # 过滤掉None值
                valid_closes = [c for c in closes if c is not None]

                if len(valid_closes) >= 2:
                    # 使用最近2个收盘价计算涨跌幅
                    previous_close = valid_closes[-2]
                    current_close = valid_closes[-1] if last_price == 0 else last_price

                    # 计算百分比涨跌幅
                    if previous_close > 0:
                        change_24h = Decimal(str((current_close - previous_close) / previous_close * 100))
                elif len(valid_closes) == 1:
                    # 只有1个数据点，使用chartPreviousClose作为参考
                    chart_previous_close = meta.get('chartPreviousClose', 0)
                    current_close = valid_closes[-1] if last_price == 0 else last_price

                    if chart_previous_close > 0:
                        change_24h = Decimal(str((current_close - chart_previous_close) / chart_previous_close * 100))

            return TickerData(
                symbol=symbol,
                last_price=Decimal(str(last_price)),
                bid_price=None,
                ask_price=None,
                high_24h=Decimal(str(meta.get('regularMarketDayHigh', 0) or 0)),
                low_24h=Decimal(str(meta.get('regularMarketDayLow', 0) or 0)),
                volume_24h=Decimal(str(meta.get('regularMarketVolume', 0) or 0)),
                change_24h=change_24h,  # 添加24小时涨跌幅
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

        Yahoo不支持批量API，逐个调用get_ticker

        Args:
            symbols: 股票符号列表

        Returns:
            行情数据列表
        """
        if not symbols:
            return []

        result = []
        for symbol in symbols:
            try:
                ticker = await self.get_ticker(symbol)
                result.append(ticker)
            except Exception as e:
                logger.warning(f"Error getting ticker for {symbol}: {e}")
                continue

        return result

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
            # 使用requests测试连接
            url = f'{settings.YAHOO_FINANCE_API_URL}/v8/finance/chart/AAPL?interval=1d&range=1d'
            resp = self._session.get(url, timeout=settings.API_REQUEST_TIMEOUT)
            resp.raise_for_status()

            data = resp.json()
            return 'chart' in data and 'result' in data['chart']
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self):
        """
        关闭连接（yfinance无需显式关闭）
        """
        pass

    # ==================== 扩展信息接口 ====================

    # 注意：以下扩展功能需要yfinance库，但核心功能已使用requests API
    # 如果需要这些功能，请在requirements.txt中保留yfinance依赖

    async def get_company_info(self, symbol: str) -> dict:
        """
        获取公司详细信息（扩展功能）

        Args:
            symbol: 股票符号

        Returns:
            公司信息字典
        """
        # 暂时返回基础信息，完整功能需要yfinance库
        try:
            ticker = await self.get_ticker(symbol)
            return {
                'symbol': symbol,
                'name': symbol,
                'sector': '',
                'industry': '',
                'market_cap': 0,
                'pe_ratio': 0,
                'dividend_yield': 0,
                'beta': 0,
                'description': '',
                'last_price': float(ticker.last_price),
            }
        except Exception as e:
            logger.error(f"Error getting company info for {symbol}: {e}")
            return {}

    async def get_dividends(self, symbol: str) -> List[dict]:
        """
        获取分红历史（扩展功能，需要yfinance）

        Args:
            symbol: 股票符号

        Returns:
            分红记录列表
        """
        # 暂时返回空列表，完整功能需要yfinance库
        logger.info(f"Dividends data for {symbol} requires yfinance library")
        return []

    async def get_splits(self, symbol: str) -> List[dict]:
        """
        获取拆股历史（扩展功能，需要yfinance）

        Args:
            symbol: 股票符号

        Returns:
            拆股记录列表
        """
        # 暂时返回空列表，完整功能需要yfinance库
        logger.info(f"Splits data for {symbol} requires yfinance library")
        return []