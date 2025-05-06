"""
api/run_api.py のユニットテスト。
専門エージェント連携APIサーバー起動スクリプトをテストします。
"""

import pytest
import sys
import signal
import threading
import subprocess
import time
from unittest.mock import patch, MagicMock, call

# インポートの前にパッチを適用
with patch.dict('sys.modules', {
    'api.specialist_api': MagicMock(),
    'uvicorn': MagicMock(),
    'api.dashboard': MagicMock()
}):
    from api.run_api import (
        run_api_server, run_dashboard_server,
        run_servers_threaded, run_servers_subprocess
    )


class TestAPIServer:
    """APIサーバー起動関数のテスト"""
    
    def test_run_api_server(self):
        """run_api_server関数が正しく動作することを確認"""
        with patch('api.run_api.uvicorn') as mock_uvicorn:
            with patch('api.run_api.specialist_api') as mock_specialist_api:
                # モックの設定
                mock_specialist_api.app = "mock_app"
                
                # 関数を実行
                run_api_server(port=9000, host="127.0.0.1", debug=True)
                
                # uvicorn.runが呼び出されたことを確認
                mock_uvicorn.run.assert_called_once()
                args, kwargs = mock_uvicorn.run.call_args
                assert args[0] == "mock_app"  # appが渡されていること
                assert kwargs["port"] == 9000
                assert kwargs["host"] == "127.0.0.1"
                assert kwargs["debug"] is True
    
    def test_run_dashboard_server(self):
        """run_dashboard_server関数が正しく動作することを確認"""
        with patch('api.run_api.dashboard') as mock_dashboard:
            # モックの設定
            mock_app = MagicMock()
            mock_dashboard.app = mock_app
            
            # 関数を実行
            run_dashboard_server(port=9050, host="127.0.0.1", debug=True)
            
            # app.runが呼び出されたことを確認
            mock_app.run.assert_called_once()
            args, kwargs = mock_app.run.call_args
            assert kwargs["port"] == 9050
            assert kwargs["host"] == "127.0.0.1"
            assert kwargs["debug"] is True


class TestThreadedServers:
    """スレッドベースのサーバー起動のテスト"""
    
    @patch("api.run_api.threading.Thread")
    @patch("api.run_api.time.sleep", side_effect=KeyboardInterrupt)  # Ctrl+Cをシミュレート
    def test_run_servers_threaded(self, mock_sleep, mock_thread):
        """run_servers_threaded関数が正しく動作することを確認"""
        # モックスレッドを設定
        mock_api_thread = MagicMock()
        mock_dashboard_thread = MagicMock()
        mock_thread.side_effect = [mock_api_thread, mock_dashboard_thread]
        
        # 関数を実行（KeyboardInterruptによりループを抜ける）
        run_servers_threaded(api_port=9000, dashboard_port=9050, debug=True)
        
        # スレッドが作成されたことを確認
        assert mock_thread.call_count == 2
        
        # APIサーバーのスレッドが作成されたことを確認
        api_call = mock_thread.call_args_list[0]
        assert api_call[1]["target"] == run_api_server
        assert api_call[1]["kwargs"]["port"] == 9000
        assert api_call[1]["kwargs"]["debug"] is True
        
        # ダッシュボードサーバーのスレッドが作成されたことを確認
        dashboard_call = mock_thread.call_args_list[1]
        assert dashboard_call[1]["target"] == run_dashboard_server
        assert dashboard_call[1]["kwargs"]["port"] == 9050
        assert dashboard_call[1]["kwargs"]["debug"] is True
        
        # スレッドが開始されたことを確認
        mock_api_thread.start.assert_called_once()
        mock_dashboard_thread.start.assert_called_once()


