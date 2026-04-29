"""
资产数据API测试 - 适配统一响应格式 {code, msg, data}
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetMetric, OHLCV
from app.core.response import ResponseCode


@pytest_asyncio.fixture(scope="function")
async def test_assets(db_session: AsyncSession):
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
            symbol="ETH",
            name="Ethereum",
            asset_type="crypto",
            exchange="OKX",
            currency="USD",
            is_active=True,
        ),
    ]
    for asset in assets:
        db_session.add(asset)
    await db_session.flush()
    return assets


@pytest_asyncio.fixture(scope="function")
async def test_metrics(db_session: AsyncSession, test_assets):
    """创建测试指标数据"""
    metrics = [
        AssetMetric(
            asset_id=test_assets[0].id,
            price=Decimal("50000.00"),
            change_24h=Decimal("2.5"),
            volatility_30d=Decimal("35.0"),
            risk_level="high",
            calculated_at=datetime.now(timezone.utc),
        ),
    ]
    for metric in metrics:
        db_session.add(metric)
    await db_session.flush()
    return metrics


class TestAssetAPI:
    """资产API测试"""

    @pytest.mark.asyncio
    async def test_get_assets_list(self, client, db_session, test_assets, override_get_db):
        """测试获取资产列表"""
        response = await client.get("/api/v1/assets/")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_get_assets_filter_by_type(self, client, db_session, test_assets, override_get_db):
        """测试按类型过滤资产"""
        response = await client.get("/api/v1/assets/?asset_type=crypto")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS

    @pytest.mark.asyncio
    async def test_get_dashboard(self, client, db_session, test_assets, test_metrics, override_get_db):
        """测试获取dashboard"""
        response = await client.get("/api/v1/assets/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "items" in data["data"]

    @pytest.mark.asyncio
    async def test_get_asset_detail(self, client, db_session, test_assets, override_get_db):
        """测试获取资产详情"""
        asset_id = str(test_assets[0].id)
        response = await client.get(f"/api/v1/assets/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["asset"]["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_asset_detail_not_found(self, client, db_session, override_get_db):
        """测试不存在资产（API使用HTTPException）"""
        non_existent_id = str(uuid4())
        response = await client.get(f"/api/v1/assets/{non_existent_id}")
        # 资产API使用HTTPException，返回标准HTTP 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_asset_detail_invalid_id(self, client, db_session, override_get_db):
        """测试无效asset_id格式（API使用HTTPException）"""
        response = await client.get("/api/v1/assets/invalid_id")
        # 资产API使用HTTPException，返回标准HTTP 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_guest_access(self, client, db_session, test_assets, override_get_db):
        """测试游客访问"""
        response = await client.get("/api/v1/assets/")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.SUCCESS

    @pytest.mark.asyncio
    async def test_dashboard_risk_preference(self, client, db_session, test_assets, test_metrics, override_get_db):
        """测试风险偏好过滤"""
        # 测试保守型偏好
        response = await client.get("/api/v1/assets/dashboard?risk_preference=conservative")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["risk_preference"] == "conservative"

        # 测试激进型偏好
        response = await client.get("/api/v1/assets/dashboard?risk_preference=aggressive")
        assert response.status_code == 200

        # 测试无效的风险偏好（FastAPI枚举验证返回HTTP 200，code=400）
        response = await client.get("/api/v1/assets/dashboard?risk_preference=invalid")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_dashboard_sort(self, client, db_session, test_assets, test_metrics, override_get_db):
        """测试排序功能"""
        # 测试按涨跌幅排序
        response = await client.get("/api/v1/assets/dashboard?sort_by=change_24h")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["sort_by"] == "change_24h"

        # 测试按夏普比率排序
        response = await client.get("/api/v1/assets/dashboard?sort_by=sharpe_ratio")
        assert response.status_code == 200

        # 测试按波动率排序
        response = await client.get("/api/v1/assets/dashboard?sort_by=volatility")
        assert response.status_code == 200

        # 测试无效的排序字段
        response = await client.get("/api/v1/assets/dashboard?sort_by=invalid")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_dashboard_limit(self, client, db_session, test_assets, test_metrics, override_get_db):
        """测试返回数量限制"""
        response = await client.get("/api/v1/assets/dashboard?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert len(data["data"]["items"]) <= 1