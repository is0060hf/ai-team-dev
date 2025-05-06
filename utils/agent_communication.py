"""
専門エージェントとコアエージェント間の標準通信プロトコルライブラリ。
エージェント間でのタスク依頼、情報交換、結果共有を標準化します。
"""

import json
import uuid
import datetime
from typing import Dict, List, Any, Optional, Union
from enum import Enum

from utils.logger import get_agent_logger

logger = get_agent_logger("agent_communication")


class TaskPriority(Enum):
    """タスク優先度の定義"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    CRITICAL = "緊急"


class TaskStatus(Enum):
    """タスク状態の定義"""
    PENDING = "保留中"
    ACCEPTED = "受理済"
    IN_PROGRESS = "処理中"
    WAITING_FOR_INFO = "情報待ち"
    COMPLETED = "完了"
    FAILED = "失敗"
    REJECTED = "拒否"


class TaskType(Enum):
    """タスク種別の定義"""
    # AIアーキテクト関連タスク
    ARCHITECTURE_DESIGN = "アーキテクチャ設計"
    TECH_STACK_SELECTION = "技術スタック選定"
    AI_MODEL_EVALUATION = "AIモデル評価"
    
    # プロンプトエンジニア関連タスク
    PROMPT_DESIGN = "プロンプト設計"
    PROMPT_OPTIMIZATION = "プロンプト最適化"
    PROMPT_EVALUATION = "プロンプト評価"
    
    # データエンジニア関連タスク
    DATA_EXTRACTION = "データ抽出"
    DATA_CLEANING = "データクリーニング"
    DATA_TRANSFORMATION = "データ変換"
    DATA_PIPELINE_DESIGN = "データパイプライン設計"
    
    # 共通タスク
    CONSULTATION = "相談・アドバイス"
    REVIEW = "レビュー"
    RESEARCH = "調査・リサーチ"


class AgentMessage:
    """
    エージェント間メッセージの基本クラス。
    標準化されたメッセージフォーマットを提供します。
    """
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        content: Dict[str, Any],
        request_id: Optional[str] = None,
        reference_id: Optional[str] = None
    ):
        """
        エージェントメッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            message_type: メッセージタイプ
            content: メッセージ本文（辞書）
            request_id: リクエストID（省略時は自動生成）
            reference_id: 参照元メッセージID（返信の場合など）
        """
        self.request_id = request_id or str(uuid.uuid4())
        self.sender = sender
        self.recipient = recipient
        self.message_type = message_type
        self.content = content
        self.timestamp = datetime.datetime.now().isoformat()
        self.reference_id = reference_id
    
    def to_dict(self) -> Dict[str, Any]:
        """メッセージを辞書形式に変換します。"""
        return {
            "request_id": self.request_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "reference_id": self.reference_id
        }
    
    def to_json(self) -> str:
        """メッセージをJSON形式に変換します。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """辞書からメッセージオブジェクトを作成します。"""
        return cls(
            sender=data["sender"],
            recipient=data["recipient"],
            message_type=data["message_type"],
            content=data["content"],
            request_id=data.get("request_id"),
            reference_id=data.get("reference_id")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        """JSON文字列からメッセージオブジェクトを作成します。"""
        return cls.from_dict(json.loads(json_str))


class TaskRequest(AgentMessage):
    """タスク依頼メッセージ"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        task_type: Union[TaskType, str],
        description: str,
        priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
        deadline: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[str]] = None,
        request_id: Optional[str] = None
    ):
        """
        タスク依頼メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            task_type: タスク種別
            description: タスク詳細説明
            priority: 優先度（デフォルト：中）
            deadline: 期限（ISO 8601形式の日時文字列）
            context: 関連情報（辞書）
            attachments: 関連ファイルパスのリスト
            request_id: リクエストID（省略時は自動生成）
        """
        # TaskTypeオブジェクトの場合は値を取得、文字列ならそのまま使用
        task_type_str = task_type.value if isinstance(task_type, TaskType) else task_type
        # TaskPriorityオブジェクトの場合は値を取得、文字列ならそのまま使用
        priority_str = priority.value if isinstance(priority, TaskPriority) else priority
        
        content = {
            "task_type": task_type_str,
            "description": description,
            "priority": priority_str,
            "deadline": deadline,
            "context": context or {},
            "attachments": attachments or [],
            "status": TaskStatus.PENDING.value
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="task_request",
            content=content,
            request_id=request_id
        )


class TaskResponse(AgentMessage):
    """タスク応答メッセージ"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        status: Union[TaskStatus, str],
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ):
        """
        タスク応答メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            request_id: 元のタスク依頼のリクエストID
            status: タスク状態
            result: タスク結果（辞書）
            message: 追加メッセージ
            attachments: 関連ファイルパスのリスト
        """
        # TaskStatusオブジェクトの場合は値を取得、文字列ならそのまま使用
        status_str = status.value if isinstance(status, TaskStatus) else status
        
        content = {
            "status": status_str,
            "result": result or {},
            "message": message or "",
            "attachments": attachments or []
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="task_response",
            content=content,
            reference_id=request_id
        )


