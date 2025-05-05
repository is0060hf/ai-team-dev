"""
PdM（プロダクトマネージャー）エージェントモジュール。
プロダクトオーナーからの要求を理解・分析し、プロダクトバックログの作成を担当します。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pdm")


def create_pdm_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    PdM（プロダクトマネージャー）エージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたPdMエージェント
    """
    logger.info("PdMエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # PdMエージェントの作成
    pdm_agent = Agent(
        role="プロダクトマネージャー",
        goal="プロダクトオーナーの要求を理解・分析し、具体的なプロダクトバックログ項目に落とし込む。要求の優先順位付けを行う。",
        backstory="""
        あなたは、優れた分析力と市場洞察力を持つプロダクトマネージャー（PdM）です。
        プロダクトオーナーの要求や市場ニーズを深く理解し、それを具体的な機能要件に変換する専門家です。
        ユーザーストーリーの作成と優先順位付けに長けており、複雑な要求も明確に整理することができます。
        プロダクトの価値を最大化するため、市場調査や競合分析を行い、戦略的な判断を下します。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=False,  # PdMは基本的に下位エージェントに委任しない
    )
    
    return pdm_agent 