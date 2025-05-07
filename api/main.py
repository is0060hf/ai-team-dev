"""
専門エージェントAPIのメインモジュール。
APIエンドポイントとセキュリティ設定を提供します。
"""

import os
import logging
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional

# ルーターをインポート
from api.routes import auth_routes, hitl_routes, pilot_project_routes, monitoring
from api.security_middleware import add_security_middlewares, api_key_auth
from api.error_handlers import setup_error_handlers
from api.openapi_docs import setup_openapi_docs

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api")

# アプリケーション初期化
app = FastAPI(
    title="専門エージェントAPI",
    description="AIエージェントチームの専門エージェント機能を提供するAPI",
    version="1.0.0"
)

# セキュリティミドルウェアを追加
app = add_security_middlewares(
    app,
    enable_security_headers=True,
    enable_https_redirect=True,
    enable_rate_limit=True,
    enable_content_length_limit=True,
    enable_xss_protection=True,
    cors_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://localhost:8000",
        "https://localhost:8000",
        os.getenv("FRONTEND_URL", "https://example.com")
    ],
)

# エラーハンドラーを設定
setup_error_handlers(app)

# OpenAPIドキュメンテーションを設定
setup_openapi_docs(app)

# ルーターを登録
app.include_router(auth_routes.router)
app.include_router(hitl_routes.router)
app.include_router(pilot_project_routes.router)
app.include_router(monitoring.router)

# ルートエンドポイント
@app.get("/")
async def root():
    """APIルートエンドポイント"""
    return {
        "status": "ok",
        "message": "専門エージェントAPIは正常に動作しています",
        "version": app.version,
        "documentation": "/docs"
    }

# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    """APIヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "api_version": app.version
    }

# 認証情報テストエンドポイント
@app.get("/auth-test", tags=["認証"])
async def auth_test(auth_info: Dict[str, Any] = Depends(api_key_auth(["read"]))):
    """認証情報をテストするエンドポイント（読み取り権限が必要）"""
    return {
        "authenticated": True,
        "owner": auth_info["owner"],
        "permissions": auth_info["permissions"],
        "api_key_id": auth_info["api_key_id"]
    }

# アプリケーション起動
if __name__ == "__main__":
    # 開発用サーバー起動
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ssl_keyfile=os.getenv("SSL_KEYFILE"),
        ssl_certfile=os.getenv("SSL_CERTFILE")
    ) 