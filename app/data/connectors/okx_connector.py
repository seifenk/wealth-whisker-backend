"""
OKX加密货币数据连接器

使用ccxt统一交易所接口，为实盘交易做好准备
支持异步操作和自动签名认证

ccxt文档: https://docs.ccxt.com/
"""
import os
import ccxt.async_support as ccxt
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from loguru import logger

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData
from app.data.constants import to_ccxt_interval, is_valid_interval


class OKXConnector(BaseConnector):
    """
    OKX交易所连接器（使用ccxt）

    支持现货、合约数据获取，为实盘交易预留接口
    """

    def __init__(self):
        super().__init__(
            api_url=settings.OKX_API_URL,
            api_key=settings.OKX_API_KEY,
            api_secret=settings.OKX_API_SECRET,
            passphrase=settings.OKX_API_PASSPHRASE,
        )
        self._exchange: Optional[ccxt.okx] = None

    async def _get_exchange(self) -> ccxt.okx:
        """
        获取ccxt交易所实例

        Returns:
            ccxt.okx 交易所实例
        """
        if self._exchange is None:
            # 获取代理配置
            http_proxy = os.environ.get('HTTP_PROXY')
            https_proxy = os.environ.get('HTTPS_PROXY')

            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'password': self.extra_config.get('passphrase'),
                'enableRateLimit': True,  # 启用请求限流，避免被封
                'options': {
                    'defaultType': 'spot',  # 默认现货交易
                    # 只加载现货市场。OKX 反向合约(BTC-USD-SWAP等)的 baseCcy 为 null，
                    # 会触发 ccxt parse_market 的 `base + '/' + quote` 崩溃，
                    # 导致整个 load_markets() 失败、所有行情不可用。
                    'fetchMarkets': ['spot'],
                },
            }

            # 配置代理（ccxt使用proxies参数）
            if http_proxy or https_proxy:
                config['proxies'] = {
                    'http': http_proxy,
                    'https': https_proxy,
                }
                logger.info(f"OKX connector using proxy: {https_proxy or http_proxy}")

            self._exchange = ccxt.okx(config)

        return self._exchange

    async def get_ohlcv(self, symbol: str, interval: str = "1h",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: Optional[int] = None) -> List[OHLCVData]:
        """
        获取K线数据

        OKX API参数说明（通过 ccxt params 传递）:
        - before: 请求此时间戳之后（更新的数据）
        - after: 请求此时间戳之前（更旧的数据）
        - limit: 最大300条

        分页逻辑：
        - 不传时间参数：返回最近 limit 条数据（从当前往前）
        - 只传 end_time：从 end_time 往前获取 limit 条（用于分页加载）
        - 传 start_time/end_time：获取时间范围内的数据

        Args:
            symbol: 交易对符号 (如 BTC/USDT，ccxt格式)
            interval: K线周期
            start_time: 开始时间（可选）
            end_time: 结束时间（可选，用于分页）
            limit: 返回数量限制 (OKX最大300)

        Returns:
            K线数据列表 (按时间正序：从旧到新)
        """
        exchange = await self._get_exchange()
        timeframe = to_ccxt_interval(interval)

        if not is_valid_interval(interval):
            logger.warning(f"Invalid interval '{interval}', using default 1h")
            timeframe = '1h'

        # OKX 单次最大 300 条
        effective_limit = min(limit or 300, 300)

        try:
            result = []

            # 场景1：只传 end_time（分页加载）
            # 使用 OKX API 的 after 参数获取 end_time 之前的旧数据
            if end_time and not start_time:
                logger.info(f"OKX OHLCV pagination: interval={timeframe}, "
                           f"end_time={end_time}, limit={effective_limit}")

                # OKX API: after 参数表示"请求此时间戳之前的数据"
                # ccxt 通过 params 传递原生参数
                ohlcv_raw = await exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=effective_limit,
                    params={'after': int(end_time.timestamp() * 1000)},
                )

                # OKX 返回的数据是倒序（最新在前），需要反转成正序
                for item in reversed(ohlcv_raw):
                    ohlcv_time = datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
                    # 确保数据在 end_time 之前
                    if ohlcv_time < end_time:
                        ohlcv = OHLCVData(
                            time=ohlcv_time,
                            open=Decimal(str(item[1])),
                            high=Decimal(str(item[2])),
                            low=Decimal(str(item[3])),
                            close=Decimal(str(item[4])),
                            volume=Decimal(str(item[5])),
                        )
                        result.append(ohlcv)

                # 再次反转确保时间正序（从旧到新）
                result.sort(key=lambda x: x.time)

            # 场景2：传 start_time 和 end_time（时间范围查询）
            elif start_time and end_time:
                time_diff = end_time - start_time
                interval_minutes = {
                    '1m': 1, '5m': 5, '15m': 15, '30m': 30,
                    '1h': 60, '4h': 240, '1d': 1440,
                    '1w': 10080, '1M': 43200
                }
                minutes = interval_minutes.get(timeframe, 60)
                expected_candles = int(time_diff.total_seconds() / 60 / minutes) + 1

                logger.info(f"OKX OHLCV range query: interval={timeframe}, "
                           f"start={start_time}, end={end_time}, "
                           f"expected={expected_candles} candles")

                # 分页获取时间范围内的数据
                batch_size = 300
                current_since = int(start_time.timestamp() * 1000)
                end_ts = int(end_time.timestamp() * 1000)
                duration_ms = minutes * 60 * 1000

                while current_since < end_ts:
                    batch_raw = await exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_since,
                        limit=batch_size,
                        params={},
                    )

                    if not batch_raw:
                        break

                    for item in batch_raw:
                        ohlcv_time = datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
                        if ohlcv_time >= start_time and ohlcv_time <= end_time:
                            ohlcv = OHLCVData(
                                time=ohlcv_time,
                                open=Decimal(str(item[1])),
                                high=Decimal(str(item[2])),
                                low=Decimal(str(item[3])),
                                close=Decimal(str(item[4])),
                                volume=Decimal(str(item[5])),
                            )
                            result.append(ohlcv)

                    last_ts = batch_raw[-1][0]
                    current_since = last_ts + duration_ms

                    if len(batch_raw) < batch_size or last_ts >= end_ts:
                        break

            # 场景3：不传时间参数（首次加载）
            else:
                logger.info(f"OKX OHLCV initial load: interval={timeframe}, limit={effective_limit}")

                # 获取最近的数据
                ohlcv_raw = await exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=effective_limit,
                    params={},
                )

                for item in ohlcv_raw:
                    ohlcv = OHLCVData(
                        time=datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                        open=Decimal(str(item[1])),
                        high=Decimal(str(item[2])),
                        low=Decimal(str(item[3])),
                        close=Decimal(str(item[4])),
                        volume=Decimal(str(item[5])),
                    )
                    result.append(ohlcv)

                # 确保时间正序
                result.sort(key=lambda x: x.time)

            logger.info(f"OKX OHLCV returned: {len(result)} candles")
            return result

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV for {symbol}: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV for {symbol}: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        ccxt统一接口: fetch_ticker

        Args:
            symbol: 交易对符号 (如 BTC/USDT)

        Returns:
            行情数据
        """
        exchange = await self._get_exchange()

        try:
            ticker = await exchange.fetch_ticker(symbol)

            # 安全处理 None 值
            last_price = ticker.get('last')
            if last_price is None:
                logger.warning(f"OKX ticker last price is None for {symbol}")
                last_price = 0

            return TickerData(
                symbol=symbol,
                last_price=Decimal(str(last_price)),
                bid_price=Decimal(str(ticker.get('bid') or 0)),
                ask_price=Decimal(str(ticker.get('ask') or 0)),
                high_24h=Decimal(str(ticker.get('high') or 0)),
                low_24h=Decimal(str(ticker.get('low') or 0)),
                volume_24h=Decimal(str(ticker.get('baseVolume') or 0)),
                change_24h=Decimal(str(ticker.get('percentage') or 0)),
                timestamp=datetime.fromtimestamp((ticker.get('timestamp') or 0) / 1000, tz=timezone.utc) if ticker.get('timestamp') else datetime.now(timezone.utc),
            )

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching ticker for {symbol}: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol}: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[TickerData]:
        """
        获取批量行情数据

        ccxt统一接口: fetch_tickers

        Args:
            symbols: 交易对符号列表

        Returns:
            行情数据列表
        """
        exchange = await self._get_exchange()

        try:
            if symbols:
                tickers = await exchange.fetch_tickers(symbols)
            else:
                # 获取所有行情
                tickers = await exchange.fetch_tickers()

            result = []
            for sym, ticker in tickers.items():
                try:
                    ticker_data = TickerData(
                        symbol=sym,
                        last_price=Decimal(str(ticker['last'])),
                        bid_price=Decimal(str(ticker.get('bid', 0) or 0)),
                        ask_price=Decimal(str(ticker.get('ask', 0) or 0)),
                        high_24h=Decimal(str(ticker.get('high', 0) or 0)),
                        low_24h=Decimal(str(ticker.get('low', 0) or 0)),
                        volume_24h=Decimal(str(ticker.get('baseVolume', 0) or 0)),
                        timestamp=datetime.fromtimestamp(ticker['timestamp'] / 1000, tz=timezone.utc),
                    )
                    result.append(ticker_data)
                except (ValueError, KeyError) as e:
                    continue

            return result

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching tickers: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching tickers: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的交易对列表

        ccxt接口: load_markets

        Returns:
            交易对符号列表 (ccxt格式: BTC/USDT)
        """
        exchange = await self._get_exchange()

        try:
            await exchange.load_markets()
            return list(exchange.symbols)
        except ccxt.NetworkError as e:
            logger.error(f"Network error loading markets: {e}")
            raise Exception(f"网络错误: {str(e)}")

    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        try:
            exchange = await self._get_exchange()
            await exchange.load_markets()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self):
        """
        关闭ccxt交易所连接

        必须调用以释放资源
        """
        if self._exchange:
            await self._exchange.close()
            self._exchange = None

    # ==================== 实盘交易预留接口 ====================

    async def create_order(self, symbol: str, order_type: str, side: str,
                           amount: float, price: Optional[float] = None) -> dict:
        """
        创建订单（实盘交易预留接口）

        ccxt统一接口: create_order

        Args:
            symbol: 交易对符号
            order_type: 订单类型 ('limit', 'market')
            side: 方向 ('buy', 'sell')
            amount: 数量
            price: 价格（限价单必填）

        Returns:
            订单信息

        注意: 此接口需要在配置中设置正确的API密钥和权限
        """
        exchange = await self._get_exchange()

        try:
            order = await exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
            )
            return order
        except ccxt.NetworkError as e:
            logger.error(f"Network error creating order: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error creating order: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def get_balance(self) -> dict:
        """
        获取账户余额（实盘交易预留接口）

        ccxt统一接口: fetch_balance

        Returns:
            账户余额信息
        """
        exchange = await self._get_exchange()

        try:
            balance = await exchange.fetch_balance()
            return balance
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching balance: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching balance: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取未完成订单（实盘交易预留接口）

        ccxt统一接口: fetch_open_orders

        Args:
            symbol: 交易对符号（可选）

        Returns:
            未完成订单列表
        """
        exchange = await self._get_exchange()

        try:
            orders = await exchange.fetch_open_orders(symbol=symbol)
            return orders
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching open orders: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching open orders: {e}")
            raise Exception(f"交易所错误: {str(e)}")

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> dict:
        """
        取消订单（实盘交易预留接口）

        ccxt统一接口: cancel_order

        Args:
            order_id: 订单ID
            symbol: 交易对符号（某些交易所需要）

        Returns:
            取消结果
        """
        exchange = await self._get_exchange()

        try:
            result = await exchange.cancel_order(order_id, symbol=symbol)
            return result
        except ccxt.NetworkError as e:
            logger.error(f"Network error canceling order: {e}")
            raise Exception(f"网络错误: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error canceling order: {e}")
            raise Exception(f"交易所错误: {str(e)}")