"""
Celery Worker 应用配置
"""
from celery import Celery

from app.core.config import settings

# 创建Celery应用
celery_app = Celery(
    "wealthwhisker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="UTC",
    enable_utc=True,

    # 任务结果过期时间
    result_expires=3600,

    # 任务限流
    task_annotations={
        "app.tasks.data_sync.*": {"rate_limit": "10/m"},
    },

    # Worker配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 自动发现任务模块
celery_app.autodiscover_tasks([
    "app.tasks.data_sync",
    "app.tasks.backtest_worker",
    "app.tasks.model_calibration",
    "app.tasks.metrics_calculation",
])