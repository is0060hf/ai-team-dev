"""
エラー処理と回復力強化のためのユーティリティモジュール。
タスク失敗時のリトライ、代替手段検討、エラー報告などの機能を提供します。
"""

import time
import random
import math
import json
import traceback
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
import logging

from utils.logger import get_agent_logger
from utils.agent_communication import (
    MessageDispatcher, send_message_to_agent,
    create_task_request, create_error_notification
)

logger = get_agent_logger("error_recovery")


class ErrorSeverity(Enum):
    """エラーの重大度を定義する列挙型"""
    LOW = "low"          # 軽微なエラー、自動的に回復可能
    MEDIUM = "medium"    # 中程度のエラー、再試行または代替手段で回復可能
    HIGH = "high"        # 重大なエラー、人間の介入が必要
    CRITICAL = "critical"  # 致命的なエラー、即時停止・報告が必要


class ErrorCategory(Enum):
    """エラーのカテゴリを定義する列挙型"""
    NETWORK = "network"      # ネットワーク関連エラー
    API = "api"              # API関連エラー
    PERMISSION = "permission"  # 権限関連エラー
    RESOURCE = "resource"    # リソース関連エラー
    LOGIC = "logic"          # ロジック関連エラー
    DATA = "data"            # データ関連エラー
    TIMEOUT = "timeout"      # タイムアウト関連エラー
    UNKNOWN = "unknown"      # 不明なエラー


class RecoveryStrategy(Enum):
    """回復戦略を定義する列挙型"""
    RETRY = "retry"                  # 単純な再試行
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数バックオフを用いた再試行
    ALTERNATIVE_METHOD = "alternative_method"    # 代替手段の試行
    HUMAN_INTERVENTION = "human_intervention"    # 人間の介入を要求
    GRACEFUL_DEGRADATION = "graceful_degradation"  # 機能の劣化を許容して継続
    CIRCUIT_BREAKER = "circuit_breaker"         # サーキットブレーカーパターン


class ErrorInfo:
    """エラー情報を保持するクラス"""
    
    def __init__(
        self,
        task_id: str,
        error: Exception,
        severity: ErrorSeverity,
        category: ErrorCategory,
        context: Dict[str, Any] = None,
        timestamp: datetime = None,
        stack_trace: str = None
    ):
        """
        Args:
            task_id: エラーが発生したタスクのID
            error: 発生した例外オブジェクト
            severity: エラーの重大度
            category: エラーのカテゴリ
            context: エラー発生時のコンテキスト情報
            timestamp: エラー発生時刻
            stack_trace: スタックトレース
        """
        self.task_id = task_id
        self.error = error
        self.error_message = str(error)
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.timestamp = timestamp or datetime.now()
        self.stack_trace = stack_trace or traceback.format_exc()
        self.recovery_attempts = []
        
    def to_dict(self) -> Dict[str, Any]:
        """エラー情報を辞書形式で取得"""
        return {
            "task_id": self.task_id,
            "error_type": self.error.__class__.__name__,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
            "recovery_attempts": self.recovery_attempts
        }
    
    def add_recovery_attempt(self, strategy: RecoveryStrategy, result: bool, details: Dict[str, Any] = None):
        """回復試行を記録"""
        self.recovery_attempts.append({
            "strategy": strategy.value,
            "timestamp": datetime.now().isoformat(),
            "result": result,
            "details": details or {}
        })


