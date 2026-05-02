"""
Celery Worker 应用配置
"""
from celery import Celery
from celery.schedules import crontab

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
        "app.tasks.research_tasks.*": {"rate_limit": "5/m"},
    },

    # Worker配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # 定时任务调度（Beat Schedule）
    beat_schedule={
        # ===== 加密货币任务（4小时滑动窗口） =====
        # 每4小时生成加密货币研究结论
        "crypto-research-generation": {
            "task": "scheduled_research_generation_crypto",
            "schedule": crontab(hour="*/4", minute=0),  # 0:00, 4:00, 8:00, 12:00, 16:00, 20:00
        },
        # 每4小时创建加密货币预测（研究生成后15分钟）
        "crypto-prediction-creation": {
            "task": "scheduled_prediction_creation_crypto",
            "schedule": crontab(hour="*/4", minute=15),
        },
        # 每4小时同步加密货币新闻
        "crypto-news-sync": {
            "task": "scheduled_crypto_news_sync",
            "schedule": crontab(hour="*/4", minute=30),
        },

        # ===== 股票任务（T+1盘后机制） =====
        # 每日17:00 UTC生成股票研究结论（美股收盘后）
        "stock-research-generation": {
            "task": "scheduled_research_generation_stock",
            "schedule": crontab(hour=17, minute=0),  # UTC 17:00 = 北京时间次日1:00
        },
        # 每日17:15 UTC创建股票预测
        "stock-prediction-creation": {
            "task": "scheduled_prediction_creation_stock",
            "schedule": crontab(hour=17, minute=15),
        },
        # 每日17:30 UTC同步股票新闻
        "stock-news-sync": {
            "task": "scheduled_stock_news_sync",
            "schedule": crontab(hour=17, minute=30),
        },

        # ===== 基金任务（A股收盘后） =====
        # 每日15:30 北京时间生成基金研究结论
        "fund-research-generation": {
            "task": "scheduled_research_generation_fund",
            "schedule": crontab(hour=7, minute=30),  # UTC 07:30 = 北京时间15:30
        },
        # 每日15:45 北京时间创建基金预测
        "fund-prediction-creation": {
            "task": "scheduled_prediction_creation_fund",
            "schedule": crontab(hour=7, minute=45),
        },
        # 每日15:55 北京时间同步基金新闻
        "fund-news-sync": {
            "task": "scheduled_fund_news_sync",
            "schedule": crontab(hour=7, minute=55),
        },

        # ===== 黄金任务 =====
        # 每日17:05 UTC生成黄金研究结论
        "gold-research-generation": {
            "task": "scheduled_research_generation_gold",
            "schedule": crontab(hour=17, minute=5),
        },
        # 每日17:20 UTC创建黄金预测
        "gold-prediction-creation": {
            "task": "scheduled_prediction_creation_gold",
            "schedule": crontab(hour=17, minute=20),
        },
        # 每日17:35 UTC同步黄金新闻
        "gold-news-sync": {
            "task": "scheduled_gold_news_sync",
            "schedule": crontab(hour=17, minute=35),
        },

        # ===== 通用任务（每日执行） =====
        # 每日凌晨更新预测实际值
        "prediction-actuals-update": {
            "task": "scheduled_actuals_update",
            "schedule": crontab(hour=0, minute=30),  # UTC 00:30
        },
        # 每日凌晨自动校准（实际值更新后30分钟）
        "auto-calibration": {
            "task": "scheduled_auto_calibration",
            "schedule": crontab(hour=1, minute=0),  # UTC 01:00
        },
        # 每日凌晨同步宏观经济新闻
        "macro-news-sync": {
            "task": "scheduled_macro_news_sync",
            "schedule": crontab(hour=1, minute=30),
        },
        # 每日凌晨聚合情感快照
        "sentiment-aggregation": {
            "task": "scheduled_sentiment_aggregation",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)

# 自动发现任务模块
celery_app.autodiscover_tasks([
    "app.tasks.data_sync",
    "app.tasks.backtest_worker",
    "app.tasks.model_calibration",
    "app.tasks.metrics_calculation",
    "app.tasks.research_tasks",  # 研究结论自动化任务
    "app.tasks.news_sync",       # 新闻数据同步任务
])