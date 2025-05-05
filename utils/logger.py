"""
ロギングモジュール。アプリケーションのロギング機能を提供します。
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from utils.config import config

# ログレベルのマッピング
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logger(name: str = "ai_team") -> logging.Logger:
    """
    ロガーを設定し返します。
    
    Args:
        name: ロガー名
        
    Returns:
        logging.Logger: 設定済みロガー
    """
    # ロガーの作成
    logger = logging.getLogger(name)
    
    # 既存のハンドラをクリア
    if logger.handlers:
        logger.handlers.clear()
    
    # ログレベルの設定
    log_level = LOG_LEVELS.get(config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # コンソールハンドラの追加
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # フォーマッタの設定
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # ハンドラの追加
    logger.addHandler(console_handler)
    
    # ファイルハンドラの追加（ログファイルへの出力）
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    log_file = logs_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger


# デフォルトロガーの作成
logger = setup_logger()


def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    特定のエージェント用のロガーを取得します。
    
    Args:
        agent_name: エージェント名
        
    Returns:
        logging.Logger: エージェント専用ロガー
    """
    return setup_logger(f"ai_team.{agent_name}") 