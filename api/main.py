"""
APIメインモジュール。
FastAPIアプリケーションのエントリーポイントです。
"""

import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional

# ルーターをインポート
from api.routes import auth_routes, hitl_routes, pilot_project_routes, monitoring
from api.routes.metrics_api import router as metrics_router
from api.security_middleware import add_security_middlewares, api_key_auth
from api.error_handlers import setup_error_handlers
from api.openapi_docs import setup_openapi_docs

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

# アプリケーション初期化
app = FastAPI(
    title="専門エージェントAPI",
    description="AIエージェントチームの専門エージェント機能を提供するAPI",
    version="1.0.0",
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# エラーハンドラーを設定
setup_error_handlers(app)

# セキュリティミドルウェアを追加
add_security_middlewares(app)

# OpenAPIドキュメンテーションを設定
setup_openapi_docs(app)

# ルーターを登録
app.include_router(auth_routes.router)
app.include_router(hitl_routes.router)
app.include_router(pilot_project_routes.router)
app.include_router(monitoring.router)
app.include_router(metrics_router)

# ルートエンドポイント
@app.get("/")
async def root():
    """APIルートエンドポイント"""
    return {
        "message": "専門エージェントAPI",
        "version": "1.0.0",
        "documentation": "/docs"
    }

# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True) 