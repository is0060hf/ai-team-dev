"""
OpenTelemetryのメトリクス機能を実装するモジュール。
既存のモニタリング機能とOpenTelemetryを連携するためのブリッジを提供します。
"""

import os
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Callable

# OpenTelemetryのメトリクス関連のインポート
try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    
    # プロトコルエクスポーター
    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        OTLP_METRICS_AVAILABLE = True
    except ImportError:
        OTLP_METRICS_AVAILABLE = False
    
    # Prometheusエクスポーター
    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        PROMETHEUS_AVAILABLE = True
    except ImportError:
        PROMETHEUS_AVAILABLE = False
    
    # コンソールエクスポーター
    try:
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        CONSOLE_METRICS_AVAILABLE = True
    except ImportError:
        CONSOLE_METRICS_AVAILABLE = False
    
    OTEL_METRICS_AVAILABLE = True
except ImportError:
    OTEL_METRICS_AVAILABLE = False
    OTLP_METRICS_AVAILABLE = False
    PROMETHEUS_AVAILABLE = False
    CONSOLE_METRICS_AVAILABLE = False

from utils.logger import get_structured_logger
from utils.config import config
from utils.monitoring import MetricType, MetricUnit, MetricsCollector, record_gauge, record_histogram, increment_counter

# ロガーの取得
logger = get_structured_logger("opentelemetry_metrics")

# グローバルのOpenTelemetryメーター
_meter_provider = None
_meter = None


def init_opentelemetry_metrics(
    service_name: str = "ai_team",
    resource_attributes: Optional[Dict[str, str]] = None,
    exporters: Optional[List[str]] = None,
    export_interval_millis: int = 30000
) -> bool:
    """
    OpenTelemetryメトリクスの初期化を行います

    Args:
        service_name: サービス名
        resource_attributes: リソース属性
        exporters: 使用するエクスポーター（"otlp", "prometheus", "console"）
        export_interval_millis: メトリクスのエクスポート間隔（ミリ秒）

    Returns:
        bool: 初期化に成功したらTrue
    """
    global _meter_provider, _meter
    
    if not OTEL_METRICS_AVAILABLE:
        logger.warning("OpenTelemetryメトリクスパッケージが見つかりません。")
        return False

    # 既に初期化済みの場合は何もしない
    if _meter_provider is not None:
        return True

    # リソース属性の設定
    attrs = {
        ResourceAttributes.SERVICE_NAME: service_name,
    }
    
    if resource_attributes:
        attrs.update(resource_attributes)
    
    resource = Resource.create(attrs)
    
    # メトリクスリーダーを準備
    readers = []
    
    if exporters:
        for exporter in exporters:
            if exporter.lower() == "otlp" and OTLP_METRICS_AVAILABLE:
                # OTLP (OpenTelemetry Protocol) エクスポーター
                otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:4318/v1/metrics")
                otlp_headers = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_HEADERS", "")
                
                headers = {}
                if otlp_headers:
                    for header_item in otlp_headers.split(","):
                        if "=" in header_item:
                            key, value = header_item.split("=", 1)
                            headers[key.strip()] = value.strip()
                
                otlp_exporter = OTLPMetricExporter(
                    endpoint=otlp_endpoint,
                    headers=headers
                )
                readers.append(
                    PeriodicExportingMetricReader(
                        exporter=otlp_exporter,
                        export_interval_millis=export_interval_millis
                    )
                )
                logger.info(f"OTLP Metrics Exporterを設定しました: {otlp_endpoint}")
            
            elif exporter.lower() == "prometheus" and PROMETHEUS_AVAILABLE:
                # Prometheusエクスポーター
                prometheus_port = int(os.environ.get("OTEL_EXPORTER_PROMETHEUS_PORT", "9464"))
                
                # Prometheusリーダーを追加
                readers.append(PrometheusMetricReader())
                logger.info(f"Prometheus Metrics Exporterを設定しました（ポート：{prometheus_port}）")
                # 注：PrometheusMetricReaderはHTTPサーバーを自動的に起動します
            
            elif exporter.lower() == "console" and CONSOLE_METRICS_AVAILABLE:
                # コンソールエクスポーター
                console_exporter = ConsoleMetricExporter()
                readers.append(
                    PeriodicExportingMetricReader(
                        exporter=console_exporter,
                        export_interval_millis=export_interval_millis
                    )
                )
                logger.info("Console Metrics Exporterを設定しました")
    
    # リーダーが未設定の場合はコンソールエクスポーターをデフォルトとして使用
    if not readers and CONSOLE_METRICS_AVAILABLE:
        console_exporter = ConsoleMetricExporter()
        readers.append(
            PeriodicExportingMetricReader(
                exporter=console_exporter,
                export_interval_millis=export_interval_millis
            )
        )
        logger.info("デフォルトのConsole Metrics Exporterを設定しました")
    
    # メーター・プロバイダーの設定
    if readers:
        _meter_provider = MeterProvider(
            resource=resource,
            metric_readers=readers
        )
        
        # グローバルメーター・プロバイダーとして設定
        metrics.set_meter_provider(_meter_provider)
        
        # メーターの取得
        _meter = metrics.get_meter(service_name)
        
        logger.info(f"OpenTelemetryメトリクスを初期化しました (service_name: {service_name})")
        return True
    else:
        logger.warning("利用可能なメトリクスエクスポーターがありません。OpenTelemetryメトリクスの初期化をスキップします。")
        return False


