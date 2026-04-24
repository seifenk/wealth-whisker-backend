"""
东方财富基金数据连接器

用于获取中国公募基金数据
通过东方财富网API获取基金净值、收益率等信息
"""
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import httpx

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData


class EastMoneyConnector(BaseConnector):
    """
    东方财富基金数据连接器

    获取中国公募基金净值数据
    """

    def __init__(self):
        super().__init__(
            api_url=settings.EASTMONEY_API_URL,
            api_key=None,
            api_secret=None,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "http://fund.eastmoney.com/",
                },
            )
        return self._client

    async def _request(self, url: str) -> dict:
        """
        发送API请求

        Args:
            url: 完整URL

        Returns:
            API响应数据
        """
        client = await self._get_client()

        try:
            response = await client.get(url)
            response.raise_for_status()
            # 尝试解析JSON
            try:
                return response.json()
            except:
                # 如果不是JSON，返回原始文本
                return {"raw_text": response.text}
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"Request error: {str(e)}")

    async def get_fund_info(self, fund_code: str) -> dict:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码 (如 000001)

        Returns:
            基金信息字典
        """
        url = f"http://fundgz.eastmoney.com/fundgz/{fund_code}.json"
        data = await self._request(url)

        if "raw_text" in data:
            # 东方财富返回jsonp格式: jsonpgz({"datas": {...}})
            text = data["raw_text"]
            match = re.search(r'jsonpgz\((.*?)\)', text)
            if match:
                import json
                return json.loads(match.group(1))

        return data.get("datas", {})

    async def get_fund_net_value(self, fund_code: str) -> TickerData:
        """
        获取基金净值

        Args:
            fund_code: 基金代码

        Returns:
            基金行情数据
        """
        info = await self.get_fund_info(fund_code)

        if not info:
            raise Exception(f"No fund data for {fund_code}")

        # 东方财富返回的字段
        # fundcode: 基金代码
        # name: 基金名称
        # jzrqv: 净值日期
        # dwjz: 单位净值
        # gsz: 估算净值
        # gszzl: 估算涨幅
        # gztime: 估算时间

        net_value = Decimal(str(info.get("dwjz", 0) or 0))
        estimated_value = Decimal(str(info.get("gsz", 0) or 0))
        change_percent = Decimal(str(info.get("gszzl", 0) or 0))

        # 使用估算净值作为当前价格（如果在交易时间内）
        last_price = estimated_value if estimated_value > 0 else net_value

        # 解析时间
        gz_time = info.get("gztime", "")
        try:
            # 格式: "2024-01-15 15:00"
            timestamp = datetime.strptime(gz_time, "%Y-%m-%d %H:%M")
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        except:
            timestamp = datetime.now(timezone.utc)

        return TickerData(
            symbol=fund_code,
            last_price=last_price,
            change_24h=change_percent,
            volume_24h=None,
            high_24h=None,
            low_24h=None,
            bid_price=None,
            ask_price=None,
            timestamp=timestamp,
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1d",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[OHLCVData]:
        """
        获取基金净值历史数据

        东方财富API获取基金净值历史

        Args:
            symbol: 基金代码
            interval: K线周期 (基金只有日线数据)
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            净值历史数据列表
        """
        # 基金净值历史API
        # http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&page=1&sdate={start}&edate={end}&per=20

        if not start_time:
            start_time = datetime.now(timezone.utc) - __import__('datetime').timedelta(days=30)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        start_str = start_time.strftime("%Y-%m-%d")
        end_str = end_time.strftime("%Y-%m-%d")

        url = f"http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={symbol}&page=1&sdate={start_str}&edate={end_str}&per={limit}"

        data = await self._request(url)

        if "raw_text" not in data:
            return []

        # 解析HTML表格数据
        text = data["raw_text"]
        ohlcv_list = []

        # 提取净值记录表格行
        # 格式: <td>2024-01-15</td><td class='tor bold'>1.2345</td><td class='tor bold red'>2.15%</td>...
        rows = re.findall(r'<tr>(.*?)</tr>', text, re.DOTALL)

        for row in rows:
            try:
                # 提取日期
                date_match = re.search(r'<td>(\d{4}-\d{2}-\d{2})</td>', row)
                if not date_match:
                    continue
                date_str = date_match.group(1)
                time = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                # 提取单位净值
                value_match = re.search(r"class='tor bold'>([\d.]+)</td>", row)
                if not value_match:
                    continue
                net_value = Decimal(value_match.group(1))

                # 基金净值没有open/high/low/volume，都用净值表示
                ohlcv = OHLCVData(
                    time=time,
                    open=net_value,
                    high=net_value,
                    low=net_value,
                    close=net_value,
                    volume=Decimal("0"),
                )
                ohlcv_list.append(ohlcv)
            except (ValueError, AttributeError):
                continue

        # 按时间正序排列
        ohlcv_list.sort(key=lambda x: x.time)
        return ohlcv_list[-limit:] if len(ohlcv_list) > limit else ohlcv_list

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取基金实时净值

        Args:
            symbol: 基金代码

        Returns:
            基金行情数据
        """
        return await self.get_fund_net_value(symbol)

    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[TickerData]:
        """
        获取批量基金净值

        Args:
            symbols: 基金代码列表

        Returns:
            基金行情数据列表
        """
        if not symbols:
            symbols = await self.get_supported_symbols()

        tickers = []
        for code in symbols:
            try:
                ticker = await self.get_fund_net_value(code)
                tickers.append(ticker)
            except Exception:
                continue

        return tickers

    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的基金代码列表

        返回热门基金代码

        Returns:
            基金代码列表
        """
        # 热门基金列表
        return [
            "000001",  # 华夏成长混合
            "000011",  # 华夏大盘精选混合
            "110022",  # 易方达消费行业股票
            "161725",  # 招商中证白酒指数
            "519674",  # 银河创新成长混合
            "000300",  # 华夏沪深300ETF联接
            "510300",  # 华泰柏瑞沪深300ETF
            "510050",  # 华夏上证50ETF
            "159915",  # 易方达深证100ETF
            "040040",  # 华安黄金易ETF联接
        ]

    async def health_check(self) -> bool:
        """
        检查连接器健康状态

        Returns:
            是否健康
        """
        try:
            await self.get_fund_net_value("000001")
            return True
        except Exception:
            return False

    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()