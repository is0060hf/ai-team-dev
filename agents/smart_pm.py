"""
強化されたPMエージェントモジュール。
動的スケーリング判断のためのインテリジェントなロジックを実装します。
"""

import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum

from utils.logger import get_structured_logger
from utils.load_detection import get_current_load, predict_future_load, LoadMetricType
from utils.load_detection import TaskPriority, LoadTrend
from utils.agent_scaling import get_pool_manager, manual_scale_pool, get_scaling_events
from utils.agent_scaling import ScalingDirection, ScalingTrigger

logger = get_structured_logger("smart_pm")

class ScalingDecision(Enum):
    """スケーリング決定を定義する列挙型"""
    NO_ACTION = "no_action"        # スケーリングなし
    SCALE_UP = "scale_up"          # スケールアップ
    SCALE_DOWN = "scale_down"      # スケールダウン
    PREVENTIVE_SCALE_UP = "preventive_scale_up"    # 予防的スケールアップ
    GRADUAL_SCALE_DOWN = "gradual_scale_down"      # 段階的スケールダウン

class ScalingReason(Enum):
    """スケーリング理由を定義する列挙型"""
    HIGH_LOAD = "high_load"          # 高負荷
    LOW_LOAD = "low_load"            # 低負荷
    INCREASING_TREND = "increasing_trend"  # 増加傾向
    DECREASING_TREND = "decreasing_trend"  # 減少傾向
    LOAD_SPIKE = "load_spike"        # 負荷急増
    PREDICTION = "prediction"        # 予測に基づく
    TASK_PRIORITY = "task_priority"  # タスク優先度
    RESOURCE_OPTIMIZATION = "resource_optimization"  # リソース最適化

