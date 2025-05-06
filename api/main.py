"""
メインAPIアプリケーション。
すべてのAPIルートとUI機能を統合します。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from starlette.middleware.sessions import SessionMiddleware

from api.routes import auth_routes, hitl_routes, hitl_interface
from api.error_handlers import setup_error_handlers
from api.auth import get_current_active_user

# アプリケーションの初期化
app = FastAPI(
    title="Webシステム開発AIエージェントチームAPI",
    description="AIエージェントチームのAPIとHuman-in-the-Loop (HITL) インターフェース",
    version="0.1.0"
)

# 静的ファイルディレクトリの設定
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# テンプレートディレクトリの作成
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
os.makedirs(templates_dir, exist_ok=True)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セッションミドルウェアの設定
app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key"  # 本番環境では環境変数から取得するなど安全に管理する
)

# エラーハンドラーの設定
setup_error_handlers(app)

# ルーターの登録
app.include_router(auth_routes.router)
app.include_router(hitl_routes.router)
app.include_router(hitl_interface.router)

# ルートページ
@app.get("/")
async def root():
    """ルートページ - APIの基本情報を返す"""
    return {
        "name": "Webシステム開発AIエージェントチームAPI",
        "version": "0.1.0",
        "documentation": "/docs",
        "hitl_interface": "/hitl-ui/"
    }


# アプリケーションの状態確認
@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"} 