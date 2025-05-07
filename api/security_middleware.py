"""
APIセキュリティミドルウェアモジュール。
セキュリティヘッダーの追加や認証の強化を行います。
"""

from typing import List, Dict, Any, Optional, Callable, Union
import time
import secrets
import re

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from utils.ssl_manager import get_security_headers
from utils.api_key_manager import validate_api_key
from utils.logger import get_structured_logger

# ロガーの設定
logger = get_structured_logger("security_middleware")

# セキュリティヘッダー
DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache"
}

# HTTP Strict Transport Security（HSTS）ヘッダー
HSTS_HEADER = {"Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload"}

# Content Security Policy（CSP）
DEFAULT_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'self';"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティヘッダーを追加するミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        security_headers: Dict[str, str] = None,
        enable_hsts: bool = True,
        enable_csp: bool = True,
        csp_policy: str = DEFAULT_CSP,
        excluded_paths: List[str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            security_headers: 追加するセキュリティヘッダー
            enable_hsts: HSTSヘッダーを有効にするかどうか
            enable_csp: CSPヘッダーを有効にするかどうか
            csp_policy: CSPポリシー
            excluded_paths: ヘッダーを追加しないパスのリスト
        """
        super().__init__(app)
        self.security_headers = security_headers or DEFAULT_SECURITY_HEADERS.copy()
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp
        self.csp_policy = csp_policy
        self.excluded_paths = excluded_paths or []
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 処理
        response = await call_next(request)
        
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return response
        
        # セキュリティヘッダーを追加
        for name, value in self.security_headers.items():
            response.headers[name] = value
        
        # HSTS ヘッダーを追加
        if self.enable_hsts and request.url.scheme == "https":
            response.headers.update(HSTS_HEADER)
        
        # CSP ヘッダーを追加
        if self.enable_csp:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        return response


class APIKeyHeaderHTTPBearer(HTTPBearer):
    """API Key認証（X-API-Key ヘッダー）またはJWT Bearer認証をサポート"""
    
    def __init__(
        self,
        auto_error: bool = True,
        api_key_header_name: str = "X-API-Key",
        api_key_query_param: Optional[str] = None,
    ):
        """
        Args:
            auto_error: エラー時に自動的に例外を発生させるかどうか
            api_key_header_name: APIキーのヘッダー名
            api_key_query_param: APIキーのクエリパラメータ名（Noneの場合はクエリパラメータを使用しない）
        """
        super().__init__(auto_error=auto_error)
        self.api_key_header_name = api_key_header_name
        self.api_key_query_param = api_key_query_param
    
    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        # Bearerトークン（JWT）認証を試す
        try:
            # 親クラスの処理でBearerトークンを検証
            credentials = await super().__call__(request)
            if credentials:
                return credentials
        except HTTPException:
            # Bearer認証が失敗した場合はAPIキー認証を試す
            pass
        
        # APIキーをヘッダーから取得
        api_key = request.headers.get(self.api_key_header_name)
        
        # APIキーをクエリパラメータから取得（設定されている場合）
        if not api_key and self.api_key_query_param:
            api_key = request.query_params.get(self.api_key_query_param)
        
        if not api_key:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="認証情報がありません",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        
        # APIキー形式のバリデーション（必要に応じて調整）
        if not re.match(r"^sk_[a-zA-Z0-9]+_[a-zA-Z0-9]+$", api_key):
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="APIキーの形式が無効です",
                )
            else:
                return None
        
        # APIキーを検証
        is_valid, api_key_obj = validate_api_key(api_key)
        
        if not is_valid or not api_key_obj:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="APIキーが無効または期限切れです",
                )
            else:
                return None
        
        # APIキー情報をHTTPAuthorizationCredentials形式で返す
        # schemeに "ApiKey" を設定して、Bearer認証と区別できるようにする
        return HTTPAuthorizationCredentials(scheme="ApiKey", credentials=api_key)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """レート制限を行うミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        rate_limit: int = 100,
        time_window: int = 60,
        exclude_paths: List[str] = None,
        key_func: Callable[[Request], str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            rate_limit: 時間枠内の最大リクエスト数
            time_window: 時間枠（秒）
            exclude_paths: レート制限を適用しないパスのリスト
            key_func: レート制限のキーを生成する関数（デフォルトはIPアドレス）
        """
        super().__init__(app)
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.exclude_paths = exclude_paths or []
        self.key_func = key_func or (lambda request: request.client.host)
        
        # クライアント情報を保持する辞書
        # key -> {'count': n, 'reset_time': timestamp, 'first_request': timestamp}
        self.clients = {}
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # クライアントキーを取得
        client_key = self.key_func(request)
        current_time = time.time()
        
        # クライアント情報が存在しない場合は新規作成
        if client_key not in self.clients:
            self.clients[client_key] = {
                'count': 1,
                'reset_time': current_time + self.time_window,
                'first_request': current_time
            }
            return await call_next(request)
        
        client = self.clients[client_key]
        
        # 時間枠が過ぎていれば、カウンターをリセット
        if current_time > client['reset_time']:
            client['count'] = 1
            client['reset_time'] = current_time + self.time_window
            client['first_request'] = current_time
            return await call_next(request)
        
        # 制限内かチェック
        if client['count'] < self.rate_limit:
            client['count'] += 1
            return await call_next(request)
        
        # 制限超過
        reset_time = client['reset_time']
        retry_after = int(reset_time - current_time)
        
        return Response(
            content='{"detail": "リクエスト回数の制限を超えました。しばらく経ってから再試行してください。"}',
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={
                "Retry-After": str(retry_after),
                "Content-Type": "application/json"
            }
        )


class ContentLengthLimitMiddleware(BaseHTTPMiddleware):
    """リクエストボディのサイズを制限するミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        max_content_length: int = 10 * 1024 * 1024, # 10 MB
        exclude_paths: List[str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            max_content_length: 最大コンテンツ長（バイト）
            exclude_paths: サイズ制限を適用しないパスのリスト
        """
        super().__init__(app)
        self.max_content_length = max_content_length
        self.exclude_paths = exclude_paths or []
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Content-Lengthヘッダーをチェック
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_content_length:
                    return Response(
                        content='{"detail": "リクエストボディが大きすぎます"}',
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        headers={"Content-Type": "application/json"}
                    )
            except ValueError:
                # Content-Lengthヘッダーが整数でない場合
                pass
        
        return await call_next(request)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """HTTPリクエストをHTTPSにリダイレクトするミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: List[str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            exclude_paths: リダイレクトしないパスのリスト
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # HTTPS接続かどうかチェック
        is_secure = request.url.scheme == "https"
        
        # X-Forwarded-Protoヘッダーがある場合はそちらを使用
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            is_secure = forwarded_proto.lower() == "https"
        
        # HTTP接続の場合はHTTPSにリダイレクト
        if not is_secure:
            https_url = str(request.url.replace(scheme="https"))
            return Response(
                status_code=status.HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": https_url}
            )
        
        return await call_next(request)


class XSSProtectionMiddleware(BaseHTTPMiddleware):
    """XSS攻撃を防止するためのミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        sanitize_input: bool = True,
        sanitize_response: bool = True,
        exclude_paths: List[str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            sanitize_input: 入力をサニタイズするかどうか
            sanitize_response: レスポンスをサニタイズするかどうか
            exclude_paths: サニタイズしないパスのリスト
        """
        super().__init__(app)
        self.sanitize_input = sanitize_input
        self.sanitize_response = sanitize_response
        self.exclude_paths = exclude_paths or []
        
        # 危険なパターンの正規表現
        self.xss_patterns = [
            re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE),
            re.compile(r"<iframe.*?>.*?</iframe>", re.IGNORECASE | re.DOTALL),
            re.compile(r"<embed.*?>.*?</embed>", re.IGNORECASE | re.DOTALL),
            re.compile(r"<object.*?>.*?</object>", re.IGNORECASE | re.DOTALL),
        ]
    
    def _sanitize(self, text: str) -> str:
        """危険なパターンを置換する関数"""
        for pattern in self.xss_patterns:
            text = pattern.sub("", text)
        return text
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # 入力をサニタイズ
        if self.sanitize_input and request.method in ["POST", "PUT", "PATCH"]:
            # リクエストボディを取得
            body = await request.body()
            body_str = body.decode("utf-8")
            
            # サニタイズ
            sanitized_body = self._sanitize(body_str)
            
            # リクエストを再構築
            async def receive():
                return {"type": "http.request", "body": sanitized_body.encode()}
            
            request._receive = receive
        
        # 元のレスポンスを取得
        response = await call_next(request)
        
        # レスポンスをサニタイズ
        if self.sanitize_response and "text/html" in response.headers.get("content-type", ""):
            # レスポンスボディを取得
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # サニタイズ
            body_str = body.decode("utf-8")
            sanitized_body = self._sanitize(body_str)
            
            # レスポンスを再構築
            response = Response(
                content=sanitized_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF攻撃を防止するためのミドルウェア"""
    
    def __init__(
        self,
        app: ASGIApp,
        token_name: str = "csrf_token",
        cookie_name: str = "csrf_token",
        safe_methods: List[str] = None,
        exclude_paths: List[str] = None,
    ):
        """
        Args:
            app: ASGIアプリケーション
            token_name: CSRFトークンのフォームフィールド名
            cookie_name: CSRFトークンのCookie名
            safe_methods: CSRFチェックを行わないHTTPメソッドのリスト
            exclude_paths: CSRFチェックを行わないパスのリスト
        """
        super().__init__(app)
        self.token_name = token_name
        self.cookie_name = cookie_name
        self.safe_methods = safe_methods or ["GET", "HEAD", "OPTIONS"]
        self.exclude_paths = exclude_paths or []
        self.tokens = {}  # ユーザーセッションID -> トークン
    
    def _generate_token(self) -> str:
        """CSRFトークンを生成する関数"""
        return secrets.token_hex(32)
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 除外パスかどうかチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # 安全なメソッドかどうかチェック
        if request.method in self.safe_methods:
            # GETリクエストなどの場合はCSRFトークンを設定
            session_id = request.cookies.get("session", "")
            if not session_id:
                session_id = secrets.token_hex(16)
            
            # 既存のトークンを取得するか、新しいトークンを生成
            csrf_token = self.tokens.get(session_id, self._generate_token())
            self.tokens[session_id] = csrf_token
            
            # レスポンスの処理
            response = await call_next(request)
            
            # Cookieを設定
            response.set_cookie(
                key=self.cookie_name,
                value=csrf_token,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="strict"
            )
            
            # セッションCookieを設定
            if "session" not in request.cookies:
                response.set_cookie(
                    key="session",
                    value=session_id,
                    httponly=True,
                    secure=request.url.scheme == "https",
                    samesite="strict"
                )
            
            return response
        
        # POST, PUT, DELETE などの場合はCSRFトークンを検証
        session_id = request.cookies.get("session", "")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="セッションが無効です"
            )
        
        expected_token = self.tokens.get(session_id)
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRFトークンが無効です"
            )
        
        # ヘッダーからトークンを取得
        header_token = request.headers.get("X-CSRF-Token")
        
        # フォームデータからトークンを取得
        form_token = None
        try:
            form = await request.form()
            form_token = form.get(self.token_name)
        except:
            pass
        
        # Cookie からトークンを取得（SameSiteでもダブルチェック）
        cookie_token = request.cookies.get(self.cookie_name)
        
        # いずれかのトークンが一致するかチェック
        token = header_token or form_token or cookie_token
        
        if not token or token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRFトークンが一致しません"
            )
        
        return await call_next(request)


# セキュリティミドルウェアをアプリケーションに追加する関数
def add_security_middlewares(
    app: FastAPI,
    enable_security_headers: bool = True,
    enable_https_redirect: bool = True,
    enable_rate_limit: bool = True,
    enable_content_length_limit: bool = True,
    enable_xss_protection: bool = True,
    enable_csrf_protection: bool = False,  # APIではデフォルトでオフ
    rate_limit: int = 100,
    time_window: int = 60,
    max_content_length: int = 10 * 1024 * 1024,  # 10 MB
    cors_origins: List[str] = None,
) -> FastAPI:
    """
    セキュリティミドルウェアをFastAPIアプリケーションに追加する
    
    Args:
        app: FastAPIアプリケーション
        enable_security_headers: セキュリティヘッダーを有効にするかどうか
        enable_https_redirect: HTTPSリダイレクトを有効にするかどうか
        enable_rate_limit: レート制限を有効にするかどうか
        enable_content_length_limit: コンテンツ長の制限を有効にするかどうか
        enable_xss_protection: XSS保護を有効にするかどうか
        enable_csrf_protection: CSRF保護を有効にするかどうか
        rate_limit: レート制限のリクエスト数
        time_window: レート制限の時間枠（秒）
        max_content_length: 最大コンテンツ長（バイト）
        cors_origins: CORSで許可するオリジンのリスト
        
    Returns:
        FastAPI: ミドルウェアが追加されたアプリケーション
    """
    # CORS設定
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
        )
    
    # コンテンツ長制限
    if enable_content_length_limit:
        app.add_middleware(
            ContentLengthLimitMiddleware,
            max_content_length=max_content_length,
        )
    
    # レート制限
    if enable_rate_limit:
        app.add_middleware(
            RateLimitMiddleware,
            rate_limit=rate_limit,
            time_window=time_window,
        )
    
    # XSS保護
    if enable_xss_protection:
        app.add_middleware(
            XSSProtectionMiddleware,
            sanitize_input=True,
            sanitize_response=True,
        )
    
    # CSRF保護（APIでは通常不要）
    if enable_csrf_protection:
        app.add_middleware(
            CSRFProtectionMiddleware,
        )
    
    # HTTPSリダイレクト
    if enable_https_redirect:
        app.add_middleware(
            HTTPSRedirectMiddleware,
        )
    
    # セキュリティヘッダー
    if enable_security_headers:
        app.add_middleware(
            SecurityHeadersMiddleware,
            security_headers=DEFAULT_SECURITY_HEADERS,
            enable_hsts=True,
            enable_csp=True,
        )
    
    return app


# APIキー認証を行う依存関数
def api_key_auth(required_permissions: List[str] = None):
    """
    APIキー認証を行う依存関数
    
    Args:
        required_permissions: 必要な権限のリスト
        
    Returns:
        Callable: 依存関数
    """
    async def auth_dependency(
        credentials: HTTPAuthorizationCredentials = Depends(APIKeyHeaderHTTPBearer()),
    ) -> Dict[str, Any]:
        # API Keyかどうかを確認
        if credentials.scheme != "ApiKey":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="有効なAPIキーが必要です",
            )
        
        # APIキーを検証
        is_valid, api_key_obj = validate_api_key(credentials.credentials)
        
        if not is_valid or not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="APIキーが無効または期限切れです",
            )
        
        # 権限チェック
        if required_permissions:
            for permission in required_permissions:
                if not api_key_obj.has_permission(permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"この操作には '{permission}' 権限が必要です",
                    )
        
        # APIキー情報を返す
        return {
            "api_key_id": api_key_obj.key_id,
            "owner": api_key_obj.owner,
            "permissions": api_key_obj.permissions,
            "metadata": api_key_obj.metadata,
        }
    
    return auth_dependency


# 以下はアプリケーションで使用する例
"""
from fastapi import FastAPI, Depends
from api.security_middleware import add_security_middlewares, api_key_auth

app = FastAPI()

# セキュリティミドルウェアを追加
app = add_security_middlewares(
    app,
    cors_origins=["https://example.com"],
)

# APIキー認証が必要なエンドポイント
@app.get("/protected")
async def protected_route(api_key_info: Dict[str, Any] = Depends(api_key_auth(["read"]))):
    return {"message": "認証成功", "owner": api_key_info["owner"]}
""" 