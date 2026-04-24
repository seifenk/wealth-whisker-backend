"""
OKX交易所数据连接器

OKX API文档: https://www.okx.com/docs-v5/
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData


# OKX K线周期映射
INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
    "1D": "1D",
    "1w": "1W",
    "1M": "1M",
}


class OKXConnector(BaseConnector):
    """
    OKX交易所数据连接器

    支持获取加密货币K线和实时行情数据
    """

    def __init__(self):
        super().__init__(
            api_url=settings.OKX_API_URL,
            api_key=settings.OKX_API_KEY,
            api_secret=settings.OKX_API_SECRET,
            passphrase=settings.OKX_API_PASSPHRASE,
        )
        self.passphrase = settings.OKX_API_PASSPHRASE
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def _generate_signature(self, timestamp: str, method: str,
                            request_path: str, body: str = "") -> str:
        """
        生成API签名

        Args:
            timestamp: 时间戳字符串
            method: HTTP方法
            request_path: 请求路径
            body: 请求体

        Returns:
            签名字符串
        """
        if not self.api_secret:
            return ""

        message = timestamp + method + request_path + body
        mac = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        )
        return mac.hexdigest()

    def _get_headers(self, method: str, request_path: str,
                     body: str = "") -> dict:
        """
        获取认证请求头

        Args:
            method: HTTP方法
            request_path: 请求路径
            body: 请求体

        Returns:
            请求头字典
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        sign = self._generate_signature(timestamp, method, request_path, body)

        headers = {
            "OK-ACCESS-KEY": self.api_key or "",
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase or "",
            "Content-Type": "application/json",
        }
        return headers

    async def _request(self, method: str, path: str,
                       params: Optional[dict] = None) -> dict:
        """
        发送API请求

        Args:
            method: HTTP方法
            path: API路径
            params: 查询参数

        Returns:
            API响应数据
        """
        client = await self._get_client()
        query_string = urlencode(params or {})
        request_path = path + ("?" + query_string if query_string else "")

        headers = self._get_headers(method, request_path)

        try:
            if method == "GET":
                response = await client.get(path, params=params, headers=headers)
            else:
                response = await client.post(path, json=params, headers=headers)

            response.raise_for_status()
            data = response.json()

            if data.get("code") != "0":
                raise Exception(f"OKX API error: {data.get('msg', 'Unknown error')}")

            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"Request error: {str(e)}")

    async def get_ohlcv(self, symbol: str, interval: str = "1h",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取K线数据

        OKX API: GET /api/v5/market/candles

        Args:
            symbol: 交易对符号 (如 BTC-USDT)
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制 (最大300)

        Returns:
            K线数据列表 (按时间正序)
        """
        bar = INTERVAL_MAP.get(interval, interval)

        params = {
            "instId": symbol,
            "bar": bar,
            "limit": min(limit, 300),
        }

        # OKX使用ISO 8601格式的毫秒时间戳
        if start_time:
            params["before"] = str(int(start_time.timestamp() * 1000))
        if end_time:
            params["after"] = str(int(end_time.timestamp() * 1000))

        raw_data = await self._request("GET", "/api/v5/market/candles", params)

        # OKX返回的数据格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        # ts是毫秒时间戳，o/h/l/c/vol是字符串
        result = []
        for item in raw_data:
            try:
                ohlcv = OHLCVData(
                    time=datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.utc),
                    open=Decimal(item[1]),
                    high=Decimal(item[2]),
                    low=Decimal(item[3]),
                    close=Decimal(item[4]),
                    volume=Decimal(item[5]),
                )
                result.append(ohlcv)
            except (ValueError, IndexError) as e:
                continue

        # OKX返回数据是倒序的，需要正序排列
        result.sort(key=lambda x: x.time)
        return result

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        OKX API: GET /api/v5/market/ticker

        Args:
            symbol: 交易对符号

        Returns:
            行情数据
        """
        params = {"instId": symbol}
        raw_data = await self._request("GET", "/api/v5/market/ticker", params)

        if not raw_data:
            raise Exception(f"No ticker data for {symbol}")

        item = raw_data[0]
        return TickerData(
            symbol=symbol,
            last_price=Decimal(item.get("last", "0")),
            bid_price=Decimal(item.get("bidPx", "0")),
            ask_price=Decimal(item.get("askPx", "0")),
            high_24h=Decimal(item.get("high24h", "0")),
            low_24h=Decimal(item.get("low24h", "0")),
            volume_24h=Decimal(item.get("vol24h", "0")),
            change_24h=Decimal(item.get("sodUtc0", "0")),  # 开盘价
            timestamp=datetime.fromtimestamp(int(item.get("ts", "0")) / 1000, tz=timezone.utc),
        )

    async def get_tickers(self, instType: str = "SPOT") -> List[TickerData]:
        """
        获取批量行情数据

        OKX API: GET /api/v5/market/tickers

        Args:
            instType: 产品类型 (SPOT, MARGIN, SWAP, FUTURES, OPTION)

        Returns:
            行情数据列表
        """
        params = {"instType": instType}
        raw_data = await self._request("GET", "/api/v5/market/tickers", params)

        result = []
        for item in raw_data:
            try:
                ticker = TickerData(
                    symbol=item.get("instId", ""),
                    last_price=Decimal(item.get("last", "0")),
                    bid_price=Decimal(item.get("bidPx", "0") or "0"),
                    ask_price=Decimal(item.get("askPx", "0") or "0"),
                    high_24h=Decimal(item.get("high24h", "0") or "0"),
                    low_24h=Decimal(item.get("low24h", "0") or "0"),
                    volume_24h=Decimal(item.get("vol24h", "0") or "0"),
                    timestamp=datetime.fromtimestamp(int(item.get("ts", "0")) / 1000, tz=timezone.utc),
                )
                result.append(ticker)
            except (ValueError, KeyError) as e:
                continue

        return result

    async def get_supported_symbols(self, instType: str = "SPOT") -> List[str]:
        """
        获取支持的交易对列表

        OKX API: GET /api/v5/public/instruments

        Args:
            instType: 产品类型

        Returns:
            交易对符号列表
        """
        params = {"instType": instType}
        raw_data = await self._request("GET", "/api/v5/public/instruments", params)

        return [item.get("instId", "") for item in raw_data if item.get("instId")]

    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        try:
            # 尝试获取BTC-USDT行情作为健康检查
            await self.get_ticker("BTC-USDT")
            return True
        except Exception:
            return False

    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()