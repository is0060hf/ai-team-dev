"""
専門エージェントとコアエージェント間の連携ワークフロー自動化モジュール。
専門エージェントの起動、タスク依頼、結果連携、モニタリングのプロセスを自動化します。
"""

import json
import datetime
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
import uuid
import os

from utils.agent_communication import (
    TaskType, TaskPriority, TaskStatus, 
    send_task_request, send_task_response, update_task_status,
    request_information, respond_to_information, get_task_status,
    dispatcher, MessageDispatcher
)
from utils.logger import get_agent_logger

logger = get_agent_logger("workflow_automation")


# 専門エージェント識別子
class SpecialistAgents:
    """専門エージェントの識別子定義"""
    AI_ARCHITECT = "ai_architect"
    PROMPT_ENGINEER = "prompt_engineer"
    DATA_ENGINEER = "data_engineer"


# コアエージェント識別子
class CoreAgents:
    """コアエージェントの識別子定義"""
    PDM = "pdm"
    PM = "pm"
    DESIGNER = "designer"
    PL = "pl"
    ENGINEER = "engineer"
    TESTER = "tester"


class SpecialistTaskRegistry:
    """
    専門エージェントタスクの登録と管理を行うレジストリ。
    実行中のタスクや完了したタスクの追跡を担当します。
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpecialistTaskRegistry, cls).__new__(cls)
            cls._instance._active_tasks = {}  # タスクID -> タスク情報
            cls._instance._completed_tasks = {}  # タスクID -> 結果情報
            cls._instance._task_history = []  # 全タスクの履歴
            cls._instance._approval_callbacks = {}  # タスクID -> 承認コールバック関数
        return cls._instance
    
    def register_task(self, 
                     task_id: str, 
                     sender: str, 
                     recipient: str, 
                     task_type: str, 
                     description: str,
                     priority: str,
                     deadline: Optional[str] = None,
                     context: Optional[Dict[str, Any]] = None) -> None:
        """
        タスクを登録します。
        
        Args:
            task_id: タスクID
            sender: 送信元エージェント
            recipient: 受信先エージェント
            task_type: タスク種別
            description: タスク詳細
            priority: 優先度
            deadline: 期限（オプション）
            context: コンテキスト情報（オプション）
        """
        task_info = {
            "task_id": task_id,
            "sender": sender,
            "recipient": recipient,
            "task_type": task_type,
            "description": description,
            "priority": priority,
            "deadline": deadline,
            "context": context or {},
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "approved_by_pm": False
        }
        
        self._active_tasks[task_id] = task_info
        self._task_history.append(task_info.copy())
        logger.info(f"タスクを登録しました: {task_id} ({task_type})")
    
    def update_task_status(self, task_id: str, status: str, progress: Optional[float] = None) -> None:
        """
        タスクの状態を更新します。
        
        Args:
            task_id: タスクID
            status: 新しい状態
            progress: 進捗率（オプション）
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id]["status"] = status
            self._active_tasks[task_id]["updated_at"] = datetime.datetime.now().isoformat()
            
            if progress is not None:
                self._active_tasks[task_id]["progress"] = progress
            
            # 履歴にステータス更新を追加
            self._task_history.append({
                **self._active_tasks[task_id],
                "event_type": "status_update"
            })
            
            logger.info(f"タスク状態を更新しました: {task_id} -> {status}")
            
            # タスクが完了または失敗した場合はアクティブタスクから完了タスクへ移動
            if status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.REJECTED.value]:
                self._complete_task(task_id, status)
    
    def _complete_task(self, task_id: str, final_status: str) -> None:
        """
        タスクを完了状態に移行します。
        
        Args:
            task_id: タスクID
            final_status: 最終状態
        """
        if task_id in self._active_tasks:
            task_info = self._active_tasks[task_id].copy()
            task_info["final_status"] = final_status
            task_info["completed_at"] = datetime.datetime.now().isoformat()
            
            self._completed_tasks[task_id] = task_info
            del self._active_tasks[task_id]
            
            logger.info(f"タスクを完了しました: {task_id} (最終状態: {final_status})")
    
    def approve_task(self, task_id: str, approver: str = CoreAgents.PM) -> None:
        """
        PMによるタスク承認を記録します。
        
        Args:
            task_id: タスクID
            approver: 承認者（デフォルト: PM）
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id]["approved_by_pm"] = True
            self._active_tasks[task_id]["approver"] = approver
            self._active_tasks[task_id]["approved_at"] = datetime.datetime.now().isoformat()
            
            # 履歴に承認イベントを追加
            self._task_history.append({
                **self._active_tasks[task_id],
                "event_type": "task_approval"
            })
            
            logger.info(f"タスクが承認されました: {task_id} (承認者: {approver})")
            
            # 承認コールバックがあれば実行
            if task_id in self._approval_callbacks:
                try:
                    self._approval_callbacks[task_id]()
                    del self._approval_callbacks[task_id]
                except Exception as e:
                    logger.error(f"承認コールバック実行中にエラーが発生しました: {str(e)}")
    
    def reject_task(self, task_id: str, reason: str, rejecter: str = CoreAgents.PM) -> None:
        """
        PMによるタスク拒否を記録します。
        
        Args:
            task_id: タスクID
            reason: 拒否理由
            rejecter: 拒否者（デフォルト: PM）
        """
        task_info = self.get_task_info(task_id)
        if task_info is None:
            logger.warning(f"タスク拒否処理: タスクIDが見つかりません: {task_id}")
            return
            
        # タスク情報のコピーを作成して更新
        task_info_copy = task_info.copy() if task_info else {}
        task_info_copy["rejected_by_pm"] = True
        task_info_copy["rejecter"] = rejecter
        task_info_copy["rejection_reason"] = reason
        task_info_copy["rejected_at"] = datetime.datetime.now().isoformat()
        
        # アクティブタスクに存在する場合のみ更新
        if task_id in self._active_tasks:
            self._active_tasks[task_id].update(task_info_copy)
            
        # 状態を拒否に更新
        self.update_task_status(task_id, TaskStatus.REJECTED.value)
        
        # 履歴に拒否イベントを追加
        rejection_event = task_info_copy.copy()
        rejection_event["event_type"] = "task_rejection"  # 明示的にイベント種別を設定
        self._task_history.append(rejection_event)
        
        logger.info(f"タスクが拒否されました: {task_id} (拒否者: {rejecter}, 理由: {reason})")
    
    def set_task_result(self, task_id: str, result: Dict[str, Any], attachments: Optional[List[str]] = None) -> None:
        """
        タスクの結果を設定します。
        
        Args:
            task_id: タスクID
            result: タスク結果
            attachments: 添付ファイル（オプション）
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id]["result"] = result
            
            if attachments:
                self._active_tasks[task_id]["attachments"] = attachments
            
            self._active_tasks[task_id]["result_set_at"] = datetime.datetime.now().isoformat()
            
            # 履歴に結果設定イベントを追加
            self._task_history.append({
                **self._active_tasks[task_id],
                "event_type": "result_set"
            })
            
            logger.info(f"タスク結果が設定されました: {task_id}")
    
    def register_approval_callback(self, task_id: str, callback: Callable[[], None]) -> None:
        """
        タスク承認時のコールバック関数を登録します。
        
        Args:
            task_id: タスクID
            callback: 承認時に実行するコールバック関数
        """
        self._approval_callbacks[task_id] = callback
        logger.info(f"タスク承認コールバックを登録しました: {task_id}")
    
    def is_task_approved(self, task_id: str) -> bool:
        """
        タスクがPMに承認されているかを確認します。
        
        Args:
            task_id: タスクID
            
        Returns:
            bool: 承認されている場合はTrue
        """
        if task_id in self._active_tasks:
            return self._active_tasks[task_id].get("approved_by_pm", False)
        elif task_id in self._completed_tasks:
            return self._completed_tasks[task_id].get("approved_by_pm", False)
        return False
    
    def get_active_tasks(self, specialist_agent: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        アクティブなタスクのリストを取得します。
        
        Args:
            specialist_agent: 専門エージェント（指定時はそのエージェント宛のタスクのみ）
            
        Returns:
            List[Dict[str, Any]]: アクティブタスクのリスト
        """
        tasks = list(self._active_tasks.values())
        
        if specialist_agent:
            tasks = [task for task in tasks if task["recipient"] == specialist_agent]
            
        return sorted(tasks, key=lambda x: x.get("created_at", ""))
    
    def get_completed_tasks(self, specialist_agent: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        完了したタスクのリストを取得します。
        
        Args:
            specialist_agent: 専門エージェント（指定時はそのエージェント宛のタスクのみ）
            
        Returns:
            List[Dict[str, Any]]: 完了タスクのリスト
        """
        tasks = list(self._completed_tasks.values())
        
        if specialist_agent:
            tasks = [task for task in tasks if task["recipient"] == specialist_agent]
            
        return sorted(tasks, key=lambda x: x.get("completed_at", ""), reverse=True)
    
    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        タスク履歴を取得します。
        
        Args:
            limit: 取得する履歴の最大数
            
        Returns:
            List[Dict[str, Any]]: タスク履歴のリスト
        """
        return sorted(self._task_history, key=lambda x: x.get("updated_at", ""), reverse=True)[:limit]
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        タスク情報を取得します。
        
        Args:
            task_id: タスクID
            
        Returns:
            Optional[Dict[str, Any]]: タスク情報（存在しない場合はNone）
        """
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]
        elif task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        return None
    
    def save_to_file(self, filepath: str = "storage/specialist_tasks.json") -> None:
        """
        タスク情報をファイルに保存します。
        
        Args:
            filepath: 保存先ファイルパス
        """
        # ディレクトリがなければ作成
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            "active_tasks": self._active_tasks,
            "completed_tasks": self._completed_tasks,
            "task_history": self._task_history
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"タスク情報をファイルに保存しました: {filepath}")
    
    def load_from_file(self, filepath: str = "storage/specialist_tasks.json") -> bool:
        """
        ファイルからタスク情報を読み込みます。
        
        Args:
            filepath: 読み込み元ファイルパス
            
        Returns:
            bool: 読み込み成功の場合はTrue
        """
        if not os.path.exists(filepath):
            logger.warning(f"ファイルが存在しません: {filepath}")
            return False
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._active_tasks = data.get("active_tasks", {})
            self._completed_tasks = data.get("completed_tasks", {})
            self._task_history = data.get("task_history", [])
            
            logger.info(f"タスク情報をファイルから読み込みました: {filepath}")
            return True
        except Exception as e:
            logger.error(f"ファイルからの読み込み中にエラーが発生しました: {str(e)}")
            return False


