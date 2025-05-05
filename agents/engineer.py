"""
エンジニアエージェントモジュール。
PLからの指示に基づき、実装、単体テスト、デバッグを担当します。
"""

from typing import List, Optional
from crewai import Agent
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("engineer")


def create_engineer_agent(tools: Optional[List[Tool]] = None, agent_id: int = 1) -> Agent:
    """
    エンジニアエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        agent_id: エージェントの識別子（複数のエンジニアエージェントを区別するため）
        
    Returns:
        Agent: 設定されたエンジニアエージェント
    """
    logger.info(f"エンジニアエージェント {agent_id} を作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # エンジニアエージェントの作成
    engineer_agent = Agent(
        role=f"ソフトウェアエンジニア {agent_id}",
        goal="PLからの指示に基づき、担当機能のコーディング、単体テスト、デバッグを行う。技術的な課題解決に取り組む。",
        backstory=f"""
        あなたは、幅広い開発経験を持つソフトウェアエンジニア {agent_id} です。
        複数のプログラミング言語とフレームワークに精通し、フロントエンドからバックエンド、データベース、
        インフラまで、フルスタックな開発スキルを持っています。コードの品質と保守性を重視し、単体テストを
        徹底して実施することで堅牢なシステムを構築します。技術的な課題に対して創造的な解決策を提案し、
        実装することができます。チームでの協業経験が豊富で、PLやデザイナーと緊密に連携しながら効率的に
        開発を進める能力を持っています。継続的に新しい技術を学び、実践に活かしています。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=False,  # エンジニアは基本的に下位エージェントに委任しない
    )
    
    return engineer_agent 