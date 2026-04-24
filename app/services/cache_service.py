"""
Redis缓存服务

提供统一的缓存接口，支持：
- 实时价格短期缓存
- 资产列表缓存
- Dashboard数据缓存
"""
import json
from datetime import datetime, timezone
from typing import Optional, Any
from decimal import Decimal

import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class CacheService:
    """Redis缓存服务"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._enabled = settings.CACHE_ENABLED

    async def _get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self):
        """关闭Redis连接"""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值（JSON解析后）
        """
        if not self._enabled:
            return None

        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        if not self._enabled:
            return False

        try:
            client = await self._get_client()
            await client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._enabled:
            return False

        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配的缓存"""
        if not self._enabled:
            return 0

        try:
            client = await self._get_client()
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error for {pattern}: {e}")
            return 0

    # ==================== 缓存键生成 ====================

    @staticmethod
    def realtime_price_key(symbol: str) -> str:
        """实时价格缓存键"""
        return f"price:realtime:{symbol}"

    @staticmethod
    def asset_list_key(asset_type: Optional[str] = None) -> str:
        """资产列表缓存键"""
        return f"assets:list:{asset_type or 'all'}"

    @staticmethod
    def dashboard_key(asset_type: Optional[str] = None) -> str:
        """Dashboard缓存键"""
        return f"dashboard:{asset_type or 'all'}"

    @staticmethod
    def metric_key(asset_id: str) -> str:
        """资产指标缓存键"""
        return f"metric:{asset_id}"

    @staticmethod
    def ohlcv_key(asset_id: str, interval: str) -> str:
        """K线数据缓存键"""
        return f"ohlcv:{asset_id}:{interval}"


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """获取缓存服务实例"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


async def close_cache_service():
    """关闭缓存服务"""
    global _cache_service
    if _cache_service:
        await _cache_service.close()
        _cache_service = None