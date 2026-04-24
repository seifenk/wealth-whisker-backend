"""
K线时间间隔定义

OKX标准格式: 小写m代表分钟，大写H/D/W/M代表小时/天/周/月
支持的间隔: ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W', '1M']
"""

# 标准时间间隔（OKX格式，前端使用）
# 规则: 小写m=分钟，大写H=小时，大写D=天，大写W=周，大写M=月
STANDARD_INTERVALS = ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W', '1M']

# 时间间隔秒数映射
INTERVAL_SECONDS = {
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1H': 3600,
    '4H': 14400,
    '1D': 86400,
    '1W': 604800,
    '1M': 2592000,  # 约30天
}

# 间隔显示名称
INTERVAL_DISPLAY_NAMES = {
    '1m': '1分钟',
    '5m': '5分钟',
    '15m': '15分钟',
    '30m': '30分钟',
    '1H': '1小时',
    '4H': '4小时',
    '1D': '1天',
    '1W': '1周',
    '1M': '1月',
}


def normalize_interval(interval: str) -> str:
    """
    标准化时间间隔格式（OKX格式）

    小写m代表分钟，大写H/D/W/M代表小时/天/周/月

    Args:
        interval: 原始间隔格式

    Returns:
        标准化的OKX格式
    """
    # 统一处理
    interval = interval.strip()

    # 已是标准格式，直接返回
    if interval in STANDARD_INTERVALS:
        return interval

    # 处理常见变体格式
    # 小写h/d/w转大写
    if interval.lower().endswith('h'):
        return interval.upper().replace('H', 'H')
    if interval.lower().endswith('d'):
        return interval.upper().replace('D', 'D')
    if interval.lower().endswith('w'):
        return interval.upper().replace('W', 'W')

    # m保持小写
    if interval.upper().endswith('M') and not interval.endswith('M'):
        # 如果是大写M但不是月（可能是分钟），转小写
        base = interval[:-1]
        if base.isdigit() and int(base) <= 60:
            return interval.lower()  # 1M -> 1m (分钟)

    # 处理60m -> 1H
    if interval == '60m' or interval == '60M':
        return '1H'

    return interval


def to_ccxt_interval(interval: str) -> str:
    """
    转换为ccxt格式

    ccxt使用全小写: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M

    Args:
        interval: 标准OKX间隔格式

    Returns:
        ccxt格式（全小写，月保持1M）
    """
    normalized = normalize_interval(interval)

    # ccxt格式：全部小写，但月用1M
    mapping = {
        '1H': '1h',
        '4H': '4h',
        '1D': '1d',
        '1W': '1w',
        '1M': '1M',  # 月保持大写M
    }

    return mapping.get(normalized, normalized)


def to_yfinance_interval(interval: str) -> str:
    """
    转换为yfinance格式

    yfinance使用: 1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo

    Args:
        interval: 标准OKX间隔格式

    Returns:
        yfinance格式
    """
    normalized = normalize_interval(interval)

    mapping = {
        '1H': '60m',
        '4H': '4h',  # yfinance不支持4H，用4h尝试
        '1D': '1d',
        '1W': '1wk',
        '1M': '1mo',
    }

    return mapping.get(normalized, normalized)


def is_valid_interval(interval: str) -> bool:
    """
    检查间隔是否有效

    Args:
        interval: 时间间隔

    Returns:
        是否是有效间隔
    """
    normalized = normalize_interval(interval)
    return normalized in STANDARD_INTERVALS