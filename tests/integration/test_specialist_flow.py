"""
専門エージェント連携フローの統合テスト。
エンドツーエンドの流れが正しく動作することを確認します。
"""

import pytest
import os
import json
import time
import threading
import subprocess
from unittest.mock import patch, MagicMock

from utils.agent_communication import TaskStatus, TaskPriority, TaskType
from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, task_registry,
    workflow_automation, request_ai_architect_task
)
from utils.specialist_triggers import request_specialist_if_needed


@pytest.fixture
def setup_temp_storage(temp_storage_dir):
    """テスト用のストレージディレクトリをセットアップ"""
    # 環境変数を一時的に変更
    original_storage = os.environ.get("STORAGE_DIR", "")
    os.environ["STORAGE_DIR"] = temp_storage_dir
    
    yield temp_storage_dir
    
    # 環境変数を元に戻す
    os.environ["STORAGE_DIR"] = original_storage


@pytest.fixture
def api_server(request):
    """APIサーバーを起動するフィクスチャ"""
    # APIサーバーをバックグラウンドで起動
    process = subprocess.Popen(
        ["python", "-m", "api.run_api", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # サーバーの起動を待機
    time.sleep(2)
    
    yield process
    
    # テスト終了後にサーバーを終了
    process.terminate()
    process.wait()


@pytest.mark.integration
@patch("utils.specialist_triggers.trigger_analyzer")
@patch("utils.agent_communication.dispatcher")
class TestSpecialistWorkflow:
    """専門エージェント連携ワークフローの統合テスト"""
    
    def test_end_to_end_ai_architect_flow(self, mock_dispatcher, mock_analyzer, setup_temp_storage):
        """AIアーキテクトとの連携フローが正しく動作することを確認"""
        # トリガー分析のモック設定
        mock_analyzer.analyze_request.return_value = (True, SpecialistAgents.AI_ARCHITECT, 0.85)
        
        # メッセージディスパッチャーのモック設定
        mock_dispatcher.send_message.return_value = True
        mock_dispatcher.get_task_status.return_value = TaskStatus.PENDING.value
        
        # 1. タスク依頼のリクエスト
        request_text = "システムアーキテクチャ設計を支援してください。スケーラビリティが必要です。"
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=request_text
        )
        
        # タスクIDが生成されていることを確認
        assert task_id is not None
        assert isinstance(task_id, str)
        
        # 2. レジストリにタスクが登録されていることを確認
        task_info = task_registry.get_task_info(task_id)
        assert task_info is not None
        assert task_info["sender"] == CoreAgents.ENGINEER
        assert task_info["recipient"] == SpecialistAgents.AI_ARCHITECT
        assert task_info["status"] == TaskStatus.PENDING.value
        
        # 3. PMによるタスク承認
        task_registry.approve_task(task_id, CoreAgents.PM)
        
        # タスクが承認されていることを確認
        task_info = task_registry.get_task_info(task_id)
        assert task_info["approved_by_pm"] is True
        
        # 4. 専門エージェントによるタスク処理（ステータス更新）
        task_registry.update_task_status(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS.value,
            progress=0.5,
            message="アーキテクチャ設計の50%が完了しました"
        )
        
        # ステータスが更新されていることを確認
        task_info = task_registry.get_task_info(task_id)
        assert task_info["status"] == TaskStatus.IN_PROGRESS.value
        assert task_info["progress"] == 0.5
        
        # 5. 専門エージェントによるタスク結果の設定
        result = {
            "architecture": {
                "type": "マイクロサービス",
                "components": ["APIゲートウェイ", "認証サービス", "コアサービス"],
                "databases": ["PostgreSQL", "Redis"]
            },
            "recommendations": [
                "Kubernetes上での展開を推奨",
                "水平スケーリングのためのステートレス設計"
            ]
        }
        
        task_registry.set_task_result(
            task_id=task_id,
            result=result,
            attachments=["architecture_diagram.png"]
        )
        
        # 結果が設定されていることを確認
        task_info = task_registry.get_task_info(task_id)
        assert "result" in task_info
        assert task_info["result"]["architecture"]["type"] == "マイクロサービス"
        assert "attachments" in task_info
        assert task_info["attachments"] == ["architecture_diagram.png"]
        
        # 6. タスク完了
        task_registry.update_task_status(
            task_id=task_id,
            status=TaskStatus.COMPLETED.value,
            progress=1.0,
            message="アーキテクチャ設計が完了しました"
        )
        
        # タスクが完了タスクに移動していることを確認
        task_info = task_registry.get_task_info(task_id)
        assert task_info["final_status"] == TaskStatus.COMPLETED.value
        
        # 履歴にイベントが記録されていることを確認
        history = task_registry.get_task_history()
        assert len(history) >= 6  # 登録、承認、進捗更新、結果設定、完了の最低5イベント
        
        # ファイルに保存されていることを確認（オプション）
        task_registry.save_to_file(os.path.join(setup_temp_storage, "tasks.json"))
        assert os.path.exists(os.path.join(setup_temp_storage, "tasks.json"))
    
    def test_rejection_flow(self, mock_dispatcher, mock_analyzer, setup_temp_storage):
        """タスク拒否フローが正しく動作することを確認"""
        # トリガー分析のモック設定
        mock_analyzer.analyze_request.return_value = (True, SpecialistAgents.PROMPT_ENGINEER, 0.75)
        
        # メッセージディスパッチャーのモック設定
        mock_dispatcher.send_message.return_value = True
        
        # 1. タスク依頼のリクエスト
        request_text = "プロンプト最適化を支援してください。"
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=request_text
        )
        
        # 2. PMによるタスク拒否
        task_registry.reject_task(
            task_id=task_id,
            reason="現段階では優先度が低いです",
            rejecter=CoreAgents.PM
        )
        
        # タスクが拒否されていることを確認
        task_info = task_registry.get_task_info(task_id)
        assert task_info["rejected_by_pm"] is True
        assert task_info["rejection_reason"] == "現段階では優先度が低いです"
        assert task_info["final_status"] == TaskStatus.REJECTED.value
        
        # 履歴に拒否イベントが記録されていることを確認
        history = task_registry.get_task_history()
        rejection_events = [h for h in history if h.get("event_type") == "task_rejection"]
        assert len(rejection_events) > 0
    
    @pytest.mark.parametrize("specialist_type", [
        SpecialistAgents.AI_ARCHITECT,
        SpecialistAgents.PROMPT_ENGINEER,
        SpecialistAgents.DATA_ENGINEER
    ])
    def test_dashboard_data_integration(self, mock_dispatcher, mock_analyzer, setup_temp_storage, specialist_type):
        """ダッシュボードデータ生成が正しく動作することを確認"""
        # 各種専門エージェント向けのタスクを作成
        mock_analyzer.analyze_request.return_value = (True, specialist_type, 0.8)
        mock_dispatcher.send_message.return_value = True
        
        # タスクを登録
        request_text = f"{specialist_type}向けのタスクです"
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=request_text
        )
        
        # ステータスを更新
        task_registry.update_task_status(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS.value
        )
        
        # ダッシュボードデータを取得
        dashboard_data = workflow_automation.get_specialist_dashboard_data()
        
        # データ構造を確認
        assert "timestamp" in dashboard_data
        assert "active_tasks_count" in dashboard_data
        assert dashboard_data["active_tasks_count"] >= 1
        assert "agents" in dashboard_data
        assert specialist_type in dashboard_data["agents"]
        
        # 該当エージェントのデータを確認
        agent_data = dashboard_data["agents"][specialist_type]
        assert "active_tasks" in agent_data
        assert len(agent_data["active_tasks"]) >= 1
        assert "stats" in agent_data
        
        # 最近の活動に記録されていることを確認
        assert "recent_activities" in dashboard_data
        assert len(dashboard_data["recent_activities"]) >= 1


