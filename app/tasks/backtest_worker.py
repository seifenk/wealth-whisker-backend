"""
回测计算Worker任务模块

占位文件 - Phase 3实现
"""
from celery import shared_task


@shared_task(name="run_backtest")
def run_backtest_task(strategy_id: str, params: dict):
    """
    执行回测任务（占位）
    """
    # TODO: Phase 3实现
    return {"status": "pending", "message": "Backtest feature will be implemented in Phase 3"}