"""
api/dashboard.py のユニットテスト。
専門エージェント活用状況モニタリングダッシュボードをテストします。
"""

import pytest
import json
import datetime
from unittest.mock import patch, MagicMock

import dash
from dash.testing.application_runners import import_app
from dash.testing.composite import DashComposite

from api.dashboard import (
    app, fetch_dashboard_data, update_dashboard_data,
    create_task_count_indicator, create_task_distribution_chart,
    create_specialist_activity_chart, create_recent_activity_list,
    create_specialist_task_table
)
from utils.workflow_automation import SpecialistAgents, CoreAgents
from utils.agent_communication import TaskStatus, TaskPriority, TaskType


@pytest.fixture
def mock_dashboard_data(sample_dashboard_data):
    """ダッシュボードデータのモック"""
    return sample_dashboard_data


@pytest.fixture
def mock_fetch_data():
    """データ取得関数のパッチ"""
    with patch('api.dashboard.fetch_dashboard_data') as mock_fetch:
        yield mock_fetch


class TestDashboardComponents:
    """ダッシュボードのUIコンポーネントテスト"""
    
    def test_app_initialization(self):
        """Dashアプリが正しく初期化されることを確認"""
        assert isinstance(app, dash.Dash)
        assert app.title == "専門エージェント活用状況モニタリングダッシュボード"
        assert app.layout is not None
        assert len(app.callback_map) > 0  # コールバックが登録されている
    
    def test_create_task_count_indicator(self, mock_dashboard_data):
        """タスクカウントインジケーターが正しく生成されることを確認"""
        active_count = mock_dashboard_data["active_tasks_count"]
        completed_count = mock_dashboard_data["completed_tasks_count"]
        
        # アクティブタスク用インジケーター
        active_indicator = create_task_count_indicator(
            "アクティブタスク", active_count, "primary"
        )
        assert active_indicator is not None
        
        # 完了タスク用インジケーター
        completed_indicator = create_task_count_indicator(
            "完了タスク", completed_count, "success"
        )
        assert completed_indicator is not None
    
    def test_create_task_distribution_chart(self, mock_dashboard_data):
        """タスク分布チャートが正しく生成されることを確認"""
        data = mock_dashboard_data
        
        chart = create_task_distribution_chart(data)
        assert chart is not None
        assert "data" in chart
        assert "layout" in chart
    
    def test_create_specialist_activity_chart(self, mock_dashboard_data):
        """専門エージェント活動チャートが正しく生成されることを確認"""
        data = mock_dashboard_data
        
        chart = create_specialist_activity_chart(data)
        assert chart is not None
        assert "data" in chart
        assert "layout" in chart
    
    def test_create_recent_activity_list(self, mock_dashboard_data):
        """最近の活動リストが正しく生成されることを確認"""
        activities = mock_dashboard_data["recent_activities"]
        
        activity_list = create_recent_activity_list(activities)
        assert activity_list is not None
        assert len(activity_list.children) > 0
    
    def test_create_specialist_task_table(self, mock_dashboard_data):
        """専門エージェントタスクテーブルが正しく生成されることを確認"""
        agent_data = mock_dashboard_data["agents"][SpecialistAgents.AI_ARCHITECT]
        
        # アクティブタスクのテーブル
        active_table = create_specialist_task_table(agent_data["active_tasks"], "アクティブタスク")
        assert active_table is not None
        
        # 完了タスクのテーブル
        completed_table = create_specialist_task_table(agent_data["completed_tasks"], "完了タスク")
        assert completed_table is not None


class TestDashboardData:
    """ダッシュボードデータ取得・更新のテスト"""
    
    @patch("api.dashboard.requests.get")
    def test_fetch_dashboard_data(self, mock_get):
        """fetch_dashboard_data関数が正しく動作することを確認"""
        # モックの設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "timestamp": datetime.datetime.now().isoformat(),
            "active_tasks_count": 3,
            "completed_tasks_count": 2,
            "agents": {},
            "recent_activities": []
        }
        mock_get.return_value = mock_response
        
        # 関数を呼び出し
        data = fetch_dashboard_data()
        
        # 結果を確認
        assert data is not None
        assert data["active_tasks_count"] == 3
        assert data["completed_tasks_count"] == 2
        
        # 正しいURLが呼び出されたことを確認
        mock_get.assert_called_once_with("http://localhost:8000/specialist/dashboard")
    
    @patch("api.dashboard.requests.get")
    def test_fetch_dashboard_data_error(self, mock_get):
        """APIエラー時にfetch_dashboard_data関数が適切に処理されることを確認"""
        # モックの設定（エラー応答）
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # 関数を呼び出し
        data = fetch_dashboard_data()
        
        # 結果を確認（デフォルト値が返される）
        assert data is not None
        assert data["active_tasks_count"] == 0
        assert data["completed_tasks_count"] == 0
        assert SpecialistAgents.AI_ARCHITECT in data["agents"]
        assert SpecialistAgents.PROMPT_ENGINEER in data["agents"]
        assert SpecialistAgents.DATA_ENGINEER in data["agents"]
    
    @patch("api.dashboard.fetch_dashboard_data")
    def test_update_dashboard_data(self, mock_fetch):
        """update_dashboard_data関数が正しく動作することを確認"""
        # モックの設定
        mock_fetch.return_value = {
            "timestamp": datetime.datetime.now().isoformat(),
            "active_tasks_count": 3,
            "completed_tasks_count": 2,
            "agents": {},
            "recent_activities": []
        }
        
        # 関数を呼び出し
        interval, data_store = update_dashboard_data(n_intervals=5)
        
        # 結果を確認
        assert interval == 5
        assert data_store is not None
        assert json.loads(data_store)["active_tasks_count"] == 3
        
        # データ取得関数が呼び出されたことを確認
        mock_fetch.assert_called_once()


class TestDashboardCallbacks:
    """ダッシュボードコールバックのテスト"""
    
    @patch("api.dashboard.fetch_dashboard_data")
    def test_interval_callback(self, mock_fetch, mock_dashboard_data):
        """インターバルコールバックが正しく動作することを確認"""
        # モックの設定
        mock_fetch.return_value = mock_dashboard_data
        
        # アプリのコールバックを確認
        assert "interval-component.n_intervals" in app.callback_map
        
        # コールバック関数を直接呼び出し
        outputs = update_dashboard_data(n_intervals=10)
        
        # 出力が期待通りであることを確認
        assert len(outputs) == 2
        assert outputs[0] == 10
        assert outputs[1] is not None
        assert "dashboard-data-store" in app.callback_map


@pytest.mark.skip(reason="Requires a running server for integration testing")
class TestDashboardIntegration:
    """ダッシュボードの統合テスト"""
    
    def test_dashboard_initial_load(self, dash_duo, mock_fetch_data, mock_dashboard_data):
        """ダッシュボードの初期ロードが正しく行われることを確認"""
        # モックの設定
        mock_fetch_data.return_value = mock_dashboard_data
        
        # ダッシュボードを起動
        dash_duo.start_server(app)
        
        # ロードを待機
        dash_duo.wait_for_element("#dashboard-content")
        
        # 主要なコンポーネントが表示されていることを確認
        assert dash_duo.find_element("#task-counts-row") is not None
        assert dash_duo.find_element("#task-distribution-chart") is not None
        assert dash_duo.find_element("#specialist-activity-chart") is not None
        assert dash_duo.find_element("#recent-activity-list") is not None 