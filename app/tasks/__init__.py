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
from app.tasks.research_tasks import (
    generate_research_cards_task,
    create_model_predictions_task,
    update_prediction_actuals_task,
    auto_calibrate_models_task,
    scheduled_research_generation_crypto,
    scheduled_research_generation_stock,
    scheduled_research_generation_fund,
    scheduled_research_generation_gold,
    scheduled_prediction_creation_crypto,
    scheduled_prediction_creation_stock,
    scheduled_prediction_creation_fund,
    scheduled_prediction_creation_gold,
    scheduled_actuals_update,
    scheduled_auto_calibration,
)

__all__ = [
    "celery_app",
    # 数据同步任务
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
    # 研究结论自动化任务
    "generate_research_cards_task",
    "create_model_predictions_task",
    "update_prediction_actuals_task",
    "auto_calibrate_models_task",
    "scheduled_research_generation_crypto",
    "scheduled_research_generation_stock",
    "scheduled_research_generation_fund",
    "scheduled_research_generation_gold",
    "scheduled_prediction_creation_crypto",
    "scheduled_prediction_creation_stock",
    "scheduled_prediction_creation_fund",
    "scheduled_prediction_creation_gold",
    "scheduled_actuals_update",
    "scheduled_auto_calibration",
]