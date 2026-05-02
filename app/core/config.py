"""
应用核心配置
"""
from functools import lru_cache
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略.env中未定义的字段
    )

    # Application
    APP_NAME: str = "WealthWhisker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # API
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7天 = 7 * 24 * 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wealthwhisker"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/wealthwhisker"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Cache settings
    CACHE_ENABLED: bool = True
    CACHE_REALTIME_PRICE_TTL: int = 60  # 实时价格缓存60秒
    CACHE_ASSET_LIST_TTL: int = 600  # 资产列表缓存10分钟
    CACHE_DASHBOARD_TTL: int = 120  # Dashboard缓存2分钟
    CACHE_METRIC_TTL: int = 300  # 指标缓存5分钟

    # External APIs
    OKX_API_KEY: Optional[str] = None
    OKX_API_SECRET: Optional[str] = None
    OKX_API_PASSPHRASE: Optional[str] = None
    OKX_API_URL: str = "https://www.okx.com"

    # Yahoo Finance (免费，无需API密钥)
    YAHOO_FINANCE_ENABLED: bool = True

    # Alpha Vantage (需要API密钥，备用)
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_URL: str = "https://www.alphavantage.co"

    # 东方财富/天天基金 (中国基金数据)
    EASTMONEY_API_URL: str = "http://fund.eastmoney.com"
    EASTMONEY_ENABLED: bool = True

    # Metals API (黄金贵金属数据)
    METALS_API_KEY: Optional[str] = None
    METALS_API_URL: str = "https://api.metals.live"

    # News APIs (新闻数据源)
    CRYPTOPANIC_API_KEY: Optional[str] = None  # CryptoPanic加密货币新闻API
    NEWSAPI_KEY: Optional[str] = None          # NewsAPI.org通用新闻API

    # Data Sync
    DATA_SYNC_INTERVAL_MINUTES: int = 60
    CRYPTO_SYNC_INTERVAL_MINUTES: int = 15

    # Model Calibration
    CALIBRATION_THRESHOLD: float = 0.05
    CRYPTO_CALIBRATION_INTERVAL_HOURS: int = 4
    STOCK_CALIBRATION_SCHEDULE: str = "17:00"

    # LLM Integration
    LLM_API_BASE: Optional[str] = None  # API基础URL（如https://api.openai.com/v1）
    LLM_API_KEY: Optional[str] = None   # API密钥
    LLM_MODEL: str = "gpt-4o-mini"      # 模型名称（默认使用轻量模型）
    LLM_TIMEOUT: int = 30               # 请求超时（秒）
    LLM_MAX_TOKENS: int = 1000          # 最大输出token数
    LLM_TEMPERATURE: float = 0.7        # 温度参数（创意性）
    LLM_ENABLED: bool = False           # 是否启用LLM功能（默认关闭）

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """解析 CORS_ORIGINS，支持逗号分隔的字符串"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: str = "logs/app.log"


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例"""
    return Settings()


settings = get_settings()