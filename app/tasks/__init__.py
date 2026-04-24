"""
Celery 异步任务模块索引
"""
from app.core.celery_app import celery_app
from app.tasks.data_sync import (
    sync_crypto_data_task,
    sync_crypto_tickers_task,
    scheduled_crypto_sync,
    scheduled_crypto_tickers_sync,
    sync_stock_data_task,
    sync_stock_tickers_task,
    scheduled_stock_sync,
    sync_gold_data_task,
    scheduled_gold_sync,
    sync_fund_data_task,
    scheduled_fund_sync,
    sync_all_data_task,
)

__all__ = [
    "celery_app",
    "sync_crypto_data_task",
    "sync_crypto_tickers_task",
    "scheduled_crypto_sync",
    "scheduled_crypto_tickers_sync",
    "sync_stock_data_task",
    "sync_stock_tickers_task",
    "scheduled_stock_sync",
    "sync_gold_data_task",
    "scheduled_gold_sync",
    "sync_fund_data_task",
    "scheduled_fund_sync",
    "sync_all_data_task",
]