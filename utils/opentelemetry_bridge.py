"""
OpenTelemetryブリッジモジュール。
既存のトレーシングシステムとOpenTelemetryを連携するためのブリッジを提供します。
"""

import os
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Callable

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.context.context import Context
from opentelemetry.trace.span import Span, SpanContext as OTelSpanContext, TraceFlags

# オプショナルな依存関係
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter as OTelJaegerExporter
    JAEGER_AVAILABLE = True
except ImportError:
    JAEGER_AVAILABLE = False

try:
    from opentelemetry.exporter.zipkin.json import ZipkinExporter as OTelZipkinExporter
    ZIPKIN_AVAILABLE = True
except ImportError:
    ZIPKIN_AVAILABLE = False

try:
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    CLOUD_TRACE_AVAILABLE = True
except ImportError:
    CLOUD_TRACE_AVAILABLE = False

from utils.logger import get_structured_logger
from utils.config import config
from utils.tracing import SpanContext, Tracer as CustomTracer

# ロガーの取得
logger = get_structured_logger("opentelemetry_bridge")

# グローバルのOpenTelemetryトレーサープロバイダー
_tracer_provider = None
# グローバルのOpenTelemetryトレーサー
_tracer = None
# トレースコンテキスト用のスレッドローカルストレージ
_otel_context = threading.local()


def init_opentelemetry(
    service_name: str = "ai_team",
    resource_attributes: Optional[Dict[str, str]] = None,
    exporters: Optional[List[str]] = None
) -> None:
    """
    OpenTelemetryの初期化を行います

    Args:
        service_name: サービス名
        resource_attributes: リソース属性
        exporters: 使用するエクスポーター（"otlp", "jaeger", "zipkin", "cloud_trace", "console"）
    """
    global _tracer_provider, _tracer

    # 既に初期化済みの場合は何もしない
    if _tracer_provider is not None:
        return

    # リソース属性の設定
    attrs = {
        ResourceAttributes.SERVICE_NAME: service_name,
    }
    
    if resource_attributes:
        attrs.update(resource_attributes)
    
    resource = Resource.create(attrs)
    
    # トレーサープロバイダーの設定
    _tracer_provider = TracerProvider(resource=resource)
    
    # エクスポーターの設定
    if not exporters:
        # デフォルトはコンソールエクスポーター
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    else:
        for exporter in exporters:
            if exporter.lower() == "otlp" and OTLP_AVAILABLE:
                # OTLP (OpenTelemetry Protocol) エクスポーター
                otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
                otlp_headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
                
                headers = {}
                if otlp_headers:
                    for header_item in otlp_headers.split(","):
                        if "=" in header_item:
                            key, value = header_item.split("=", 1)
                            headers[key.strip()] = value.strip()
                
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(
                        OTLPSpanExporter(
                            endpoint=otlp_endpoint,
                            headers=headers
                        )
                    )
                )
                logger.info(f"OTLP Exporterを設定しました: {otlp_endpoint}")
            
            elif exporter.lower() == "jaeger" and JAEGER_AVAILABLE:
                # Jaegerエクスポーター
                jaeger_host = os.environ.get("OTEL_EXPORTER_JAEGER_AGENT_HOST", "localhost")
                jaeger_port = int(os.environ.get("OTEL_EXPORTER_JAEGER_AGENT_PORT", "6831"))
                
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(
                        OTelJaegerExporter(
                            agent_host_name=jaeger_host,
                            agent_port=jaeger_port,
                        )
                    )
                )
                logger.info(f"Jaeger Exporterを設定しました: {jaeger_host}:{jaeger_port}")
            
            elif exporter.lower() == "zipkin" and ZIPKIN_AVAILABLE:
                # Zipkinエクスポーター
                zipkin_endpoint = os.environ.get(
                    "OTEL_EXPORTER_ZIPKIN_ENDPOINT", 
                    "http://localhost:9411/api/v2/spans"
                )
                
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(
                        OTelZipkinExporter(
                            endpoint=zipkin_endpoint
                        )
                    )
                )
                logger.info(f"Zipkin Exporterを設定しました: {zipkin_endpoint}")
            
            elif exporter.lower() == "cloud_trace" and CLOUD_TRACE_AVAILABLE:
                # Google Cloud Traceエクスポーター
                project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
                if project_id:
                    _tracer_provider.add_span_processor(
                        BatchSpanProcessor(
                            CloudTraceSpanExporter(project_id=project_id)
                        )
                    )
                    logger.info(f"Cloud Trace Exporterを設定しました: {project_id}")
                else:
                    logger.warning("GOOGLE_CLOUD_PROJECT環境変数が設定されていないため、Cloud Trace Exporterを設定できません")
            
            elif exporter.lower() == "console":
                # コンソールエクスポーター
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(ConsoleSpanExporter())
                )
                logger.info("Console Exporterを設定しました")
    
    # グローバルトレーサープロバイダーとして設定
    trace.set_tracer_provider(_tracer_provider)
    
    # トレーサーの取得
    _tracer = trace.get_tracer(service_name)
    
    logger.info(f"OpenTelemetryを初期化しました (service_name: {service_name})")


