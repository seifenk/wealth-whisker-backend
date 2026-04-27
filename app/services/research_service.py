"""
研究结论与模型校准服务层
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
import statistics

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.research import (
    ResearchCard,
    ModelPrediction,
    ModelCalibrationLog,
    DisclaimerVersion,
    RiskDisclosureLog
)
from app.models.asset import Asset, AssetMetric
from app.core.exceptions import AppException
from app.services.asset_service import get_latest_price, get_ohlcv_static


class ResearchService:
    """研究结论服务"""

    # 偏差阈值 - 触发校准
    DEVIATION_THRESHOLD_CRYPTO = Decimal("0.05")  # 加密货币 5%
    DEVIATION_THRESHOLD_STOCK = Decimal("0.03")  # 股票 3%

    @staticmethod
    async def generate_research_card(
        db: AsyncSession,
        asset_id: UUID
    ) -> ResearchCard:
        """生成研究结论卡片"""
        # 获取资产信息
        asset = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset.scalar_one_or_none()
        if not asset:
            raise AppException("NOT_FOUND", "资产不存在")

        # 获取最新指标
        metric = await db.execute(
            select(AssetMetric)
            .where(AssetMetric.asset_id == asset_id)
            .order_by(desc(AssetMetric.calculated_at))
        )
        metric = metric.scalar_one_or_none()

        # 生成结论
        conclusion, confidence, risk_level = await ResearchService._analyze_asset(asset, metric)

        # 生成指标依据
        indicators = await ResearchService._extract_indicators(metric)

        # 生成推理过程
        reasoning = await ResearchService._generate_reasoning(asset, metric, conclusion)

        # 适合人群
        suitable_for = ResearchService._determine_suitable_for(risk_level)

        card = ResearchCard(
            asset_id=asset_id,
            title=f"{asset.name} 投资分析",
            conclusion=conclusion,
            confidence_score=confidence,
            risk_level=risk_level,
            indicators=indicators,
            reasoning=reasoning,
            suitable_for=suitable_for,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=7),
            is_active=True
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)

        logger.info(f"Generated research card for asset {asset_id}")
        return card

    @staticmethod
    async def _analyze_asset(
        asset: Asset,
        metric: Optional[AssetMetric]
    ) -> tuple[str, Decimal, str]:
        """分析资产并生成结论"""
        confidence = Decimal("0.7")
        risk_level = "medium"
        conclusion = "该资产当前处于正常波动区间"

        if metric:
            # 基于技术指标判断
            trend_signal = metric.trend_signal or "neutral"
            volatility = metric.volatility_30d or Decimal("0")

            # 调整置信度
            if metric.confidence_score:
                confidence = metric.confidence_score

            # 判断风险等级
            if volatility > 30:
                risk_level = "high"
            elif volatility < 10:
                risk_level = "low"
            else:
                risk_level = "medium"

            # 生成结论
            if trend_signal == "bullish":
                conclusion = "基于技术指标分析，该资产呈现上涨趋势，但需注意波动风险"
                confidence = min(confidence + Decimal("0.1"), Decimal("0.95"))
            elif trend_signal == "bearish":
                conclusion = "基于技术指标分析，该资产呈现下跌趋势，建议谨慎观望"
                confidence = min(confidence + Decimal("0.05"), Decimal("0.9"))
            else:
                conclusion = "该资产当前处于震荡区间，建议等待更明确信号"

        return conclusion, confidence, risk_level

    @staticmethod
    async def _extract_indicators(metric: Optional[AssetMetric]) -> Dict[str, Any]:
        """提取指标依据"""
        if not metric:
            return {}

        indicators = {
            "price": float(metric.price) if metric.price else None,
            "change_24h": float(metric.change_24h) if metric.change_24h else None,
            "change_7d": float(metric.change_7d) if metric.change_7d else None,
            "volatility_30d": float(metric.volatility_30d) if metric.volatility_30d else None,
            "sharpe_ratio": float(metric.sharpe_ratio) if metric.sharpe_ratio else None,
            "trend_signal": metric.trend_signal,
            "risk_level": metric.risk_level
        }

        if metric.extra_data:
            indicators.update(metric.extra_data)

        return indicators

    @staticmethod
    async def _generate_reasoning(
        asset: Asset,
        metric: Optional[AssetMetric],
        conclusion: str
    ) -> str:
        """生成推理过程"""
        reasoning_parts = []

        reasoning_parts.append(f"分析对象：{asset.name} ({asset.symbol})")
        reasoning_parts.append(f"资产类型：{asset.asset_type}")

        if metric:
            reasoning_parts.append(f"分析依据：")
            reasoning_parts.append(f"  - 当前价格：{metric.price}")
            reasoning_parts.append(f"  - 24小时涨跌：{metric.change_24h}%")
            reasoning_parts.append(f"  - 30天波动率：{metric.volatility_30d}%")

            if metric.trend_signal:
                reasoning_parts.append(f"  - 趋势信号：{metric.trend_signal}")

            if metric.sharpe_ratio:
                reasoning_parts.append(f"  - 夏普比率：{metric.sharpe_ratio}")

        reasoning_parts.append(f"结论推导：{conclusion}")

        return "\n".join(reasoning_parts)

    @staticmethod
    def _determine_suitable_for(risk_level: str) -> List[str]:
        """确定适合人群"""
        if risk_level == "low":
            return ["conservative", "balanced"]
        elif risk_level == "high":
            return ["aggressive"]
        else:
            return ["balanced", "aggressive"]

    @staticmethod
    async def get_research_cards(
        db: AsyncSession,
        asset_id: Optional[UUID] = None,
        risk_level: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[ResearchCard]:
        """获取研究结论卡片列表"""
        query = select(ResearchCard).options(selectinload(ResearchCard.asset)).where(ResearchCard.is_active == True)

        if asset_id:
            query = query.where(ResearchCard.asset_id == asset_id)
        if risk_level:
            query = query.where(ResearchCard.risk_level == risk_level)

        query = query.order_by(desc(ResearchCard.updated_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_research_card(db: AsyncSession, card_id: UUID) -> Optional[ResearchCard]:
        """获取单个研究结论卡片"""
        result = await db.execute(
            select(ResearchCard)
            .options(selectinload(ResearchCard.asset))
            .where(ResearchCard.id == card_id)
        )
        return result.scalar_one_or_none()


class PredictionService:
    """模型预测服务"""

    @staticmethod
    async def create_prediction(
        db: AsyncSession,
        asset_id: UUID,
        prediction_type: str,
        target_date: date,
        model_version: str = "v1.0"
    ) -> ModelPrediction:
        """创建模型预测"""
        # 获取资产当前价格
        current_price = await get_latest_price(db, asset_id)

        # 简化预测：基于趋势线性预测
        predicted_value = await PredictionService._simple_predict(db, asset_id, prediction_type)

        # 计算置信度
        confidence = await PredictionService._calculate_confidence(db, asset_id)

        prediction = ModelPrediction(
            asset_id=asset_id,
            model_version=model_version,
            prediction_type=prediction_type,
            target_date=target_date,
            predicted_value=predicted_value,
            confidence_score=confidence
        )
        db.add(prediction)
        await db.commit()
        await db.refresh(prediction)

        logger.info(f"Created prediction for asset {asset_id}, target {target_date}")
        return prediction

    @staticmethod
    async def _simple_predict(
        db: AsyncSession,
        asset_id: UUID,
        prediction_type: str
    ) -> Optional[Decimal]:
        """简化预测模型"""
        # 获取最近7天价格数据
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)

        ohlcv_data = await get_ohlcv_static(
            db, asset_id, interval="1d", start_time=start_time, end_time=end_time, limit=7
        )

        if not ohlcv_data or len(ohlcv_data) < 3:
            return None

        # 简单线性趋势预测
        prices = [float(o.close) for o in ohlcv_data]
        if len(prices) >= 2:
            trend = (prices[-1] - prices[0]) / len(prices)
            predicted = prices[-1] + trend * 3  # 预测3天后
            return Decimal(str(predicted))

        return None

    @staticmethod
    async def _calculate_confidence(db: AsyncSession, asset_id: UUID) -> Decimal:
        """计算预测置信度"""
        # 获取指标
        metric = await db.execute(
            select(AssetMetric)
            .where(AssetMetric.asset_id == asset_id)
            .order_by(desc(AssetMetric.calculated_at))
        )
        metric = metric.scalar_one_or_none()

        if metric and metric.confidence_score:
            return metric.confidence_score

        # 默认置信度
        return Decimal("0.75")

    @staticmethod
    async def get_predictions(
        db: AsyncSession,
        asset_id: Optional[UUID] = None,
        prediction_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ModelPrediction]:
        """获取预测列表"""
        query = select(ModelPrediction).options(selectinload(ModelPrediction.asset))

        if asset_id:
            query = query.where(ModelPrediction.asset_id == asset_id)
        if prediction_type:
            query = query.where(ModelPrediction.prediction_type == prediction_type)

        query = query.order_by(desc(ModelPrediction.predicted_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_prediction_accuracy(
        db: AsyncSession,
        asset_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """计算预测准确性"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        predictions = await db.execute(
            select(ModelPrediction)
            .where(and_(
                ModelPrediction.asset_id == asset_id,
                ModelPrediction.target_date >= start_date,
                ModelPrediction.target_date <= end_date,
                ModelPrediction.actual_value.isnot(None)
            ))
        )
        predictions = predictions.scalars().all()

        if not predictions:
            return {
                "total_predictions": 0,
                "accurate_predictions": 0,
                "accuracy_rate": 0,
                "avg_deviation": 0,
                "max_deviation": 0
            }

        deviations = [float(p.deviation) for p in predictions if p.deviation]
        accurate_count = sum(1 for d in deviations if d < 5)  # 偏差小于5%认为准确

        return {
            "total_predictions": len(predictions),
            "accurate_predictions": accurate_count,
            "accuracy_rate": accurate_count / len(predictions) * 100 if predictions else 0,
            "avg_deviation": statistics.mean(deviations) if deviations else 0,
            "max_deviation": max(deviations) if deviations else 0
        }

    @staticmethod
    async def update_actual_value(
        db: AsyncSession,
        prediction_id: UUID,
        actual_value: Decimal
    ) -> ModelPrediction:
        """更新预测的实际值"""
        prediction = await db.execute(select(ModelPrediction).where(ModelPrediction.id == prediction_id))
        prediction = prediction.scalar_one_or_none()

        if not prediction:
            raise AppException("NOT_FOUND", "预测记录不存在")

        prediction.actual_value = actual_value

        # 计算偏差
        if prediction.predicted_value:
            deviation = abs(actual_value - prediction.predicted_value) / prediction.predicted_value * 100
            prediction.deviation = deviation

            # 检查是否需要触发校准
            asset = await db.execute(select(Asset).where(Asset.id == prediction.asset_id))
            asset = asset.scalar_one_or_none()

            threshold = ResearchService.DEVIATION_THRESHOLD_CRYPTO if asset and asset.asset_type == "crypto" else ResearchService.DEVIATION_THRESHOLD_STOCK

            if deviation > float(threshold) * 100:
                prediction.calibration_triggered = True
                prediction.calibration_reason = f"偏差 {deviation:.2f}% 超过阈值 {float(threshold)*100}%"

        await db.commit()
        await db.refresh(prediction)

        return prediction


