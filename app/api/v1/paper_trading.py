"""
模拟交易 API 路由
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.core.response import ResponseWrapper, UnifiedResponse
from app.models.user import User
from app.schemas.paper_trading import (
    PaperAccountCreate,
    PaperAccountUpdate,
    PaperAccountResponse,
    PaperAccountListResponse,
    AccountSummaryResponse,
    PositionResponse,
    PositionListResponse,
    OrderCreate,
    OrderResponse,
    OrderListResponse,
    TransactionResponse,
    TransactionListResponse,
    PerformanceResponse,
    AccountSnapshotResponse,
    SnapshotListResponse
)
from app.services.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/paper-trading")


# ============ 账户管理 ============

@router.post(
    "/accounts",
    summary="创建模拟账户",
    response_model=UnifiedResponse[PaperAccountResponse],
    description="""
创建一个新的模拟交易账户。

**请求参数**:
- `name`: 账户名称（1-100字符）
- `initial_capital`: 初始资金（1000-10000000）
- `currency`: 货币类型，默认USD

**返回**: 账户详情，包含账户ID、初始资金、现金余额等
"""
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
    return ResponseWrapper.success(
        data=PaperAccountResponse.model_validate(account),
        msg="模拟账户创建成功"
    )


@router.get(
    "/accounts",
    summary="获取账户列表",
    response_model=UnifiedResponse[PaperAccountListResponse],
    description="获取当前用户的所有模拟交易账户列表"
)
async def list_accounts(
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
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
    total = len(accounts)
    return ResponseWrapper.success(
        data=PaperAccountListResponse(
            items=[PaperAccountResponse.model_validate(a) for a in accounts],
            total=total
        )
    )


@router.get(
    "/accounts/{account_id}",
    summary="获取账户详情",
    response_model=UnifiedResponse[PaperAccountResponse],
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
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    return ResponseWrapper.success(data=PaperAccountResponse.model_validate(account))


@router.get(
    "/accounts/{account_id}/summary",
    summary="获取账户摘要",
    response_model=UnifiedResponse[Dict[str, Any]],
    description="获取账户摘要（包含持仓总市值、盈亏等统计信息）"
)
async def get_account_summary(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户摘要（包含持仓总市值、盈亏等）"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    summary = await PaperTradingService.get_account_summary(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    return ResponseWrapper.success(
        data={
            "account": PaperAccountResponse.model_validate(summary["account"]),
            "total_position_value": float(summary["total_position_value"]),
            "total_value": float(summary["total_value"]),
            "total_pnl": float(summary["total_pnl"]),
            "total_pnl_pct": float(summary["total_pnl_pct"]),
            "positions_count": summary["positions_count"]
        }
    )


@router.put(
    "/accounts/{account_id}",
    summary="更新账户信息",
    response_model=UnifiedResponse[PaperAccountResponse],
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
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    if data.name:
        account.name = data.name
        await db.commit()
        await db.refresh(account)

    return ResponseWrapper.success(
        data=PaperAccountResponse.model_validate(account),
        msg="账户更新成功"
    )


# ============ 持仓管理 ============

@router.get(
    "/accounts/{account_id}/positions",
    summary="获取持仓列表",
    response_model=UnifiedResponse[PositionListResponse],
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
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    await PaperTradingService.update_account_prices(db, account_uuid)
    positions = await PaperTradingService.get_positions(db, account_uuid)

    items = []
    for pos in positions:
        pos_data = PositionResponse.model_validate(pos)
        if pos.asset:
            pos_data.asset_symbol = pos.asset.symbol
            pos_data.asset_name = pos.asset.name
        items.append(pos_data)

    return ResponseWrapper.success(data=PositionListResponse(items=items, total=len(items)))


# ============ 订单管理 ============

@router.post(
    "/accounts/{account_id}/orders",
    summary="创建订单",
    response_model=UnifiedResponse[OrderResponse],
    description="""
创建交易订单（市价单或限价单）。

**请求参数**:
- `asset_id`: 资产ID（UUID格式）
- `order_type`: 订单类型 - `market`(市价单) 或 `limit`(限价单)
- `side`: 交易方向 - `buy`(买入) 或 `sell`(卖出)
- `quantity`: 交易数量
- `price`: 限价单价格（限价单必填）

**注意**: 买入时需确保资金充足，卖出时需确保持仓充足
"""
)
async def create_order(
    account_id: str,
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建订单（市价单或限价单）"""
    try:
        account_uuid = UUID(account_id)
        asset_uuid = UUID(data.asset_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的ID格式", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    order = await PaperTradingService.create_order(
        db=db,
        account_id=account_uuid,
        asset_id=asset_uuid,
        order_type=data.order_type,
        side=data.side,
        quantity=data.quantity,
        price=data.price
    )
    return ResponseWrapper.success(
        data=OrderResponse.model_validate(order),
        msg="订单创建成功"
    )


