"""
トレースコンテキスト伝播モジュール。
分散トレーシングのコンテキスト情報を異なるコンポーネント、サービス間で伝播するための機能を提供します。
"""

import base64
import json
import uuid
import threading
import time
from typing import Dict, Any, Optional, List, Tuple, Union
import inspect

from utils.logger import get_structured_logger
from utils.config import config
from utils.trace_sampling import should_sample_trace

# ロガーの取得
logger = get_structured_logger("trace_context")

# スレッドローカルストレージ
_trace_context_local = threading.local()


class TraceContext:
    """
    トレースコンテキスト情報を保持するクラス
    
    Attributes:
        trace_id (str): トレースID
        span_id (str): スパンID
        parent_span_id (str): 親スパンID
        trace_flags (int): トレースフラグ（サンプリングなど）
        trace_state (Dict[str, str]): トレース状態（ベンダー固有情報など）
        baggage (Dict[str, str]): ユーザー定義のバゲージアイテム
        start_time (float): 開始時間（エポック秒）
    """
    
    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        trace_flags: int = 1,  # デフォルトはサンプリングあり
        trace_state: Optional[Dict[str, str]] = None,
        baggage: Optional[Dict[str, str]] = None
    ):
        """
        初期化
        
        Args:
            trace_id: トレースID（省略時は自動生成）
            span_id: スパンID（省略時は自動生成）
            parent_span_id: 親スパンID
            trace_flags: トレースフラグ
            trace_state: トレース状態
            baggage: バゲージアイテム
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        self.trace_flags = trace_flags
        self.trace_state = trace_state or {}
        self.baggage = baggage or {}
        self.start_time = time.time()
    
    def create_child_span(self, span_id: Optional[str] = None) -> 'TraceContext':
        """
        子スパンを作成
        
        Args:
            span_id: 子スパンID（省略時は自動生成）
            
        Returns:
            TraceContext: 子スパンのトレースコンテキスト
        """
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id or str(uuid.uuid4()),
            parent_span_id=self.span_id,
            trace_flags=self.trace_flags,
            trace_state=self.trace_state.copy(),
            baggage=self.baggage.copy()
        )
    
    def to_w3c_traceparent(self) -> str:
        """
        W3C Trace Context traceparent形式に変換
        
        Returns:
            str: W3C Trace Context traceparent
        """
        # 16バイトのトレースIDに正規化（UUID形式からバイナリに変換）
        if '-' in self.trace_id:
            # UUID形式の場合はバイナリに変換
            trace_id_bin = uuid.UUID(self.trace_id).bytes
        else:
            # 既に16進数文字列の場合
            trace_id_bin = bytes.fromhex(self.trace_id.replace('-', ''))
        
        # 8バイトのスパンIDに正規化
        if '-' in self.span_id:
            # UUID形式の場合は後半8バイトを使用
            span_id_bin = uuid.UUID(self.span_id).bytes[-8:]
        else:
            # 既に16進数文字列の場合
            span_id_hex = self.span_id.replace('-', '')
            if len(span_id_hex) > 16:  # 8バイト = 16文字
                span_id_hex = span_id_hex[-16:]  # 長すぎる場合は後半を使用
            span_id_bin = bytes.fromhex(span_id_hex.zfill(16))[-8:]
        
        # 16進数文字列に変換
        trace_id_hex = trace_id_bin.hex()
        span_id_hex = span_id_bin.hex()
        
        # バージョン=00, トレースフラグ=01（サンプリングあり）または00（サンプリングなし）
        flags_hex = format(self.trace_flags & 0xff, '02x')
        
        # traceparent: バージョン-トレースID-スパンID-トレースフラグ
        return f"00-{trace_id_hex}-{span_id_hex}-{flags_hex}"
    
    def to_w3c_tracestate(self) -> str:
        """
        W3C Trace Context tracestate形式に変換
        
        Returns:
            str: W3C Trace Context tracestate
        """
        if not self.trace_state:
            return ""
        
        # key=value形式に変換してカンマで連結
        return ",".join(f"{k}={v}" for k, v in self.trace_state.items())
    
    def to_w3c_baggage(self) -> str:
        """
        W3C Baggage形式に変換
        
        Returns:
            str: W3C Baggage
        """
        if not self.baggage:
            return ""
        
        # key=value形式に変換してカンマで連結
        return ",".join(f"{k}={v}" for k, v in self.baggage.items())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        辞書形式に変換
        
        Returns:
            Dict[str, Any]: コンテキスト情報の辞書
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_flags": self.trace_flags,
            "trace_state": self.trace_state,
            "baggage": self.baggage,
            "start_time": self.start_time,
            "sampled": bool(self.trace_flags & 0x01)
        }
    
    @classmethod
    def from_w3c_headers(
        cls,
        traceparent: Optional[str] = None,
        tracestate: Optional[str] = None,
        baggage: Optional[str] = None
    ) -> Optional['TraceContext']:
        """
        W3C Trace Context ヘッダーからトレースコンテキストを作成
        
        Args:
            traceparent: traceparentヘッダー
            tracestate: tracestateヘッダー
            baggage: baggageヘッダー
            
        Returns:
            Optional[TraceContext]: トレースコンテキスト、解析エラー時はNone
        """
        if not traceparent:
            return None
        
        try:
            # traceparentの解析
            parts = traceparent.strip().split('-')
            if len(parts) != 4:
                logger.warning(f"不正なtraceparentフォーマット: {traceparent}")
                return None
            
            version, trace_id_hex, span_id_hex, flags_hex = parts
            
            # バージョンチェック
            if version != "00":
                logger.warning(f"サポートされていないtraceparentバージョン: {version}")
                # 未知のバージョンでも処理を続行
            
            # トレースID、スパンIDの検証
            if len(trace_id_hex) != 32 or int(trace_id_hex, 16) == 0:
                logger.warning(f"不正なトレースID: {trace_id_hex}")
                return None
            
            if len(span_id_hex) != 16 or int(span_id_hex, 16) == 0:
                logger.warning(f"不正なスパンID: {span_id_hex}")
                return None
            
            # フラグの解析
            trace_flags = int(flags_hex, 16)
            
            # tracestateの解析
            trace_state = {}
            if tracestate:
                for item in tracestate.split(','):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        trace_state[key.strip()] = value.strip()
            
            # baggageの解析
            baggage_items = {}
            if baggage:
                for item in baggage.split(','):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        baggage_items[key.strip()] = value.strip()
            
            # トレースコンテキストの作成
            return cls(
                trace_id=trace_id_hex,
                span_id=span_id_hex,
                parent_span_id=None,  # 親スパンIDはtraceparentに含まれない
                trace_flags=trace_flags,
                trace_state=trace_state,
                baggage=baggage_items
            )
        
        except Exception as e:
            logger.error(f"トレースコンテキストの解析に失敗しました: {str(e)}")
            return None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceContext':
        """
        辞書からトレースコンテキストを作成
        
        Args:
            data: トレースコンテキスト情報の辞書
            
        Returns:
            TraceContext: トレースコンテキスト
        """
        return cls(
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
            parent_span_id=data.get("parent_span_id"),
            trace_flags=data.get("trace_flags", 1),
            trace_state=data.get("trace_state", {}),
            baggage=data.get("baggage", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> Optional['TraceContext']:
        """
        JSON文字列からトレースコンテキストを作成
        
        Args:
            json_str: JSON文字列
            
        Returns:
            Optional[TraceContext]: トレースコンテキスト、解析エラー時はNone
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except Exception as e:
            logger.error(f"JSONからのトレースコンテキスト作成に失敗しました: {str(e)}")
            return None
    
    def to_json(self) -> str:
        """
        JSON文字列に変換
        
        Returns:
            str: JSON文字列
        """
        return json.dumps(self.to_dict())
    
    def should_sample(self, name: str = "") -> bool:
        """
        このトレースをサンプリングすべきかを判断
        
        Args:
            name: スパン名（サンプリング決定に使用）
            
        Returns:
            bool: サンプリングすべきならTrue
        """
        # 既にフラグで決定されている場合はそれに従う
        if self.trace_flags & 0x01:
            return True
        
        # サンプリング判断
        return should_sample_trace(name)


