"""
研究结论与模型校准 API 路由（自动化版本）

前端只需查询结果，后台自动执行生成和校准
"""
from datetime import datetime, date
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.asset import Asset
from app.schemas.research import (
    ResearchCardResponse,
    ResearchCardListResponse,
    RiskDisclaimer,
    ModelPredictionResponse,
    PredictionListResponse,
    PredictionAccuracy,
    CalibrationLogResponse,
    CalibrationLogListResponse,
    ModelVersionInfo,
    ModelVersionListResponse,
    AssetAnalysisResponse
)
from app.schemas.enums import PredictionType
from app.services.research_service import (
    ResearchService,
    PredictionService,
    CalibrationService,
    DisclaimerService
)
from app.services.asset_service import get_latest_price

router = APIRouter(prefix="/research")


# ============ 研究结论卡片（查询接口） ============

@router.get(
    "/cards",
    summary="获取研究结论列表",
    response_model=ResearchCardListResponse,
    description="获取AI生成的资产研究结论卡片列表（游客可访问）"
)
async def list_research_cards(
    asset_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取研究结论卡片列表"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的资产ID")

    cards = await ResearchService.get_research_cards(
        db=db, asset_id=asset_uuid, risk_level=risk_level, skip=skip, limit=limit
    )

    items = []
    for card in cards:
        card_dict = ResearchCardResponse.model_validate(card).model_dump()
        if card.asset:
            card_dict["asset_symbol"] = card.asset.symbol
            card_dict["asset_name"] = card.asset.name
        items.append(ResearchCardResponse(**card_dict))

    return ResearchCardListResponse(items=items, total=len(items))


@router.get(
    "/cards/{card_id}",
    summary="获取研究结论详情",
    response_model=ResearchCardResponse,
    description="获取单个研究结论卡片详情"
)
async def get_research_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取研究结论详情"""
    try:
        card_uuid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的卡片ID")

    card = await ResearchService.get_research_card(db, card_uuid)
    if not card:
        raise HTTPException(status_code=404, detail="研究结论不存在")

    card_dict = ResearchCardResponse.model_validate(card).model_dump()
    if card.asset:
        card_dict["asset_symbol"] = card.asset.symbol
        card_dict["asset_name"] = card.asset.name

    await DisclaimerService.log_risk_disclosure(
        db=db, user_id=current_user.id if current_user else None,
        page="research_card", disclosure_type="prediction_risk"
    )

    return ResearchCardResponse(**card_dict)


# ============ 模型预测（查询接口） ============

@router.get(
    "/predictions",
    summary="获取预测列表",
    response_model=PredictionListResponse,
    description="获取AI模型预测记录（游客可访问）"
)
async def list_predictions(
    asset_id: Optional[str] = Query(default=None),
    prediction_type: Optional[PredictionType] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取预测列表"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的资产ID")

    predictions = await PredictionService.get_predictions(
        db=db, asset_id=asset_uuid, prediction_type=prediction_type.value if prediction_type else None, skip=skip, limit=limit
    )

    items = []
    for pred in predictions:
        pred_dict = ModelPredictionResponse.model_validate(pred).model_dump()
        if pred.asset:
            pred_dict["asset_symbol"] = pred.asset.symbol
            pred_dict["asset_name"] = pred.asset.name
        items.append(ModelPredictionResponse(**pred_dict))

    return PredictionListResponse(items=items, total=len(items))


@router.get(
    "/predictions/{asset_id}/accuracy",
    summary="获取预测准确性",
    response_model=PredictionAccuracy,
    description="获取预测准确性统计"
)
async def get_prediction_accuracy(
    asset_id: str,
    days: int = Query(default=30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取预测准确性"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的资产ID")

    accuracy = await PredictionService.get_prediction_accuracy(db, asset_uuid, days)
    return PredictionAccuracy(**accuracy)


# ============ 校准日志 ============

@router.get(
    "/calibration-logs",
    summary="获取校准日志",
    response_model=CalibrationLogListResponse,
    description="获取模型校准日志"
)
async def list_calibration_logs(
    asset_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取校准日志"""
    asset_uuid = None
    if asset_id:
        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的资产ID")

    logs = await CalibrationService.get_calibration_logs(
        db=db, asset_id=asset_uuid, skip=skip, limit=limit
    )

    items = []
    for log in logs:
        log_dict = CalibrationLogResponse.model_validate(log).model_dump()
        if log.asset:
            log_dict["asset_symbol"] = log.asset.symbol
            log_dict["asset_name"] = log.asset.name
        items.append(CalibrationLogResponse(**log_dict))

    return CalibrationLogListResponse(items=items, total=len(items))


