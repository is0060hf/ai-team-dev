"""
設定管理モジュール。環境変数からアプリケーション設定を読み込みます。
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()


class Config:
    """設定管理クラス。環境変数から設定を読み込み、提供します。"""

    # OpenAI API設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # エージェント設定
    AGENT_COUNT: int = int(os.getenv("AGENT_COUNT", "1"))

    # LLM設定
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    
    # データベース設定
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    
    # ストレージ設定
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./storage")
    
    # Web検索API設定
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")

    # オブザーバビリティ設定
    TRACE_LOG_SPANS: bool = os.getenv("TRACE_LOG_SPANS", "true").lower() in ("true", "1", "yes")
    ENABLE_DEFAULT_ALERTS: bool = os.getenv("ENABLE_DEFAULT_ALERTS", "true").lower() in ("true", "1", "yes")
    MONITORING_INTERVAL: int = int(os.getenv("MONITORING_INTERVAL", "60"))  # 秒単位
    
    # アラート通知設定
    ALERT_EMAIL_ENABLED: bool = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
    ALERT_EMAIL_SMTP_SERVER: Optional[str] = os.getenv("ALERT_EMAIL_SMTP_SERVER")
    ALERT_EMAIL_SMTP_PORT: int = int(os.getenv("ALERT_EMAIL_SMTP_PORT", "587"))
    ALERT_EMAIL_USERNAME: Optional[str] = os.getenv("ALERT_EMAIL_USERNAME")
    ALERT_EMAIL_PASSWORD: Optional[str] = os.getenv("ALERT_EMAIL_PASSWORD")
    ALERT_EMAIL_FROM: Optional[str] = os.getenv("ALERT_EMAIL_FROM")
    ALERT_EMAIL_TO: Optional[str] = os.getenv("ALERT_EMAIL_TO")
    
    ALERT_SLACK_ENABLED: bool = os.getenv("ALERT_SLACK_ENABLED", "false").lower() in ("true", "1", "yes")
    ALERT_SLACK_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_SLACK_WEBHOOK_URL")

    @classmethod
    def validate(cls) -> bool:
        """
        必須設定が正しく設定されているか検証します。
        
        Returns:
            bool: すべての必須設定が設定されていればTrue、そうでなければFalse
        """
        if not cls.OPENAI_API_KEY:
            print("エラー: OPENAI_API_KEYが設定されていません。")
            return False
        
        return True

    @classmethod
    def get_llm_config(cls) -> Dict[str, Any]:
        """
        LLM設定を辞書形式で取得します。
        
        Returns:
            Dict[str, Any]: LLM設定の辞書
        """
        return {
            "model": cls.MODEL_NAME,
            "api_key": cls.OPENAI_API_KEY,
        }
    
    @classmethod
    def get_alert_email_config(cls) -> Dict[str, Any]:
        """
        アラートメール設定を辞書形式で取得します。
        
        Returns:
            Dict[str, Any]: アラートメール設定の辞書
        """
        if not cls.ALERT_EMAIL_ENABLED:
            return {}
        
        to_addrs = cls.ALERT_EMAIL_TO.split(",") if cls.ALERT_EMAIL_TO else []
        
        return {
            "smtp_server": cls.ALERT_EMAIL_SMTP_SERVER,
            "smtp_port": cls.ALERT_EMAIL_SMTP_PORT,
            "username": cls.ALERT_EMAIL_USERNAME,
            "password": cls.ALERT_EMAIL_PASSWORD,
            "from_addr": cls.ALERT_EMAIL_FROM,
            "to_addrs": to_addrs,
            "use_tls": True
        }
    
    @classmethod
    def get_alert_slack_config(cls) -> Dict[str, Any]:
        """
        アラートSlack設定を辞書形式で取得します。
        
        Returns:
            Dict[str, Any]: アラートSlack設定の辞書
        """
        if not cls.ALERT_SLACK_ENABLED:
            return {}
        
        return {
            "webhook_url": cls.ALERT_SLACK_WEBHOOK_URL,
            "timeout": 10
        }


# 設定のエクスポート
config = Config() 