# タスクレジストリのインスタンスを作成（シングルトン）
task_registry = SpecialistTaskRegistry()


class SpecialistWorkflowAutomation:
    """
    専門エージェント連携ワークフローの自動化を行うクラス。
    専門エージェントの起動判断、タスク依頼、PM承認、結果連携のプロセスを自動化します。
    """
    
    def __init__(self):
        """ワークフロー自動化クラスを初期化します。"""
        # エージェント登録
        self._register_agents()
        # ハンドラー登録
        self._register_handlers()
    
    def _register_agents(self) -> None:
        """エージェントをメッセージディスパッチャーに登録します。"""
        # コアエージェント登録
        dispatcher.register_agent(CoreAgents.PDM)
        dispatcher.register_agent(CoreAgents.PM)
        dispatcher.register_agent(CoreAgents.DESIGNER)
        dispatcher.register_agent(CoreAgents.PL)
        dispatcher.register_agent(CoreAgents.ENGINEER)
        dispatcher.register_agent(CoreAgents.TESTER)
        
        # 専門エージェント登録
        dispatcher.register_agent(SpecialistAgents.AI_ARCHITECT)
        dispatcher.register_agent(SpecialistAgents.PROMPT_ENGINEER)
        dispatcher.register_agent(SpecialistAgents.DATA_ENGINEER)
    
    def _register_handlers(self) -> None:
        """メッセージハンドラーを登録します。"""
        # PMのタスク承認ハンドラー
        dispatcher.register_handler(CoreAgents.PM, "task_request", self._pm_task_approval_handler)
        
        # 専門エージェントの進捗更新ハンドラー
        dispatcher.register_handler(SpecialistAgents.AI_ARCHITECT, "status_update", self._specialist_status_update_handler)
        dispatcher.register_handler(SpecialistAgents.PROMPT_ENGINEER, "status_update", self._specialist_status_update_handler)
        dispatcher.register_handler(SpecialistAgents.DATA_ENGINEER, "status_update", self._specialist_status_update_handler)
        
        # タスク応答ハンドラー
        dispatcher.register_handler(SpecialistAgents.AI_ARCHITECT, "task_response", self._specialist_task_response_handler)
        dispatcher.register_handler(SpecialistAgents.PROMPT_ENGINEER, "task_response", self._specialist_task_response_handler)
        dispatcher.register_handler(SpecialistAgents.DATA_ENGINEER, "task_response", self._specialist_task_response_handler)
    
    def _pm_task_approval_handler(self, message) -> None:
        """
        PMによるタスク承認を処理するハンドラー。
        
        Args:
            message: タスク承認メッセージ
        """
        # ここではPMへのタスク依頼を処理
        # 実際の実装では、PMがUIから承認するため、このハンドラーはタスク通知のみを行う
        logger.info(f"PMにタスク依頼が届きました: {message.request_id}")
        
        # タスクを登録
        task_registry.register_task(
            task_id=message.request_id,
            sender=message.sender,
            recipient=message.recipient,
            task_type=message.content.get("task_type"),
            description=message.content.get("description"),
            priority=message.content.get("priority"),
            deadline=message.content.get("deadline"),
            context=message.content.get("context")
        )
        
        # TODO: 実際の実装では、PMに通知を送り、UIから承認を行えるようにする
        # デモ用に自動承認のロジックを追加
        self._simulate_pm_approval(message.request_id)
    
    def _simulate_pm_approval(self, task_id: str) -> None:
        """
        デモ用のPM承認シミュレーション。
        
        Args:
            task_id: タスクID
        """
        task_info = task_registry.get_task_info(task_id)
        if task_info:
            # 承認
            task_registry.approve_task(task_id)
            
            # 専門エージェントへのタスク転送
            update_task_status(
                sender=CoreAgents.PM,
                recipient=task_info["recipient"],
                request_id=task_id,
                status=TaskStatus.ACCEPTED.value,
                message="PMによって承認されました。タスクを実行してください。"
            )
    
    def _specialist_status_update_handler(self, message) -> None:
        """
        専門エージェントからのステータス更新を処理するハンドラー。
        
        Args:
            message: ステータス更新メッセージ
        """
        task_id = message.reference_id
        status = message.content.get("status")
        progress = message.content.get("progress")
        
        # タスク状態を更新
        task_registry.update_task_status(task_id, status, progress)
        
        # 元の依頼者にも状態更新を転送
        task_info = task_registry.get_task_info(task_id)
        if task_info:
            update_task_status(
                sender=message.sender,
                recipient=task_info["sender"],
                request_id=task_id,
                status=status,
                progress=progress,
                message=message.content.get("message")
            )
    
    def _specialist_task_response_handler(self, message) -> None:
        """
        専門エージェントからのタスク応答を処理するハンドラー。
        
        Args:
            message: タスク応答メッセージ
        """
        task_id = message.reference_id
        status = message.content.get("status")
        result = message.content.get("result")
        attachments = message.content.get("attachments")
        
        # タスク状態と結果を更新
        task_registry.update_task_status(task_id, status)
        if result:
            task_registry.set_task_result(task_id, result, attachments)
        
        # 元の依頼者にも応答を転送
        task_info = task_registry.get_task_info(task_id)
        if task_info:
            send_task_response(
                sender=message.sender,
                recipient=task_info["sender"],
                request_id=task_id,
                status=status,
                result=result,
                message=message.content.get("message"),
                attachments=attachments
            )
    
    def request_specialist_task(
        self,
        sender: str,
        specialist: str,
        task_type: Union[TaskType, str],
        description: str,
        priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
        deadline: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[str]] = None
    ) -> str:
        """
        専門エージェントにタスクを依頼します。
        
        Args:
            sender: 送信元エージェント
            specialist: 専門エージェント
            task_type: タスク種別
            description: タスク詳細
            priority: 優先度（デフォルト：中）
            deadline: 期限（ISO 8601形式の日時文字列）
            context: コンテキスト情報（辞書）
            attachments: 添付ファイル（オプション）
            
        Returns:
            str: タスクID
        """
        # 専門エージェント起動条件の確認は、業務ロジックで行われるべき
        # ここではPMを通してタスク依頼を送信するプロセスを実装
        
        # PMにタスク依頼を送信
        task_id = send_task_request(
            sender=sender,
            recipient=CoreAgents.PM,  # PMを経由
            task_type=task_type,
            description=description,
            priority=priority,
            deadline=deadline,
            context={
                **(context or {}),
                "target_specialist": specialist  # 最終的な担当専門エージェント
            },
            attachments=attachments
        )
        
        logger.info(f"{sender}から{specialist}へのタスク依頼をPM経由で送信しました: {task_id}")
        return task_id
    
    def is_specialist_needed(self, context: Dict[str, Any], task: str) -> Tuple[bool, Optional[str]]:
        """
        専門エージェントが必要かどうかを判断します。
        
        Args:
            context: タスクコンテキスト
            task: タスク内容
            
        Returns:
            Tuple[bool, Optional[str]]: (必要かどうか, 必要な専門エージェント)
        """
        # 単純なキーワードマッチングによる判断（実際の実装ではもっと複雑なロジックになる）
        
        # AIアーキテクト判定
        ai_architect_keywords = [
            "アーキテクチャ", "設計", "システム構成", "技術スタック", "スケーラビリティ", 
            "AI設計", "システム設計", "アーキテクト", "インフラ設計"
        ]
        
        # プロンプトエンジニア判定
        prompt_engineer_keywords = [
            "プロンプト", "LLM", "指示", "プロンプトエンジニアリング", "プロンプト設計",
            "プロンプト最適化", "モデル応答", "GPT", "指示調整"
        ]
        
        # データエンジニア判定
        data_engineer_keywords = [
            "データ", "パイプライン", "ETL", "データクレンジング", "データ変換",
            "データ抽出", "データベース", "データモデル", "データフロー"
        ]
        
        # タスク内容にキーワードが含まれるか確認
        for keyword in ai_architect_keywords:
            if keyword in task:
                return True, SpecialistAgents.AI_ARCHITECT
        
        for keyword in prompt_engineer_keywords:
            if keyword in task:
                return True, SpecialistAgents.PROMPT_ENGINEER
        
        for keyword in data_engineer_keywords:
            if keyword in task:
                return True, SpecialistAgents.DATA_ENGINEER
        
        return False, None
    
    def handle_specialist_request(
        self,
        core_agent: str,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        コアエージェントからの専門エージェント依頼を処理します。
        
        Args:
            core_agent: コアエージェント
            task_description: タスク説明
            context: タスクコンテキスト
            
        Returns:
            Optional[str]: タスクID（依頼しなかった場合はNone）
        """
        # 専門エージェントが必要かどうかを判断
        needed, specialist = self.is_specialist_needed(context or {}, task_description)
        
        if not needed or specialist is None:
            logger.info(f"専門エージェントは不要と判断されました: {task_description[:30]}...")
            return None
        
        # タスク種別を推定
        task_type = self._estimate_task_type(specialist, task_description)
        
        # 専門エージェントにタスクを依頼
        task_id = self.request_specialist_task(
            sender=core_agent,
            specialist=specialist,
            task_type=task_type,
            description=task_description,
            context=context
        )
        
        logger.info(f"{core_agent}から{specialist}へタスクを依頼しました: {task_id}")
        return task_id
    
    def _estimate_task_type(self, specialist: str, task_description: str) -> str:
        """
        タスク種別を推定します。
        
        Args:
            specialist: 専門エージェント
            task_description: タスク説明
            
        Returns:
            str: 推定されたタスク種別
        """
        # 簡易的な推定ロジック（実際の実装ではより高度な分類を行う）
        if specialist == SpecialistAgents.AI_ARCHITECT:
            if "アーキテクチャ" in task_description or "設計" in task_description:
                return TaskType.ARCHITECTURE_DESIGN.value
            elif "技術スタック" in task_description:
                return TaskType.TECH_STACK_SELECTION.value
            else:
                return TaskType.CONSULTATION.value
                
        elif specialist == SpecialistAgents.PROMPT_ENGINEER:
            if "設計" in task_description:
                return TaskType.PROMPT_DESIGN.value
            elif "最適化" in task_description:
                return TaskType.PROMPT_OPTIMIZATION.value
            elif "評価" in task_description:
                return TaskType.PROMPT_EVALUATION.value
            else:
                return TaskType.CONSULTATION.value
                
        elif specialist == SpecialistAgents.DATA_ENGINEER:
            if "抽出" in task_description:
                return TaskType.DATA_EXTRACTION.value
            elif "クリーニング" in task_description:
                return TaskType.DATA_CLEANING.value
            elif "変換" in task_description:
                return TaskType.DATA_TRANSFORMATION.value
            elif "パイプライン" in task_description:
                return TaskType.DATA_PIPELINE_DESIGN.value
            else:
                return TaskType.CONSULTATION.value
        
        return TaskType.CONSULTATION.value
    
    def get_specialist_dashboard_data(self) -> Dict[str, Any]:
        """
        専門エージェントダッシュボード用のデータを取得します。
        
        Returns:
            Dict[str, Any]: ダッシュボードデータ
        """
        # 各専門エージェントのアクティブタスク
        ai_architect_tasks = task_registry.get_active_tasks(SpecialistAgents.AI_ARCHITECT)
        prompt_engineer_tasks = task_registry.get_active_tasks(SpecialistAgents.PROMPT_ENGINEER)
        data_engineer_tasks = task_registry.get_active_tasks(SpecialistAgents.DATA_ENGINEER)
        
        # 各専門エージェントの完了タスク
        ai_architect_completed = task_registry.get_completed_tasks(SpecialistAgents.AI_ARCHITECT)
        prompt_engineer_completed = task_registry.get_completed_tasks(SpecialistAgents.PROMPT_ENGINEER)
        data_engineer_completed = task_registry.get_completed_tasks(SpecialistAgents.DATA_ENGINEER)
        
        # 集計情報（各状態のタスク数など）
        ai_architect_stats = self._calculate_agent_stats(ai_architect_tasks, ai_architect_completed)
        prompt_engineer_stats = self._calculate_agent_stats(prompt_engineer_tasks, prompt_engineer_completed)
        data_engineer_stats = self._calculate_agent_stats(data_engineer_tasks, data_engineer_completed)
        
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "active_tasks_count": len(ai_architect_tasks) + len(prompt_engineer_tasks) + len(data_engineer_tasks),
            "completed_tasks_count": len(ai_architect_completed) + len(prompt_engineer_completed) + len(data_engineer_completed),
            "agents": {
                SpecialistAgents.AI_ARCHITECT: {
                    "active_tasks": ai_architect_tasks,
                    "completed_tasks": ai_architect_completed[:5],  # 最新5件のみ
                    "stats": ai_architect_stats
                },
                SpecialistAgents.PROMPT_ENGINEER: {
                    "active_tasks": prompt_engineer_tasks,
                    "completed_tasks": prompt_engineer_completed[:5],  # 最新5件のみ
                    "stats": prompt_engineer_stats
                },
                SpecialistAgents.DATA_ENGINEER: {
                    "active_tasks": data_engineer_tasks,
                    "completed_tasks": data_engineer_completed[:5],  # 最新5件のみ
                    "stats": data_engineer_stats
                }
            },
            "recent_activities": task_registry.get_task_history(10)  # 最新10件のアクティビティ
        }
    
    def _calculate_agent_stats(self, active_tasks: List[Dict[str, Any]], completed_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        エージェントの統計情報を計算します。
        
        Args:
            active_tasks: アクティブタスクのリスト
            completed_tasks: 完了タスクのリスト
            
        Returns:
            Dict[str, Any]: 統計情報
        """
        # 状態ごとのカウント
        status_counts = {}
        for task in active_tasks:
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 完了タスクの結果統計
        success_count = 0
        fail_count = 0
        
        for task in completed_tasks:
            final_status = task.get("final_status")
            if final_status == TaskStatus.COMPLETED.value:
                success_count += 1
            elif final_status in [TaskStatus.FAILED.value, TaskStatus.REJECTED.value]:
                fail_count += 1
        
        # 平均応答時間の計算
        response_times = []
        for task in completed_tasks:
            created_at = datetime.datetime.fromisoformat(task.get("created_at", ""))
            completed_at = datetime.datetime.fromisoformat(task.get("completed_at", ""))
            response_time = (completed_at - created_at).total_seconds() / 60  # 分単位
            response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "active_count": len(active_tasks),
            "completed_count": len(completed_tasks),
            "success_rate": success_count / len(completed_tasks) if completed_tasks else 0,
            "status_distribution": status_counts,
            "avg_response_time_minutes": avg_response_time
        }


