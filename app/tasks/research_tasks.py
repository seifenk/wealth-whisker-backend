"""
研究结论自动化任务模块

负责定期生成研究结论、创建预测、更新实际值、触发校准
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
import asyncio

from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.asset import Asset
from app.models.research import ResearchCard, ModelPrediction
from app.services.research_service import ResearchService, PredictionService, CalibrationService


# ==================== 核心任务 ====================

@celery_app.task(bind=True, name="generate_research_cards")
def generate_research_cards_task(self, asset_type: Optional[str] = None):
    """
    定期生成研究结论卡片

    Args:
        asset_type: 资产类型过滤（crypto/stock/fund/gold），None表示生成所有活跃资产

    Returns:
        dict: 包含生成数量和状态的统计信息
    """
    logger.info(f"Starting research cards generation task: {self.request.id}")

    async def _generate():
        async with async_session_maker() as session:
            # 查询活跃资产
            query = select(Asset).where(Asset.is_active == True)
            if asset_type:
                query = query.where(Asset.asset_type == asset_type)

            result = await session.execute(query)
            assets = result.scalars().all()

            if not assets:
                logger.warning("No active assets found")
                return {
                    "status": "completed",
                    "generated_count": 0,
                    "total_assets": 0,
                    "message": "No active assets found"
                }

            generated_count = 0
            skipped_count = 0
            error_count = 0

            for asset in assets:
                try:
                    # 检查是否已有最近的研究卡片（24小时内有效）
                    recent_card = await session.execute(
                        select(ResearchCard)
                        .where(and_(
                            ResearchCard.asset_id == asset.id,
                            ResearchCard.valid_until >= datetime.now(timezone.utc)
                        ))
                        .order_by(desc(ResearchCard.created_at))
                        .limit(1)
                    )
                    recent_card = recent_card.scalar_one_or_none()

                    # 如果已有有效卡片，跳过
                    if recent_card:
                        logger.debug(f"Skipping {asset.symbol}: recent card exists until {recent_card.valid_until}")
                        skipped_count += 1
                        continue

                    # 生成新的研究卡片
                    card = await ResearchService.generate_research_card(session, asset.id)
                    generated_count += 1
                    logger.info(f"Generated research card for {asset.symbol}: {card.title}")

                except Exception as e:
                    logger.error(f"Failed to generate card for {asset.symbol}: {e}")
                    error_count += 1
                    continue

            await session.commit()
            logger.info(
                f"Research cards generation completed: "
                f"generated={generated_count}, skipped={skipped_count}, errors={error_count}"
            )

            return {
                "status": "completed",
                "generated_count": generated_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "total_assets": len(assets)
            }

    return asyncio.run(_generate())


@celery_app.task(bind=True, name="create_model_predictions")
def create_model_predictions_task(self, asset_type: Optional[str] = None):
    """
    定期创建模型预测

    为每个资产创建新的价格预测
    预测周期：
    - 加密货币：短期预测（3天后）
    - 股票/基金/黄金：中期预测（7天后）

    Args:
        asset_type: 资产类型过滤，None表示创建所有活跃资产的预测

    Returns:
        dict: 包含创建数量和状态的统计信息
    """
    logger.info(f"Starting model predictions creation task: {self.request.id}")

    async def _create_predictions():
        async with async_session_maker() as session:
            # 查询活跃资产
            query = select(Asset).where(Asset.is_active == True)
            if asset_type:
                query = query.where(Asset.asset_type == asset_type)

            result = await session.execute(query)
            assets = result.scalars().all()

            if not assets:
                logger.warning("No active assets found")
                return {
                    "status": "completed",
                    "created_count": 0,
                    "total_assets": 0,
                    "message": "No active assets found"
                }

            created_count = 0
            skipped_count = 0
            error_count = 0

            for asset in assets:
                try:
                    # 确定预测目标日期和类型
                    if asset.asset_type == "crypto":
                        target_date = date.today() + timedelta(days=3)
                        prediction_type = "price_short"
                    else:
                        target_date = date.today() + timedelta(days=7)
                        prediction_type = "price_mid"

                    # 检查是否已有相同目标日期的预测
                    existing = await session.execute(
                        select(ModelPrediction)
                        .where(and_(
                            ModelPrediction.asset_id == asset.id,
                            ModelPrediction.target_date == target_date,
                            ModelPrediction.prediction_type == prediction_type
                        ))
                    )
                    if existing.scalar_one_or_none():
                        logger.debug(
                            f"Skipping {asset.symbol}: prediction exists for {target_date}"
                        )
                        skipped_count += 1
                        continue

                    # 创建预测
                    prediction = await PredictionService.create_prediction(
                        db=session,
                        asset_id=asset.id,
                        prediction_type=prediction_type,
                        target_date=target_date,
                        model_version="v1.0"
                    )
                    created_count += 1
                    logger.info(
                        f"Created prediction for {asset.symbol}: "
                        f"target={target_date}, predicted={prediction.predicted_value}"
                    )

                except Exception as e:
                    logger.error(f"Failed to create prediction for {asset.symbol}: {e}")
                    error_count += 1
                    continue

            await session.commit()
            logger.info(
                f"Predictions creation completed: "
                f"created={created_count}, skipped={skipped_count}, errors={error_count}"
            )

            return {
                "status": "completed",
                "created_count": created_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "total_assets": len(assets)
            }

    return asyncio.run(_create_predictions())


@celery_app.task(bind=True, name="update_prediction_actuals")
def update_prediction_actuals_task(self):
    """
    定期更新预测的实际值

    执行逻辑：
    1. 查询所有已到期但未更新实际值的预测
    2. 获取当前价格作为实际值
    3. 计算偏差并标记是否触发校准

    Returns:
        dict: 包含更新数量和触发校准数量的统计信息
    """
    logger.info(f"Starting prediction actuals update task: {self.request.id}")

    async def _update_actuals():
        async with async_session_maker() as session:
            # 查询已到期但未更新实际值的预测
            today = date.today()
            predictions = await session.execute(
                select(ModelPrediction)
                .where(and_(
                    ModelPrediction.target_date <= today,
                    ModelPrediction.actual_value.is_(None)
                ))
            )
            predictions = predictions.scalars().all()

            if not predictions:
                logger.info("No expired predictions found")
                return {
                    "status": "completed",
                    "updated_count": 0,
                    "calibration_triggered": 0,
                    "message": "No expired predictions found"
                }

            updated_count = 0
            calibration_triggered_count = 0
            error_count = 0

            for prediction in predictions:
                try:
                    # 获取当前价格作为实际值
                    from app.services.asset_service import get_latest_price
                    actual_price = await get_latest_price(session, prediction.asset_id)

                    if not actual_price:
                        logger.warning(
                            f"No price data for asset {prediction.asset_id}, skipping"
                        )
                        error_count += 1
                        continue

                    # 更新实际值（内部会计算偏差和判断是否触发校准）
                    updated_pred = await PredictionService.update_actual_value(
                        db=session,
                        prediction_id=prediction.id,
                        actual_value=actual_price
                    )

                    updated_count += 1

                    if updated_pred.calibration_triggered:
                        calibration_triggered_count += 1
                        logger.info(
                            f"Calibration triggered for asset {prediction.asset_id}: "
                            f"deviation={updated_pred.deviation:.2f}% exceeds threshold"
                        )

                except Exception as e:
                    logger.error(f"Failed to update prediction {prediction.id}: {e}")
                    error_count += 1
                    continue

            await session.commit()
            logger.info(
                f"Actuals update completed: "
                f"updated={updated_count}, calibration_triggered={calibration_triggered_count}, "
                f"errors={error_count}"
            )

            return {
                "status": "completed",
                "updated_count": updated_count,
                "calibration_triggered": calibration_triggered_count,
                "error_count": error_count,
                "total_expired": len(predictions)
            }

    return asyncio.run(_update_actuals())


@celery_app.task(bind=True, name="auto_calibrate_models")
def auto_calibrate_models_task(self):
    """
    自动触发模型校准

    执行逻辑：
    1. 查询所有标记为 calibration_triggered=True 的预测
    2. 按资产分组
    3. 执行校准逻辑
    4. 重置触发标记

    Returns:
        dict: 包含校准数量和状态的统计信息
    """
    logger.info(f"Starting auto calibration task: {self.request.id}")

    async def _calibrate():
        async with async_session_maker() as session:
            # 查询触发校准的预测记录
            triggered_predictions = await session.execute(
                select(ModelPrediction)
                .where(ModelPrediction.calibration_triggered == True)
            )
            triggered_predictions = triggered_predictions.scalars().all()

            if not triggered_predictions:
                logger.info("No calibration triggered")
                return {
                    "status": "completed",
                    "calibrated_count": 0,
                    "triggered_assets": 0,
                    "message": "No calibration triggered"
                }

            # 按资产分组
            asset_ids = set(p.asset_id for p in triggered_predictions)
            logger.info(f"Found {len(asset_ids)} assets requiring calibration")

            calibrated_count = 0
            error_count = 0

            for asset_id in asset_ids:
                try:
                    # 执行校准
                    log = await CalibrationService.check_and_calibrate(session, asset_id)

                    if log:
                        calibrated_count += 1
                        logger.info(
                            f"Calibration completed for asset {asset_id}: "
                            f"before={log.performance_before}, after={log.performance_after}"
                        )
                    else:
                        logger.debug(f"No calibration executed for asset {asset_id}")

                except Exception as e:
                    logger.error(f"Failed to calibrate asset {asset_id}: {e}")
                    error_count += 1
                    continue

            await session.commit()
            logger.info(
                f"Auto calibration completed: "
                f"calibrated={calibrated_count}, errors={error_count}, "
                f"triggered_assets={len(asset_ids)}"
            )

            return {
                "status": "completed",
                "calibrated_count": calibrated_count,
                "error_count": error_count,
                "triggered_assets": len(asset_ids)
            }

    return asyncio.run(_calibrate())


# ==================== 定时调度包装任务 ====================

@celery_app.task(name="scheduled_research_generation_crypto")
def scheduled_research_generation_crypto():
    """
    加密货币研究结论定时生成（每4小时）

    符合PRD中加密货币4小时滑动窗口校准机制要求
    """
    logger.info("Executing scheduled research generation for crypto assets")
    return generate_research_cards_task(asset_type="crypto")


@celery_app.task(name="scheduled_research_generation_stock")
def scheduled_research_generation_stock():
    """
    股票研究结论定时生成（每日17:00 UTC）

    符合PRD中股票T+1盘后批量校准机制要求
    """
    logger.info("Executing scheduled research generation for stock assets")
    return generate_research_cards_task(asset_type="stock")


@celery_app.task(name="scheduled_research_generation_fund")
def scheduled_research_generation_fund():
    """
    基金研究结论定时生成（每日15:30 北京时间）

    符合PRD中基金T+1盘后批量校准机制要求
    """
    logger.info("Executing scheduled research generation for fund assets")
    return generate_research_cards_task(asset_type="fund")


@celery_app.task(name="scheduled_research_generation_gold")
def scheduled_research_generation_gold():
    """
    黄金研究结论定时生成（每日）

    黄金市场收盘后生成
    """
    logger.info("Executing scheduled research generation for gold assets")
    return generate_research_cards_task(asset_type="gold")


@celery_app.task(name="scheduled_prediction_creation_crypto")
def scheduled_prediction_creation_crypto():
    """
    加密货币预测定时创建（每4小时）

    研究生成后15分钟执行，创建短期预测
    """
    logger.info("Executing scheduled prediction creation for crypto assets")
    return create_model_predictions_task(asset_type="crypto")


@celery_app.task(name="scheduled_prediction_creation_stock")
def scheduled_prediction_creation_stock():
    """
    股票预测定时创建（每日17:15 UTC）

    研究生成后15分钟执行，创建中期预测
    """
    logger.info("Executing scheduled prediction creation for stock assets")
    return create_model_predictions_task(asset_type="stock")


@celery_app.task(name="scheduled_prediction_creation_fund")
def scheduled_prediction_creation_fund():
    """
    基金预测定时创建（每日）

    创建中期预测
    """
    logger.info("Executing scheduled prediction creation for fund assets")
    return create_model_predictions_task(asset_type="fund")


@celery_app.task(name="scheduled_prediction_creation_gold")
def scheduled_prediction_creation_gold():
    """
    黄金预测定时创建（每日）

    创建中期预测
    """
    logger.info("Executing scheduled prediction creation for gold assets")
    return create_model_predictions_task(asset_type="gold")


@celery_app.task(name="scheduled_actuals_update")
def scheduled_actuals_update():
    """
    定时更新预测实际值（每日执行）

    每日凌晨00:30 UTC执行，检查所有到期预测
    """
    logger.info("Executing scheduled prediction actuals update")
    return update_prediction_actuals_task()


@celery_app.task(name="scheduled_auto_calibration")
def scheduled_auto_calibration():
    """
    定时自动校准（每日执行）

    实际值更新后30分钟执行，处理所有触发校准的预测
    """
    logger.info("Executing scheduled auto calibration")
    return auto_calibrate_models_task()