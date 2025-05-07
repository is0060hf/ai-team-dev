"""
分散トレーシングのためのユーティリティモジュール。
OpenTelemetryを使用して、アプリケーション全体の実行パスを追跡します。
"""

import os
import uuid
import time
import json
import logging
import functools
import threading
from typing import Dict, Any, Optional, Callable, List, Union, TypeVar, cast
from datetime import datetime
from contextlib import contextmanager

from utils.logger import get_structured_logger, StructuredLogger
from utils.config import config

# trace_storageモジュールをインポート
try:
    from utils.trace_storage import get_trace_storage, get_exporter
except ImportError:
    # trace_storageモジュールがない場合は動作継続できるようにする
    get_trace_storage = None
    get_exporter = None

# 型変数の定義
T = TypeVar('T')

# ロガーの取得
logger = get_structured_logger("tracing")

# グローバルトレース情報を保持するスレッドローカルストレージ
_trace_context = threading.local()

# エクスポーターのキャッシュ
_exporters = {}


class SpanContext:
    """スパンコンテキストを表すクラス"""
    
    def __init__(
        self, 
        trace_id: str, 
        span_id: str, 
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            trace_id: トレースID
            span_id: スパンID
            parent_span_id: 親スパンID
            attributes: スパン属性
        """
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attributes = attributes or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.events: List[Dict[str, Any]] = []
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """イベントを追加"""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """スパンコンテキストを辞書形式で取得"""
        span_dict = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "start_time": self.start_time,
            "attributes": self.attributes,
            "events": self.events
        }
        
        if self.parent_span_id:
            span_dict["parent_span_id"] = self.parent_span_id
        
        if self.end_time:
            span_dict["end_time"] = self.end_time
            span_dict["duration_ms"] = (self.end_time - self.start_time) * 1000
        
        return span_dict


class Tracer:
    """トレーサークラス"""
    
    def __init__(self, service_name: str = "ai_team"):
        """
        Args:
            service_name: サービス名
        """
        self.service_name = service_name
        self.spans: Dict[str, SpanContext] = {}
        self.active_spans: Dict[str, List[SpanContext]] = {}  # trace_id -> [active_spans]
        self.log_spans = config.TRACE_LOG_SPANS
        self._trace_logger = get_structured_logger(f"trace.{service_name}")
        
        # 外部ストレージの設定
        self.external_storage_enabled = getattr(config, "ENABLE_EXTERNAL_TRACE_STORAGE", False)
        self.storage = get_trace_storage() if get_trace_storage and self.external_storage_enabled else None
        
        # トレースデータのエクスポート設定
        self.export_enabled = getattr(config, "ENABLE_TRACE_EXPORT", False) and bool(get_exporter)
        self.export_batch_size = getattr(config, "TRACE_EXPORT_BATCH_SIZE", 10)
        self.export_queue = []
        self.export_lock = threading.Lock()
    
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
        # トレースIDの生成または使用
        trace_id = trace_id or str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        # 基本属性の設定
        span_attributes = {
            "service.name": self.service_name,
            "span.name": name,
            "span.kind": "internal",
            "span.type": "root"
        }
        
        # 追加属性の設定
        if attributes:
            span_attributes.update(attributes)
        
        # スパンコンテキストの作成
        span_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            attributes=span_attributes
        )
        
        # スパンの保存
        self.spans[span_id] = span_context
        
        # アクティブスパンリストに追加
        if trace_id not in self.active_spans:
            self.active_spans[trace_id] = []
        self.active_spans[trace_id].append(span_context)
        
        # グローバルトレース情報の設定
        self._set_current_span(span_context)
        
        # トレース開始をログに記録
        logger.info(
            f"トレース開始: {name}",
            context={
                "trace_id": trace_id,
                "span_id": span_id,
                "service": self.service_name
            }
        )
        
        # トレース情報をロガーに設定
        if isinstance(self._trace_logger, StructuredLogger):
            self._trace_logger.set_trace_info(trace_id, span_id)
        
        return span_context
    
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
        
        # スパンIDの生成
        span_id = str(uuid.uuid4())
        
        # 基本属性の設定
        span_attributes = {
            "service.name": self.service_name,
            "span.name": name,
            "span.kind": "internal",
            "span.type": "child"
        }
        
        # 追加属性の設定
        if attributes:
            span_attributes.update(attributes)
        
        # スパンコンテキストの作成
        span_context = SpanContext(
            trace_id=current_span.trace_id,
            span_id=span_id,
            parent_span_id=current_span.span_id,
            attributes=span_attributes
        )
        
        # スパンの保存
        self.spans[span_id] = span_context
        
        # アクティブスパンリストに追加
        if current_span.trace_id not in self.active_spans:
            self.active_spans[current_span.trace_id] = []
        self.active_spans[current_span.trace_id].append(span_context)
        
        # グローバルトレース情報の更新
        self._set_current_span(span_context)
        
        # スパン開始をログに記録
        logger.debug(
            f"スパン開始: {name}",
            context={
                "trace_id": current_span.trace_id,
                "span_id": span_id,
                "parent_span_id": current_span.span_id,
                "service": self.service_name
            }
        )
        
        # トレース情報をロガーに設定
        if isinstance(self._trace_logger, StructuredLogger):
            self._trace_logger.set_trace_info(
                current_span.trace_id, 
                span_id, 
                current_span.span_id
            )
        
        return span_context
    
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
        
        # 終了時刻を設定
        span.end_time = time.time()
        
        # エラー情報を設定
        if error:
            span.attributes["error"] = True
            span.attributes["error.type"] = error.__class__.__name__
            span.attributes["error.message"] = str(error)
        
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
        else:
            # 親スパンがない場合はクリア
            self._clear_current_span()
        
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
        
        # スパン情報をログに記録（設定されている場合）
        if self.log_spans:
            self._log_span(span)
        
        # 外部ストレージに保存
        if self.storage:
            self._store_span(span)
        
        # トレース全体が終了した場合（ルートスパンが終了した場合）
        if self.export_enabled and not span.parent_span_id:
            self._queue_trace_for_export(span.trace_id)
    
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
        
        # イベントを追加
        target_span.add_event(name, attributes)
        
        # イベント追加をログに記録
        logger.debug(
            f"イベント追加: {name}",
            context={
                "trace_id": target_span.trace_id,
                "span_id": target_span.span_id,
                "event": name
            }
        )
    
    def _set_current_span(self, span: SpanContext):
        """現在のスパンを設定"""
        _trace_context.current_span = span
    
    def _get_current_span(self) -> Optional[SpanContext]:
        """現在のスパンを取得"""
        return getattr(_trace_context, "current_span", None)
    
    def _clear_current_span(self):
        """現在のスパンをクリア"""
        if hasattr(_trace_context, "current_span"):
            delattr(_trace_context, "current_span")
    
    def _log_span(self, span: SpanContext):
        """スパン情報をログに記録"""
        span_dict = span.to_dict()
        self._trace_logger.info(
            f"Span: {span.attributes.get('span.name')}",
            context={"span": span_dict}
        )
        
        # もし終了したスパンがルートスパン（トレース）で、すべてのスパンが終了している場合
        # トレース全体の情報をログに記録
        if (not span.parent_span_id and 
            span.trace_id not in self.active_spans):
            self._log_trace(span.trace_id)
    
    def _log_trace(self, trace_id: str):
        """トレース全体の情報をログに記録"""
        # このトレースに関連するすべてのスパンを収集
        trace_spans = [
            span for span in self.spans.values()
            if span.trace_id == trace_id and span.end_time is not None
        ]
        
        if not trace_spans:
            return
        
        # ルートスパンを特定
        root_span = next(
            (span for span in trace_spans if not span.parent_span_id),
            None
        )
        
        if not root_span:
            return
        
        # トレース情報を構築
        trace_info = {
            "trace_id": trace_id,
            "root_span": root_span.to_dict(),
            "spans": [span.to_dict() for span in trace_spans],
            "total_spans": len(trace_spans),
            "start_time": root_span.start_time,
            "end_time": root_span.end_time,
            "duration_ms": (root_span.end_time - root_span.start_time) * 1000 if root_span.end_time else None
        }
        
        # トレース情報をログに記録
        self._trace_logger.info(
            f"トレース完了: {root_span.attributes.get('span.name')} "
            f"({trace_info['duration_ms']:.2f}ms, {len(trace_spans)}スパン)",
            context={"trace": trace_info}
        )
    
    def _store_span(self, span: SpanContext):
        """
        スパン情報を外部ストレージに保存
        
        Args:
            span: スパンコンテキスト
        """
        if not self.storage:
            return
        
        try:
            self.storage.store_span(span)
            
            # ルートスパンの場合はトレース情報も保存
            if not span.parent_span_id:
                self.storage.store_trace(span.trace_id, span)
        except Exception as e:
            logger.error(f"スパン情報の保存に失敗しました: {str(e)}")
    
    def _queue_trace_for_export(self, trace_id: str):
        """
        トレースをエクスポートキューに追加
        
        Args:
            trace_id: トレースID
        """
        if not self.export_enabled or not self.storage:
            return
        
        with self.export_lock:
            self.export_queue.append(trace_id)
            
            # キューサイズがバッチサイズを超えたらエクスポート
            if len(self.export_queue) >= self.export_batch_size:
                self._export_traces()
    
    def _export_traces(self):
        """キューに入っているトレースをエクスポート"""
        if not self.export_enabled or not self.storage or not get_exporter:
            return
        
        with self.export_lock:
            if not self.export_queue:
                return
            
            trace_ids = self.export_queue.copy()
            self.export_queue.clear()
        
        # 設定されたエクスポーターでトレースをエクスポート
        exporters_config = getattr(config, "TRACE_EXPORTERS", [])
        
        for exporter_config in exporters_config:
            exporter_type = exporter_config.get("type")
            if not exporter_type:
                continue
            
            # エクスポーターを取得または初期化
            exporter_key = json.dumps(exporter_config, sort_keys=True)
            if exporter_key not in _exporters:
                exporter_params = {k: v for k, v in exporter_config.items() if k != "type"}
                _exporters[exporter_key] = get_exporter(exporter_type, **exporter_params)
            
            exporter = _exporters[exporter_key]
            if not exporter:
                continue
            
            # トレースをエクスポート
            exported_count = 0
            for trace_id in trace_ids:
                try:
                    trace = self.storage.get_trace(trace_id)
                    if trace and exporter.export_trace(trace):
                        exported_count += 1
                except Exception as e:
                    logger.error(f"トレース {trace_id} のエクスポートに失敗しました: {str(e)}")
            
            if exported_count > 0:
                logger.info(f"{exported_count}件のトレースを {exporter_type} にエクスポートしました")


# グローバルトレーサーインスタンス
tracer = Tracer()


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    スパンをトレースするコンテキストマネージャ
    
    Args:
        name: スパン名
        attributes: スパン属性
    
    Yields:
        SpanContext: 生成されたスパンコンテキスト
    """
    span = tracer.start_span(name, attributes)
    try:
        yield span
    except Exception as e:
        tracer.end_span(span, error=e)
        raise
    else:
        tracer.end_span(span)


def trace(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    関数をトレースするデコレーター
    
    Args:
        name: スパン名（省略時は関数名）
        attributes: スパン属性
    
    Returns:
        Callable: デコレートされた関数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            span_name = name or f"{func.__module__}.{func.__name__}"
            span_attributes = attributes or {}
            
            # クラスメソッドの場合、クラス名を追加
            if args and hasattr(args[0], "__class__"):
                class_name = args[0].__class__.__name__
                if class_name != "type":
                    span_name = f"{class_name}.{func.__name__}"
                    span_attributes["class"] = class_name
            
            with trace_span(span_name, span_attributes) as span:
                return func(*args, **kwargs)
        
        return cast(Callable[..., T], wrapper)
    
    # 関数が直接渡された場合（@trace）
    if callable(name):
        func, name = name, None
        return decorator(func)
    
    # 引数付きデコレーターの場合（@trace("name")）
    return decorator


def add_trace_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    現在のスパンにイベントを追加する関数
    
    Args:
        name: イベント名
        attributes: イベント属性
    """
    tracer.add_event(name, attributes)


def get_current_trace_id() -> Optional[str]:
    """
    現在のトレースIDを取得する関数
    
    Returns:
        Optional[str]: 現在のトレースID
    """
    current_span = getattr(_trace_context, "current_span", None)
    return current_span.trace_id if current_span else None


def get_current_span_id() -> Optional[str]:
    """
    現在のスパンIDを取得する関数
    
    Returns:
        Optional[str]: 現在のスパンID
    """
    current_span = getattr(_trace_context, "current_span", None)
    return current_span.span_id if current_span else None


def set_span_attribute(key: str, value: Any):
    """
    現在のスパンに属性を設定する関数
    
    Args:
        key: 属性キー
        value: 属性値
    """
    current_span = getattr(_trace_context, "current_span", None)
    if current_span:
        current_span.attributes[key] = value


def export_pending_traces():
    """保留中のトレースをエクスポート"""
    if hasattr(tracer, "_export_traces"):
        tracer._export_traces() 