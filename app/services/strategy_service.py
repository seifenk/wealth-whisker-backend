"""
策略服务模块

管理策略模板和用户策略配置
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import StrategyTemplate, UserStrategy, BacktestJob, BacktestResult
from app.schemas.strategy import (
    MA_CROSS_PARAMS,
    MOMENTUM_PARAMS,
    DCA_PARAMS,
    RISK_PARITY_PARAMS,
)


# 预定义策略模板
DEFAULT_TEMPLATES = [
    {
        "code": "ma_cross",
        "name": "均线突破策略",
        "description": "基于快慢均线交叉信号进行买卖，当快线突破慢线向上时买入，向下时卖出",
        "category": "trend",
        "parameters": MA_CROSS_PARAMS,
    },
    {
        "code": "momentum",
        "name": "动量轮动策略",
        "description": "根据资产近期表现进行轮动，定期调整持仓到表现最好的资产",
        "category": "trend",
        "parameters": MOMENTUM_PARAMS,
    },
    {
        "code": "dca",
        "name": "定投策略",
        "description": "定期定额投资，分散时间风险，适合长期稳健投资",
        "category": "portfolio",
        "parameters": DCA_PARAMS,
    },
    {
        "code": "risk_parity",
        "name": "风险平价策略",
        "description": "根据资产波动率分配权重，使各资产贡献相同的风险",
        "category": "portfolio",
        "parameters": RISK_PARITY_PARAMS,
    },
]


class StrategyService:
    """策略服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_templates(
        self,
        category: Optional[str] = None,
        is_public: bool = True,
    ) -> List[StrategyTemplate]:
        """
        获取策略模板列表

        Args:
            category: 分类过滤
            is_public: 是否只返回公开模板

        Returns:
            策略模板列表
        """
        query = select(StrategyTemplate)

        if category:
            query = query.where(StrategyTemplate.category == category)
        if is_public:
            query = query.where(StrategyTemplate.is_public == True)

        query = query.order_by(StrategyTemplate.name)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_template_by_id(self, template_id: UUID) -> Optional[StrategyTemplate]:
        """根据ID获取策略模板"""
        result = await self.session.execute(
            select(StrategyTemplate).where(StrategyTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_template_by_code(self, code: str) -> Optional[StrategyTemplate]:
        """根据code获取策略模板"""
        result = await self.session.execute(
            select(StrategyTemplate).where(StrategyTemplate.code == code)
        )
        return result.scalar_one_or_none()

    async def ensure_default_templates(self) -> int:
        """
        确保默认策略模板存在

        Returns:
            创建的模板数量
        """
        created = 0
        for template_data in DEFAULT_TEMPLATES:
            existing = await self.get_template_by_code(template_data["code"])
            if not existing:
                template = StrategyTemplate(
                    code=template_data["code"],
                    name=template_data["name"],
                    description=template_data["description"],
                    category=template_data["category"],
                    parameters=template_data["parameters"],
                    is_public=True,
                )
                self.session.add(template)
                created += 1
                logger.info(f"创建策略模板: {template_data['code']}")

        if created > 0:
            await self.session.flush()

        return created

    async def validate_parameters(
        self,
        template: StrategyTemplate,
        parameters: Dict,
    ) -> Dict:
        """
        验证策略参数

        Args:
            template: 策略模板
            parameters: 用户配置的参数

        Returns:
            验证后的参数（包含默认值）

        Raises:
            ValueError: 参数验证失败
        """
        validated = {}
        param_schema = template.parameters

        for param_name, param_def in param_schema.items():
            user_value = parameters.get(param_name)

            # 使用默认值
            if user_value is None:
                validated[param_name] = param_def.get("default")
                continue

            # 类型验证
            param_type = param_def.get("type")
            if param_type == "integer":
                if not isinstance(user_value, int):
                    try:
                        user_value = int(user_value)
                    except (ValueError, TypeError):
                        raise ValueError(f"参数 {param_name} 必须是整数")

                # 范围验证
                if param_def.get("min") and user_value < param_def["min"]:
                    raise ValueError(f"参数 {param_name} 不能小于 {param_def['min']}")
                if param_def.get("max") and user_value > param_def["max"]:
                    raise ValueError(f"参数 {param_name} 不能大于 {param_def['max']}")

            elif param_type == "number":
                if not isinstance(user_value, (int, float)):
                    try:
                        user_value = float(user_value)
                    except (ValueError, TypeError):
                        raise ValueError(f"参数 {param_name} 必须是数字")

                if param_def.get("min") and user_value < param_def["min"]:
                    raise ValueError(f"参数 {param_name} 不能小于 {param_def['min']}")
                if param_def.get("max") and user_value > param_def["max"]:
                    raise ValueError(f"参数 {param_name} 不能大于 {param_def['max']}")

            elif param_type == "string":
                if not isinstance(user_value, str):
                    user_value = str(user_value)

                # 选项验证
                options = param_def.get("options")
                if options and user_value not in options:
                    raise ValueError(f"参数 {param_name} 必须是以下选项之一: {options}")

            validated[param_name] = user_value

        return validated

    # ============ 用户策略 ============

    async def create_user_strategy(
        self,
        user_id: UUID,
        template_id: UUID,
        name: str,
        parameters: Dict,
    ) -> UserStrategy:
        """
        创建用户策略

        Args:
            user_id: 用户ID
            template_id: 策略模板ID
            name: 策略名称
            parameters: 策略参数

        Returns:
            用户策略
        """
        template = await self.get_template_by_id(template_id)
        if not template:
            raise ValueError("策略模板不存在")

        # 验证参数
        validated_params = await self.validate_parameters(template, parameters)

        strategy = UserStrategy(
            user_id=user_id,
            template_id=template_id,
            name=name,
            parameters=validated_params,
        )
        self.session.add(strategy)
        await self.session.flush()

        return strategy

    async def get_user_strategies(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UserStrategy]:
        """获取用户策略列表"""
        query = select(UserStrategy).where(UserStrategy.user_id == user_id)
        query = query.order_by(desc(UserStrategy.updated_at)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_strategy_by_id(
        self,
        strategy_id: UUID,
        user_id: UUID,
    ) -> Optional[UserStrategy]:
        """获取用户策略（验证所有权）"""
        result = await self.session.execute(
            select(UserStrategy).where(
                and_(
                    UserStrategy.id == strategy_id,
                    UserStrategy.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_user_strategy(
        self,
        strategy_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        parameters: Optional[Dict] = None,
    ) -> Optional[UserStrategy]:
        """更新用户策略"""
        strategy = await self.get_user_strategy_by_id(strategy_id, user_id)
        if not strategy:
            return None

        if name:
            strategy.name = name

        if parameters:
            template = await self.get_template_by_id(strategy.template_id)
            validated_params = await self.validate_parameters(template, parameters)
            strategy.parameters = validated_params

        strategy.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        return strategy

    async def delete_user_strategy(
        self,
        strategy_id: UUID,
        user_id: UUID,
    ) -> bool:
        """删除用户策略"""
        strategy = await self.get_user_strategy_by_id(strategy_id, user_id)
        if not strategy:
            return False

        await self.session.delete(strategy)
        await self.session.flush()
        return True

    # ============ 回测任务 ============

    async def create_backtest_job(
        self,
        user_id: UUID,
        strategy_id: UUID,
        config: Dict,
    ) -> BacktestJob:
        """
        创建回测任务

        Args:
            user_id: 用户ID
            strategy_id: 策略ID
            config: 回测配置（资产、时间范围、初始资金等）

        Returns:
            回测任务
        """
        # 验证策略所有权
        strategy = await self.get_user_strategy_by_id(strategy_id, user_id)
        if not strategy:
            raise ValueError("策略不存在或不属于该用户")

        job = BacktestJob(
            user_id=user_id,
            strategy_id=strategy_id,
            status="pending",
            config=config,
        )
        self.session.add(job)
        await self.session.flush()

        logger.info(f"创建回测任务: {job.id}")
        return job

    async def get_backtest_jobs(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BacktestJob]:
        """获取用户回测任务列表"""
        query = select(BacktestJob).where(BacktestJob.user_id == user_id)

        if status:
            query = query.where(BacktestJob.status == status)

        query = query.order_by(desc(BacktestJob.created_at)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_backtest_job_by_id(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> Optional[BacktestJob]:
        """获取回测任务（验证所有权）"""
        result = await self.session.execute(
            select(BacktestJob).where(
                and_(
                    BacktestJob.id == job_id,
                    BacktestJob.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_backtest_result(self, job_id: UUID) -> Optional[BacktestResult]:
        """获取回测结果"""
        result = await self.session.execute(
            select(BacktestResult).where(BacktestResult.job_id == job_id)
        )
        return result.scalar_one_or_none()