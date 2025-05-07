"""
アプリケーション設定を管理するモジュール。
環境変数や設定ファイルからの設定値読み込みを行います。
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Set
from pathlib import Path

# 設定デフォルト値
DEFAULT_CONFIG = {
    # 基本設定
    "ENV": "development",
    "DEBUG": True,
    "LOG_LEVEL": "DEBUG",
    "TRACE_LOG_SPANS": True,
    
    # APIエージェント設定
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "GOOGLE_API_KEY": "",
    "AI_MODEL": "gpt-4o-mini",
    
    # 外部サービス
    "SERPER_API_KEY": "",
    
    # ストレージパス
    "ARTIFACTS_DIR": "artifacts",
    "LOGS_DIR": "logs",
    "STORAGE_DIR": "storage",
    
    # アラート設定
    "ENABLE_DEFAULT_ALERTS": True,
    
    # トレース設定
    "ENABLE_EXTERNAL_TRACE_STORAGE": True,
    "ENABLE_TRACE_EXPORT": False,
    "TRACE_EXPORT_BATCH_SIZE": 10,
    "TRACE_RETENTION_DAYS": 30,
    "TRACE_EXPORTERS": [
        # {
        #     "type": "jaeger",
        #     "host": "localhost",
        #     "port": 14268
        # },
        # {
        #     "type": "zipkin",
        #     "host": "localhost",
        #     "port": 9411
        # },
        # {
        #     "type": "otlp",
        #     "host": "localhost",
        #     "port": 4318
        # },
        # {
        #     "type": "cloud_trace",
        #     "project_id": "your-gcp-project-id",
        #     "credentials_path": "/path/to/credentials.json"
        # }
    ],
    
    # メトリクス設定
    "ENABLE_METRICS_COLLECTION": True,
    "METRICS_COLLECTION_INTERVAL": 30,  # 秒
    "METRICS_RETENTION_DAYS": 30,
    "ENABLE_METRICS_EXPORT": False,
    "METRICS_EXPORTERS": [
        # {
        #     "type": "prometheus",
        #     "port": 9090
        # },
        # {
        #     "type": "influxdb",
        #     "host": "localhost",
        #     "port": 8086,
        #     "token": "",
        #     "org": "ai_team",
        #     "bucket": "metrics"
        # }
    ],
    
    # ロギング設定
    "LOG_FORMAT": "structured",  # structured or text
    "LOG_RETENTION_DAYS": 30,
    "ENABLE_LOG_EXPORT": False,
    "ENABLE_LOG_ROTATION": True,
    "LOG_ROTATION_INTERVAL": "1d",  # 1d, 1w, 1m
    "LOG_ARCHIVE_FORMAT": "gzip",   # gzip, zip, none
    "LOG_EXPORTERS": [
        # {
        #     "type": "elasticsearch",
        #     "host": "localhost",
        #     "port": 9200,
        #     "index_prefix": "ai_team_logs"
        # },
        # {
        #     "type": "loki",
        #     "host": "localhost",
        #     "port": 3100
        # }
    ],
    
    # ダッシュボード設定
    "DASHBOARD_HOST": "0.0.0.0",
    "DASHBOARD_PORT": 8050,
    "API_HOST": "0.0.0.0",
    "API_PORT": 8000,
    "ENABLE_METRICS_DASHBOARD": True,
    "ENABLE_TRACES_DASHBOARD": True,
    "ENABLE_LOGS_DASHBOARD": True,
    
    # カスタム設定
    "ENABLE_SPECIALIST_AGENT_DASHBOARD": True,
    "ENABLE_AGENT_SCALING": True
}


class Config:
    """アプリケーション設定クラス"""
    
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load_config()
    
    def _load_config(self):
        """環境変数および設定ファイルから設定値を読み込む"""
        # 環境変数からの読み込み
        for key in self._config.keys():
            env_value = os.environ.get(key)
            if env_value is not None:
                self._parse_config_value(key, env_value)
        
        # 設定ファイルからの読み込み（存在する場合）
        config_file = os.environ.get("CONFIG_FILE", "config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                for key, value in file_config.items():
                    if key in self._config:
                        self._config[key] = value
    
    def _parse_config_value(self, key: str, value: str):
        """
        環境変数値を適切な型に変換
        
        Args:
            key: 設定キー
            value: 文字列値
        """
        current_value = self._config.get(key)
        
        if isinstance(current_value, bool):
            # 真偽値の場合
            self._config[key] = value.lower() in ("true", "1", "yes", "y", "t")
        elif isinstance(current_value, int):
            # 整数の場合
            try:
                self._config[key] = int(value)
            except ValueError:
                pass
        elif isinstance(current_value, float):
            # 浮動小数点の場合
            try:
                self._config[key] = float(value)
            except ValueError:
                pass
        elif isinstance(current_value, list):
            # リストの場合はJSONとして解析
            try:
                parsed_value = json.loads(value)
                if isinstance(parsed_value, list):
                    self._config[key] = parsed_value
            except json.JSONDecodeError:
                # カンマ区切りと仮定
                self._config[key] = [item.strip() for item in value.split(",")]
        elif isinstance(current_value, dict):
            # 辞書の場合
            try:
                parsed_value = json.loads(value)
                if isinstance(parsed_value, dict):
                    self._config[key] = parsed_value
            except json.JSONDecodeError:
                pass
        else:
            # その他の場合は文字列として設定
            self._config[key] = value
    
    def __getattr__(self, name: str) -> Any:
        """
        設定値へのアクセサ
        
        Args:
            name: 設定キー
            
        Returns:
            Any: 設定値
        
        Raises:
            AttributeError: 設定キーが存在しない場合
        """
        if name in self._config:
            return self._config[name]
        raise AttributeError(f"設定 '{name}' は定義されていません")
    
    def update(self, key: str, value: Any):
        """
        設定値を更新
        
        Args:
            key: 設定キー
            value: 設定値
        """
        if key in self._config:
            self._config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        すべての設定値を取得
        
        Returns:
            Dict[str, Any]: 全設定値の辞書
        """
        return self._config.copy()


# 設定のシングルトンインスタンス
config = Config()


def get_config() -> Config:
    """
    設定インスタンスを取得
    
    Returns:
        Config: 設定インスタンス
    """
    return config 