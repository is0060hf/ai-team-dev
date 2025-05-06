"""
パフォーマンスモニタリングおよびプロファイリングモジュール。
アプリケーションのボトルネックを特定し、最適化するための機能を提供します。
"""

import time
import functools
import gc
import threading
import tracemalloc
from typing import Dict, List, Any, Callable, Optional, TypeVar, Union, cast
from contextlib import contextmanager
import cProfile
import pstats
import io
import psutil
from datetime import datetime

from utils.logger import get_structured_logger
from utils.tracing import trace, add_trace_event

# 型変数の定義
T = TypeVar('T')

# ロガーの設定
logger = get_structured_logger("performance")

# パフォーマンスメトリクスの保存
_performance_metrics = {
    "function_timings": {},  # 関数ごとの実行時間統計
    "memory_usage": [],      # メモリ使用量履歴
    "cpu_usage": [],         # CPU使用量履歴
    "slow_operations": [],   # 遅い操作のリスト
}

# 設定
_settings = {
    "slow_threshold_ms": 500,  # 「遅い」と判断する閾値（ミリ秒）
    "enable_profiling": False,  # プロファイリングが有効かどうか
    "max_history_size": 100,   # 履歴の最大サイズ
}


@contextmanager
def time_operation(operation_name: str, log_level: str = "debug", add_to_trace: bool = True):
    """
    処理時間を測定するコンテキストマネージャー
    
    Args:
        operation_name: 操作の名前
        log_level: ログレベル（debug, info, warning, error）
        add_to_trace: トレース情報に追加するかどうか
        
    Yields:
        None
    """
    start_time = time.time()
    
    try:
        yield
    finally:
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # 関数実行時間統計を更新
        if operation_name not in _performance_metrics["function_timings"]:
            _performance_metrics["function_timings"][operation_name] = {
                "count": 0,
                "total_ms": 0,
                "min_ms": float('inf'),
                "max_ms": 0,
                "avg_ms": 0,
            }
        
        stats = _performance_metrics["function_timings"][operation_name]
        stats["count"] += 1
        stats["total_ms"] += duration_ms
        stats["min_ms"] = min(stats["min_ms"], duration_ms)
        stats["max_ms"] = max(stats["max_ms"], duration_ms)
        stats["avg_ms"] = stats["total_ms"] / stats["count"]
        
        # 「遅い」操作をログに記録
        if duration_ms > _settings["slow_threshold_ms"]:
            _performance_metrics["slow_operations"].append({
                "name": operation_name,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat(),
            })
            
            # 履歴サイズを制限
            if len(_performance_metrics["slow_operations"]) > _settings["max_history_size"]:
                _performance_metrics["slow_operations"] = _performance_metrics["slow_operations"][-_settings["max_history_size"]:]
            
            log_context = {
                "operation": operation_name,
                "duration_ms": duration_ms,
                "threshold_ms": _settings["slow_threshold_ms"]
            }
            
            # ログレベルに応じたメソッドを呼び出し
            if log_level == "info":
                logger.info(f"遅い操作: {operation_name} ({duration_ms:.2f}ms)", context=log_context)
            elif log_level == "warning":
                logger.warning(f"遅い操作: {operation_name} ({duration_ms:.2f}ms)", context=log_context)
            elif log_level == "error":
                logger.error(f"遅い操作: {operation_name} ({duration_ms:.2f}ms)", context=log_context)
            else:  # デフォルトはdebug
                logger.debug(f"遅い操作: {operation_name} ({duration_ms:.2f}ms)", context=log_context)
        
        # トレース情報に追加（オプション）
        if add_to_trace:
            add_trace_event(f"operation_{operation_name}", {"duration_ms": duration_ms})