class TaskRetryManager:
    """タスク再試行を管理するクラス"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        """
        Args:
            max_retries: 最大再試行回数
            base_delay: 基本遅延時間（秒）
            max_delay: 最大遅延時間（秒）
            jitter: ランダムな揺らぎを加えるかどうか
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retry_counts = {}  # タスクIDごとの再試行回数
        
    def should_retry(self, task_id: str, error_info: ErrorInfo) -> bool:
        """再試行すべきかどうかを判断"""
        # 再試行回数を取得（初回の場合は0）
        retry_count = self.retry_counts.get(task_id, 0)
        
        # 最大再試行回数を超えている場合はFalse
        if retry_count >= self.max_retries:
            logger.info(f"タスク {task_id} の最大再試行回数 ({self.max_retries}) に達しました")
            return False
        
        # 重大度に応じた判断
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.warning(f"タスク {task_id} で致命的なエラーが発生しました。再試行しません")
            return False
        
        # エラーカテゴリに応じた判断
        if error_info.category == ErrorCategory.PERMISSION:
            logger.warning(f"タスク {task_id} で権限エラーが発生しました。再試行しても解決しない可能性が高いです")
            return False
        
        # その他の場合は再試行可能
        return True
    
    def get_retry_delay(self, task_id: str) -> float:
        """再試行の遅延時間を計算"""
        retry_count = self.retry_counts.get(task_id, 0)
        
        # 指数バックオフによる遅延計算
        delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
        
        # ランダムな揺らぎを加える（ジッター）
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def increment_retry_count(self, task_id: str):
        """再試行回数をインクリメント"""
        self.retry_counts[task_id] = self.retry_counts.get(task_id, 0) + 1
    
    def reset_retry_count(self, task_id: str):
        """再試行回数をリセット"""
        if task_id in self.retry_counts:
            del self.retry_counts[task_id]
    
    def get_retry_count(self, task_id: str) -> int:
        """現在の再試行回数を取得"""
        return self.retry_counts.get(task_id, 0)


