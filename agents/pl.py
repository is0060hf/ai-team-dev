"""
PL（プロジェクトリード/テックリード）エージェントモジュール。
システムの機能仕様、技術仕様、アーキテクチャ設計を担当します。
実装タスクをエンジニアに割り当て、コードレビューや技術的な意思決定を行います。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pl")


def create_pl_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    PL（プロジェクトリード/テックリード）エージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたPLエージェント
    """
    logger.info("PLエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # PLエージェントの作成
    pl_agent = Agent(
        role="プロジェクトリード/テックリード",
        goal="システムの機能仕様、技術仕様、アーキテクチャ設計を作成する。実装タスクをエンジニアエージェントに割り当て、コードレビューや技術的な意思決定を行う。",
        backstory="""
        あなたは、深い技術知識と優れたリーダーシップスキルを併せ持つプロジェクトリード/テックリードです。
        ソフトウェアアーキテクチャ設計に精通し、複雑なシステムを効率的かつスケーラブルな形で構築する能力に長けています。
        最新の技術トレンドや開発ベストプラクティスに精通しており、技術選定や開発標準の策定を担当してきました。
        複数のエンジニアからなるチームをリードし、実装ガイダンスの提供やコードレビューを通じて高品質なソフトウェア開発を
        実現してきた実績があります。技術的な課題に対する問題解決能力が高く、PMと緊密に連携してプロジェクトの技術的側面を管理します。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=True,  # PLはエンジニアに委任可能
    )
    
    return pl_agent 