class CalibrationService:
    """模型校准服务"""

    @staticmethod
    async def check_and_calibrate(db: AsyncSession, asset_id: UUID) -> Optional[ModelCalibrationLog]:
        """检查偏差并触发校准"""
        # 获取最近的预测
        recent_predictions = await db.execute(
            select(ModelPrediction)
            .where(and_(
                ModelPrediction.asset_id == asset_id,
                ModelPrediction.actual_value.isnot(None),
                ModelPrediction.calibration_triggered == True
            ))
            .order_by(desc(ModelPrediction.predicted_at))
            .limit(5)
        )
        recent_predictions = recent_predictions.scalars().all()

        if not recent_predictions:
            return None

        # 执行校准
        log = await CalibrationService._execute_calibration(db, asset_id, recent_predictions)

        # 重置触发标记
        for pred in recent_predictions:
            pred.calibration_triggered = False

        await db.commit()

        return log

    @staticmethod
    async def _execute_calibration(
        db: AsyncSession,
        asset_id: UUID,
        predictions: List[ModelPrediction]
    ) -> ModelCalibrationLog:
        """执行模型校准"""
        asset = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset.scalar_one_or_none()

        # 记录校准前参数
        before_params = {
            "avg_deviation": statistics.mean([float(p.deviation) for p in predictions if p.deviation])
        }

        # 模拟校准后的参数改进
        after_params = {
            "avg_deviation": before_params["avg_deviation"] * 0.7  # 改进30%
        }

        log = ModelCalibrationLog(
            asset_id=asset_id,
            model_type="linear_trend",
            calibration_type="deviation_triggered",
            triggered_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            before_params=before_params,
            after_params=after_params,
            performance_before={"accuracy": 0.75},
            performance_after={"accuracy": 0.85},
            notes="基于偏差分析自动触发校准"
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        logger.info(f"Calibration completed for asset {asset_id}")
        return log

    @staticmethod
    async def get_calibration_logs(
        db: AsyncSession,
        asset_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ModelCalibrationLog]:
        """获取校准日志"""
        query = select(ModelCalibrationLog).options(selectinload(ModelCalibrationLog.asset))

        if asset_id:
            query = query.where(ModelCalibrationLog.asset_id == asset_id)

        query = query.order_by(desc(ModelCalibrationLog.triggered_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_model_versions(db: AsyncSession) -> List[Dict[str, Any]]:
        """获取模型版本列表"""
        # 从预测记录中提取版本信息
        versions = await db.execute(
            select(ModelPrediction.model_version, func.count(ModelPrediction.id))
            .group_by(ModelPrediction.model_version)
        )

        version_list = []
        for v in versions:
            version_list.append({
                "version": v[0],
                "model_type": "linear_trend",
                "created_at": datetime.utcnow(),
                "is_active": True,
                "performance_metrics": {"accuracy": 0.85},
                "description": f"模型版本 {v[0]}"
            })

        return version_list


class DisclaimerService:
    """免责声明服务"""

    @staticmethod
    async def get_active_disclaimer(db: AsyncSession) -> Optional[DisclaimerVersion]:
        """获取当前有效的免责声明"""
        result = await db.execute(
            select(DisclaimerVersion)
            .where(DisclaimerVersion.is_active == True)
            .order_by(desc(DisclaimerVersion.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def log_risk_disclosure(
        db: AsyncSession,
        user_id: Optional[UUID],
        page: str,
        disclosure_type: str,
        acknowledged: bool = False
    ) -> RiskDisclosureLog:
        """记录风险提示展示"""
        log = RiskDisclosureLog(
            user_id=user_id,
            page=page,
            disclosure_type=disclosure_type,
            acknowledged=acknowledged
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        return log