def get_current_trace_context() -> Optional[TraceContext]:
    """
    現在のスレッドのトレースコンテキストを取得
    
    Returns:
        Optional[TraceContext]: トレースコンテキスト、設定されていない場合はNone
    """
    return getattr(_trace_context_local, "context", None)


def set_current_trace_context(context: Optional[TraceContext]):
    """
    現在のスレッドにトレースコンテキストを設定
    
    Args:
        context: トレースコンテキスト
    """
    if context is None:
        if hasattr(_trace_context_local, "context"):
            delattr(_trace_context_local, "context")
    else:
        _trace_context_local.context = context


def create_trace_context(
    name: str = "",
    trace_id: Optional[str] = None,
    parent_context: Optional[TraceContext] = None
) -> TraceContext:
    """
    新しいトレースコンテキストを作成
    
    Args:
        name: トレース名（サンプリング判断に使用）
        trace_id: トレースID（省略時は自動生成）
        parent_context: 親コンテキスト（省略時は新しいトレースを開始）
        
    Returns:
        TraceContext: 作成されたトレースコンテキスト
    """
    # 親コンテキストがある場合は子スパンを作成
    if parent_context:
        context = parent_context.create_child_span()
    else:
        # 新しいトレースコンテキストを作成
        # サンプリング判断
        sampled = should_sample_trace(name)
        trace_flags = 1 if sampled else 0
        
        context = TraceContext(
            trace_id=trace_id,
            trace_flags=trace_flags
        )
    
    return context