class ErrorRecoveryService:
    """エラー回復サービスクラス"""
    
    def __init__(self, retry_manager: TaskRetryManager = None):
        """
        Args:
            retry_manager: タスク再試行マネージャー
        """
        self.retry_manager = retry_manager or TaskRetryManager()
        self.error_history = {}  # タスクIDごとのエラー履歴
        self.alternative_strategies = {}  # タスク種別ごとの代替戦略
        self.dispatcher = MessageDispatcher()
        
    def register_alternative_strategy(
        self, 
        task_type: str, 
        error_category: ErrorCategory,
        strategy_func: Callable[[str, Dict[str, Any]], Any]
    ):
        """特定のタスク種別とエラーカテゴリに対する代替戦略を登録"""
        key = (task_type, error_category.value)
        self.alternative_strategies[key] = strategy_func
    
    def handle_error(
        self,
        task_id: str,
        error: Exception,
        context: Dict[str, Any],
        notify_agents: List[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        エラーを処理し、適切な回復戦略を適用
        
        Args:
            task_id: タスクID
            error: 発生した例外
            context: エラー発生時のコンテキスト
            notify_agents: エラーを通知するエージェントのリスト
            
        Returns:
            Tuple[bool, Optional[Dict]]: (回復成功したか, 回復結果)
        """
        # エラー情報を作成
        error_info = self._analyze_error(task_id, error, context)
        
        # エラー履歴に追加
        self.error_history.setdefault(task_id, []).append(error_info)
        
        # エラーをログに記録
        logger.error(
            f"タスク {task_id} でエラーが発生しました: {error_info.error_message} "
            f"(重大度: {error_info.severity.value}, カテゴリ: {error_info.category.value})"
        )
        
        # 指定されたエージェントにエラーを通知
        if notify_agents:
            self._notify_agents(error_info, notify_agents)
        
        # 回復戦略の決定と実行
        recovery_result = self._apply_recovery_strategy(error_info)
        
        return recovery_result
    
    def _analyze_error(self, task_id: str, error: Exception, context: Dict[str, Any]) -> ErrorInfo:
        """エラーを分析し、情報を抽出"""
        # エラータイプに基づいて重大度とカテゴリを判断
        severity = ErrorSeverity.MEDIUM  # デフォルト
        category = ErrorCategory.UNKNOWN  # デフォルト
        
        # 各種エラータイプの判別
        if isinstance(error, (ConnectionError, TimeoutError)):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.MEDIUM
        elif "api" in str(error).lower() or "rate limit" in str(error).lower():
            category = ErrorCategory.API
            severity = ErrorSeverity.MEDIUM
        elif "permission" in str(error).lower() or "access" in str(error).lower():
            category = ErrorCategory.PERMISSION
            severity = ErrorSeverity.HIGH
        elif "resource" in str(error).lower() or "memory" in str(error).lower():
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH
        elif "timeout" in str(error).lower():
            category = ErrorCategory.TIMEOUT
            severity = ErrorSeverity.MEDIUM
        elif "data" in str(error).lower() or "parsing" in str(error).lower():
            category = ErrorCategory.DATA
            severity = ErrorSeverity.MEDIUM
        
        # コンテキスト情報から追加の判断
        if context.get("critical", False):
            severity = ErrorSeverity.CRITICAL
        
        return ErrorInfo(task_id, error, severity, category, context)
    
    def _apply_recovery_strategy(self, error_info: ErrorInfo) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """適切な回復戦略を適用"""
        # タスク情報を取得
        task_id = error_info.task_id
        task_type = error_info.context.get("task_type", "unknown")
        
        # 重大度に基づく戦略選択
        if error_info.severity == ErrorSeverity.CRITICAL:
            # 致命的なエラーは人間の介入を要求
            strategy = RecoveryStrategy.HUMAN_INTERVENTION
            error_info.add_recovery_attempt(strategy, False, {"message": "人間の介入が必要です"})
            return False, {"strategy": strategy.value, "message": "人間の介入が必要です"}
        
        # 再試行可能か判断
        if self.retry_manager.should_retry(task_id, error_info):
            # 再試行戦略を適用
            strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
            delay = self.retry_manager.get_retry_delay(task_id)
            
            logger.info(f"タスク {task_id} を {delay:.2f} 秒後に再試行します（{self.retry_manager.get_retry_count(task_id) + 1}/{self.retry_manager.max_retries}回目）")
            
            # 遅延を適用
            time.sleep(delay)
            
            # 再試行カウントを増加
            self.retry_manager.increment_retry_count(task_id)
            
            # 再試行結果（この時点では結果不明なのでFalseを返す）
            error_info.add_recovery_attempt(strategy, False, {"delay": delay})
            return False, {"strategy": strategy.value, "retry_count": self.retry_manager.get_retry_count(task_id)}
        
        # 代替戦略があるか確認
        alternative_key = (task_type, error_info.category.value)
        if alternative_key in self.alternative_strategies:
            strategy = RecoveryStrategy.ALTERNATIVE_METHOD
            alternative_func = self.alternative_strategies[alternative_key]
            
            try:
                # 代替戦略を実行
                logger.info(f"タスク {task_id} に代替戦略を適用します")
                result = alternative_func(task_id, error_info.context)
                
                # 成功した場合
                error_info.add_recovery_attempt(strategy, True, {"alternative_result": str(result)})
                return True, {"strategy": strategy.value, "result": result}
            except Exception as alt_error:
                # 代替戦略も失敗した場合
                logger.error(f"代替戦略の実行に失敗しました: {str(alt_error)}")
                error_info.add_recovery_attempt(strategy, False, {"error": str(alt_error)})
        
        # 機能の劣化を許容して継続
        if error_info.severity != ErrorSeverity.HIGH:
            strategy = RecoveryStrategy.GRACEFUL_DEGRADATION
            logger.info(f"タスク {task_id} は機能を劣化させて継続します")
            error_info.add_recovery_attempt(strategy, True, {"message": "機能を劣化させて継続"})
            return True, {"strategy": strategy.value, "degraded": True}
        
        # 上記以外は人間の介入を要求
        strategy = RecoveryStrategy.HUMAN_INTERVENTION
        logger.warning(f"タスク {task_id} は回復できませんでした。人間の介入が必要です")
        error_info.add_recovery_attempt(strategy, False, {"message": "人間の介入が必要です"})
        return False, {"strategy": strategy.value, "message": "人間の介入が必要です"}
    
    def _notify_agents(self, error_info: ErrorInfo, agents: List[str]):
        """指定されたエージェントにエラーを通知"""
        error_notification = create_error_notification(
            task_id=error_info.task_id,
            error_type=error_info.error.__class__.__name__,
            error_message=error_info.error_message,
            severity=error_info.severity.value,
            context=error_info.context
        )
        
        for agent in agents:
            try:
                send_message_to_agent(agent, error_notification)
                logger.info(f"エージェント {agent} にエラー通知を送信しました")
            except Exception as e:
                logger.error(f"エージェント {agent} へのエラー通知送信に失敗しました: {str(e)}")
    
    def get_error_history(self, task_id: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """エラー履歴を取得"""
        if task_id:
            # 特定のタスクのエラー履歴を取得
            history = self.error_history.get(task_id, [])
            return {task_id: [error.to_dict() for error in history]}
        else:
            # 全タスクのエラー履歴を取得
            return {
                task_id: [error.to_dict() for error in errors]
                for task_id, errors in self.error_history.items()
            }
    
    def reset_error_history(self, task_id: str = None):
        """エラー履歴をリセット"""
        if task_id:
            # 特定のタスクのエラー履歴をリセット
            if task_id in self.error_history:
                del self.error_history[task_id]
                self.retry_manager.reset_retry_count(task_id)
        else:
            # 全タスクのエラー履歴をリセット
            self.error_history = {}
            for task_id in list(self.retry_manager.retry_counts.keys()):
                self.retry_manager.reset_retry_count(task_id)


# グローバルインスタンス（シングルトン）
error_recovery_service = ErrorRecoveryService()


# ヘルパー関数
def handle_task_error(
    task_id: str,
    error: Exception,
    context: Dict[str, Any] = None,
    notify_agents: List[str] = None
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    タスクエラーを処理するヘルパー関数
    
    Args:
        task_id: タスクID
        error: 発生した例外
        context: エラー発生時のコンテキスト
        notify_agents: エラーを通知するエージェントのリスト
        
    Returns:
        Tuple[bool, Optional[Dict]]: (回復成功したか, 回復結果)
    """
    return error_recovery_service.handle_error(task_id, error, context or {}, notify_agents)


def register_alternative_strategy(
    task_type: str,
    error_category: Union[ErrorCategory, str],
    strategy_func: Callable[[str, Dict[str, Any]], Any]
):
    """
    代替戦略を登録するヘルパー関数
    
    Args:
        task_type: タスク種別
        error_category: エラーカテゴリ
        strategy_func: 代替戦略関数
    """
    if isinstance(error_category, str):
        error_category = ErrorCategory(error_category)
    
    error_recovery_service.register_alternative_strategy(task_type, error_category, strategy_func)


def get_task_error_history(task_id: str = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    タスクのエラー履歴を取得するヘルパー関数
    
    Args:
        task_id: タスクID（Noneの場合は全てのタスクの履歴を取得）
        
    Returns:
        Dict[str, List[Dict]]: タスクIDをキーとするエラー履歴
    """
    return error_recovery_service.get_error_history(task_id)


def reset_task_error_history(task_id: str = None):
    """
    タスクのエラー履歴をリセットするヘルパー関数
    
    Args:
        task_id: タスクID（Noneの場合は全てのタスクの履歴をリセット）
    """
    error_recovery_service.reset_error_history(task_id)


# デフォルトの代替戦略
def default_data_processing_alternative(task_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """データ処理タスクの代替戦略（例）"""
    logger.info(f"データ処理タスク {task_id} の代替戦略を実行します")
    # 簡略化されたデータ処理を実行
    return {"status": "simplified_processing_completed"}


def default_api_call_alternative(task_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """API呼び出しタスクの代替戦略（例）"""
    logger.info(f"API呼び出しタスク {task_id} の代替戦略を実行します")
    # キャッシュからデータを取得するなどの代替処理
    return {"status": "used_cached_data"}


# デフォルト代替戦略の登録
register_alternative_strategy("data_processing", ErrorCategory.DATA, default_data_processing_alternative)
register_alternative_strategy("api_call", ErrorCategory.API, default_api_call_alternative)
register_alternative_strategy("api_call", ErrorCategory.NETWORK, default_api_call_alternative) 