"""
API統合テストモジュール。
API認証・認可、HITL、エラーハンドリングといった新機能をテストします。
workflow_automation属性の問題解決とAPIパスの一貫性を確保する機能を検証します。
"""

import pytest
import uuid
import json
from unittest.mock import patch, MagicMock
import datetime

from api.api_utils import (
    create_test_client, 
    get_api_url, 
    get_auth_headers, 
    fix_workflow_automation_attribute
)
from utils.workflow_automation import (
    SpecialistAgents, 
    CoreAgents, 
    TaskPriority, 
    TaskStatus
)


@pytest.fixture
def api_client():
    """APIテストクライアントを提供するフィクスチャ"""
    # workflow_automation属性の問題を修正
    fix_workflow_automation_attribute()
    
    # テストクライアントを作成
    client = create_test_client()
    return client


@pytest.fixture
def admin_headers(api_client):
    """管理者権限のAuthorizationヘッダーを提供するフィクスチャ"""
    return get_auth_headers(api_client, "admin", "adminpass")


@pytest.fixture
def user_headers(api_client):
    """一般ユーザーのAuthorizationヘッダーを提供するフィクスチャ"""
    return get_auth_headers(api_client, "user", "userpass")


@pytest.fixture
def manager_headers(api_client):
    """マネージャーのAuthorizationヘッダーを提供するフィクスチャ"""
    return get_auth_headers(api_client, "manager", "managerpass")


@pytest.mark.api
class TestApiAuthentication:
    """API認証・認可機能のテスト"""
    
    def test_token_endpoint(self, api_client):
        """トークン取得エンドポイントが正しく動作することを確認"""
        response = api_client.post(
            get_api_url("auth_token"),
            data={"username": "user", "password": "userpass"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
    
    def test_invalid_credentials(self, api_client):
        """不正な認証情報でトークン取得が失敗することを確認"""
        response = api_client.post(
            get_api_url("auth_token"),
            data={"username": "invalid", "password": "wrongpass"}
        )
        
        assert response.status_code == 401
    
    def test_auth_required_endpoint(self, api_client, user_headers):
        """認証が必要なエンドポイントが認証なしでアクセスできないことを確認"""
        # 認証なしでアクセス
        response = api_client.get(get_api_url("auth_users_me"))
        assert response.status_code == 401
        
        # 認証付きでアクセス
        response = api_client.get(
            get_api_url("auth_users_me"),
            headers=user_headers
        )
        assert response.status_code == 200
    
    def test_role_based_access(self, api_client, admin_headers, user_headers):
        """ロールベースのアクセス制御が正しく動作することを確認"""
        # 管理者は管理者エンドポイントにアクセス可能
        response = api_client.get(
            get_api_url("auth_admin"),
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # 一般ユーザーは管理者エンドポイントにアクセス不可
        response = api_client.get(
            get_api_url("auth_admin"),
            headers=user_headers
        )
        assert response.status_code == 403


@pytest.mark.api
class TestApiErrorHandling:
    """APIエラーハンドリング機能のテスト"""
    
    def test_validation_error(self, api_client, user_headers):
        """バリデーションエラーが適切に処理されることを確認"""
        # 必須フィールドが欠けたリクエスト
        response = api_client.post(
            get_api_url("specialist_request"),
            headers=user_headers,
            json={"core_agent": "engineer"}  # request_textが欠けている
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "details" in data["error"]
    
    def test_404_error(self, api_client, user_headers):
        """存在しないリソースへのアクセスが適切に処理されることを確認"""
        response = api_client.get(
            get_api_url("specialist_task", task_id="nonexistent"),
            headers=user_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]


@pytest.mark.api
@patch("utils.workflow_automation.SpecialistTaskRegistry.get_active_tasks")
@patch("utils.workflow_automation.SpecialistTaskRegistry.get_task_info")
@patch("utils.workflow_automation.SpecialistTaskRegistry.approve_task")
class TestHitlInterface:
    """HITL（Human-in-the-loop）インターフェースのテスト"""
    
    def test_pending_approvals(self, mock_approve, mock_get_info, mock_active, api_client, manager_headers):
        """承認待ちタスクの取得が正しく動作することを確認"""
        # モックデータの設定
        mock_active.return_value = [
            {
                "task_id": str(uuid.uuid4()),
                "sender": CoreAgents.ENGINEER,
                "recipient": SpecialistAgents.AI_ARCHITECT,
                "approved_by_pm": False,
                "rejected_by_pm": False,
                "description": "テスト用タスク"
            }
        ]
        
        # エンドポイント呼び出し
        response = api_client.get(
            get_api_url("hitl_pending_approvals"),
            headers=manager_headers
        )
        
        # 結果検証
        assert response.status_code == 200
        data = response.json()
        assert "pending_count" in data
        assert data["pending_count"] == 1
        assert "tasks" in data
        assert len(data["tasks"]) == 1
    
    def test_approve_task(self, mock_approve, mock_get_info, mock_active, api_client, manager_headers):
        """タスク承認が正しく動作することを確認"""
        # モックデータの設定
        task_id = str(uuid.uuid4())
        mock_get_info.return_value = {
            "task_id": task_id,
            "sender": CoreAgents.ENGINEER,
            "recipient": SpecialistAgents.AI_ARCHITECT,
            "approved_by_pm": False,
            "rejected_by_pm": False,
            "description": "テスト用タスク"
        }
        
        # エンドポイント呼び出し
        response = api_client.post(
            get_api_url("hitl_approve", task_id=task_id),
            headers=manager_headers,
            json={"comment": "優先対応してください"}
        )
        
        # 結果検証
        assert response.status_code == 200
        assert mock_approve.called
        mock_approve.assert_called_with(task_id, "manager")


@pytest.mark.api
class TestWorkflowAutomationAttributeFix:
    """workflow_automation属性の問題修正機能のテスト"""
    
    @patch("api.specialist_api.task_registry.get_task_info")
    @patch("api.specialist_api.request_specialist_if_needed")
    def test_attribute_fix(self, mock_request, mock_get_info, api_client, user_headers):
        """workflow_automation属性が存在することを確認"""
        # タスクIDを用意
        task_id = str(uuid.uuid4())
        
        # モックの設定
        mock_request.return_value = task_id
        mock_get_info.return_value = {
            "task_id": task_id,
            "recipient": SpecialistAgents.AI_ARCHITECT,
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.datetime.now().isoformat(),
            "description": "テスト用タスク"
        }
        
        # API呼び出し
        response = api_client.post(
            get_api_url("specialist_request"),
            headers=user_headers,
            json={
                "core_agent": CoreAgents.ENGINEER,
                "request_text": "テスト用リクエスト",
                "specialist_type": SpecialistAgents.AI_ARCHITECT
            }
        )
        
        # 結果検証
        assert response.status_code == 200
        assert mock_request.called
        assert mock_get_info.called 