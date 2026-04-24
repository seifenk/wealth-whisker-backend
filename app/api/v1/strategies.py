"""
策略管理API路由
"""
from typing import List, Optional
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
    StrategyTemplateResponse,
    StrategyTemplateListResponse,
    UserStrategyCreate,
    UserStrategyUpdate,
    UserStrategyResponse,
    UserStrategyListResponse,
)
from app.services.strategy_service import StrategyService

router = APIRouter(prefix="/strategies", tags=["策略管理"])


# ============ 策略模板 ============

@router.get("/templates", response_model=StrategyTemplateListResponse)
async def get_strategy_templates(
    category: Optional[str] = Query(None, description="策略分类: trend, mean_reversion, portfolio"),
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    获取策略模板列表

    游客可查看公开模板
    """
    service = StrategyService(db)

    # 确保默认模板存在
    await service.ensure_default_templates()

    templates = await service.get_templates(category=category)

    items = [
        StrategyTemplateResponse(
            id=str(t.id),
            code=t.code,
            name=t.name,
            description=t.description,
            category=t.category,
            parameters=t.parameters,
            is_public=t.is_public,
        )
        for t in templates
    ]

    return StrategyTemplateListResponse(items=items, total=len(items))


@router.get("/templates/{template_id}", response_model=StrategyTemplateResponse)
async def get_strategy_template(
    template_id: str,
    db = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    获取策略模板详情
    """
    try:
        uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的模板ID格式",
        )

    service = StrategyService(db)
    template = await service.get_template_by_id(uuid)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略模板不存在",
        )

    return StrategyTemplateResponse(
        id=str(template.id),
        code=template.code,
        name=template.name,
        description=template.description,
        category=template.category,
        parameters=template.parameters,
        is_public=template.is_public,
    )


# ============ 用户策略 ============

@router.post("/", response_model=UserStrategyResponse)
async def create_user_strategy(
    data: UserStrategyCreate,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建用户策略配置

    需要登录
    """
    try:
        template_uuid = UUID(data.template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的模板ID格式",
        )

    service = StrategyService(db)

    try:
        strategy = await service.create_user_strategy(
            user_id=current_user.id,
            template_id=template_uuid,
            name=data.name,
            parameters=data.parameters,
        )

        # 获取模板信息
        template = await service.get_template_by_id(template_uuid)

        return UserStrategyResponse(
            id=str(strategy.id),
            template_id=str(strategy.template_id),
            template_code=template.code if template else None,
            template_name=template.name if template else None,
            name=strategy.name,
            parameters=strategy.parameters,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/", response_model=UserStrategyListResponse)
async def get_user_strategies(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户策略列表

    需要登录
    """
    service = StrategyService(db)
    strategies = await service.get_user_strategies(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    items = []
    for s in strategies:
        template = await service.get_template_by_id(s.template_id)
        items.append(UserStrategyResponse(
            id=str(s.id),
            template_id=str(s.template_id),
            template_code=template.code if template else None,
            template_name=template.name if template else None,
            name=s.name,
            parameters=s.parameters,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return UserStrategyListResponse(items=items, total=len(items))


@router.get("/{strategy_id}", response_model=UserStrategyResponse)
async def get_user_strategy(
    strategy_id: str,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户策略详情
    """
    try:
        uuid = UUID(strategy_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的策略ID格式",
        )

    service = StrategyService(db)
    strategy = await service.get_user_strategy_by_id(uuid, current_user.id)

    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在或不属于您",
        )

    template = await service.get_template_by_id(strategy.template_id)

    return UserStrategyResponse(
        id=str(strategy.id),
        template_id=str(strategy.template_id),
        template_code=template.code if template else None,
        template_name=template.name if template else None,
        name=strategy.name,
        parameters=strategy.parameters,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


@router.put("/{strategy_id}", response_model=UserStrategyResponse)
async def update_user_strategy(
    strategy_id: str,
    data: UserStrategyUpdate,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新用户策略配置
    """
    try:
        uuid = UUID(strategy_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的策略ID格式",
        )

    service = StrategyService(db)

    try:
        strategy = await service.update_user_strategy(
            strategy_id=uuid,
            user_id=current_user.id,
            name=data.name,
            parameters=data.parameters,
        )

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="策略不存在或不属于您",
            )

        template = await service.get_template_by_id(strategy.template_id)

        return UserStrategyResponse(
            id=str(strategy.id),
            template_id=str(strategy.template_id),
            template_code=template.code if template else None,
            template_name=template.name if template else None,
            name=strategy.name,
            parameters=strategy.parameters,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{strategy_id}")
async def delete_user_strategy(
    strategy_id: str,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除用户策略
    """
    try:
        uuid = UUID(strategy_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的策略ID格式",
        )

    service = StrategyService(db)
    deleted = await service.delete_user_strategy(uuid, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在或不属于您",
        )

    return {"message": "策略已删除"}