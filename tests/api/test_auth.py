"""
认证API测试 - 适配统一响应格式 {code, msg, data}

HTTP状态码始终为200，错误通过code字段区分
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ResponseCode
from app.main import app
from app.models.user import User


class TestUserRegistration:
    """用户注册测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client, db_session, override_get_db):
        """测试正常用户注册"""
        # 使用唯一邮箱避免冲突
        unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
        user_data = {
            "email": unique_email,
            "password": "NewUser123456",
            "nickname": "新用户",
        }
        response = await client.post("/api/v1/auth/register", json=user_data)
        # 注册API返回HTTP 201 Created
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "id" in data["data"]
        assert data["data"]["email"] == unique_email

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, db_session, test_user, override_get_db):
        """测试重复邮箱注册"""
        user_data = {"email": test_user.email, "password": "Duplicate123", "nickname": "重复用户"}
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.CONFLICT

    @pytest.mark.asyncio
    async def test_register_password_validation(self, client, db_session, override_get_db):
        """测试密码格式验证"""
        # 缺少大写字母
        response = await client.post("/api/v1/auth/register", json={
            "email": "test1@example.com", "password": "nouppercase123", "nickname": "test"
        })
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.VALIDATION_ERROR

        # 缺少小写字母
        response = await client.post("/api/v1/auth/register", json={
            "email": "test2@example.com", "password": "NOLOWERCASE123", "nickname": "test"
        })
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.VALIDATION_ERROR

        # 缺少数字
        response = await client.post("/api/v1/auth/register", json={
            "email": "test3@example.com", "password": "NoDigitPassword", "nickname": "test"
        })
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.VALIDATION_ERROR


class TestUserLogin:
    """用户登录测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, client, db_session, test_user, override_get_db):
        """测试正常用户登录"""
        login_data = {"email": test_user.email, "password": "Test123456"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, db_session, test_user, override_get_db):
        """测试错误密码登录"""
        login_data = {"email": test_user.email, "password": "WrongPassword123"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client, db_session, override_get_db):
        """测试不存在用户登录"""
        login_data = {"email": "nonexistent@example.com", "password": "Nonexistent123"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED


class TestTokenRefresh:
    """Token刷新测试"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, db_session, test_user, override_get_db):
        """测试正常刷新token"""
        login_data = {"email": test_user.email, "password": "Test123456"}
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        refresh_token = login_response.json()["data"]["refresh_token"]

        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert "access_token" in data["data"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client, db_session, override_get_db):
        """测试无效refresh_token"""
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid_token"})
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED


class TestGetCurrentUser:
    """获取当前用户信息测试"""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, authenticated_client, db_session, test_user, override_get_db):
        """测试正常获取当前用户信息"""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_without_auth(self, client, db_session, override_get_db):
        """测试无认证访问用户信息"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED


class TestUpdateUser:
    """更新用户信息测试"""

    @pytest.mark.asyncio
    async def test_update_user_info_success(self, authenticated_client, db_session, test_user, override_get_db):
        """测试正常更新用户信息"""
        update_data = {"nickname": "更新后的昵称", "avatar_url": "https://example.com/avatar.jpg"}
        response = await authenticated_client.patch("/api/v1/auth/me", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["nickname"] == update_data["nickname"]

    @pytest.mark.asyncio
    async def test_update_risk_preference(self, authenticated_client, db_session, test_user, override_get_db):
        """测试更新风险偏好"""
        response = await authenticated_client.patch("/api/v1/auth/me", json={"risk_preference": "aggressive"})
        assert response.status_code == 200
        assert response.json()["data"]["risk_preference"] == "aggressive"

    @pytest.mark.asyncio
    async def test_update_invalid_risk_preference(self, authenticated_client, db_session, test_user, override_get_db):
        """测试无效风险偏好值"""
        response = await authenticated_client.patch("/api/v1/auth/me", json={"risk_preference": "invalid"})
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.VALIDATION_ERROR


class TestChangePassword:
    """密码修改测试"""

    @pytest.mark.asyncio
    async def test_change_password_success(self, authenticated_client, db_session, test_user, override_get_db):
        """测试正常修改密码"""
        password_data = {"old_password": "Test123456", "new_password": "NewPassword123"}
        response = await authenticated_client.post("/api/v1/auth/me/password", json=password_data)
        # 204 No Content可能被转换为200
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self, authenticated_client, db_session, test_user, override_get_db):
        """测试错误旧密码"""
        password_data = {"old_password": "WrongOldPassword123", "new_password": "NewPassword123"}
        response = await authenticated_client.post("/api/v1/auth/me/password", json=password_data)
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_change_password_invalid_new_password(self, authenticated_client, db_session, test_user, override_get_db):
        """测试新密码格式错误"""
        password_data = {"old_password": "Test123456", "new_password": "invalidpassword"}
        response = await authenticated_client.post("/api/v1/auth/me/password", json=password_data)
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.VALIDATION_ERROR


class TestAcceptDisclaimer:
    """免责声明确认测试"""

    @pytest.mark.asyncio
    async def test_accept_disclaimer_success(self, authenticated_client, db_session, test_user, override_get_db):
        """测试正常确认免责声明"""
        response = await authenticated_client.post("/api/v1/auth/me/disclaimer", json={"accepted": True})
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == ResponseCode.SUCCESS
        assert data["data"]["disclaimer_accepted"] == True

    @pytest.mark.asyncio
    async def test_decline_disclaimer(self, authenticated_client, db_session, test_user, override_get_db):
        """测试拒绝确认免责声明"""
        response = await authenticated_client.post("/api/v1/auth/me/disclaimer", json={"accepted": False})
        assert response.status_code == 200
        assert response.json()["data"]["disclaimer_accepted"] == False


class TestLogout:
    """登出测试"""

    @pytest.mark.asyncio
    async def test_logout_success(self, authenticated_client, db_session, test_user, override_get_db):
        """测试正常登出"""
        response = await authenticated_client.post("/api/v1/auth/logout")
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_logout_without_auth(self, client, db_session, override_get_db):
        """测试无认证登出"""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["code"] == ResponseCode.UNAUTHORIZED