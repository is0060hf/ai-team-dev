"""
高度な負荷検知機能モジュール。
リアルタイムタスクキューモニタリング、タスク実行時間統計収集、
CPU/メモリ使用状況モニタリング連携、予測的負荷分析アルゴリズム、
負荷閾値自動調整機能を提供します。
"""

import time
import threading
import asyncio
import numpy as np
from typing import Dict, List, Any, Optional, Callable, Union, Tuple, Deque
from collections import deque
from datetime import datetime
import psutil
from enum import Enum
import json
import os
from pathlib import Path

from utils.logger import get_structured_logger
from utils.performance import collect_system_metrics
from utils.monitoring import MetricType, MetricUnit, MetricDefinition, MetricValue
from utils.monitoring import increment_counter, record_gauge, record_histogram
from utils.tracing import trace, add_trace_event

# ロガーの設定
logger = get_structured_logger("load_detection")

class LoadMetricType(Enum):
    """負荷メトリクスの種類を定義する列挙型"""
    TASK_QUEUE_LENGTH = "task_queue_length"
    TASK_EXECUTION_TIME = "task_execution_time"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    COMBINED_LOAD = "combined_load"

class TaskPriority(Enum):
    """タスクの優先度を定義する列挙型"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class LoadTrend(Enum):
    """負荷トレンドを定義する列挙型"""
    STABLE = "stable"
    INCREASING = "increasing"
    DECREASING = "decreasing"
    SPIKING = "spiking"

class LoadMetrics:
    """負荷メトリクスの収集と分析を行うクラス"""
    
    def __init__(
        self,
        history_size: int = 60,
        window_size: int = 10,
        save_path: Optional[str] = None
    ):
        """
        Args:
            history_size: 履歴を保存するデータポイント数
            window_size: トレンド分析に使用するウィンドウサイズ
            save_path: メトリクス履歴の保存先パス
        """
        self.history_size = history_size
        self.window_size = window_size
        
        # メトリクス履歴の初期化
        self.metrics_history: Dict[str, Deque] = {
            LoadMetricType.TASK_QUEUE_LENGTH.value: deque(maxlen=history_size),
            LoadMetricType.TASK_EXECUTION_TIME.value: deque(maxlen=history_size),
            LoadMetricType.CPU_USAGE.value: deque(maxlen=history_size),
            LoadMetricType.MEMORY_USAGE.value: deque(maxlen=history_size),
            LoadMetricType.COMBINED_LOAD.value: deque(maxlen=history_size),
        }
        
        # タスク実行時間の詳細統計
        self.execution_time_stats = {
            "count": 0,
            "sum": 0,
            "min": float('inf'),
            "max": 0,
            "mean": 0,
            "p50": 0,  # 50th percentile (median)
            "p90": 0,  # 90th percentile
            "p95": 0,  # 95th percentile
            "p99": 0,  # 99th percentile
            "recent_values": deque(maxlen=100),  # 直近の実行時間
        }
        
        # 負荷閾値の設定（初期値）
        self.thresholds = {
            LoadMetricType.TASK_QUEUE_LENGTH.value: {
                "low": 2,
                "medium": 5,
                "high": 10
            },
            LoadMetricType.TASK_EXECUTION_TIME.value: {
                "low": 1.0,  # 秒
                "medium": 3.0,
                "high": 8.0
            },
            LoadMetricType.CPU_USAGE.value: {
                "low": 30.0,  # パーセント
                "medium": 60.0,
                "high": 80.0
            },
            LoadMetricType.MEMORY_USAGE.value: {
                "low": 30.0,  # パーセント
                "medium": 60.0,
                "high": 80.0
            },
            LoadMetricType.COMBINED_LOAD.value: {
                "low": 0.3,  # 正規化された値
                "medium": 0.6,
                "high": 0.8
            }
        }
        
        # 自動調整のための閾値履歴
        self.threshold_history = {metric: [] for metric in self.thresholds}
        
        # 予測モデルのパラメータ
        self.prediction_weights = np.array([0.7, 0.2, 0.05, 0.05])  # 現在値、変化率、変化の加速度、周期性の重み
        
        # メトリクス保存パス設定
        if save_path is None:
            storage_dir = Path("storage/load_metrics")
            storage_dir.mkdir(parents=True, exist_ok=True)
            self.save_path = str(storage_dir / "load_metrics_history.json")
        else:
            self.save_path = save_path
        
        # 負荷メトリクスの監視スレッド
        self.monitor_thread = None
        self.running = False
        self.lock = threading.RLock()
        
        # 起動時に履歴を読み込み
        self._load_history()

    def start_monitoring(self, interval: int = 5):
        """
        負荷メトリクスの監視を開始
        
        Args:
            interval: 監視間隔（秒）
        """
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("負荷メトリクス監視は既に実行中です")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_worker,
            args=(interval,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info(f"負荷メトリクス監視を開始しました（間隔: {interval}秒）")

    def stop_monitoring(self):
        """負荷メトリクス監視を停止"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            self.monitor_thread = None
            logger.info("負荷メトリクス監視を停止しました")

    def _monitoring_worker(self, interval: int):
        """
        負荷メトリクスを定期的に収集するワーカー関数
        
        Args:
            interval: 収集間隔（秒）
        """
        while self.running:
            try:
                # システムメトリクスの収集
                system_metrics = collect_system_metrics()
                
                # メトリクスの更新
                cpu_usage = system_metrics["system"]["cpu_percent"]
                memory_usage = system_metrics["system"]["memory_percent"]
                
                self.update_cpu_usage(cpu_usage)
                self.update_memory_usage(memory_usage)
                
                # 閾値の自動調整（10分ごと）
                if int(time.time()) % 600 < interval:
                    self.adjust_thresholds()
                
                # メトリクス履歴の保存（1時間ごと）
                if int(time.time()) % 3600 < interval:
                    self._save_history()
                
                # モニタリングメトリクスの送信
                record_gauge("agent_scaling.load.cpu_usage", cpu_usage)
                record_gauge("agent_scaling.load.memory_usage", memory_usage)
                
                # 結合負荷の計算と更新
                self.update_combined_load()
                
                # 次の収集まで待機
                time.sleep(interval)
            except Exception as e:
                logger.error(f"負荷メトリクス収集中にエラーが発生しました: {str(e)}")
                time.sleep(interval)

    @trace("update_task_queue_length")
    def update_task_queue_length(self, queue_length: int, agent_pool: str = "default"):
        """
        タスクキュー長を更新
        
        Args:
            queue_length: タスクキューの長さ
            agent_pool: エージェントプール名
        """
        with self.lock:
            timestamp = time.time()
            
            # タスクキュー長を履歴に追加
            self.metrics_history[LoadMetricType.TASK_QUEUE_LENGTH.value].append({
                "value": queue_length,
                "timestamp": timestamp,
                "agent_pool": agent_pool
            })
            
            # モニタリングメトリクスの送信
            record_gauge("agent_scaling.queue_length", queue_length, labels={"agent_pool": agent_pool})
            
            # 結合負荷の更新
            self.update_combined_load()
            
            logger.debug(f"タスクキュー長を更新: {queue_length} (プール: {agent_pool})")
            return queue_length

    @trace("update_task_execution_time")
    def update_task_execution_time(self, execution_time: float, task_type: str = "default", priority: TaskPriority = TaskPriority.MEDIUM):
        """
        タスク実行時間を更新
        
        Args:
            execution_time: タスク実行時間（秒）
            task_type: タスクの種類
            priority: タスクの優先度
        """
        with self.lock:
            timestamp = time.time()
            
            # タスク実行時間を履歴に追加
            self.metrics_history[LoadMetricType.TASK_EXECUTION_TIME.value].append({
                "value": execution_time,
                "timestamp": timestamp,
                "task_type": task_type,
                "priority": priority.value
            })
            
            # 実行時間統計の更新
            self.execution_time_stats["count"] += 1
            self.execution_time_stats["sum"] += execution_time
            self.execution_time_stats["min"] = min(self.execution_time_stats["min"], execution_time)
            self.execution_time_stats["max"] = max(self.execution_time_stats["max"], execution_time)
            self.execution_time_stats["mean"] = self.execution_time_stats["sum"] / self.execution_time_stats["count"]
            
            # 直近の値を追加
            self.execution_time_stats["recent_values"].append(execution_time)
            
            # パーセンタイルの更新（直近100件のみを使用）
            if len(self.execution_time_stats["recent_values"]) >= 5:  # 最低5件のデータが必要
                recent_values = sorted(self.execution_time_stats["recent_values"])
                n = len(recent_values)
                
                self.execution_time_stats["p50"] = recent_values[int(n * 0.5)]
                self.execution_time_stats["p90"] = recent_values[int(n * 0.9)]
                self.execution_time_stats["p95"] = recent_values[int(n * 0.95)]
                self.execution_time_stats["p99"] = recent_values[min(int(n * 0.99), n - 1)]
            
            # モニタリングメトリクスの送信
            record_histogram("agent_scaling.execution_time", execution_time, 
                           labels={"task_type": task_type, "priority": str(priority.value)})
            
            # 結合負荷の更新
            self.update_combined_load()
            
            logger.debug(f"タスク実行時間を更新: {execution_time}秒 (タイプ: {task_type}, 優先度: {priority.name})")
            return self.execution_time_stats

    def update_cpu_usage(self, cpu_percent: float):
        """
        CPU使用率を更新
        
        Args:
            cpu_percent: CPU使用率（パーセント）
        """
        with self.lock:
            timestamp = time.time()
            
            # CPU使用率を履歴に追加
            self.metrics_history[LoadMetricType.CPU_USAGE.value].append({
                "value": cpu_percent,
                "timestamp": timestamp
            })
            
            # 結合負荷の更新
            self.update_combined_load()
            
            logger.debug(f"CPU使用率を更新: {cpu_percent}%")
            return cpu_percent

    def update_memory_usage(self, memory_percent: float):
        """
        メモリ使用率を更新
        
        Args:
            memory_percent: メモリ使用率（パーセント）
        """
        with self.lock:
            timestamp = time.time()
            
            # メモリ使用率を履歴に追加
            self.metrics_history[LoadMetricType.MEMORY_USAGE.value].append({
                "value": memory_percent,
                "timestamp": timestamp
            })
            
            # 結合負荷の更新
            self.update_combined_load()
            
            logger.debug(f"メモリ使用率を更新: {memory_percent}%")
            return memory_percent

    def update_combined_load(self):
        """結合負荷指標を計算して更新"""
        with self.lock:
            # 各メトリクスの最新値を取得
            queue_length = self._get_latest_value(LoadMetricType.TASK_QUEUE_LENGTH.value, 0)
            execution_time = self._get_latest_value(LoadMetricType.TASK_EXECUTION_TIME.value, 0)
            cpu_usage = self._get_latest_value(LoadMetricType.CPU_USAGE.value, 0)
            memory_usage = self._get_latest_value(LoadMetricType.MEMORY_USAGE.value, 0)
            
            # 各メトリクスを正規化（0-1スケール）
            normalized_queue = min(1.0, queue_length / self.thresholds[LoadMetricType.TASK_QUEUE_LENGTH.value]["high"])
            normalized_exec_time = min(1.0, execution_time / self.thresholds[LoadMetricType.TASK_EXECUTION_TIME.value]["high"])
            normalized_cpu = min(1.0, cpu_usage / 100.0)
            normalized_memory = min(1.0, memory_usage / 100.0)
            
            # 重み付き結合（ここでは単純な平均を使用）
            weights = [0.4, 0.2, 0.25, 0.15]  # キュー長、実行時間、CPU、メモリの重み
            combined_load = (
                weights[0] * normalized_queue +
                weights[1] * normalized_exec_time +
                weights[2] * normalized_cpu +
                weights[3] * normalized_memory
            )
            
            timestamp = time.time()
            
            # 結合負荷を履歴に追加
            self.metrics_history[LoadMetricType.COMBINED_LOAD.value].append({
                "value": combined_load,
                "timestamp": timestamp,
                "components": {
                    "queue_length": normalized_queue,
                    "execution_time": normalized_exec_time,
                    "cpu_usage": normalized_cpu,
                    "memory_usage": normalized_memory
                }
            })
            
            # モニタリングメトリクスの送信
            record_gauge("agent_scaling.combined_load", combined_load)
            
            logger.debug(f"結合負荷指標を更新: {combined_load:.4f}")
            return combined_load

    def get_current_load(self) -> Dict[str, Any]:
        """
        現在の負荷状態を取得
        
        Returns:
            Dict: 負荷メトリクスと状態の辞書
        """
        with self.lock:
            # 各メトリクスの最新値を取得
            queue_length = self._get_latest_value(LoadMetricType.TASK_QUEUE_LENGTH.value, 0)
            execution_time = self._get_latest_value(LoadMetricType.TASK_EXECUTION_TIME.value, 0)
            cpu_usage = self._get_latest_value(LoadMetricType.CPU_USAGE.value, 0)
            memory_usage = self._get_latest_value(LoadMetricType.MEMORY_USAGE.value, 0)
            combined_load = self._get_latest_value(LoadMetricType.COMBINED_LOAD.value, 0)
            
            # 負荷レベルの判定
            load_level = self._determine_load_level(combined_load, LoadMetricType.COMBINED_LOAD.value)
            
            # トレンドの分析
            load_trend = self._analyze_trend(LoadMetricType.COMBINED_LOAD.value)
            
            # 予測値
            predicted_load = self.predict_load(minutes_ahead=5)
            
            return {
                "metrics": {
                    "task_queue_length": queue_length,
                    "task_execution_time": execution_time,
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "combined_load": combined_load
                },
                "execution_time_stats": self.execution_time_stats,
                "load_level": load_level,
                "load_trend": load_trend.value,
                "predicted_load": predicted_load,
                "timestamp": time.time()
            }

    def _get_latest_value(self, metric_type: str, default: float = 0) -> float:
        """
        指定したメトリクスの最新値を取得
        
        Args:
            metric_type: メトリクスタイプ
            default: 値が存在しない場合のデフォルト値
            
        Returns:
            float: メトリクスの最新値
        """
        history = self.metrics_history.get(metric_type, [])
        if not history:
            return default
        
        return history[-1]["value"]

    def _determine_load_level(self, value: float, metric_type: str) -> str:
        """
        負荷レベルを判定
        
        Args:
            value: メトリクス値
            metric_type: メトリクスタイプ
            
        Returns:
            str: 負荷レベル（"low", "medium", "high", "critical"）
        """
        thresholds = self.thresholds.get(metric_type, {"low": 0.3, "medium": 0.6, "high": 0.8})
        
        if value < thresholds["low"]:
            return "low"
        elif value < thresholds["medium"]:
            return "medium"
        elif value < thresholds["high"]:
            return "high"
        else:
            return "critical"

    def _analyze_trend(self, metric_type: str) -> LoadTrend:
        """
        メトリクスのトレンドを分析
        
        Args:
            metric_type: メトリクスタイプ
            
        Returns:
            LoadTrend: トレンド（安定、増加、減少、急増）
        """
        history = self.metrics_history.get(metric_type, [])
        if len(history) < self.window_size:
            return LoadTrend.STABLE
        
        # 最新のwindow_size分のデータを抽出
        recent_values = [item["value"] for item in list(history)[-self.window_size:]]
        
        # 線形回帰で傾きを計算
        x = np.arange(len(recent_values))
        slope, _ = np.polyfit(x, recent_values, 1)
        
        # 変動係数を計算
        mean = np.mean(recent_values)
        std = np.std(recent_values)
        variation = std / mean if mean > 0 else 0
        
        # 傾きと変動からトレンドを判定
        if variation > 0.3:  # 高い変動性
            return LoadTrend.SPIKING
        elif slope > 0.05:   # 有意な増加
            return LoadTrend.INCREASING
        elif slope < -0.05:  # 有意な減少
            return LoadTrend.DECREASING
        else:
            return LoadTrend.STABLE

    @trace("predict_load")
    def predict_load(self, minutes_ahead: int = 5) -> Dict[str, Any]:
        """
        将来の負荷を予測
        
        Args:
            minutes_ahead: 何分先の負荷を予測するか
            
        Returns:
            Dict: 予測負荷と信頼度の辞書
        """
        with self.lock:
            # 予測対象のメトリクス
            metrics_to_predict = [
                LoadMetricType.TASK_QUEUE_LENGTH.value,
                LoadMetricType.CPU_USAGE.value,
                LoadMetricType.MEMORY_USAGE.value,
                LoadMetricType.COMBINED_LOAD.value
            ]
            
            predictions = {}
            
            for metric in metrics_to_predict:
                history = self.metrics_history.get(metric, [])
                if len(history) < self.window_size:
                    predictions[metric] = {
                        "value": self._get_latest_value(metric),
                        "confidence": 0.5
                    }
                    continue
                
                # 最新のデータを抽出
                recent_values = [item["value"] for item in list(history)[-self.window_size:]]
                
                # 現在値
                current_value = recent_values[-1]
                
                # 変化率（一次微分）
                change_rate = 0
                if len(recent_values) >= 2:
                    change_rate = recent_values[-1] - recent_values[-2]
                
                # 変化の加速度（二次微分）
                acceleration = 0
                if len(recent_values) >= 3:
                    prev_change = recent_values[-2] - recent_values[-3]
                    acceleration = change_rate - prev_change
                
                # 周期性（自己相関）
                periodicity = 0
                if len(recent_values) >= 10:
                    try:
                        autocorr = np.correlate(recent_values, recent_values, mode='full')
                        autocorr = autocorr[len(autocorr)//2:]
                        periodicity = np.max(autocorr[1:]) / autocorr[0] if autocorr[0] > 0 else 0
                    except:
                        periodicity = 0
                
                # 予測モデルの適用
                prediction = (
                    current_value +
                    self.prediction_weights[0] * current_value +
                    self.prediction_weights[1] * change_rate * minutes_ahead +
                    self.prediction_weights[2] * acceleration * minutes_ahead * minutes_ahead / 2 +
                    self.prediction_weights[3] * periodicity * current_value
                )
                
                # 予測信頼度（履歴が長いほど、変動が少ないほど高い）
                history_factor = min(1.0, len(history) / self.history_size)
                stability_factor = 1.0 - min(1.0, np.std(recent_values) / (np.mean(recent_values) if np.mean(recent_values) > 0 else 1))
                confidence = (history_factor + stability_factor) / 2
                
                predictions[metric] = {
                    "value": max(0, prediction),  # 負の値は防止
                    "confidence": confidence
                }
            
            # 予測結果をログに記録
            logger.debug(f"{minutes_ahead}分後の負荷予測: {predictions[LoadMetricType.COMBINED_LOAD.value]}")
            
            return {
                "minutes_ahead": minutes_ahead,
                "predictions": predictions,
                "timestamp": time.time()
            }

    @trace("adjust_thresholds")
    def adjust_thresholds(self):
        """負荷閾値を自動調整"""
        with self.lock:
            for metric, history in self.metrics_history.items():
                if not history or metric not in self.thresholds:
                    continue
                
                # 最新の値を取得（直近のみでなく、ある程度の期間のデータを使用）
                values = [item["value"] for item in list(history)]
                if len(values) < 10:  # 最低10件のデータが必要
                    continue
                
                # 値の分布を分析
                values = np.array(values)
                p25 = np.percentile(values, 25)
                p50 = np.percentile(values, 50)
                p75 = np.percentile(values, 75)
                p90 = np.percentile(values, 90)
                
                # 新しい閾値の計算
                new_thresholds = {
                    "low": p25,
                    "medium": p50,
                    "high": p90
                }
                
                # 急激な変化を防ぐため、現在の閾値と新しい閾値の平均を取る（スムージング）
                current_thresholds = self.thresholds[metric]
                for level in ["low", "medium", "high"]:
                    self.thresholds[metric][level] = (
                        current_thresholds[level] * 0.7 +  # 現在の閾値の重み
                        new_thresholds[level] * 0.3        # 新しい閾値の重み
                    )
                
                # 閾値の順序を保証（low < medium < high）
                self.thresholds[metric]["low"] = min(
                    self.thresholds[metric]["low"],
                    self.thresholds[metric]["medium"] * 0.7
                )
                self.thresholds[metric]["high"] = max(
                    self.thresholds[metric]["high"],
                    self.thresholds[metric]["medium"] * 1.3
                )
                
                # 閾値履歴に追加
                self.threshold_history[metric].append({
                    "thresholds": dict(self.thresholds[metric]),
                    "timestamp": time.time()
                })
                
                # 履歴サイズの制限
                if len(self.threshold_history[metric]) > 100:
                    self.threshold_history[metric] = self.threshold_history[metric][-100:]
                
                logger.info(f"メトリクス '{metric}' の閾値を調整しました: {self.thresholds[metric]}")

    def get_thresholds(self) -> Dict[str, Dict[str, float]]:
        """
        現在の閾値設定を取得
        
        Returns:
            Dict: 閾値設定の辞書
        """
        with self.lock:
            return dict(self.thresholds)

    def set_thresholds(self, metric_type: str, low: float, medium: float, high: float):
        """
        閾値を手動で設定
        
        Args:
            metric_type: メトリクスタイプ
            low: 低負荷閾値
            medium: 中負荷閾値
            high: 高負荷閾値
        """
        with self.lock:
            if metric_type not in self.thresholds:
                logger.warning(f"未知のメトリクスタイプ: {metric_type}")
                return
            
            # 閾値の順序を検証
            if not (low < medium < high):
                logger.error(f"閾値の順序が無効です: low({low}) < medium({medium}) < high({high})が成立する必要があります")
                return
            
            # 閾値を更新
            self.thresholds[metric_type] = {
                "low": low,
                "medium": medium,
                "high": high
            }
            
            # 閾値履歴に追加
            self.threshold_history[metric_type].append({
                "thresholds": dict(self.thresholds[metric_type]),
                "timestamp": time.time(),
                "manual": True  # 手動設定を記録
            })
            
            logger.info(f"メトリクス '{metric_type}' の閾値を手動設定しました: {self.thresholds[metric_type]}")

    def get_metrics_history(self, metric_type: Optional[str] = None, limit: int = 100) -> Dict[str, List]:
        """
        メトリクス履歴を取得
        
        Args:
            metric_type: 取得するメトリクスタイプ（Noneの場合は全て）
            limit: 取得する最大レコード数
            
        Returns:
            Dict: メトリクス履歴の辞書
        """
        with self.lock:
            result = {}
            
            if metric_type:
                if metric_type in self.metrics_history:
                    result[metric_type] = list(self.metrics_history[metric_type])[-limit:]
            else:
                for metric, history in self.metrics_history.items():
                    result[metric] = list(history)[-limit:]
            
            return result

    def get_threshold_history(self, metric_type: Optional[str] = None) -> Dict[str, List]:
        """
        閾値履歴を取得
        
        Args:
            metric_type: 取得するメトリクスタイプ（Noneの場合は全て）
            
        Returns:
            Dict: 閾値履歴の辞書
        """
        with self.lock:
            result = {}
            
            if metric_type:
                if metric_type in self.threshold_history:
                    result[metric_type] = self.threshold_history[metric_type]
            else:
                result = dict(self.threshold_history)
            
            return result

    def _save_history(self):
        """メトリクス履歴をファイルに保存"""
        try:
            with self.lock:
                # 履歴データの準備
                data = {
                    "metrics_history": {k: list(v) for k, v in self.metrics_history.items()},
                    "threshold_history": self.threshold_history,
                    "execution_time_stats": {
                        k: list(v) if k == "recent_values" else v
                        for k, v in self.execution_time_stats.items()
                    },
                    "thresholds": self.thresholds,
                    "timestamp": time.time()
                }
                
                # JSONに変換して保存
                with open(self.save_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.debug(f"負荷メトリクス履歴を保存しました: {self.save_path}")
        except Exception as e:
            logger.error(f"負荷メトリクス履歴の保存に失敗しました: {str(e)}")

    def _load_history(self):
        """メトリクス履歴をファイルから読み込み"""
        try:
            if not os.path.exists(self.save_path):
                logger.debug(f"負荷メトリクス履歴ファイルが存在しません: {self.save_path}")
                return
            
            with open(self.save_path, 'r') as f:
                data = json.load(f)
            
            with self.lock:
                # 履歴データの読み込み
                for metric, history in data.get("metrics_history", {}).items():
                    self.metrics_history[metric] = deque(history, maxlen=self.history_size)
                
                self.threshold_history = data.get("threshold_history", self.threshold_history)
                
                # 実行時間統計の読み込み
                stats = data.get("execution_time_stats", {})
                for k, v in stats.items():
                    if k == "recent_values":
                        self.execution_time_stats[k] = deque(v, maxlen=100)
                    else:
                        self.execution_time_stats[k] = v
                
                self.thresholds = data.get("thresholds", self.thresholds)
                
                logger.info(f"負荷メトリクス履歴を読み込みました: {self.save_path}")
        except Exception as e:
            logger.error(f"負荷メトリクス履歴の読み込みに失敗しました: {str(e)}")


# グローバルインスタンス
_load_metrics = None

def get_load_metrics() -> LoadMetrics:
    """
    LoadMetricsのグローバルインスタンスを取得
    
    Returns:
        LoadMetrics: 負荷メトリクスのインスタンス
    """
    global _load_metrics
    if _load_metrics is None:
        _load_metrics = LoadMetrics()
    return _load_metrics

def start_load_monitoring(interval: int = 5):
    """
    負荷メトリクスの監視を開始
    
    Args:
        interval: 監視間隔（秒）
    """
    metrics = get_load_metrics()
    metrics.start_monitoring(interval)

def stop_load_monitoring():
    """負荷メトリクスの監視を停止"""
    metrics = get_load_metrics()
    metrics.stop_monitoring()

def get_current_load() -> Dict[str, Any]:
    """
    現在の負荷状態を取得
    
    Returns:
        Dict: 負荷メトリクスと状態の辞書
    """
    metrics = get_load_metrics()
    return metrics.get_current_load()

def predict_future_load(minutes_ahead: int = 5) -> Dict[str, Any]:
    """
    将来の負荷を予測
    
    Args:
        minutes_ahead: 何分先の負荷を予測するか
        
    Returns:
        Dict: 予測負荷と信頼度の辞書
    """
    metrics = get_load_metrics()
    return metrics.predict_load(minutes_ahead)

def update_queue_length(queue_length: int, agent_pool: str = "default") -> int:
    """
    タスクキュー長を更新するヘルパー関数
    
    Args:
        queue_length: タスクキューの長さ
        agent_pool: エージェントプール名
        
    Returns:
        int: 更新されたタスクキュー長
    """
    metrics = get_load_metrics()
    return metrics.update_task_queue_length(queue_length, agent_pool)

def record_task_execution_time(execution_time: float, task_type: str = "default", priority: TaskPriority = TaskPriority.MEDIUM) -> Dict[str, Any]:
    """
    タスク実行時間を記録するヘルパー関数
    
    Args:
        execution_time: タスク実行時間（秒）
        task_type: タスクの種類
        priority: タスクの優先度
        
    Returns:
        Dict: 更新された実行時間統計
    """
    metrics = get_load_metrics()
    return metrics.update_task_execution_time(execution_time, task_type, priority) 