def get_meter():
    """
    OpenTelemetryメーターを取得します
    
    Returns:
        Meter: OpenTelemetryメーターインスタンス
    """
    global _meter
    
    if _meter is None:
        # 初期化されていない場合は初期化
        init_opentelemetry_metrics()
    
    return _meter


class OTelMetricsCollector:
    """
    既存のメトリクスコレクターとOpenTelemetryの統合を行うクラス
    """
    
    def __init__(self, service_name: str = "ai_team"):
        """
        Args:
            service_name: サービス名
        """
        self.service_name = service_name
        self.meter = None
        self.counters = {}
        self.gauges = {}
        self.histograms = {}
        
        if OTEL_METRICS_AVAILABLE:
            # 設定からエクスポーターを取得
            exporters = getattr(config, "OPENTELEMETRY_METRIC_EXPORTERS", ["console"])
            
            # リソース属性の設定
            resource_attributes = {
                "deployment.environment": getattr(config, "ENVIRONMENT", "development"),
            }
            
            # OpenTelemetryメトリクスを初期化
            if init_opentelemetry_metrics(
                service_name=service_name,
                resource_attributes=resource_attributes,
                exporters=exporters
            ):
                self.meter = get_meter()
                logger.info(f"OpenTelemetryメトリクスコレクターを初期化しました (service_name: {service_name})")
            else:
                logger.warning("OpenTelemetryメトリクスの初期化に失敗しました。標準のメトリクスコレクターを使用します。")
        else:
            logger.warning("OpenTelemetryメトリクスパッケージが見つかりません。標準のメトリクスコレクターを使用します。")
    
    def register_counter(self, name: str, description: str, unit: str = "1"):
        """
        カウンタータイプのメトリクスを登録します

        Args:
            name: メトリクス名
            description: メトリクスの説明
            unit: メトリクスの単位
        """
        if self.meter is None:
            return
        
        if name in self.counters:
            return
        
        counter = self.meter.create_counter(
            name=name,
            description=description,
            unit=unit
        )
        self.counters[name] = counter
        logger.debug(f"カウンターメトリクスを登録しました: {name}")
    
    def register_gauge(self, name: str, description: str, unit: str = "1"):
        """
        ゲージタイプのメトリクスを登録します

        Args:
            name: メトリクス名
            description: メトリクスの説明
            unit: メトリクスの単位
        """
        if self.meter is None:
            return
        
        if name in self.gauges:
            return
        
        # OpenTelemetryではGaugeの代わりにObservableGaugeを使用
        gauge = self.meter.create_observable_gauge(
            name=name,
            description=description,
            unit=unit,
            callbacks=[self._get_gauge_callback(name)]
        )
        self.gauges[name] = gauge
        logger.debug(f"ゲージメトリクスを登録しました: {name}")
    
    def register_histogram(self, name: str, description: str, unit: str = "1"):
        """
        ヒストグラムタイプのメトリクスを登録します

        Args:
            name: メトリクス名
            description: メトリクスの説明
            unit: メトリクスの単位
        """
        if self.meter is None:
            return
        
        if name in self.histograms:
            return
        
        histogram = self.meter.create_histogram(
            name=name,
            description=description,
            unit=unit
        )
        self.histograms[name] = histogram
        logger.debug(f"ヒストグラムメトリクスを登録しました: {name}")
    
    def increment_counter(self, name: str, value: float = 1.0, attributes: Optional[Dict[str, str]] = None):
        """
        カウンターメトリクスの値を増加させます

        Args:
            name: メトリクス名
            value: 増加値
            attributes: メトリクス属性
        """
        # 既存のインクリメント関数を呼び出し
        increment_counter(name, attributes, int(value))
        
        # OpenTelemetryカウンターを使用
        if self.meter is not None:
            if name not in self.counters:
                self.register_counter(name, f"Counter metric: {name}")
            
            counter = self.counters.get(name)
            if counter:
                counter.add(value, attributes or {})
    
    def record_gauge(self, name: str, value: float, attributes: Optional[Dict[str, str]] = None):
        """
        ゲージメトリクスの値を記録します

        Args:
            name: メトリクス名
            value: メトリクス値
            attributes: メトリクス属性
        """
        # 既存のゲージ記録関数を呼び出し
        record_gauge(name, value, attributes)
        
        # OpenTelemetryでは、ObservableGaugeはコールバックを通して値を取得するため、
        # ここでは直接記録せず、値を保存しておく
        if name not in self.gauges and self.meter is not None:
            self.register_gauge(name, f"Gauge metric: {name}")
    
    def record_histogram(self, name: str, value: float, attributes: Optional[Dict[str, str]] = None):
        """
        ヒストグラムメトリクスの値を記録します

        Args:
            name: メトリクス名
            value: メトリクス値
            attributes: メトリクス属性
        """
        # 既存のヒストグラム記録関数を呼び出し
        record_histogram(name, value, attributes)
        
        # OpenTelemetryヒストグラムを使用
        if self.meter is not None:
            if name not in self.histograms:
                self.register_histogram(name, f"Histogram metric: {name}")
            
            histogram = self.histograms.get(name)
            if histogram:
                histogram.record(value, attributes or {})
    
    def _get_gauge_callback(self, metric_name: str):
        """
        ObservableGauge用のコールバック関数を生成します

        Args:
            metric_name: メトリクス名

        Returns:
            Callable: コールバック関数
        """
        def callback(observer):
            from utils.monitoring import _get_metric_storage
            
            try:
                # 最新のメトリクス値を取得
                storage = _get_metric_storage()
                metrics = storage.get_metric_values(metric_name, limit=10)
                
                for metric in metrics:
                    observer.observe(
                        metric["value"],
                        metric.get("labels", {})
                    )
            except Exception as e:
                logger.error(f"ゲージメトリクスの取得中にエラーが発生しました: {str(e)}")
        
        return callback


