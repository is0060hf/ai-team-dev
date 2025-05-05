"""
PdM（プロダクトマネージャー）エージェントモジュール。
プロダクトオーナーからの要求を理解・分析し、プロダクトバックログの作成を担当します。
"""

import re
import json
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pdm")


class RequirementAnalysisTool(Tool):
    """要求分析ツール"""
    
    name = "要求分析"
    description = "ユーザーの要求を分析し、その主要なポイント、制約、ユースケースなどを抽出します。"
    
    def _run(self, request: str) -> str:
        """
        ユーザーの要求を分析します。
        
        Args:
            request: ユーザーからの要求文
            
        Returns:
            str: 分析結果
        """
        logger.info("要求分析ツールが呼び出されました。")
        
        analysis_template = """
        # 要求分析レポート

        ## 要約
        {summary}

        ## 主要機能
        {features}

        ## 非機能要件
        {non_functional}

        ## ユーザー層
        {users}

        ## 制約条件
        {constraints}

        ## ビジネス目標
        {business_goals}

        ## リスクと考慮事項
        {risks}
        """
        
        # 実際のプロジェクトでは、ここでLLMを使用して要求を分析する
        # 現段階ではテンプレートとしてのみ返す
        return analysis_template.format(
            summary="[要約をここに記述]",
            features="[主要機能をここに箇条書きで記述]",
            non_functional="[非機能要件をここに記述]",
            users="[想定ユーザー層をここに記述]",
            constraints="[制約条件をここに記述]",
            business_goals="[ビジネス目標をここに記述]",
            risks="[リスクと考慮事項をここに記述]"
        )


class BacklogItemGeneratorTool(Tool):
    """バックログ項目生成ツール"""
    
    name = "バックログ項目生成"
    description = "ユーザーの要求から具体的なバックログ項目（ユーザーストーリー形式）を生成します。"
    
    def _run(self, requirements: str) -> str:
        """
        要求からバックログ項目を生成します。
        
        Args:
            requirements: 要求の分析結果
            
        Returns:
            str: バックログ項目（JSON形式）
        """
        logger.info("バックログ項目生成ツールが呼び出されました。")
        
        # サンプルのバックログ項目を返す
        # 実際のプロジェクトでは、ここでLLMを使用してバックログ項目を生成する
        backlog_items = [
            {
                "id": "US001",
                "title": "ユーザーストーリー1",
                "description": "ユーザーとして、〜ができる必要がある。それによって〜という価値が得られる。",
                "acceptance_criteria": [
                    "条件1が満たされていること",
                    "条件2が満たされていること",
                    "条件3が満たされていること"
                ],
                "estimated_effort": "M",
                "priority": 0,  # 優先順位は後で設定される
                "dependencies": []
            },
            {
                "id": "US002",
                "title": "ユーザーストーリー2",
                "description": "ユーザーとして、〜ができる必要がある。それによって〜という価値が得られる。",
                "acceptance_criteria": [
                    "条件1が満たされていること",
                    "条件2が満たされていること"
                ],
                "estimated_effort": "S",
                "priority": 0,
                "dependencies": ["US001"]
            }
        ]
        
        return json.dumps(backlog_items, ensure_ascii=False, indent=2)


