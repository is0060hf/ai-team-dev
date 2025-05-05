"""
PM（プロジェクトマネージャー）エージェントモジュール。
プロジェクト全体の計画立案、タスク分解、スケジュール管理、進捗監視を担当します。
"""

import json
import datetime
from typing import List, Dict, Any, Optional, Tuple
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pm")


class TaskBreakdownTool(Tool):
    """タスク分解ツール"""
    
    name = "タスク分解"
    description = "バックログ項目を詳細なタスクに分解します。"
    
    def _run(self, backlog_items_json: str) -> str:
        """
        バックログ項目を詳細なタスクに分解します。
        
        Args:
            backlog_items_json: バックログ項目（JSON形式）
            
        Returns:
            str: 分解されたタスク（JSON形式）
        """
        logger.info("タスク分解ツールが呼び出されました。")
        
        try:
            backlog_items = json.loads(backlog_items_json)
            
            # タスクの分解（実際のプロジェクトではLLMを使用してより詳細なタスク分解を行う）
            tasks = []
            task_id = 1
            
            for item in backlog_items:
                # ユーザーストーリーごとにタスクを生成
                story_id = item["id"]
                
                # 設計タスク
                tasks.append({
                    "id": f"TASK-{task_id:03d}",
                    "title": f"{item['title']}の設計",
                    "description": f"{item['title']}の詳細設計を行います。",
                    "type": "design",
                    "story_id": story_id,
                    "assignee_role": "デザイナー",
                    "status": "to_do",
                    "estimated_hours": 4,
                    "dependencies": []
                })
                task_id += 1
                
                # 技術仕様タスク
                tasks.append({
                    "id": f"TASK-{task_id:03d}",
                    "title": f"{item['title']}の技術仕様書作成",
                    "description": f"{item['title']}の技術仕様書を作成します。",
                    "type": "specification",
                    "story_id": story_id,
                    "assignee_role": "PL",
                    "status": "to_do",
                    "estimated_hours": 3,
                    "dependencies": [f"TASK-{task_id-1:03d}"]
                })
                task_id += 1
                
                # 実装タスク
                tasks.append({
                    "id": f"TASK-{task_id:03d}",
                    "title": f"{item['title']}の実装",
                    "description": f"{item['title']}を実装します。",
                    "type": "implementation",
                    "story_id": story_id,
                    "assignee_role": "エンジニア",
                    "status": "to_do",
                    "estimated_hours": 8,
                    "dependencies": [f"TASK-{task_id-1:03d}"]
                })
                task_id += 1
                
                # テストタスク
                tasks.append({
                    "id": f"TASK-{task_id:03d}",
                    "title": f"{item['title']}のテスト",
                    "description": f"{item['title']}のテストを実施します。",
                    "type": "testing",
                    "story_id": story_id,
                    "assignee_role": "テスター",
                    "status": "to_do",
                    "estimated_hours": 4,
                    "dependencies": [f"TASK-{task_id-1:03d}"]
                })
                task_id += 1
            
            return json.dumps(tasks, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: タスク分解に失敗しました: {str(e)}"


class TaskAssignmentTool(Tool):
    """タスク割当ツール"""
    
    name = "タスク割当"
    description = "タスクをエージェントに割り当てます。"
    
    def _run(self, tasks_json: str, available_agents_json: str = None) -> str:
        """
        タスクをエージェントに割り当てます。
        
        Args:
            tasks_json: タスク（JSON形式）
            available_agents_json: 利用可能なエージェント情報（JSON形式、オプション）
            
        Returns:
            str: 割り当て結果（JSON形式）
        """
        logger.info("タスク割当ツールが呼び出されました。")
        
        try:
            tasks = json.loads(tasks_json)
            
            # デフォルトのエージェント情報
            default_agents = [
                {"role": "デザイナー", "id": "designer-1", "capacity": 40},
                {"role": "PL", "id": "pl-1", "capacity": 40},
                {"role": "エンジニア", "id": "engineer-1", "capacity": 40},
                {"role": "エンジニア", "id": "engineer-2", "capacity": 40},
                {"role": "テスター", "id": "tester-1", "capacity": 40}
            ]
            
            # 利用可能なエージェント情報が提供されている場合は、それを使用
            if available_agents_json:
                try:
                    available_agents = json.loads(available_agents_json)
                except:
                    available_agents = default_agents
            else:
                available_agents = default_agents
            
            # エージェントごとの負荷を計算
            agent_loads = {agent["id"]: 0 for agent in available_agents}
            
            # タスクの割り当て
            for task in tasks:
                role = task["assignee_role"]
                
                # 該当ロールの中で最も負荷の少ないエージェントを選択
                eligible_agents = [a for a in available_agents if a["role"] == role]
                if eligible_agents:
                    selected_agent = min(eligible_agents, key=lambda a: agent_loads[a["id"]])
                    task["assignee"] = selected_agent["id"]
                    agent_loads[selected_agent["id"]] += task["estimated_hours"]
                else:
                    # 該当ロールのエージェントが見つからない場合
                    task["assignee"] = "unassigned"
            
            # 割り当て結果を含むタスクリストと、負荷状況を返す
            result = {
                "tasks": tasks,
                "agent_loads": [{"agent_id": agent_id, "hours": hours} for agent_id, hours in agent_loads.items()]
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: タスク割当に失敗しました: {str(e)}"


class ScheduleGeneratorTool(Tool):
    """スケジュール生成ツール"""
    
    name = "スケジュール生成"
    description = "タスクの依存関係に基づいてスケジュールを生成します。"
    
    def _run(self, tasks_with_assignments_json: str, start_date: str = None) -> str:
        """
        タスクのスケジュールを生成します。
        
        Args:
            tasks_with_assignments_json: 割り当て済みタスク（JSON形式）
            start_date: プロジェクト開始日（YYYY-MM-DD形式、指定がなければ現在日）
            
        Returns:
            str: スケジュール（JSON形式）
        """
        logger.info("スケジュール生成ツールが呼び出されました。")
        
        try:
            # タスク情報の取得
            data = json.loads(tasks_with_assignments_json)
            tasks = data.get("tasks", [])
            
            # 開始日の設定
            if start_date:
                current_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            else:
                current_date = datetime.datetime.now().date()
            
            # タスクID → タスクのマッピングを作成
            task_map = {task["id"]: task for task in tasks}
            
            # 各タスクの開始日・終了日を計算
            for task in tasks:
                # 依存タスクの終了日を確認
                if task["dependencies"]:
                    latest_end_date = current_date
                    dependencies_ready = True
                    
                    for dep_id in task["dependencies"]:
                        if dep_id in task_map and "end_date" in task_map[dep_id]:
                            dep_end_date = datetime.datetime.strptime(task_map[dep_id]["end_date"], "%Y-%m-%d").date()
                            if dep_end_date > latest_end_date:
                                latest_end_date = dep_end_date
                        else:
                            dependencies_ready = False
                    
                    if dependencies_ready:
                        # 依存タスクの終了翌日から開始
                        start_date = latest_end_date + datetime.timedelta(days=1)
                    else:
                        # 依存タスクのスケジュールが未定の場合
                        start_date = current_date
                else:
                    # 依存タスクがない場合は現在日から開始
                    start_date = current_date
                
                # 作業日数を計算（簡易的に1日8時間で計算）
                work_days = max(1, int((task["estimated_hours"] + 7) / 8))
                
                # 終了日を計算
                end_date = start_date + datetime.timedelta(days=work_days - 1)
                
                # スケジュール情報をタスクに追加
                task["start_date"] = start_date.strftime("%Y-%m-%d")
                task["end_date"] = end_date.strftime("%Y-%m-%d")
                task["work_days"] = work_days
            
            # 全体のスケジュール情報
            earliest_start = min(datetime.datetime.strptime(task["start_date"], "%Y-%m-%d").date() for task in tasks)
            latest_end = max(datetime.datetime.strptime(task["end_date"], "%Y-%m-%d").date() for task in tasks)
            
            schedule = {
                "tasks": tasks,
                "project_start_date": earliest_start.strftime("%Y-%m-%d"),
                "project_end_date": latest_end.strftime("%Y-%m-%d"),
                "total_days": (latest_end - earliest_start).days + 1
            }
            
            return json.dumps(schedule, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: スケジュール生成に失敗しました: {str(e)}"


class ProgressMonitorTool(Tool):
    """進捗監視ツール"""
    
    name = "進捗監視"
    description = "タスクの進捗状況を監視し、プロジェクトの現在の状態を報告します。"
    
    def _run(self, scheduled_tasks_json: str, current_date: str = None) -> str:
        """
        プロジェクトの進捗状況を監視します。
        
        Args:
            scheduled_tasks_json: スケジュール済みタスク（JSON形式）
            current_date: 現在日（YYYY-MM-DD形式、指定がなければ現在日）
            
        Returns:
            str: 進捗状況（JSON形式）
        """
        logger.info("進捗監視ツールが呼び出されました。")
        
        try:
            # タスク情報の取得
            data = json.loads(scheduled_tasks_json)
            tasks = data.get("tasks", [])
            
            # 現在日の設定
            if current_date:
                now = datetime.datetime.strptime(current_date, "%Y-%m-%d").date()
            else:
                now = datetime.datetime.now().date()
            
            # 各タスクの進捗状況を計算
            for task in tasks:
                start_date = datetime.datetime.strptime(task["start_date"], "%Y-%m-%d").date()
                end_date = datetime.datetime.strptime(task["end_date"], "%Y-%m-%d").date()
                
                # タスクのステータスに基づいて進捗率を計算
                if task["status"] == "done":
                    task["progress"] = 100
                elif task["status"] == "in_progress":
                    # 開始日から終了日までの進捗を線形に計算
                    if now >= end_date:
                        task["progress"] = 90  # 終了日を過ぎているが完了していない場合
                    elif now < start_date:
                        task["progress"] = 10  # 早期に着手している場合
                    else:
                        total_days = max(1, (end_date - start_date).days)
                        elapsed_days = (now - start_date).days
                        task["progress"] = min(90, max(10, int(10 + (elapsed_days / total_days) * 80)))
                elif task["status"] == "to_do":
                    if now > end_date:
                        task["status"] = "delayed"
                        task["progress"] = 0
                    else:
                        task["progress"] = 0
            
            # プロジェクト全体の進捗を計算
            total_hours = sum(task["estimated_hours"] for task in tasks)
            completed_hours = sum(task["estimated_hours"] * task["progress"] / 100 for task in tasks)
            overall_progress = int(completed_hours / total_hours * 100) if total_hours > 0 else 0
            
            # 遅延タスクの特定
            delayed_tasks = [task for task in tasks if task["status"] == "delayed"]
            at_risk_tasks = [task for task in tasks if task["status"] == "in_progress" and 
                            datetime.datetime.strptime(task["end_date"], "%Y-%m-%d").date() <= now]
            
            # 進捗状況レポート
            progress_report = {
                "current_date": now.strftime("%Y-%m-%d"),
                "overall_progress": overall_progress,
                "task_status_summary": {
                    "total": len(tasks),
                    "done": len([t for t in tasks if t["status"] == "done"]),
                    "in_progress": len([t for t in tasks if t["status"] == "in_progress"]),
                    "to_do": len([t for t in tasks if t["status"] == "to_do"]),
                    "delayed": len(delayed_tasks)
                },
                "delayed_tasks": [{"id": t["id"], "title": t["title"]} for t in delayed_tasks],
                "at_risk_tasks": [{"id": t["id"], "title": t["title"]} for t in at_risk_tasks],
                "tasks": tasks
            }
            
            return json.dumps(progress_report, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: 進捗監視に失敗しました: {str(e)}"


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
    
    # PM固有のツールを追加
    pm_specific_tools = [
        TaskBreakdownTool(),
        TaskAssignmentTool(),
        ScheduleGeneratorTool(),
        ProgressMonitorTool(),
    ]
    
    all_tools = tools + pm_specific_tools
    
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
        tools=all_tools,
        allow_delegation=True,  # PMは下位エージェントに委任可能
    )
    
    return pm_agent


def breakdown_tasks(agent: Agent, backlog_items: str) -> Dict[str, Any]:
    """
    バックログ項目をタスクに分解します。
    
    Args:
        agent: PMエージェント
        backlog_items: バックログ項目（文字列またはオブジェクト）
        
    Returns:
        Dict[str, Any]: 分解されたタスク
    """
    logger.info("タスク分解を開始します。")
    
    # バックログ項目がJSON文字列でない場合、JSON文字列に変換
    if not isinstance(backlog_items, str):
        backlog_items_json = json.dumps(backlog_items, ensure_ascii=False)
    else:
        backlog_items_json = backlog_items
    
    # タスク分解タスクの実行
    breakdown_task = Task(
        description="バックログ項目を詳細なタスクに分解してください。各タスクには、ID、タイトル、説明、タイプ、担当者ロール、見積時間を含めてください。",
        expected_output="分解されたタスク（JSON形式）",
        agent=agent
    )
    
    breakdown_result = agent.execute_task(breakdown_task, context={"backlog_items": backlog_items_json})
    
    # 結果をパースする
    try:
        tasks = json.loads(breakdown_result)
        breakdown_result = tasks
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("タスク分解が完了しました。")
    return {"tasks": breakdown_result}


def assign_tasks(agent: Agent, tasks: Dict[str, Any], available_agents: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    タスクをエージェントに割り当てます。
    
    Args:
        agent: PMエージェント
        tasks: 分解されたタスク
        available_agents: 利用可能なエージェント情報
        
    Returns:
        Dict[str, Any]: 割り当て結果
    """
    logger.info("タスク割当を開始します。")
    
    # タスクがJSON文字列でない場合、JSON文字列に変換
    if not isinstance(tasks, str):
        tasks_json = json.dumps(tasks, ensure_ascii=False)
    else:
        tasks_json = tasks
    
    # 利用可能なエージェント情報
    if available_agents is not None:
        agents_json = json.dumps(available_agents, ensure_ascii=False)
    else:
        agents_json = None
    
    # タスク割当タスクの実行
    assignment_task = Task(
        description="タスクを適切なエージェントに割り当ててください。各エージェントのスキルと負荷を考慮してください。",
        expected_output="割り当て結果（JSON形式）",
        agent=agent
    )
    
    assignment_result = agent.execute_task(assignment_task, context={
        "tasks": tasks_json,
        "available_agents": agents_json
    })
    
    # 結果をパースする
    try:
        assignments = json.loads(assignment_result)
        assignment_result = assignments
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("タスク割当が完了しました。")
    return {"assignments": assignment_result}


def generate_schedule(agent: Agent, assignments: Dict[str, Any], start_date: str = None) -> Dict[str, Any]:
    """
    スケジュールを生成します。
    
    Args:
        agent: PMエージェント
        assignments: タスク割当結果
        start_date: プロジェクト開始日
        
    Returns:
        Dict[str, Any]: スケジュール
    """
    logger.info("スケジュール生成を開始します。")
    
    # 割当結果がJSON文字列でない場合、JSON文字列に変換
    if not isinstance(assignments, str):
        assignments_json = json.dumps(assignments, ensure_ascii=False)
    else:
        assignments_json = assignments
    
    # スケジュール生成タスクの実行
    schedule_task = Task(
        description="タスクの依存関係に基づいてスケジュールを生成してください。各タスクの開始日と終了日を計算してください。",
        expected_output="スケジュール（JSON形式）",
        agent=agent
    )
    
    schedule_result = agent.execute_task(schedule_task, context={
        "tasks_with_assignments": assignments_json,
        "start_date": start_date
    })
    
    # 結果をパースする
    try:
        schedule = json.loads(schedule_result)
        schedule_result = schedule
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("スケジュール生成が完了しました。")
    return {"schedule": schedule_result}


def monitor_progress(agent: Agent, schedule: Dict[str, Any], current_date: str = None) -> Dict[str, Any]:
    """
    プロジェクトの進捗状況を監視します。
    
    Args:
        agent: PMエージェント
        schedule: スケジュール
        current_date: 現在日
        
    Returns:
        Dict[str, Any]: 進捗状況
    """
    logger.info("進捗監視を開始します。")
    
    # スケジュールがJSON文字列でない場合、JSON文字列に変換
    if not isinstance(schedule, str):
        schedule_json = json.dumps(schedule, ensure_ascii=False)
    else:
        schedule_json = schedule
    
    # 進捗監視タスクの実行
    progress_task = Task(
        description="プロジェクトの進捗状況を監視してください。完了したタスク、進行中のタスク、遅延しているタスクを特定してください。",
        expected_output="進捗状況（JSON形式）",
        agent=agent
    )
    
    progress_result = agent.execute_task(progress_task, context={
        "scheduled_tasks": schedule_json,
        "current_date": current_date
    })
    
    # 結果をパースする
    try:
        progress = json.loads(progress_result)
        progress_result = progress
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("進捗監視が完了しました。")
    return {"progress": progress_result} 