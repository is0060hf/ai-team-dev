"""
Prometheusエクスポーターモジュール。
システムメトリクスをPrometheusで利用可能な形式で公開するための機能を提供します。
"""

import time
import threading
from typing import Dict, Any, Optional, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import logging

from utils.logger import get_structured_logger
from utils.config import config
from utils.monitoring import PrometheusMetricExporter, MetricType, _get_metric_storage
from utils.tracing import trace, trace_span

# ロガーの取得
logger = get_structured_logger("prometheus_exporter")


class PrometheusEndpoint:
    """
    Prometheusエンドポイントを提供するクラス
    
    Attributes:
        host (str): バインドするホスト
        port (int): リッスンするポート
        path (str): メトリクスを提供するパス
        server (HTTPServer): HTTPサーバーインスタンス
        server_thread (threading.Thread): サーバースレッド
        exporter (PrometheusMetricExporter): メトリクスエクスポーター
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9090,
        path: str = "/metrics",
        collect_interval: int = 15
    ):
        """
        初期化
        
        Args:
            host: バインドするホスト
            port: リッスンするポート
            path: メトリクスを提供するパス
            collect_interval: メトリクス収集間隔（秒）
        """
        self.host = host
        self.port = port
        self.path = path
        self.collect_interval = collect_interval
        self.server = None
        self.server_thread = None
        self.stopping = False
        
        # メトリクスストレージからエクスポーターを作成
        storage = _get_metric_storage()
        self.exporter = PrometheusMetricExporter(storage)
        
        # キャッシュしたメトリクス文字列
        self._metrics_cache = ""
        self._last_collect_time = 0
        self._cache_lock = threading.Lock()
    
    def start(self):
        """
        Prometheusエンドポイントを開始
        """
        if self.server is not None:
            logger.warning("Prometheusエンドポイントは既に実行中です")
            return
        
        # リクエストハンドラの設定
        endpoint = self  # self参照を渡す
        
        class PrometheusHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == endpoint.path:
                    # メトリクスの取得（キャッシュから）
                    metrics = endpoint.get_metrics()
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", str(len(metrics)))
                    self.end_headers()
                    self.wfile.write(metrics.encode("utf-8"))
                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"Not Found")
            
            # ログ出力を抑制
            def log_message(self, format, *args):
                if config.PROMETHEUS_ACCESS_LOG:
                    logger.debug(f"Prometheus: {format % args}")
        
        try:
            # HTTPサーバーを作成
            self.server = HTTPServer((self.host, self.port), PrometheusHandler)
            
            # サーバースレッドを開始
            self.stopping = False
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self.server_thread.start()
            
            logger.info(f"Prometheusエンドポイントを開始しました - http://{self.host}:{self.port}{self.path}")
            return True
        except Exception as e:
            logger.error(f"Prometheusエンドポイントの開始に失敗しました: {str(e)}")
            return False
    
    def stop(self):
        """
        Prometheusエンドポイントを停止
        """
        if self.server is None:
            logger.warning("Prometheusエンドポイントは実行されていません")
            return
        
        # サーバーを停止
        self.stopping = True
        self.server.shutdown()
        self.server.server_close()
        
        # スレッドの終了を待機
        if self.server_thread:
            self.server_thread.join(timeout=5)
        
        self.server = None
        self.server_thread = None
        
        logger.info("Prometheusエンドポイントを停止しました")
    
    @trace
    def get_metrics(self) -> str:
        """
        Prometheusフォーマットのメトリクスを取得
        
        Returns:
            str: Prometheusフォーマットのメトリクス
        """
        with self._cache_lock:
            now = time.time()
            
            # キャッシュ有効期限をチェック
            if now - self._last_collect_time < self.collect_interval and self._metrics_cache:
                return self._metrics_cache
            
            # メトリクスを生成
            with trace_span("generate_prometheus_metrics"):
                metrics = self.exporter.generate_prometheus_metrics()
            
            # 内部メトリクスを追加
            metrics += self._get_internal_metrics()
            
            # キャッシュを更新
            self._metrics_cache = metrics
            self._last_collect_time = now
            
            return metrics
    
    def _run_server(self):
        """サーバーを実行（スレッド内）"""
        try:
            logger.debug("Prometheusエンドポイントサーバーを開始します")
            self.server.serve_forever()
        except Exception as e:
            if not self.stopping:
                logger.error(f"Prometheusサーバーエラー: {str(e)}")
        finally:
            logger.debug("Prometheusエンドポイントサーバーを終了します")
    
    def _get_internal_metrics(self) -> str:
        """
        内部メトリクスを生成
        
        Returns:
            str: Prometheusフォーマットの内部メトリクス
        """
        lines = []
        
        # サーバー起動時間
        uptime = time.time() - self._last_collect_time
        lines.append("# HELP prometheus_exporter_uptime_seconds Uptime of the Prometheus exporter")
        lines.append("# TYPE prometheus_exporter_uptime_seconds gauge")
        lines.append(f"prometheus_exporter_uptime_seconds {uptime}")
        
        # サーバー情報
        lines.append("# HELP prometheus_exporter_info Information about the Prometheus exporter")
        lines.append("# TYPE prometheus_exporter_info gauge")
        lines.append(f'prometheus_exporter_info{{version="{config.VERSION}"}} 1')
        
        # ホスト情報
        hostname = socket.gethostname()
        lines.append("# HELP prometheus_exporter_host_info Information about the host")
        lines.append("# TYPE prometheus_exporter_host_info gauge")
        lines.append(f'prometheus_exporter_host_info{{hostname="{hostname}"}} 1')
        
        # メトリクス収集時間
        collect_time = time.time() - self._last_collect_time
        lines.append("# HELP prometheus_exporter_collect_seconds Time spent collecting metrics")
        lines.append("# TYPE prometheus_exporter_collect_seconds gauge")
        lines.append(f"prometheus_exporter_collect_seconds {collect_time}")
        
        return "\n".join(lines)


# シングルトンインスタンス
_prometheus_endpoint = None


def get_prometheus_endpoint() -> PrometheusEndpoint:
    """
    PrometheusEndpointのシングルトンインスタンスを取得
    
    Returns:
        PrometheusEndpoint: Prometheusエンドポイントインスタンス
    """
    global _prometheus_endpoint
    
    if _prometheus_endpoint is None:
        host = getattr(config, "PROMETHEUS_HOST", "0.0.0.0")
        port = getattr(config, "PROMETHEUS_PORT", 9090)
        path = getattr(config, "PROMETHEUS_PATH", "/metrics")
        collect_interval = getattr(config, "PROMETHEUS_COLLECT_INTERVAL", 15)
        
        _prometheus_endpoint = PrometheusEndpoint(
            host=host,
            port=port,
            path=path,
            collect_interval=collect_interval
        )
    
    return _prometheus_endpoint


def start_prometheus_endpoint():
    """
    Prometheusエンドポイントを開始する便利関数
    """
    endpoint = get_prometheus_endpoint()
    endpoint.start()


def stop_prometheus_endpoint():
    """
    Prometheusエンドポイントを停止する便利関数
    """
    global _prometheus_endpoint
    
    if _prometheus_endpoint is not None:
        _prometheus_endpoint.stop()
        _prometheus_endpoint = None 