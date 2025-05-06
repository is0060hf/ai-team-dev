"""
OpenAPI（Swagger）ドキュメントを生成・拡張するためのモジュール。
FastAPIのOpenAPI機能を強化し、APIドキュメントを自動生成します。
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any, List, Optional


def customize_openapi_docs(
    app: FastAPI,
    title: str = "専門エージェントAPI",
    description: str = "専門エージェント連携APIのドキュメント",
    version: str = "1.0.0",
    tags_metadata: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    FastAPIアプリケーションのOpenAPIドキュメントをカスタマイズします。
    
    Args:
        app: FastAPIアプリケーションインスタンス
        title: APIのタイトル
        description: APIの説明
        version: APIのバージョン
        tags_metadata: タグのメタデータ
    """
    if tags_metadata is None:
        tags_metadata = [
            {
                "name": "認証",
                "description": "認証・認可関連のエンドポイント。JWT認証とロールベースのアクセス制御を提供します。"
            },
            {
                "name": "HITL",
                "description": "Human-in-the-loop（人間参加型）インターフェース関連のエンドポイント。タスク承認、フィードバック、介入などの機能を提供します。"
            },
            {
                "name": "specialist",
                "description": "専門エージェント（AIアーキテクト、プロンプトエンジニア、データエンジニア）との連携APIエンドポイント。"
            }
        ]
    
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=title,
            version=version,
            description=description,
            routes=app.routes,
            tags=tags_metadata
        )
        
        # セキュリティスキーマの追加
        openapi_schema["components"]["securitySchemes"] = {
            "Bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }
        
        # グローバルセキュリティ要件
        openapi_schema["security"] = [{"Bearer": []}]
        
        # APIエンドポイントのサンプルコードを追加
        for path in openapi_schema["paths"]:
            for method in openapi_schema["paths"][path]:
                if method in ["get", "post", "put", "delete", "patch"]:
                    operation = openapi_schema["paths"][path][method]
                    
                    # 例のサンプルコードを追加
                    if "requestBody" in operation:
                        # リクエストボディサンプルの追加
                        add_example_for_request_body(operation, path, method)
                    
                    # レスポンス例の追加
                    if "responses" in operation:
                        add_example_for_responses(operation, path, method)
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    # OpenAPIスキーマ生成関数を設定
    app.openapi = custom_openapi


def add_example_for_request_body(operation: Dict[str, Any], path: str, method: str) -> None:
    """
    リクエストボディにサンプル例を追加します。
    
    Args:
        operation: OpenAPIオペレーション辞書
        path: エンドポイントパス
        method: HTTPメソッド
    """
    examples = {}
    
    # /specialist/request エンドポイント
    if path == "/specialist/request" and method == "post":
        examples["専門エージェントにタスクを依頼"] = {
            "summary": "AIアーキテクトにシステム設計を依頼",
            "value": {
                "core_agent": "engineer",
                "request_text": "スケーラビリティを考慮したマイクロサービスアーキテクチャの設計を支援してください",
                "specialist_type": "ai_architect",
                "priority": "medium",
                "context": {"project": "eコマースプラットフォーム"}
            }
        }
    
    # /hitl/approve/{task_id} エンドポイント
    elif path == "/hitl/approve/{task_id}" and method == "post":
        examples["タスクを承認"] = {
            "summary": "タスクをコメント付きで承認",
            "value": {
                "comment": "優先して対応してください"
            }
        }
    
    # /hitl/feedback エンドポイント
    elif path == "/hitl/feedback" and method == "post":
        examples["フィードバックを送信"] = {
            "summary": "タスク結果に対するフィードバック",
            "value": {
                "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "feedback_type": "quality",
                "rating": 4,
                "comment": "とても良い設計で分かりやすい。もう少し詳細なコード例があると更によかった。"
            }
        }
    
    # 例が追加された場合、リクエストボディにセット
    if examples:
        operation["requestBody"]["content"]["application/json"]["examples"] = examples


def add_example_for_responses(operation: Dict[str, Any], path: str, method: str) -> None:
    """
    レスポンスにサンプル例を追加します。
    
    Args:
        operation: OpenAPIオペレーション辞書
        path: エンドポイントパス
        method: HTTPメソッド
    """
    # /specialist/dashboard エンドポイント
    if path == "/specialist/dashboard" and method == "get" and "200" in operation["responses"]:
        if "content" in operation["responses"]["200"]:
            operation["responses"]["200"]["content"]["application/json"]["example"] = {
                "timestamp": "2023-06-15T12:34:56.789012",
                "active_tasks_count": 3,
                "completed_tasks_count": 12,
                "agents": {
                    "ai_architect": {
                        "active_tasks": [
                            {
                                "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "sender": "engineer",
                                "recipient": "ai_architect",
                                "status": "処理中",
                                "progress": 0.5,
                                "description": "マイクロサービスアーキテクチャの設計"
                            }
                        ],
                        "stats": {
                            "active_count": 1,
                            "completed_count": 5,
                            "success_rate": 0.8,
                            "avg_response_time_minutes": 45.2
                        }
                    }
                },
                "recent_activities": [
                    {
                        "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "event_type": "status_update",
                        "timestamp": "2023-06-15T12:30:00.000000",
                        "status": "処理中",
                        "progress": 0.5
                    }
                ]
            }
    
    # /auth/token エンドポイント
    elif path == "/auth/token" and method == "post" and "200" in operation["responses"]:
        if "content" in operation["responses"]["200"]:
            operation["responses"]["200"]["content"]["application/json"]["example"] = {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }


def generate_openapi_json(app: FastAPI, output_file: str = "openapi.json") -> bool:
    """
    OpenAPIスキーマをJSONファイルに出力します。
    
    Args:
        app: FastAPIアプリケーションインスタンス
        output_file: 出力ファイルパス
        
    Returns:
        bool: 成功したかどうか
    """
    try:
        import json
        
        # OpenAPIスキーマの取得
        openapi_schema = app.openapi()
        
        # JSONファイルに出力
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(openapi_schema, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"OpenAPIスキーマの出力中にエラーが発生しました: {str(e)}")
        return False 