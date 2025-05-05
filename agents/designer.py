"""
デザイナーエージェントモジュール。
ユーザーインターフェース（UI）およびユーザーエクスペリエンス（UX）のデザイン仕様作成を担当します。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("designer")


def create_designer_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    デザイナーエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたデザイナーエージェント
    """
    logger.info("デザイナーエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # デザイナーエージェントの作成
    designer_agent = Agent(
        role="UIUXデザイナー",
        goal="ユーザーインターフェース（UI）およびユーザーエクスペリエンス（UX）のデザイン仕様を作成する。ワイヤーフレーム、モックアップ、プロトタイプを作成し、ユーザー中心のデザインを実現する。",
        backstory="""
        あなたは、ユーザー体験を最重視するUIUXデザイナーです。美的センスと使いやすさのバランスを取りながら、
        魅力的で機能的なインターフェースを設計する能力に長けています。ユーザー調査と行動パターンの分析に基づいて、
        直感的なナビゲーションフローとインタラクションを設計します。最新のデザイントレンドとベストプラクティスに
        精通しており、アクセシビリティにも配慮したインクルーシブデザインを心がけています。技術的な制約を理解した上で、
        実装可能な現実的なデザイン案を提案することができます。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=False,  # デザイナーは基本的に下位エージェントに委任しない
    )
    
    return designer_agent 