class InfoRequest(AgentMessage):
    """情報要求メッセージ"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        questions: List[str],
        context: Optional[Dict[str, Any]] = None
    ):
        """
        情報要求メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            request_id: 関連するタスクのリクエストID
            questions: 質問のリスト
            context: 質問の背景情報（辞書）
        """
        content = {
            "questions": questions,
            "context": context or {}
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="info_request",
            content=content,
            reference_id=request_id
        )


class InfoResponse(AgentMessage):
    """情報応答メッセージ"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        answers: Dict[str, Any],
        attachments: Optional[List[str]] = None
    ):
        """
        情報応答メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            request_id: 情報要求のリクエストID
            answers: 質問への回答（辞書）
            attachments: 関連ファイルパスのリスト
        """
        content = {
            "answers": answers,
            "attachments": attachments or []
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="info_response",
            content=content,
            reference_id=request_id
        )


class StatusUpdate(AgentMessage):
    """ステータス更新メッセージ"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        status: Union[TaskStatus, str],
        progress: Optional[float] = None,
        message: Optional[str] = None
    ):
        """
        ステータス更新メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            request_id: 関連するタスクのリクエストID
            status: タスク状態
            progress: 進捗率（0.0-1.0）
            message: 追加メッセージ
        """
        # TaskStatusオブジェクトの場合は値を取得、文字列ならそのまま使用
        status_str = status.value if isinstance(status, TaskStatus) else status
        
        content = {
            "status": status_str,
            "progress": progress,
            "message": message or ""
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="status_update",
            content=content,
            reference_id=request_id
        )


# メッセージディスパッチャー（シングルトンパターン）
class MessageDispatcher:
    """
    エージェント間メッセージの送受信を管理するディスパッチャー。
    メッセージの登録、キュー管理、配信を担当します。
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageDispatcher, cls).__new__(cls)
            cls._instance._message_queues = {}  # エージェントごとのメッセージキュー
            cls._instance._handlers = {}  # メッセージタイプごとのハンドラー
        return cls._instance
    
    def register_agent(self, agent_id: str) -> None:
        """
        エージェントを登録します。
        
        Args:
            agent_id: エージェントID
        """
        if agent_id not in self._message_queues:
            self._message_queues[agent_id] = []
            logger.info(f"エージェント {agent_id} を登録しました")
    
    def register_handler(self, agent_id: str, message_type: str, handler_function: callable) -> None:
        """
        メッセージハンドラーを登録します。
        
        Args:
            agent_id: エージェントID
            message_type: 処理するメッセージタイプ
            handler_function: ハンドラー関数
        """
        if agent_id not in self._handlers:
            self._handlers[agent_id] = {}
        
        self._handlers[agent_id][message_type] = handler_function
        logger.info(f"エージェント {agent_id} の {message_type} ハンドラーを登録しました")
    
    def send_message(self, message: AgentMessage) -> bool:
        """
        メッセージを送信します。
        
        Args:
            message: 送信するメッセージ
            
        Returns:
            bool: 送信成功の場合はTrue
        """
        recipient = message.recipient
        
        if recipient not in self._message_queues:
            logger.warning(f"受信先 {recipient} が見つかりません")
            return False
        
        # メッセージをキューに追加
        self._message_queues[recipient].append(message)
        logger.info(f"メッセージを {message.sender} から {recipient} へ送信しました（ID: {message.request_id}）")
        
        # 非同期処理として実装する場合は、ここでイベントを発火するなどの処理を行う
        # 現在の実装では同期的に処理
        self._process_message(recipient, message)
        
        return True
    
    def _process_message(self, agent_id: str, message: AgentMessage) -> None:
        """
        メッセージを処理します。
        
        Args:
            agent_id: 処理するエージェントID
            message: 処理するメッセージ
        """
        if agent_id in self._handlers and message.message_type in self._handlers[agent_id]:
            handler = self._handlers[agent_id][message.message_type]
            try:
                handler(message)
                logger.info(f"エージェント {agent_id} がメッセージを処理しました（ID: {message.request_id}）")
            except Exception as e:
                logger.error(f"メッセージ処理中にエラーが発生しました: {str(e)}")
        else:
            logger.warning(f"エージェント {agent_id} には {message.message_type} のハンドラーがありません")
    
    def get_messages(self, agent_id: str, message_type: Optional[str] = None) -> List[AgentMessage]:
        """
        エージェントのメッセージキューからメッセージを取得します。
        
        Args:
            agent_id: エージェントID
            message_type: 取得するメッセージタイプ（省略時は全て）
            
        Returns:
            List[AgentMessage]: メッセージのリスト
        """
        if agent_id not in self._message_queues:
            logger.warning(f"エージェント {agent_id} が見つかりません")
            return []
        
        messages = self._message_queues[agent_id]
        if message_type:
            messages = [msg for msg in messages if msg.message_type == message_type]
        
        return messages
    
    def get_task_status(self, request_id: str) -> Optional[str]:
        """
        タスクの状態を取得します。
        
        Args:
            request_id: タスクのリクエストID
            
        Returns:
            Optional[str]: タスクの状態（見つからない場合はNone）
        """
        for queue in self._message_queues.values():
            for message in queue:
                if message.request_id == request_id and message.message_type == "task_response":
                    return message.content.get("status")
                if message.request_id == request_id and message.message_type == "status_update":
                    return message.content.get("status")
        
        return None


