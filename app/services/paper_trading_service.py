"""
模拟交易服务层
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.paper_trading import PaperAccount, Position, Order, Transaction, AccountSnapshot
from app.models.asset import Asset
from app.core.exceptions import AppException
from app.services.asset_service import get_latest_price


class PaperTradingService:
    """模拟交易服务"""

    COMMISSION_RATE = Decimal("0.001")  # 0.1% 手续费

    @staticmethod
    async def create_account(
        db: AsyncSession,
        user_id: UUID,
        name: str,
        initial_capital: Decimal,
        currency: str = "USD"
    ) -> PaperAccount:
        """创建模拟账户"""
        account = PaperAccount(
            user_id=user_id,
            name=name,
            initial_capital=initial_capital,
            current_capital=initial_capital,
            cash_balance=initial_capital,
            currency=currency
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        # 创建初始快照
        await PaperTradingService.create_snapshot(db, account.id)

        logger.info(f"Created paper account {account.id} for user {user_id}")
        return account

    @staticmethod
    async def get_accounts(
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20
    ) -> List[PaperAccount]:
        """获取用户账户列表"""
        result = await db.execute(
            select(PaperAccount)
            .where(PaperAccount.user_id == user_id)
            .order_by(desc(PaperAccount.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_account(db: AsyncSession, account_id: UUID, user_id: UUID) -> Optional[PaperAccount]:
        """获取账户详情"""
        result = await db.execute(
            select(PaperAccount)
            .where(and_(PaperAccount.id == account_id, PaperAccount.user_id == user_id))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_account_summary(
        db: AsyncSession,
        account_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """获取账户摘要"""
        account = await PaperTradingService.get_account(db, account_id, user_id)
        if not account:
            raise AppException("NOT_FOUND", "账户不存在")

        # 获取持仓
        positions = await PaperTradingService.get_positions(db, account_id)

        # 计算总持仓市值和盈亏
        total_position_value = Decimal("0")
        total_pnl = Decimal("0")

        for pos in positions:
            if pos.market_value:
                total_position_value += pos.market_value
            if pos.unrealized_pnl:
                total_pnl += pos.unrealized_pnl

        total_value = account.cash_balance + total_position_value
        total_pnl_pct = (total_pnl / account.initial_capital * 100) if account.initial_capital > 0 else Decimal("0")

        return {
            "account": account,
            "total_position_value": total_position_value,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "positions_count": len(positions)
        }

    @staticmethod
    async def update_account_prices(db: AsyncSession, account_id: UUID) -> None:
        """更新账户持仓价格"""
        positions = await PaperTradingService.get_positions(db, account_id)
        account = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = account.scalar_one_or_none()

        if not account:
            return

        for pos in positions:
            try:
                # 获取当前价格
                asset_result = await db.execute(select(Asset).where(Asset.id == pos.asset_id))
                asset = asset_result.scalar_one_or_none()
                if asset:
                    current_price = await get_latest_price(db, pos.asset_id)
                    if current_price:
                        pos.current_price = current_price
                        pos.market_value = pos.quantity * current_price
                        pos.unrealized_pnl = pos.market_value - (pos.quantity * pos.avg_cost)
                        pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.quantity * pos.avg_cost) * 100) if pos.avg_cost > 0 else Decimal("0")
            except Exception as e:
                logger.warning(f"Failed to update price for position {pos.id}: {e}")

        # 计算账户总市值
        total_position_value = sum(p.market_value or Decimal("0") for p in positions)
        account.current_capital = account.cash_balance + total_position_value

        await db.commit()

    @staticmethod
    async def get_positions(db: AsyncSession, account_id: UUID) -> List[Position]:
        """获取账户持仓"""
        result = await db.execute(
            select(Position)
            .options(selectinload(Position.asset))
            .where(Position.account_id == account_id)
            .order_by(desc(Position.opened_at))
        )
        return result.scalars().all()

    @staticmethod
    async def create_order(
        db: AsyncSession,
        account_id: UUID,
        asset_id: UUID,
        order_type: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> Order:
        """创建订单"""
        # 验证订单类型
        if order_type not in ["market", "limit"]:
            raise AppException("VALIDATION_ERROR", "订单类型必须是 market 或 limit")
        if side not in ["buy", "sell"]:
            raise AppException("VALIDATION_ERROR", "订单方向必须是 buy 或 sell")
        if order_type == "limit" and price is None:
            raise AppException("VALIDATION_ERROR", "限价单必须指定价格")

        # 获取账户
        account = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = account.scalar_one_or_none()
        if not account:
            raise AppException("NOT_FOUND", "账户不存在")

        # 验证资产
        asset = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset.scalar_one_or_none()
        if not asset:
            raise AppException("NOT_FOUND", "资产不存在")

        # 订单预检查
        if order_type == "market":
            # 获取当前价格
            current_price = await get_latest_price(db, asset_id)
            if not current_price:
                raise AppException("VALIDATION_ERROR", "无法获取当前价格")
            estimated_cost = quantity * current_price
            commission = estimated_cost * PaperTradingService.COMMISSION_RATE
            total_cost = estimated_cost + commission

            if side == "buy":
                # 检查资金是否充足
                if account.cash_balance < total_cost:
                    raise AppException("VALIDATION_ERROR", "资金不足")
            else:
                # 检查持仓是否充足
                position = await PaperTradingService._get_position(db, account_id, asset_id)
                if not position or position.quantity < quantity:
                    raise AppException("VALIDATION_ERROR", "持仓不足")

        # 创建订单
        order = Order(
            account_id=account_id,
            asset_id=asset_id,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            status="pending"
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)

        logger.info(f"Created order {order.id} for account {account_id}")
        return order

    @staticmethod
    async def execute_order(db: AsyncSession, order_id: UUID) -> Order:
        """执行订单"""
        # 获取订单
        order = await db.execute(
            select(Order)
            .options(selectinload(Order.account))
            .where(Order.id == order_id)
        )
        order = order.scalar_one_or_none()

        if not order:
            raise AppException("NOT_FOUND", "订单不存在")
        if order.status != "pending":
            raise AppException("VALIDATION_ERROR", f"订单状态为 {order.status}, 无法执行")

        # 确定执行价格
        if order.order_type == "market":
            execution_price = await get_latest_price(db, order.asset_id)
            if not execution_price:
                raise AppException("VALIDATION_ERROR", "无法获取当前价格")
        else:
            # 限价单：简化处理，假设能以限价成交
            execution_price = order.price

        # 计算费用
        total_amount = order.quantity * execution_price
        commission = total_amount * PaperTradingService.COMMISSION_RATE

        # 更新账户和持仓
        account = order.account
        position = await PaperTradingService._get_position(db, account.id, order.asset_id)

        if order.side == "buy":
            # 买入
            total_cost = total_amount + commission
            account.cash_balance -= total_cost

            if position:
                # 更新持仓
                new_quantity = position.quantity + order.quantity
                new_avg_cost = (position.quantity * position.avg_cost + total_amount) / new_quantity
                position.quantity = new_quantity
                position.avg_cost = new_avg_cost
            else:
                # 创建新持仓
                position = Position(
                    account_id=account.id,
                    asset_id=order.asset_id,
                    quantity=order.quantity,
                    avg_cost=execution_price
                )
                db.add(position)
        else:
            # 卖出
            if not position or position.quantity < order.quantity:
                raise AppException("VALIDATION_ERROR", "持仓不足")

            total_revenue = total_amount - commission
            account.cash_balance += total_revenue

            # 更新持仓
            position.quantity -= order.quantity
            if position.quantity <= 0:
                # 清空持仓
                await db.delete(position)

        # 创建交易记录
        transaction = Transaction(
            account_id=account.id,
            order_id=order.id,
            asset_id=order.asset_id,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            total_amount=total_amount,
            commission=commission
        )
        db.add(transaction)

        # 更新订单状态
        order.status = "filled"
        order.filled_quantity = order.quantity
        order.filled_price = execution_price
        order.commission = commission
        order.filled_at = datetime.utcnow()

        # 更新账户总市值
        await PaperTradingService.update_account_prices(db, account.id)

        # 创建快照
        await PaperTradingService.create_snapshot(db, account.id)

        await db.commit()
        await db.refresh(order)

        logger.info(f"Executed order {order.id} at price {execution_price}")
        return order

    @staticmethod
    async def cancel_order(db: AsyncSession, order_id: UUID) -> Order:
        """取消订单"""
        order = await db.execute(select(Order).where(Order.id == order_id))
        order = order.scalar_one_or_none()

        if not order:
            raise AppException("NOT_FOUND", "订单不存在")
        if order.status != "pending":
            raise AppException("VALIDATION_ERROR", f"订单状态为 {order.status}, 无法取消")

        order.status = "cancelled"
        await db.commit()
        await db.refresh(order)

        logger.info(f"Cancelled order {order_id}")
        return order

    @staticmethod
    async def get_orders(
        db: AsyncSession,
        account_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Order]:
        """获取订单列表"""
        query = select(Order).options(selectinload(Order.account)).where(Order.account_id == account_id)

        if status:
            query = query.where(Order.status == status)

        query = query.order_by(desc(Order.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_transactions(
        db: AsyncSession,
        account_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> List[Transaction]:
        """获取交易记录"""
        result = await db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(desc(Transaction.executed_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def create_snapshot(db: AsyncSession, account_id: UUID) -> AccountSnapshot:
        """创建账户快照"""
        # 获取账户当前状态
        account = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = account.scalar_one_or_none()
        if not account:
            raise AppException("NOT_FOUND", "账户不存在")

        # 计算持仓市值
        positions = await PaperTradingService.get_positions(db, account_id)
        position_value = sum(p.market_value or Decimal("0") for p in positions)
        total_value = account.cash_balance + position_value

        # 计算每日盈亏
        daily_pnl = None
        daily_pnl_pct = None

        # 获取上一个快照
        last_snapshot = await db.execute(
            select(AccountSnapshot)
            .where(AccountSnapshot.account_id == account_id)
            .order_by(desc(AccountSnapshot.snapshot_at))
            .limit(1)
        )
        last_snapshot = last_snapshot.scalar_one_or_none()

        if last_snapshot:
            daily_pnl = total_value - last_snapshot.total_value
            if last_snapshot.total_value > 0:
                daily_pnl_pct = (daily_pnl / last_snapshot.total_value) * 100

        snapshot = AccountSnapshot(
            account_id=account_id,
            snapshot_at=datetime.utcnow(),
            total_value=total_value,
            cash_balance=account.cash_balance,
            position_value=position_value,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        return snapshot

    @staticmethod
    async def get_snapshots(
        db: AsyncSession,
        account_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AccountSnapshot]:
        """获取快照列表"""
        query = select(AccountSnapshot).where(AccountSnapshot.account_id == account_id)

        if start_time:
            query = query.where(AccountSnapshot.snapshot_at >= start_time)
        if end_time:
            query = query.where(AccountSnapshot.snapshot_at <= end_time)

        query = query.order_by(desc(AccountSnapshot.snapshot_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def calculate_performance(
        db: AsyncSession,
        account_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """计算绩效指标"""
        account = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = account.scalar_one_or_none()
        if not account:
            raise AppException("NOT_FOUND", "账户不存在")

        # 获取快照数据
        snapshots = await PaperTradingService.get_snapshots(
            db, account_id, start_time, end_time, limit=365
        )

        if not snapshots:
            return {
                "overview": {
                    "total_value": account.current_capital,
                    "total_return": account.current_capital - account.initial_capital,
                    "total_return_pct": (account.current_capital - account.initial_capital) / account.initial_capital * 100,
                    "daily_pnl": None,
                    "daily_pnl_pct": None
                },
                "metrics": None,
                "equity_curve": None,
                "period_start": None,
                "period_end": None
            }

        # 计算绩效指标
        equity_values = [float(s.total_value) for s in reversed(snapshots)]

        total_return = equity_values[-1] - float(account.initial_capital)
        total_return_pct = total_return / float(account.initial_capital) * 100

        # 年化收益
        days = len(snapshots)
        annualized_return = (total_return_pct / days) * 365 if days > 0 else 0

        # 最大回撤
        max_drawdown = 0
        peak = equity_values[0]
        for value in equity_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 波动率 (日收益率标准差)
        returns = []
        for i in range(1, len(equity_values)):
            if equity_values[i-1] > 0:
                returns.append((equity_values[i] - equity_values[i-1]) / equity_values[i-1])

        volatility = 0
        if returns:
            import statistics
            volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0

        # 夏普比率 (简化计算)
        sharpe_ratio = 0
        if volatility > 0:
            sharpe_ratio = annualized_return / volatility

        # 获取交易统计
        transactions = await PaperTradingService.get_transactions(db, account_id, limit=1000)
        total_trades = len(transactions)

        profit_trades = 0
        loss_trades = 0
        win_rate = 0
        avg_profit = 0
        avg_loss = 0

        if total_trades > 0:
            # 简化计算：基于盈亏
            sell_trades = [t for t in transactions if t.side == "sell"]
            # 这里需要更复杂的计算来准确统计盈亏交易
            # 暂时使用简单估算
            profit_trades = len(sell_trades)  # 简化
            loss_trades = total_trades - profit_trades
            win_rate = profit_trades / total_trades * 100

        metrics = {
            "total_return": total_return_pct,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "profit_trades": profit_trades,
            "loss_trades": loss_trades,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss
        }

        # 构建资金曲线
        equity_curve = [
            {
                "time": s.snapshot_at,
                "total_value": s.total_value,
                "cash_balance": s.cash_balance,
                "position_value": s.position_value,
                "daily_pnl": s.daily_pnl
            }
            for s in reversed(snapshots)
        ]

        # 最新日盈亏
        latest_snapshot = snapshots[0] if snapshots else None
        daily_pnl = float(latest_snapshot.daily_pnl) if latest_snapshot and latest_snapshot.daily_pnl else None
        daily_pnl_pct = float(latest_snapshot.daily_pnl_pct) if latest_snapshot and latest_snapshot.daily_pnl_pct else None

        return {
            "overview": {
                "total_value": account.current_capital,
                "total_return": Decimal(str(total_return)),
                "total_return_pct": Decimal(str(total_return_pct)),
                "daily_pnl": Decimal(str(daily_pnl)) if daily_pnl else None,
                "daily_pnl_pct": Decimal(str(daily_pnl_pct)) if daily_pnl_pct else None
            },
            "metrics": metrics,
            "equity_curve": equity_curve,
            "period_start": snapshots[-1].snapshot_at if snapshots else None,
            "period_end": snapshots[0].snapshot_at if snapshots else None
        }

    @staticmethod
    async def _get_position(db: AsyncSession, account_id: UUID, asset_id: UUID) -> Optional[Position]:
        """获取特定持仓"""
        result = await db.execute(
            select(Position)
            .where(and_(Position.account_id == account_id, Position.asset_id == asset_id))
        )
        return result.scalar_one_or_none()