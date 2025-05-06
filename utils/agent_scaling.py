"""
動的エージェントスケーリングユーティリティ。
負荷やタスクの複雑さに応じてエージェントを増減できる機能を提供します。
"""

import time
import threading
import asyncio
from typing import Dict, List, Callable, Any, Optional, Type, Tuple
import concurrent.futures
from enum import Enum

from utils.logger import get_logger
from utils.config import config

logger = get_logger("agent_scaling")

class ScalingTrigger(Enum):
    """スケーリングをトリガーする条件"""
    QUEUE_LENGTH = "queue_length"  # タスクキューの長さ
    RESPONSE_TIME = "response_time"  # エージェントの応答時間
    CPU_USAGE = "cpu_usage"  # CPUリソース使用率
    MEMORY_USAGE = "memory_usage"  # メモリリソース使用率
    TASK_COMPLEXITY = "task_complexity"  # タスクの複雑さ

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
        
        # スケールアップの条件
        if (metrics > self.scaling_policy.scale_up_threshold and 
                current_instances < self.scaling_policy.max_instances):
            for _ in range(min(self.scaling_policy.scaling_step, 
                              self.scaling_policy.max_instances - current_instances)):
                self._create_worker()
            self.scaling_policy.update_last_scaling_time()
            logger.info(f"Scaled up {self.pool_name} to {len(self.workers)} workers")
        
        # スケールダウンの条件
        elif (metrics < self.scaling_policy.scale_down_threshold and 
                current_instances > self.scaling_policy.min_instances):
            idle_workers = [w_id for w_id, w in self.workers.items() if not w.busy]
            for _ in range(min(self.scaling_policy.scaling_step, 
                              current_instances - self.scaling_policy.min_instances,
                              len(idle_workers))):
                if idle_workers:
                    self._remove_worker(idle_workers.pop())
            self.scaling_policy.update_last_scaling_time()
            logger.info(f"Scaled down {self.pool_name} to {len(self.workers)} workers")
    
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
    ) -> AgentPool:
        """新しいエージェントプールを作成"""
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
    
    def get_pool(self, pool_name: str) -> Optional[AgentPool]:
        """名前でプールを取得"""
        return self.pools.get(pool_name)
    
    def list_pools(self) -> List[str]:
        """すべてのプール名のリストを取得"""
        return list(self.pools.keys())
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """すべてのプールのメトリクスを取得"""
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
        """プールを削除（非推奨、通常はstopを使用）"""
        with self.lock:
            if pool_name in self.pools:
                del self.pools[pool_name]
                logger.info(f"Removed agent pool: {pool_name}") 