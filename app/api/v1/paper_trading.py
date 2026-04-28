"""
模拟交易 API 路由
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.paper_trading import (
    PaperAccountCreate,
    PaperAccountUpdate,
    PaperAccountResponse,
    PaperAccountListResponse,
    PositionResponse,
    PositionListResponse,
    OrderCreate,
    OrderResponse,
    OrderListResponse,
    TransactionResponse,
    TransactionListResponse,
    AccountSnapshotResponse,
    SnapshotListResponse
)
from app.services.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/paper-trading")


# ============ 账户管理 ============

@router.post(
    "/accounts",
    summary="创建模拟账户",
    response_model=PaperAccountResponse,
    description="创建一个新的模拟交易账户"
)
async def create_account(
    data: PaperAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建模拟账户"""
    account = await PaperTradingService.create_account(
        db=db,
        user_id=current_user.id,
        name=data.name,
        initial_capital=data.initial_capital,
        currency=data.currency
    )
    return PaperAccountResponse.model_validate(account)


@router.get(
    "/accounts",
    summary="获取账户列表",
    response_model=PaperAccountListResponse,
    description="获取当前用户的所有模拟交易账户列表"
)
async def list_accounts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的模拟账户列表"""
    accounts = await PaperTradingService.get_accounts(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return PaperAccountListResponse(
        items=[PaperAccountResponse.model_validate(a) for a in accounts],
        total=len(accounts)
    )


@router.get(
    "/accounts/{account_id}",
    summary="获取账户详情",
    response_model=PaperAccountResponse,
    description="获取指定账户的详细信息"
)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户详情"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    return PaperAccountResponse.model_validate(account)


@router.delete(
    "/accounts/{account_id}",
    summary="删除模拟账户",
    description="""
删除模拟账户及其所有关联数据。

**级联删除内容**:
- 持仓记录（positions）
- 订单记录（orders）
- 交易记录（transactions）
- 账户快照（account_snapshots）

**注意**: 此操作不可撤销，请谨慎操作。
"""
)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模拟账户（级联删除持仓、订单、交易记录、快照）"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    await PaperTradingService.delete_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    return {"message": "账户已删除"}


@router.get(
    "/accounts/{account_id}/summary",
    summary="获取账户摘要",
    description="获取账户摘要（包含持仓总市值、盈亏等统计信息）"
)
async def get_account_summary(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户摘要"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    summary = await PaperTradingService.get_account_summary(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    return {
        "account": PaperAccountResponse.model_validate(summary["account"]),
        "total_position_value": float(summary["total_position_value"]),
        "total_value": float(summary["total_value"]),
        "total_pnl": float(summary["total_pnl"]),
        "total_pnl_pct": float(summary["total_pnl_pct"]),
        "positions_count": summary["positions_count"]
    }


@router.put(
    "/accounts/{account_id}",
    summary="更新账户信息",
    response_model=PaperAccountResponse,
    description="更新账户名称"
)
async def update_account(
    account_id: str,
    data: PaperAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新账户名称"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    if data.name:
        account.name = data.name
        await db.commit()
        await db.refresh(account)

    return PaperAccountResponse.model_validate(account)


# ============ 持仓管理 ============

@router.get(
    "/accounts/{account_id}/positions",
    summary="获取持仓列表",
    response_model=PositionListResponse,
    description="获取账户当前持仓，包含实时盈亏计算"
)
async def list_positions(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户持仓"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    await PaperTradingService.update_account_prices(db, account_uuid)
    positions = await PaperTradingService.get_positions(db, account_uuid)

    items = []
    for pos in positions:
        pos_dict = {
            "id": pos.id,
            "account_id": pos.account_id,
            "asset_id": pos.asset_id,
            "quantity": pos.quantity,
            "avg_cost": pos.avg_cost,
            "current_price": pos.current_price,
            "market_value": pos.market_value,
            "unrealized_pnl": pos.unrealized_pnl,
            "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            "opened_at": pos.opened_at,
        }
        if pos.asset:
            pos_dict["asset_symbol"] = pos.asset.symbol
            pos_dict["asset_name"] = pos.asset.name
        items.append(PositionResponse(**pos_dict))

    return PositionListResponse(items=items, total=len(items))


# ============ 订单管理 ============

@router.post(
    "/accounts/{account_id}/orders",
    summary="创建订单",
    response_model=OrderResponse,
    description="创建交易订单（市价单或限价单）"
)
async def create_order(
    account_id: str,
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建订单"""
    try:
        account_uuid = UUID(account_id)
        asset_uuid = UUID(data.asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的ID格式")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    order = await PaperTradingService.create_order(
        db=db,
        account_id=account_uuid,
        asset_id=asset_uuid,
        order_type=data.order_type,
        side=data.side,
        quantity=data.quantity,
        price=data.price
    )
    return OrderResponse.model_validate(order)


