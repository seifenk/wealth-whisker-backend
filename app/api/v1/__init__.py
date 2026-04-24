"""
API v1 路由模块
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.assets import router as assets_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.backtest import router as backtest_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(assets_router, tags=["资产数据"])
api_router.include_router(strategies_router, tags=["策略管理"])
api_router.include_router(backtest_router, tags=["回测服务"])