# インスタンスを作成（シングルトン）
dispatcher = MessageDispatcher()


def create_task_request(
    sender: str,
    recipient: str,
    task_type: Union[TaskType, str],
    description: str,
    priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
    deadline: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None
) -> TaskRequest:
    """
    タスク依頼メッセージを作成するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        task_type: タスク種別
        description: タスク詳細説明
        priority: 優先度（デフォルト：中）
        deadline: 期限（ISO 8601形式の日時文字列）
        context: 関連情報（辞書）
        attachments: 関連ファイルパスのリスト
        
    Returns:
        TaskRequest: 作成されたタスク依頼メッセージ
    """
    return TaskRequest(
        sender=sender,
        recipient=recipient,
        task_type=task_type,
        description=description,
        priority=priority,
        deadline=deadline,
        context=context,
        attachments=attachments
    )


def create_task_response(
    sender: str,
    recipient: str,
    request_id: str,
    status: Union[TaskStatus, str],
    result: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    attachments: Optional[List[str]] = None
) -> TaskResponse:
    """
    タスク応答メッセージを作成するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        request_id: 元のタスク依頼のリクエストID
        status: タスク状態
        result: タスク結果（辞書）
        message: 追加メッセージ
        attachments: 関連ファイルパスのリスト
        
    Returns:
        TaskResponse: 作成されたタスク応答メッセージ
    """
    return TaskResponse(
        sender=sender,
        recipient=recipient,
        request_id=request_id,
        status=status,
        result=result,
        message=message,
        attachments=attachments
    )


