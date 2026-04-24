"""
指标计算任务模块

占位文件 - Phase 3实现
"""
from celery import shared_task


@shared_task(name="calculate_metrics")
def calculate_metrics_task(asset_id: str):
    """
    执行指标计算任务（占位）
    """
    # TODO: Phase 3实现
    return {"status": "pending", "message": "Metrics calculation will be implemented in Phase 3"}