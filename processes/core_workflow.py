"""
コアワークフローモジュール。
CrewAIのプロセスとタスクを定義し、エージェント間の連携フローを構築します。
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from crewai import Task, Crew, Process, Agent

from utils.logger import logger
from agents.pdm import create_pdm_agent, analyze_requirements, generate_backlog, prioritize_backlog
from agents.pm import create_pm_agent, breakdown_tasks, assign_tasks, generate_schedule, monitor_progress
from agents.designer import create_designer_agent
from agents.pl import create_pl_agent, generate_technical_spec, create_implementation_guide, review_code
from agents.engineer import create_engineer_agent, generate_code, debug_code, run_code
from agents.tester import create_tester_agent, generate_test_cases, execute_tests, generate_bug_report


class WorkflowContext:
    """ワークフロー全体で共有される実行コンテキスト"""
    
    def __init__(self):
        self.data = {}
        self.status = "initialized"
        self.current_phase = None
        self.start_time = None
        self.end_time = None
        self.metrics = {}
    
    def store(self, key: str, value: Any) -> None:
        """データを保存"""
        self.data[key] = value
        logger.info(f"コンテキストに '{key}' を保存しました。")
    
    def retrieve(self, key: str, default: Any = None) -> Any:
        """データを取得"""
        value = self.data.get(key, default)
        logger.info(f"コンテキストから '{key}' を取得しました。")
        return value
    
    def update_status(self, status: str) -> None:
        """ステータスを更新"""
        self.status = status
        logger.info(f"ワークフローステータスを '{status}' に更新しました。")
    
    def set_phase(self, phase: str) -> None:
        """現在のフェーズを設定"""
        self.current_phase = phase
        logger.info(f"現在のフェーズを '{phase}' に設定しました。")
    
    def start_execution(self) -> None:
        """実行開始時間を記録"""
        self.start_time = time.time()
        self.update_status("running")
        logger.info("ワークフロー実行を開始しました。")
    
    def end_execution(self) -> None:
        """実行終了時間を記録"""
        self.end_time = time.time()
        self.update_status("completed")
        execution_time = self.end_time - self.start_time if self.start_time else 0
        self.metrics["execution_time"] = execution_time
        logger.info(f"ワークフロー実行が完了しました。実行時間: {execution_time:.2f}秒")
    
    def to_json(self) -> str:
        """コンテキストをJSON形式に変換"""
        export_data = {
            "status": self.status,
            "current_phase": self.current_phase,
            "metrics": self.metrics,
            "data": {k: str(v)[:1000] + "..." if isinstance(v, str) and len(str(v)) > 1000 else v 
                    for k, v in self.data.items()}
        }
        return json.dumps(export_data, ensure_ascii=False, indent=2)


def create_requirement_analysis_tasks(context: WorkflowContext, pdm_agent: Agent) -> List[Task]:
    """要求分析フェーズのタスクを作成"""
    tasks = []
    
    # 要求分析タスク
    task1 = Task(
        description="プロダクトオーナーの要求を詳細に分析し、その主要なポイント、制約、ユースケースなどを抽出してください。",
        expected_output="要求分析レポート",
        agent=pdm_agent,
        async_execution=False,
        output_file="artifacts/requirement_analysis.md"
    )
    tasks.append(task1)
    
    # バックログ項目生成タスク
    task2 = Task(
        description="要求分析に基づいて、具体的なバックログ項目（ユーザーストーリー形式）を生成してください。各項目には、ID、タイトル、説明、受け入れ基準、見積り工数を含めてください。",
        expected_output="バックログ項目（JSON形式）",
        agent=pdm_agent,
        async_execution=False,
        context=[
            {
                "role": "PdM",
                "input": "要求分析が完了しました。これに基づいてバックログ項目を生成します。"
            }
        ],
        output_file="artifacts/backlog_items.json"
    )
    tasks.append(task2)
    
    # 優先順位付けタスク
    task3 = Task(
        description="バックログ項目に優先順位を付けてください。ビジネス価値、技術的な依存関係、リスクなどを考慮してください。",
        expected_output="優先順位付きバックログ項目（JSON形式）",
        agent=pdm_agent,
        async_execution=False,
        context=[
            {
                "role": "PdM",
                "input": "バックログ項目が生成されました。これに優先順位を付けます。"
            }
        ],
        output_file="artifacts/prioritized_backlog.json"
    )
    tasks.append(task3)
    
    return tasks


def create_planning_tasks(context: WorkflowContext, pm_agent: Agent) -> List[Task]:
    """計画フェーズのタスクを作成"""
    tasks = []
    
    # タスク分解タスク
    task1 = Task(
        description="バックログ項目を詳細なタスクに分解してください。各タスクには、ID、タイトル、説明、タイプ、担当者ロール、見積時間を含めてください。",
        expected_output="分解されたタスク（JSON形式）",
        agent=pm_agent,
        async_execution=False,
        context=[
            {
                "role": "PM",
                "input": "PdMから優先順位付きバックログ項目が提供されました。これをタスクに分解します。"
            }
        ],
        output_file="artifacts/breakdown_tasks.json"
    )
    tasks.append(task1)
    
    # タスク割当タスク
    task2 = Task(
        description="タスクを適切なエージェントに割り当ててください。各エージェントのスキルと負荷を考慮してください。",
        expected_output="割り当て結果（JSON形式）",
        agent=pm_agent,
        async_execution=False,
        context=[
            {
                "role": "PM",
                "input": "タスク分解が完了しました。これを適切なエージェントに割り当てます。"
            }
        ],
        output_file="artifacts/task_assignments.json"
    )
    tasks.append(task2)
    
    # スケジュール生成タスク
    task3 = Task(
        description="タスクの依存関係に基づいてスケジュールを生成してください。各タスクの開始日と終了日を計算してください。",
        expected_output="スケジュール（JSON形式）",
        agent=pm_agent,
        async_execution=False,
        context=[
            {
                "role": "PM",
                "input": "タスク割当が完了しました。これに基づいてスケジュールを生成します。"
            }
        ],
        output_file="artifacts/schedule.json"
    )
    tasks.append(task3)
    
    return tasks


def create_design_tasks(context: WorkflowContext, designer_agent: Agent) -> List[Task]:
    """設計フェーズのタスクを作成"""
    tasks = []
    
    # UI/UX仕様生成タスク
    task1 = Task(
        description="プロダクトバックログとプロジェクト計画に基づいて、UI/UXデザイン仕様を作成してください。画面レイアウト、コンポーネント、スタイルガイドなどを含めてください。",
        expected_output="UI/UXデザイン仕様書（Markdown形式）",
        agent=designer_agent,
        async_execution=False,
        context=[
            {
                "role": "デザイナー",
                "input": "PdMからバックログ項目、PMからプロジェクト計画が提供されました。これに基づいてUI/UXデザイン仕様を作成します。"
            }
        ],
        output_file="artifacts/ui_design_spec.md"
    )
    tasks.append(task1)
    
    # ワイヤーフレーム生成タスク
    task2 = Task(
        description="UI/UX仕様に基づいて、主要画面のワイヤーフレームを作成してください。レイアウト、コンポーネントの配置、ユーザーフローを示してください。",
        expected_output="ワイヤーフレーム（テキスト表現）",
        agent=designer_agent,
        async_execution=False,
        context=[
            {
                "role": "デザイナー",
                "input": "UI/UXデザイン仕様が完成しました。これに基づいてワイヤーフレームを作成します。"
            }
        ],
        output_file="artifacts/wireframes.md"
    )
    tasks.append(task2)
    
    return tasks


def create_technical_spec_tasks(context: WorkflowContext, pl_agent: Agent) -> List[Task]:
    """技術仕様フェーズのタスクを作成"""
    tasks = []
    
    # 技術仕様生成タスク
    task1 = Task(
        description="UI/UXデザイン仕様とバックログ項目に基づいて、技術仕様書を作成してください。アーキテクチャ設計、データモデル、APIインターフェース、技術スタックの選定を含めてください。",
        expected_output="技術仕様書（Markdown形式）",
        agent=pl_agent,
        async_execution=False,
        context=[
            {
                "role": "PL",
                "input": "デザイナーからUI/UXデザイン仕様、PdMからバックログ項目が提供されました。これに基づいて技術仕様書を作成します。"
            }
        ],
        output_file="artifacts/technical_spec.md"
    )
    tasks.append(task1)
    
    return tasks


def create_implementation_tasks(context: WorkflowContext, pl_agent: Agent, engineer_agents: List[Agent]) -> List[Task]:
    """実装フェーズのタスクを作成"""
    tasks = []
    
    # 実装指示書作成タスク
    implementation_guide_tasks = []
    for i, task_desc in enumerate([
        "ユーザー認証機能", "データ管理機能", "UI画面", "API連携機能"
    ]):
        task = Task(
            description=f"{task_desc}の実装指示書を作成してください。タスクの詳細、実装アプローチ、コード構造、テスト要件を含めてください。",
            expected_output="実装指示書（Markdown形式）",
            agent=pl_agent,
            async_execution=False,
            context=[
                {
                    "role": "PL",
                    "input": f"技術仕様書が完成しました。これに基づいて{task_desc}の実装指示書を作成します。"
                }
            ],
            output_file=f"artifacts/implementation_guide_{i+1}.md"
        )
        implementation_guide_tasks.append(task)
    
    tasks.extend(implementation_guide_tasks)
    
    # 実装タスク
    implementation_tasks = []
    task_descriptions = ["ユーザー認証機能", "データ管理機能", "UI画面", "API連携機能"]
    languages = ["python", "python", "html", "javascript"]
    
    for i, (engineer, task_desc, lang) in enumerate(zip(engineer_agents * (len(task_descriptions) // len(engineer_agents) + 1), task_descriptions, languages)):
        if i >= len(task_descriptions):
            break
            
        task = Task(
            description=f"{task_desc}の実装を行ってください。実装指示書に基づいて、{lang}で実装してください。コードは読みやすく、保守性を考慮してください。",
            expected_output=f"{task_desc}の実装コード",
            agent=engineer,
            async_execution=True,  # 並列実行
            context=[
                {
                    "role": "エンジニア",
                    "input": f"PLから{task_desc}の実装指示書が提供されました。これに基づいて実装を行います。"
                }
            ],
            output_file=f"artifacts/implementation_{i+1}.{lang}"
        )
        implementation_tasks.append(task)
    
    tasks.extend(implementation_tasks)
    
    # デバッグタスク（例として1つだけ作成）
    debug_task = Task(
        description="実装したコードの潜在的な問題を特定し、修正してください。",
        expected_output="デバッグレポートと修正済みコード",
        agent=engineer_agents[0],
        async_execution=False,
        context=[
            {
                "role": "エンジニア",
                "input": "実装が完了しました。潜在的な問題がないかデバッグを行います。"
            }
        ],
        output_file="artifacts/debug_report.md"
    )
    tasks.append(debug_task)
    
    return tasks


def create_test_tasks(context: WorkflowContext, tester_agents: List[Agent]) -> List[Task]:
    """テストフェーズのタスクを作成"""
    tasks = []
    
    # テストケース生成タスク
    test_case_tasks = []
    for i, task_desc in enumerate([
        "ユーザー認証機能", "データ管理機能", "UI画面", "API連携機能"
    ]):
        task = Task(
            description=f"{task_desc}のテストケースを作成してください。正常系、異常系、エッジケースを含め、機能が仕様通りに動作することを確認するテストを設計してください。",
            expected_output="テストケース（JSON形式）",
            agent=tester_agents[i % len(tester_agents)],
            async_execution=True,  # 並列実行
            context=[
                {
                    "role": "テスター",
                    "input": f"エンジニアから{task_desc}の実装が提供されました。これに対するテストケースを作成します。"
                }
            ],
            output_file=f"artifacts/test_cases_{i+1}.json"
        )
        test_case_tasks.append(task)
    
    tasks.extend(test_case_tasks)
    
    # テスト実行タスク
    test_execution_tasks = []
    for i, task_desc in enumerate([
        "ユーザー認証機能", "データ管理機能", "UI画面", "API連携機能"
    ]):
        task = Task(
            description=f"{task_desc}のテストを実行してください。各テストの成功/失敗、実行時間、詳細な結果情報を含めてください。",
            expected_output="テスト結果（JSON形式）",
            agent=tester_agents[i % len(tester_agents)],
            async_execution=False,
            context=[
                {
                    "role": "テスター",
                    "input": f"{task_desc}のテストケースが作成されました。これに基づいてテストを実行します。"
                }
            ],
            output_file=f"artifacts/test_results_{i+1}.json"
        )
        test_execution_tasks.append(task)
    
    tasks.extend(test_execution_tasks)
    
    # バグ報告タスク
    bug_report_task = Task(
        description="テスト結果から、検出されたバグに関する詳細なレポートを作成してください。バグの再現手順、期待される動作と実際の動作、影響範囲を含めてください。",
        expected_output="バグレポート（Markdown形式）",
        agent=tester_agents[0],
        async_execution=False,
        context=[
            {
                "role": "テスター",
                "input": "テスト実行が完了しました。検出されたバグに関するレポートを作成します。"
            }
        ],
        output_file="artifacts/bug_report.md"
    )
    tasks.append(bug_report_task)
    
    return tasks


def create_review_tasks(context: WorkflowContext, pl_agent: Agent, pm_agent: Agent) -> List[Task]:
    """レビューフェーズのタスクを作成"""
    tasks = []
    
    # コードレビュータスク
    code_review_task = Task(
        description="実装コードをレビューし、フィードバックを提供してください。コードの品質、セキュリティ、パフォーマンス、コーディング規約への準拠を評価してください。",
        expected_output="コードレビュー結果（Markdown形式）",
        agent=pl_agent,
        async_execution=False,
        context=[
            {
                "role": "PL",
                "input": "エンジニアから実装コードが提供されました。これをレビューします。"
            }
        ],
        output_file="artifacts/code_review.md"
    )
    tasks.append(code_review_task)
    
    # 進捗監視タスク
    progress_monitoring_task = Task(
        description="プロジェクトの進捗状況を監視し、完了したタスク、進行中のタスク、遅延しているタスクを特定してください。全体の進捗率を計算してください。",
        expected_output="進捗状況レポート（JSON形式）",
        agent=pm_agent,
        async_execution=False,
        context=[
            {
                "role": "PM",
                "input": "プロジェクトの進捗状況を評価します。"
            }
        ],
        output_file="artifacts/progress_report.json"
    )
    tasks.append(progress_monitoring_task)
    
    # 総括レポートタスク
    final_report_task = Task(
        description="プロジェクト全体の成果をまとめ、達成した目標、残された課題、今後の展望を報告してください。",
        expected_output="プロジェクト総括レポート（Markdown形式）",
        agent=pm_agent,
        async_execution=False,
        context=[
            {
                "role": "PM",
                "input": "プロジェクトの全フェーズが完了しました。プロジェクト全体の成果をまとめます。"
            }
        ],
        output_file="artifacts/final_report.md"
    )
    tasks.append(final_report_task)
    
    return tasks


def create_full_development_workflow(
    request: str,
    pdm_tools: List[Any] = None,
    pm_tools: List[Any] = None,
    designer_tools: List[Any] = None,
    pl_tools: List[Any] = None,
    engineer_tools: List[Any] = None,
    tester_tools: List[Any] = None,
    engineer_count: int = 2,
    tester_count: int = 1,
) -> Tuple[Crew, WorkflowContext]:
    """
    完全な開発ワークフローを持つCrewを作成します。
    
    Args:
        request: プロダクトオーナーからの要求
        pdm_tools: PdMエージェントのツールリスト
        pm_tools: PMエージェントのツールリスト
        designer_tools: デザイナーエージェントのツールリスト
        pl_tools: PLエージェントのツールリスト
        engineer_tools: エンジニアエージェントのツールリスト
        tester_tools: テスターエージェントのツールリスト
        engineer_count: エンジニアエージェントの数
        tester_count: テスターエージェントの数
        
    Returns:
        Tuple[Crew, WorkflowContext]: 設定されたCrewオブジェクトとワークフローコンテキスト
    """
    logger.info("完全な開発ワークフローCrewを作成します。")
    
    # ワークフローコンテキストの初期化
    context = WorkflowContext()
    context.store("request", request)
    
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
    
    # 各フェーズのタスクを作成
    tasks = []
    
    # 1. 要求分析フェーズ
    context.set_phase("requirement_analysis")
    req_analysis_tasks = create_requirement_analysis_tasks(context, pdm_agent)
    tasks.extend(req_analysis_tasks)
    
    # 2. 計画フェーズ
    context.set_phase("planning")
    planning_tasks = create_planning_tasks(context, pm_agent)
    tasks.extend(planning_tasks)
    
    # 3. 設計フェーズ
    context.set_phase("design")
    design_tasks = create_design_tasks(context, designer_agent)
    tasks.extend(design_tasks)
    
    # 4. 技術仕様フェーズ
    context.set_phase("technical_specification")
    tech_spec_tasks = create_technical_spec_tasks(context, pl_agent)
    tasks.extend(tech_spec_tasks)
    
    # 5. 実装フェーズ
    context.set_phase("implementation")
    implementation_tasks = create_implementation_tasks(context, pl_agent, engineer_agents)
    tasks.extend(implementation_tasks)
    
    # 6. テストフェーズ
    context.set_phase("testing")
    test_tasks = create_test_tasks(context, tester_agents)
    tasks.extend(test_tasks)
    
    # 7. レビューフェーズ
    context.set_phase("review")
    review_tasks = create_review_tasks(context, pl_agent, pm_agent)
    tasks.extend(review_tasks)
    
    # ハイブリッドプロセス（一部シーケンシャル、一部パラレル）を実現するカスタムプロセス
    class HybridProcess(Process):
        """シーケンシャルと並列を組み合わせたハイブリッドプロセス"""
        
        @staticmethod
        def execute(crew: Crew, tasks: List[Task], **kwargs) -> List[str]:
            """
            タスクの実行方法に基づいて、シーケンシャルまたは並列で実行
            
            Args:
                crew: Crewオブジェクト
                tasks: 実行するタスクのリスト
                
            Returns:
                List[str]: タスク実行結果のリスト
            """
            results = []
            
            # フェーズごとにタスクをグループ化
            phase_tasks = {}
            for task in tasks:
                # コンテキストからフェーズを取得
                task_context = getattr(task, "context", [])
                phase = None
                for ctx in task_context:
                    if ctx.get("role") in ["PdM", "PM", "デザイナー", "PL", "エンジニア", "テスター"]:
                        phase = ctx.get("role")
                        break
                
                if phase not in phase_tasks:
                    phase_tasks[phase] = []
                
                phase_tasks[phase].append(task)
            
            # 各フェーズ内でタスクを実行
            for phase, phase_task_list in phase_tasks.items():
                # 各フェーズは順次実行
                logger.info(f"フェーズ '{phase}' の実行を開始します。")
                
                # フェーズ内のタスクを非同期属性に基づいて分類
                sync_tasks = [t for t in phase_task_list if not getattr(t, "async_execution", False)]
                async_tasks = [t for t in phase_task_list if getattr(t, "async_execution", False)]
                
                # 同期タスクを順次実行
                for task in sync_tasks:
                    result = crew.process_task(task)
                    results.append(result)
                
                # 非同期タスクを並列実行
                if async_tasks:
                    logger.info(f"フェーズ '{phase}' 内で {len(async_tasks)} 個のタスクを並列実行します。")
                    
                    # 並列実行用のメソッドを使用
                    async_results = Process.parallel.execute(crew, async_tasks, **kwargs)
                    results.extend(async_results)
            
            return results
    
    # Crewの作成（カスタムハイブリッドプロセス）
    crew = Crew(
        agents=all_agents,
        tasks=tasks,
        verbose=2,
        process=HybridProcess,
        workflow_context=context
    )
    
    return crew, context


def execute_and_monitor_workflow(crew: Crew, context: WorkflowContext) -> Dict[str, Any]:
    """
    ワークフローを実行し、監視します。
    
    Args:
        crew: 実行するCrewオブジェクト
        context: ワークフローコンテキスト
        
    Returns:
        Dict[str, Any]: 実行結果と監視情報
    """
    logger.info("ワークフローの実行と監視を開始します。")
    
    # 実行開始を記録
    context.start_execution()
    
    try:
        # Crewの実行
        results = crew.kickoff()
        
        # 結果をコンテキストに保存
        context.store("results", results)
        
        # メトリクスの計算
        metrics = {
            "task_count": len(crew.tasks),
            "agent_count": len(crew.agents),
            "success_rate": 1.0  # 実際のプロジェクトでは、成功/失敗の判定ロジックを実装
        }
        context.metrics.update(metrics)
        
    except Exception as e:
        # エラー発生時の処理
        logger.error(f"ワークフロー実行中にエラーが発生しました: {str(e)}")
        context.update_status("failed")
        context.store("error", str(e))
        
    finally:
        # 実行終了を記録
        context.end_execution()
    
    # 実行結果と監視情報を返す
    return {
        "status": context.status,
        "execution_time": context.metrics.get("execution_time", 0),
        "metrics": context.metrics,
        "context_data": context.data
    }


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