def extract_http_headers(context: TraceContext) -> Dict[str, str]:
    """
    トレースコンテキストからHTTPヘッダーを抽出
    
    Args:
        context: トレースコンテキスト
        
    Returns:
        Dict[str, str]: HTTPヘッダー
    """
    headers = {
        "traceparent": context.to_w3c_traceparent()
    }
    
    tracestate = context.to_w3c_tracestate()
    if tracestate:
        headers["tracestate"] = tracestate
    
    baggage = context.to_w3c_baggage()
    if baggage:
        headers["baggage"] = baggage
    
    return headers


def inject_trace_context(carrier: Dict[str, str], context: Optional[TraceContext] = None):
    """
    キャリアにトレースコンテキストを注入
    
    Args:
        carrier: コンテキストを注入するキャリア（辞書）
        context: 注入するトレースコンテキスト（省略時は現在のコンテキスト）
    """
    if context is None:
        context = get_current_trace_context()
    
    if context is None:
        return
    
    # W3C Trace Context形式で注入
    carrier["traceparent"] = context.to_w3c_traceparent()
    
    tracestate = context.to_w3c_tracestate()
    if tracestate:
        carrier["tracestate"] = tracestate
    
    baggage = context.to_w3c_baggage()
    if baggage:
        carrier["baggage"] = baggage


def extract_trace_context(carrier: Dict[str, str]) -> Optional[TraceContext]:
    """
    キャリアからトレースコンテキストを抽出
    
    Args:
        carrier: コンテキストを抽出するキャリア（辞書）
        
    Returns:
        Optional[TraceContext]: 抽出されたトレースコンテキスト、失敗時はNone
    """
    traceparent = carrier.get("traceparent")
    tracestate = carrier.get("tracestate")
    baggage = carrier.get("baggage")
    
    return TraceContext.from_w3c_headers(traceparent, tracestate, baggage)


