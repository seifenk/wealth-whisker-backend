"""
东方财富基金数据连接器

用于获取中国公募基金数据
通过天天基金页面数据接口(pingzhongdata)获取基金净值、收益率等信息

注意：东方财富无官方Python SDK，使用HTTP请求获取数据。
旧接口 fundgz.eastmoney.com(302重定向失效) 与 api.fund.eastmoney.com/F10DataApi.aspx(404)
均已废弃，现改用基金详情页自带的 pingzhongdata JS 数据源，一次请求即可拿到全量历史净值。
"""
import re
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.data.connectors.base import BaseConnector, OHLCVData, TickerData
from app.data.constants import normalize_interval


# 热门基金列表
FUND_SYMBOLS = [
    ("000001", "000001", "华夏成长混合", "fund", "EastMoney"),
    ("000011", "000011", "华夏大盘精选", "fund", "EastMoney"),
    ("110022", "110022", "易方达消费行业", "fund", "EastMoney"),
    ("161725", "161725", "招商中证白酒", "fund", "EastMoney"),
    ("519674", "519674", "银河创新成长", "fund", "EastMoney"),
    ("510300", "510300", "华泰柏瑞沪深300ETF", "fund", "EastMoney"),
    ("510050", "510050", "华夏上证50ETF", "fund", "EastMoney"),
    ("159915", "159915", "易方达深证100ETF", "fund", "EastMoney"),
]


