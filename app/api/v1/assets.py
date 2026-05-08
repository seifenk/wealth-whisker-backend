"""
资产数据API路由

支持实时数据获取：
- 默认优先查数据库缓存
- force_refresh=true 强制从数据源实时获取
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.api.dependencies import get_current_user_optional, get_db
from app.models.user import User
from app.schemas.asset import (
    AssetDetailResponse,
    AssetMetricResponse,
    AssetResponse,
    DashboardResponse,
    DashboardItemResponse,
    OHLCVResponse,
    PerformanceMetricsResponse,
)
from app.schemas.enums import AssetType, Interval, RiskPreference
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["资产数据"])


@router.get("/", response_model=List[AssetResponse])
async def get_assets(
    asset_type: Optional[AssetType] = Query(None, description="资产类型"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取资产列表

    游客和登录用户均可访问
    """
    service = AssetService(db)
    try:
        assets = await service.get_assets(
            asset_type=asset_type.value if asset_type else None,
            limit=limit,
            offset=offset,
        )

        return [
            AssetResponse(
                id=str(asset.id),
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type,
                exchange=asset.exchange,
                currency=asset.currency,
                is_active=asset.is_active,
                min_lot=asset.min_lot,
                tick_size=asset.tick_size,
            )
            for asset in assets
        ]
    finally:
        await service.close_connectors()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    asset_type: Optional[AssetType] = Query(None, description="资产类型过滤"),
    risk_preference: Optional[RiskPreference] = Query(None, description="风险偏好"),
    sort_by: Optional[str] = Query(None, description="排序字段: change_24h, change_7d, sharpe_ratio, volatility, recommendation"),
    force_refresh: bool = Query(False, description="强制从数据源实时获取"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取多资产决策看板数据

    包含资产基础信息和最新指标，支持风险偏好过滤和排序

    - risk_preference: 根据用户风险偏好调整推荐策略
      - conservative: 低波动、低风险资产优先
      - balanced: 综合考量收益与风险
      - aggressive: 高收益趋势资产优先

    - sort_by: 排序方式
      - change_24h: 按24h涨跌幅排序
      - change_7d: 按7天涨跌幅排序
      - sharpe_ratio: 按夏普比率排序
      - volatility: 按波动率排序（低波动优先）
      - recommendation: 按综合推荐分数排序（默认）

    - force_refresh=false: 优先使用数据库缓存（默认）
    - force_refresh=true: 强制从数据源实时获取
    """
    # 验证排序参数
    if sort_by and sort_by not in ["change_24h", "change_7d", "sharpe_ratio", "volatility", "recommendation"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_by必须是change_24h, change_7d, sharpe_ratio, volatility或recommendation",
        )

    # 如果用户已登录且没有指定风险偏好，使用用户设置的风险偏好
    risk_pref_value = risk_preference.value if risk_preference else None
    if current_user and not risk_pref_value:
        risk_pref_value = current_user.risk_preference

    service = AssetService(db)
    try:
        dashboard_data, query_params = await service.get_dashboard_data(
            asset_type=asset_type.value if asset_type else None,
            force_refresh=force_refresh,
            risk_preference=risk_pref_value,
            sort_by=sort_by,
        )

        # 限制返回数量
        dashboard_data = dashboard_data[:limit]

        items = [DashboardItemResponse(**data) for data in dashboard_data]

        return DashboardResponse(
            items=items,
            total=len(items),
            asset_type_filter=query_params.get("asset_type_filter"),
            risk_preference=query_params.get("risk_preference"),
            sort_by=query_params.get("sort_by"),
        )
    finally:
        await service.close_connectors()


@router.get("/{asset_id}", response_model=AssetDetailResponse)
async def get_asset_detail(
    asset_id: str,
    force_refresh: bool = Query(False, description="强制实时获取指标"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取资产详情

    包含基础信息和最新指标
    """
    try:
        uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的资产ID格式",
        )

    service = AssetService(db)
    try:
        asset = await service.get_asset_by_id(uuid)

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资产不存在",
            )

        metric = await service.get_latest_metric(uuid, force_refresh=force_refresh)

        return AssetDetailResponse(
            asset=AssetResponse(
                id=str(asset.id),
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type,
                exchange=asset.exchange,
                currency=asset.currency,
                is_active=asset.is_active,
                min_lot=asset.min_lot,
                tick_size=asset.tick_size,
            ),
            latest_metric=AssetMetricResponse(
                price=metric.price if metric else None,
                change_24h=metric.change_24h if metric else None,
                change_7d=metric.change_7d if metric else None,
                volatility_30d=metric.volatility_30d if metric else None,
                sharpe_ratio=metric.sharpe_ratio if metric else None,
                risk_level=metric.risk_level if metric else None,
                trend_signal=metric.trend_signal if metric else None,
                confidence_score=metric.confidence_score if metric else None,
                calculated_at=metric.calculated_at if metric else None,
            ) if metric else None,
            latest_price=metric.price if metric else None,
        )
    finally:
        await service.close_connectors()


