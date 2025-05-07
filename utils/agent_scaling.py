"""
動的エージェントスケーリングユーティリティ。
負荷やタスクの複雑さに応じてエージェントを増減できる機能を提供します。
"""

import time
import threading
import asyncio
import json
from typing import Dict, List, Callable, Any, Optional, Type, Tuple
import concurrent.futures
from enum import Enum
from datetime import datetime
from pathlib import Path
import os

from utils.logger import get_logger
from utils.config import config
from utils.tracing import trace, add_trace_event

logger = get_logger("agent_scaling")

class ScalingDirection(Enum):
    """スケーリング方向を定義する列挙型"""
    UP = "up"
    DOWN = "down"
    NONE = "none"

class ScalingTrigger(Enum):
    """スケーリングをトリガーする条件"""
    QUEUE_LENGTH = "queue_length"  # タスクキューの長さ
    RESPONSE_TIME = "response_time"  # エージェントの応答時間
    CPU_USAGE = "cpu_usage"  # CPUリソース使用率
    MEMORY_USAGE = "memory_usage"  # メモリリソース使用率
    TASK_COMPLEXITY = "task_complexity"  # タスクの複雑さ
    COMBINED_LOAD = "combined_load"  # 複合負荷指標
    MANUAL = "manual"  # 手動操作によるスケーリング