def time_function(log_level: str = "debug", add_to_trace: bool = True):
    """
    関数の実行時間を測定するデコレーター
    
    Args:
        log_level: ログレベル（debug, info, warning, error）
        add_to_trace: トレース情報に追加するかどうか
        
    Returns:
        Callable: デコレーター関数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            operation_name = f"{func.__module__}.{func.__name__}"
            with time_operation(operation_name, log_level, add_to_trace):
                return func(*args, **kwargs)
        
        return cast(Callable[..., T], wrapper)
    
    return decorator


@contextmanager
def profile_operation(operation_name: str, output_file: Optional[str] = None):
    """
    処理のプロファイリングを行うコンテキストマネージャー
    
    Args:
        operation_name: 操作の名前
        output_file: 結果を出力するファイル名
        
    Yields:
        None
    """
    if not _settings["enable_profiling"]:
        yield
        return
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        yield
    finally:
        profiler.disable()
        
        # 結果を文字列にフォーマット
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # 上位20件のみ
        
        # ログに記録
        logger.info(f"プロファイリング結果: {operation_name}", context={
            "operation": operation_name,
            "profile_results": s.getvalue()
        })
        
        # ファイルに出力（オプション）
        if output_file:
            ps.dump_stats(output_file)


def profile_function(output_file: Optional[str] = None):
    """
    関数のプロファイリングを行うデコレーター
    
    Args:
        output_file: 結果を出力するファイル名
        
    Returns:
        Callable: デコレーター関数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            operation_name = f"{func.__module__}.{func.__name__}"
            with profile_operation(operation_name, output_file):
                return func(*args, **kwargs)
        
        return cast(Callable[..., T], wrapper)
    
    return decorator


@contextmanager
def memory_profiler(operation_name: str, log_level: str = "debug"):
    """
    メモリ使用量を測定するコンテキストマネージャー
    
    Args:
        operation_name: 操作の名前
        log_level: ログレベル（debug, info, warning, error）
        
    Yields:
        None
    """
    # tracemalloc を開始
    tracemalloc.start()
    start_snapshot = tracemalloc.take_snapshot()
    
    try:
        yield
    finally:
        # 終了時のスナップショットを取得
        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()
        
        # 差分を計算
        top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')
        
        # メモリ使用量を記録
        total_diff = sum(stat.size_diff for stat in top_stats)
        
        _performance_metrics["memory_usage"].append({
            "operation": operation_name,
            "memory_diff_bytes": total_diff,
            "timestamp": datetime.now().isoformat(),
        })
        
        # 履歴サイズを制限
        if len(_performance_metrics["memory_usage"]) > _settings["max_history_size"]:
            _performance_metrics["memory_usage"] = _performance_metrics["memory_usage"][-_settings["max_history_size"]:]
        
        # 結果をログに記録
        memory_diff_mb = total_diff / (1024 * 1024)
        log_context = {
            "operation": operation_name,
            "memory_diff_mb": memory_diff_mb,
            "top_allocations": [str(stat) for stat in top_stats[:5]]
        }
        
        # ログレベルに応じたメソッドを呼び出し
        if log_level == "info":
            logger.info(f"メモリ使用量: {operation_name} ({memory_diff_mb:.2f}MB)", context=log_context)
        elif log_level == "warning":
            logger.warning(f"メモリ使用量: {operation_name} ({memory_diff_mb:.2f}MB)", context=log_context)
        elif log_level == "error":
            logger.error(f"メモリ使用量: {operation_name} ({memory_diff_mb:.2f}MB)", context=log_context)
        else:  # デフォルトはdebug
            logger.debug(f"メモリ使用量: {operation_name} ({memory_diff_mb:.2f}MB)", context=log_context)