@router.get("/{asset_id}/ohlcv", response_model=List[OHLCVResponse])
async def get_asset_ohlcv(
    asset_id: str,
    interval: Interval = Query(Interval.HOUR_1, alias="interval", description="K线周期"),
    start_time: Optional[datetime] = Query(None, alias="startTime", description="开始时间(可选)"),
    end_time: Optional[datetime] = Query(None, alias="endTime", description="结束时间(可选，用于分页加载)"),
    limit: int = Query(300, alias="limit", ge=1, le=300, description="返回数量限制(默认300)"),
    force_refresh: bool = Query(False, alias="forceRefresh", description="强制从数据源实时获取"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取资产K线数据

    分页逻辑：
    - 首次加载：不传参数，返回最近300根K线
    - 加载更多：传 endTime（第一条K线时间），返回 endTime 之前的300根

    时间范围：
    - 不传 startTime/endTime：从当前时间往前获取 limit 根
    - 只传 endTime：从 endTime 往前获取 limit 根（用于分页）
    - 传 startTime/endTime：获取指定时间范围内的数据

    - forceRefresh=false: 优先使用数据库缓存（默认）
    - forceRefresh=true: 强制从数据源实时获取
    """
    try:
        uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的资产ID格式",
        )

    service = AssetService(db)
    try:
        asset = await service.get_asset_by_id(uuid)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资产不存在",
            )

        logger.info(f"OHLCV request: asset={asset.symbol}, interval={interval.value}, "
                   f"start={start_time}, end={end_time}, limit={limit}")

        ohlcv_list = await service.get_ohlcv(
            asset_id=uuid,
            interval=interval.value,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            force_refresh=force_refresh,
        )

        return [
            OHLCVResponse(
                time=ohlcv.time,
                open=ohlcv.open,
                high=ohlcv.high,
                low=ohlcv.low,
                close=ohlcv.close,
                volume=ohlcv.volume,
            )
            for ohlcv in ohlcv_list
        ]
    finally:
        await service.close_connectors()


@router.get("/{asset_id}/metrics", response_model=AssetMetricResponse)
async def get_asset_metrics(
    asset_id: str,
    force_refresh: bool = Query(False, description="强制实时获取"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取资产最新指标

    - force_refresh=false: 使用缓存（1小时内有效）
    - force_refresh=true: 强制实时获取
    """
    try:
        uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的资产ID格式",
        )

    service = AssetService(db)
    try:
        metric = await service.get_latest_metric(uuid, force_refresh=force_refresh)

        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="暂无指标数据，请稍后重试或使用force_refresh=true实时获取",
            )

        return AssetMetricResponse(
            price=metric.price,
            change_24h=metric.change_24h,
            change_7d=metric.change_7d,
            volatility_30d=metric.volatility_30d,
            sharpe_ratio=metric.sharpe_ratio,
            risk_level=metric.risk_level,
            trend_signal=metric.trend_signal,
            confidence_score=metric.confidence_score,
            calculated_at=metric.calculated_at,
        )
    finally:
        await service.close_connectors()


@router.get("/{asset_id}/performance", response_model=PerformanceMetricsResponse)
async def get_asset_performance(
    asset_id: str,
    days: int = Query(30, ge=7, le=365, description="计算周期天数"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取资产绩效指标

    计算收益、波动率、最大回撤、夏普比率等
    """
    try:
        uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的资产ID格式",
        )

    service = AssetService(db)
    try:
        asset = await service.get_asset_by_id(uuid)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资产不存在",
            )

        metrics = await service.calculate_performance_metrics(
            asset_id=uuid,
            days=days,
        )

        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="暂无足够历史数据进行计算",
            )

        return PerformanceMetricsResponse(**metrics)
    finally:
        await service.close_connectors()


@router.get("/realtime/{symbol}")
async def get_realtime_price(
    symbol: str,
    asset_type: Optional[AssetType] = Query(None, description="资产类型"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    直接获取实时价格（无需资产ID）

    适用于快速查询特定资产价格
    """
    service = AssetService(db)
    try:
        price = await service.get_realtime_price(symbol, asset_type.value if asset_type else None)

        if price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"无法获取 {symbol} 的实时价格",
            )

        return {
            "symbol": symbol,
            "price": float(price),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await service.close_connectors()