class ScalingEvent:
    """スケーリングイベント情報を記録するクラス"""
    
    def __init__(
        self, 
        pool_name: str,
        direction: ScalingDirection,
        trigger: ScalingTrigger,
        prev_count: int,
        new_count: int,
        metrics: Dict[str, float],
        timestamp: Optional[float] = None,
        success: bool = True,
        reason: Optional[str] = None
    ):
        """
        Args:
            pool_name: エージェントプール名
            direction: スケーリング方向（UP/DOWN）
            trigger: スケーリングのトリガー条件
            prev_count: スケーリング前のインスタンス数
            new_count: スケーリング後のインスタンス数
            metrics: スケーリング時のメトリクス値
            timestamp: イベントのタイムスタンプ
            success: スケーリングが成功したかどうか
            reason: スケーリングの詳細な理由
        """
        self.pool_name = pool_name
        self.direction = direction
        self.trigger = trigger
        self.prev_count = prev_count
        self.new_count = new_count
        self.metrics = metrics
        self.timestamp = timestamp or time.time()
        self.success = success
        self.reason = reason or f"{trigger.value}に基づく自動スケーリング"
        self.id = f"{pool_name}-{int(self.timestamp)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """イベントを辞書形式に変換"""
        return {
            "id": self.id,
            "pool_name": self.pool_name,
            "direction": self.direction.value,
            "trigger": self.trigger.value,
            "prev_count": self.prev_count,
            "new_count": self.new_count,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "success": self.success,
            "reason": self.reason,
            "timestamp_str": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        }

class ScalingHistory:
    """スケーリングイベントの履歴を管理するクラス"""
    
    def __init__(self, max_history: int = 1000, storage_path: Optional[str] = None):
        """
        Args:
            max_history: 保持する最大履歴数
            storage_path: 履歴保存先のファイルパス
        """
        self.events: List[ScalingEvent] = []
        self.max_history = max_history
        self.lock = threading.RLock()
        
        # 保存先パスの設定
        if storage_path is None:
            storage_dir = Path("storage/scaling_history")
            storage_dir.mkdir(parents=True, exist_ok=True)
            self.storage_path = str(storage_dir / "scaling_events.json")
        else:
            self.storage_path = storage_path
        
        # 既存データの読み込み
        self._load_history()
    
    def add_event(self, event: ScalingEvent):
        """
        スケーリングイベントを履歴に追加
        
        Args:
            event: 記録するスケーリングイベント
        """
        with self.lock:
            self.events.append(event)
            
            # 最大履歴数を超えたら古いものから削除
            if len(self.events) > self.max_history:
                self.events = self.events[-self.max_history:]
            
            # イベント追加時に保存
            self._save_history()
            
            # トレース情報に追加
            add_trace_event(
                f"scaling_{event.direction.value}",
                {
                    "pool_name": event.pool_name,
                    "trigger": event.trigger.value,
                    "prev_count": event.prev_count,
                    "new_count": event.new_count,
                    "reason": event.reason
                }
            )
            
            logger.info(
                f"スケーリングイベント記録: {event.pool_name} {event.direction.value} "
                f"({event.prev_count}→{event.new_count}, トリガー: {event.trigger.value})"
            )
    
    def get_events(self, 
                  pool_name: Optional[str] = None, 
                  limit: int = 100,
                  start_time: Optional[float] = None,
                  end_time: Optional[float] = None,
                  direction: Optional[ScalingDirection] = None,
                  trigger: Optional[ScalingTrigger] = None) -> List[Dict[str, Any]]:
        """
        条件に一致するスケーリングイベントを取得
        
        Args:
            pool_name: エージェントプール名フィルタ
            limit: 取得する最大イベント数
            start_time: 取得開始時間（秒単位のエポック時間）
            end_time: 取得終了時間（秒単位のエポック時間）
            direction: スケーリング方向フィルタ
            trigger: トリガー条件フィルタ
            
        Returns:
            List[Dict[str, Any]]: イベント辞書のリスト
        """
        with self.lock:
            filtered_events = []
            
            for event in reversed(self.events):  # 新しいものから順に処理
                if pool_name and event.pool_name != pool_name:
                    continue
                
                if start_time and event.timestamp < start_time:
                    continue
                
                if end_time and event.timestamp > end_time:
                    continue
                
                if direction and event.direction != direction:
                    continue
                
                if trigger and event.trigger != trigger:
                    continue
                
                filtered_events.append(event.to_dict())
                
                if len(filtered_events) >= limit:
                    break
            
            return filtered_events
    
    def get_summary(self, 
                   pool_name: Optional[str] = None,
                   period_hours: int = 24) -> Dict[str, Any]:
        """
        スケーリングイベントのサマリー統計を取得
        
        Args:
            pool_name: エージェントプール名フィルタ
            period_hours: 集計期間（時間）
            
        Returns:
            Dict[str, Any]: サマリー統計
        """
        with self.lock:
            # 集計期間の開始時間
            period_start = time.time() - (period_hours * 3600)
            
            # 対象イベントのフィルタリング
            target_events = [
                e for e in self.events
                if (not pool_name or e.pool_name == pool_name) and
                   e.timestamp >= period_start
            ]
            
            # 基本統計の初期化
            summary = {
                "total_events": len(target_events),
                "scale_up_count": 0,
                "scale_down_count": 0,
                "by_trigger": {},
                "by_pool": {},
                "period_hours": period_hours,
                "timestamp": time.time()
            }
            
            # イベントを分類して集計
            for event in target_events:
                # 方向別カウント
                if event.direction == ScalingDirection.UP:
                    summary["scale_up_count"] += 1
                elif event.direction == ScalingDirection.DOWN:
                    summary["scale_down_count"] += 1
                
                # トリガー別カウント
                trigger = event.trigger.value
                if trigger not in summary["by_trigger"]:
                    summary["by_trigger"][trigger] = {
                        "total": 0,
                        "up": 0,
                        "down": 0
                    }
                
                summary["by_trigger"][trigger]["total"] += 1
                if event.direction == ScalingDirection.UP:
                    summary["by_trigger"][trigger]["up"] += 1
                elif event.direction == ScalingDirection.DOWN:
                    summary["by_trigger"][trigger]["down"] += 1
                
                # プール別カウント
                pool = event.pool_name
                if pool not in summary["by_pool"]:
                    summary["by_pool"][pool] = {
                        "total": 0,
                        "up": 0,
                        "down": 0
                    }
                
                summary["by_pool"][pool]["total"] += 1
                if event.direction == ScalingDirection.UP:
                    summary["by_pool"][pool]["up"] += 1
                elif event.direction == ScalingDirection.DOWN:
                    summary["by_pool"][pool]["down"] += 1
            
            return summary
    
    def get_scaling_rate(self, 
                        pool_name: Optional[str] = None,
                        period_hours: int = 24,
                        interval_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        時間間隔ごとのスケーリング回数を取得（時系列分析用）
        
        Args:
            pool_name: エージェントプール名フィルタ
            period_hours: 集計期間（時間）
            interval_minutes: 集計間隔（分）
            
        Returns:
            List[Dict[str, Any]]: 時間間隔ごとのスケーリング回数
        """
        with self.lock:
            # 集計期間の開始時間と集計間隔（秒）
            period_start = time.time() - (period_hours * 3600)
            interval_seconds = interval_minutes * 60
            
            # 対象イベントのフィルタリング
            target_events = [
                e for e in self.events
                if (not pool_name or e.pool_name == pool_name) and
                   e.timestamp >= period_start
            ]
            
            # 時間間隔ごとのバケットを作成
            buckets = {}
            current_time = time.time()
            
            # 最新の時間から過去に遡って集計期間分のバケットを初期化
            for offset in range(0, period_hours * 3600, interval_seconds):
                bucket_end = current_time - offset
                bucket_start = bucket_end - interval_seconds
                
                if bucket_start < period_start:
                    continue
                
                bucket_key = datetime.fromtimestamp(bucket_start).strftime("%Y-%m-%d %H:%M")
                buckets[bucket_key] = {
                    "start_time": bucket_start,
                    "end_time": bucket_end,
                    "up_count": 0,
                    "down_count": 0,
                    "timestamp_str": bucket_key
                }
            
            # イベントをバケットに振り分け
            for event in target_events:
                # イベント時間を含むバケットを特定
                event_time = event.timestamp
                
                for bucket_key, bucket in buckets.items():
                    if bucket["start_time"] <= event_time < bucket["end_time"]:
                        if event.direction == ScalingDirection.UP:
                            bucket["up_count"] += 1
                        elif event.direction == ScalingDirection.DOWN:
                            bucket["down_count"] += 1
                        break
            
            # バケットを時間順にソートして返却
            result = list(buckets.values())
            result.sort(key=lambda x: x["start_time"])
            
            return result
    
    def analyze_triggers(self, 
                        pool_name: Optional[str] = None,
                        period_hours: int = 24) -> Dict[str, Any]:
        """
        スケーリングトリガーの傾向を分析
        
        Args:
            pool_name: エージェントプール名フィルタ
            period_hours: 集計期間（時間）
            
        Returns:
            Dict[str, Any]: トリガー分析結果
        """
        with self.lock:
            # 集計期間の開始時間
            period_start = time.time() - (period_hours * 3600)
            
            # 対象イベントのフィルタリング
            target_events = [
                e for e in self.events
                if (not pool_name or e.pool_name == pool_name) and
                   e.timestamp >= period_start
            ]
            
            # トリガーごとのスケーリング成功率
            trigger_success = {}
            
            # トリガーごとのメトリクス値の分布
            trigger_metrics = {}
            
            # 分析結果の初期化
            for trigger in [t.value for t in ScalingTrigger]:
                trigger_success[trigger] = {
                    "total": 0,
                    "success": 0,
                    "success_rate": 0
                }
                trigger_metrics[trigger] = {}
            
            # イベントを分類して集計
            for event in target_events:
                trigger = event.trigger.value
                
                # 成功率の計算
                trigger_success[trigger]["total"] += 1
                if event.success:
                    trigger_success[trigger]["success"] += 1
                
                # メトリクス値の収集
                for metric_name, metric_value in event.metrics.items():
                    if metric_name not in trigger_metrics[trigger]:
                        trigger_metrics[trigger][metric_name] = []
                    
                    trigger_metrics[trigger][metric_name].append(metric_value)
            
            # 成功率の計算
            for trigger, data in trigger_success.items():
                if data["total"] > 0:
                    data["success_rate"] = data["success"] / data["total"]
            
            # メトリクス値の統計計算
            metrics_stats = {}
            for trigger, metrics in trigger_metrics.items():
                metrics_stats[trigger] = {}
                
                for metric_name, values in metrics.items():
                    if not values:
                        continue
                    
                    metrics_stats[trigger][metric_name] = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "count": len(values)
                    }
            
            return {
                "success_rates": trigger_success,
                "metrics_stats": metrics_stats,
                "period_hours": period_hours,
                "timestamp": time.time()
            }
    
    def _save_history(self):
        """履歴をJSONファイルに保存"""
        try:
            with self.lock:
                # 辞書形式に変換
                data = {
                    "events": [event.to_dict() for event in self.events],
                    "updated_at": time.time()
                }
                
                # JSONに変換して保存
                with open(self.storage_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.debug(f"スケーリング履歴を保存しました: {self.storage_path}")
        except Exception as e:
            logger.error(f"スケーリング履歴の保存に失敗しました: {str(e)}")
    
    def _load_history(self):
        """履歴をJSONファイルから読み込み"""
        try:
            if not os.path.exists(self.storage_path):
                logger.debug(f"スケーリング履歴ファイルが存在しません: {self.storage_path}")
                return
            
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            with self.lock:
                # イベントの復元
                for event_dict in data.get("events", []):
                    # dict形式からEventオブジェクトに変換
                    event = ScalingEvent(
                        pool_name=event_dict["pool_name"],
                        direction=ScalingDirection(event_dict["direction"]),
                        trigger=ScalingTrigger(event_dict["trigger"]),
                        prev_count=event_dict["prev_count"],
                        new_count=event_dict["new_count"],
                        metrics=event_dict["metrics"],
                        timestamp=event_dict["timestamp"],
                        success=event_dict["success"],
                        reason=event_dict["reason"]
                    )
                    
                    # IDを復元
                    if "id" in event_dict:
                        event.id = event_dict["id"]
                    
                    self.events.append(event)
                
                # 最大履歴数を超えたら古いものから削除
                if len(self.events) > self.max_history:
                    self.events = self.events[-self.max_history:]
                
                logger.info(f"スケーリング履歴を読み込みました: {len(self.events)}件")
        except Exception as e:
            logger.error(f"スケーリング履歴の読み込みに失敗しました: {str(e)}")

# グローバルなスケーリング履歴インスタンス
_scaling_history = None

def get_scaling_history() -> ScalingHistory:
    """スケーリング履歴のグローバルインスタンスを取得"""
    global _scaling_history
    if _scaling_history is None:
        _scaling_history = ScalingHistory()
    return _scaling_history

class ScalingPolicy:
    """エージェントスケーリングのポリシーを定義するクラス"""
    
    def __init__(
        self, 
        trigger: ScalingTrigger,
        min_instances: int = 1,
        max_instances: int = 5,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2,
        cooldown_period: int = 60,  # スケーリング操作後のクールダウン期間（秒）
        scaling_step: int = 1  # 一度にスケールする数
    ):
        self.trigger = trigger
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.cooldown_period = cooldown_period
        self.scaling_step = scaling_step
        self.last_scaling_time = 0
        
    def can_scale(self) -> bool:
        """クールダウン期間を考慮してスケーリング可能かどうかを判断"""
        current_time = time.time()
        return (current_time - self.last_scaling_time) > self.cooldown_period
    
    def update_last_scaling_time(self):
        """スケーリング操作後に最終スケーリング時間を更新"""
        self.last_scaling_time = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """ポリシーを辞書形式に変換"""
        return {
            "trigger": self.trigger.value,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances,
            "scale_up_threshold": self.scale_up_threshold,
            "scale_down_threshold": self.scale_down_threshold,
            "cooldown_period": self.cooldown_period,
            "scaling_step": self.scaling_step,
            "last_scaling_time": self.last_scaling_time,
            "can_scale_now": self.can_scale()
        }

class AgentWorker:
    """エージェントプールで使用される個々のワーカー"""
    
    def __init__(self, agent_instance: Any, worker_id: str):
        self.agent_instance = agent_instance
        self.worker_id = worker_id
        self.busy = False
        self.last_task_start_time = 0
        self.last_task_end_time = 0
        self.task_count = 0
        self.current_task = None
        
    def assign_task(self, task: Any):
        """タスクをワーカーに割り当て"""
        self.busy = True
        self.last_task_start_time = time.time()
        self.current_task = task
        
    def complete_task(self):
        """タスク完了時の処理"""
        self.busy = False
        self.last_task_end_time = time.time()
        self.task_count += 1
        self.current_task = None
        
    def get_response_time(self) -> float:
        """最後のタスクの応答時間を取得"""
        if self.last_task_start_time == 0 or self.last_task_end_time == 0:
            return 0
        return self.last_task_end_time - self.last_task_start_time
    
    def get_metrics(self) -> Dict[str, Any]:
        """ワーカーのメトリクスを取得"""
        return {
            "worker_id": self.worker_id,
            "busy": self.busy,
            "task_count": self.task_count,
            "last_response_time": self.get_response_time(),
            "current_task": self.current_task
        }

class AgentPool:
    """複数のエージェントインスタンスを管理するプール"""
    
    def __init__(
        self,
        agent_class: Type,
        agent_kwargs: Dict[str, Any],
        scaling_policy: ScalingPolicy,
        pool_name: str = "default"
    ):
        self.agent_class = agent_class
        self.agent_kwargs = agent_kwargs
        self.scaling_policy = scaling_policy
        self.pool_name = pool_name
        self.workers: Dict[str, AgentWorker] = {}
        self.task_queue = asyncio.Queue()
        self.lock = threading.RLock()
        self.monitor_thread = None
        self.running = False
        
        # 初期エージェントを作成
        for i in range(scaling_policy.min_instances):
            self._create_worker()
    
    def _create_worker(self) -> str:
        """新しいワーカーを作成して追加"""
        with self.lock:
            worker_id = f"{self.pool_name}-worker-{len(self.workers)}"
            agent_instance = self.agent_class(**self.agent_kwargs)
            worker = AgentWorker(agent_instance, worker_id)
            self.workers[worker_id] = worker
            logger.info(f"Worker {worker_id} created in pool {self.pool_name}")
            return worker_id
    
    def _remove_worker(self, worker_id: str):
        """ワーカーを削除"""
        with self.lock:
            if worker_id in self.workers and not self.workers[worker_id].busy:
                del self.workers[worker_id]
                logger.info(f"Worker {worker_id} removed from pool {self.pool_name}")
                return True
            return False
    
    async def start(self):
        """プールを起動し、モニタリングを開始"""
        self.running = True
        loop = asyncio.get_event_loop()
        self.monitor_thread = threading.Thread(
            target=self._run_monitor_in_thread,
            args=(loop,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info(f"Agent pool {self.pool_name} started with {len(self.workers)} workers")
    
    def _run_monitor_in_thread(self, loop):
        """スレッド内でモニタリングタスクを実行"""
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._monitor_loop())
    
    async def stop(self):
        """プールを停止"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info(f"Agent pool {self.pool_name} stopped")
    
    async def _monitor_loop(self):
        """リソース使用率とタスクキューをモニタリングし、必要に応じてスケーリング"""
        while self.running:
            try:
                # スケーリングの判断
                await self._check_scaling()
                
                # タスク割り当て処理
                await self._assign_tasks()
                
                # 短い間隔で再チェック
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error in agent pool monitor: {str(e)}")
                await asyncio.sleep(10)  # エラー時は少し長めに待機
    
    async def _check_scaling(self):
        """スケーリングの必要性をチェックし、必要に応じて実行"""
        if not self.scaling_policy.can_scale():
            return
        
        current_instances = len(self.workers)
        
        # スケーリングの判断基準となるメトリクスを取得
        metrics = self._get_scaling_metrics()
        
        # 現在のメトリクス情報を収集
        metrics_info = {
            "queue_length": self.task_queue.qsize(),
            "worker_count": current_instances,
            "utilization": sum(1 for w in self.workers.values() if w.busy) / max(1, current_instances),
            "scaling_metric": metrics
        }
        
        # スケールアップの条件
        if (metrics > self.scaling_policy.scale_up_threshold and 
                current_instances < self.scaling_policy.max_instances):
            for _ in range(min(self.scaling_policy.scaling_step, 
                              self.scaling_policy.max_instances - current_instances)):
                self._create_worker()
            self.scaling_policy.update_last_scaling_time()
            new_count = len(self.workers)
            logger.info(f"Scaled up {self.pool_name} to {new_count} workers")
            
            # スケーリングイベントを記録
            scaling_event = ScalingEvent(
                pool_name=self.pool_name,
                direction=ScalingDirection.UP,
                trigger=self.scaling_policy.trigger,
                prev_count=current_instances,
                new_count=new_count,
                metrics=metrics_info,
                reason=f"負荷指標 {metrics:.2f} が閾値 {self.scaling_policy.scale_up_threshold} を超過"
            )
            get_scaling_history().add_event(scaling_event)
        
        # スケールダウンの条件
        elif (metrics < self.scaling_policy.scale_down_threshold and 
                current_instances > self.scaling_policy.min_instances):
            idle_workers = [w_id for w_id, w in self.workers.items() if not w.busy]
            scale_down_count = min(self.scaling_policy.scaling_step, 
                                  current_instances - self.scaling_policy.min_instances,
                                  len(idle_workers))
            
            if scale_down_count > 0:
                for _ in range(scale_down_count):
                    if idle_workers:
                        self._remove_worker(idle_workers.pop())
                
                self.scaling_policy.update_last_scaling_time()
                new_count = len(self.workers)
                logger.info(f"Scaled down {self.pool_name} to {new_count} workers")
                
                # スケーリングイベントを記録
                scaling_event = ScalingEvent(
                    pool_name=self.pool_name,
                    direction=ScalingDirection.DOWN,
                    trigger=self.scaling_policy.trigger,
                    prev_count=current_instances,
                    new_count=new_count,
                    metrics=metrics_info,
                    reason=f"負荷指標 {metrics:.2f} が閾値 {self.scaling_policy.scale_down_threshold} を下回り"
                )
                get_scaling_history().add_event(scaling_event)
    
    def _get_scaling_metrics(self) -> float:
        """スケーリングの判断に使うメトリクスを計算"""
        trigger = self.scaling_policy.trigger
        
        if trigger == ScalingTrigger.QUEUE_LENGTH:
            return self.task_queue.qsize() / (len(self.workers) * 5)  # 1ワーカーあたり5タスクを目安に
        
        elif trigger == ScalingTrigger.RESPONSE_TIME:
            # 直近の応答時間の平均を取得
            response_times = [w.get_response_time() for w in self.workers.values() 
                             if w.get_response_time() > 0]
            if not response_times:
                return 0
            avg_response_time = sum(response_times) / len(response_times)
            target_response_time = config.get('target_response_time', 5.0)  # 目標応答時間（秒）
            return avg_response_time / target_response_time  # 目標に対する比率
        
        elif trigger == ScalingTrigger.CPU_USAGE:
            # CPUリソース使用率の簡易的な近似（実際の実装ではシステムのCPU使用率を測定）
            busy_count = sum(1 for w in self.workers.values() if w.busy)
            return busy_count / len(self.workers)
        
        elif trigger == ScalingTrigger.MEMORY_USAGE:
            # メモリリソース使用率（実際の実装ではsysなどを使ってメモリ使用率を測定）
            return 0.5  # 仮の値
        
        elif trigger == ScalingTrigger.TASK_COMPLEXITY:
            # タスクの複雑さ（実際の実装ではタスクのトークン数や処理時間などから算出）
            return 0.5  # 仮の値
        
        return 0.5  # デフォルト値
    
    async def _assign_tasks(self):
        """キューからタスクを取り出し、空いているワーカーに割り当て"""
        # 空いているワーカーがあり、キューにタスクがある場合に処理
        while not self.task_queue.empty():
            idle_workers = [w_id for w_id, w in self.workers.items() if not w.busy]
            if not idle_workers:
                break  # 空きワーカーがない場合は中断
            
            # タスクを取得して割り当て
            try:
                task = self.task_queue.get_nowait()
                worker_id = idle_workers[0]
                worker = self.workers[worker_id]
                worker.assign_task(task)
                
                # ワーカーでタスクを実行（非同期）
                asyncio.create_task(self._execute_task(worker_id, task))
            except asyncio.QueueEmpty:
                break
    
    async def _execute_task(self, worker_id: str, task: Any):
        """ワーカーでタスクを実行"""
        worker = self.workers.get(worker_id)
        if not worker:
            return
        
        try:
            # 実行する関数とタスクパラメータを取得
            func, params = task
            
            # 実行（スレッドプールを使用して実行）
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor, 
                    lambda: func(worker.agent_instance, **params)
                )
            
            # タスク完了処理
            worker.complete_task()
            return result
        except Exception as e:
            logger.error(f"Error executing task on worker {worker_id}: {str(e)}")
            worker.complete_task()  # エラー時も完了とマーク
            raise
    
    async def submit_task(self, func: Callable, **params) -> asyncio.Future:
        """タスクをプールに提出"""
        future = asyncio.Future()
        await self.task_queue.put((func, params, future))
        logger.debug(f"Task submitted to pool {self.pool_name}, queue size: {self.task_queue.qsize()}")
        return future
    
    def get_metrics(self) -> Dict[str, Any]:
        """プール全体のメトリクスを取得"""
        worker_metrics = [w.get_metrics() for w in self.workers.values()]
        busy_count = sum(1 for w in self.workers.values() if w.busy)
        
        return {
            "pool_name": self.pool_name,
            "worker_count": len(self.workers),
            "busy_workers": busy_count,
            "utilization": busy_count / len(self.workers) if self.workers else 0,
            "queue_size": self.task_queue.qsize(),
            "workers": worker_metrics
        }


class AgentPoolManager:
    """複数のエージェントプールを管理するシングルトンマネージャー"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentPoolManager, cls).__new__(cls)
            cls._instance.pools = {}
            cls._instance.lock = threading.RLock()
        return cls._instance
    
    def create_pool(
        self,
        pool_name: str,
        agent_class: Type,
        agent_kwargs: Dict[str, Any],
        scaling_policy: Optional[ScalingPolicy] = None
    ) -> "AgentPool":
        """
        新しいエージェントプールを作成
        
        Args:
            pool_name: プール名
            agent_class: エージェントクラス
            agent_kwargs: エージェント初期化引数
            scaling_policy: スケーリングポリシー（Noneの場合はデフォルト設定）
            
        Returns:
            AgentPool: 作成されたプール
        """
        with self.lock:
            if pool_name in self.pools:
                logger.warning(f"Pool {pool_name} already exists, returning existing pool")
                return self.pools[pool_name]
            
            # デフォルトのスケーリングポリシー
            if scaling_policy is None:
                scaling_policy = ScalingPolicy(
                    trigger=ScalingTrigger.QUEUE_LENGTH,
                    min_instances=1,
                    max_instances=5
                )
            
            # プールを作成
            pool = AgentPool(
                agent_class=agent_class,
                agent_kwargs=agent_kwargs,
                scaling_policy=scaling_policy,
                pool_name=pool_name
            )
            self.pools[pool_name] = pool
            logger.info(f"Created agent pool: {pool_name}")
            return pool
    
    def get_pool(self, pool_name: str) -> Optional["AgentPool"]:
        """
        名前でプールを取得
        
        Args:
            pool_name: プール名
            
        Returns:
            Optional[AgentPool]: 見つかったプールまたはNone
        """
        return self.pools.get(pool_name)
    
    def list_pools(self) -> List[str]:
        """
        すべてのプール名のリストを取得
        
        Returns:
            List[str]: プール名のリスト
        """
        return list(self.pools.keys())
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        すべてのプールのメトリクスを取得
        
        Returns:
            Dict[str, Any]: プール名をキーとしたメトリクス辞書
        """
        return {name: pool.get_metrics() for name, pool in self.pools.items()}
    
    async def start_all_pools(self):
        """すべてのプールを起動"""
        for pool in self.pools.values():
            await pool.start()
    
    async def stop_all_pools(self):
        """すべてのプールを停止"""
        for pool in self.pools.values():
            await pool.stop()
    
    def remove_pool(self, pool_name: str):
        """
        プールを削除（非推奨、通常はstopを使用）
        
        Args:
            pool_name: 削除するプール名
        """
        with self.lock:
            if pool_name in self.pools:
                del self.pools[pool_name]
                logger.info(f"Removed agent pool: {pool_name}")
    
    def manual_scale(self, pool_name: str, target_count: int, reason: str = "手動スケーリング") -> bool:
        """
        指定されたプールのエージェント数を手動で調整
        
        Args:
            pool_name: エージェントプール名
            target_count: 目標エージェント数
            reason: スケーリングの理由
            
        Returns:
            bool: 成功したかどうか
        """
        with self.lock:
            pool = self.pools.get(pool_name)
            if pool is None:
                logger.error(f"プール {pool_name} が存在しません")
                return False
            
            # 現在のエージェント数
            current_count = len(pool.workers)
            
            # 現在のエージェント数と同じ場合は何もしない
            if target_count == current_count:
                logger.info(f"プール {pool_name} のエージェント数は既に {target_count} です")
                return True
            
            # スケーリングポリシーの範囲内に調整
            target_count = max(pool.scaling_policy.min_instances, 
                             min(pool.scaling_policy.max_instances, target_count))
            
            # スケーリング方向の判定
            if target_count > current_count:
                direction = ScalingDirection.UP
            else:
                direction = ScalingDirection.DOWN
            
            # 現在のメトリクス情報を収集
            metrics_info = {
                "queue_length": pool.task_queue.qsize(),
                "worker_count": current_count,
                "utilization": sum(1 for w in pool.workers.values() if w.busy) / max(1, current_count),
                "target_count": target_count
            }
            
            try:
                # スケールアップ
                if direction == ScalingDirection.UP:
                    for _ in range(target_count - current_count):
                        pool._create_worker()
                    
                    logger.info(f"手動でプール {pool_name} を {current_count} から {target_count} へスケールアップしました")
                
                # スケールダウン
                else:
                    # アイドル状態のワーカーを特定
                    idle_workers = [w_id for w_id, w in pool.workers.items() if not w.busy]
                    
                    # 削除するワーカー数
                    remove_count = current_count - target_count
                    
                    # アイドルワーカーから順に削除
                    for _ in range(min(remove_count, len(idle_workers))):
                        if idle_workers:
                            pool._remove_worker(idle_workers.pop())
                    
                    # ビジー状態のワーカーが多い場合は警告
                    if len(pool.workers) > target_count:
                        logger.warning(f"ビジー状態のワーカーがあるため、目標数 {target_count} に達していません（現在: {len(pool.workers)}）")
                    
                    logger.info(f"手動でプール {pool_name} を {current_count} から {len(pool.workers)} へスケールダウンしました")
                
                # スケーリングイベントを記録
                scaling_event = ScalingEvent(
                    pool_name=pool_name,
                    direction=direction,
                    trigger=ScalingTrigger.MANUAL,
                    prev_count=current_count,
                    new_count=len(pool.workers),
                    metrics=metrics_info,
                    reason=reason
                )
                get_scaling_history().add_event(scaling_event)
                
                # クールダウン期間をリセット
                pool.scaling_policy.update_last_scaling_time()
                
                return True
            except Exception as e:
                logger.error(f"手動スケーリング実行中にエラーが発生しました: {str(e)}")
                
                # 失敗イベントを記録
                scaling_event = ScalingEvent(
                    pool_name=pool_name,
                    direction=direction,
                    trigger=ScalingTrigger.MANUAL,
                    prev_count=current_count,
                    new_count=len(pool.workers),
                    metrics=metrics_info,
                    success=False,
                    reason=f"スケーリング失敗: {str(e)}"
                )
                get_scaling_history().add_event(scaling_event)
                
                return False
    
    def get_scaling_metrics(self, pool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        プールのスケーリングメトリクスを取得
        
        Args:
            pool_name: 特定のプール名（Noneの場合は全て）
            
        Returns:
            Dict: スケーリングメトリクス
        """
        with self.lock:
            result = {}
            
            pools_to_check = [pool_name] if pool_name else self.pools.keys()
            
            for name in pools_to_check:
                pool = self.pools.get(name)
                if not pool:
                    continue
                
                # 基本メトリクス
                metrics = {
                    "current_count": len(pool.workers),
                    "min_instances": pool.scaling_policy.min_instances,
                    "max_instances": pool.scaling_policy.max_instances,
                    "queue_length": pool.task_queue.qsize(),
                    "busy_workers": sum(1 for w in pool.workers.values() if w.busy),
                    "scaling_trigger": pool.scaling_policy.trigger.value,
                    "scale_up_threshold": pool.scaling_policy.scale_up_threshold,
                    "scale_down_threshold": pool.scaling_policy.scale_down_threshold,
                    "cooldown_period": pool.scaling_policy.cooldown_period,
                    "last_scaling_time": pool.scaling_policy.last_scaling_time,
                    "can_scale_now": pool.scaling_policy.can_scale(),
                    "time_since_last_scaling": time.time() - pool.scaling_policy.last_scaling_time
                }
                
                # 現在の負荷指標値（ここではメソッドが存在することを前提としています）
                try:
                    current_metric = pool._get_scaling_metrics()
                    metrics["current_metric_value"] = current_metric
                    
                    # 現在の負荷レベル判定
                    if current_metric >= pool.scaling_policy.scale_up_threshold:
                        metrics["load_level"] = "high"
                    elif current_metric <= pool.scaling_policy.scale_down_threshold:
                        metrics["load_level"] = "low"
                    else:
                        metrics["load_level"] = "medium"
                except Exception as e:
                    logger.warning(f"スケーリングメトリクス取得中にエラー: {str(e)}")
                    metrics["current_metric_value"] = None
                    metrics["load_level"] = "unknown"
                
                # ワーカー詳細
                try:
                    metrics["workers"] = [w.get_metrics() for w in pool.workers.values()]
                except Exception:
                    metrics["workers"] = []
                
                result[name] = metrics
            
            return result
    
    def get_pools_status(self) -> Dict[str, Dict[str, Any]]:
        """
        全プールのステータス情報を取得
        
        Returns:
            Dict: プール名をキーとしたステータス情報
        """
        with self.lock:
            status = {}
            
            for name, pool in self.pools.items():
                # 基本情報
                pool_status = {
                    "name": name,
                    "worker_count": len(pool.workers),
                    "busy_workers": sum(1 for w in pool.workers.values() if w.busy),
                    "idle_workers": sum(1 for w in pool.workers.values() if not w.busy),
                    "queue_size": pool.task_queue.qsize(),
                    "agent_class": pool.agent_class.__name__,
                    "is_running": hasattr(pool, 'running') and pool.running,
                    "scaling_policy": pool.scaling_policy.to_dict() if hasattr(pool, 'scaling_policy') else None
                }
                
                # 利用率の計算
                if pool_status["worker_count"] > 0:
                    pool_status["utilization"] = pool_status["busy_workers"] / pool_status["worker_count"]
                else:
                    pool_status["utilization"] = 0
                
                status[name] = pool_status
            
            return status
    
    def update_scaling_policy(
        self,
        pool_name: str,
        min_instances: Optional[int] = None,
        max_instances: Optional[int] = None,
        scale_up_threshold: Optional[float] = None,
        scale_down_threshold: Optional[float] = None,
        cooldown_period: Optional[int] = None,
        scaling_step: Optional[int] = None,
        trigger: Optional[ScalingTrigger] = None
    ) -> bool:
        """
        プールのスケーリングポリシーを更新
        
        Args:
            pool_name: プール名
            min_instances: 最小インスタンス数
            max_instances: 最大インスタンス数
            scale_up_threshold: スケールアップ閾値
            scale_down_threshold: スケールダウン閾値
            cooldown_period: クールダウン期間（秒）
            scaling_step: 一度にスケールするステップ数
            trigger: スケーリングトリガー
            
        Returns:
            bool: 更新が成功したかどうか
        """
        with self.lock:
            pool = self.pools.get(pool_name)
            if pool is None:
                logger.error(f"プール {pool_name} が存在しません")
                return False
            
            try:
                policy = pool.scaling_policy
                
                # 値の検証
                if min_instances is not None and min_instances < 1:
                    logger.warning(f"min_instances は 1 以上である必要があります (指定値: {min_instances})")
                    min_instances = 1
                
                if max_instances is not None and min_instances is not None and max_instances < min_instances:
                    logger.warning(f"max_instances は min_instances 以上である必要があります (指定値: min={min_instances}, max={max_instances})")
                    max_instances = min_instances
                
                if scale_up_threshold is not None and scale_down_threshold is not None and scale_up_threshold <= scale_down_threshold:
                    logger.warning(f"scale_up_threshold は scale_down_threshold より大きい必要があります (指定値: up={scale_up_threshold}, down={scale_down_threshold})")
                    scale_up_threshold = scale_down_threshold + 0.2
                
                # 値の更新
                if min_instances is not None:
                    policy.min_instances = min_instances
                
                if max_instances is not None:
                    policy.max_instances = max_instances
                
                if scale_up_threshold is not None:
                    policy.scale_up_threshold = scale_up_threshold
                
                if scale_down_threshold is not None:
                    policy.scale_down_threshold = scale_down_threshold
                
                if cooldown_period is not None:
                    policy.cooldown_period = cooldown_period
                
                if scaling_step is not None:
                    policy.scaling_step = scaling_step
                
                if trigger is not None:
                    policy.trigger = trigger
                
                logger.info(f"プール {pool_name} のスケーリングポリシーを更新しました: {policy.to_dict()}")
                
                # 現在のワーカー数が新しい最小値を下回っている場合、スケールアップ
                current_count = len(pool.workers)
                if current_count < policy.min_instances:
                    logger.info(f"プール {pool_name} を最小インスタンス数 {policy.min_instances} まで自動スケールアップします")
                    self.manual_scale(pool_name, policy.min_instances, "最小インスタンス数に合わせた自動調整")
                
                return True
            except Exception as e:
                logger.error(f"スケーリングポリシー更新中にエラーが発生しました: {str(e)}")
                return False

# ヘルパー関数

def get_pool_manager() -> AgentPoolManager:
    """AgentPoolManagerのグローバルインスタンスを取得"""
    return AgentPoolManager()

def get_scaling_events(
    pool_name: Optional[str] = None,
    limit: int = 100,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    direction: Optional[ScalingDirection] = None,
    trigger: Optional[ScalingTrigger] = None
) -> List[Dict[str, Any]]:
    """
    条件に一致するスケーリングイベントを取得するヘルパー関数
    
    Args:
        pool_name: エージェントプール名フィルタ
        limit: 取得する最大イベント数
        start_time: 取得開始時間（秒単位のエポック時間）
        end_time: 取得終了時間（秒単位のエポック時間）
        direction: スケーリング方向フィルタ
        trigger: トリガー条件フィルタ
        
    Returns:
        List[Dict[str, Any]]: イベント辞書のリスト
    """
    history = get_scaling_history()
    return history.get_events(
        pool_name=pool_name,
        limit=limit,
        start_time=start_time,
        end_time=end_time,
        direction=direction,
        trigger=trigger
    )

def get_scaling_summary(pool_name: Optional[str] = None, period_hours: int = 24) -> Dict[str, Any]:
    """
    スケーリングイベントのサマリー統計を取得するヘルパー関数
    
    Args:
        pool_name: エージェントプール名フィルタ
        period_hours: 集計期間（時間）
        
    Returns:
        Dict[str, Any]: サマリー統計
    """
    history = get_scaling_history()
    return history.get_summary(pool_name=pool_name, period_hours=period_hours)

def manual_scale_pool(pool_name: str, target_count: int, reason: str = "手動スケーリング") -> bool:
    """
    指定されたプールのエージェント数を手動で調整するヘルパー関数
    
    Args:
        pool_name: エージェントプール名
        target_count: 目標エージェント数
        reason: スケーリングの理由
        
    Returns:
        bool: 成功したかどうか
    """
    manager = get_pool_manager()
    return manager.manual_scale(pool_name, target_count, reason) 