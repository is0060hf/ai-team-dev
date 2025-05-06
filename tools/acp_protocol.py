"""
ACP（Agent Communication Protocol）プロトコルモジュール。
エージェント間通信の標準規格として、IBMが主導するACPプロトコルを実装します。
ACP標準仕様: https://docs.beeai.dev/acp
"""

import os
import uuid
import json
import time
import asyncio
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable, Awaitable, Type
from dataclasses import dataclass, field, asdict

from utils.logger import get_logger

logger = get_logger("acp_protocol")

class ACPMessageType(Enum):
    """ACP メッセージタイプ"""
    CAPABILITY_ADVERTISEMENT = "capability_advertisement"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_UPDATE = "task_update"
    TASK_CANCEL = "task_cancel"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

class ACPErrorCode(Enum):
    """ACP エラーコード"""
    INVALID_REQUEST = "invalid_request"
    CAPABILITY_NOT_FOUND = "capability_not_found"
    TASK_NOT_FOUND = "task_not_found"
    TASK_ALREADY_COMPLETED = "task_already_completed"
    TASK_EXECUTION_ERROR = "task_execution_error"
    INTERNAL_ERROR = "internal_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"

class ACPTaskStatus(Enum):
    """ACP タスクステータス"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REJECTED = "rejected"

@dataclass
class ACPCapabilityDescriptor:
    """ACP 機能記述子"""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ACPCapabilityDescriptor':
        """辞書から機能記述子を作成"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            metadata=data.get("metadata", {})
        )

@dataclass
class ACPTask:
    """ACP タスク"""
    id: str
    capability_id: str
    input_data: Dict[str, Any]
    status: ACPTaskStatus = ACPTaskStatus.PENDING
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, status: ACPTaskStatus, output: Optional[Dict[str, Any]] = None,
                     error: Optional[Dict[str, Any]] = None, progress: Optional[float] = None) -> None:
        """タスクステータスを更新"""
        self.status = status
        self.updated_at = time.time()
        
        if output is not None:
            self.output_data = output
        
        if error is not None:
            self.error = error
        
        if progress is not None:
            self.progress = progress
        
        if status == ACPTaskStatus.RUNNING and self.started_at is None:
            self.started_at = time.time()
        
        if status in [ACPTaskStatus.COMPLETED, ACPTaskStatus.FAILED, ACPTaskStatus.CANCELED]:
            self.completed_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        result = {
            "id": self.id,
            "capability_id": self.capability_id,
            "input_data": self.input_data,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.progress,
            "metadata": self.metadata
        }
        
        if self.output_data is not None:
            result["output_data"] = self.output_data
        
        if self.error is not None:
            result["error"] = self.error
        
        if self.started_at is not None:
            result["started_at"] = self.started_at
        
        if self.completed_at is not None:
            result["completed_at"] = self.completed_at
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ACPTask':
        """辞書からタスクを作成"""
        try:
            status = ACPTaskStatus(data.get("status", "pending"))
        except ValueError:
            logger.warning(f"Unknown task status: {data.get('status')}, falling back to PENDING")
            status = ACPTaskStatus.PENDING
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            capability_id=data.get("capability_id", ""),
            input_data=data.get("input_data", {}),
            status=status,
            output_data=data.get("output_data"),
            error=data.get("error"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress=data.get("progress", 0.0),
            metadata=data.get("metadata", {})
        )