class SmartPMScalingController:
    """
    PMエージェントによる高度なスケーリング判断ロジックを実装するクラス。
    自動スケーリングとヒューリスティックな判断を組み合わせて、より効果的なスケーリングを実現します。
    """
    
    def __init__(
        self,
        scaling_enabled: bool = True,
        check_interval: int = 30,
        decision_window: int = 5,
        prediction_window: int = 15
    ):
        """
        Args:
            scaling_enabled: スケーリングを有効にするフラグ
            check_interval: スケーリングチェック間隔（秒）
            decision_window: スケーリング判断に使用する直近の時間ウィンドウ（分）
            prediction_window: 予測に使用する将来の時間ウィンドウ（分）
        """
        self.scaling_enabled = scaling_enabled
        self.check_interval = check_interval
        self.decision_window = decision_window
        self.prediction_window = prediction_window
        
        # スケーリング決定の履歴
        self.decision_history: List[Dict[str, Any]] = []
        self.max_history = 100
        
        # タスク優先度の記録
        self.task_priorities: Dict[str, Dict[str, Any]] = {}
        
        # モニタリング用スレッド
        self.monitor_thread = None
        self.running = False
        self.lock = threading.RLock()
    
    def start_monitoring(self):
        """スケーリングモニタリングを開始"""
        if not self.scaling_enabled:
            logger.info("スケーリングは無効になっています")
            return
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("スケーリングモニタリングは既に実行中です")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"スケーリングモニタリングを開始しました（間隔: {self.check_interval}秒）")
    
    def stop_monitoring(self):
        """スケーリングモニタリングを停止"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            self.monitor_thread = None
            logger.info("スケーリングモニタリングを停止しました")
    
    def _monitoring_loop(self):
        """定期的にスケーリング判断を実行するループ"""
        while self.running:
            try:
                # 全プールのチェック
                pool_manager = get_pool_manager()
                pools = pool_manager.list_pools()
                
                for pool_name in pools:
                    decision = self.evaluate_scaling_decision(pool_name)
                    if decision and decision[0] != ScalingDecision.NO_ACTION:
                        # スケーリングアクションを実行
                        self._execute_scaling_action(pool_name, decision)
                
                # 次のチェックまで待機
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"スケーリングモニタリングでエラーが発生: {str(e)}")
                time.sleep(self.check_interval)
    
    def evaluate_scaling_decision(self, pool_name: str) -> Optional[Tuple[ScalingDecision, ScalingReason, int]]:
        """
        プールに対するスケーリング判断を評価
        
        Args:
            pool_name: プール名
            
        Returns:
            Optional[Tuple[ScalingDecision, ScalingReason, int]]: 決定、理由、推奨インスタンス数のタプル、またはNone
        """
        with self.lock:
            try:
                # プール情報の取得
                pool_manager = get_pool_manager()
                pool_status = pool_manager.get_pools_status().get(pool_name)
                if not pool_status:
                    logger.warning(f"プール {pool_name} の情報を取得できません")
                    return None
                
                # プールのスケーリングポリシー情報
                scaling_policy = pool_status.get('scaling_policy')
                if not scaling_policy or not scaling_policy.get('can_scale_now', False):
                    # スケーリングできない場合は何もしない
                    return None
                
                # 現在のワーカー数
                current_count = pool_status.get('worker_count', 0)
                min_instances = scaling_policy.get('min_instances', 1)
                max_instances = scaling_policy.get('max_instances', 5)
                
                # 負荷メトリクスの取得
                current_load = get_current_load()
                if not current_load:
                    logger.warning("現在の負荷情報を取得できません")
                    return None
                
                # 結合負荷とトレンド
                combined_load = current_load['metrics']['combined_load']
                load_trend = current_load.get('load_trend', 'stable')
                load_level = current_load.get('load_level', 'medium')
                
                # 負荷予測
                future_load = predict_future_load(minutes_ahead=self.prediction_window)
                predicted_combined_load = None
                prediction_confidence = 0.5
                
                if future_load and 'predictions' in future_load:
                    predictions = future_load['predictions']
                    if 'combined_load' in predictions:
                        predicted_combined_load = predictions['combined_load']['value']
                        prediction_confidence = predictions['combined_load']['confidence']
                
                # タスクキュー情報
                queue_length = pool_status.get('queue_size', 0)
                utilization = pool_status.get('utilization', 0)
                
                # スケーリング判断の基本メトリクス
                metrics = {
                    'combined_load': combined_load,
                    'load_trend': load_trend,
                    'load_level': load_level,
                    'predicted_load': predicted_combined_load,
                    'prediction_confidence': prediction_confidence,
                    'queue_length': queue_length,
                    'utilization': utilization,
                    'current_count': current_count,
                    'min_instances': min_instances,
                    'max_instances': max_instances
                }
                
                # スケーリング判断
                if predicted_combined_load is not None and prediction_confidence > 0.7:
                    # 予測に基づく判断（高い信頼度）
                    if predicted_combined_load > 0.8 and current_count < max_instances:
                        # 将来の高負荷予測に基づく予防的スケールアップ
                        target_count = min(current_count + 1, max_instances)
                        return (ScalingDecision.PREVENTIVE_SCALE_UP, ScalingReason.PREDICTION, target_count)
                
                if load_trend == 'increasing' and combined_load > 0.6:
                    # 増加傾向での予防的スケールアップ
                    if current_count < max_instances:
                        target_count = min(current_count + 1, max_instances)
                        return (ScalingDecision.PREVENTIVE_SCALE_UP, ScalingReason.INCREASING_TREND, target_count)
                
                if load_trend == 'spiking':
                    # 急激な負荷変動への対応
                    if combined_load > 0.7 and current_count < max_instances:
                        # 負荷スパイクに対する即時スケールアップ
                        target_count = min(current_count + 2, max_instances)  # 2つ増やす
                        return (ScalingDecision.SCALE_UP, ScalingReason.LOAD_SPIKE, target_count)
                
                # 基本的な負荷レベルに基づく判断
                if combined_load > 0.8 and current_count < max_instances:
                    # 高負荷でのスケールアップ
                    target_count = min(current_count + 1, max_instances)
                    return (ScalingDecision.SCALE_UP, ScalingReason.HIGH_LOAD, target_count)
                
                if combined_load < 0.2 and current_count > min_instances:
                    # 低負荷での段階的スケールダウン
                    if load_trend == 'decreasing' or load_trend == 'stable':
                        target_count = max(current_count - 1, min_instances)
                        return (ScalingDecision.GRADUAL_SCALE_DOWN, ScalingReason.LOW_LOAD, target_count)
                
                # 待機中のタスクがない場合のリソース最適化
                if queue_length == 0 and utilization < 0.5 and current_count > min_instances:
                    # 最適化のためのスケールダウン
                    target_count = max(current_count - 1, min_instances)
                    return (ScalingDecision.SCALE_DOWN, ScalingReason.RESOURCE_OPTIMIZATION, target_count)
                
                # 変更なし
                return (ScalingDecision.NO_ACTION, ScalingReason.HIGH_LOAD, current_count)
                
            except Exception as e:
                logger.error(f"スケーリング判断中にエラーが発生: {str(e)}")
                return None
    
    def _execute_scaling_action(self, pool_name: str, decision: Tuple[ScalingDecision, ScalingReason, int]):
        """
        スケーリングアクションを実行
        
        Args:
            pool_name: プール名
            decision: (スケーリング決定, 理由, 目標インスタンス数)のタプル
        """
        scaling_decision, scaling_reason, target_count = decision
        
        # NO_ACTIONの場合は何もしない
        if scaling_decision == ScalingDecision.NO_ACTION:
            return
        
        # 理由に基づいたメッセージを生成
        reason_messages = {
            ScalingReason.HIGH_LOAD: "高負荷に対応するために",
            ScalingReason.LOW_LOAD: "低負荷状態のリソース最適化のために",
            ScalingReason.INCREASING_TREND: "負荷増加傾向に対応するために",
            ScalingReason.DECREASING_TREND: "負荷減少傾向に合わせて",
            ScalingReason.LOAD_SPIKE: "急激な負荷増加に対応するために",
            ScalingReason.PREDICTION: "将来の負荷予測に基づいて",
            ScalingReason.TASK_PRIORITY: "優先度の高いタスク処理のために",
            ScalingReason.RESOURCE_OPTIMIZATION: "リソース使用効率の最適化のために"
        }
        
        reason_text = reason_messages.get(scaling_reason, "自動スケーリング判断に基づいて")
        
        # スケーリング実行
        try:
            # プール情報の取得
            pool_manager = get_pool_manager()
            pool_status = pool_manager.get_pools_status().get(pool_name)
            current_count = pool_status.get('worker_count', 0) if pool_status else 0
            
            if target_count == current_count:
                logger.info(f"プール {pool_name} のワーカー数は既に目標値 ({target_count}) と同じです")
                return
            
            # マニュアルスケーリング実行
            # メッセージに決定ロジック情報を追加
            message = f"PM判断: {reason_text} {scaling_decision.value} ({current_count}→{target_count})"
            success = manual_scale_pool(pool_name, target_count, message)
            
            if success:
                logger.info(f"プール {pool_name} を {current_count} から {target_count} に自動スケーリングしました: {scaling_decision.value}, {scaling_reason.value}")
                
                # 決定履歴に追加
                with self.lock:
                    self.decision_history.append({
                        "pool_name": pool_name,
                        "timestamp": time.time(),
                        "decision": scaling_decision.value,
                        "reason": scaling_reason.value,
                        "prev_count": current_count,
                        "target_count": target_count,
                        "success": True
                    })
                    
                    # 履歴サイズの制限
                    if len(self.decision_history) > self.max_history:
                        self.decision_history = self.decision_history[-self.max_history:]
            else:
                logger.error(f"プール {pool_name} の自動スケーリングに失敗: {scaling_decision.value}, {scaling_reason.value}")
                
                # 失敗も履歴に記録
                with self.lock:
                    self.decision_history.append({
                        "pool_name": pool_name,
                        "timestamp": time.time(),
                        "decision": scaling_decision.value,
                        "reason": scaling_reason.value,
                        "prev_count": current_count,
                        "target_count": target_count,
                        "success": False
                    })
        except Exception as e:
            logger.error(f"スケーリングアクション実行中にエラーが発生: {str(e)}")
    
    def register_task_priority(self, task_id: str, task_type: str, priority: TaskPriority, estimated_duration: float = 0.0):
        """
        タスク優先度を登録（スケーリング判断に使用）
        
        Args:
            task_id: タスクID
            task_type: タスクタイプ
            priority: 優先度
            estimated_duration: 推定実行時間（秒）
        """
        with self.lock:
            self.task_priorities[task_id] = {
                "type": task_type,
                "priority": priority,
                "estimated_duration": estimated_duration,
                "registered_at": time.time()
            }
    
    def get_decision_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        スケーリング判断履歴を取得
        
        Args:
            limit: 取得する最大履歴数
            
        Returns:
            List[Dict[str, Any]]: スケーリング判断履歴
        """
        with self.lock:
            return list(reversed(self.decision_history))[-limit:]

