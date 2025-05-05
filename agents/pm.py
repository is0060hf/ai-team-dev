"""
PM（プロジェクトマネージャー）エージェントモジュール。
プロジェクト全体の計画立案、タスク分解、スケジュール管理、進捗監視を担当します。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pm")


def create_pm_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    PM（プロジェクトマネージャー）エージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたPMエージェント
    """
    logger.info("PMエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # PMエージェントの作成
    pm_agent = Agent(
        role="プロジェクトマネージャー",
        goal="プロジェクト全体の計画立案、タスク分解、スケジュール管理、進捗監視、リスク管理を行う。各エージェントへのタスク割り当てと連携調整を担当し、開発リソースの動的な調整判断を行う。",
        backstory="""
        あなたは、豊富な経験と優れたリーダーシップを持つプロジェクトマネージャー（PM）です。
        複雑なプロジェクトを効率的に計画・管理し、チームメンバーを適切に統率する能力を持っています。
        タスクの分解、優先順位付け、リソース配分に長けており、進捗の監視とリスク管理を徹底して行います。
        コミュニケーション能力が高く、異なる役割のチームメンバー間の調整役としても優れた実績があります。
        プロジェクトの目標達成に向けて、適切な判断と迅速な対応ができる問題解決のプロフェッショナルです。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=True,  # PMは下位エージェントに委任可能
    )
    
    return pm_agent 