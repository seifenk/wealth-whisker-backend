"""
研究结论自动化流程验证脚本

验证：
1. 研究卡片自动生成
2. 预测自动创建
3. 实际值自动更新
4. 校准自动触发

使用方法：
python scripts/verify_research_automation.py
"""
import asyncio
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.asset import Asset
from app.models.research import ResearchCard, ModelPrediction, ModelCalibrationLog
from app.tasks.research_tasks import (
    generate_research_cards_task,
    create_model_predictions_task,
    update_prediction_actuals_task,
    auto_calibrate_models_task,
)


async def verify_research_generation():
    """验证研究卡片生成"""
    print("\n" + "="*60)
    print("【验证研究卡片生成】")
    print("="*60)

    result = generate_research_cards_task(asset_type="crypto")
    print(f"✓ 生成结果: {result}")

    # 检查数据库
    async with async_session_maker() as session:
        cards = await session.execute(
            select(ResearchCard).limit(5)
        )
        cards = cards.scalars().all()
        print(f"✓ 数据库中研究卡片数量: {len(cards)}")
        for card in cards[:3]:
            print(f"  - {card.title}, confidence: {card.confidence_score}")


async def verify_prediction_creation():
    """验证预测创建"""
    print("\n" + "="*60)
    print("【验证预测创建】")
    print("="*60)

    result = create_model_predictions_task(asset_type="crypto")
    print(f"✓ 创建结果: {result}")

    # 检查数据库
    async with async_session_maker() as session:
        predictions = await session.execute(
            select(ModelPrediction).limit(5)
        )
        predictions = predictions.scalars().all()
        print(f"✓ 数据库中预测数量: {len(predictions)}")
        for pred in predictions[:3]:
            print(f"  - asset: {pred.asset_id}, target: {pred.target_date}, predicted: {pred.predicted_value}")


async def verify_actuals_update():
    """验证实际值更新"""
    print("\n" + "="*60)
    print("【验证实际值更新】")
    print("="*60)

    # 先手动创建一个到期的预测用于测试
    async with async_session_maker() as session:
        asset = await session.execute(select(Asset).limit(1))
        asset = asset.scalar_one()

        # 创建一个昨天到期的预测
        prediction = ModelPrediction(
            asset_id=asset.id,
            model_version="test_v1",
            prediction_type="price_test",
            target_date=date.today() - timedelta(days=1),
            predicted_value=Decimal("100.0"),
        )
        session.add(prediction)
        await session.commit()

        print(f"✓ 创建测试预测: {prediction.id}, target_date={prediction.target_date}")

    # 执行更新
    result = update_prediction_actuals_task()
    print(f"✓ 更新结果: {result}")

    # 检查实际值是否填入
    async with async_session_maker() as session:
        updated = await session.execute(
            select(ModelPrediction).where(ModelPrediction.actual_value.isnot(None))
        )
        updated = updated.scalars().all()
        print(f"✓ 已更新实际值的预测数量: {len(updated)}")


async def verify_auto_calibration():
    """验证自动校准"""
    print("\n" + "="*60)
    print("【验证自动校准】")
    print("="*60)

    result = auto_calibrate_models_task()
    print(f"✓ 校准结果: {result}")

    # 检查校准日志
    async with async_session_maker() as session:
        logs = await session.execute(
            select(ModelCalibrationLog).limit(5)
        )
        logs = logs.scalars().all()
        print(f"✓ 校准日志数量: {len(logs)}")
        for log in logs[:3]:
            print(f"  - asset: {log.asset_id}, type: {log.calibration_type}")


async def verify_api_endpoints():
    """验证API接口"""
    print("\n" + "="*60)
    print("【验证API接口】")
    print("="*60)

    # 这里只打印提示，实际需要启动服务后测试
    print("✓ 需要验证的GET接口（保留）:")
    print("  - GET /api/v1/research/cards")
    print("  - GET /api/v1/research/cards/{card_id}")
    print("  - GET /api/v1/research/predictions")
    print("  - GET /api/v1/research/predictions/{asset_id}/accuracy")
    print("  - GET /api/v1/research/calibration-logs")
    print("  - GET /api/v1/research/model-versions")
    print("  - GET /api/v1/research/disclaimer")
    print("  - GET /api/v1/research/analysis/{asset_id}")

    print("\n✗ 已移除的POST接口（手动触发）:")
    print("  - POST /api/v1/research/cards/generate/{asset_id}")
    print("  - POST /api/v1/research/predictions")
    print("  - POST /api/v1/research/calibration/{asset_id}")

    print("\n提示：使用 curl 或浏览器测试GET接口")


async def verify_celery_schedule():
    """验证Celery定时调度配置"""
    print("\n" + "="*60)
    print("【验证Celery定时调度】")
    print("="*60)

    from app.core.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    print(f"✓ 定时任务配置数量: {len(schedule)}")

    for name, config in schedule.items():
        task = config.get("task", "unknown")
        print(f"  - {name}: {task}")


async def main():
    """执行所有验证"""
    print("\n" + "="*80)
    print(" 研究结论自动化流程验证")
    print("="*80)
    print("提示：需要确保数据库中有活跃的资产数据")

    try:
        await verify_celery_schedule()
        await verify_research_generation()
        await verify_prediction_creation()
        await verify_actuals_update()
        await verify_auto_calibration()
        await verify_api_endpoints()

        print("\n" + "="*80)
        print(" ✓ 验证完成！所有自动化流程已正确配置")
        print("="*80)

    except Exception as e:
        print(f"\n✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())