# グローバルなコントローラーインスタンス
_pm_scaling_controller = None

def get_pm_scaling_controller() -> SmartPMScalingController:
    """
    PMスケーリングコントローラーのグローバルインスタンスを取得
    
    Returns:
        SmartPMScalingController: コントローラーのインスタンス
    """
    global _pm_scaling_controller
    if _pm_scaling_controller is None:
        _pm_scaling_controller = SmartPMScalingController()
    return _pm_scaling_controller

def start_pm_scaling_monitoring():
    """PMによるスケーリングモニタリングを開始"""
    controller = get_pm_scaling_controller()
    controller.start_monitoring()

def stop_pm_scaling_monitoring():
    """PMによるスケーリングモニタリングを停止"""
    controller = get_pm_scaling_controller()
    controller.stop_monitoring()

def register_task_with_priority(task_id: str, task_type: str, priority: Union[TaskPriority, str, int], estimated_duration: float = 0.0):
    """
    タスク優先度を登録するヘルパー関数
    
    Args:
        task_id: タスクID
        task_type: タスクタイプ
        priority: 優先度（TaskPriority列挙型、文字列、または数値1-4）
        estimated_duration: 推定実行時間（秒）
    """
    # 優先度の正規化
    if isinstance(priority, str):
        try:
            priority = TaskPriority[priority.upper()]
        except KeyError:
            # デフォルト
            priority = TaskPriority.MEDIUM
    elif isinstance(priority, int):
        if 1 <= priority <= 4:
            priority_map = {
                1: TaskPriority.LOW,
                2: TaskPriority.MEDIUM,
                3: TaskPriority.HIGH,
                4: TaskPriority.CRITICAL
            }
            priority = priority_map[priority]
        else:
            # デフォルト
            priority = TaskPriority.MEDIUM
    
    # コントローラーに登録
    controller = get_pm_scaling_controller()
    controller.register_task_priority(task_id, task_type, priority, estimated_duration) 