@router.post(
    "/accounts/{account_id}/orders/{order_id}/execute",
    summary="执行订单",
    response_model=OrderResponse,
    description="执行订单完成交易撮合"
)
async def execute_order(
    account_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """执行订单"""
    try:
        account_uuid = UUID(account_id)
        order_uuid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的ID格式")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    order = await PaperTradingService.execute_order(db, order_uuid)
    order_dict = OrderResponse.model_validate(order).model_dump()

    asset_result = await db.execute(
        text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
        {"asset_id": str(order.asset_id)}
    )
    asset_row = asset_result.fetchone()
    if asset_row:
        order_dict["asset_symbol"] = asset_row[0]
        order_dict["asset_name"] = asset_row[1]

    return OrderResponse(**order_dict)


@router.post(
    "/accounts/{account_id}/orders/{order_id}/cancel",
    summary="取消订单",
    response_model=OrderResponse,
    description="取消未执行的订单"
)
async def cancel_order(
    account_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消订单"""
    try:
        account_uuid = UUID(account_id)
        order_uuid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的ID格式")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    order = await PaperTradingService.cancel_order(db, order_uuid)
    return OrderResponse.model_validate(order)


@router.get(
    "/accounts/{account_id}/orders",
    summary="获取订单列表",
    response_model=OrderListResponse,
    description="获取账户的历史订单列表"
)
async def list_orders(
    account_id: str,
    order_status: Optional[str] = Query(default=None, alias="status", description="订单状态过滤"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取订单列表"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    orders = await PaperTradingService.get_orders(
        db=db, account_id=account_uuid, status=order_status, skip=skip, limit=limit
    )

    items = []
    for order in orders:
        order_dict = OrderResponse.model_validate(order).model_dump()
        asset_result = await db.execute(
            text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
            {"asset_id": str(order.asset_id)}
        )
        asset_row = asset_result.fetchone()
        if asset_row:
            order_dict["asset_symbol"] = asset_row[0]
            order_dict["asset_name"] = asset_row[1]
        items.append(OrderResponse(**order_dict))

    return OrderListResponse(items=items, total=len(items))


# ============ 交易记录 ============

@router.get(
    "/accounts/{account_id}/transactions",
    summary="获取交易记录",
    response_model=TransactionListResponse,
    description="获取账户的历史交易记录"
)
async def list_transactions(
    account_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取交易记录"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    transactions = await PaperTradingService.get_transactions(
        db=db, account_id=account_uuid, skip=skip, limit=limit
    )

    items = []
    for tx in transactions:
        tx_dict = TransactionResponse.model_validate(tx).model_dump()
        asset_result = await db.execute(
            text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
            {"asset_id": str(tx.asset_id)}
        )
        asset_row = asset_result.fetchone()
        if asset_row:
            tx_dict["asset_symbol"] = asset_row[0]
            tx_dict["asset_name"] = asset_row[1]
        items.append(TransactionResponse(**tx_dict))

    return TransactionListResponse(items=items, total=len(items))


# ============ 绩效分析 ============

@router.get(
    "/accounts/{account_id}/performance",
    summary="获取绩效分析",
    description="获取账户绩效分析报告"
)
async def get_performance(
    account_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取绩效分析"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    if not start_time:
        start_time = datetime.utcnow() - timedelta(days=30)
    if not end_time:
        end_time = datetime.utcnow()

    return await PaperTradingService.calculate_performance(
        db=db, account_id=account_uuid, start_time=start_time, end_time=end_time
    )


# ============ 账户快照 ============

@router.get(
    "/accounts/{account_id}/snapshots",
    summary="获取账户快照",
    response_model=SnapshotListResponse,
    description="获取账户历史快照用于绘制资金曲线"
)
async def list_snapshots(
    account_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户快照"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的账户ID")

    account = await PaperTradingService.get_account(
        db=db, account_id=account_uuid, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    snapshots = await PaperTradingService.get_snapshots(
        db=db, account_id=account_uuid,
        start_time=start_time, end_time=end_time, skip=skip, limit=limit
    )

    return SnapshotListResponse(
        items=[AccountSnapshotResponse.model_validate(s) for s in snapshots],
        total=len(snapshots)
    )