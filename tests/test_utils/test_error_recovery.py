"""
エラー処理と回復力強化モジュールのユニットテスト。
TaskRetryManager、ErrorRecoveryService、およびヘルパー関数のテストを行います。
"""

import pytest
from unittest.mock import patch, MagicMock, call
import time
from datetime import datetime

from utils.error_recovery import (
    ErrorSeverity, ErrorCategory, RecoveryStrategy, ErrorInfo,
    TaskRetryManager, ErrorRecoveryService,
    handle_task_error, register_alternative_strategy,
    get_task_error_history, reset_task_error_history
)


class TestErrorClasses:
    """エラー関連クラスのテスト"""
    
    def test_error_info_creation(self):
        """ErrorInfoクラスの作成テスト"""
        # テスト用のエラーを作成
        test_error = ValueError("テスト用エラー")
        
        # ErrorInfoオブジェクトを作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=test_error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DATA,
            context={"task_type": "data_processing"}
        )
        
        # 属性が正しく設定されることを確認
        assert error_info.task_id == "task-123"
        assert error_info.error == test_error
        assert error_info.error_message == "テスト用エラー"
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.category == ErrorCategory.DATA
        assert error_info.context == {"task_type": "data_processing"}
        assert isinstance(error_info.timestamp, datetime)
        assert error_info.recovery_attempts == []
    
    def test_error_info_to_dict(self):
        """ErrorInfo.to_dict()メソッドのテスト"""
        # テスト用のエラーを作成
        test_error = ValueError("テスト用エラー")
        
        # ErrorInfoオブジェクトを作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=test_error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DATA,
            context={"task_type": "data_processing"}
        )
        
        # to_dict()の結果を取得
        result = error_info.to_dict()
        
        # 辞書の構造が正しいことを確認
        assert isinstance(result, dict)
        assert result["task_id"] == "task-123"
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "テスト用エラー"
        assert result["severity"] == "medium"
        assert result["category"] == "data"
        assert result["context"] == {"task_type": "data_processing"}
        assert "timestamp" in result
        assert "stack_trace" in result
        assert result["recovery_attempts"] == []
    
    def test_add_recovery_attempt(self):
        """ErrorInfo.add_recovery_attempt()メソッドのテスト"""
        # ErrorInfoオブジェクトを作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=ValueError("テスト用エラー"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DATA
        )
        
        # 回復試行を追加
        error_info.add_recovery_attempt(
            strategy=RecoveryStrategy.RETRY,
            result=True,
            details={"attempt": 1}
        )
        
        # 回復試行が正しく追加されることを確認
        assert len(error_info.recovery_attempts) == 1
        attempt = error_info.recovery_attempts[0]
        assert attempt["strategy"] == "retry"
        assert attempt["result"] is True
        assert attempt["details"] == {"attempt": 1}
        assert "timestamp" in attempt


