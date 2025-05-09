"""
システムメトリクス収集モジュール。
システムリソースとパフォーマンスに関するメトリクスの収集を強化するための機能を提供します。
"""

import os
import sys
import time
import json
import threading
import platform
import socket
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

import psutil

from utils.logger import get_structured_logger
from utils.config import config
from utils.monitoring import (
    MetricsCollector, MetricType, MetricUnit, 
    record_gauge, record_histogram, increment_counter
)
from utils.tracing import trace, trace_span

# ロガーの取得
logger = get_structured_logger("system_metrics")


class SystemMetricsCollector:
    """
    システムメトリクスを収集するクラス
    
    Attributes:
        metrics_collector (MetricsCollector): メトリクスコレクター
        collection_interval (int): 収集間隔
        stop_event (threading.Event): 停止イベント
        collection_thread (threading.Thread): 収集スレッド
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        collection_interval: int = 60
    ):
        """
        初期化
        
        Args:
            metrics_collector: メトリクスコレクター
            collection_interval: 収集間隔（秒）
        """
        self.metrics_collector = metrics_collector
        self.collection_interval = collection_interval
        self.stop_event = threading.Event()
        self.collection_thread = None
        
        # システムメトリクス定義を登録
        self._register_system_metrics()
    
    def start(self):
        """
        システムメトリクス収集を開始
        """
        if self.collection_thread and self.collection_thread.is_alive():
            logger.warning("システムメトリクス収集は既に実行中です")
            return
        
        # 停止イベントをリセット
        self.stop_event.clear()
        
        # 収集スレッドを開始
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        
        logger.info(f"システムメトリクス収集を開始しました（間隔: {self.collection_interval}秒）")
    
    def stop(self):
        """
        システムメトリクス収集を停止
        """
        if not self.collection_thread or not self.collection_thread.is_alive():
            logger.warning("システムメトリクス収集は実行されていません")
            return
        
        # 停止イベントをセット
        self.stop_event.set()
        
        # スレッドの終了を待機
        self.collection_thread.join(timeout=10)
        self.collection_thread = None
        
        logger.info("システムメトリクス収集を停止しました")
    
    def _collection_loop(self):
        """メトリクス収集ループ"""
        logger.debug("システムメトリクス収集ループを開始します")
        
        try:
            # 初回のメトリクス収集
            self._collect_all_metrics()
            
            # 定期的な収集
            while not self.stop_event.is_set():
                # 次の収集まで待機
                if self.stop_event.wait(self.collection_interval):
                    break
                
                # メトリクスを収集
                self._collect_all_metrics()
        except Exception as e:
            logger.error(f"システムメトリクス収集中にエラーが発生しました: {str(e)}")
        finally:
            logger.debug("システムメトリクス収集ループを終了します")
    
    @trace
    def _collect_all_metrics(self):
        """すべてのシステムメトリクスを収集"""
        try:
            # CPU関連メトリクス
            self._collect_cpu_metrics()
            
            # メモリ関連メトリクス
            self._collect_memory_metrics()
            
            # ディスク関連メトリクス
            self._collect_disk_metrics()
            
            # ネットワーク関連メトリクス
            self._collect_network_metrics()
            
            # プロセス関連メトリクス
            self._collect_process_metrics()
            
            # サーバー負荷メトリクス
            self._collect_load_metrics()
            
            # Python関連メトリクス
            self._collect_python_metrics()
            
            logger.debug("システムメトリクスの収集が完了しました")
        except Exception as e:
            logger.error(f"システムメトリクス収集中にエラーが発生しました: {str(e)}")
    
    @trace
    def _collect_cpu_metrics(self):
        """CPU関連メトリクスを収集"""
        with trace_span("collect_cpu_metrics"):
            # CPU使用率（システム全体）
            cpu_percent = psutil.cpu_percent(interval=1)
            record_gauge("system_cpu_usage_percent", cpu_percent, {"source": "system_metrics"})
            
            # CPU使用率（コアごと）
            per_cpu_percent = psutil.cpu_percent(interval=0, percpu=True)
            for i, percent in enumerate(per_cpu_percent):
                record_gauge("system_cpu_core_usage_percent", percent, {"core": str(i), "source": "system_metrics"})
            
            # CPU負荷（過去1分、5分、15分）
            if hasattr(psutil, "getloadavg"):
                load1, load5, load15 = psutil.getloadavg()
                record_gauge("system_load_avg_1m", load1, {"source": "system_metrics"})
                record_gauge("system_load_avg_5m", load5, {"source": "system_metrics"})
                record_gauge("system_load_avg_15m", load15, {"source": "system_metrics"})
            
            # CPU周波数
            if hasattr(psutil, "cpu_freq") and psutil.cpu_freq():
                freq = psutil.cpu_freq()
                if freq.current:
                    record_gauge("system_cpu_freq_mhz", freq.current, {"source": "system_metrics"})
            
            # コンテキストスイッチ数
            ctx_switches = psutil.cpu_stats().ctx_switches
            increment_counter("system_context_switches_total", {"source": "system_metrics"}, ctx_switches)
            
            # 割り込み数
            interrupts = psutil.cpu_stats().interrupts
            increment_counter("system_interrupts_total", {"source": "system_metrics"}, interrupts)
            
            # システムコール数
            if hasattr(psutil.cpu_stats(), "syscalls"):
                syscalls = psutil.cpu_stats().syscalls
                increment_counter("system_syscalls_total", {"source": "system_metrics"}, syscalls)
    
    @trace
    def _collect_memory_metrics(self):
        """メモリ関連メトリクスを収集"""
        with trace_span("collect_memory_metrics"):
            # 仮想メモリ情報
            virtual_mem = psutil.virtual_memory()
            
            # 使用率
            record_gauge("system_memory_usage_percent", virtual_mem.percent, {"source": "system_metrics"})
            
            # 総メモリ容量
            record_gauge("system_memory_total_bytes", virtual_mem.total, {"source": "system_metrics"})
            
            # 使用中メモリ
            record_gauge("system_memory_used_bytes", virtual_mem.used, {"source": "system_metrics"})
            
            # 空きメモリ
            record_gauge("system_memory_free_bytes", virtual_mem.available, {"source": "system_metrics"})
            
            # スワップ情報
            swap = psutil.swap_memory()
            
            # スワップ使用率
            record_gauge("system_swap_usage_percent", swap.percent, {"source": "system_metrics"})
            
            # 総スワップ容量
            record_gauge("system_swap_total_bytes", swap.total, {"source": "system_metrics"})
            
            # 使用中スワップ
            record_gauge("system_swap_used_bytes", swap.used, {"source": "system_metrics"})
            
            # 空きスワップ
            record_gauge("system_swap_free_bytes", swap.free, {"source": "system_metrics"})
    
    @trace
    def _collect_disk_metrics(self):
        """ディスク関連メトリクスを収集"""
        with trace_span("collect_disk_metrics"):
            # 各マウントポイントについて収集
            for part in psutil.disk_partitions(all=False):
                if not part.mountpoint:
                    continue
                
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    
                    # ディスク使用率
                    record_gauge(
                        "system_disk_usage_percent", 
                        usage.percent, 
                        {"mountpoint": part.mountpoint, "source": "system_metrics"}
                    )
                    
                    # 総ディスク容量
                    record_gauge(
                        "system_disk_total_bytes", 
                        usage.total, 
                        {"mountpoint": part.mountpoint, "source": "system_metrics"}
                    )
                    
                    # 使用中ディスク
                    record_gauge(
                        "system_disk_used_bytes", 
                        usage.used, 
                        {"mountpoint": part.mountpoint, "source": "system_metrics"}
                    )
                    
                    # 空きディスク
                    record_gauge(
                        "system_disk_free_bytes", 
                        usage.free, 
                        {"mountpoint": part.mountpoint, "source": "system_metrics"}
                    )
                except PermissionError:
                    # アクセス権がない場合はスキップ
                    continue
                except FileNotFoundError:
                    # マウントポイントが見つからない場合はスキップ
                    continue
            
            # ディスクIO統計
            try:
                disk_io = psutil.disk_io_counters()
                
                if disk_io:
                    # 読み込みバイト数
                    increment_counter(
                        "system_disk_read_bytes_total", 
                        {"source": "system_metrics"}, 
                        disk_io.read_bytes
                    )
                    
                    # 書き込みバイト数
                    increment_counter(
                        "system_disk_write_bytes_total", 
                        {"source": "system_metrics"}, 
                        disk_io.write_bytes
                    )
                    
                    # 読み込み回数
                    increment_counter(
                        "system_disk_read_count_total", 
                        {"source": "system_metrics"}, 
                        disk_io.read_count
                    )
                    
                    # 書き込み回数
                    increment_counter(
                        "system_disk_write_count_total", 
                        {"source": "system_metrics"}, 
                        disk_io.write_count
                    )
            except (AttributeError, IOError, NotImplementedError):
                # プラットフォームによってはディスクIO統計が利用できない場合がある
                pass
    
    @trace
    def _collect_network_metrics(self):
        """ネットワーク関連メトリクスを収集"""
        with trace_span("collect_network_metrics"):
            # ネットワークIO統計
            try:
                net_io = psutil.net_io_counters()
                
                if net_io:
                    # 送信バイト数
                    increment_counter(
                        "system_network_sent_bytes_total", 
                        {"source": "system_metrics"}, 
                        net_io.bytes_sent
                    )
                    
                    # 受信バイト数
                    increment_counter(
                        "system_network_recv_bytes_total", 
                        {"source": "system_metrics"}, 
                        net_io.bytes_recv
                    )
                    
                    # 送信パケット数
                    increment_counter(
                        "system_network_sent_packets_total", 
                        {"source": "system_metrics"}, 
                        net_io.packets_sent
                    )
                    
                    # 受信パケット数
                    increment_counter(
                        "system_network_recv_packets_total", 
                        {"source": "system_metrics"}, 
                        net_io.packets_recv
                    )
                    
                    # エラー数
                    if hasattr(net_io, "errin") and hasattr(net_io, "errout"):
                        increment_counter(
                            "system_network_err_in_total", 
                            {"source": "system_metrics"}, 
                            net_io.errin
                        )
                        increment_counter(
                            "system_network_err_out_total", 
                            {"source": "system_metrics"}, 
                            net_io.errout
                        )
                    
                    # ドロップ数
                    if hasattr(net_io, "dropin") and hasattr(net_io, "dropout"):
                        increment_counter(
                            "system_network_drop_in_total", 
                            {"source": "system_metrics"}, 
                            net_io.dropin
                        )
                        increment_counter(
                            "system_network_drop_out_total", 
                            {"source": "system_metrics"}, 
                            net_io.dropout
                        )
            
            except (AttributeError, IOError, NotImplementedError):
                # プラットフォームによってはネットワークIO統計が利用できない場合がある
                pass
            
            # ネットワーク接続数
            try:
                connections = psutil.net_connections()
                
                # 状態別の接続数をカウント
                conn_stats = {}
                for conn in connections:
                    status = conn.status if hasattr(conn, "status") else "UNKNOWN"
                    if status in conn_stats:
                        conn_stats[status] += 1
                    else:
                        conn_stats[status] = 1
                
                # 各状態の接続数を記録
                for status, count in conn_stats.items():
                    record_gauge(
                        "system_network_connections", 
                        count, 
                        {"status": status, "source": "system_metrics"}
                    )
            
            except (AttributeError, IOError, NotImplementedError, PermissionError):
                # 権限または実装の問題で接続情報が取得できない場合がある
                pass
    
    @trace
    def _collect_process_metrics(self):
        """プロセス関連メトリクスを収集"""
        with trace_span("collect_process_metrics"):
            # 現在のプロセス数
            process_count = len(psutil.pids())
            record_gauge("system_process_count", process_count, {"source": "system_metrics"})
            
            # 自プロセスの情報
            try:
                current_process = psutil.Process()
                
                # CPU使用率
                with trace_span("process_cpu_percent"):
                    proc_cpu = current_process.cpu_percent(interval=0.1)
                    record_gauge("process_cpu_usage_percent", proc_cpu, {"source": "system_metrics"})
                
                # メモリ使用率
                with trace_span("process_memory_info"):
                    proc_mem = current_process.memory_info()
                    record_gauge("process_memory_rss_bytes", proc_mem.rss, {"source": "system_metrics"})
                    record_gauge("process_memory_vms_bytes", proc_mem.vms, {"source": "system_metrics"})
                
                # オープンファイル数
                with trace_span("process_open_files"):
                    try:
                        open_files = current_process.open_files()
                        record_gauge("process_open_files", len(open_files), {"source": "system_metrics"})
                    except (AttributeError, IOError, NotImplementedError, PermissionError):
                        pass
                
                # スレッド数
                with trace_span("process_threads"):
                    threads = current_process.threads()
                    record_gauge("process_thread_count", len(threads), {"source": "system_metrics"})
                
                # コネクション数
                with trace_span("process_connections"):
                    try:
                        connections = current_process.connections()
                        record_gauge("process_connection_count", len(connections), {"source": "system_metrics"})
                    except (AttributeError, IOError, NotImplementedError, PermissionError):
                        pass
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                logger.warning("プロセス情報の収集に失敗しました")
    
    @trace
    def _collect_load_metrics(self):
        """サーバー負荷メトリクスを収集"""
        with trace_span("collect_load_metrics"):
            # ロードアベレージ（Unix系のみ）
            if hasattr(os, "getloadavg"):
                try:
                    load1, load5, load15 = os.getloadavg()
                    record_gauge("system_load_average_1m", load1, {"source": "system_metrics"})
                    record_gauge("system_load_average_5m", load5, {"source": "system_metrics"})
                    record_gauge("system_load_average_15m", load15, {"source": "system_metrics"})
                except (AttributeError, IOError, NotImplementedError):
                    pass
            
            # 起動時間
            try:
                boot_time = psutil.boot_time()
                uptime = time.time() - boot_time
                record_gauge("system_uptime_seconds", uptime, {"source": "system_metrics"})
            except (AttributeError, IOError, NotImplementedError):
                pass
            
            # ユーザー数
            try:
                users = psutil.users()
                record_gauge("system_user_count", len(users), {"source": "system_metrics"})
            except (AttributeError, IOError, NotImplementedError):
                pass
    
    @trace
    def _collect_python_metrics(self):
        """Python関連メトリクスを収集"""
        with trace_span("collect_python_metrics"):
            import gc
            
            # GCカウンター
            gc_counts = gc.get_count()
            for i, count in enumerate(gc_counts):
                record_gauge("python_gc_collection_count", count, {"generation": str(i), "source": "system_metrics"})
            
            # GCしきい値
            gc_threshold = gc.get_threshold()
            for i, threshold in enumerate(gc_threshold):
                record_gauge("python_gc_threshold", threshold, {"generation": str(i), "source": "system_metrics"})
            
            # GCオブジェクト数
            try:
                gc_objects = len(gc.get_objects())
                record_gauge("python_gc_object_count", gc_objects, {"source": "system_metrics"})
            except (AttributeError, IOError, NotImplementedError):
                pass
            
            # スレッド数
            import threading
            record_gauge("python_thread_count", threading.active_count(), {"source": "system_metrics"})
    
    def _register_system_metrics(self):
        """システムメトリクス定義を登録"""
        # CPU関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_cpu_usage_percent",
            description="システム全体のCPU使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_cpu_core_usage_percent",
            description="各CPUコアの使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["core", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_load_avg_1m",
            description="1分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_load_avg_5m",
            description="5分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_load_avg_15m",
            description="15分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_cpu_freq_mhz",
            description="CPU周波数（MHz）",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_context_switches_total",
            description="コンテキストスイッチの総数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_interrupts_total",
            description="割り込みの総数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_syscalls_total",
            description="システムコールの総数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        # メモリ関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_memory_usage_percent",
            description="メモリ使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_memory_total_bytes",
            description="総メモリ容量",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_memory_used_bytes",
            description="使用中メモリ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_memory_free_bytes",
            description="空きメモリ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_swap_usage_percent",
            description="スワップメモリ使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_swap_total_bytes",
            description="総スワップメモリ容量",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_swap_used_bytes",
            description="使用中スワップメモリ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_swap_free_bytes",
            description="空きスワップメモリ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        # ディスク関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_disk_usage_percent",
            description="ディスク使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["mountpoint", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_total_bytes",
            description="総ディスク容量",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["mountpoint", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_used_bytes",
            description="使用中ディスク容量",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["mountpoint", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_free_bytes",
            description="空きディスク容量",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["mountpoint", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_read_bytes_total",
            description="ディスク読み込みバイト数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_write_bytes_total",
            description="ディスク書き込みバイト数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_read_count_total",
            description="ディスク読み込み回数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_disk_write_count_total",
            description="ディスク書き込み回数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        # ネットワーク関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_network_sent_bytes_total",
            description="送信バイト数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_recv_bytes_total",
            description="受信バイト数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_sent_packets_total",
            description="送信パケット数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_recv_packets_total",
            description="受信パケット数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_err_in_total",
            description="受信エラー数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_err_out_total",
            description="送信エラー数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_drop_in_total",
            description="受信パケットドロップ数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_drop_out_total",
            description="送信パケットドロップ数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_network_connections",
            description="ネットワーク接続数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["status", "source"]
        )
        
        # プロセス関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_process_count",
            description="システム上のプロセス数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_cpu_usage_percent",
            description="現在のプロセスのCPU使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_memory_rss_bytes",
            description="現在のプロセスの常駐メモリサイズ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_memory_vms_bytes",
            description="現在のプロセスの仮想メモリサイズ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_open_files",
            description="現在のプロセスのオープンファイル数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_thread_count",
            description="現在のプロセスのスレッド数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="process_connection_count",
            description="現在のプロセスのネットワーク接続数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        # サーバー負荷メトリクス
        self.metrics_collector.define_custom_metric(
            name="system_load_average_1m",
            description="1分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_load_average_5m",
            description="5分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_load_average_15m",
            description="15分間のロードアベレージ",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.CUSTOM,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_uptime_seconds",
            description="システム起動からの経過時間（秒）",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.SECONDS,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="system_user_count",
            description="ログインユーザー数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        # Python関連メトリクス
        self.metrics_collector.define_custom_metric(
            name="python_gc_collection_count",
            description="Pythonガベージコレクションカウント",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["generation", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="python_gc_threshold",
            description="Pythonガベージコレクションしきい値",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["generation", "source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="python_gc_object_count",
            description="Pythonガベージコレクション対象オブジェクト数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )
        
        self.metrics_collector.define_custom_metric(
            name="python_thread_count",
            description="Pythonスレッド数",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.COUNT,
            labels=["source"]
        )


# シングルトンインスタンス
_system_metrics_collector = None


def get_system_metrics_collector() -> SystemMetricsCollector:
    """
    SystemMetricsCollectorのシングルトンインスタンスを取得
    
    Returns:
        SystemMetricsCollector: システムメトリクスコレクター
    """
    global _system_metrics_collector
    
    if _system_metrics_collector is None:
        from utils.monitoring import metrics_collector
        collection_interval = getattr(config, "SYSTEM_METRICS_INTERVAL", 60)
        
        _system_metrics_collector = SystemMetricsCollector(
            metrics_collector=metrics_collector,
            collection_interval=collection_interval
        )
    
    return _system_metrics_collector


def start_system_metrics_collection():
    """
    システムメトリクス収集を開始する便利関数
    """
    collector = get_system_metrics_collector()
    collector.start()


def stop_system_metrics_collection():
    """
    システムメトリクス収集を停止する便利関数
    """
    global _system_metrics_collector
    
    if _system_metrics_collector is not None:
        _system_metrics_collector.stop() 