def send_task_request(
    sender: str,
    recipient: str,
    task_type: Union[TaskType, str],
    description: str,
    priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
    deadline: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None
) -> str:
    """
    タスク依頼メッセージを送信するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        task_type: タスク種別
        description: タスク詳細説明
        priority: 優先度（デフォルト：中）
        deadline: 期限（ISO 8601形式の日時文字列）
        context: 関連情報（辞書）
        attachments: 関連ファイルパスのリスト
        
    Returns:
        str: 送信されたタスク依頼のリクエストID
    """
    task_request = create_task_request(
        sender=sender,
        recipient=recipient,
        task_type=task_type,
        description=description,
        priority=priority,
        deadline=deadline,
        context=context,
        attachments=attachments
    )
    
    dispatcher.send_message(task_request)
    logger.info(f"{sender} から {recipient} へタスク依頼を送信しました（ID: {task_request.request_id}）")
    
    return task_request.request_id


def send_task_response(
    sender: str,
    recipient: str,
    request_id: str,
    status: Union[TaskStatus, str],
    result: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    attachments: Optional[List[str]] = None
) -> None:
    """
    タスク応答メッセージを送信するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        request_id: 元のタスク依頼のリクエストID
        status: タスク状態
        result: タスク結果（辞書）
        message: 追加メッセージ
        attachments: 関連ファイルパスのリスト
    """
    task_response = create_task_response(
        sender=sender,
        recipient=recipient,
        request_id=request_id,
        status=status,
        result=result,
        message=message,
        attachments=attachments
    )
    
    dispatcher.send_message(task_response)
    logger.info(f"{sender} から {recipient} へタスク応答を送信しました（ID: {task_response.request_id}）")


def update_task_status(
    sender: str,
    recipient: str,
    request_id: str,
    status: Union[TaskStatus, str],
    progress: Optional[float] = None,
    message: Optional[str] = None
) -> None:
    """
    タスク状態を更新するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        request_id: 関連するタスクのリクエストID
        status: タスク状態
        progress: 進捗率（0.0-1.0）
        message: 追加メッセージ
    """
    status_update = StatusUpdate(
        sender=sender,
        recipient=recipient,
        request_id=request_id,
        status=status,
        progress=progress,
        message=message
    )
    
    dispatcher.send_message(status_update)
    logger.info(f"{sender} から {recipient} へステータス更新を送信しました（ID: {status_update.request_id}）")


def request_information(
    sender: str,
    recipient: str,
    request_id: str,
    questions: List[str],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    情報要求メッセージを送信するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        request_id: 関連するタスクのリクエストID
        questions: 質問のリスト
        context: 質問の背景情報（辞書）
        
    Returns:
        str: 送信された情報要求のリクエストID
    """
    info_request = InfoRequest(
        sender=sender,
        recipient=recipient,
        request_id=request_id,
        questions=questions,
        context=context
    )
    
    dispatcher.send_message(info_request)
    logger.info(f"{sender} から {recipient} へ情報要求を送信しました（ID: {info_request.request_id}）")
    
    return info_request.request_id


def respond_to_information(
    sender: str,
    recipient: str,
    request_id: str,
    answers: Dict[str, Any],
    attachments: Optional[List[str]] = None
) -> None:
    """
    情報応答メッセージを送信するヘルパー関数。
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        request_id: 情報要求のリクエストID
        answers: 質問への回答（辞書）
        attachments: 関連ファイルパスのリスト
    """
    info_response = InfoResponse(
        sender=sender,
        recipient=recipient,
        request_id=request_id,
        answers=answers,
        attachments=attachments
    )
    
    dispatcher.send_message(info_response)
    logger.info(f"{sender} から {recipient} へ情報応答を送信しました（ID: {info_response.request_id}）")


def get_task_status(request_id: str) -> Optional[str]:
    """
    タスクの状態を取得するヘルパー関数。
    
    Args:
        request_id: タスクのリクエストID
        
    Returns:
        Optional[str]: タスクの状態（見つからない場合はNone）
    """
    return dispatcher.get_task_status(request_id) 