class TestSubprocessServers:
    """サブプロセスベースのサーバー起動のテスト"""
    
    @patch("api.run_api.subprocess.Popen")
    @patch("api.run_api.sys.executable", "/path/to/python")
    def test_run_servers_subprocess(self, mock_popen):
        """run_servers_subprocess関数が正しく動作することを確認"""
        # モックのプロセスを設定
        mock_api_process = MagicMock()
        mock_dashboard_process = MagicMock()
        # KeyboardInterruptをシミュレートするため、最初の待機でKeyboardInterruptを発生させる
        mock_api_process.wait.side_effect = KeyboardInterrupt
        mock_popen.side_effect = [mock_api_process, mock_dashboard_process]
        
        # 関数を実行
        run_servers_subprocess(api_port=9000, dashboard_port=9050, debug=True)
        
        # サブプロセスが作成されたことを確認
        assert mock_popen.call_count == 2
        
        # APIサーバーのサブプロセスが正しいコマンドで作成されたことを確認
        api_call = mock_popen.call_args_list[0]
        api_cmd = api_call[0][0]
        assert "/path/to/python" in api_cmd
        assert "-m" in api_cmd
        assert "uvicorn" in api_cmd
        assert "api.specialist_api:app" in api_cmd
        assert "--port" in api_cmd
        assert "9000" in api_cmd
        
        # ダッシュボードサーバーのサブプロセスが正しいコマンドで作成されたことを確認
        dashboard_call = mock_popen.call_args_list[1]
        dashboard_cmd = dashboard_call[0][0]
        assert "/path/to/python" in dashboard_cmd
        assert "api/dashboard.py" in dashboard_cmd
        
        # プロセスが終了されたことを確認
        mock_api_process.terminate.assert_called_once()
        mock_dashboard_process.terminate.assert_called_once()


@patch("api.run_api.argparse.ArgumentParser.parse_args")
class TestArgumentParsing:
    """コマンドライン引数解析のテスト"""
    
    @patch("api.run_api.run_servers_subprocess")
    def test_main_subprocess_method(self, mock_run_subprocess, mock_parse_args):
        """サブプロセス方式のメイン関数実行をテスト"""
        # コマンドライン引数をモック
        args = MagicMock()
        args.api_port = 9000
        args.dashboard_port = 9050
        args.debug = True
        args.method = "subprocess"
        mock_parse_args.return_value = args
        
        # テスト対象の関数を実行
        import api.run_api
        api.run_api.main()
        
        # サブプロセス方式で起動されたことを確認
        mock_run_subprocess.assert_called_once_with(9000, 9050, True)
    
    @patch("api.run_api.run_servers_threaded")
    def test_main_thread_method(self, mock_run_threaded, mock_parse_args):
        """スレッド方式のメイン関数実行をテスト"""
        # コマンドライン引数をモック
        args = MagicMock()
        args.api_port = 9000
        args.dashboard_port = 9050
        args.debug = True
        args.method = "thread"
        mock_parse_args.return_value = args
        
        # テスト対象の関数を実行
        import api.run_api
        api.run_api.main()
        
        # スレッド方式で起動されたことを確認
        mock_run_threaded.assert_called_once_with(9000, 9050, True)


class TestSignalHandling:
    """シグナルハンドリングのテスト"""
    
    @patch("api.run_api.subprocess.Popen")
    @patch("api.run_api.sys.executable", "/path/to/python")
    def test_keyboard_interrupt_handling(self, mock_popen):
        """KeyboardInterrupt（Ctrl+C）が適切に処理されることを確認"""
        # モックのプロセスを設定
        mock_api_process = MagicMock()
        mock_dashboard_process = MagicMock()
        # KeyboardInterruptをシミュレート
        mock_api_process.wait.side_effect = KeyboardInterrupt
        mock_popen.side_effect = [mock_api_process, mock_dashboard_process]
        
        # 関数を実行
        run_servers_subprocess(api_port=9000, dashboard_port=9050)
        
        # プロセスが終了されたことを確認
        mock_api_process.terminate.assert_called_once()
        mock_dashboard_process.terminate.assert_called_once()
    
    @patch("api.run_api.subprocess.Popen")
    @patch("api.run_api.sys.executable", "/path/to/python")
    def test_process_timeout_handling(self, mock_popen):
        """プロセス終了がタイムアウトした場合、強制終了されることを確認"""
        # モックのプロセスを設定
        mock_api_process = MagicMock()
        mock_dashboard_process = MagicMock()
        # タイムアウトをシミュレート
        mock_api_process.wait.side_effect = KeyboardInterrupt
        mock_api_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_popen.side_effect = [mock_api_process, mock_dashboard_process]
        
        # 関数を実行
        run_servers_subprocess(api_port=9000, dashboard_port=9050)
        
        # プロセスが強制終了されたことを確認
        mock_api_process.kill.assert_called_once() 