"""
研究结论与模型校准 API 路由
"""
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_user_optional
from app.core.response import ResponseWrapper, UnifiedResponse
from app.models.user import User
from app.models.asset import Asset
from app.schemas.research import (
    ResearchCardResponse,
    ResearchCardListResponse,
    RiskDisclaimer,
    ModelPredictionResponse,
    PredictionListResponse,
    PredictionAccuracy,
    PredictionCreate,
    CalibrationLogResponse,
    CalibrationLogListResponse,
    ModelVersionInfo,
    ModelVersionListResponse,
    AssetAnalysisResponse
)
from app.services.research_service import (
    ResearchService,
    PredictionService,
    CalibrationService,
    DisclaimerService
)
from app.services.asset_service import get_latest_price

router = APIRouter(prefix="/research")


# ============ 研究结论卡片 ============

@router.get(
    "/cards",
    summary="获取研究结论列表",
    response_model=UnifiedResponse[ResearchCardListResponse],
    description="""
获取AI生成的资产研究结论卡片列表。

**游客可访问**，无需认证。

**返回内容**:
- `title`: 分析标题
- `conclusion`: 投资结论
- `confidence_score`: 置信度(0-1)
- `risk_level`: 风险等级(low/medium/high)
- `indicators`: 技术指标依据
- `reasoning`: 推理过程
- `suitable_for`: 适合人群标签
"""
)
async def list_research_cards(
    asset_id: Optional[str] = Query(default=None, description="资产ID（可选）"),
    risk_level: Optional[str] = Query(default=None, description="风险等级过滤: low, medium, high"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取研究结论卡片列表（游客可访问）"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            return ResponseWrapper.error(msg="无效的资产ID", code=400)

    cards = await ResearchService.get_research_cards(
        db=db,
        asset_id=asset_uuid,
        risk_level=risk_level,
        skip=skip,
        limit=limit
    )

    items = []
    for card in cards:
        card_data = ResearchCardResponse.model_validate(card)
        if card.asset:
            card_data.asset_symbol = card.asset.symbol
            card_data.asset_name = card.asset.name
        items.append(card_data)

    return ResponseWrapper.success(data=ResearchCardListResponse(items=items, total=len(items)))


@router.get(
    "/cards/{card_id}",
    summary="获取研究结论详情",
    response_model=UnifiedResponse[ResearchCardResponse],
    description="获取单个研究结论卡片的详细信息"
)
async def get_research_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取单个研究结论卡片详情"""
    try:
        card_uuid = UUID(card_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的卡片ID", code=400)

    card = await ResearchService.get_research_card(db, card_uuid)
    if not card:
        return ResponseWrapper.error(msg="研究结论不存在", code=404)

    card_data = ResearchCardResponse.model_validate(card)
    if card.asset:
        card_data.asset_symbol = card.asset.symbol
        card_data.asset_name = card.asset.name

    await DisclaimerService.log_risk_disclosure(
        db=db,
        user_id=current_user.id if current_user else None,
        page="research_card",
        disclosure_type="prediction_risk"
    )

    return ResponseWrapper.success(data=card_data)


@router.post(
    "/cards/generate/{asset_id}",
    summary="生成研究结论",
    response_model=UnifiedResponse[ResearchCardResponse],
    description="为指定资产AI生成研究结论卡片"
)
async def generate_research_card(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """为指定资产生成研究结论卡片"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的资产ID", code=400)

    card = await ResearchService.generate_research_card(db, asset_uuid)
    card_data = ResearchCardResponse.model_validate(card)
    if card.asset:
        card_data.asset_symbol = card.asset.symbol
        card_data.asset_name = card.asset.name

    return ResponseWrapper.success(data=card_data, msg="研究结论生成成功")


# ============ 模型预测 ============

@router.get(
    "/predictions",
    summary="获取预测列表",
    response_model=UnifiedResponse[PredictionListResponse],
    description="""
获取AI模型预测记录列表。

**游客可访问**，无需认证。

**返回内容**:
- `predicted_value`: 预测值
- `confidence_score`: 置信度
- `actual_value`: 实际值（校准后填入）
- `deviation`: 偏差率
- `calibration_triggered`: 是否触发校准
"""
)
async def list_predictions(
    asset_id: Optional[str] = Query(default=None, description="资产ID（可选）"),
    prediction_type: Optional[str] = Query(default=None, description="预测类型: price(价格), trend(趋势), volatility(波动率)"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取模型预测列表（游客可访问）"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            return ResponseWrapper.error(msg="无效的资产ID", code=400)

    predictions = await PredictionService.get_predictions(
        db=db,
        asset_id=asset_uuid,
        prediction_type=prediction_type,
        skip=skip,
        limit=limit
    )

    items = []
    for pred in predictions:
        pred_data = ModelPredictionResponse.model_validate(pred)
        if pred.asset:
            pred_data.asset_symbol = pred.asset.symbol
            pred_data.asset_name = pred.asset.name
        items.append(pred_data)

    return ResponseWrapper.success(data=PredictionListResponse(items=items, total=len(items)))


@router.post(
    "/predictions",
    summary="创建预测",
    response_model=UnifiedResponse[ModelPredictionResponse],
    description="创建新的AI模型预测"
)
async def create_prediction(
    data: PredictionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的模型预测"""
    try:
        asset_uuid = UUID(data.asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的资产ID", code=400)

    prediction = await PredictionService.create_prediction(
        db=db,
        asset_id=asset_uuid,
        prediction_type=data.prediction_type,
        target_date=data.target_date,
        model_version=data.model_version
    )

    pred_data = ModelPredictionResponse.model_validate(prediction)
    if prediction.asset:
        pred_data.asset_symbol = prediction.asset.symbol
        pred_data.asset_name = prediction.asset.name

    return ResponseWrapper.success(data=pred_data, msg="预测创建成功")


@router.get(
    "/predictions/{asset_id}/accuracy",
    summary="获取预测准确性",
    response_model=UnifiedResponse[PredictionAccuracy],
    description="获取指定资产的历史预测准确性统计"
)
async def get_prediction_accuracy(
    asset_id: str,
    days: int = Query(default=30, ge=7, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取指定资产的预测准确性统计"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的资产ID", code=400)

    accuracy = await PredictionService.get_prediction_accuracy(
        db=db,
        asset_id=asset_uuid,
        days=days
    )
    return ResponseWrapper.success(data=accuracy)


# ============ 模型校准日志 ============

@router.get(
    "/calibration-logs",
    summary="获取校准日志",
    response_model=UnifiedResponse[CalibrationLogListResponse],
    description="获取模型动态校准的历史日志"
)
async def list_calibration_logs(
    asset_id: Optional[str] = Query(default=None, description="资产ID"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取模型校准日志列表"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            return ResponseWrapper.error(msg="无效的资产ID", code=400)

    logs = await CalibrationService.get_calibration_logs(
        db=db,
        asset_id=asset_uuid,
        skip=skip,
        limit=limit
    )

    items = []
    for log in logs:
        log_data = CalibrationLogResponse.model_validate(log)
        if log.asset:
            log_data.asset_symbol = log.asset.symbol
            log_data.asset_name = log.asset.name
        items.append(log_data)

    return ResponseWrapper.success(data=CalibrationLogListResponse(items=items, total=len(items)))


@router.post(
    "/calibration/{asset_id}",
    summary="触发模型校准",
    response_model=UnifiedResponse[CalibrationLogResponse],
    description="手动触发对指定资产的模型校准"
)
async def trigger_calibration(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发模型校准"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的资产ID", code=400)

    log = await CalibrationService.check_and_calibrate(db, asset_uuid)
    if not log:
        return ResponseWrapper.success(data=None, msg="当前无需校准")

    log_data = CalibrationLogResponse.model_validate(log)
    if log.asset:
        log_data.asset_symbol = log.asset.symbol
        log_data.asset_name = log.asset.name

    return ResponseWrapper.success(data=log_data, msg="模型校准完成")


# ============ 模型版本管理 ============

@router.get(
    "/model-versions",
    summary="获取模型版本列表",
    response_model=UnifiedResponse[ModelVersionListResponse],
    description="获取当前使用的模型版本信息"
)
async def list_model_versions(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取模型版本列表"""
    versions = await CalibrationService.get_model_versions(db)
    items = [ModelVersionInfo(**v) for v in versions]
    return ResponseWrapper.success(data=ModelVersionListResponse(items=items, total=len(items)))


# ============ 综合分析 ============

@router.get(
    "/analysis/{asset_id}",
    summary="获取资产综合分析",
    response_model=UnifiedResponse[AssetAnalysisResponse],
    description="""
获取资产的综合分析报告，包含：
- 当前价格
- 研究结论卡片
- 最新预测
- 预测准确性统计
- 风险免责声明
"""
)
async def get_asset_analysis(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取资产的综合分析（包含研究结论、预测、准确性等）"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的资产ID", code=400)

    asset = await db.execute(select(Asset).where(Asset.id == asset_uuid))
    asset = asset.scalar_one_or_none()
    if not asset:
        return ResponseWrapper.error(msg="资产不存在", code=404)

    current_price = await get_latest_price(db, asset_uuid)

    cards = await ResearchService.get_research_cards(db, asset_id=asset_uuid, limit=1)
    research_card = None
    if cards:
        card_data = ResearchCardResponse.model_validate(cards[0])
        if cards[0].asset:
            card_data.asset_symbol = cards[0].asset.symbol
            card_data.asset_name = cards[0].asset.name
        research_card = card_data

    predictions = await PredictionService.get_predictions(db, asset_id=asset_uuid, limit=1)
    latest_prediction = None
    if predictions:
        pred_data = ModelPredictionResponse.model_validate(predictions[0])
        if predictions[0].asset:
            pred_data.asset_symbol = predictions[0].asset.symbol
            pred_data.asset_name = predictions[0].asset.name
        latest_prediction = pred_data

    accuracy = await PredictionService.get_prediction_accuracy(db, asset_uuid, days=30)

    disclaimer = await DisclaimerService.get_active_disclaimer(db)
    risk_disclaimer = None
    if disclaimer:
        risk_disclaimer = RiskDisclaimer(
            content=disclaimer.content,
            version=disclaimer.version,
            accepted=False
        )
    else:
        risk_disclaimer = RiskDisclaimer(
            content="本预测基于算法模型动态生成，不构成任何实质性投资建议。历史表现不代表未来，投资有风险，决策需谨慎。",
            version="default",
            accepted=False
        )

    await DisclaimerService.log_risk_disclosure(
        db=db,
        user_id=current_user.id if current_user else None,
        page="asset_analysis",
        disclosure_type="comprehensive_risk"
    )

    return ResponseWrapper.success(
        data=AssetAnalysisResponse(
            asset_id=str(asset_uuid),
            asset_symbol=asset.symbol,
            asset_name=asset.name,
            current_price=current_price,
            research_card=research_card,
            latest_prediction=latest_prediction,
            prediction_accuracy=PredictionAccuracy(**accuracy),
            disclaimer=risk_disclaimer
        )
    )


# ============ 免责声明 ============

@router.get(
    "/disclaimer",
    summary="获取免责声明",
    response_model=UnifiedResponse[RiskDisclaimer],
    description="获取当前有效的风险免责声明"
)
async def get_disclaimer(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取当前有效的免责声明"""
    disclaimer = await DisclaimerService.get_active_disclaimer(db)
    if not disclaimer:
        return ResponseWrapper.success(
            data=RiskDisclaimer(
                content="本平台提供的所有分析、预测和建议均基于算法模型动态生成，不构成任何实质性投资建议。历史表现不代表未来收益，投资有风险，决策需谨慎。用户应根据自身情况独立判断，并承担相应风险。",
                version="default",
                accepted=False
            )
        )

    return ResponseWrapper.success(
        data=RiskDisclaimer(
            content=disclaimer.content,
            version=disclaimer.version,
            accepted=False
        )
    )