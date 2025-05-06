"""
api/dashboard.py のユニットテスト。
専門エージェント活用状況モニタリングダッシュボードをテストします。
"""

import pytest
import json
import datetime
from unittest.mock import patch, MagicMock
import requests

import dash

# percy関連のインポートはスキップ
# from dash.testing.application_runners import import_app
# from dash.testing.composite import DashComposite

from api.dashboard import (
    app, get_dashboard_data, update_dashboard_data
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
    with patch('api.dashboard.get_dashboard_data') as mock_fetch:
        yield mock_fetch


class TestDashboardComponents:
    """ダッシュボードのUIコンポーネントテスト"""
    
    def test_app_initialization(self):
        """Dashアプリが正しく初期化されることを確認"""
        assert isinstance(app, dash.Dash)
        assert app.title == "専門エージェント活用状況モニタリングダッシュボード"
        assert app.layout is not None
        assert len(app.callback_map) > 0  # コールバックが登録されている


class TestDashboardData:
    """ダッシュボードデータ取得・更新のテスト"""
    
    @patch("api.dashboard.requests.get")
    def test_get_dashboard_data(self, mock_get):
        """get_dashboard_data関数が正しく動作することを確認"""
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
        data = get_dashboard_data()
        
        # 結果を確認
        assert data is not None
        assert data["active_tasks_count"] == 3
        assert data["completed_tasks_count"] == 2
        
        # 正しいURLが呼び出されたことを確認
        mock_get.assert_called_once_with("http://localhost:8000/specialist/dashboard")
    
    @patch("api.dashboard.requests.get")
    def test_get_dashboard_data_error(self, mock_get):
        """APIエラー時にget_dashboard_data関数が適切に処理されることを確認"""
        # モックの設定（エラー応答）
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Internal Server Error")
        mock_get.return_value = mock_response
        
        # 関数を呼び出し
        data = get_dashboard_data()
        
        # 結果を確認
        assert data is None
    
    @patch("api.dashboard.get_dashboard_data")
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
        result = update_dashboard_data(5, 10)
        
        # 結果を確認
        assert result is not None
        
        # データ取得関数が呼び出されたことを確認
        mock_fetch.assert_called_once()


class TestDashboardCallbacks:
    """ダッシュボードコールバックのテスト"""
    
    @patch("api.dashboard.get_dashboard_data")
    def test_interval_callback(self, mock_fetch, mock_dashboard_data):
        """インターバルコールバックが正しく動作することを確認"""
        # モックの設定
        mock_fetch.return_value = mock_dashboard_data
        
        # アプリのコールバックを確認
        assert "dashboard-data.data" in app.callback_map
        
        # dashboard-data.dataコールバックの入力に自動更新インターバルが含まれていることを確認
        inputs = app.callback_map["dashboard-data.data"]["inputs"]
        input_ids = [input_item["id"] for input_item in inputs]
        assert "auto-refresh" in input_ids
        
        # コールバック関数を直接呼び出し
        result = update_dashboard_data(10, 5)
        
        # 出力が想定通りであることを確認
        assert result is not None


@pytest.mark.skip(reason="Requires Percy client which is not available")
class TestDashboardIntegration:
    """ダッシュボードの統合テスト"""
    
    def test_dashboard_initial_load(self, dash_duo, mock_fetch_data, mock_dashboard_data):
        """ダッシュボードの初期ロードが正しく行われることを確認"""
        # モックの設定
        mock_fetch_data.return_value = mock_dashboard_data
        
        # ダッシュボードを起動
        dash_duo.start_server(app)
        
        # ロードを待機
        dash_duo.wait_for_element("body")
        
        # ダッシュボードのレイアウトがロードされたことを確認
        assert dash_duo.find_element("div") is not None 