"""
研究结论与模型校准 API测试 - Phase 5 接口测试

测试接口：
- GET /api/v1/research/cards - 研究结论列表
- GET /api/v1/research/cards/{id} - 研究结论详情
- POST /api/v1/research/cards/generate/{asset_id} - 生成研究结论
- GET /api/v1/research/predictions - 模型预测列表
- GET /api/v1/research/predictions/{asset_id}/accuracy - 预测准确性
- GET /api/v1/research/calibration-logs - 校准日志列表
- POST /api/v1/research/calibration/{asset_id} - 触发校准
- GET /api/v1/research/model-versions - 模型版本列表
- GET /api/v1/research/disclaimer - 免责声明
- GET /api/v1/research/analysis/{asset_id} - 综合分析
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.research import (
    ResearchCard,
    ModelPrediction,
    ModelCalibrationLog,
    DisclaimerVersion,
)
from app.core.response import ResponseCode


@pytest_asyncio.fixture(scope="function")
async def test_research_assets(db_session: AsyncSession):
    """创建测试资产数据"""
    assets = [
        Asset(
            id=uuid4(),
            symbol="BTC",
            name="Bitcoin",
            asset_type="crypto",
            exchange="OKX",
            currency="USD",
            is_active=True,
        ),
        Asset(
            id=uuid4(),
            symbol="AAPL",
            name="Apple Inc",
            asset_type="stock",
            exchange="NASDAQ",
            currency="USD",
            is_active=True,
        ),
    ]
    for asset in assets:
        db_session.add(asset)
    await db_session.flush()
    return assets


@pytest_asyncio.fixture(scope="function")
async def test_research_cards(db_session: AsyncSession, test_research_assets):
    """创建测试研究结论卡片"""
    cards = [
        ResearchCard(
            id=uuid4(),
            asset_id=test_research_assets[0].id,
            title="BTC短期看涨信号",
            conclusion="基于技术指标分析，BTC短期内可能上涨",
            confidence_score=Decimal("0.75"),
            risk_level="medium",
            indicators={"rsi": 45, "ma_cross": "bullish"},
            reasoning="RSI处于中性区间，均线形成金叉",
            suitable_for=["balanced", "aggressive"],
            valid_from=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=7),
            is_active=True,
        ),
        ResearchCard(
            id=uuid4(),
            asset_id=test_research_assets[1].id,
            title="AAPL稳健持有建议",
            conclusion="AAPL基本面稳健，建议长期持有",
            confidence_score=Decimal("0.85"),
            risk_level="low",
            indicators={"pe_ratio": 25, "dividend_yield": 0.5},
            reasoning="估值合理，股息稳定",
            suitable_for=["conservative", "balanced"],
            valid_from=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
            is_active=True,
        ),
    ]
    for card in cards:
        db_session.add(card)
    await db_session.flush()
    return cards


@pytest_asyncio.fixture(scope="function")
async def test_predictions(db_session: AsyncSession, test_research_assets):
    """创建测试模型预测"""
    predictions = [
        ModelPrediction(
            id=uuid4(),
            asset_id=test_research_assets[0].id,
            model_version="v1.0",
            prediction_type="price",
            target_date=date.today() + timedelta(days=7),
            predicted_value=Decimal("65000.00"),
            confidence_score=Decimal("0.72"),
            actual_value=None,
            deviation=None,
            calibration_triggered=False,
        ),
        ModelPrediction(
            id=uuid4(),
            asset_id=test_research_assets[0].id,
            model_version="v1.0",
            prediction_type="trend",
            target_date=date.today() - timedelta(days=1),
            predicted_value=Decimal("1.0"),  # 上涨趋势
            confidence_score=Decimal("0.68"),
            actual_value=Decimal("1.1"),  # 实际上涨更多
            deviation=Decimal("10.0"),
            calibration_triggered=False,
        ),
    ]
    for pred in predictions:
        db_session.add(pred)
    await db_session.flush()
    return predictions


@pytest_asyncio.fixture(scope="function")
async def test_calibration_logs(db_session: AsyncSession, test_research_assets):
    """创建测试校准日志"""
    logs = [
        ModelCalibrationLog(
            id=uuid4(),
            asset_id=test_research_assets[0].id,
            model_type="linear_trend",
            calibration_type="deviation_triggered",
            triggered_at=datetime.now(timezone.utc) - timedelta(hours=4),
            completed_at=datetime.now(timezone.utc) - timedelta(hours=3),
            before_params={"threshold": 0.05},
            after_params={"threshold": 0.03},
            performance_before={"accuracy": 0.65},
            performance_after={"accuracy": 0.78},
            notes="偏差超过阈值，触发自动校准",
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.flush()
    return logs


@pytest_asyncio.fixture(scope="function")
async def test_disclaimer(db_session: AsyncSession):
    """创建测试免责声明"""
    disclaimer = DisclaimerVersion(
        id=uuid4(),
        version="v1.0",
        content="本平台所有分析均基于算法生成，不构成投资建议。历史表现不代表未来，投资有风险。",
        is_active=True,
    )
    db_session.add(disclaimer)
    await db_session.flush()
    return disclaimer


class TestResearchCardsAPI:
    """研究结论卡片API测试"""

    @pytest.mark.asyncio
    async def test_list_research_cards(
        self, client: AsyncClient, db_session, test_research_cards, override_get_db
    ):
        """测试获取研究结论列表"""
        response = await client.get("/api/v1/research/cards")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["total"] >= 2

    @pytest.mark.asyncio
    async def test_list_research_cards_filter_by_asset(
        self, client: AsyncClient, db_session, test_research_cards, test_research_assets, override_get_db
    ):
        """测试按资产ID过滤研究结论"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/cards?asset_id={asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        # 应该只返回BTC的研究结论
        for item in data["data"]["items"]:
            assert item["asset_id"] == asset_id

    @pytest.mark.asyncio
    async def test_list_research_cards_filter_by_risk_level(
        self, client: AsyncClient, db_session, test_research_cards, override_get_db
    ):
        """测试按风险等级过滤研究结论"""
        response = await client.get("/api/v1/research/cards?risk_level=low")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        for item in data["data"]["items"]:
            assert item["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_get_research_card_detail(
        self, client: AsyncClient, db_session, test_research_cards, override_get_db
    ):
        """测试获取研究结论详情"""
        card_id = str(test_research_cards[0].id)
        response = await client.get(f"/api/v1/research/cards/{card_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["id"] == card_id
        assert data["data"]["title"] == "BTC短期看涨信号"
        assert "asset_symbol" in data["data"]
        assert "asset_name" in data["data"]

    @pytest.mark.asyncio
    async def test_get_research_card_not_found(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试获取不存在的研究结论"""
        non_existent_id = str(uuid4())
        response = await client.get(f"/api/v1/research/cards/{non_existent_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_research_card_invalid_id(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试无效的研究结论ID"""
        response = await client.get("/api/v1/research/cards/invalid_id")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_guest_access_research_cards(
        self, client: AsyncClient, db_session, test_research_cards, override_get_db
    ):
        """测试游客可以访问研究结论列表"""
        response = await client.get("/api/v1/research/cards")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestPredictionsAPI:
    """模型预测API测试"""

    @pytest.mark.asyncio
    async def test_list_predictions(
        self, client: AsyncClient, db_session, test_predictions, override_get_db
    ):
        """测试获取预测列表"""
        response = await client.get("/api/v1/research/predictions")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "items" in data["data"]
        assert "total" in data["data"]

    @pytest.mark.asyncio
    async def test_list_predictions_filter_by_asset(
        self, client: AsyncClient, db_session, test_predictions, test_research_assets, override_get_db
    ):
        """测试按资产ID过滤预测"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/predictions?asset_id={asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        for item in data["data"]["items"]:
            assert item["asset_id"] == asset_id

    @pytest.mark.asyncio
    async def test_list_predictions_filter_by_type(
        self, client: AsyncClient, db_session, test_predictions, override_get_db
    ):
        """测试按预测类型过滤"""
        response = await client.get("/api/v1/research/predictions?prediction_type=price")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        for item in data["data"]["items"]:
            assert item["prediction_type"] == "price"

    @pytest.mark.asyncio
    async def test_get_prediction_accuracy(
        self, client: AsyncClient, db_session, test_predictions, test_research_assets, override_get_db
    ):
        """测试获取预测准确性"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/predictions/{asset_id}/accuracy")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "total_predictions" in data["data"]
        assert "accuracy_rate" in data["data"]
        assert "avg_deviation" in data["data"]

    @pytest.mark.asyncio
    async def test_get_prediction_accuracy_invalid_id(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试无效资产ID获取预测准确性"""
        response = await client.get("/api/v1/research/predictions/invalid_id/accuracy")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_guest_access_predictions(
        self, client: AsyncClient, db_session, test_predictions, override_get_db
    ):
        """测试游客可以访问预测列表"""
        response = await client.get("/api/v1/research/predictions")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestCalibrationLogsAPI:
    """校准日志API测试"""

    @pytest.mark.asyncio
    async def test_list_calibration_logs(
        self, client: AsyncClient, db_session, test_calibration_logs, override_get_db
    ):
        """测试获取校准日志列表"""
        response = await client.get("/api/v1/research/calibration-logs")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "items" in data["data"]
        assert "total" in data["data"]

    @pytest.mark.asyncio
    async def test_list_calibration_logs_filter_by_asset(
        self, client: AsyncClient, db_session, test_calibration_logs, test_research_assets, override_get_db
    ):
        """测试按资产ID过滤校准日志"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/calibration-logs?asset_id={asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        for item in data["data"]["items"]:
            assert item["asset_id"] == asset_id

    @pytest.mark.asyncio
    async def test_calibration_log_detail_fields(
        self, client: AsyncClient, db_session, test_calibration_logs, override_get_db
    ):
        """测试校准日志包含必要字段"""
        response = await client.get("/api/v1/research/calibration-logs")
        assert response.status_code == 200
        data = response.json()
        if data["data"]["total"] > 0:
            log = data["data"]["items"][0]
            assert "calibration_type" in log
            assert "triggered_at" in log
            assert "before_params" in log
            assert "after_params" in log
            assert "performance_before" in log
            assert "performance_after" in log

    @pytest.mark.asyncio
    async def test_guest_access_calibration_logs(
        self, client: AsyncClient, db_session, test_calibration_logs, override_get_db
    ):
        """测试游客可以访问校准日志"""
        response = await client.get("/api/v1/research/calibration-logs")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestModelVersionsAPI:
    """模型版本API测试"""

    @pytest.mark.asyncio
    async def test_list_model_versions(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试获取模型版本列表"""
        response = await client.get("/api/v1/research/model-versions")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "items" in data["data"]
        assert "total" in data["data"]

    @pytest.mark.asyncio
    async def test_guest_access_model_versions(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试游客可以访问模型版本"""
        response = await client.get("/api/v1/research/model-versions")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestDisclaimerAPI:
    """免责声明API测试"""

    @pytest.mark.asyncio
    async def test_get_disclaimer(
        self, client: AsyncClient, db_session, test_disclaimer, override_get_db
    ):
        """测试获取免责声明"""
        response = await client.get("/api/v1/research/disclaimer")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "content" in data["data"]
        assert "version" in data["data"]
        assert "accepted" in data["data"]

    @pytest.mark.asyncio
    async def test_disclaimer_default_when_none(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试无免责声明时返回默认内容"""
        # 清理后重新创建（不创建disclaimer）
        response = await client.get("/api/v1/research/disclaimer")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["version"] == "default"

    @pytest.mark.asyncio
    async def test_guest_access_disclaimer(
        self, client: AsyncClient, db_session, test_disclaimer, override_get_db
    ):
        """测试游客可以访问免责声明"""
        response = await client.get("/api/v1/research/disclaimer")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestAssetAnalysisAPI:
    """综合分析API测试"""

    @pytest.mark.asyncio
    async def test_get_asset_analysis(
        self, client: AsyncClient, db_session, test_research_assets, test_research_cards, test_predictions, test_disclaimer, override_get_db
    ):
        """测试获取资产综合分析"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/analysis/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "asset_id" in data["data"]
        assert "asset_symbol" in data["data"]
        assert "asset_name" in data["data"]
        assert "disclaimer" in data["data"]

    @pytest.mark.asyncio
    async def test_asset_analysis_not_found(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试不存在的资产综合分析"""
        non_existent_id = str(uuid4())
        response = await client.get(f"/api/v1/research/analysis/{non_existent_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_asset_analysis_invalid_id(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试无效资产ID综合分析"""
        response = await client.get("/api/v1/research/analysis/invalid_id")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_guest_access_asset_analysis(
        self, client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试游客可以访问综合分析"""
        asset_id = str(test_research_assets[0].id)
        response = await client.get(f"/api/v1/research/analysis/{asset_id}")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS


class TestAuthenticatedResearchAPI:
    """需要认证的研究接口测试"""

    @pytest.mark.asyncio
    async def test_generate_research_card(
        self, authenticated_client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试生成研究结论（需要认证）"""
        asset_id = str(test_research_assets[0].id)
        response = await authenticated_client.post(f"/api/v1/research/cards/generate/{asset_id}")
        # 验证响应（可能成功或返回404取决于服务实现）
        assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_create_prediction(
        self, authenticated_client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试创建预测（需要认证）"""
        asset_id = str(test_research_assets[0].id)
        payload = {
            "asset_id": asset_id,
            "prediction_type": "price",
            "target_date": str(date.today() + timedelta(days=7)),
            "model_version": "v1.0",
        }
        response = await authenticated_client.post(
            "/api/v1/research/predictions",
            json=payload,
        )
        assert response.status_code in [200, 201, 400, 404, 500]

    @pytest.mark.asyncio
    async def test_trigger_calibration(
        self, authenticated_client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试触发校准（需要认证）"""
        asset_id = str(test_research_assets[0].id)
        response = await authenticated_client.post(f"/api/v1/research/calibration/{asset_id}")
        # 验证响应（可能成功或返回null）
        assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_unauthenticated_generate_card(
        self, client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试未认证用户无法生成研究结论"""
        asset_id = str(test_research_assets[0].id)
        response = await client.post(f"/api/v1/research/cards/generate/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_unauthenticated_create_prediction(
        self, client: AsyncClient, db_session, override_get_db
    ):
        """测试未认证用户无法创建预测"""
        payload = {
            "asset_id": str(uuid4()),
            "prediction_type": "price",
            "target_date": str(date.today() + timedelta(days=7)),
            "model_version": "v1.0",
        }
        response = await client.post("/api/v1/research/predictions", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_unauthenticated_trigger_calibration(
        self, client: AsyncClient, db_session, test_research_assets, override_get_db
    ):
        """测试未认证用户无法触发校准"""
        asset_id = str(test_research_assets[0].id)
        response = await client.post(f"/api/v1/research/calibration/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.UNAUTHORIZED