class TestTaskRetryManager:
    """TaskRetryManagerクラスのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        self.retry_manager = TaskRetryManager(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            jitter=False  # テストの再現性のためjitterを無効化
        )
    
    def test_should_retry_first_attempt(self):
        """初回試行時の再試行判断テスト"""
        # 中程度の重大度のエラー情報を作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=ValueError("テスト用エラー"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DATA
        )
        
        # 初回は再試行可能であることを確認
        assert self.retry_manager.should_retry("task-123", error_info) is True
    
    def test_should_retry_max_retries_reached(self):
        """最大再試行回数到達時のテスト"""
        # 再試行回数を最大値に設定
        self.retry_manager.retry_counts["task-123"] = 3
        
        # エラー情報を作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=ValueError("テスト用エラー"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DATA
        )
        
        # 最大再試行回数に達した場合は再試行不可能であることを確認
        assert self.retry_manager.should_retry("task-123", error_info) is False
    
    def test_should_retry_critical_error(self):
        """致命的なエラーの再試行判断テスト"""
        # 致命的なエラー情報を作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=ValueError("致命的なエラー"),
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.DATA
        )
        
        # 致命的なエラーは再試行不可能であることを確認
        assert self.retry_manager.should_retry("task-123", error_info) is False
    
    def test_should_retry_permission_error(self):
        """権限エラーの再試行判断テスト"""
        # 権限エラー情報を作成
        error_info = ErrorInfo(
            task_id="task-123",
            error=ValueError("権限エラー"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PERMISSION
        )
        
        # 権限エラーは再試行不可能であることを確認
        assert self.retry_manager.should_retry("task-123", error_info) is False
    
    def test_get_retry_delay(self):
        """再試行遅延時間計算のテスト"""
        # 初回（count=0）の遅延時間
        delay0 = self.retry_manager.get_retry_delay("task-123")
        assert delay0 == 1.0  # base_delay
        
        # 1回目（count=1）の遅延時間
        self.retry_manager.retry_counts["task-123"] = 1
        delay1 = self.retry_manager.get_retry_delay("task-123")
        assert delay1 == 2.0  # base_delay * 2^1
        
        # 2回目（count=2）の遅延時間
        self.retry_manager.retry_counts["task-123"] = 2
        delay2 = self.retry_manager.get_retry_delay("task-123")
        assert delay2 == 4.0  # base_delay * 2^2
        
        # 最大遅延を超える場合
        self.retry_manager.retry_counts["task-123"] = 10
        delay10 = self.retry_manager.get_retry_delay("task-123")
        assert delay10 == 10.0  # max_delay
    
    def test_increment_retry_count(self):
        """再試行回数インクリメントのテスト"""
        # 初期状態
        assert self.retry_manager.get_retry_count("task-123") == 0
        
        # インクリメント
        self.retry_manager.increment_retry_count("task-123")
        assert self.retry_manager.get_retry_count("task-123") == 1
        
        # 再度インクリメント
        self.retry_manager.increment_retry_count("task-123")
        assert self.retry_manager.get_retry_count("task-123") == 2
    
    def test_reset_retry_count(self):
        """再試行回数リセットのテスト"""
        # 回数を設定
        self.retry_manager.retry_counts["task-123"] = 2
        
        # リセット
        self.retry_manager.reset_retry_count("task-123")
        
        # カウントがリセットされることを確認
        assert "task-123" not in self.retry_manager.retry_counts


@patch("utils.error_recovery.send_message_to_agent")
@patch("utils.error_recovery.create_error_notification")
class TestErrorRecoveryService:
    """ErrorRecoveryServiceクラスのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        # テスト用の再試行マネージャーを作成
        self.retry_manager = TaskRetryManager(
            max_retries=2,
            base_delay=0.1,  # テストの高速化のため小さい値を設定
            max_delay=0.5,
            jitter=False
        )
        
        # テスト用のエラー回復サービスを作成
        self.recovery_service = ErrorRecoveryService(self.retry_manager)
    
    def test_handle_error_retry(self, mock_create_notification, mock_send_message):
        """再試行による回復戦略のテスト"""
        # モックの設定
        mock_create_notification.return_value = {"type": "error_notification"}
        
        # エラー処理を実行
        success, result = self.recovery_service.handle_error(
            task_id="task-123",
            error=ValueError("テスト用エラー"),
            context={"task_type": "data_processing"},
            notify_agents=["PM"]
        )
        
        # 結果の検証
        assert success is False  # 再試行中なのでFalse
        assert result["strategy"] == "exponential_backoff"
        assert result["retry_count"] == 1
        
        # エラー履歴が作成されることを確認
        assert "task-123" in self.recovery_service.error_history
        error_info = self.recovery_service.error_history["task-123"][0]
        assert error_info.error_message == "テスト用エラー"
        
        # 通知が送信されることを確認
        mock_create_notification.assert_called_once()
        mock_send_message.assert_called_once_with("PM", {"type": "error_notification"})
    
    def test_handle_error_critical(self, mock_create_notification, mock_send_message):
        """致命的なエラーの処理テスト"""
        # エラー処理を実行（致命的なエラー）
        success, result = self.recovery_service.handle_error(
            task_id="task-123",
            error=ValueError("致命的なエラー"),
            context={"critical": True, "task_type": "data_processing"}
        )
        
        # 結果の検証
        assert success is False
        assert result["strategy"] == "human_intervention"
        assert "message" in result
    
    def test_handle_error_alternative_strategy(self, mock_create_notification, mock_send_message):
        """代替戦略による回復テスト"""
        # 代替戦略を登録
        mock_strategy = MagicMock(return_value={"status": "success"})
        self.recovery_service.register_alternative_strategy(
            task_type="data_processing",
            error_category=ErrorCategory.DATA,
            strategy_func=mock_strategy
        )
        
        # 最大再試行回数に達するようにカウントを設定
        self.retry_manager.retry_counts["task-123"] = 2
        
        # エラー処理を実行
        success, result = self.recovery_service.handle_error(
            task_id="task-123",
            error=ValueError("データエラー"),
            context={"task_type": "data_processing"}
        )
        
        # 結果の検証
        assert success is True  # 代替戦略が成功
        assert result["strategy"] == "alternative_method"
        assert "result" in result
        
        # 代替戦略が呼び出されることを確認
        mock_strategy.assert_called_once_with("task-123", {"task_type": "data_processing"})
    
    def test_handle_error_graceful_degradation(self, mock_create_notification, mock_send_message):
        """機能劣化による継続テスト"""
        # 最大再試行回数に達するようにカウントを設定
        self.retry_manager.retry_counts["task-123"] = 2
        
        # 未知のタスク種別でエラー処理を実行（代替戦略なし）
        success, result = self.recovery_service.handle_error(
            task_id="task-123",
            error=ValueError("軽微なエラー"),
            context={"task_type": "unknown_task"}
        )
        
        # 結果の検証
        assert success is True  # 機能劣化で継続
        assert result["strategy"] == "graceful_degradation"
        assert result["degraded"] is True
    
    def test_handle_error_human_intervention(self, mock_create_notification, mock_send_message):
        """人間の介入を要求するテスト"""
        # 最大再試行回数に達するようにカウントを設定
        self.retry_manager.retry_counts["task-123"] = 2
        
        # 重大なエラーで処理を実行
        success, result = self.recovery_service.handle_error(
            task_id="task-123",
            error=ValueError("重大なエラー"),
            context={"task_type": "unknown_task"},
            notify_agents=["PM", "PdM"]
        )
        
        # 結果の検証
        assert success is False
        assert result["strategy"] == "human_intervention"
        assert "message" in result
        
        # 複数のエージェントに通知されることを確認
        assert mock_send_message.call_count == 2
    
    def test_error_history_management(self, mock_create_notification, mock_send_message):
        """エラー履歴管理のテスト"""
        # 複数のエラーを発生させる
        self.recovery_service.handle_error(
            task_id="task-1",
            error=ValueError("エラー1"),
            context={"task_type": "task1"}
        )
        
        self.recovery_service.handle_error(
            task_id="task-2",
            error=ValueError("エラー2"),
            context={"task_type": "task2"}
        )
        
        self.recovery_service.handle_error(
            task_id="task-1",
            error=ValueError("エラー1-2"),
            context={"task_type": "task1"}
        )
        
        # 全タスクのエラー履歴を取得
        all_history = self.recovery_service.get_error_history()
        assert len(all_history) == 2  # 2つのタスク
        assert len(all_history["task-1"]) == 2  # task-1は2回エラー
        assert len(all_history["task-2"]) == 1  # task-2は1回エラー
        
        # 特定タスクのエラー履歴を取得
        task1_history = self.recovery_service.get_error_history("task-1")
        assert len(task1_history["task-1"]) == 2
        
        # 特定タスクのエラー履歴をリセット
        self.recovery_service.reset_error_history("task-1")
        assert "task-1" not in self.recovery_service.error_history
        assert "task-2" in self.recovery_service.error_history
        
        # 全エラー履歴をリセット
        self.recovery_service.reset_error_history()
        assert len(self.recovery_service.error_history) == 0