@dataclass
class ACPMessage:
    """ACP メッセージ"""
    type: ACPMessageType
    sender_id: str
    receiver_id: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    in_reply_to: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        result = {
            "type": self.type.value,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        
        if self.receiver_id is not None:
            result["receiver_id"] = self.receiver_id
        
        if self.in_reply_to is not None:
            result["in_reply_to"] = self.in_reply_to
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ACPMessage':
        """辞書からメッセージを作成"""
        try:
            msg_type = ACPMessageType(data.get("type", "event"))
        except ValueError:
            logger.warning(f"Unknown message type: {data.get('type')}, falling back to EVENT")
            msg_type = ACPMessageType.EVENT
        
        return cls(
            type=msg_type,
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id"),
            message_id=data.get("message_id", str(uuid.uuid4())),
            in_reply_to=data.get("in_reply_to"),
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {})
        )
    
    @classmethod
    def create_capability_advertisement(cls, sender_id: str, 
                                       capabilities: List[ACPCapabilityDescriptor]) -> 'ACPMessage':
        """機能アドバタイズメッセージを作成"""
        return cls(
            type=ACPMessageType.CAPABILITY_ADVERTISEMENT,
            sender_id=sender_id,
            payload={
                "capabilities": [cap.to_dict() for cap in capabilities]
            }
        )
    
    @classmethod
    def create_capability_query(cls, sender_id: str, receiver_id: Optional[str] = None) -> 'ACPMessage':
        """機能クエリメッセージを作成"""
        return cls(
            type=ACPMessageType.CAPABILITY_QUERY,
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload={}
        )
    
    @classmethod
    def create_capability_response(cls, sender_id: str, receiver_id: str, 
                                 in_reply_to: str, 
                                 capabilities: List[ACPCapabilityDescriptor]) -> 'ACPMessage':
        """機能レスポンスメッセージを作成"""
        return cls(
            type=ACPMessageType.CAPABILITY_RESPONSE,
            sender_id=sender_id,
            receiver_id=receiver_id,
            in_reply_to=in_reply_to,
            payload={
                "capabilities": [cap.to_dict() for cap in capabilities]
            }
        )
    
    @classmethod
    def create_task_request(cls, sender_id: str, receiver_id: str, 
                          capability_id: str, input_data: Dict[str, Any]) -> 'ACPMessage':
        """タスクリクエストメッセージを作成"""
        task_id = str(uuid.uuid4())
        return cls(
            type=ACPMessageType.TASK_REQUEST,
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload={
                "task": {
                    "id": task_id,
                    "capability_id": capability_id,
                    "input_data": input_data,
                    "status": ACPTaskStatus.PENDING.value,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "progress": 0.0
                }
            }
        )
    
    @classmethod
    def create_task_response(cls, sender_id: str, receiver_id: str, 
                           in_reply_to: str, task: ACPTask) -> 'ACPMessage':
        """タスクレスポンスメッセージを作成"""
        return cls(
            type=ACPMessageType.TASK_RESPONSE,
            sender_id=sender_id,
            receiver_id=receiver_id,
            in_reply_to=in_reply_to,
            payload={
                "task": task.to_dict()
            }
        )
    
    @classmethod
    def create_task_update(cls, sender_id: str, receiver_id: str, 
                         task: ACPTask) -> 'ACPMessage':
        """タスク更新メッセージを作成"""
        return cls(
            type=ACPMessageType.TASK_UPDATE,
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload={
                "task": task.to_dict()
            }
        )
    
    @classmethod
    def create_task_cancel(cls, sender_id: str, receiver_id: str, 
                         task_id: str) -> 'ACPMessage':
        """タスクキャンセルメッセージを作成"""
        return cls(
            type=ACPMessageType.TASK_CANCEL,
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload={
                "task_id": task_id
            }
        )
    
    @classmethod
    def create_error(cls, sender_id: str, receiver_id: str, 
                   in_reply_to: Optional[str], 
                   error_code: ACPErrorCode, 
                   error_message: str, 
                   details: Optional[Dict[str, Any]] = None) -> 'ACPMessage':
        """エラーメッセージを作成"""
        payload = {
            "error": {
                "code": error_code.value,
                "message": error_message
            }
        }
        
        if details is not None:
            payload["error"]["details"] = details
        
        return cls(
            type=ACPMessageType.ERROR,
            sender_id=sender_id,
            receiver_id=receiver_id,
            in_reply_to=in_reply_to,
            payload=payload
        )
    
    @classmethod
    def create_heartbeat(cls, sender_id: str) -> 'ACPMessage':
        """ハートビートメッセージを作成"""
        return cls(
            type=ACPMessageType.HEARTBEAT,
            sender_id=sender_id,
            payload={
                "status": "alive",
                "timestamp": time.time()
            }
        )
    
    @classmethod
    def create_event(cls, sender_id: str, receiver_id: Optional[str], 
                   event_type: str, event_data: Dict[str, Any]) -> 'ACPMessage':
        """イベントメッセージを作成"""
        return cls(
            type=ACPMessageType.EVENT,
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload={
                "event_type": event_type,
                "event_data": event_data
            }
        )

