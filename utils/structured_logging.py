"""
構造化ロギングモジュール。
アプリケーションログを構造化し、ログ管理システムとの連携機能を提供します。
"""

import os
import sys
import json
import logging
import logging.handlers
import threading
import time
import socket
import traceback
from enum import Enum
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime
from pathlib import Path

from utils.config import config
from utils.tracing import get_current_trace_id, get_current_span_id, get_parent_span_id

# ログレベルの文字列とロギングレベルのマッピング
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class LogFormat(Enum):
    """ログ出力フォーマットの種類"""
    JSON = "json"
    TEXT = "text"
    PRETTY = "pretty"


class StructuredLogRecord(logging.LogRecord):
    """構造化ログレコードクラス"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = socket.gethostname()
        self.context = getattr(self, "context", {})
        
        # トレース情報の追加
        self.trace_id = get_current_trace_id()
        self.span_id = get_current_span_id()
        self.parent_span_id = get_parent_span_id()


class StructuredFormatter(logging.Formatter):
    """構造化ログのフォーマッタ"""
    
    def __init__(
        self,
        format_type: LogFormat = LogFormat.JSON,
        additional_fields: Optional[Dict[str, Any]] = None
    ):
        """
        初期化
        
        Args:
            format_type: 出力フォーマット
            additional_fields: 追加のフィールド
        """
        super().__init__()
        self.format_type = format_type
        self.additional_fields = additional_fields or {}
        self.hostname = socket.gethostname()
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをフォーマット"""
        if self.format_type == LogFormat.JSON:
            return self._format_json(record)
        elif self.format_type == LogFormat.PRETTY:
            return self._format_pretty(record)
        else:
            return self._format_text(record)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """JSONフォーマット"""
        # 基本的なログ情報
        structured_log = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
            "thread_name": threading.current_thread().name,
            "hostname": getattr(record, "hostname", self.hostname),
        }
        
        # 追加のフィールドを追加
        structured_log.update(self.additional_fields)
        
        # 例外情報があれば追加
        if record.exc_info:
            structured_log["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # コンテキスト情報を追加
        if hasattr(record, "context") and record.context:
            structured_log["context"] = record.context
        
        # トレース情報があれば追加
        if hasattr(record, "trace_id") and record.trace_id:
            structured_log["trace_id"] = record.trace_id
            
            if hasattr(record, "span_id") and record.span_id:
                structured_log["span_id"] = record.span_id
                
                if hasattr(record, "parent_span_id") and record.parent_span_id:
                    structured_log["parent_span_id"] = record.parent_span_id
        
        # 環境に関する情報を追加
        structured_log["environment"] = getattr(config, "ENVIRONMENT", "development")
        
        return json.dumps(structured_log)
    
    def _format_text(self, record: logging.LogRecord) -> str:
        """テキストフォーマット"""
        base_msg = f"[{datetime.fromtimestamp(record.created).isoformat()}] [{record.levelname}] {record.getMessage()}"
        
        # トレース情報があれば追加
        trace_info = ""
        if hasattr(record, "trace_id") and record.trace_id:
            trace_info = f" [trace_id={record.trace_id[:8]}...]"
            
            if hasattr(record, "span_id") and record.span_id:
                trace_info += f" [span_id={record.span_id[:8]}...]"
        
        # コンテキスト情報を追加
        context_info = ""
        if hasattr(record, "context") and record.context:
            context_str = " ".join([f"{k}={v}" for k, v in record.context.items()])
            if context_str:
                context_info = f" [{context_str}]"
        
        # 例外情報を追加
        exc_info = ""
        if record.exc_info:
            exc_info = f"\n{self.formatException(record.exc_info)}"
        
        return f"{base_msg}{trace_info}{context_info}{exc_info}"
    
    def _format_pretty(self, record: logging.LogRecord) -> str:
        """読みやすいフォーマット"""
        # レベルに応じた色の設定
        level_colors = {
            "DEBUG": "\033[36m",     # シアン
            "INFO": "\033[32m",      # 緑
            "WARNING": "\033[33m",   # 黄
            "ERROR": "\033[31m",     # 赤
            "CRITICAL": "\033[35m",  # マゼンタ
        }
        reset_color = "\033[0m"
        level_color = level_colors.get(record.levelname, reset_color)
        
        # タイムスタンプ
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # 基本メッセージ
        base_msg = f"{timestamp} {level_color}{record.levelname:<8}{reset_color} {record.getMessage()}"
        
        # トレース情報
        trace_info = ""
        if hasattr(record, "trace_id") and record.trace_id:
            trace_id = record.trace_id[:8] + "..." if len(record.trace_id) > 8 else record.trace_id
            trace_info = f" \033[90m[trace_id={trace_id}]\033[0m"
        
        # ロガー名
        logger_info = f" \033[90m[{record.name}]\033[0m"
        
        # コンテキスト情報
        context_info = ""
        if hasattr(record, "context") and record.context:
            context_items = []
            for k, v in record.context.items():
                if isinstance(v, str) and len(v) > 20:
                    v = v[:17] + "..."
                context_items.append(f"{k}={v}")
            
            context_str = " ".join(context_items)
            if context_str:
                context_info = f" \033[90m[{context_str}]\033[0m"
        
        # ファイル情報
        file_info = f" \033[90m[{record.pathname}:{record.lineno}]\033[0m"
        
        # 例外情報
        exc_info = ""
        if record.exc_info:
            exc_info = f"\n\033[31m{self.formatException(record.exc_info)}\033[0m"
        
        return f"{base_msg}{logger_info}{trace_info}{context_info}{file_info}{exc_info}"


class StructuredLogger(logging.Logger):
    """構造化ロギングをサポートするロガークラス"""
    
    def __init__(self, name: str, level: int = logging.NOTSET):
        """
        初期化
        
        Args:
            name: ロガー名
            level: ログレベル
        """
        super().__init__(name, level)
        self._context = {}
    
    def _log_with_context(
        self, 
        level: int, 
        msg: str, 
        args: tuple, 
        exc_info=None, 
        extra: Optional[Dict[str, Any]] = None, 
        stack_info: bool = False, 
        context: Optional[Dict[str, Any]] = None
    ):
        """コンテキスト情報を含めてログを記録"""
        # 追加のコンテキスト情報を設定
        extra = extra or {}
        
        # ロガーのコンテキストを適用
        merged_context = self._context.copy()
        
        # メソッド呼び出し時のコンテキストを適用（優先）
        if context:
            merged_context.update(context)
        
        extra["context"] = merged_context
        
        # 標準のログメソッドを呼び出し
        super().log(level, msg, *args, exc_info=exc_info, extra=extra, stack_info=stack_info)
    
    def debug(self, msg: str, *args, **kwargs):
        """デバッグログを記録"""
        context = kwargs.pop("context", None)
        self._log_with_context(logging.DEBUG, msg, args, context=context, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """情報ログを記録"""
        context = kwargs.pop("context", None)
        self._log_with_context(logging.INFO, msg, args, context=context, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """警告ログを記録"""
        context = kwargs.pop("context", None)
        self._log_with_context(logging.WARNING, msg, args, context=context, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """エラーログを記録"""
        context = kwargs.pop("context", None)
        self._log_with_context(logging.ERROR, msg, args, context=context, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """重大エラーログを記録"""
        context = kwargs.pop("context", None)
        self._log_with_context(logging.CRITICAL, msg, args, context=context, **kwargs)
    
    def set_context(self, context: Dict[str, Any]):
        """
        ロガーのコンテキストを設定
        
        Args:
            context: コンテキスト情報
        """
        self._context = context.copy()
    
    def update_context(self, context: Dict[str, Any]):
        """
        ロガーのコンテキストを更新
        
        Args:
            context: 追加のコンテキスト情報
        """
        self._context.update(context)
    
    def clear_context(self):
        """ロガーのコンテキストをクリア"""
        self._context = {}


class RotatingTimeAndSizeHandler(logging.handlers.RotatingFileHandler):
    """時間とサイズの両方でローテーションするハンドラ"""
    
    def __init__(
        self,
        filename: str,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        encoding: Optional[str] = None,
        delay: bool = False,
        rotation_time: int = 24 * 60 * 60  # 1日（秒）
    ):
        """
        初期化
        
        Args:
            filename: ログファイル名
            max_bytes: 最大ファイルサイズ
            backup_count: バックアップファイル数
            encoding: エンコーディング
            delay: ファイルオープンを遅延するかどうか
            rotation_time: ローテーション間隔（秒）
        """
        super().__init__(
            filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay
        )
        self.rotation_time = rotation_time
        self.next_rotation_time = self._compute_next_rotation_time()
    
    def _compute_next_rotation_time(self) -> float:
        """次のローテーション時刻を計算"""
        current_time = time.time()
        # 現在時刻を rotation_time の倍数に切り上げ
        return current_time + self.rotation_time - (current_time % self.rotation_time)
    
    def shouldRollover(self, record: logging.LogRecord) -> int:
        """ローテーションが必要かどうかを判断"""
        # サイズベースのローテーションが必要か
        size_based = super().shouldRollover(record)
        if size_based:
            return True
        
        # 時間ベースのローテーションが必要か
        if time.time() >= self.next_rotation_time:
            self.next_rotation_time = self._compute_next_rotation_time()
            return True
        
        return False


def get_log_path(name: str, format_type: LogFormat) -> Path:
    """
    ログファイルのパスを取得
    
    Args:
        name: ロガー名
        format_type: ログフォーマットタイプ
    
    Returns:
        Path: ログファイルのパス
    """
    logs_dir = Path(getattr(config, "LOG_DIR", "logs"))
    logs_dir.mkdir(exist_ok=True)
    
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{name}_{date_str}"
    
    if format_type == LogFormat.JSON:
        filename += ".json"
    else:
        filename += ".log"
    
    return logs_dir / filename


def setup_structured_logger(
    name: str,
    level: Optional[str] = None,
    console_format: LogFormat = LogFormat.PRETTY,
    file_format: LogFormat = LogFormat.JSON,
    additional_fields: Optional[Dict[str, Any]] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    rotation_time: int = 24 * 60 * 60,  # 1日（秒）
    additional_handlers: Optional[List[logging.Handler]] = None
) -> StructuredLogger:
    """
    構造化ロガーを設定
    
    Args:
        name: ロガー名
        level: ログレベル
        console_format: コンソール出力のフォーマット
        file_format: ファイル出力のフォーマット
        additional_fields: 追加のフィールド
        max_file_size: 最大ファイルサイズ
        backup_count: バックアップファイル数
        rotation_time: ローテーション間隔（秒）
        additional_handlers: 追加のハンドラ
    
    Returns:
        StructuredLogger: 設定済みロガー
    """
    # カスタムログレコードファクトリを設定
    logging.setLogRecordFactory(StructuredLogRecord)
    
    # ロガークラスを設定して取得
    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)
    logging.setLoggerClass(logging.Logger)  # リセット
    
    # ログレベルの設定
    if level is None:
        level = getattr(config, "LOG_LEVEL", "INFO")
    
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 既存のハンドラをクリア
    if logger.handlers:
        logger.handlers.clear()
    
    # コンソールハンドラの設定
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(StructuredFormatter(
        format_type=console_format,
        additional_fields=additional_fields
    ))
    logger.addHandler(console_handler)
    
    # ファイルハンドラの設定
    file_path = get_log_path(name, file_format)
    file_handler = RotatingTimeAndSizeHandler(
        filename=str(file_path),
        max_bytes=max_file_size,
        backup_count=backup_count,
        rotation_time=rotation_time
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(StructuredFormatter(
        format_type=file_format,
        additional_fields=additional_fields
    ))
    logger.addHandler(file_handler)
    
    # 追加のハンドラがあれば登録
    if additional_handlers:
        for handler in additional_handlers:
            logger.addHandler(handler)
    
    return logger


# シングルトンのロガーマップ
_loggers = {}


def get_structured_logger(
    name: str,
    level: Optional[str] = None,
    console_format: LogFormat = LogFormat.PRETTY,
    file_format: LogFormat = LogFormat.JSON,
    additional_fields: Optional[Dict[str, Any]] = None
) -> StructuredLogger:
    """
    構造化ロガーを取得（シングルトン）
    
    Args:
        name: ロガー名
        level: ログレベル
        console_format: コンソール出力のフォーマット
        file_format: ファイル出力のフォーマット
        additional_fields: 追加のフィールド
    
    Returns:
        StructuredLogger: 構造化ロガー
    """
    global _loggers
    
    # 既存のロガーがあれば返す
    if name in _loggers:
        return _loggers[name]
    
    # ロガーを作成してキャッシュ
    logger = setup_structured_logger(
        name=name,
        level=level,
        console_format=console_format,
        file_format=file_format,
        additional_fields=additional_fields
    )
    
    _loggers[name] = logger
    return logger


# ELK（Elasticsearch, Logstash, Kibana）用のハンドラー
class ElasticSearchHandler(logging.Handler):
    """
    Elasticsearchにログを送信するハンドラ
    
    Logstash経由でElasticsearchにログを送信する場合は、
    Logstashが公開するHTTPエンドポイントを使用します。
    """
    
    def __init__(
        self,
        url: str,
        index: str = "logs",
        auth: Optional[Dict[str, str]] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
        level: int = logging.NOTSET,
        batch_size: int = 10,
        flush_interval: float = 5.0,
        max_retries: int = 3
    ):
        """
        初期化
        
        Args:
            url: Elasticsearch/LogstashのURL
            index: インデックス名
            auth: 認証情報（username, password）
            additional_fields: 追加のフィールド
            level: ログレベル
            batch_size: バッチサイズ
            flush_interval: フラッシュ間隔（秒）
            max_retries: 最大リトライ回数
        """
        super().__init__(level)
        self.url = url
        self.index = index
        self.auth = auth
        self.additional_fields = additional_fields or {}
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        
        # バッチ処理用の変数
        self.buffer = []
        self.buffer_lock = threading.RLock()
        self.last_flush = time.time()
        
        # 定期的なフラッシュのためのタイマー
        self.timer = None
        self._schedule_flush()
    
    def emit(self, record: logging.LogRecord):
        """ログレコードを処理"""
        try:
            # ログレコードをJSON形式に変換
            log_entry = self._format_record(record)
            
            with self.buffer_lock:
                # バッファに追加
                self.buffer.append(log_entry)
                
                # バッファサイズがバッチサイズ以上ならフラッシュ
                if len(self.buffer) >= self.batch_size:
                    self._flush()
        
        except Exception:
            self.handleError(record)
    
    def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """ログレコードをJSON形式に変換"""
        # 基本情報
        log_entry = {
            "@timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
            "thread_name": threading.current_thread().name,
            "hostname": getattr(record, "hostname", socket.gethostname()),
        }
        
        # 追加のフィールドを追加
        log_entry.update(self.additional_fields)
        
        # 例外情報があれば追加
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info))
            }
        
        # コンテキスト情報を追加
        if hasattr(record, "context") and record.context:
            log_entry["context"] = record.context
        
        # トレース情報があれば追加
        if hasattr(record, "trace_id") and record.trace_id:
            log_entry["trace_id"] = record.trace_id
            
            if hasattr(record, "span_id") and record.span_id:
                log_entry["span_id"] = record.span_id
                
                if hasattr(record, "parent_span_id") and record.parent_span_id:
                    log_entry["parent_span_id"] = record.parent_span_id
        
        # 環境情報を追加
        log_entry["environment"] = getattr(config, "ENVIRONMENT", "development")
        
        return log_entry
    
    def _flush(self):
        """バッファをフラッシュ"""
        if not self.buffer:
            return
        
        with self.buffer_lock:
            records = self.buffer.copy()
            self.buffer.clear()
        
        self.last_flush = time.time()
        
        # 非同期でElasticsearchに送信（スレッドプール使用）
        # スレッドプールはAPIやログ処理で共有されるため、念のため新しいスレッドを作成
        thread = threading.Thread(
            target=self._send_to_elasticsearch,
            args=(records,),
            daemon=True
        )
        thread.start()
    
    def _send_to_elasticsearch(self, records: List[Dict[str, Any]]):
        """ElasticsearchにログレコードをPOST"""
        import requests
        
        if not records:
            return
        
        # リトライ用のループ
        retries = 0
        while retries <= self.max_retries:
            try:
                # バルク送信用のデータを準備
                bulk_data = []
                
                for record in records:
                    # インデックス情報
                    bulk_data.append(json.dumps({
                        "index": {
                            "_index": self.index,
                        }
                    }))
                    
                    # ログデータ
                    bulk_data.append(json.dumps(record))
                
                # バルクAPIエンドポイント
                url = f"{self.url.rstrip('/')}/_bulk"
                
                # リクエストの準備
                headers = {"Content-Type": "application/x-ndjson"}
                auth = None
                
                if self.auth:
                    auth = (self.auth.get("username"), self.auth.get("password"))
                
                # POSTリクエスト
                response = requests.post(
                    url,
                    headers=headers,
                    auth=auth,
                    data="\n".join(bulk_data) + "\n",  # 最後に改行を追加
                    timeout=10
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    # 成功
                    return
                
                # エラーの場合はリトライ
                retries += 1
                if retries <= self.max_retries:
                    time.sleep(retries * 2)  # 指数バックオフ
            
            except Exception as e:
                # 例外が発生した場合もリトライ
                retries += 1
                if retries <= self.max_retries:
                    time.sleep(retries * 2)
                else:
                    # 最大リトライ回数を超えた場合はエラーログを出力
                    sys.stderr.write(f"Failed to send logs to Elasticsearch: {str(e)}\n")
    
    def _schedule_flush(self):
        """定期的なフラッシュを予約"""
        if hasattr(self, "_is_closing") and self._is_closing:
            return
        
        def _flush_and_reschedule():
            if hasattr(self, "_is_closing") and self._is_closing:
                return
            
            # 最後のフラッシュから一定時間経過していればフラッシュ
            if time.time() - self.last_flush >= self.flush_interval:
                self._flush()
            
            # 次のフラッシュを予約
            self._schedule_flush()
        
        # タイマーを設定
        self.timer = threading.Timer(self.flush_interval, _flush_and_reschedule)
        self.timer.daemon = True
        self.timer.start()
    
    def close(self):
        """ハンドラを閉じる"""
        self._is_closing = True
        
        # タイマーを停止
        if self.timer:
            self.timer.cancel()
        
        # 残りのログをフラッシュ
        self._flush()
        
        super().close()


def create_elk_handler(
    url: str,
    index: str = "logs",
    auth: Optional[Dict[str, str]] = None,
    additional_fields: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO
) -> ElasticSearchHandler:
    """
    ELK用のハンドラを作成
    
    Args:
        url: Elasticsearch/LogstashのURL
        index: インデックス名
        auth: 認証情報
        additional_fields: 追加のフィールド
        level: ログレベル
    
    Returns:
        ElasticSearchHandler: ELK用ハンドラ
    """
    handler = ElasticSearchHandler(
        url=url,
        index=index,
        auth=auth,
        additional_fields=additional_fields,
        level=level
    )
    
    return handler


def create_loki_handler(
    url: str,
    labels: Optional[Dict[str, str]] = None,
    auth: Optional[Dict[str, str]] = None,
    level: int = logging.INFO
) -> logging.Handler:
    """
    Loki用のハンドラを作成
    
    Args:
        url: LokiのURL
        labels: ラベル
        auth: 認証情報
        level: ログレベル
    
    Returns:
        logging.Handler: Loki用ハンドラ
    """
    # Loki用のHTTPハンドラを作成
    class LokiHandler(logging.Handler):
        """Lokiにログを送信するハンドラ"""
        
        def __init__(
            self,
            url: str,
            labels: Optional[Dict[str, str]] = None,
            auth: Optional[Dict[str, str]] = None,
            level: int = logging.NOTSET,
            batch_size: int = 10,
            flush_interval: float = 5.0,
            max_retries: int = 3
        ):
            """
            初期化
            
            Args:
                url: LokiのURL
                labels: ラベル
                auth: 認証情報
                level: ログレベル
                batch_size: バッチサイズ
                flush_interval: フラッシュ間隔（秒）
                max_retries: 最大リトライ回数
            """
            super().__init__(level)
            self.url = url
            self.labels = labels or {}
            self.auth = auth
            self.batch_size = batch_size
            self.flush_interval = flush_interval
            self.max_retries = max_retries
            
            # バッチ処理用の変数
            self.buffer = []
            self.buffer_lock = threading.RLock()
            self.last_flush = time.time()
            
            # 定期的なフラッシュのためのタイマー
            self.timer = None
            self._schedule_flush()
        
        def emit(self, record: logging.LogRecord):
            """ログレコードを処理"""
            try:
                # ログレコードをJSON形式に変換
                log_entry = self._format_record(record)
                
                with self.buffer_lock:
                    # バッファに追加
                    self.buffer.append(log_entry)
                    
                    # バッファサイズがバッチサイズ以上ならフラッシュ
                    if len(self.buffer) >= self.batch_size:
                        self._flush()
            
            except Exception:
                self.handleError(record)
        
        def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
            """ログレコードをLokiフォーマットに変換"""
            # ログメッセージの準備
            message = record.getMessage()
            
            # 例外情報があれば追加
            if record.exc_info:
                message += "\n" + self.formatter.formatException(record.exc_info)
            
            # ラベルの準備
            labels = {
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "hostname": getattr(record, "hostname", socket.gethostname()),
                "environment": getattr(config, "ENVIRONMENT", "development")
            }
            
            # ユーザー指定のラベルを追加
            labels.update(self.labels)
            
            # トレース情報があれば追加
            if hasattr(record, "trace_id") and record.trace_id:
                labels["trace_id"] = record.trace_id
                
                if hasattr(record, "span_id") and record.span_id:
                    labels["span_id"] = record.span_id
            
            # コンテキスト情報があればメッセージに追加
            if hasattr(record, "context") and record.context:
                context_json = json.dumps(record.context)
                message += f" {context_json}"
            
            # Lokiエントリの作成
            entry = {
                "stream": labels,
                "values": [[str(int(record.created * 1e9)), message]]
            }
            
            return entry
        
        def _flush(self):
            """バッファをフラッシュ"""
            if not self.buffer:
                return
            
            with self.buffer_lock:
                records = self.buffer.copy()
                self.buffer.clear()
            
            self.last_flush = time.time()
            
            # 非同期でLokiに送信
            thread = threading.Thread(
                target=self._send_to_loki,
                args=(records,),
                daemon=True
            )
            thread.start()
        
        def _send_to_loki(self, records: List[Dict[str, Any]]):
            """Lokiにログレコードを送信"""
            import requests
            
            if not records:
                return
            
            # リトライ用のループ
            retries = 0
            while retries <= self.max_retries:
                try:
                    # Loki Push APIのURLを構築
                    push_url = f"{self.url.rstrip('/')}/loki/api/v1/push"
                    
                    # Lokiフォーマットのリクエストボディを構築
                    request_body = {
                        "streams": records
                    }
                    
                    # リクエストヘッダ
                    headers = {"Content-Type": "application/json"}
                    
                    # 認証設定
                    auth = None
                    if self.auth:
                        auth = (self.auth.get("username"), self.auth.get("password"))
                    
                    # POSTリクエスト
                    response = requests.post(
                        push_url,
                        headers=headers,
                        auth=auth,
                        json=request_body,
                        timeout=10
                    )
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        # 成功
                        return
                    
                    # エラーの場合はリトライ
                    retries += 1
                    if retries <= self.max_retries:
                        time.sleep(retries * 2)  # 指数バックオフ
                
                except Exception as e:
                    # 例外が発生した場合もリトライ
                    retries += 1
                    if retries <= self.max_retries:
                        time.sleep(retries * 2)
                    else:
                        # 最大リトライ回数を超えた場合はエラーログを出力
                        sys.stderr.write(f"Failed to send logs to Loki: {str(e)}\n")
        
        def _schedule_flush(self):
            """定期的なフラッシュを予約"""
            if hasattr(self, "_is_closing") and self._is_closing:
                return
            
            def _flush_and_reschedule():
                if hasattr(self, "_is_closing") and self._is_closing:
                    return
                
                # 最後のフラッシュから一定時間経過していればフラッシュ
                if time.time() - self.last_flush >= self.flush_interval:
                    self._flush()
                
                # 次のフラッシュを予約
                self._schedule_flush()
            
            # タイマーを設定
            self.timer = threading.Timer(self.flush_interval, _flush_and_reschedule)
            self.timer.daemon = True
            self.timer.start()
        
        def close(self):
            """ハンドラを閉じる"""
            self._is_closing = True
            
            # タイマーを停止
            if self.timer:
                self.timer.cancel()
            
            # 残りのログをフラッシュ
            self._flush()
            
            super().close()
    
    # ハンドラを作成
    handler = LokiHandler(
        url=url,
        labels=labels,
        auth=auth,
        level=level
    )
    
    return handler 