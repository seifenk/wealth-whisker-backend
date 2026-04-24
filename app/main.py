"""
FastAPI 应用入口 - 统一响应格式 {code, msg, data}
"""
import sys
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.response import ResponseCode, ResponseWrapper, UnifiedJSONResponse, UnifiedErrorResponse

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
    """创建 FastAPI 应用 - 使用统一响应格式"""

    app = FastAPI(
        title=settings.APP_NAME,
        description="财智猫理财平台后端 API - 多资产理财决策与咨询平台",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        # 使用自定义响应类实现统一格式
        default_response_class=UnifiedJSONResponse,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # 全局异常处理 - 统一返回 {code, msg, data} 格式
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误"""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            msg = error.get("msg", "验证失败")
            if msg.startswith("Value error, "):
                msg = msg[13:]
            errors.append({"field": field, "message": msg})

        first_error = errors[0] if errors else {"field": "", "message": "验证失败"}
        return UnifiedErrorResponse(
            msg=first_error["message"],
            code=ResponseCode.VALIDATION_ERROR,
            data={"errors": errors},
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """处理应用异常"""
        code_map = {
            "UNAUTHORIZED": ResponseCode.UNAUTHORIZED,
            "FORBIDDEN": ResponseCode.FORBIDDEN,
            "NOT_FOUND": ResponseCode.NOT_FOUND,
            "CONFLICT": ResponseCode.CONFLICT,
            "VALIDATION_ERROR": ResponseCode.VALIDATION_ERROR,
            "INTERNAL_ERROR": ResponseCode.INTERNAL_ERROR,
        }
        code = code_map.get(exc.error_code, ResponseCode.FAIL)

        return UnifiedErrorResponse(
            msg=exc.detail,
            code=code,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理未知异常"""
        logger.error(f"Unhandled exception: {exc}")
        return UnifiedErrorResponse(
            msg="服务器内部错误" if not settings.DEBUG else str(exc),
            code=ResponseCode.INTERNAL_ERROR,
        )

    # 路由注册
    from app.api.v1 import api_router
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 健康检查（不使用统一格式）
    @app.get("/health", tags=["健康检查"], response_class=JSONResponse)
    async def health_check():
        return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    # 根路径（不使用统一格式）
    @app.get("/", tags=["根路径"], response_class=JSONResponse)
    async def root():
        return {"message": "欢迎来到财智猫理财平台 API", "docs": "/docs", "health": "/health"}

    logger.info(f"Application {settings.APP_NAME} v{settings.APP_VERSION} started")

    return app


app = create_application()