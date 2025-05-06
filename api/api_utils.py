"""
API統合テスト環境の改善と一般的なAPIユーティリティのためのモジュール。
workflow_automation属性の問題解決とAPIパスの一貫性確保のための機能を提供します。
"""

import os
import importlib
from typing import Dict, Any, Optional, List, Callable, Tuple
from urllib.parse import urljoin

# APIの設定
API_VERSION = "v1"
DEFAULT_API_BASE_URL = "http://localhost:8000"

# APIのエンドポイントパス
API_PATHS = {
    # Specialist endpoints
    "specialist_request": "/specialist/request",
    "specialist_analyze": "/specialist/analyze",
    "specialist_tasks": "/specialist/tasks",
    "specialist_task": "/specialist/task/{task_id}",
    "specialist_task_update": "/specialist/task/{task_id}/update",
    "specialist_task_approve": "/specialist/task/{task_id}/approve",
    "specialist_dashboard": "/specialist/dashboard",
    "specialist_save": "/specialist/save",
    "specialist_load": "/specialist/load",
    
    # Auth endpoints
    "auth_token": "/auth/token",
    "auth_users_me": "/auth/users/me",
    "auth_users_me_roles": "/auth/users/me/roles",
    "auth_admin": "/auth/admin",
    "auth_manager": "/auth/manager",
    
    # HITL endpoints
    "hitl_pending_approvals": "/hitl/pending-approvals",
    "hitl_approve": "/hitl/approve/{task_id}",
    "hitl_reject": "/hitl/reject/{task_id}",
    "hitl_feedback": "/hitl/feedback",
    "hitl_assign_task": "/hitl/assign-task",
    "hitl_intervene": "/hitl/intervene",
}


def get_api_url(endpoint_name: str, base_url: Optional[str] = None, **path_params) -> str:
    """
    エンドポイント名からAPIのURLを取得します。
    
    Args:
        endpoint_name: エンドポイント名（API_PATHSのキー）
        base_url: ベースURL（デフォルト：http://localhost:8000）
        **path_params: パスパラメータ（例：task_id="abc123"）
        
    Returns:
        str: 完全なAPIのURL
    """
    if endpoint_name not in API_PATHS:
        raise ValueError(f"不明なエンドポイント名: {endpoint_name}")
    
    base = base_url or os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL)
    path = API_PATHS[endpoint_name]
    
    # パスパラメータの置換
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", str(value))
    
    return urljoin(base, path)


def fix_workflow_automation_attribute():
    """
    テスト環境で問題になるworkflow_automation属性の問題を解決します。
    モジュールが存在することを確認し、必要に応じて循環参照を修正します。
    
    Returns:
        bool: 修正が成功したかどうか
    """
    try:
        # utils.workflow_automationモジュールの動的インポート
        workflow_module = importlib.import_module("utils.workflow_automation")
        
        # モジュールにworkflow_automationインスタンスが存在するか確認
        if hasattr(workflow_module, "workflow_automation"):
            return True
        
        # 存在しない場合、APIテスト用のモックを作成
        from unittest.mock import MagicMock
        
        # SpecialistWorkflowAutomationクラスの存在確認
        if hasattr(workflow_module, "SpecialistWorkflowAutomation"):
            # モックインスタンスを作成
            mock_instance = MagicMock(spec=workflow_module.SpecialistWorkflowAutomation)
            
            # モジュールに属性として追加
            setattr(workflow_module, "workflow_automation", mock_instance)
            return True
            
    except (ImportError, AttributeError) as e:
        print(f"workflow_automation属性の修正中にエラーが発生しました: {str(e)}")
        return False
    
    return False


def create_test_client(app_module_path: str = "api.specialist_api:app"):
    """
    APIのテストクライアントを作成します。
    
    Args:
        app_module_path: アプリケーションモジュールのパス
        
    Returns:
        TestClient: FastAPIのテストクライアント
    """
    try:
        # workflow_automation属性を修正
        fix_workflow_automation_attribute()
        
        # FastAPIのTestClientをインポート
        from fastapi.testclient import TestClient
        
        # アプリケーションのインポート
        module_path, app_name = app_module_path.split(":")
        module = importlib.import_module(module_path)
        app = getattr(module, app_name)
        
        # テストクライアントを作成
        client = TestClient(app)
        return client
        
    except Exception as e:
        print(f"テストクライアント作成中にエラーが発生しました: {str(e)}")
        raise


def get_auth_headers(client, username: str = "user", password: str = "userpass") -> Dict[str, str]:
    """
    認証トークンを取得し、Authorization headerを生成します。
    
    Args:
        client: FastAPIのテストクライアント
        username: ユーザー名
        password: パスワード
        
    Returns:
        Dict[str, str]: AuthorizationヘッダーのDict
    """
    try:
        # トークンを取得
        response = client.post(
            get_api_url("auth_token"),
            data={"username": username, "password": password}
        )
        
        if response.status_code != 200:
            raise ValueError(f"認証に失敗しました: {response.json()}")
        
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
        
    except Exception as e:
        print(f"認証ヘッダー取得中にエラーが発生しました: {str(e)}")
        return {} 