def collect_system_metrics():
    """
    システムメトリクス（CPU、メモリ使用率など）を収集
    
    Returns:
        Dict: システムメトリクス
    """
    process = psutil.Process()
    
    # プロセスのCPU使用率
    process_cpu_percent = process.cpu_percent(interval=0.1)
    
    # プロセスのメモリ使用量
    memory_info = process.memory_info()
    memory_usage_mb = memory_info.rss / (1024 * 1024)
    
    # システム全体のCPU使用率
    system_cpu_percent = psutil.cpu_percent(interval=0.1)
    
    # システム全体のメモリ使用率
    system_memory = psutil.virtual_memory()
    system_memory_percent = system_memory.percent
    
    metrics = {
        "process": {
            "cpu_percent": process_cpu_percent,
            "memory_usage_mb": memory_usage_mb,
            "thread_count": threading.active_count(),
        },
        "system": {
            "cpu_percent": system_cpu_percent,
            "memory_percent": system_memory_percent,
            "memory_available_mb": system_memory.available / (1024 * 1024),
            "memory_total_mb": system_memory.total / (1024 * 1024),
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    # メトリクスを履歴に追加
    _performance_metrics["cpu_usage"].append({
        "process_cpu_percent": process_cpu_percent,
        "system_cpu_percent": system_cpu_percent,
        "timestamp": metrics["timestamp"],
    })
    
    # 履歴サイズを制限
    if len(_performance_metrics["cpu_usage"]) > _settings["max_history_size"]:
        _performance_metrics["cpu_usage"] = _performance_metrics["cpu_usage"][-_settings["max_history_size"]:]
    
    return metrics


@trace("get_performance_metrics")
def get_performance_metrics(reset: bool = False) -> Dict[str, Any]:
    """
    収集したパフォーマンスメトリクスを取得
    
    Args:
        reset: 取得後にメトリクスをリセットするかどうか
        
    Returns:
        Dict: パフォーマンスメトリクス
    """
    # 現在のメトリクスのコピーを作成
    metrics_copy = {
        "function_timings": dict(_performance_metrics["function_timings"]),
        "memory_usage": list(_performance_metrics["memory_usage"]),
        "cpu_usage": list(_performance_metrics["cpu_usage"]),
        "slow_operations": list(_performance_metrics["slow_operations"]),
        "current_system_metrics": collect_system_metrics(),
    }
    
    # リセットが要求された場合
    if reset:
        _performance_metrics["function_timings"] = {}
        _performance_metrics["memory_usage"] = []
        _performance_metrics["cpu_usage"] = []
        _performance_metrics["slow_operations"] = []
    
    return metrics_copy


def optimize_memory():
    """メモリ使用量を最適化（不要なオブジェクトの解放など）"""
    # 明示的なガベージコレクションを実行
    collected = gc.collect()
    
    logger.info(f"ガベージコレクション実行: {collected} オブジェクトを解放しました")
    
    # 現在のメモリ使用量を取得
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_usage_mb = memory_info.rss / (1024 * 1024)
    
    logger.info(f"現在のメモリ使用量: {memory_usage_mb:.2f}MB")
    
    return {
        "collected_objects": collected,
        "memory_usage_mb": memory_usage_mb,
    }


def configure_performance_settings(
    slow_threshold_ms: Optional[int] = None,
    enable_profiling: Optional[bool] = None,
    max_history_size: Optional[int] = None
):
    """
    パフォーマンス設定を構成
    
    Args:
        slow_threshold_ms: 「遅い」と判断する閾値（ミリ秒）
        enable_profiling: プロファイリングを有効にするかどうか
        max_history_size: 履歴の最大サイズ
    """
    if slow_threshold_ms is not None:
        _settings["slow_threshold_ms"] = slow_threshold_ms
    
    if enable_profiling is not None:
        _settings["enable_profiling"] = enable_profiling
    
    if max_history_size is not None:
        _settings["max_history_size"] = max_history_size
    
    logger.info("パフォーマンス設定を更新しました", context=_settings)


# 自動的にメトリクスを収集するバックグラウンドスレッド
class MetricsCollectorThread(threading.Thread):
    """メトリクスを定期的に収集するスレッド"""
    
    def __init__(self, interval: int = 60):
        """
        Args:
            interval: 収集間隔（秒）
        """
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_event = threading.Event()
    
    def run(self):
        """スレッドの実行"""
        logger.info(f"メトリクス収集スレッドを開始しました（間隔: {self.interval}秒）")
        
        while not self.stop_event.is_set():
            try:
                collect_system_metrics()
            except Exception as e:
                logger.error(f"メトリクス収集中にエラーが発生しました: {str(e)}")
            
            # 次の収集まで待機
            self.stop_event.wait(self.interval)
        
        logger.info("メトリクス収集スレッドを停止しました")
    
    def stop(self):
        """スレッドの停止"""
        self.stop_event.set()


# メトリクス収集スレッドのインスタンス
_metrics_collector_thread = None


def start_metrics_collector(interval: int = 60):
    """
    メトリクス収集スレッドを開始
    
    Args:
        interval: 収集間隔（秒）
    """
    global _metrics_collector_thread
    
    if _metrics_collector_thread is not None and _metrics_collector_thread.is_alive():
        logger.warning("メトリクス収集スレッドは既に実行中です")
        return
    
    _metrics_collector_thread = MetricsCollectorThread(interval)
    _metrics_collector_thread.start()


def stop_metrics_collector():
    """メトリクス収集スレッドを停止"""
    global _metrics_collector_thread
    
    if _metrics_collector_thread is None or not _metrics_collector_thread.is_alive():
        logger.warning("メトリクス収集スレッドは実行されていません")
        return
    
    _metrics_collector_thread.stop()
    _metrics_collector_thread.join(timeout=5)
    _metrics_collector_thread = None 