class ACPTransport:
    """ACP転送基底クラス"""
    
    def __init__(self):
        self.message_handlers: Dict[ACPMessageType, List[Callable[[ACPMessage], Awaitable[None]]]] = {
            msg_type: [] for msg_type in ACPMessageType
        }
        self.message_buffer: List[ACPMessage] = []
        self.connected = False
    
    async def connect(self) -> None:
        """転送を接続"""
        self.connected = True
    
    async def disconnect(self) -> None:
        """転送を切断"""
        self.connected = False
    
    async def send_message(self, message: ACPMessage) -> None:
        """メッセージを送信（サブクラスで実装）"""
        raise NotImplementedError
    
    async def receive_message(self) -> Optional[ACPMessage]:
        """メッセージを受信（サブクラスで実装）"""
        raise NotImplementedError
    
    def register_handler(self, message_type: ACPMessageType, 
                        handler: Callable[[ACPMessage], Awaitable[None]]) -> None:
        """特定タイプのメッセージハンドラーを登録"""
        self.message_handlers[message_type].append(handler)
    
    def register_global_handler(self, handler: Callable[[ACPMessage], Awaitable[None]]) -> None:
        """すべてのメッセージタイプに対するハンドラーを登録"""
        for msg_type in ACPMessageType:
            self.message_handlers[msg_type].append(handler)
    
    async def dispatch_message(self, message: ACPMessage) -> None:
        """メッセージをハンドラーに転送"""
        handlers = self.message_handlers.get(message.type, [])
        if handlers:
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error handling message {message.type}: {str(e)}")
        else:
            # ハンドラーがない場合はバッファに追加
            self.message_buffer.append(message)
            logger.debug(f"No handler for message type {message.type}, buffered")
    
    async def process_message_loop(self) -> None:
        """メッセージ処理ループを実行"""
        while self.connected:
            try:
                message = await self.receive_message()
                if message:
                    await self.dispatch_message(message)
            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
                await asyncio.sleep(1)  # エラー時は少し待機

class ACPLocalTransport(ACPTransport):
    """ローカルメモリ内ACP転送（同一プロセス内）"""
    
    # 名前付きの転送チャネルを格納するグローバル辞書
    _channels: Dict[str, 'ACPLocalTransport'] = {}
    
    def __init__(self, channel_name: str):
        super().__init__()
        self.channel_name = channel_name
        self.message_queue = asyncio.Queue()
        ACPLocalTransport._channels[channel_name] = self
    
    async def connect(self) -> None:
        """転送を接続"""
        await super().connect()
        logger.info(f"Local transport connected to channel: {self.channel_name}")
    
    async def disconnect(self) -> None:
        """転送を切断"""
        await super().disconnect()
        if self.channel_name in ACPLocalTransport._channels:
            del ACPLocalTransport._channels[self.channel_name]
        logger.info(f"Local transport disconnected from channel: {self.channel_name}")
    
    async def send_message(self, message: ACPMessage) -> None:
        """メッセージを送信（異なるエージェントへの転送）"""
        if not self.connected:
            raise RuntimeError("Transport not connected")
        
        # 受信者IDが指定されている場合は特定のエージェントに送信
        if message.receiver_id and message.receiver_id in ACPLocalTransport._channels:
            receiver = ACPLocalTransport._channels[message.receiver_id]
            await receiver.message_queue.put(message)
            logger.debug(f"Message sent to agent {message.receiver_id}")
        # 受信者IDがない場合はブロードキャスト（送信者以外の全エージェントに送信）
        elif not message.receiver_id:
            for agent_id, transport in ACPLocalTransport._channels.items():
                if agent_id != message.sender_id:
                    await transport.message_queue.put(message)
            logger.debug(f"Message broadcast to all agents except sender")
        else:
            logger.warning(f"Receiver {message.receiver_id} not found, message discarded")
    
    async def receive_message(self) -> Optional[ACPMessage]:
        """メッセージを受信（キューから取得）"""
        if not self.connected:
            raise RuntimeError("Transport not connected")
        
        try:
            return await self.message_queue.get()
        except asyncio.QueueEmpty:
            return None

