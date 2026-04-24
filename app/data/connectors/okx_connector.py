"""
OKX加密货币数据连接器

使用ccxt统一交易所接口，为实盘交易做好准备
支持异步操作和自动签名认证

ccxt文档: https://docs.ccxt.com/
"""
import ccxt.async_support as ccxt
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from loguru import logger

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData


# ccxt K线周期映射
CCXT_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
    "1M": "1M",
}


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
            self._exchange = ccxt.okx({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'password': self.extra_config.get('passphrase'),
                'enableRateLimit': True,  # 启用请求限流，避免被封
                'options': {
                    'defaultType': 'spot',  # 默认现货交易
                },
            })

        return self._exchange

    async def get_ohlcv(self, symbol: str, interval: str = "1h",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取K线数据

        ccxt统一接口: fetch_ohlcv

        Args:
            symbol: 交易对符号 (如 BTC/USDT，ccxt格式)
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制 (ccxt默认100，最大1000)

        Returns:
            K线数据列表 (按时间正序)
        """
        exchange = await self._get_exchange()
        timeframe = CCXT_INTERVAL_MAP.get(interval, interval)

        # ccxt使用毫秒时间戳
        since = None
        if start_time:
            since = int(start_time.timestamp() * 1000)

        try:
            # ccxt返回格式: [[timestamp, open, high, low, close, volume], ...]
            ohlcv_raw = await exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit,
            )

            result = []
            for item in ohlcv_raw:
                # 过滤结束时间
                if end_time:
                    item_time = datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
                    if item_time > end_time:
                        continue

                ohlcv = OHLCVData(
                    time=datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                    open=Decimal(str(item[1])),
                    high=Decimal(str(item[2])),
                    low=Decimal(str(item[3])),
                    close=Decimal(str(item[4])),
                    volume=Decimal(str(item[5])),
                )
                result.append(ohlcv)

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

            return TickerData(
                symbol=symbol,
                last_price=Decimal(str(ticker['last'])),
                bid_price=Decimal(str(ticker.get('bid', 0) or 0)),
                ask_price=Decimal(str(ticker.get('ask', 0) or 0)),
                high_24h=Decimal(str(ticker.get('high', 0) or 0)),
                low_24h=Decimal(str(ticker.get('low', 0) or 0)),
                volume_24h=Decimal(str(ticker.get('baseVolume', 0) or 0)),
                change_24h=Decimal(str(ticker.get('percentage', 0) or 0)),
                timestamp=datetime.fromtimestamp(ticker['timestamp'] / 1000, tz=timezone.utc),
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