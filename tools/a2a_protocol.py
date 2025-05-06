"""
A2A（Agent to Agent）通信プロトコルモジュール。
エージェント間の標準化された通信インターフェースを提供します。
A2A標準仕様: https://github.com/google/agent-to-agent
"""

import uuid
import json
import time
import asyncio
import logging
import aiohttp
import ssl
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable, Type, TypeVar, Generic, Awaitable

from utils.logger import get_logger

logger = get_logger("a2a_protocol")

class TaskStatus(Enum):
    """タスクのステータス"""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"

class MessageRole(Enum):
    """メッセージの役割"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

class ContentType(Enum):
    """メッセージコンテンツのタイプ"""
    TEXT = "text"
    FILE = "file"
    DATA = "data"
    ERROR = "error"

@dataclass
class TextPart:
    """テキストパート"""
    type: str = "text"
    text: str = ""

@dataclass
class FilePart:
    """ファイルパート"""
    type: str = "file"
    file_id: str = ""
    mime_type: str = ""
    file_name: Optional[str] = None

@dataclass
class DataPart:
    """データパート"""
    type: str = "data"
    mime_type: str = "application/json"
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorPart:
    """エラーパート"""
    type: str = "error"
    code: str = ""
    message: str = ""
    details: Optional[Dict[str, Any]] = None

@dataclass
class Message:
    """A2Aメッセージ"""
    role: str
    parts: List[Union[TextPart, FilePart, DataPart, ErrorPart]] = field(default_factory=list)
    name: Optional[str] = None
    
    def add_text(self, text: str) -> 'Message':
        """テキストを追加"""
        self.parts.append(TextPart(text=text))
        return self
    
    def add_file(self, file_id: str, mime_type: str, file_name: Optional[str] = None) -> 'Message':
        """ファイルを追加"""
        self.parts.append(FilePart(file_id=file_id, mime_type=mime_type, file_name=file_name))
        return self
    
    def add_data(self, data: Dict[str, Any], mime_type: str = "application/json") -> 'Message':
        """データを追加"""
        self.parts.append(DataPart(mime_type=mime_type, data=data))
        return self
    
    def add_error(self, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> 'Message':
        """エラーを追加"""
        self.parts.append(ErrorPart(code=code, message=message, details=details))
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        result = {"role": self.role, "parts": []}
        
        if self.name:
            result["name"] = self.name
        
        for part in self.parts:
            if isinstance(part, TextPart):
                result["parts"].append({"type": "text", "text": part.text})
            elif isinstance(part, FilePart):
                file_part = {"type": "file", "file_id": part.file_id, "mime_type": part.mime_type}
                if part.file_name:
                    file_part["file_name"] = part.file_name
                result["parts"].append(file_part)
            elif isinstance(part, DataPart):
                result["parts"].append({"type": "data", "mime_type": part.mime_type, "data": part.data})
            elif isinstance(part, ErrorPart):
                error_part = {"type": "error", "code": part.code, "message": part.message}
                if part.details:
                    error_part["details"] = part.details
                result["parts"].append(error_part)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """辞書からメッセージを作成"""
        role = data.get("role", "user")
        name = data.get("name")
        msg = cls(role=role, name=name)
        
        for part_data in data.get("parts", []):
            part_type = part_data.get("type")
            
            if part_type == "text":
                msg.add_text(part_data.get("text", ""))
            elif part_type == "file":
                msg.add_file(
                    part_data.get("file_id", ""),
                    part_data.get("mime_type", ""),
                    part_data.get("file_name")
                )
            elif part_type == "data":
                msg.add_data(
                    part_data.get("data", {}),
                    part_data.get("mime_type", "application/json")
                )
            elif part_type == "error":
                msg.add_error(
                    part_data.get("code", ""),
                    part_data.get("message", ""),
                    part_data.get("details")
                )
        
        return msg

@dataclass
class Task:
    """A2Aタスク"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.SUBMITTED
    messages: List[Message] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    session_id: Optional[str] = None
    
    def add_message(self, message: Message) -> 'Task':
        """メッセージを追加"""
        self.messages.append(message)
        self.updated_at = time.time()
        return self
    
    def update_status(self, status: TaskStatus) -> 'Task':
        """ステータスを更新"""
        self.status = status
        self.updated_at = time.time()
        
        if status in [TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED]:
            self.completed_at = time.time()
        
        return self
    
    def add_artifact(self, artifact_id: str, data: Any, mime_type: str, name: Optional[str] = None) -> 'Task':
        """成果物を追加"""
        artifact = {
            "artifact_id": artifact_id,
            "mime_type": mime_type,
            "created_at": time.time()
        }
        
        if name:
            artifact["name"] = name
        
        # 実際のデータを格納する方法はアプリケーションによる
        # ここでは単純化のためデータも含める
        artifact["data"] = data
        
        self.artifacts.append(artifact)
        self.updated_at = time.time()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        result = {
            "task_id": self.task_id,
            "status": self.status.value,
            "messages": [msg.to_dict() for msg in self.messages],
            "artifacts": self.artifacts.copy(),
            "metadata": self.metadata.copy(),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self.completed_at:
            result["completed_at"] = self.completed_at
        
        if self.session_id:
            result["session_id"] = self.session_id
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """辞書からタスクを作成"""
        try:
            status = TaskStatus(data.get("status", "submitted"))
        except ValueError:
            logger.warning(f"Unknown task status: {data.get('status')}, falling back to SUBMITTED")
            status = TaskStatus.SUBMITTED
        
        messages = [Message.from_dict(msg_data) for msg_data in data.get("messages", [])]
        
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            status=status,
            messages=messages,
            artifacts=data.get("artifacts", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            completed_at=data.get("completed_at"),
            session_id=data.get("session_id")
        )

@dataclass
class Skill:
    """エージェントスキル定義"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Skill':
        """辞書からスキルを作成"""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            metadata=data.get("metadata", {})
        )

@dataclass
class AgentCard:
    """エージェントカード定義（Googleの仕様に準拠）"""
    name: str
    agent_url: str
    description: str
    default_role: str = "assistant"
    contact_email: Optional[str] = None
    version: str = "0.1.0"
    auth_methods: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_skill(self, skill: Skill) -> 'AgentCard':
        """スキルを追加"""
        self.skills.append(skill)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return {
            "name": self.name,
            "agent_url": self.agent_url,
            "description": self.description,
            "default_role": self.default_role,
            "contact_email": self.contact_email,
            "version": self.version,
            "auth_methods": self.auth_methods,
            "skills": [skill.to_dict() for skill in self.skills],
            "models": self.models,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCard':
        """辞書からエージェントカードを作成"""
        skills = [Skill.from_dict(skill_data) for skill_data in data.get("skills", [])]
        
        return cls(
            name=data.get("name", ""),
            agent_url=data.get("agent_url", ""),
            description=data.get("description", ""),
            default_role=data.get("default_role", "assistant"),
            contact_email=data.get("contact_email"),
            version=data.get("version", "0.1.0"),
            auth_methods=data.get("auth_methods", []),
            skills=skills,
            models=data.get("models", []),
            metadata=data.get("metadata", {})
        )

class A2AClient:
    """A2A APIクライアント"""
    
    def __init__(
        self,
        agent_url: str,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: int = 60
    ):
        self.agent_url = agent_url.rstrip('/')
        self.auth_token = auth_token
        self.api_key = api_key
        self.session = session
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._own_session = False
        self._first_update_callback = None
    
    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self._own_session = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session is not None:
            await self.session.close()
            self.session = None
    
    def _get_headers(self) -> Dict[str, str]:
        """リクエストヘッダーを作成"""
        headers = {'Content-Type': 'application/json'}
        
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        elif self.api_key:
            headers['X-API-Key'] = self.api_key
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """HTTP リクエストを実行"""
        url = f"{self.agent_url}/{endpoint.lstrip('/')}"
        
        if self.session is None:
            raise RuntimeError("Session is not initialized. Use 'async with' context.")
        
        async with self.session.request(
            method,
            url,
            json=data,
            params=params,
            headers=self._get_headers()
        ) as response:
            response_data = await response.json()
            
            if response.status >= 400:
                error_message = response_data.get('message', 'Unknown error')
                raise Exception(f"API error ({response.status}): {error_message}")
            
            return response_data
    
    async def get_agent_card(self) -> AgentCard:
        """エージェントカードを取得"""
        data = await self._make_request('GET', '/agent-card')
        return AgentCard.from_dict(data)
    
    async def submit_task(self, task: Task) -> Task:
        """タスクを提出"""
        data = await self._make_request('POST', '/tasks', data=task.to_dict())
        return Task.from_dict(data)
    
    async def get_task(self, task_id: str) -> Task:
        """タスクを取得"""
        data = await self._make_request('GET', f'/tasks/{task_id}')
        return Task.from_dict(data)
    
    async def update_task(self, task: Task) -> Task:
        """タスクを更新"""
        data = await self._make_request('PUT', f'/tasks/{task.task_id}', data=task.to_dict())
        return Task.from_dict(data)
    
    async def cancel_task(self, task_id: str) -> Task:
        """タスクをキャンセル"""
        data = await self._make_request('POST', f'/tasks/{task_id}/cancel')
        return Task.from_dict(data)
    
    async def add_message(self, task_id: str, message: Message) -> Task:
        """タスクにメッセージを追加"""
        data = await self._make_request(
            'POST',
            f'/tasks/{task_id}/messages',
            data=message.to_dict()
        )
        return Task.from_dict(data)
    
    async def stream_task_updates(
        self,
        task_id: str,
        update_callback: Callable[[Task], Awaitable[None]],
        first_update_callback: Optional[Callable[[Task], Awaitable[None]]] = None
    ) -> None:
        """タスクの更新をストリーミング受信"""
        url = f"{self.agent_url}/tasks/{task_id}/updates"
        self._first_update_callback = first_update_callback or update_callback
        
        if self.session is None:
            raise RuntimeError("Session is not initialized. Use 'async with' context.")
        
        async with self.session.get(url, headers=self._get_headers()) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"API error ({response.status}): {error_text}")
            
            # Server-Sent Eventsを処理
            first_update = True
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if not line or line.startswith(':'):
                    continue
                
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # 'data: ' を除去
                        task = Task.from_dict(data)
                        
                        if first_update and self._first_update_callback:
                            await self._first_update_callback(task)
                            first_update = False
                        else:
                            await update_callback(task)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SSE data: {line}")

class A2AServer:
    """A2A APIサーバー"""
    
    def __init__(
        self,
        agent_card: AgentCard,
        task_handler: Callable[[Task], Awaitable[Task]],
        message_handler: Optional[Callable[[str, Message], Awaitable[Task]]] = None
    ):
        self.agent_card = agent_card
        self.task_handler = task_handler
        self.message_handler = message_handler
        self.tasks: Dict[str, Task] = {}
        self.task_updates: Dict[str, List[Dict[str, Any]]] = {}  # クライアントにSSEで送信する更新履歴
        self.update_subscribers: Dict[str, List[asyncio.Queue]] = {}  # タスクIDごとの購読者キュー
    
    def register_task(self, task: Task) -> None:
        """タスクを登録"""
        self.tasks[task.task_id] = task
        self.task_updates[task.task_id] = [task.to_dict()]
        self.update_subscribers[task.task_id] = []
    
    async def update_task(self, task: Task) -> None:
        """タスクを更新し、購読者に通知"""
        self.tasks[task.task_id] = task
        task_dict = task.to_dict()
        self.task_updates[task.task_id].append(task_dict)
        
        # 購読者に通知
        for queue in self.update_subscribers.get(task.task_id, []):
            await queue.put(task_dict)
    
    async def handle_get_agent_card(self) -> Dict[str, Any]:
        """エージェントカードを返却"""
        return self.agent_card.to_dict()
    
    async def handle_submit_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """タスク提出リクエストを処理"""
        task = Task.from_dict(task_data)
        
        # タスク登録
        self.register_task(task)
        
        # タスク処理
        asyncio.create_task(self._process_task(task))
        
        return task.to_dict()
    
    async def _process_task(self, task: Task) -> None:
        """タスクを非同期に処理"""
        try:
            updated_task = await self.task_handler(task)
            await self.update_task(updated_task)
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {str(e)}")
            task.update_status(TaskStatus.FAILED)
            error_message = Message(role=MessageRole.SYSTEM.value)
            error_message.add_error("internal_error", str(e))
            task.add_message(error_message)
            await self.update_task(task)
    
    async def handle_get_task(self, task_id: str) -> Dict[str, Any]:
        """タスク取得リクエストを処理"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        return task.to_dict()
    
    async def handle_update_task(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """タスク更新リクエストを処理"""
        if task_id != task_data.get("task_id"):
            raise ValueError("Task ID mismatch")
        
        existing_task = self.tasks.get(task_id)
        if not existing_task:
            raise ValueError(f"Task not found: {task_id}")
        
        updated_task = Task.from_dict(task_data)
        await self.update_task(updated_task)
        
        return updated_task.to_dict()
    
    async def handle_cancel_task(self, task_id: str) -> Dict[str, Any]:
        """タスクキャンセルリクエストを処理"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        task.update_status(TaskStatus.CANCELED)
        await self.update_task(task)
        
        return task.to_dict()
    
    async def handle_add_message(self, task_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """メッセージ追加リクエストを処理"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        message = Message.from_dict(message_data)
        task.add_message(message)
        
        # メッセージハンドラがあれば実行
        if self.message_handler:
            updated_task = await self.message_handler(task_id, message)
            await self.update_task(updated_task)
        else:
            await self.update_task(task)
        
        return task.to_dict()
    
    async def handle_stream_task_updates(self, task_id: str) -> Optional[Dict[str, Any]]:
        """タスク更新ストリームリクエストを処理"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # 更新通知用のキューを作成
        queue = asyncio.Queue()
        self.update_subscribers[task_id].append(queue)
        
        try:
            # 最初は現在のタスク状態を送信
            task_dict = task.to_dict()
            yield task_dict
            
            # 以降は更新を待機して送信
            while True:
                update = await queue.get()
                yield update
        finally:
            # クリーンアップ
            if queue in self.update_subscribers.get(task_id, []):
                self.update_subscribers[task_id].remove(queue)
    
    def create_fastapi_routes(self, app):
        """FastAPIルートを作成"""
        from fastapi import FastAPI, HTTPException, Request, Response
        from fastapi.responses import JSONResponse, StreamingResponse
        import json
        
        # エージェントカード取得
        @app.get("/agent-card")
        async def get_agent_card():
            return await self.handle_get_agent_card()
        
        # タスク提出
        @app.post("/tasks")
        async def submit_task(data: dict):
            try:
                return await self.handle_submit_task(data)
            except Exception as e:
                logger.error(f"Error submitting task: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))
        
        # タスク取得
        @app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            try:
                return await self.handle_get_task(task_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Error getting task: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # タスク更新
        @app.put("/tasks/{task_id}")
        async def update_task(task_id: str, data: dict):
            try:
                return await self.handle_update_task(task_id, data)
            except ValueError as e:
                if "not found" in str(e):
                    raise HTTPException(status_code=404, detail=str(e))
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Error updating task: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # タスクキャンセル
        @app.post("/tasks/{task_id}/cancel")
        async def cancel_task(task_id: str):
            try:
                return await self.handle_cancel_task(task_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Error canceling task: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # メッセージ追加
        @app.post("/tasks/{task_id}/messages")
        async def add_message(task_id: str, data: dict):
            try:
                return await self.handle_add_message(task_id, data)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Error adding message: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # タスク更新ストリーム
        @app.get("/tasks/{task_id}/updates")
        async def stream_task_updates(task_id: str):
            try:
                async def event_stream():
                    async for update in self.handle_stream_task_updates(task_id):
                        yield f"data: {json.dumps(update)}\n\n"
                
                return StreamingResponse(
                    event_stream(),
                    media_type="text/event-stream"
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Error streaming updates: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

# ユーティリティ関数
async def create_simple_task(
    client: A2AClient,
    prompt: str,
    metadata: Dict[str, Any] = None,
    session_id: Optional[str] = None
) -> Task:
    """簡単なタスクを作成して提出"""
    task = Task(
        status=TaskStatus.SUBMITTED,
        metadata=metadata or {},
        session_id=session_id
    )
    
    # 初期メッセージを追加
    user_message = Message(role=MessageRole.USER.value)
    user_message.add_text(prompt)
    task.add_message(user_message)
    
    # タスク提出
    return await client.submit_task(task)

async def wait_for_task_completion(
    client: A2AClient,
    task: Task,
    timeout: int = 300,
    update_callback: Optional[Callable[[Task], Awaitable[None]]] = None
) -> Task:
    """タスクの完了を待機"""
    start_time = time.time()
    current_task = task
    
    # 最初にタスクが既に完了しているかチェック
    if current_task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED]:
        return current_task
    
    # 完了するまでポーリング
    while time.time() - start_time < timeout:
        # 更新を取得
        updated_task = await client.get_task(task.task_id)
        
        # 状態が変化した場合はコールバック
        if (updated_task.status != current_task.status or 
                len(updated_task.messages) != len(current_task.messages)):
            if update_callback:
                await update_callback(updated_task)
            current_task = updated_task
        
        # 完了した場合は終了
        if current_task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED]:
            return current_task
        
        # 少し待機
        await asyncio.sleep(1)
    
    # タイムアウト
    raise TimeoutError(f"Task {task.task_id} did not complete within {timeout} seconds")

def extract_text_from_task(task: Task) -> str:
    """タスクからテキスト内容を抽出"""
    result = []
    
    for message in task.messages:
        if message.role == MessageRole.ASSISTANT.value:
            for part in message.parts:
                if isinstance(part, TextPart):
                    result.append(part.text)
    
    return "\n".join(result)

def create_simple_agent_card(
    name: str,
    description: str,
    url: str,
    skills: List[Dict[str, Any]] = None,
    email: Optional[str] = None
) -> AgentCard:
    """簡易エージェントカードを作成"""
    skill_objects = []
    
    if skills:
        for skill_data in skills:
            skill = Skill(
                name=skill_data.get("name", ""),
                description=skill_data.get("description", ""),
                input_schema=skill_data.get("input_schema", {}),
                output_schema=skill_data.get("output_schema", {})
            )
            skill_objects.append(skill)
    
    return AgentCard(
        name=name,
        agent_url=url,
        description=description,
        contact_email=email,
        skills=skill_objects
    ) 