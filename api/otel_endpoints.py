"""
OpenTelemetryエンドポイントモジュール。
FastAPIおよびFlaskアプリケーション向けのOpenTelemetryエンドポイントを提供します。
"""

import os
import json
import time
from typing import Dict, Any, Optional, List, Union, Callable

from utils.logger import get_structured_logger
from utils.config import config

# ロガーの取得
logger = get_structured_logger("otel_endpoints")


def register_opentelemetry_endpoints_fastapi(app):
    """
    FastAPIアプリケーションにOpenTelemetryエンドポイントを登録します
    
    Args:
        app: FastAPIアプリケーション
    """
    from fastapi import APIRouter, Response, Depends, HTTPException
    
    # OpenTelemetryエンドポイント用のルーター
    otel_router = APIRouter(prefix="/otel", tags=["opentelemetry"])
    
    # トレースエンドポイント
    @otel_router.post("/v1/traces", status_code=200)
    async def receive_traces(request: dict):
        """
        OpenTelemetryプロトコル形式のトレースを受信するエンドポイント
        
        Args:
            request: OTLPフォーマットのトレースデータ
            
        Returns:
            dict: 処理結果
        """
        try:
            # トレースデータの処理
            from utils.trace_storage import get_trace_storage
            
            # バッファしておくトレースストレージを取得
            trace_storage = get_trace_storage()
            
            # トレースデータを内部形式に変換して保存
            _process_otlp_traces(request, trace_storage)
            
            return {"status": "success", "message": "Traces received"}
        except Exception as e:
            logger.error(f"トレースデータの処理中にエラーが発生しました: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # メトリクスエンドポイント
    @otel_router.post("/v1/metrics", status_code=200)
    async def receive_metrics(request: dict):
        """
        OpenTelemetryプロトコル形式のメトリクスを受信するエンドポイント
        
        Args:
            request: OTLPフォーマットのメトリクスデータ
            
        Returns:
            dict: 処理結果
        """
        try:
            # メトリクスデータの処理
            from utils.monitoring import _get_metric_storage
            
            # メトリクスストレージを取得
            metric_storage = _get_metric_storage()
            
            # メトリクスデータを内部形式に変換して保存
            _process_otlp_metrics(request, metric_storage)
            
            return {"status": "success", "message": "Metrics received"}
        except Exception as e:
            logger.error(f"メトリクスデータの処理中にエラーが発生しました: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Prometheusエンドポイント（メトリクス）
    @otel_router.get("/metrics", status_code=200)
    async def prometheus_metrics():
        """
        Prometheusフォーマットのメトリクスを提供するエンドポイント
        
        Returns:
            Response: Prometheusフォーマットのメトリクス
        """
        try:
            from utils.monitoring import prometheus_exporter
            
            # Prometheusフォーマットのメトリクスを生成
            metrics_text = prometheus_exporter.generate_prometheus_metrics()
            
            # OpenTelemetryのPrometheusBridgeが利用可能か確認
            try:
                from opentelemetry.exporter.prometheus import PrometheusMetricReader
                from opentelemetry.sdk.metrics import MeterProvider
                from opentelemetry.sdk.resources import Resource
                
                # OpenTelemetryからのメトリクスも取得
                # 注：この実装はOpenTelemetryが内部的に起動するPrometheusサーバーと
                # 競合する可能性があるため、設定による切り替えが必要
                if getattr(config, "USE_OTEL_PROMETHEUS_BRIDGE", False):
                    try:
                        # Prometheusサーバーからメトリクスをスクレイプしてマージする実装が必要
                        import requests
                        otel_prometheus_port = int(os.environ.get("OTEL_EXPORTER_PROMETHEUS_PORT", "9464"))
                        otel_metrics_response = requests.get(f"http://localhost:{otel_prometheus_port}/metrics")
                        if otel_metrics_response.status_code == 200:
                            # 両方のメトリクスを結合
                            metrics_text = metrics_text + "\n" + otel_metrics_response.text
                    except Exception as e:
                        logger.warning(f"OpenTelemetry Prometheusメトリクスの取得に失敗しました: {str(e)}")
            except ImportError:
                # OpenTelemetryのPrometheusサポートが利用できない場合は標準の実装のみ使用
                pass
            
            return Response(content=metrics_text, media_type="text/plain")
        except Exception as e:
            logger.error(f"Prometheusメトリクスの生成中にエラーが発生しました: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ヘルスチェックエンドポイント
    @otel_router.get("/health", status_code=200)
    async def health_check():
        """
        OpenTelemetryヘルスチェックエンドポイント
        
        Returns:
            dict: ヘルスステータス
        """
        return {
            "status": "up",
            "timestamp": time.time(),
            "components": {
                "tracing": {"status": "up"},
                "metrics": {"status": "up"}
            }
        }
    
    # ルーターをアプリケーションに登録
    app.include_router(otel_router)


def register_opentelemetry_endpoints_flask(app):
    """
    FlaskアプリケーションにOpenTelemetryエンドポイントを登録します
    
    Args:
        app: Flaskアプリケーション
    """
    from flask import request, jsonify, Response
    
    # トレースエンドポイント
    @app.route("/otel/v1/traces", methods=["POST"])
    def receive_traces():
        """
        OpenTelemetryプロトコル形式のトレースを受信するエンドポイント
        """
        try:
            # トレースデータの処理
            from utils.trace_storage import get_trace_storage
            
            # バッファしておくトレースストレージを取得
            trace_storage = get_trace_storage()
            
            # トレースデータを内部形式に変換して保存
            _process_otlp_traces(request.json, trace_storage)
            
            return jsonify({"status": "success", "message": "Traces received"})
        except Exception as e:
            logger.error(f"トレースデータの処理中にエラーが発生しました: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # メトリクスエンドポイント
    @app.route("/otel/v1/metrics", methods=["POST"])
    def receive_metrics():
        """
        OpenTelemetryプロトコル形式のメトリクスを受信するエンドポイント
        """
        try:
            # メトリクスデータの処理
            from utils.monitoring import _get_metric_storage
            
            # メトリクスストレージを取得
            metric_storage = _get_metric_storage()
            
            # メトリクスデータを内部形式に変換して保存
            _process_otlp_metrics(request.json, metric_storage)
            
            return jsonify({"status": "success", "message": "Metrics received"})
        except Exception as e:
            logger.error(f"メトリクスデータの処理中にエラーが発生しました: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # Prometheusエンドポイント（メトリクス）
    @app.route("/otel/metrics", methods=["GET"])
    def prometheus_metrics():
        """
        Prometheusフォーマットのメトリクスを提供するエンドポイント
        """
        try:
            from utils.monitoring import prometheus_exporter
            
            # Prometheusフォーマットのメトリクスを生成
            metrics_text = prometheus_exporter.generate_prometheus_metrics()
            
            # OpenTelemetryのPrometheusBridgeが利用可能か確認
            try:
                from opentelemetry.exporter.prometheus import PrometheusMetricReader
                
                # OpenTelemetryからのメトリクスも取得
                if getattr(config, "USE_OTEL_PROMETHEUS_BRIDGE", False):
                    try:
                        # Prometheusサーバーからメトリクスをスクレイプしてマージする実装が必要
                        import requests
                        otel_prometheus_port = int(os.environ.get("OTEL_EXPORTER_PROMETHEUS_PORT", "9464"))
                        otel_metrics_response = requests.get(f"http://localhost:{otel_prometheus_port}/metrics")
                        if otel_metrics_response.status_code == 200:
                            # 両方のメトリクスを結合
                            metrics_text = metrics_text + "\n" + otel_metrics_response.text
                    except Exception as e:
                        logger.warning(f"OpenTelemetry Prometheusメトリクスの取得に失敗しました: {str(e)}")
            except ImportError:
                # OpenTelemetryのPrometheusサポートが利用できない場合は標準の実装のみ使用
                pass
            
            return Response(metrics_text, mimetype="text/plain")
        except Exception as e:
            logger.error(f"Prometheusメトリクスの生成中にエラーが発生しました: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # ヘルスチェックエンドポイント
    @app.route("/otel/health", methods=["GET"])
    def health_check():
        """
        OpenTelemetryヘルスチェックエンドポイント
        """
        return jsonify({
            "status": "up",
            "timestamp": time.time(),
            "components": {
                "tracing": {"status": "up"},
                "metrics": {"status": "up"}
            }
        })


def _process_otlp_traces(data: Dict[str, Any], trace_storage):
    """
    OTLPトレースデータを処理して内部形式に変換し、保存します
    
    Args:
        data: OTLPフォーマットのトレースデータ
        trace_storage: トレースストレージ
    """
    # resourceSpans（OTLPv0.7+）またはresourceSpansとinstrumentationLibrarySpans（旧バージョン）をチェック
    resource_spans_key = next((key for key in ["resourceSpans", "resource_spans", "resource.spans"] if key in data), None)
    
    if not resource_spans_key:
        logger.warning("有効なOTLPトレースデータが見つかりません")
        return
    
    for resource_span in data[resource_spans_key]:
        # リソース情報の取得
        resource_key = next((key for key in ["resource", "resources"] if key in resource_span), None)
        resource = resource_span.get(resource_key, {})
        
        # リソース属性の取得
        resource_attributes = {}
        if "attributes" in resource:
            for attr in resource.get("attributes", []):
                if "key" in attr and "value" in attr:
                    value = _extract_otel_attribute_value(attr["value"])
                    if value is not None:
                        resource_attributes[attr["key"]] = value
        
        # サービス名の取得
        service_name = resource_attributes.get("service.name", "unknown")
        
        # スパン情報の取得（新旧両フォーマットに対応）
        span_list = []
        for spans_container_key in ["scopeSpans", "scope_spans", "instrumentationLibrarySpans", "instrumentation_library_spans"]:
            if spans_container_key in resource_span:
                for scope_span in resource_span[spans_container_key]:
                    # スコープまたはインストルメンテーションライブラリ情報
                    scope_key = next((key for key in ["scope", "instrumentationLibrary", "instrumentation_library"] if key in scope_span), None)
                    scope = scope_span.get(scope_key, {})
                    
                    # スパンリストの取得
                    spans_key = next((key for key in ["spans"] if key in scope_span), None)
                    if spans_key:
                        span_list.extend(scope_span[spans_key])
        
        # 各スパンを処理
        for span in span_list:
            # スパン情報の抽出
            try:
                # トレースIDとスパンIDを16進数文字列に変換
                trace_id = span.get("traceId", "").lower()
                if not trace_id:
                    continue
                
                span_id = span.get("spanId", "").lower()
                if not span_id:
                    continue
                
                # 親スパンID（存在する場合）
                parent_span_id = span.get("parentSpanId", "").lower()
                
                # スパン名
                name = span.get("name", "unknown")
                
                # 時間情報（ナノ秒からミリ秒に変換）
                start_time_nanos = span.get("startTimeUnixNano", "0")
                start_time = float(start_time_nanos) / 1_000_000_000 if isinstance(start_time_nanos, (int, str)) else 0
                
                end_time_nanos = span.get("endTimeUnixNano", "0")
                end_time = float(end_time_nanos) / 1_000_000_000 if isinstance(end_time_nanos, (int, str)) else 0
                
                # 属性
                attributes = {"service.name": service_name}
                
                # スパン種別の設定
                span_kind = span.get("kind", "SPAN_KIND_INTERNAL")
                if isinstance(span_kind, int):
                    span_kind_map = {
                        1: "internal",
                        2: "server",
                        3: "client",
                        4: "producer",
                        5: "consumer"
                    }
                    attributes["span.kind"] = span_kind_map.get(span_kind, "internal")
                else:
                    span_kind = str(span_kind).lower()
                    if "server" in span_kind:
                        attributes["span.kind"] = "server"
                    elif "client" in span_kind:
                        attributes["span.kind"] = "client"
                    elif "producer" in span_kind:
                        attributes["span.kind"] = "producer"
                    elif "consumer" in span_kind:
                        attributes["span.kind"] = "consumer"
                    else:
                        attributes["span.kind"] = "internal"
                
                # スパン属性の処理
                for attr in span.get("attributes", []):
                    if "key" in attr and "value" in attr:
                        value = _extract_otel_attribute_value(attr["value"])
                        if value is not None:
                            attributes[attr["key"]] = value
                
                # スパン名を属性に追加
                attributes["span.name"] = name
                
                # ステータス情報
                status = span.get("status", {})
                status_code = status.get("code", "")
                if isinstance(status_code, int) and status_code == 2 or isinstance(status_code, str) and "error" in status_code.lower():
                    attributes["error"] = True
                    attributes["error.message"] = status.get("message", "Unknown error")
                
                # イベント
                events = []
                for event in span.get("events", []):
                    event_time_nanos = event.get("timeUnixNano", "0")
                    event_time = float(event_time_nanos) / 1_000_000_000 if isinstance(event_time_nanos, (int, str)) else 0
                    
                    event_attrs = {}
                    for attr in event.get("attributes", []):
                        if "key" in attr and "value" in attr:
                            value = _extract_otel_attribute_value(attr["value"])
                            if value is not None:
                                event_attrs[attr["key"]] = value
                    
                    events.append({
                        "name": event.get("name", "unknown"),
                        "timestamp": event_time,
                        "attributes": event_attrs
                    })
                
                # 内部形式のスパンを作成して保存
                from utils.tracing import SpanContext
                span_context = SpanContext(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id if parent_span_id else None,
                    attributes=attributes
                )
                span_context.start_time = start_time
                span_context.end_time = end_time
                span_context.events = events
                
                # ストレージに保存
                trace_storage.store_span(span_context)
                
                # ルートスパンの場合はトレース情報も保存
                if not parent_span_id:
                    trace_storage.store_trace(trace_id, span_context)
            
            except Exception as e:
                logger.error(f"スパンの処理中にエラーが発生しました: {str(e)}")


def _process_otlp_metrics(data: Dict[str, Any], metric_storage):
    """
    OTLPメトリクスデータを処理して内部形式に変換し、保存します
    
    Args:
        data: OTLPフォーマットのメトリクスデータ
        metric_storage: メトリクスストレージ
    """
    # resourceMetrics（OTLPv0.7+）またはresourceMetricsをチェック
    resource_metrics_key = next((key for key in ["resourceMetrics", "resource_metrics"] if key in data), None)
    
    if not resource_metrics_key:
        logger.warning("有効なOTLPメトリクスデータが見つかりません")
        return
    
    for resource_metric in data[resource_metrics_key]:
        # リソース情報の取得
        resource_key = next((key for key in ["resource", "resources"] if key in resource_metric), None)
        resource = resource_metric.get(resource_key, {})
        
        # リソース属性の取得
        resource_attributes = {}
        if "attributes" in resource:
            for attr in resource.get("attributes", []):
                if "key" in attr and "value" in attr:
                    value = _extract_otel_attribute_value(attr["value"])
                    if value is not None:
                        resource_attributes[attr["key"]] = value
        
        # サービス名の取得
        service_name = resource_attributes.get("service.name", "unknown")
        
        # メトリクス情報の取得（新旧両フォーマットに対応）
        metrics_list = []
        for metrics_container_key in ["scopeMetrics", "scope_metrics", "instrumentationLibraryMetrics", "instrumentation_library_metrics"]:
            if metrics_container_key in resource_metric:
                for scope_metric in resource_metric[metrics_container_key]:
                    # スコープまたはインストルメンテーションライブラリ情報
                    scope_key = next((key for key in ["scope", "instrumentationLibrary", "instrumentation_library"] if key in scope_metric), None)
                    scope = scope_metric.get(scope_key, {})
                    
                    # メトリクスリストの取得
                    metrics_key = next((key for key in ["metrics"] if key in scope_metric), None)
                    if metrics_key:
                        metrics_list.extend(scope_metric[metrics_key])
        
        # 各メトリクスを処理
        for metric in metrics_list:
            try:
                # メトリクス名
                name = metric.get("name", "unknown")
                
                # 説明
                description = metric.get("description", f"Metric: {name}")
                
                # 単位
                unit = metric.get("unit", "1")
                
                # メトリクスタイプの判定
                if any(key in metric for key in ["gauge", "sum", "histogram"]):
                    # メトリクスタイプと対応するデータポイントを取得
                    metric_type = None
                    data_points = []
                    
                    if "gauge" in metric:
                        metric_type = "gauge"
                        data_points = metric["gauge"].get("dataPoints", [])
                    elif "sum" in metric:
                        metric_type = "sum"
                        data_points = metric["sum"].get("dataPoints", [])
                    elif "histogram" in metric:
                        metric_type = "histogram"
                        data_points = metric["histogram"].get("dataPoints", [])
                    
                    # メトリクス定義の登録
                    from utils.monitoring import MetricDefinition, MetricType, MetricUnit
                    
                    if metric_type == "gauge":
                        definition = MetricDefinition(
                            name=name,
                            description=description,
                            metric_type=MetricType.GAUGE,
                            unit=MetricUnit.CUSTOM
                        )
                    elif metric_type == "sum":
                        definition = MetricDefinition(
                            name=name,
                            description=description,
                            metric_type=MetricType.COUNTER,
                            unit=MetricUnit.CUSTOM
                        )
                    elif metric_type == "histogram":
                        definition = MetricDefinition(
                            name=name,
                            description=description,
                            metric_type=MetricType.HISTOGRAM,
                            unit=MetricUnit.CUSTOM
                        )
                    else:
                        continue  # 不明なメトリクスタイプはスキップ
                    
                    # メトリクス定義を保存
                    metric_storage.store_metric_definition(definition)
                    
                    # データポイントを処理
                    for point in data_points:
                        # タイムスタンプ（ナノ秒からミリ秒に変換）
                        time_unix_nano = point.get("timeUnixNano", "0")
                        timestamp = float(time_unix_nano) / 1_000_000_000 if isinstance(time_unix_nano, (int, str)) else time.time()
                        
                        # 属性
                        attributes = {"service.name": service_name}
                        for attr in point.get("attributes", []):
                            if "key" in attr and "value" in attr:
                                value = _extract_otel_attribute_value(attr["value"])
                                if value is not None:
                                    attributes[attr["key"]] = value
                        
                        # メトリクス値の取得とメトリクスの保存
                        if metric_type == "gauge":
                            # ゲージ値（as_int, as_double, as_string）
                            value = _extract_otel_point_value(point)
                            if value is not None:
                                from utils.monitoring import MetricValue
                                metric_value = MetricValue(
                                    name=name,
                                    value=value,
                                    timestamp=timestamp,
                                    labels=attributes
                                )
                                metric_storage.store_metric_value(metric_value)
                        
                        elif metric_type == "sum":
                            # カウンター値（as_int, as_double）
                            value = _extract_otel_point_value(point)
                            if value is not None:
                                from utils.monitoring import MetricValue
                                metric_value = MetricValue(
                                    name=name,
                                    value=value,
                                    timestamp=timestamp,
                                    labels=attributes
                                )
                                metric_storage.store_metric_value(metric_value)
                        
                        elif metric_type == "histogram":
                            # ヒストグラム値（count, sum, buckets）
                            count = point.get("count", 0)
                            sum_value = point.get("sum", 0)
                            
                            bucket_counts = point.get("bucketCounts", [])
                            explicit_bounds = point.get("explicitBounds", [])
                            
                            if count > 0 and bucket_counts:
                                # ヒストグラムデータから代表値を取得（平均）
                                avg_value = sum_value / count if count > 0 else 0
                                
                                # バケットの分布からサンプルを生成
                                samples = []
                                for i, bucket_count in enumerate(bucket_counts):
                                    if bucket_count > 0:
                                        # バケットの下限と上限
                                        lower_bound = explicit_bounds[i-1] if i > 0 else 0
                                        upper_bound = explicit_bounds[i] if i < len(explicit_bounds) else float('inf')
                                        
                                        # 中央値を代表値として使用
                                        if upper_bound == float('inf'):
                                            # 最後のバケットの場合、平均値を使用
                                            sample_value = avg_value
                                        else:
                                            sample_value = (lower_bound + upper_bound) / 2
                                        
                                        # サンプル数分だけ追加
                                        for _ in range(int(bucket_count)):
                                            samples.append(sample_value)
                                
                                from utils.monitoring import MetricValue
                                metric_value = MetricValue(
                                    name=name,
                                    value=samples,
                                    timestamp=timestamp,
                                    labels=attributes
                                )
                                metric_storage.store_metric_value(metric_value)
                
            except Exception as e:
                logger.error(f"メトリクスの処理中にエラーが発生しました: {str(e)}")


def _extract_otel_attribute_value(value_container: Dict[str, Any]) -> Any:
    """
    OTLP属性値コンテナから実際の値を抽出します
    
    Args:
        value_container: 値コンテナ
        
    Returns:
        Any: 抽出された値
    """
    if "stringValue" in value_container:
        return value_container["stringValue"]
    elif "intValue" in value_container:
        return int(value_container["intValue"])
    elif "doubleValue" in value_container:
        return float(value_container["doubleValue"])
    elif "boolValue" in value_container:
        return bool(value_container["boolValue"])
    elif "arrayValue" in value_container:
        array = value_container["arrayValue"]
        if "values" in array:
            return [_extract_otel_attribute_value(v) for v in array["values"]]
    
    return None


def _extract_otel_point_value(point: Dict[str, Any]) -> Optional[Union[int, float]]:
    """
    OTLPデータポイントから値を抽出します
    
    Args:
        point: データポイント
        
    Returns:
        Optional[Union[int, float]]: 抽出された値
    """
    if "asInt" in point:
        return int(point["asInt"])
    elif "asDouble" in point:
        return float(point["asDouble"])
    elif "intValue" in point:
        return int(point["intValue"])
    elif "doubleValue" in point:
        return float(point["doubleValue"])
    
    return None 