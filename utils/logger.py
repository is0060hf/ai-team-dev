"""
構造化ロギングをサポートするモジュール。アプリケーションの詳細なロギング機能を提供します。
"""

import logging
import os
import sys
import json
import uuid
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

from utils.config import config

# ログレベルのマッピング
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredLogFormatter(logging.Formatter):
    """構造化ログのフォーマッタ"""
    
    def __init__(self, include_trace_info: bool = True):
        """
        Args:
            include_trace_info: トレース情報を含めるかどうか
        """
        super().__init__()
        self.include_trace_info = include_trace_info
        self.hostname = socket.gethostname()
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードを構造化されたJSON形式に変換"""
        # 基本的なログ情報
        structured_log = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
            "thread_name": threading.current_thread().name,
            "hostname": self.hostname,
        }
        
        # 例外情報があれば追加
        if record.exc_info:
            structured_log["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # 追加されたコンテキスト情報があれば追加
        if hasattr(record, "context") and record.context:
            structured_log["context"] = record.context
        
        # トレース情報があれば追加
        if self.include_trace_info and hasattr(record, "trace_id"):
            structured_log["trace_id"] = record.trace_id
            if hasattr(record, "span_id"):
                structured_log["span_id"] = record.span_id
            if hasattr(record, "parent_span_id"):
                structured_log["parent_span_id"] = record.parent_span_id
        
        return json.dumps(structured_log)


class StructuredLogger(logging.Logger):
    """構造化ロギングをサポートするロガークラス"""
    
    def __init__(self, name: str, level: int = logging.NOTSET):
        """
        Args:
            name: ロガー名
            level: ログレベル
        """
        super().__init__(name, level)
        self._trace_id = None
        self._span_id = None
        self._parent_span_id = None
    
    def _log_with_context(
        self, 
        level: int, 
        msg: str, 
        args: tuple, 
        exc_info: Optional[Exception] = None, 
        extra: Optional[Dict[str, Any]] = None, 
        stack_info: bool = False, 
        context: Optional[Dict[str, Any]] = None
    ):
        """コンテキスト情報を含めてログを記録"""
        # 追加のコンテキスト情報を設定
        extra = extra or {}
        if context:
            extra["context"] = context
        
        # トレース情報があれば追加
        if self._trace_id:
            extra["trace_id"] = self._trace_id
            extra["span_id"] = self._span_id
            if self._parent_span_id:
                extra["parent_span_id"] = self._parent_span_id
        
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
    
    def set_trace_info(self, trace_id: str, span_id: str, parent_span_id: Optional[str] = None):
        """トレース情報を設定"""
        self._trace_id = trace_id
        self._span_id = span_id
        self._parent_span_id = parent_span_id


def setup_logger(name: str = "ai_team", structured: bool = True) -> Union[logging.Logger, StructuredLogger]:
    """
    ロガーを設定し返します。
    
    Args:
        name: ロガー名
        structured: 構造化ロギングを使用するかどうか
        
    Returns:
        Union[logging.Logger, StructuredLogger]: 設定済みロガー
    """
    # ロガーの作成
    if structured:
        logging.setLoggerClass(StructuredLogger)
        logger = logging.getLogger(name)
        logging.setLoggerClass(logging.Logger)  # リセット
    else:
        logger = logging.getLogger(name)
    
    # 既存のハンドラをクリア
    if logger.handlers:
        logger.handlers.clear()
    
    # ログレベルの設定
    log_level = LOG_LEVELS.get(config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # フォーマッタの設定
    if structured:
        formatter = StructuredLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # コンソールハンドラの追加
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ログディレクトリの作成
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # 構造化ログ用のJSONファイルハンドラ
    if structured:
        json_log_file = logs_dir / f"{name}_structured_{datetime.now().strftime('%Y%m%d')}.json"
        json_handler = logging.FileHandler(json_log_file)
        json_handler.setLevel(log_level)
        json_handler.setFormatter(formatter)
        logger.addHandler(json_handler)
    
    # 通常のログファイルハンドラ
    log_file = logs_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    
    # 通常のログファイルにはテキスト形式のフォーマッタを使用
    text_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(text_formatter)
    
    logger.addHandler(file_handler)
    
    return logger


# デフォルトロガーの作成
logger = setup_logger()


def get_agent_logger(agent_name: str, structured: bool = True) -> Union[logging.Logger, StructuredLogger]:
    """
    特定のエージェント用のロガーを取得します。
    
    Args:
        agent_name: エージェント名
        structured: 構造化ロギングを使用するかどうか
        
    Returns:
        Union[logging.Logger, StructuredLogger]: エージェント専用ロガー
    """
    return setup_logger(f"ai_team.{agent_name}", structured)


def get_request_logger(request_id: Optional[str] = None) -> StructuredLogger:
    """
    リクエスト処理用のロガーを取得します。
    
    Args:
        request_id: リクエストID（Noneの場合は自動生成）
        
    Returns:
        StructuredLogger: リクエスト専用ロガー
    """
    request_id = request_id or str(uuid.uuid4())
    logger = setup_logger(f"ai_team.request.{request_id}")
    
    if isinstance(logger, StructuredLogger):
        # トレースIDとしてリクエストIDを設定
        logger.set_trace_info(
            trace_id=request_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=None
        )
    
    return logger


def get_structured_logger(name: str) -> StructuredLogger:
    """
    構造化ロギング用のロガーを取得します。
    
    Args:
        name: ロガー名
        
    Returns:
        StructuredLogger: 構造化ロガー
    """
    return setup_logger(name, structured=True) 