def create_metrics_bridge(metrics_collector: MetricsCollector) -> OTelMetricsCollector:
    """
    既存のメトリクスコレクターとOpenTelemetryを連携するブリッジを作成します

    Args:
        metrics_collector: 既存のメトリクスコレクター

    Returns:
        OTelMetricsCollector: OpenTelemetryメトリクスコレクター
    """
    service_name = getattr(metrics_collector, "service_name", "ai_team")
    otel_collector = OTelMetricsCollector(service_name)
    
    # 既存のメトリクス定義を登録
    for collector_name, collector_func in metrics_collector.collectors.items():
        # メトリクス定義を取得
        definition = None
        for name, definition_obj in metrics_collector.storage.__dict__.get("metric_definitions", {}).items():
            if name == collector_name:
                definition = definition_obj
                break
        
        if definition:
            metric_type = definition.metric_type
            description = definition.description
            unit = str(definition.unit.value) if hasattr(definition.unit, "value") else "1"
            
            if metric_type == MetricType.COUNTER:
                otel_collector.register_counter(collector_name, description, unit)
            elif metric_type == MetricType.GAUGE:
                otel_collector.register_gauge(collector_name, description, unit)
            elif metric_type == MetricType.HISTOGRAM or metric_type == MetricType.SUMMARY:
                otel_collector.register_histogram(collector_name, description, unit)
    
    return otel_collector


# グローバルメトリクスコレクター（シングルトン）
_otel_metrics_collector = None


def get_otel_metrics_collector(service_name: str = "ai_team") -> OTelMetricsCollector:
    """
    OpenTelemetryメトリクスコレクターを取得します

    Args:
        service_name: サービス名

    Returns:
        OTelMetricsCollector: メトリクスコレクター
    """
    global _otel_metrics_collector
    
    if _otel_metrics_collector is None:
        _otel_metrics_collector = OTelMetricsCollector(service_name)
    
    return _otel_metrics_collector


def increment_otel_counter(name: str, value: float = 1.0, attributes: Optional[Dict[str, str]] = None):
    """
    OpenTelemetryカウンターメトリクスの値を増加させます

    Args:
        name: メトリクス名
        value: 増加値
        attributes: メトリクス属性
    """
    collector = get_otel_metrics_collector()
    collector.increment_counter(name, value, attributes)


def record_otel_gauge(name: str, value: float, attributes: Optional[Dict[str, str]] = None):
    """
    OpenTelemetryゲージメトリクスの値を記録します

    Args:
        name: メトリクス名
        value: メトリクス値
        attributes: メトリクス属性
    """
    collector = get_otel_metrics_collector()
    collector.record_gauge(name, value, attributes)


def record_otel_histogram(name: str, value: float, attributes: Optional[Dict[str, str]] = None):
    """
    OpenTelemetryヒストグラムメトリクスの値を記録します

    Args:
        name: メトリクス名
        value: メトリクス値
        attributes: メトリクス属性
    """
    collector = get_otel_metrics_collector()
    collector.record_histogram(name, value, attributes) 