def get_tracer():
    """
    OpenTelemetryトレーサーを取得します
    
    Returns:
        トレーサーインスタンス
    """
    global _tracer
    
    if _tracer is None:
        # 初期化されていない場合は初期化
        init_opentelemetry()
    
    return _tracer


def custom_span_to_otel_span(custom_span: SpanContext) -> Span:
    """
    カスタムSpanContextからOpenTelemetry Spanを作成

    Args:
        custom_span: カスタムのSpanContext

    Returns:
        Span: OpenTelemetry Span
    """
    # OpenTelemetryのSpanContextを作成
    trace_id_bytes = bytes.fromhex(custom_span.trace_id.replace('-', ''))
    if len(trace_id_bytes) < 16:  # 16バイトに満たない場合は0埋め
        trace_id_bytes = b'\x00' * (16 - len(trace_id_bytes)) + trace_id_bytes
    
    span_id_bytes = bytes.fromhex(custom_span.span_id.replace('-', ''))
    if len(span_id_bytes) < 8:  # 8バイトに満たない場合は0埋め
        span_id_bytes = b'\x00' * (8 - len(span_id_bytes)) + span_id_bytes
    
    # SpanContextの作成
    span_context = OTelSpanContext(
        trace_id=int.from_bytes(trace_id_bytes, byteorder='big'),
        span_id=int.from_bytes(span_id_bytes, byteorder='big'),
        is_remote=False,
        trace_flags=TraceFlags(1),  # サンプリングフラグを有効に
    )
    
    # 現在のコンテキストを取得
    current_context = trace.get_current_span().get_span_context()
    parent_context = None
    
    # 親コンテキストの設定
    if custom_span.parent_span_id:
        parent_id_bytes = bytes.fromhex(custom_span.parent_span_id.replace('-', ''))
        if len(parent_id_bytes) < 8:
            parent_id_bytes = b'\x00' * (8 - len(parent_id_bytes)) + parent_id_bytes
        
        parent_span_id = int.from_bytes(parent_id_bytes, byteorder='big')
        if current_context and current_context.span_id == parent_span_id:
            parent_context = trace.get_current_span()
    
    # OpenTelemetry Spanの作成
    tracer = get_tracer()
    span_name = custom_span.attributes.get("span.name", "unknown")
    
    # 開始時間と終了時間をナノ秒に変換
    start_time = int(custom_span.start_time * 1_000_000_000)
    end_time = int(custom_span.end_time * 1_000_000_000) if custom_span.end_time else None
    
    # Spanの作成
    span = tracer.start_span(
        name=span_name,
        context=parent_context,
        start_time=start_time,
        attributes={k: v for k, v in custom_span.attributes.items()},
    )
    
    # イベントを追加
    for event in custom_span.events:
        span.add_event(
            name=event["name"],
            timestamp=int(event["timestamp"] * 1_000_000_000),
            attributes=event.get("attributes", {})
        )
    
    # 終了時間が設定されている場合は終了
    if end_time:
        span.end(end_time=end_time)
    
    return span


