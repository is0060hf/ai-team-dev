"""
専門エージェントAPIのグローバルエラーハンドリングモジュール。
標準化されたエラーレスポンスとロギングを提供します。
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import time
from typing import Dict, Any, Optional

from utils.logger import get_agent_logger

logger = get_agent_logger("api_error_handler")


# エラーレスポンスモデル
def create_error_response(
    status_code: int, 
    message: str, 
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    標準化されたエラーレスポンスを作成します。
    
    Args:
        status_code: HTTPステータスコード
        message: エラーメッセージ
        details: 詳細情報（オプション）
        request_id: リクエストID（オプション）
        
    Returns:
        Dict[str, Any]: 標準化されたエラーレスポンス
    """
    response = {
        "error": {
            "status": status_code,
            "message": message,
            "timestamp": time.time()
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    if request_id:
        response["error"]["request_id"] = request_id
    
    return response


# エラーハンドラーの登録
def add_error_handlers(app: FastAPI) -> None:
    """
    FastAPIアプリケーションにエラーハンドラーを登録します。
    
    Args:
        app: FastAPIアプリケーションインスタンス
    """
    
    # リクエスト検証エラー
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        リクエスト検証エラーを処理するハンドラー。
        フィールドごとのエラー情報を標準化された形式で返します。
        """
        # リクエスト情報をログに記録
        logger.warning(
            f"リクエスト検証エラー: {request.method} {request.url}"
        )
        
        # エラー詳細をログに記録
        errors = exc.errors()
        logger.debug(f"検証エラー詳細: {errors}")
        
        # フィールドごとのエラーメッセージを整形
        error_details = []
        for error in errors:
            error_details.append({
                "field": ".".join([str(loc) for loc in error["loc"] if loc != "body"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        # レスポンスを作成
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="リクエストデータが無効です",
                details={"errors": error_details},
                request_id=request.headers.get("X-Request-ID")
            )
        )
    
    # HTTP例外
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        HTTPException例外を処理するハンドラー。
        例外のステータスコードとメッセージを使用して標準レスポンスを返します。
        """
        # リクエスト情報をログに記録
        logger.warning(
            f"HTTPエラー: {exc.status_code} - {request.method} {request.url} - {exc.detail}"
        )
        
        # レスポンスを作成
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                status_code=exc.status_code,
                message=exc.detail,
                request_id=request.headers.get("X-Request-ID")
            ),
            headers=exc.headers
        )
    
    # その他の例外
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        未処理の例外を処理するハンドラー。
        内部サーバーエラーとして処理し、スタックトレースをログに記録します。
        """
        # スタックトレースを取得
        stack_trace = traceback.format_exc()
        
        # 深刻なエラーとしてログに記録
        logger.error(
            f"未処理の例外: {request.method} {request.url} - {str(exc)}\n{stack_trace}"
        )
        
        # レスポンスを作成（詳細はログに記録するのみで、クライアントには最小限の情報を返す）
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="内部サーバーエラーが発生しました",
                request_id=request.headers.get("X-Request-ID")
            )
        )


# ミドルウェア
class RequestLoggingMiddleware:
    """リクエストとレスポンスをログに記録するミドルウェア"""
    
    def __init__(self, app: FastAPI):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        # リクエスト開始時刻
        start_time = time.time()
        
        # リクエスト情報をログに記録
        client_ip = request.client.host if request.client else "unknown"
        request_id = request.headers.get("X-Request-ID", "")
        logger.info(
            f"リクエスト開始: {request.method} {request.url.path} - クライアント: {client_ip} - リクエストID: {request_id}"
        )
        
        # リクエスト処理
        try:
            response = await call_next(request)
            
            # 処理時間
            process_time = time.time() - start_time
            
            # レスポンス情報をログに記録
            logger.info(
                f"リクエスト完了: {request.method} {request.url.path} - ステータス: {response.status_code} - 処理時間: {process_time:.3f}秒"
            )
            
            return response
        except Exception as e:
            # 例外発生時は他のハンドラーに任せるが、ここでもログに記録
            logger.error(
                f"リクエスト処理中に例外が発生: {request.method} {request.url.path} - {str(e)}"
            )
            raise


def add_middlewares(app: FastAPI) -> None:
    """
    アプリケーションにミドルウェアを追加します。
    
    Args:
        app: FastAPIアプリケーションインスタンス
    """
    # リクエストロギングミドルウェアを追加
    app.middleware("http")(RequestLoggingMiddleware(app)) 