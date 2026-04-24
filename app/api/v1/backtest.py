"""
回测API路由
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.strategy import (
    BacktestJobCreate,
    BacktestJobResponse,
    BacktestJobListResponse,
    BacktestResultResponse,
)
from app.services.strategy_service import StrategyService
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtest", tags=["回测服务"])


@router.post("/jobs", response_model=BacktestJobResponse)
async def create_backtest_job(
    data: BacktestJobCreate,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建回测任务

    需要登录，验证策略所有权和配置
    """
    try:
        strategy_uuid = UUID(data.strategy_id)
        asset_uuids = [UUID(aid) for aid in data.asset_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的ID格式",
        )

    # 验证时间范围
    if data.end_date <= data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="结束时间必须大于开始时间",
        )

    # 构建配置
    config = {
        "asset_ids": data.asset_ids,
        "start_date": data.start_date.isoformat(),
        "end_date": data.end_date.isoformat(),
        "initial_capital": str(data.initial_capital),
        "rebalance_frequency": data.rebalance_frequency,
    }

    service = StrategyService(db)

    try:
        job = await service.create_backtest_job(
            user_id=current_user.id,
            strategy_id=strategy_uuid,
            config=config,
        )

        return BacktestJobResponse(
            id=str(job.id),
            strategy_id=str(job.strategy_id),
            status=job.status,
            config=job.config,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/jobs", response_model=BacktestJobListResponse)
async def get_backtest_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="状态过滤: pending, running, completed, failed"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户回测任务列表

    需要登录
    """
    service = StrategyService(db)
    jobs = await service.get_backtest_jobs(
        user_id=current_user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    items = [
        BacktestJobResponse(
            id=str(j.id),
            strategy_id=str(j.strategy_id),
            status=j.status,
            config=j.config,
            error_message=j.error_message,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
        )
        for j in jobs
    ]

    return BacktestJobListResponse(items=items, total=len(items))


@router.get("/jobs/{job_id}", response_model=BacktestJobResponse)
async def get_backtest_job(
    job_id: str,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取回测任务详情

    需要登录，验证所有权
    """
    try:
        uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式",
        )

    service = StrategyService(db)
    job = await service.get_backtest_job_by_id(uuid, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回测任务不存在或不属于您",
        )

    return BacktestJobResponse(
        id=str(job.id),
        strategy_id=str(job.strategy_id),
        status=job.status,
        config=job.config,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("/jobs/{job_id}/run")
async def run_backtest_job(
    job_id: str,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    执行回测任务

    需要登录，验证所有权
    注意：当前为同步执行，后续可改为异步任务队列
    """
    try:
        uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式",
        )

    # 验证所有权
    strategy_service = StrategyService(db)
    job = await strategy_service.get_backtest_job_by_id(uuid, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回测任务不存在或不属于您",
        )

    if job.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {job.status}，无法执行",
        )

    # 执行回测
    backtest_service = BacktestService(db)
    result = await backtest_service.run_backtest(uuid)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="回测执行失败",
        )

    return {
        "message": "回测完成",
        "job_id": str(uuid),
        "status": job.status,
    }


@router.get("/jobs/{job_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result(
    job_id: str,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取回测结果

    需要登录，验证所有权
    """
    try:
        uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID格式",
        )

    # 验证所有权
    strategy_service = StrategyService(db)
    job = await strategy_service.get_backtest_job_by_id(uuid, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回测任务不存在或不属于您",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {job.status}，结果尚未生成",
        )

    # 获取结果
    backtest_service = BacktestService(db)
    result = await strategy_service.get_backtest_result(uuid)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回测结果不存在",
        )

    return BacktestResultResponse(
        job_id=str(result.job_id),
        total_return=float(result.total_return) if result.total_return else None,
        annualized_return=float(result.annualized_return) if result.annualized_return else None,
        max_drawdown=float(result.max_drawdown) if result.max_drawdown else None,
        volatility=float(result.volatility) if result.volatility else None,
        sharpe_ratio=float(result.sharpe_ratio) if result.sharpe_ratio else None,
        win_rate=float(result.win_rate) if result.win_rate else None,
        total_trades=result.total_trades,
        profit_trades=result.profit_trades,
        loss_trades=result.loss_trades,
        equity_curve=result.equity_curve,
        trades=result.trades,
        metrics=result.metrics,
    )