def otel_span_to_custom_span(otel_span: Span) -> SpanContext:
    """
    OpenTelemetry SpanからカスタムSpanContextを作成

    Args:
        otel_span: OpenTelemetry Span

    Returns:
        SpanContext: カスタムのSpanContext
    """
    context = otel_span.get_span_context()
    
    # トレースIDとスパンIDを16進数文字列に変換
    trace_id_hex = format(context.trace_id, '032x')
    span_id_hex = format(context.span_id, '016x')
    
    # 親スパンIDの取得
    parent_span_id = None
    parent_context = trace.get_current_span().get_span_context()
    if parent_context and parent_context.span_id != 0:
        parent_span_id = format(parent_context.span_id, '016x')
    
    # 属性の取得
    attributes = {}
    for key, value in otel_span.attributes.items():
        attributes[key] = value
    
    if "span.name" not in attributes:
        attributes["span.name"] = otel_span.name
    
    # SpanContextの作成
    span_context = SpanContext(
        trace_id=trace_id_hex,
        span_id=span_id_hex,
        parent_span_id=parent_span_id,
        attributes=attributes
    )
    
    # 開始時間と終了時間の設定
    span_context.start_time = otel_span.start_time / 1_000_000_000  # ナノ秒から秒に変換
    if hasattr(otel_span, "end_time") and otel_span.end_time:
        span_context.end_time = otel_span.end_time / 1_000_000_000  # ナノ秒から秒に変換
    
    # イベントの設定 (OpenTelemetryのAPIでは直接イベントを取得できないため、ここでは空リスト)
    span_context.events = []
    
    return span_context


