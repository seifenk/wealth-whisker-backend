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
        title="财智猫(WealthWhisker) API",
        description="""
## 财智猫理财平台 API 文档

多资产理财决策与咨询平台，让用户在同一个平台比较资产、验证策略、低风险试错。

### 核心功能模块

| 模块 | 说明 |
|------|------|
| **认证** | 用户注册、登录、JWT认证 |
| **资产数据** | 多资产看板、K线数据、指标计算 |
| **策略管理** | 策略模板、用户策略配置 |
| **回测服务** | 策略回测执行、结果分析 |
| **模拟交易** | 模拟账户、订单交易、持仓管理、绩效分析 |
| **研究结论** | 研究卡片、模型预测、动态校准、免责声明 |

### 研究结论模块详解 (Phase 5)

研究结论模块提供AI驱动的资产分析能力：

- **研究结论卡片**：AI生成的投资分析结论，包含置信度、依据指标、风险提示
- **模型预测**：基于历史数据的趋势预测，支持价格预测和趋势判断
- **模型动态校准**：自动检测预测偏差并触发校准，提升预测准确性
- **预测准确性分析**：历史预测与实际值的对比统计
- **模型版本管理**：跟踪模型版本迭代和参数变化
- **免责声明**：合规的风险提示和免责声明体系
- **综合分析报告**：整合研究结论、预测、准确性的完整分析报告

### 统一响应格式

所有API返回统一格式：`{"code": 0, "msg": "success", "data": {...}}`

- `code`: 0表示成功，其他表示错误
- `msg`: 描述信息
- `data`: 返回数据

### 认证方式

使用JWT Bearer认证，在请求头添加：`Authorization: Bearer <token>`
""",
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