def trace_context_decorator(fn=None, name=None):
    """
    関数呼び出しのトレースコンテキストを管理するデコレータ
    
    Args:
        fn: デコレートする関数
        name: トレース名（省略時は関数名）
        
    Returns:
        関数: デコレートされた関数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # トレース名の決定
            trace_name = name or f"{func.__module__}.{func.__name__}"
            
            # 現在のコンテキストを取得
            current_context = get_current_trace_context()
            
            if current_context:
                # 親コンテキストがある場合は子スパンを作成
                context = current_context.create_child_span()
            else:
                # 新しいコンテキストを作成
                context = create_trace_context(name=trace_name)
            
            # コンテキストを設定
            set_current_trace_context(context)
            
            try:
                # 関数を実行
                return func(*args, **kwargs)
            finally:
                # コンテキストを元に戻す
                if current_context:
                    set_current_trace_context(current_context)
                else:
                    set_current_trace_context(None)
        
        return wrapper
    
    if fn:
        return decorator(fn)
    
    return decorator


class TraceContextManager:
    """
    トレースコンテキストを管理するコンテキストマネージャ
    
    Args:
        name: トレース名
        trace_id: トレースID（省略時は自動生成）
        parent_context: 親コンテキスト（省略時は現在のコンテキスト）
    """
    
    def __init__(
        self,
        name: str = "",
        trace_id: Optional[str] = None,
        parent_context: Optional[TraceContext] = None
    ):
        self.name = name
        self.trace_id = trace_id
        self.parent_context = parent_context
        self.previous_context = None
        self.context = None
    
    def __enter__(self):
        # 現在のコンテキストを保存
        self.previous_context = get_current_trace_context()
        
        # 親コンテキストが指定されていない場合は現在のコンテキストを使用
        parent = self.parent_context or self.previous_context
        
        if parent:
            # 親コンテキストがある場合は子スパンを作成
            self.context = parent.create_child_span()
        else:
            # 新しいコンテキストを作成
            self.context = create_trace_context(name=self.name, trace_id=self.trace_id)
        
        # コンテキストを設定
        set_current_trace_context(self.context)
        
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # コンテキストを元に戻す
        set_current_trace_context(self.previous_context)


def trace_context(name: str = "", trace_id: Optional[str] = None):
    """
    トレースコンテキストを管理するコンテキストマネージャを作成
    
    Args:
        name: トレース名
        trace_id: トレースID（省略時は自動生成）
        
    Returns:
        TraceContextManager: コンテキストマネージャ
    """
    return TraceContextManager(name=name, trace_id=trace_id)


# ユーティリティ関数
def get_trace_id() -> Optional[str]:
    """
    現在のトレースIDを取得
    
    Returns:
        Optional[str]: トレースID、設定されていない場合はNone
    """
    context = get_current_trace_context()
    return context.trace_id if context else None


def get_span_id() -> Optional[str]:
    """
    現在のスパンIDを取得
    
    Returns:
        Optional[str]: スパンID、設定されていない場合はNone
    """
    context = get_current_trace_context()
    return context.span_id if context else None


def get_parent_span_id() -> Optional[str]:
    """
    現在の親スパンIDを取得
    
    Returns:
        Optional[str]: 親スパンID、設定されていない場合はNone
    """
    context = get_current_trace_context()
    return context.parent_span_id if context else None


def is_sampled() -> bool:
    """
    現在のトレースがサンプリング対象かどうかを取得
    
    Returns:
        bool: サンプリング対象ならTrue、コンテキストがない場合はFalse
    """
    context = get_current_trace_context()
    return bool(context and context.trace_flags & 0x01)


def add_baggage_item(key: str, value: str):
    """
    バゲージアイテムを追加
    
    Args:
        key: キー
        value: 値
    """
    context = get_current_trace_context()
    if context:
        context.baggage[key] = value


def get_baggage_item(key: str) -> Optional[str]:
    """
    バゲージアイテムを取得
    
    Args:
        key: キー
        
    Returns:
        Optional[str]: 値、存在しない場合はNone
    """
    context = get_current_trace_context()
    if context and key in context.baggage:
        return context.baggage[key]
    return None


def get_all_baggage() -> Dict[str, str]:
    """
    すべてのバゲージアイテムを取得
    
    Returns:
        Dict[str, str]: バゲージアイテム、コンテキストがない場合は空辞書
    """
    context = get_current_trace_context()
    return context.baggage.copy() if context else {} 