class OTelTracer(CustomTracer):
    """
    OpenTelemetryベースのトレーサー実装
    既存のCustomTracerインターフェースを維持しつつ、内部でOpenTelemetryを使用
    """
    
    def __init__(self, service_name: str = "ai_team"):
        """
        Args:
            service_name: サービス名
        """
        super().__init__(service_name)
        
        # OpenTelemetryが初期化されていない場合は初期化
        if _tracer_provider is None:
            # 設定からエクスポーターを取得
            exporters = getattr(config, "OPENTELEMETRY_EXPORTERS", ["console"])
            
            # リソース属性の設定
            resource_attributes = {
                "deployment.environment": getattr(config, "ENVIRONMENT", "development"),
            }
            
            # OpenTelemetryを初期化
            init_opentelemetry(
                service_name=service_name,
                resource_attributes=resource_attributes,
                exporters=exporters
            )
    
    def start_trace(
        self, 
        name: str, 
        attributes: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> SpanContext:
        """
        新しいトレースを開始
        
        Args:
            name: トレース名
            attributes: トレース属性
            trace_id: 特定のトレースIDを使用する場合（省略時は自動生成）
            
        Returns:
            SpanContext: 生成されたスパンコンテキスト
        """
        # OpenTelemetryトレーサーを取得
        tracer = get_tracer()
        
        # 属性を準備
        otel_attributes = {
            "service.name": self.service_name,
            "span.kind": "internal",
            "span.type": "root"
        }
        
        if attributes:
            otel_attributes.update(attributes)
        
        # OpenTelemetryでスパンを開始
        span = tracer.start_span(name=name, attributes=otel_attributes)
        
        # カレントスパンとして設定
        context = trace.set_span_in_context(span)
        setattr(_otel_context, "current_context", context)
        
        # カスタムSpanContextに変換して返す
        custom_span = otel_span_to_custom_span(span)
        
        # グローバルトレース情報の設定
        self._set_current_span(custom_span)
        
        # トレース開始をログに記録
        logger.info(
            f"トレース開始: {name}",
            context={
                "trace_id": custom_span.trace_id,
                "span_id": custom_span.span_id,
                "service": self.service_name
            }
        )
        
        return custom_span
    
    def start_span(
        self, 
        name: str, 
        attributes: Optional[Dict[str, Any]] = None,
        parent_span: Optional[SpanContext] = None
    ) -> SpanContext:
        """
        現在のトレース内に新しいスパンを開始
        
        Args:
            name: スパン名
            attributes: スパン属性
            parent_span: 親スパン（省略時は現在のスパン）
            
        Returns:
            SpanContext: 生成されたスパンコンテキスト
        """
        # 現在のスパンを取得
        current_span = parent_span or self._get_current_span()
        
        # 現在のスパンがない場合は新しいトレースを開始
        if not current_span:
            return self.start_trace(name, attributes)
        
        # OpenTelemetryトレーサーを取得
        tracer = get_tracer()
        
        # 属性を準備
        otel_attributes = {
            "service.name": self.service_name,
            "span.kind": "internal",
            "span.type": "child"
        }
        
        if attributes:
            otel_attributes.update(attributes)
        
        # 親スパンのコンテキストを取得
        parent_otel_span = custom_span_to_otel_span(current_span)
        parent_context = trace.set_span_in_context(parent_otel_span)
        
        # OpenTelemetryでスパンを開始
        with trace.use_span(parent_otel_span, end_on_exit=False):
            span = tracer.start_span(name=name, attributes=otel_attributes)
        
        # カレントスパンとして設定
        context = trace.set_span_in_context(span)
        setattr(_otel_context, "current_context", context)
        
        # カスタムSpanContextに変換
        custom_span = otel_span_to_custom_span(span)
        
        # グローバルトレース情報の更新
        self._set_current_span(custom_span)
        
        # スパン開始をログに記録
        logger.debug(
            f"スパン開始: {name}",
            context={
                "trace_id": custom_span.trace_id,
                "span_id": custom_span.span_id,
                "parent_span_id": custom_span.parent_span_id,
                "service": self.service_name
            }
        )
        
        return custom_span
    
    def end_span(self, span: Union[SpanContext, str], error: Optional[Exception] = None):
        """
        スパンを終了
        
        Args:
            span: 終了するスパンまたはスパンID
            error: エラーが発生した場合はその例外
        """
        # スパンIDからスパンを取得
        if isinstance(span, str):
            if span not in self.spans:
                logger.warning(f"スパンID {span} が見つかりません")
                return
            span = self.spans[span]
        
        # 既に終了しているかチェック
        if span.end_time:
            logger.warning(f"スパン {span.span_id} は既に終了しています")
            return
        
        # OpenTelemetryスパンを取得
        otel_span = custom_span_to_otel_span(span)
        
        # エラー情報を設定
        if error:
            otel_span.record_exception(error)
            otel_span.set_status(trace.StatusCode.ERROR, str(error))
        
        # スパンを終了
        otel_span.end()
        
        # 終了時刻を設定
        span.end_time = time.time()
        
        # アクティブスパンリストから削除
        if span.trace_id in self.active_spans:
            try:
                self.active_spans[span.trace_id].remove(span)
                # リストが空になった場合は削除
                if not self.active_spans[span.trace_id]:
                    del self.active_spans[span.trace_id]
            except ValueError:
                pass
        
        # 親スパンがあれば、現在のスパンを親スパンに戻す
        if span.parent_span_id and span.parent_span_id in self.spans:
            parent_span = self.spans[span.parent_span_id]
            self._set_current_span(parent_span)
            
            # OpenTelemetryのコンテキストも更新
            parent_otel_span = custom_span_to_otel_span(parent_span)
            context = trace.set_span_in_context(parent_otel_span)
            setattr(_otel_context, "current_context", context)
        else:
            # 親スパンがない場合はクリア
            self._clear_current_span()
            delattr(_otel_context, "current_context")
        
        # スパン終了をログに記録
        duration_ms = (span.end_time - span.start_time) * 1000
        log_level = logging.ERROR if error else logging.DEBUG
        
        logger.log(
            log_level,
            f"スパン終了: {span.attributes.get('span.name')} ({duration_ms:.2f}ms)",
            context={
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "duration_ms": duration_ms,
                "error": bool(error)
            }
        )
    
    def add_event(
        self, 
        name: str, 
        attributes: Optional[Dict[str, Any]] = None,
        span: Optional[Union[SpanContext, str]] = None
    ):
        """
        現在のスパンにイベントを追加
        
        Args:
            name: イベント名
            attributes: イベント属性
            span: 特定のスパンまたはスパンID（省略時は現在のスパン）
        """
        # スパンの取得
        target_span = None
        
        if span:
            if isinstance(span, str):
                if span in self.spans:
                    target_span = self.spans[span]
            else:
                target_span = span
        else:
            target_span = self._get_current_span()
        
        if not target_span:
            logger.warning(f"イベント {name} を追加できません: アクティブなスパンがありません")
            return
        
        # イベントをカスタムスパンに追加
        target_span.add_event(name, attributes)
        
        # OpenTelemetryスパンにもイベントを追加
        otel_span = custom_span_to_otel_span(target_span)
        otel_span.add_event(name, attributes)
        
        # イベント追加をログに記録
        logger.debug(
            f"イベント追加: {name}",
            context={
                "trace_id": target_span.trace_id,
                "span_id": target_span.span_id,
                "event": name
            }
        )


# OpenTelemetry用の分散トレーシングミドルウェアの実装
class OpenTelemetryMiddleware:
    """
    FastAPIやFlaskで使用する分散トレーシングミドルウェア
    """
    
    def __init__(self, app, tracer: Optional[OTelTracer] = None):
        """
        Args:
            app: FastAPIまたはFlaskアプリケーション
            tracer: トレーサーインスタンス（省略時は新規作成）
        """
        self.app = app
        self.tracer = tracer or OTelTracer("web_server")
        
        # FastAPIとFlaskの識別
        self.is_fastapi = hasattr(app, "router")
        
        if self.is_fastapi:
            # FastAPI用のセットアップ
            from fastapi import Request, Response
            from starlette.middleware.base import BaseHTTPMiddleware
            
            class FastAPIMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    # トレースコンテキストの抽出
                    carrier = {}
                    for key, value in request.headers.items():
                        carrier[key] = value
                    
                    propagator = TraceContextTextMapPropagator()
                    context = propagator.extract(carrier=carrier)
                    
                    # リクエスト属性
                    attributes = {
                        "http.method": request.method,
                        "http.url": str(request.url),
                        "http.host": request.headers.get("host", ""),
                        "http.user_agent": request.headers.get("user-agent", ""),
                        "http.client_ip": request.client.host if request.client else "",
                        "http.flavor": request.scope.get("http_version", ""),
                    }
                    
                    # スパンの開始
                    with trace.use_span(
                        get_tracer().start_span(
                            f"{request.method} {request.url.path}",
                            context=context,
                            attributes=attributes,
                            kind=trace.SpanKind.SERVER,
                        ),
                        end_on_exit=True,
                    ) as span:
                        try:
                            response = await call_next(request)
                            
                            # レスポンス属性
                            span.set_attribute("http.status_code", response.status_code)
                            if response.status_code >= 400:
                                span.set_status(
                                    trace.StatusCode.ERROR, 
                                    f"HTTP {response.status_code}"
                                )
                            
                            return response
                        except Exception as e:
                            span.record_exception(e)
                            span.set_status(trace.StatusCode.ERROR, str(e))
                            raise
            
            app.add_middleware(FastAPIMiddleware)
        else:
            # Flask用のセットアップ
            @app.before_request
            def before_request():
                from flask import request, g
                
                # トレースコンテキストの抽出
                carrier = {}
                for key, value in request.headers.items():
                    carrier[key] = value
                
                propagator = TraceContextTextMapPropagator()
                context = propagator.extract(carrier=carrier)
                
                # リクエスト属性
                attributes = {
                    "http.method": request.method,
                    "http.url": request.url,
                    "http.host": request.host,
                    "http.user_agent": request.user_agent.string,
                    "http.client_ip": request.remote_addr,
                    "http.flavor": request.environ.get("SERVER_PROTOCOL", ""),
                }
                
                # スパンの開始
                span = get_tracer().start_span(
                    f"{request.method} {request.path}",
                    context=context,
                    attributes=attributes,
                    kind=trace.SpanKind.SERVER,
                )
                
                # Flaskのグローバルオブジェクトにスパンを保存
                g.otel_span = span
                g.otel_context = trace.set_span_in_context(span)
            
            @app.after_request
            def after_request(response):
                from flask import g
                
                if hasattr(g, "otel_span"):
                    # レスポンス属性
                    g.otel_span.set_attribute("http.status_code", response.status_code)
                    if response.status_code >= 400:
                        g.otel_span.set_status(
                            trace.StatusCode.ERROR, 
                            f"HTTP {response.status_code}"
                        )
                    
                    # スパンの終了
                    g.otel_span.end()
                
                return response
            
            @app.teardown_request
            def teardown_request(exception):
                from flask import g
                
                if exception and hasattr(g, "otel_span"):
                    g.otel_span.record_exception(exception)
                    g.otel_span.set_status(trace.StatusCode.ERROR, str(exception))
                    
                    # スパンが終了していない場合は終了
                    if not hasattr(g.otel_span, "end_time"):
                        g.otel_span.end()


# グローバル関数
def init_tracing(
    service_name: str = "ai_team",
    exporters: Optional[List[str]] = None,
    resource_attributes: Optional[Dict[str, str]] = None
) -> OTelTracer:
    """
    OpenTelemetryトレーシングの初期化を行います

    Args:
        service_name: サービス名
        exporters: 使用するエクスポーター
        resource_attributes: リソース属性

    Returns:
        OTelTracer: トレーサーインスタンス
    """
    # OpenTelemetryの初期化
    init_opentelemetry(
        service_name=service_name,
        resource_attributes=resource_attributes,
        exporters=exporters
    )
    
    # トレーサーの作成と返却
    return OTelTracer(service_name)


def get_otel_tracer(service_name: str = "ai_team") -> OTelTracer:
    """
    OpenTelemetryベースのトレーサーを取得します

    Args:
        service_name: サービス名

    Returns:
        OTelTracer: トレーサーインスタンス
    """
    return OTelTracer(service_name) 