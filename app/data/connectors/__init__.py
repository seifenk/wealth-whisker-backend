"""
数据连接器模块

提供统一的数据源接口，支持实盘交易：
- OKX: 使用ccxt统一交易所接口
- Yahoo Finance: 使用yfinance库获取股票/黄金数据
- 东方财富: HTTP请求获取中国公募基金数据
"""
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData
from app.data.connectors.okx_connector import OKXConnector
from app.data.connectors.yahoo_connector import YahooFinanceConnector
from app.data.connectors.gold_connector import GoldConnector
from app.data.connectors.eastmoney_connector import EastMoneyConnector

__all__ = [
    "BaseConnector",
    "OHLCVData",
    "TickerData",
    "OKXConnector",
    "YahooFinanceConnector",
    "GoldConnector",
    "EastMoneyConnector",
]