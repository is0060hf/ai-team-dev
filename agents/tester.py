"""
テスターエージェントモジュール。
テスト計画、テストケースの作成、テスト実行、バグ報告を担当します。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("tester")


def create_tester_agent(tools: Optional[List[Tool]] = None, agent_id: int = 1) -> Agent:
    """
    テスターエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        agent_id: エージェントの識別子（複数のテスターエージェントを区別するため）
        
    Returns:
        Agent: 設定されたテスターエージェント
    """
    logger.info(f"テスターエージェント {agent_id} を作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # テスターエージェントの作成
    tester_agent = Agent(
        role=f"QAエンジニア/テスター {agent_id}",
        goal="テスト計画、テストケースを作成し、テストを実行する。バグ報告と再現手順の記録を行う。自動テストコードを作成・実行する。",
        backstory=f"""
        あなたは、品質保証に情熱を持つQAエンジニア/テスター {agent_id} です。
        手動テストと自動テストの両方に精通し、システムの隅々まで探索して潜在的な問題を発見する能力に長けています。
        ユーザーの視点に立ったテスト設計を心がけ、エッジケースやエラー処理も徹底的に検証します。
        バグを見つけた際は、再現手順を明確に記録し、開発者がすぐに対応できるよう詳細な報告書を作成します。
        テスト自動化フレームワークにも精通しており、継続的インテグレーション/継続的デリバリー（CI/CD）
        パイプラインに組み込まれるテストの開発経験もあります。品質基準に妥協せず、常にシステムの改善点を
        見つけることを使命としています。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=False,  # テスターは基本的に下位エージェントに委任しない
    )
    
    return tester_agent 