class ACPWebSocketTransport(ACPTransport):
    """WebSocket ACP転送"""
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.websocket = None
        self.session = None
    
    async def connect(self) -> None:
        """WebSocketに接続"""
        import aiohttp
        
        self.session = aiohttp.ClientSession()
        try:
            self.websocket = await self.session.ws_connect(self.url)
            await super().connect()
            logger.info(f"WebSocket transport connected to: {self.url}")
        except Exception as e:
            if self.session:
                await self.session.close()
                self.session = None
            raise RuntimeError(f"Failed to connect to WebSocket: {str(e)}")
    
    async def disconnect(self) -> None:
        """WebSocketから切断"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        if self.session:
            await self.session.close()
            self.session = None
        
        await super().disconnect()
        logger.info(f"WebSocket transport disconnected from: {self.url}")
    
    async def send_message(self, message: ACPMessage) -> None:
        """メッセージをWebSocketで送信"""
        if not self.connected or not self.websocket:
            raise RuntimeError("Transport not connected")
        
        try:
            await self.websocket.send_json(message.to_dict())
            logger.debug(f"Message sent via WebSocket: {message.type}")
        except Exception as e:
            logger.error(f"Error sending message via WebSocket: {str(e)}")
            raise
    
    async def receive_message(self) -> Optional[ACPMessage]:
        """WebSocketからメッセージを受信"""
        if not self.connected or not self.websocket:
            raise RuntimeError("Transport not connected")
        
        try:
            msg = await self.websocket.receive()
            
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    return ACPMessage.from_dict(data)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON via WebSocket")
                    return None
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                logger.info("WebSocket connection closed")
                self.connected = False
                return None
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self.websocket.exception()}")
                self.connected = False
                return None
        except Exception as e:
            logger.error(f"Error receiving message via WebSocket: {str(e)}")
            return None
        
        return None

class ACPAgent:
    """ACP対応エージェント"""
    
    def __init__(
        self,
        agent_id: str,
        capabilities: List[ACPCapabilityDescriptor] = None,
        transport: Optional[ACPTransport] = None
    ):
        self.agent_id = agent_id
        self.capabilities = capabilities or []
        self.transport = transport
        self.tasks: Dict[str, ACPTask] = {}
        
        # 機能IDによるルックアップ
        self.capability_map = {cap.id: cap for cap in self.capabilities}
        
        # 機能実装ハンドラー
        self.capability_handlers: Dict[str, Callable[[ACPTask], Awaitable[ACPTask]]] = {}
        
        # その他のエージェントの機能キャッシュ
        self.agent_capabilities: Dict[str, List[ACPCapabilityDescriptor]] = {}
        
        # プロセス管理
        self.running = False
        self.message_handler_task = None
    
    def register_capability_handler(
        self,
        capability_id: str,
        handler: Callable[[ACPTask], Awaitable[ACPTask]]
    ) -> None:
        """機能実装ハンドラーを登録"""
        if capability_id not in self.capability_map:
            raise ValueError(f"Capability {capability_id} not registered")
        
        self.capability_handlers[capability_id] = handler
    
    async def start(self) -> None:
        """エージェントを起動"""
        if self.running:
            return
        
        # 転送がある場合は接続
        if self.transport:
            await self.transport.connect()
            
            # メッセージハンドラーを登録
            self.transport.register_handler(ACPMessageType.CAPABILITY_QUERY, 
                                          self._handle_capability_query)
            self.transport.register_handler(ACPMessageType.CAPABILITY_ADVERTISEMENT, 
                                          self._handle_capability_advertisement)
            self.transport.register_handler(ACPMessageType.CAPABILITY_RESPONSE, 
                                          self._handle_capability_response)
            self.transport.register_handler(ACPMessageType.TASK_REQUEST, 
                                          self._handle_task_request)
            self.transport.register_handler(ACPMessageType.TASK_RESPONSE, 
                                          self._handle_task_response)
            self.transport.register_handler(ACPMessageType.TASK_UPDATE, 
                                          self._handle_task_update)
            self.transport.register_handler(ACPMessageType.TASK_CANCEL, 
                                          self._handle_task_cancel)
            
            # メッセージ処理ループを開始
            self.message_handler_task = asyncio.create_task(self.transport.process_message_loop())
            
            # 機能をアドバタイズ
            if self.capabilities:
                await self.advertise_capabilities()
        
        self.running = True
        logger.info(f"Agent {self.agent_id} started")
    
    async def stop(self) -> None:
        """エージェントを停止"""
        if not self.running:
            return
        
        self.running = False
        
        # メッセージ処理ループを停止
        if self.message_handler_task:
            self.message_handler_task.cancel()
            try:
                await self.message_handler_task
            except asyncio.CancelledError:
                pass
            self.message_handler_task = None
        
        # 転送がある場合は切断
        if self.transport:
            await self.transport.disconnect()
        
        logger.info(f"Agent {self.agent_id} stopped")
    
    async def advertise_capabilities(self) -> None:
        """機能をアドバタイズ"""
        if not self.transport or not self.capabilities:
            return
        
        message = ACPMessage.create_capability_advertisement(
            sender_id=self.agent_id,
            capabilities=self.capabilities
        )
        
        await self.transport.send_message(message)
        logger.info(f"Agent {self.agent_id} advertised {len(self.capabilities)} capabilities")
    
    async def query_capabilities(self, receiver_id: Optional[str] = None) -> None:
        """他のエージェントの機能をクエリ"""
        if not self.transport:
            return
        
        message = ACPMessage.create_capability_query(
            sender_id=self.agent_id,
            receiver_id=receiver_id
        )
        
        await self.transport.send_message(message)
        logger.info(f"Agent {self.agent_id} queried capabilities from {receiver_id or 'all agents'}")
    
    async def submit_task(self, receiver_id: str, capability_id: str, 
                         input_data: Dict[str, Any]) -> str:
        """タスクを他のエージェントに提出"""
        if not self.transport:
            raise RuntimeError("Agent has no transport")
        
        message = ACPMessage.create_task_request(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            capability_id=capability_id,
            input_data=input_data
        )
        
        # タスクIDを取得
        task_id = message.payload["task"]["id"]
        
        # タスクを登録
        task = ACPTask.from_dict(message.payload["task"])
        self.tasks[task_id] = task
        
        # タスクリクエストを送信
        await self.transport.send_message(message)
        logger.info(f"Agent {self.agent_id} submitted task {task_id} to {receiver_id}")
        
        return task_id
    
    async def cancel_task(self, receiver_id: str, task_id: str) -> None:
        """タスクをキャンセル"""
        if not self.transport:
            raise RuntimeError("Agent has no transport")
        
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        message = ACPMessage.create_task_cancel(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            task_id=task_id
        )
        
        await self.transport.send_message(message)
        logger.info(f"Agent {self.agent_id} canceled task {task_id}")
    
    async def get_task(self, task_id: str) -> Optional[ACPTask]:
        """タスクの状態を取得"""
        return self.tasks.get(task_id)
    
    async def wait_for_task_completion(self, task_id: str, timeout: float = 60.0) -> Optional[ACPTask]:
        """タスクの完了を待機"""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = self.tasks[task_id]
            
            if task.status in [ACPTaskStatus.COMPLETED, ACPTaskStatus.FAILED, ACPTaskStatus.CANCELED]:
                return task
            
            await asyncio.sleep(0.1)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
    
    async def _handle_capability_query(self, message: ACPMessage) -> None:
        """機能クエリを処理"""
        # 自分宛かブロードキャストの場合のみ処理
        if message.receiver_id and message.receiver_id != self.agent_id:
            return
        
        # 機能レスポンスを送信
        response = ACPMessage.create_capability_response(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            in_reply_to=message.message_id,
            capabilities=self.capabilities
        )
        
        await self.transport.send_message(response)
        logger.debug(f"Agent {self.agent_id} responded to capability query from {message.sender_id}")
    
    async def _handle_capability_advertisement(self, message: ACPMessage) -> None:
        """機能アドバタイズを処理"""
        capabilities = []
        
        for cap_data in message.payload.get("capabilities", []):
            capabilities.append(ACPCapabilityDescriptor.from_dict(cap_data))
        
        # 機能キャッシュを更新
        self.agent_capabilities[message.sender_id] = capabilities
        logger.debug(f"Agent {self.agent_id} received {len(capabilities)} capabilities from {message.sender_id}")
    
    async def _handle_capability_response(self, message: ACPMessage) -> None:
        """機能レスポンスを処理"""
        if message.receiver_id != self.agent_id:
            return
        
        capabilities = []
        
        for cap_data in message.payload.get("capabilities", []):
            capabilities.append(ACPCapabilityDescriptor.from_dict(cap_data))
        
        # 機能キャッシュを更新
        self.agent_capabilities[message.sender_id] = capabilities
        logger.debug(f"Agent {self.agent_id} received {len(capabilities)} capabilities from {message.sender_id}")
    
    async def _handle_task_request(self, message: ACPMessage) -> None:
        """タスクリクエストを処理"""
        if message.receiver_id != self.agent_id:
            return
        
        task_data = message.payload.get("task", {})
        task = ACPTask.from_dict(task_data)
        
        # タスクを登録
        self.tasks[task.id] = task
        
        # 機能が見つからない場合はエラー応答
        if task.capability_id not in self.capability_map:
            task.update_status(ACPTaskStatus.REJECTED, error={
                "code": ACPErrorCode.CAPABILITY_NOT_FOUND.value,
                "message": f"Capability {task.capability_id} not found"
            })
            
            response = ACPMessage.create_task_response(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                in_reply_to=message.message_id,
                task=task
            )
            
            await self.transport.send_message(response)
            logger.warning(f"Agent {self.agent_id} rejected task {task.id}: capability not found")
            return
        
        # 機能ハンドラーが見つからない場合はエラー応答
        if task.capability_id not in self.capability_handlers:
            task.update_status(ACPTaskStatus.REJECTED, error={
                "code": ACPErrorCode.CAPABILITY_NOT_FOUND.value,
                "message": f"No handler for capability {task.capability_id}"
            })
            
            response = ACPMessage.create_task_response(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                in_reply_to=message.message_id,
                task=task
            )
            
            await self.transport.send_message(response)
            logger.warning(f"Agent {self.agent_id} rejected task {task.id}: no handler")
            return
        
        # タスクを受け付け
        task.update_status(ACPTaskStatus.ACCEPTED)
        
        response = ACPMessage.create_task_response(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            in_reply_to=message.message_id,
            task=task
        )
        
        await self.transport.send_message(response)
        logger.info(f"Agent {self.agent_id} accepted task {task.id}")
        
        # 非同期でタスクを実行
        asyncio.create_task(self._execute_task(message.sender_id, task))
    
    async def _execute_task(self, requester_id: str, task: ACPTask) -> None:
        """タスクを実行"""
        try:
            # 実行中に更新
            task.update_status(ACPTaskStatus.RUNNING)
            
            # 更新通知
            update = ACPMessage.create_task_update(
                sender_id=self.agent_id,
                receiver_id=requester_id,
                task=task
            )
            
            await self.transport.send_message(update)
            
            # ハンドラーを実行
            handler = self.capability_handlers[task.capability_id]
            result = await handler(task)
            
            # タスクオブジェクトを更新
            self.tasks[task.id] = result
            
            # 完了通知
            update = ACPMessage.create_task_update(
                sender_id=self.agent_id,
                receiver_id=requester_id,
                task=result
            )
            
            await self.transport.send_message(update)
            logger.info(f"Agent {self.agent_id} completed task {task.id}")
        except Exception as e:
            # エラー処理
            task.update_status(ACPTaskStatus.FAILED, error={
                "code": ACPErrorCode.TASK_EXECUTION_ERROR.value,
                "message": str(e)
            })
            
            # エラー通知
            update = ACPMessage.create_task_update(
                sender_id=self.agent_id,
                receiver_id=requester_id,
                task=task
            )
            
            await self.transport.send_message(update)
            logger.error(f"Agent {self.agent_id} failed to execute task {task.id}: {str(e)}")
    
    async def _handle_task_response(self, message: ACPMessage) -> None:
        """タスクレスポンスを処理"""
        if message.receiver_id != self.agent_id:
            return
        
        task_data = message.payload.get("task", {})
        task = ACPTask.from_dict(task_data)
        
        # タスクを更新
        if task.id in self.tasks:
            self.tasks[task.id] = task
            logger.debug(f"Agent {self.agent_id} updated task {task.id} from response")
        else:
            logger.warning(f"Agent {self.agent_id} received response for unknown task {task.id}")
    
    async def _handle_task_update(self, message: ACPMessage) -> None:
        """タスク更新を処理"""
        if message.receiver_id != self.agent_id:
            return
        
        task_data = message.payload.get("task", {})
        task = ACPTask.from_dict(task_data)
        
        # タスクを更新
        if task.id in self.tasks:
            self.tasks[task.id] = task
            logger.debug(f"Agent {self.agent_id} updated task {task.id} from update")
        else:
            logger.warning(f"Agent {self.agent_id} received update for unknown task {task.id}")
    
    async def _handle_task_cancel(self, message: ACPMessage) -> None:
        """タスクキャンセルを処理"""
        if message.receiver_id != self.agent_id:
            return
        
        task_id = message.payload.get("task_id")
        
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            # すでに完了している場合は無視
            if task.status in [ACPTaskStatus.COMPLETED, ACPTaskStatus.FAILED, ACPTaskStatus.CANCELED]:
                logger.warning(f"Agent {self.agent_id} ignoring cancel for already completed task {task_id}")
                return
            
            # キャンセル状態に更新
            task.update_status(ACPTaskStatus.CANCELED)
            
            # 更新通知
            update = ACPMessage.create_task_update(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                task=task
            )
            
            await self.transport.send_message(update)
            logger.info(f"Agent {self.agent_id} canceled task {task_id}")
        else:
            logger.warning(f"Agent {self.agent_id} received cancel for unknown task {task_id}")

# ユーティリティ関数
def create_capability(
    name: str,
    description: str,
    input_schema: Dict[str, Any] = None,
    output_schema: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None
) -> ACPCapabilityDescriptor:
    """簡易的な機能記述子を作成"""
    return ACPCapabilityDescriptor(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        input_schema=input_schema or {},
        output_schema=output_schema or {},
        metadata=metadata or {}
    )

def capability_handler(agent: ACPAgent, capability_id: str):
    """機能実装ハンドラーを登録するデコレーター"""
    def decorator(func: Callable[[ACPTask], Awaitable[ACPTask]]):
        agent.register_capability_handler(capability_id, func)
        return func
    return decorator

async def create_agent_network(agent_ids: List[str]) -> Dict[str, ACPAgent]:
    """ローカルエージェントネットワークを作成"""
    agents = {}
    
    for agent_id in agent_ids:
        transport = ACPLocalTransport(agent_id)
        agent = ACPAgent(agent_id=agent_id, transport=transport)
        agents[agent_id] = agent
        await agent.start()
    
    return agents

async def shutdown_agent_network(agents: Dict[str, ACPAgent]) -> None:
    """エージェントネットワークをシャットダウン"""
    for agent in agents.values():
        await agent.stop() 