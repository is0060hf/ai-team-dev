"""
api/specialist_api.py のユニットテスト。
専門エージェント連携APIのエンドポイントをテストします。
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from api.specialist_api import app
from utils.agent_communication import TaskStatus, TaskPriority, TaskType
from utils.workflow_automation import SpecialistAgents, CoreAgents


@pytest.fixture
def test_client():
    """テスト用APIクライアント"""
    return TestClient(app)


class TestAPIBasics:
    """API基本機能のテスト"""
    
    def test_api_root(self, test_client):
        """APIルートエンドポイントの動作を確認"""
        response = test_client.get("/")
        
        assert response.status_code == 200
        assert "message" in response.json()
        assert "専門エージェント連携API" in response.json()["message"]
    
    def test_api_docs_available(self, test_client):
        """APIドキュメント(OpenAPI)が利用可能であることを確認"""
        # Swagger UIのエンドポイント
        response = test_client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        # OpenAPI JSONスキーマ
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        
        # スキーマに必要な情報が含まれていることを確認
        openapi_schema = response.json()
        assert "paths" in openapi_schema
        assert "/specialist/tasks" in openapi_schema["paths"]


@patch("api.specialist_api.workflow_automation")
@patch("api.specialist_api.task_registry")
class TestTaskManagementEndpoints:
    """タスク管理エンドポイントのテスト"""
    
    def test_analyze_request(self, mock_task_registry, mock_workflow, test_client):
        """要求分析エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_workflow.is_specialist_needed.return_value = (True, SpecialistAgents.AI_ARCHITECT, 0.8)
        
        # リクエストデータ
        request_data = {
            "request_text": "システムアーキテクチャの設計をお願いします。",
            "context": {"project": "test_project"}
        }
        
        # エンドポイントを呼び出し
        response = test_client.post("/specialist/analyze", json=request_data)
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["needed"] is True
        assert result["specialist_type"] == SpecialistAgents.AI_ARCHITECT
        assert "confidence" in result
        
        # モックが正しく呼び出されたことを確認
        mock_workflow.is_specialist_needed.assert_called_once_with(
            task=request_data["request_text"],
            context=request_data["context"]
        )
    
    def test_create_task(self, mock_task_registry, mock_workflow, test_client):
        """タスク作成エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_workflow.request_specialist_task.return_value = "test_task_id"
        
        # リクエストデータ
        request_data = {
            "core_agent": CoreAgents.ENGINEER,
            "request_text": "システムアーキテクチャの設計をお願いします。",
            "specialist_type": SpecialistAgents.AI_ARCHITECT,
            "priority": TaskPriority.MEDIUM.value,
            "context": {"project": "test_project"}
        }
        
        # エンドポイントを呼び出し
        response = test_client.post("/specialist/tasks", json=request_data)
        
        # 応答を確認
        assert response.status_code == 201
        result = response.json()
        assert result["task_id"] == "test_task_id"
        assert result["status"] == "success"
        
        # モックが正しく呼び出されたことを確認
        mock_workflow.request_specialist_task.assert_called_once()
    
    def test_create_task_invalid_data(self, mock_task_registry, mock_workflow, test_client):
        """不正なデータによるタスク作成要求を適切に処理できることを確認"""
        # 必須フィールドが不足したリクエストデータ
        request_data = {
            "core_agent": CoreAgents.ENGINEER,
            # request_textが不足
            "specialist_type": SpecialistAgents.AI_ARCHITECT
        }
        
        # エンドポイントを呼び出し
        response = test_client.post("/specialist/tasks", json=request_data)
        
        # 応答を確認（バリデーションエラー）
        assert response.status_code == 422
        assert "detail" in response.json()
    
    def test_get_tasks(self, mock_task_registry, mock_workflow, test_client):
        """タスク一覧取得エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.get_active_tasks.return_value = [
            {
                "task_id": "task1",
                "sender": CoreAgents.ENGINEER,
                "recipient": SpecialistAgents.AI_ARCHITECT,
                "task_type": TaskType.ARCHITECTURE_DESIGN.value,
                "description": "システムアーキテクチャの設計",
                "status": TaskStatus.PENDING.value,
                "created_at": "2023-01-01T00:00:00"
            }
        ]
        
        # エンドポイントを呼び出し（パラメータなし）
        response = test_client.get("/specialist/tasks")
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 1
        assert result[0]["task_id"] == "task1"
        
        # エンドポイントを呼び出し（専門エージェント指定）
        response = test_client.get("/specialist/tasks?specialist_type=ai_architect")
        
        # 応答を確認
        assert response.status_code == 200
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.get_active_tasks.assert_called_with(SpecialistAgents.AI_ARCHITECT)
    
    def test_get_task_by_id(self, mock_task_registry, mock_workflow, test_client):
        """タスク詳細取得エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.get_task_info.return_value = {
            "task_id": "task1",
            "sender": CoreAgents.ENGINEER,
            "recipient": SpecialistAgents.AI_ARCHITECT,
            "task_type": TaskType.ARCHITECTURE_DESIGN.value,
            "description": "システムアーキテクチャの設計",
            "status": TaskStatus.PENDING.value,
            "created_at": "2023-01-01T00:00:00"
        }
        
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/tasks/task1")
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["task_id"] == "task1"
        assert result["recipient"] == SpecialistAgents.AI_ARCHITECT
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.get_task_info.assert_called_once_with("task1")
    
    def test_get_task_by_id_not_found(self, mock_task_registry, mock_workflow, test_client):
        """存在しないタスクIDのリクエストを適切に処理できることを確認"""
        # モックの動作を設定
        mock_task_registry.get_task_info.return_value = None
        
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/tasks/nonexistent")
        
        # 応答を確認（Not Found）
        assert response.status_code == 404
        assert "detail" in response.json()
        assert "not found" in response.json()["detail"].lower()
    
    def test_update_task_status(self, mock_task_registry, mock_workflow, test_client):
        """タスク状態更新エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.update_task_status.return_value = True
        mock_task_registry.get_task_info.return_value = {
            "task_id": "task1",
            "status": TaskStatus.IN_PROGRESS.value
        }
        
        # リクエストデータ
        update_data = {
            "status": TaskStatus.IN_PROGRESS.value,
            "progress": 0.5,
            "message": "50%完了しました"
        }
        
        # エンドポイントを呼び出し
        response = test_client.put("/specialist/tasks/task1/status", json=update_data)
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["task_id"] == "task1"
        assert result["status"] == TaskStatus.IN_PROGRESS.value
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.update_task_status.assert_called_once_with(
            task_id="task1",
            status=TaskStatus.IN_PROGRESS.value,
            progress=0.5,
            message="50%完了しました"
        )
    
    def test_set_task_result(self, mock_task_registry, mock_workflow, test_client):
        """タスク結果設定エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.set_task_result.return_value = True
        mock_task_registry.get_task_info.return_value = {
            "task_id": "task1",
            "result": {"recommendation": "テスト用のアーキテクチャ推奨事項"}
        }
        
        # リクエストデータ
        result_data = {
            "result": {"recommendation": "テスト用のアーキテクチャ推奨事項"},
            "attachments": ["result1.txt", "result2.txt"]
        }
        
        # エンドポイントを呼び出し
        response = test_client.put("/specialist/tasks/task1/result", json=result_data)
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["task_id"] == "task1"
        assert result["result"]["recommendation"] == "テスト用のアーキテクチャ推奨事項"
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.set_task_result.assert_called_once_with(
            task_id="task1",
            result=result_data["result"],
            attachments=result_data["attachments"]
        )
    
    def test_approve_task(self, mock_task_registry, mock_workflow, test_client):
        """タスク承認エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.approve_task.return_value = True
        mock_task_registry.get_task_info.return_value = {
            "task_id": "task1",
            "approved_by_pm": True
        }
        
        # リクエストデータ
        approve_data = {
            "approver": CoreAgents.PM
        }
        
        # エンドポイントを呼び出し
        response = test_client.post("/specialist/tasks/task1/approve", json=approve_data)
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["task_id"] == "task1"
        assert result["approved"] is True
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.approve_task.assert_called_once_with(
            task_id="task1",
            approver=CoreAgents.PM
        )
    
    def test_reject_task(self, mock_task_registry, mock_workflow, test_client):
        """タスク拒否エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_task_registry.reject_task.return_value = True
        mock_task_registry.get_task_info.return_value = {
            "task_id": "task1",
            "rejected_by_pm": True,
            "final_status": TaskStatus.REJECTED.value
        }
        
        # リクエストデータ
        reject_data = {
            "reason": "要件を満たしていません",
            "rejecter": CoreAgents.PM
        }
        
        # エンドポイントを呼び出し
        response = test_client.post("/specialist/tasks/task1/reject", json=reject_data)
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        assert result["task_id"] == "task1"
        assert result["rejected"] is True
        assert result["final_status"] == TaskStatus.REJECTED.value
        
        # モックが正しく呼び出されたことを確認
        mock_task_registry.reject_task.assert_called_once_with(
            task_id="task1",
            reason="要件を満たしていません",
            rejecter=CoreAgents.PM
        )


@patch("api.specialist_api.workflow_automation")
class TestDashboardEndpoints:
    """ダッシュボード関連エンドポイントのテスト"""
    
    def test_get_dashboard_data(self, mock_workflow, test_client, sample_dashboard_data):
        """ダッシュボードデータ取得エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_workflow.get_specialist_dashboard_data.return_value = sample_dashboard_data
        
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/dashboard")
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        
        # 必要なフィールドが含まれていることを確認
        assert "timestamp" in result
        assert "active_tasks_count" in result
        assert "completed_tasks_count" in result
        assert "agents" in result
        assert "recent_activities" in result
        
        # モックが正しく呼び出されたことを確認
        mock_workflow.get_specialist_dashboard_data.assert_called_once()
    
    def test_get_specialist_stats(self, mock_workflow, test_client, sample_dashboard_data):
        """特定の専門エージェントの統計情報取得エンドポイントの動作を確認"""
        # モックの動作を設定
        mock_workflow.get_specialist_dashboard_data.return_value = sample_dashboard_data
        
        # AIアーキテクト向けエンドポイントを呼び出し
        response = test_client.get(f"/specialist/stats/{SpecialistAgents.AI_ARCHITECT}")
        
        # 応答を確認
        assert response.status_code == 200
        result = response.json()
        
        # AIアーキテクトの統計情報が含まれていることを確認
        assert "active_count" in result
        assert "completed_count" in result
        assert "success_rate" in result
        assert "status_distribution" in result
        
        # モックが正しく呼び出されたことを確認
        mock_workflow.get_specialist_dashboard_data.assert_called_once()
    
    def test_get_specialist_stats_invalid_agent(self, mock_workflow, test_client):
        """存在しない専門エージェントの統計情報リクエストを適切に処理できることを確認"""
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/stats/nonexistent")
        
        # 応答を確認（Not Found）
        assert response.status_code == 404
        assert "detail" in response.json()
        assert "not found" in response.json()["detail"].lower()


