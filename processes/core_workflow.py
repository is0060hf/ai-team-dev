"""
コアワークフローモジュール。
CrewAIのプロセスとタスクを定義し、エージェント間の連携フローを構築します。
"""

from typing import Dict, List, Any
from crewai import Task, Crew, Process

from utils.logger import logger
from agents.pdm import create_pdm_agent
from agents.pm import create_pm_agent
from agents.designer import create_designer_agent
from agents.pl import create_pl_agent
from agents.engineer import create_engineer_agent
from agents.tester import create_tester_agent


def create_basic_workflow(
    pdm_tools: List[Any] = None,
    pm_tools: List[Any] = None,
    designer_tools: List[Any] = None,
    pl_tools: List[Any] = None,
    engineer_tools: List[Any] = None,
    tester_tools: List[Any] = None,
    engineer_count: int = 1,
    tester_count: int = 1,
) -> Crew:
    """
    基本的なワークフローを持つCrewを作成します。
    
    Args:
        pdm_tools: PdMエージェントのツールリスト
        pm_tools: PMエージェントのツールリスト
        designer_tools: デザイナーエージェントのツールリスト
        pl_tools: PLエージェントのツールリスト
        engineer_tools: エンジニアエージェントのツールリスト
        tester_tools: テスターエージェントのツールリスト
        engineer_count: エンジニアエージェントの数
        tester_count: テスターエージェントの数
        
    Returns:
        Crew: 設定されたCrewオブジェクト
    """
    logger.info("基本ワークフローCrewを作成します。")
    
    # 各ツールリストの初期化
    if pdm_tools is None:
        pdm_tools = []
    if pm_tools is None:
        pm_tools = []
    if designer_tools is None:
        designer_tools = []
    if pl_tools is None:
        pl_tools = []
    if engineer_tools is None:
        engineer_tools = []
    if tester_tools is None:
        tester_tools = []
    
    # エージェントの作成
    pdm_agent = create_pdm_agent(tools=pdm_tools)
    pm_agent = create_pm_agent(tools=pm_tools)
    designer_agent = create_designer_agent(tools=designer_tools)
    pl_agent = create_pl_agent(tools=pl_tools)
    
    # 複数のエンジニアとテスターを作成
    engineer_agents = [
        create_engineer_agent(tools=engineer_tools, agent_id=i+1)
        for i in range(engineer_count)
    ]
    
    tester_agents = [
        create_tester_agent(tools=tester_tools, agent_id=i+1)
        for i in range(tester_count)
    ]
    
    # 全エージェントのリスト
    all_agents = [pdm_agent, pm_agent, designer_agent, pl_agent] + engineer_agents + tester_agents
    
    # タスクの定義
    tasks = []
    
    # 1. PdMが要求分析を行う
    pdm_task = Task(
        description="プロダクトオーナーの要求を分析し、プロダクトバックログを作成する。要求の優先順位付けを行う。",
        agent=pdm_agent,
        expected_output="プロダクトバックログ（機能要件リスト）と優先順位"
    )
    tasks.append(pdm_task)
    
    # 2. PMがプロジェクト計画を立てる
    pm_task = Task(
        description="プロダクトバックログに基づいて、プロジェクト計画を立案する。タスクを分解し、スケジュールを作成する。",
        agent=pm_agent,
        context=[
            {
                "role": "PdM",
                "input": "プロダクトバックログと優先順位に基づいて、プロジェクト計画を立案してください。"
            }
        ],
        expected_output="プロジェクト計画書（タスク分解、スケジュール、担当者割り当て）"
    )
    tasks.append(pm_task)
    
    # 3. デザイナーがUI/UX設計を行う
    designer_task = Task(
        description="プロダクトバックログとプロジェクト計画に基づいて、UI/UXデザインを作成する。ワイヤーフレームやモックアップを含める。",
        agent=designer_agent,
        context=[
            {
                "role": "PM",
                "input": "UI/UXデザインを作成してください。ユーザーフレンドリーで直感的なインターフェースが求められています。"
            }
        ],
        expected_output="UI/UXデザイン仕様書（ワイヤーフレーム、デザインガイドライン）"
    )
    tasks.append(designer_task)
    
    # 4. PLが技術仕様を作成する
    pl_task = Task(
        description="UI/UXデザインとプロダクトバックログに基づいて、技術仕様とアーキテクチャ設計を行う。実装タスクをエンジニアに割り当てる。",
        agent=pl_agent,
        context=[
            {
                "role": "デザイナー",
                "input": "UI/UXデザイン仕様書に基づいて、技術仕様を作成してください。"
            },
            {
                "role": "PM",
                "input": "プロジェクト計画に沿った技術仕様とアーキテクチャ設計を行ってください。"
            }
        ],
        expected_output="技術仕様書とアーキテクチャ設計書、実装タスク一覧"
    )
    tasks.append(pl_task)
    
    # 5. エンジニアが実装を行う（複数のエンジニアで並行作業）
    for i, engineer_agent in enumerate(engineer_agents):
        engineer_task = Task(
            description=f"技術仕様とアーキテクチャ設計に基づいて、担当機能を実装する。単体テストを行い、コードの品質を確保する。",
            agent=engineer_agent,
            context=[
                {
                    "role": "PL",
                    "input": f"エンジニア{i+1}に割り当てられた実装タスクを完了してください。コードの品質を確保し、単体テストも実施してください。"
                }
            ],
            expected_output="実装コード、単体テスト結果、実装完了レポート"
        )
        tasks.append(engineer_task)
    
    # 6. テスターがテストを行う（複数のテスターで並行作業）
    for i, tester_agent in enumerate(tester_agents):
        tester_task = Task(
            description=f"実装された機能に対するテスト計画とテストケースを作成し、テストを実行する。バグ報告を行う。",
            agent=tester_agent,
            context=[
                {
                    "role": "PL",
                    "input": f"実装された機能のテストを実施してください。テスト計画、テストケースを作成し、実行結果とバグ報告をまとめてください。"
                },
                {
                    "role": "エンジニア",
                    "input": "実装コードが完成しました。テストを実施してください。"
                }
            ],
            expected_output="テスト計画書、テストケース、テスト結果レポート、バグ報告書"
        )
        tasks.append(tester_task)
    
    # 7. PLがレビューを行う
    pl_review_task = Task(
        description="実装コードとテスト結果をレビューし、技術的な品質を評価する。必要に応じて修正指示を出す。",
        agent=pl_agent,
        context=[
            {
                "role": "エンジニア",
                "input": "実装コードが完成しました。レビューをお願いします。"
            },
            {
                "role": "テスター",
                "input": "テスト結果とバグ報告をまとめました。レビューをお願いします。"
            }
        ],
        expected_output="コードレビュー結果、修正指示、品質評価レポート"
    )
    tasks.append(pl_review_task)
    
    # 8. PMが進捗評価と報告を行う
    pm_report_task = Task(
        description="プロジェクトの進捗を評価し、プロダクトオーナーに報告する。次のステップを計画する。",
        agent=pm_agent,
        context=[
            {
                "role": "PL",
                "input": "コードレビュー結果と品質評価レポートが完成しました。"
            }
        ],
        expected_output="進捗報告書、次のステップの計画"
    )
    tasks.append(pm_report_task)
    
    # Crewの作成（プロセスはシーケンシャル）
    crew = Crew(
        agents=all_agents,
        tasks=tasks,
        verbose=2,
        process=Process.sequential
    )
    
    return crew 