class TestHelperFunctions:
    """ヘルパー関数のテスト"""
    
    @patch("utils.error_recovery.error_recovery_service.handle_error")
    def test_handle_task_error(self, mock_handle_error):
        """handle_task_error関数のテスト"""
        # モックの設定
        mock_handle_error.return_value = (True, {"status": "recovered"})
        
        # 関数を実行
        success, result = handle_task_error(
            task_id="task-123",
            error=ValueError("テストエラー"),
            context={"test": True},
            notify_agents=["PM"]
        )
        
        # 結果の検証
        assert success is True
        assert result["status"] == "recovered"
        
        # サービスのhandle_errorが呼び出されることを確認
        mock_handle_error.assert_called_once_with(
            "task-123", ValueError("テストエラー"), {"test": True}, ["PM"]
        )
    
    @patch("utils.error_recovery.error_recovery_service.register_alternative_strategy")
    def test_register_alternative_strategy(self, mock_register):
        """register_alternative_strategy関数のテスト"""
        # モック戦略関数
        mock_strategy = lambda task_id, context: {"status": "success"}
        
        # 文字列指定での登録
        register_alternative_strategy("test_task", "api", mock_strategy)
        
        # サービスの関数が呼び出されることを確認
        mock_register.assert_called_once()
        args, kwargs = mock_register.call_args
        assert args[0] == "test_task"
        assert args[1] == ErrorCategory.API
        assert args[2] == mock_strategy
        
        # 列挙型指定での登録
        mock_register.reset_mock()
        register_alternative_strategy("test_task", ErrorCategory.NETWORK, mock_strategy)
        
        # サービスの関数が呼び出されることを確認
        mock_register.assert_called_once_with("test_task", ErrorCategory.NETWORK, mock_strategy)
    
    @patch("utils.error_recovery.error_recovery_service.get_error_history")
    def test_get_task_error_history(self, mock_get_history):
        """get_task_error_history関数のテスト"""
        # モックの設定
        mock_get_history.return_value = {"task-123": [{"error": "test error"}]}
        
        # 関数を実行
        result = get_task_error_history("task-123")
        
        # 結果の検証
        assert result == {"task-123": [{"error": "test error"}]}
        
        # サービスの関数が呼び出されることを確認
        mock_get_history.assert_called_once_with("task-123")
    
    @patch("utils.error_recovery.error_recovery_service.reset_error_history")
    def test_reset_task_error_history(self, mock_reset):
        """reset_task_error_history関数のテスト"""
        # 関数を実行
        reset_task_error_history("task-123")
        
        # サービスの関数が呼び出されることを確認
        mock_reset.assert_called_once_with("task-123")
        
        # 引数なしでの実行
        mock_reset.reset_mock()
        reset_task_error_history()
        
        # サービスの関数が呼び出されることを確認
        mock_reset.assert_called_once_with(None) 