@patch("api.specialist_api.workflow_automation")
class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    def test_task_not_found(self, mock_workflow, test_client):
        """存在しないタスクIDのリクエストが適切に処理されることを確認"""
        # モックの動作を設定
        mock_workflow.side_effect = ValueError("Task not found")
        
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/tasks/nonexistent")
        
        # 応答を確認（Not Found）
        assert response.status_code == 404
        assert "detail" in response.json()
    
    def test_invalid_operation(self, mock_workflow, test_client):
        """不正な操作が適切に処理されることを確認"""
        # リクエストデータ（不正な状態値）
        update_data = {
            "status": "不正な状態値"
        }
        
        # エンドポイントを呼び出し
        response = test_client.put("/specialist/tasks/task1/status", json=update_data)
        
        # 応答を確認（Bad Request）
        assert response.status_code == 422
        assert "detail" in response.json()
    
    def test_internal_server_error(self, mock_workflow, test_client):
        """サーバー内部エラーが適切に処理されることを確認"""
        # モックの動作を設定
        mock_workflow.get_specialist_dashboard_data.side_effect = Exception("Internal error")
        
        # エンドポイントを呼び出し
        response = test_client.get("/specialist/dashboard")
        
        # 応答を確認（Internal Server Error）
        assert response.status_code == 500
        assert "detail" in response.json()
        assert "internal server error" in response.json()["detail"].lower() 