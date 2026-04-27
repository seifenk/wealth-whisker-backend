"""
统一响应格式处理
"""
from typing import Any, Optional, Generic, TypeVar

import json
from pydantic import BaseModel
from starlette.responses import Response, JSONResponse


class ResponseCode:
    """响应状态码"""
    SUCCESS = 0
    FAIL = 1
    VALIDATION_ERROR = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_ERROR = 500


# 定义泛型类型变量
T = TypeVar('T')


class UnifiedResponse(BaseModel, Generic[T]):
    """统一响应格式模型"""
    code: int = ResponseCode.SUCCESS
    msg: str = "成功"
    data: Optional[T] = None

    class Config:
        from_attributes = True


class ResponseWrapper:
    """统一响应包装器"""

    @staticmethod
    def success(data: Any = None, msg: str = "成功", code: int = ResponseCode.SUCCESS) -> dict:
        """成功响应"""
        return {
            "code": code,
            "msg": msg,
            "data": data,
        }

    @staticmethod
    def error(msg: str, code: int = ResponseCode.FAIL, data: Any = None) -> dict:
        """错误响应"""
        return {
            "code": code,
            "msg": msg,
            "data": data,
        }


class UnifiedJSONResponse(JSONResponse):
    """统一格式的 JSON 响应 - 自动包装返回数据"""

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[dict] = None,
        media_type: Optional[str] = None,
        background: Optional[Any] = None,
        msg: str = "成功",
        code: int = ResponseCode.SUCCESS,
    ):
        # 包装为统一格式
        wrapped = ResponseWrapper.success(data=content, msg=msg, code=code)
        super().__init__(
            content=wrapped,
            status_code=status_code,
            headers=headers,
            media_type=media_type or "application/json",
            background=background,
        )


class UnifiedErrorResponse(JSONResponse):
    """统一格式的错误响应"""

    def __init__(
        self,
        msg: str,
        code: int = ResponseCode.FAIL,
        data: Any = None,
        status_code: int = 200,
        headers: Optional[dict] = None,
        media_type: Optional[str] = None,
        background: Optional[Any] = None,
    ):
        wrapped = ResponseWrapper.error(msg=msg, code=code, data=data)
        super().__init__(
            content=wrapped,
            status_code=status_code,
            headers=headers,
            media_type=media_type or "application/json",
            background=background,
        )