# ============ 模型版本 ============

@router.get(
    "/model-versions",
    summary="获取模型版本",
    response_model=ModelVersionListResponse,
    description="获取模型版本信息"
)
async def list_model_versions(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取模型版本"""
    versions = await CalibrationService.get_model_versions(db)
    items = [ModelVersionInfo(**v) for v in versions]
    return ModelVersionListResponse(items=items, total=len(items))


# ============ 综合分析 ============

@router.get(
    "/analysis/{asset_id}",
    summary="获取资产综合分析",
    response_model=AssetAnalysisResponse,
    description="获取资产综合分析报告"
)
async def get_asset_analysis(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取资产综合分析"""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的资产ID")

    asset = await db.execute(select(Asset).where(Asset.id == asset_uuid))
    asset = asset.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    current_price = await get_latest_price(db, asset_uuid)

    cards = await ResearchService.get_research_cards(db, asset_id=asset_uuid, limit=1)
    research_card = None
    if cards:
        card_dict = ResearchCardResponse.model_validate(cards[0]).model_dump()
        if cards[0].asset:
            card_dict["asset_symbol"] = cards[0].asset.symbol
            card_dict["asset_name"] = cards[0].asset.name
        research_card = ResearchCardResponse(**card_dict)

    predictions = await PredictionService.get_predictions(db, asset_id=asset_uuid, limit=1)
    latest_prediction = None
    if predictions:
        pred_dict = ModelPredictionResponse.model_validate(predictions[0]).model_dump()
        if predictions[0].asset:
            pred_dict["asset_symbol"] = predictions[0].asset.symbol
            pred_dict["asset_name"] = predictions[0].asset.name
        latest_prediction = ModelPredictionResponse(**pred_dict)

    accuracy = await PredictionService.get_prediction_accuracy(db, asset_uuid, days=30)

    disclaimer = await DisclaimerService.get_active_disclaimer(db)
    if disclaimer:
        risk_disclaimer = RiskDisclaimer(
            content=disclaimer.content, version=disclaimer.version, accepted=False
        )
    else:
        risk_disclaimer = RiskDisclaimer(
            content="本预测基于算法模型生成，不构成投资建议。投资有风险，决策需谨慎。",
            version="default", accepted=False
        )

    await DisclaimerService.log_risk_disclosure(
        db=db, user_id=current_user.id if current_user else None,
        page="asset_analysis", disclosure_type="comprehensive_risk"
    )

    return AssetAnalysisResponse(
        asset_id=str(asset_uuid),
        asset_symbol=asset.symbol,
        asset_name=asset.name,
        current_price=current_price,
        research_card=research_card,
        latest_prediction=latest_prediction,
        prediction_accuracy=PredictionAccuracy(**accuracy),
        disclaimer=risk_disclaimer
    )


# ============ 免责声明 ============

@router.get(
    "/disclaimer",
    summary="获取免责声明",
    response_model=RiskDisclaimer,
    description="获取风险免责声明"
)
async def get_disclaimer(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取免责声明"""
    disclaimer = await DisclaimerService.get_active_disclaimer(db)
    if not disclaimer:
        return RiskDisclaimer(
            content="本平台所有分析均基于算法生成，不构成投资建议。历史表现不代表未来，投资有风险。",
            version="default", accepted=False
        )
    return RiskDisclaimer(content=disclaimer.content, version=disclaimer.version, accepted=False)