@router.post(
    "/accounts/{account_id}/orders/{order_id}/execute",
    summary="执行订单",
    response_model=UnifiedResponse[OrderResponse],
    description="""
执行已创建的订单，完成交易撮合。

**流程**:
1. 获取当前市场价格（市价单）或使用限价
2. 计算交易金额和手续费（0.1%）
3. 更新账户余额和持仓
4. 创建交易记录和账户快照

**返回**: 执行后的订单详情，包含成交价格、数量、手续费等
"""
)
async def execute_order(
    account_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """执行订单（撮合成交）"""
    try:
        account_uuid = UUID(account_id)
        order_uuid = UUID(order_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的ID格式", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    order = await PaperTradingService.execute_order(db, order_uuid)
    order_data = OrderResponse.model_validate(order)

    asset_result = await db.execute(
        text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
        {"asset_id": str(order.asset_id)}
    )
    asset_row = asset_result.fetchone()
    if asset_row:
        order_data.asset_symbol = asset_row[0]
        order_data.asset_name = asset_row[1]

    return ResponseWrapper.success(data=order_data, msg="订单执行成功")


@router.post(
    "/accounts/{account_id}/orders/{order_id}/cancel",
    summary="取消订单",
    response_model=UnifiedResponse[OrderResponse],
    description="取消未执行的待处理订单"
)
async def cancel_order(
    account_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消未执行的订单"""
    try:
        account_uuid = UUID(account_id)
        order_uuid = UUID(order_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的ID格式", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    order = await PaperTradingService.cancel_order(db, order_uuid)
    return ResponseWrapper.success(
        data=OrderResponse.model_validate(order),
        msg="订单取消成功"
    )


@router.get(
    "/accounts/{account_id}/orders",
    summary="获取订单列表",
    response_model=UnifiedResponse[OrderListResponse],
    description="获取账户的历史订单列表，可按状态过滤"
)
async def list_orders(
    account_id: str,
    status: Optional[str] = Query(default=None, description="订单状态: pending, filled, cancelled"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户订单列表"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    orders = await PaperTradingService.get_orders(
        db=db,
        account_id=account_uuid,
        status=status,
        skip=skip,
        limit=limit
    )

    items = []
    for order in orders:
        order_data = OrderResponse.model_validate(order)
        asset_result = await db.execute(
            text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
            {"asset_id": str(order.asset_id)}
        )
        asset_row = asset_result.fetchone()
        if asset_row:
            order_data.asset_symbol = asset_row[0]
            order_data.asset_name = asset_row[1]
        items.append(order_data)

    return ResponseWrapper.success(data=OrderListResponse(items=items, total=len(items)))


# ============ 交易记录 ============

@router.get(
    "/accounts/{account_id}/transactions",
    summary="获取交易记录",
    response_model=UnifiedResponse[TransactionListResponse],
    description="获取账户的历史交易记录"
)
async def list_transactions(
    account_id: str,
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户交易记录"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    transactions = await PaperTradingService.get_transactions(
        db=db,
        account_id=account_uuid,
        skip=skip,
        limit=limit
    )

    items = []
    for tx in transactions:
        tx_data = TransactionResponse.model_validate(tx)
        asset_result = await db.execute(
            text("SELECT symbol, name FROM assets WHERE id = :asset_id"),
            {"asset_id": str(tx.asset_id)}
        )
        asset_row = asset_result.fetchone()
        if asset_row:
            tx_data.asset_symbol = asset_row[0]
            tx_data.asset_name = asset_row[1]
        items.append(tx_data)

    return ResponseWrapper.success(data=TransactionListResponse(items=items, total=len(items)))


# ============ 绩效分析 ============

@router.get(
    "/accounts/{account_id}/performance",
    summary="获取绩效分析",
    response_model=UnifiedResponse[Dict[str, Any]],
    description="""
获取账户绩效分析报告。

**返回内容**:
- `overview`: 绩效概览（总市值、收益率、日盈亏）
- `metrics`: 绩效指标（年化收益、最大回撤、夏普比率、胜率）
- `equity_curve`: 资金曲线数据
"""
)
async def get_performance(
    account_id: str,
    start_time: Optional[datetime] = Query(default=None, description="开始时间"),
    end_time: Optional[datetime] = Query(default=None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户绩效分析"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    if not start_time:
        start_time = datetime.utcnow() - timedelta(days=30)
    if not end_time:
        end_time = datetime.utcnow()

    performance = await PaperTradingService.calculate_performance(
        db=db,
        account_id=account_uuid,
        start_time=start_time,
        end_time=end_time
    )
    return ResponseWrapper.success(data=performance)


# ============ 账户快照 ============

@router.get(
    "/accounts/{account_id}/snapshots",
    summary="获取账户快照",
    response_model=UnifiedResponse[SnapshotListResponse],
    description="获取账户历史快照，用于绘制资金曲线"
)
async def list_snapshots(
    account_id: str,
    start_time: Optional[datetime] = Query(default=None, description="开始时间"),
    end_time: Optional[datetime] = Query(default=None, description="结束时间"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=100, ge=1, le=365, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取账户历史快照（资金曲线）"""
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return ResponseWrapper.error(msg="无效的账户ID", code=400)

    account = await PaperTradingService.get_account(
        db=db,
        account_id=account_uuid,
        user_id=current_user.id
    )
    if not account:
        return ResponseWrapper.error(msg="账户不存在", code=404)

    snapshots = await PaperTradingService.get_snapshots(
        db=db,
        account_id=account_uuid,
        start_time=start_time,
        end_time=end_time,
        skip=skip,
        limit=limit
    )

    items = [AccountSnapshotResponse.model_validate(s) for s in snapshots]
    return ResponseWrapper.success(data=SnapshotListResponse(items=items, total=len(items)))