class PriorityRankingTool(Tool):
    """優先順位付けツール"""
    
    name = "優先順位付け"
    description = "バックログ項目に優先順位を付けます。ビジネス価値、技術的な依存関係、リスクなどを考慮します。"
    
    def _run(self, backlog_items_json: str) -> str:
        """
        バックログ項目に優先順位を付けます。
        
        Args:
            backlog_items_json: バックログ項目（JSON形式）
            
        Returns:
            str: 優先順位付きバックログ項目（JSON形式）
        """
        logger.info("優先順位付けツールが呼び出されました。")
        
        try:
            backlog_items = json.loads(backlog_items_json)
            
            # 優先順位を付ける（実際のプロジェクトではLLMを使用してより高度な優先順位付けを行う）
            for i, item in enumerate(backlog_items):
                # 単純な例として、IDの順番に優先順位を付ける
                item["priority"] = len(backlog_items) - i
                
                # 依存関係がある場合、依存先より高い優先順位にならないように調整
                if item["dependencies"]:
                    for dep_id in item["dependencies"]:
                        for dep_item in backlog_items:
                            if dep_item["id"] == dep_id and dep_item["priority"] < item["priority"]:
                                item["priority"] = dep_item["priority"] - 1
                                
            # 優先順位に基づいてソート（高い順）
            backlog_items.sort(key=lambda x: x["priority"], reverse=True)
            
            return json.dumps(backlog_items, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: バックログ項目の優先順位付けに失敗しました: {str(e)}"


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
    
    # PdM固有のツールを追加
    pdm_specific_tools = [
        RequirementAnalysisTool(),
        BacklogItemGeneratorTool(),
        PriorityRankingTool(),
    ]
    
    all_tools = tools + pdm_specific_tools
    
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
        tools=all_tools,
        allow_delegation=False,  # PdMは基本的に下位エージェントに委任しない
    )
    
    return pdm_agent


def analyze_requirements(agent: Agent, request: str) -> Dict[str, Any]:
    """
    要求を分析し、その結果を返します。
    
    Args:
        agent: PdMエージェント
        request: ユーザーからの要求
        
    Returns:
        Dict[str, Any]: 分析結果
    """
    logger.info("要求分析を開始します。")
    
    # 要求分析タスクの実行
    analysis_task = Task(
        description="ユーザーの要求を分析し、主要なポイント、制約、ユースケースなどを抽出してください。",
        expected_output="要求分析レポート",
        agent=agent
    )
    
    analysis_result = agent.execute_task(analysis_task, context={"request": request})
    
    logger.info("要求分析が完了しました。")
    return {"analysis": analysis_result}


def generate_backlog(agent: Agent, requirements_analysis: str) -> Dict[str, Any]:
    """
    バックログ項目を生成します。
    
    Args:
        agent: PdMエージェント
        requirements_analysis: 要求分析の結果
        
    Returns:
        Dict[str, Any]: バックログ項目
    """
    logger.info("バックログ項目生成を開始します。")
    
    # バックログ項目生成タスクの実行
    backlog_task = Task(
        description="要求分析に基づいて、具体的なバックログ項目（ユーザーストーリー形式）を生成してください。",
        expected_output="バックログ項目（JSON形式）",
        agent=agent
    )
    
    backlog_result = agent.execute_task(backlog_task, context={"requirements_analysis": requirements_analysis})
    
    # バックログ項目がJSON形式で返ってきた場合はパースする
    try:
        backlog_items = json.loads(backlog_result)
        backlog_result = backlog_items
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("バックログ項目生成が完了しました。")
    return {"backlog": backlog_result}


def prioritize_backlog(agent: Agent, backlog_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    バックログ項目に優先順位を付けます。
    
    Args:
        agent: PdMエージェント
        backlog_items: バックログ項目のリスト
        
    Returns:
        Dict[str, Any]: 優先順位付きバックログ項目
    """
    logger.info("バックログ項目の優先順位付けを開始します。")
    
    # JSONでない場合はJSON形式に変換
    if not isinstance(backlog_items, str):
        backlog_items_json = json.dumps(backlog_items, ensure_ascii=False)
    else:
        backlog_items_json = backlog_items
    
    # 優先順位付けタスクの実行
    priority_task = Task(
        description="バックログ項目に優先順位を付けてください。ビジネス価値、技術的な依存関係、リスクなどを考慮してください。",
        expected_output="優先順位付きバックログ項目（JSON形式）",
        agent=agent
    )
    
    priority_result = agent.execute_task(priority_task, context={"backlog_items": backlog_items_json})
    
    # 優先順位付きバックログ項目がJSON形式で返ってきた場合はパースする
    try:
        prioritized_backlog = json.loads(priority_result)
        priority_result = prioritized_backlog
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("バックログ項目の優先順位付けが完了しました。")
    return {"prioritized_backlog": priority_result} 