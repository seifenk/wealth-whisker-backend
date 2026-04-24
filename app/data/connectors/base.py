"""
数据连接器基础抽象类
"""
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class OHLCVData(BaseModel):
    """K线数据模型"""
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class TickerData(BaseModel):
    """行情数据模型"""
    symbol: str
    last_price: Decimal
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    timestamp: datetime


class BaseConnector(ABC):
    """
    数据源连接器基类

    所有数据源连接器必须实现此接口
    """

    def __init__(self, api_url: str, api_key: Optional[str] = None,
                 api_secret: Optional[str] = None, **kwargs):
        self.api_url = api_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.extra_config = kwargs

    @abstractmethod
    async def get_ohlcv(self, symbol: str, interval: str = "1h",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取K线数据

        Args:
            symbol: 交易对符号 (如 BTC-USDT)
            interval: K线周期 (1m, 5m, 15m, 30m, 1H, 4H, 1D)
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取实时行情数据

        Args:
            symbol: 交易对符号

        Returns:
            行情数据
        """
        pass

    @abstractmethod
    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[TickerData]:
        """
        获取批量行情数据

        Args:
            symbols: 交易对符号列表，None表示获取全部

        Returns:
            行情数据列表
        """
        pass

    @abstractmethod
    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的交易对列表

        Returns:
            交易对符号列表
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        pass