# ワークフロー自動化のインスタンスを作成
workflow_automation = SpecialistWorkflowAutomation()


def request_ai_architect_task(
    sender: str,
    task_type: Union[TaskType, str],
    description: str,
    priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
    deadline: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None
) -> str:
    """
    AIアーキテクトエージェントにタスクを依頼するヘルパー関数。
    
    Args:
        sender: 送信元エージェント
        task_type: タスク種別
        description: タスク詳細
        priority: 優先度（デフォルト：中）
        deadline: 期限（ISO 8601形式の日時文字列）
        context: コンテキスト情報（辞書）
        attachments: 添付ファイル（オプション）
        
    Returns:
        str: タスクID
    """
    return workflow_automation.request_specialist_task(
        sender=sender,
        specialist=SpecialistAgents.AI_ARCHITECT,
        task_type=task_type,
        description=description,
        priority=priority,
        deadline=deadline,
        context=context,
        attachments=attachments
    )


def request_prompt_engineer_task(
    sender: str,
    task_type: Union[TaskType, str],
    description: str,
    priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
    deadline: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None
) -> str:
    """
    プロンプトエンジニアエージェントにタスクを依頼するヘルパー関数。
    
    Args:
        sender: 送信元エージェント
        task_type: タスク種別
        description: タスク詳細
        priority: 優先度（デフォルト：中）
        deadline: 期限（ISO 8601形式の日時文字列）
        context: コンテキスト情報（辞書）
        attachments: 添付ファイル（オプション）
        
    Returns:
        str: タスクID
    """
    return workflow_automation.request_specialist_task(
        sender=sender,
        specialist=SpecialistAgents.PROMPT_ENGINEER,
        task_type=task_type,
        description=description,
        priority=priority,
        deadline=deadline,
        context=context,
        attachments=attachments
    )


def request_data_engineer_task(
    sender: str,
    task_type: Union[TaskType, str],
    description: str,
    priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
    deadline: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None
) -> str:
    """
    データエンジニアエージェントにタスクを依頼するヘルパー関数。
    
    Args:
        sender: 送信元エージェント
        task_type: タスク種別
        description: タスク詳細
        priority: 優先度（デフォルト：中）
        deadline: 期限（ISO 8601形式の日時文字列）
        context: コンテキスト情報（辞書）
        attachments: 添付ファイル（オプション）
        
    Returns:
        str: タスクID
    """
    return workflow_automation.request_specialist_task(
        sender=sender,
        specialist=SpecialistAgents.DATA_ENGINEER,
        task_type=task_type,
        description=description,
        priority=priority,
        deadline=deadline,
        context=context,
        attachments=attachments
    )


def get_dashboard_data() -> Dict[str, Any]:
    """
    専門エージェントダッシュボード用のデータを取得するヘルパー関数。
    
    Returns:
        Dict[str, Any]: ダッシュボードデータ
    """
    return workflow_automation.get_specialist_dashboard_data()


# 初期化時にタスク履歴を読み込む
task_registry.load_from_file() 