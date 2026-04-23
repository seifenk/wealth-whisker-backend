"""
FastAPI 应用入口
"""
import sys
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.exceptions import AppException

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
if settings.LOG_FILE:
    logger.add(
        Path(settings.LOG_FILE),
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


def create_application() -> FastAPI:
    """创建 FastAPI 应用"""

    app = FastAPI(
        title=settings.APP_NAME,
        description="财智猫理财平台后端 API - 多资产理财决策与咨询平台",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # 全局异常处理
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.detail,
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误" if not settings.DEBUG else str(exc),
                }
            },
        )

    # 路由注册
    from app.api.v1 import api_router
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    # 根路径
    @app.get("/", tags=["根路径"])
    async def root():
        return {
            "message": "欢迎来到财智猫理财平台 API",
            "docs": "/docs",
            "health": "/health",
        }

    logger.info(f"Application {settings.APP_NAME} v{settings.APP_VERSION} started")

    return app


app = create_application()