@pytest.mark.integration
class TestAPIIntegration:
    """API連携の統合テスト"""
    
    def test_api_server_integration(self, api_server):
        """APIサーバーとの連携テスト"""
        import requests
        
        # APIサーバーが起動していることを確認
        try:
            response = requests.get("http://localhost:8000/")
            assert response.status_code == 200
        except requests.ConnectionError as e:
            pytest.fail(f"APIサーバーが接続できません: {e}")
        
        # タスク作成リクエスト
        task_data = {
            "core_agent": CoreAgents.ENGINEER,
            "request_text": "テスト用のシステムアーキテクチャ設計を支援してください",
            "specialist_type": SpecialistAgents.AI_ARCHITECT,
            "priority": TaskPriority.MEDIUM.value
        }
        
        response = requests.post("http://localhost:8000/specialist/tasks", json=task_data)
        assert response.status_code == 201
        
        task_id = response.json()["task_id"]
        assert task_id is not None
        
        # タスク取得
        response = requests.get(f"http://localhost:8000/specialist/tasks/{task_id}")
        assert response.status_code == 200
        task_info = response.json()
        assert task_info["task_id"] == task_id
        
        # ダッシュボードデータ取得
        response = requests.get("http://localhost:8000/specialist/dashboard")
        assert response.status_code == 200
        dashboard_data = response.json()
        assert "agents" in dashboard_data
        
        # APIサーバーのクリーンアップ（オプション）
        # 実際の実装では、テスト用のデータをクリーンアップする処理を追加 