class EastMoneyConnector(BaseConnector):
    """
    东方财富基金数据连接器

    获取中国公募基金净值数据
    使用天天基金 pingzhongdata 页面数据接口（无官方SDK）
    """

    def __init__(self):
        super().__init__(
            api_url=settings.EASTMONEY_API_URL,
            api_key=None,
            api_secret=None,
        )
        self._client: Optional[httpx.AsyncClient] = None
        # 天天基金页面数据接口地址
        self._api_base = settings.EASTMONEY_PINGZHONG_API_URL

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=settings.API_REQUEST_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://fund.eastmoney.com/",
                    "Accept": "*/*",
                },
                follow_redirects=True,
            )
        return self._client

    async def _request_html(self, url: str) -> str:
        """
        发送API请求获取JS/HTML内容

        Args:
            url: 完整URL

        Returns:
            JS/HTML文本
        """
        client = await self._get_client()

        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code}")
            raise Exception(f"HTTP错误: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"请求错误: {str(e)}")

    async def _fetch_pingzhong_data(self, fund_code: str) -> dict:
        """
        获取天天基金页面数据(全量历史净值)

        数据源: https://fund.eastmoney.com/pingzhongdata/{code}.js
        返回JS变量:
        - fS_name: 基金名称
        - Data_netWorthTrend: 单位净值趋势 [{x: 毫秒时间戳, y: 单位净值, equityReturn: 日涨幅%}]
        - Data_ACWorthTrend: 累计净值趋势(格式同netWorthTrend)

        Args:
            fund_code: 基金代码

        Returns:
            解析后的数据字典
        """
        # 加时间戳破缓存
        url = f"{self._api_base}/{fund_code}.js?v={int(datetime.now(timezone.utc).timestamp() * 1000)}"
        text = await self._request_html(url)

        result = {
            "name": "",
            "net_worth_trend": [],
            "ac_worth_trend": [],
        }

        # 提取基金名称
        name_match = re.search(r'var fS_name\s*=\s*"([^"]+)"', text)
        if name_match:
            result["name"] = name_match.group(1)

        # 提取单位净值趋势
        net_match = re.search(
            r'Data_netWorthTrend\s*=\s*(\[[\s\S]*?\]);', text
        )
        if net_match:
            try:
                result["net_worth_trend"] = json.loads(net_match.group(1))
            except json.JSONDecodeError as e:
                logger.error(f"解析净产值趋势失败 {fund_code}: {e}")

        # 提取累计净值趋势
        ac_match = re.search(
            r'Data_ACWorthTrend\s*=\s*(\[[\s\S]*?\]);', text
        )
        if ac_match:
            try:
                result["ac_worth_trend"] = json.loads(ac_match.group(1))
            except json.JSONDecodeError as e:
                logger.error(f"解析累计净值趋势失败 {fund_code}: {e}")

        logger.info(
            f"EastMoney pingzhongdata: {fund_code} {result['name']}, "
            f"net_worth={len(result['net_worth_trend'])} records"
        )
        return result

    async def get_fund_info(self, fund_code: str) -> dict:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码

        Returns:
            基金信息字典
        """
        data = await self._fetch_pingzhong_data(fund_code)

        trend = data.get("net_worth_trend") or []
        if not trend:
            return {}

        # 最新净值记录
        latest = trend[-1]
        latest_ts = int(latest.get("x") or 0)
        latest_date = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)

        # 净值日期字符串(北京时间，用于展示)
        gztime = (latest_date + timedelta(hours=8)).strftime("%Y-%m-%d")

        return {
            "fundcode": fund_code,
            "name": data.get("name", ""),
            "dwjz": Decimal(str(latest.get("y") or 0)),       # 单位净值
            "jzzzl": Decimal(str(latest.get("equityReturn") or 0)),  # 日增长率(%)
            "gztime": gztime,
            "net_worth_trend": trend,
            "ac_worth_trend": data.get("ac_worth_trend") or [],
        }

    async def get_fund_net_value(self, fund_code: str) -> TickerData:
        """
        获取基金最新净值

        Args:
            fund_code: 基金代码

        Returns:
            基金行情数据
        """
        info = await self.get_fund_info(fund_code)

        if not info:
            raise Exception(f"未找到基金数据: {fund_code}")

        net_value = info["dwjz"]
        change_percent = info["jzzzl"]

        # 解析时间
        try:
            timestamp = datetime.strptime(info["gztime"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)

        return TickerData(
            symbol=fund_code,
            last_price=net_value,
            change_24h=change_percent,
            volume_24h=None,
            high_24h=net_value,
            low_24h=net_value,
            bid_price=net_value,
            ask_price=net_value,
            timestamp=timestamp,
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1d",
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 300) -> List[OHLCVData]:
        """
        获取基金净值历史数据

        使用全量历史净值数据，在本地过滤时间和条数。

        分页逻辑：
        - 不传时间参数：返回最近 limit 条数据
        - 只传 end_time：从 end_time 往前获取 limit 条（分页加载）
        - 传 start_time/end_time：获取时间范围内的数据

        注意：基金净值只有日线数据，其他interval会被标准化为1D

        Args:
            symbol: 基金代码
            interval: K线周期（基金只有日线数据，强制使用1D）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选，用于分页）
            limit: 返回数量限制（默认300）

        Returns:
            净值历史数据列表（时间正序：从旧到新）
        """
        # 标准化interval，基金净值只有日线数据
        normalized_interval = normalize_interval(interval)
        if normalized_interval != '1D':
            logger.info(f"基金数据只支持日线，将 '{interval}' 标准化为 '1D'")

        # 获取全量历史净值
        info = await self.get_fund_info(symbol)
        trend = info.get("net_worth_trend") or []

        ohlcv_list = []
        for item in trend:
            ts = int(item.get("x") or 0)
            if ts <= 0:
                continue
            time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

            # 时间过滤
            if start_time and time < start_time:
                continue
            if end_time and time >= end_time:
                continue

            net_value = Decimal(str(item.get("y") or 0))

            # 基金净值只有收盘价，没有开高低量
            ohlcv_list.append(OHLCVData(
                time=time,
                open=net_value,
                high=net_value,
                low=net_value,
                close=net_value,
                volume=Decimal("0"),
            ))

        # 按时间正序排列
        ohlcv_list.sort(key=lambda x: x.time)

        # 分页：只传 end_time 或首次加载时，取最后 limit 条
        if len(ohlcv_list) > limit:
            # 若是时间范围查询且范围较大，保持范围内全部（由上层limit控制）
            if start_time and end_time:
                pass
            else:
                ohlcv_list = ohlcv_list[-limit:]

        logger.info(f"EastMoney OHLCV returned: {len(ohlcv_list)} candles")
        return ohlcv_list

    async def get_ticker(self, symbol: str) -> TickerData:
        """
        获取基金最新净值

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
            symbols = [s[0] for s in FUND_SYMBOLS]

        tickers = []
        for code in symbols:
            try:
                ticker = await self.get_fund_net_value(code)
                tickers.append(ticker)
            except Exception as e:
                logger.warning(f"获取基金 {code} 失败: {e}")
                continue

        return tickers

    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的基金代码列表

        Returns:
            基金代码列表
        """
        return [s[0] for s in FUND_SYMBOLS]

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
            self._client = None

    # ==================== 基金特有功能 ====================

    async def get_fund_detail(self, fund_code: str) -> dict:
        """
        获取基金详细信息

        Args:
            fund_code: 基金代码

        Returns:
            基金详细信息
        """
        info = await self.get_fund_info(fund_code)

        if not info:
            return {
                'code': fund_code,
                'name': '',
                'type': '',
                'net_value': 0,
                'estimated_value': 0,
                'change_percent': 0,
                'update_time': '',
            }

        name = info.get('name', '')

        return {
            'code': fund_code,
            'name': name,
            'type': '混合型' if '混合' in name else '股票型',
            'net_value': float(info.get('dwjz', 0) or 0),
            'estimated_value': float(info.get('dwjz', 0) or 0),
            'change_percent': float(info.get('jzzzl', 0) or 0),
            'update_time': info.get('gztime', ''),
        }

    async def search_fund(self, keyword: str) -> List[dict]:
        """
        搜索基金（预留接口）

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的基金列表
        """
        # 东方财富搜索API需要复杂实现，这里返回预定义列表中匹配的基金
        results = []
        for code, _, name, _, _ in FUND_SYMBOLS:
            if keyword.lower() in name.lower() or keyword in code:
                results.append({
                    'code': code,
                    'name': name,
                })
        return results