"""
统一异常处理
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class AppException(HTTPException):
    """应用基础异常"""

    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class UnauthorizedException(AppException):
    """未授权异常"""

    def __init__(self, detail: str = "未授权访问"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="UNAUTHORIZED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """禁止访问异常"""

    def __init__(self, detail: str = "禁止访问"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN"
        )


class NotFoundException(AppException):
    """资源不存在异常"""

    def __init__(self, detail: str = "资源不存在"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="NOT_FOUND"
        )


class ConflictException(AppException):
    """冲突异常"""

    def __init__(self, detail: str = "资源冲突"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="CONFLICT"
        )


class ValidationException(AppException):
    """验证失败异常"""

    def __init__(self, detail: str = "数据验证失败"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR"
        )


class InternalServerException(AppException):
    """服务器内部错误异常"""

    def __init__(self, detail: str = "服务器内部错误"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="INTERNAL_ERROR"
        )


class ServiceUnavailableException(AppException):
    """服务不可用异常"""

    def __init__(self, detail: str = "服务暂时不可用"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="SERVICE_UNAVAILABLE"
        )