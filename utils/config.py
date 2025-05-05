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


# 設定のエクスポート
config = Config() 