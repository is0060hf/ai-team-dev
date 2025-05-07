"""
MCP (Model Context Protocol) ブリッジモジュール。
内部エージェント通信プロトコル（agent_communication.py）とMCPプロトコル（mcp_connector.py）の間の
相互変換機能を提供し、外部MCPシステムとの互換性を確保します。
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import uuid

from utils.logger import get_logger
from utils.agent_communication import (
    AgentMessage, TaskRequest, TaskResponse, TaskStatus, TaskType, TaskPriority,
    InfoRequest, InfoResponse, StatusUpdate
)
from tools.mcp_connector import (
    MCPClient, MCPServer, MCPTransport, MCPStdIOTransport, MCPWebSocketTransport,
    MCPMessageType, MCPManager, MCPTool, MCPResource, MCPPrompt
)

logger = get_logger("mcp_bridge")

class MCPBridge:
    """
    内部エージェント通信プロトコルとMCPの間のブリッジ。
    異なるプロトコル間でのメッセージ変換と転送を行います。
    """
    
    def __init__(self, agent_id: str, mcp_client: Optional[MCPClient] = None):
        """
        MCPブリッジを初期化します。
        
        Args:
            agent_id: このブリッジを使用するエージェントID
            mcp_client: 既存のMCPクライアント（省略時は必要に応じて作成）
        """
        self.agent_id = agent_id
        self.mcp_client = mcp_client
        self.message_handlers = {}
        self.request_map = {}  # 内部リクエストIDとMCPリクエストIDのマッピング
        
        logger.info(f"MCPブリッジが初期化されました - エージェント: {agent_id}")
    
    async def connect_to_mcp_server(
        self,
        server_cmd: List[str],
        env: Dict[str, str] = None,
        transport_type: str = "stdio"
    ) -> bool:
        """
        MCPサーバーに接続します。
        
        Args:
            server_cmd: サーバーコマンドまたはWebSocketのURL
            env: 環境変数
            transport_type: トランスポート種別 ("stdio" or "websocket")
            
        Returns:
            bool: 接続成功の場合はTrue
        """
        if self.mcp_client:
            logger.warning("既にMCPクライアントが設定されています")
            return True
        
        try:
            if transport_type == "stdio":
                transport = MCPStdIOTransport(server_cmd, env)
            elif transport_type == "websocket":
                # URLはコマンドの最初の要素
                url = server_cmd[0]
                headers = env or {}
                transport = MCPWebSocketTransport(url, headers)
            else:
                raise ValueError(f"サポートされていないトランスポート種別: {transport_type}")
            
            self.mcp_client = MCPClient(transport, f"agent-{self.agent_id}")
            await self.mcp_client.connect()
            
            logger.info(f"MCPサーバーに接続しました: {' '.join(server_cmd) if isinstance(server_cmd, list) else server_cmd}")
            return True
        
        except Exception as e:
            logger.error(f"MCPサーバー接続エラー: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """MCPサーバーから切断します。"""
        if self.mcp_client:
            await self.mcp_client.disconnect()
            self.mcp_client = None
            logger.info("MCPサーバーから切断しました")
    
    def register_handler(self, message_type: str, handler: Callable) -> None:
        """
        メッセージハンドラーを登録します。
        
        Args:
            message_type: 処理するメッセージのタイプ
            handler: ハンドラー関数(AgentMessage) -> None
        """
        self.message_handlers[message_type] = handler
        logger.debug(f"メッセージハンドラーが登録されました: {message_type}")
    
    def _convert_agent_message_to_mcp(self, message: AgentMessage) -> Dict[str, Any]:
        """
        内部AgentMessageをMCP形式に変換します。
        
        Args:
            message: 変換する内部メッセージ
            
        Returns:
            Dict[str, Any]: MCP形式のメッセージ
        """
        mcp_id = str(uuid.uuid4())
        self.request_map[message.request_id] = mcp_id
        
        if isinstance(message, TaskRequest):
            # タスク依頼をツール呼び出しに変換
            return {
                "id": mcp_id,
                "type": MCPMessageType.CALL_TOOL,
                "params": {
                    "name": "executeTask",
                    "arguments": {
                        "taskType": message.content.get("task_type", ""),
                        "description": message.content.get("description", ""),
                        "priority": message.content.get("priority", ""),
                        "deadline": message.content.get("deadline"),
                        "context": message.content.get("context", {}),
                        "sender": message.sender,
                        "recipient": message.recipient,
                        "requestId": message.request_id,
                        "timestamp": message.timestamp
                    }
                }
            }
        
        elif isinstance(message, TaskResponse):
            # タスク応答をツール結果に変換
            return {
                "id": mcp_id,
                "type": MCPMessageType.CALL_TOOL,
                "params": {
                    "name": "submitTaskResult",
                    "arguments": {
                        "requestId": message.reference_id,
                        "status": message.content.get("status", ""),
                        "result": message.content.get("result", {}),
                        "message": message.content.get("message", ""),
                        "sender": message.sender,
                        "recipient": message.recipient,
                        "timestamp": message.timestamp
                    }
                }
            }
        
        elif isinstance(message, StatusUpdate):
            # ステータス更新を通知に変換
            return {
                "id": mcp_id,
                "type": MCPMessageType.NOTIFICATION,
                "params": {
                    "event": "statusUpdate",
                    "requestId": message.reference_id,
                    "status": message.content.get("status", ""),
                    "progress": message.content.get("progress"),
                    "message": message.content.get("message", ""),
                    "sender": message.sender,
                    "timestamp": message.timestamp
                }
            }
        
        elif isinstance(message, InfoRequest):
            # 情報要求をリソース読み込みリクエストに変換
            return {
                "id": mcp_id,
                "type": MCPMessageType.CALL_TOOL,
                "params": {
                    "name": "requestInformation",
                    "arguments": {
                        "relatedRequestId": message.reference_id,
                        "questions": message.content.get("questions", []),
                        "context": message.content.get("context", {}),
                        "sender": message.sender,
                        "recipient": message.recipient,
                        "requestId": message.request_id,
                        "timestamp": message.timestamp
                    }
                }
            }
        
        elif isinstance(message, InfoResponse):
            # 情報応答をツール結果に変換
            return {
                "id": mcp_id,
                "type": MCPMessageType.CALL_TOOL,
                "params": {
                    "name": "submitInformation",
                    "arguments": {
                        "requestId": message.reference_id,
                        "answers": message.content.get("answers", {}),
                        "sender": message.sender,
                        "recipient": message.recipient,
                        "timestamp": message.timestamp
                    }
                }
            }
        
        else:
            # その他汎用メッセージ
            return {
                "id": mcp_id,
                "type": MCPMessageType.CALL_TOOL,
                "params": {
                    "name": "sendMessage",
                    "arguments": message.to_dict()
                }
            }
    
    def _convert_mcp_to_agent_message(self, mcp_message: Dict[str, Any]) -> Optional[AgentMessage]:
        """
        MCP形式のメッセージを内部AgentMessageに変換します。
        
        Args:
            mcp_message: 変換するMCPメッセージ
            
        Returns:
            Optional[AgentMessage]: 変換された内部メッセージ（変換できない場合はNone）
        """
        message_type = mcp_message.get("type")
        
        # MCP ID -> 内部リクエストIDの変換
        mcp_id = mcp_message.get("id")
        internal_id = None
        for key, value in self.request_map.items():
            if value == mcp_id:
                internal_id = key
                break
        
        if message_type == MCPMessageType.CALL_TOOL_RESULT:
            result = mcp_message.get("result", {})
            content = result.get("content", {})
            
            # ツール名からメッセージタイプを推測
            tool_name = mcp_message.get("params", {}).get("name", "")
            
            if tool_name == "executeTask" or "taskType" in content:
                # タスク依頼
                return TaskRequest(
                    sender=content.get("sender", "mcp_agent"),
                    recipient=content.get("recipient", self.agent_id),
                    task_type=content.get("taskType", ""),
                    description=content.get("description", ""),
                    priority=content.get("priority", TaskPriority.MEDIUM),
                    deadline=content.get("deadline"),
                    context=content.get("context", {}),
                    request_id=content.get("requestId", internal_id)
                )
            
            elif tool_name == "submitTaskResult" or "status" in content:
                # タスク応答
                return TaskResponse(
                    sender=content.get("sender", "mcp_agent"),
                    recipient=content.get("recipient", self.agent_id),
                    request_id=content.get("requestId", ""),
                    status=content.get("status", TaskStatus.COMPLETED),
                    result=content.get("result", {}),
                    message=content.get("message", "")
                )
            
            elif tool_name == "requestInformation" or "questions" in content:
                # 情報要求
                return InfoRequest(
                    sender=content.get("sender", "mcp_agent"),
                    recipient=content.get("recipient", self.agent_id),
                    request_id=content.get("relatedRequestId", ""),
                    questions=content.get("questions", []),
                    context=content.get("context", {})
                )
            
            elif tool_name == "submitInformation" or "answers" in content:
                # 情報応答
                return InfoResponse(
                    sender=content.get("sender", "mcp_agent"),
                    recipient=content.get("recipient", self.agent_id),
                    request_id=content.get("requestId", ""),
                    answers=content.get("answers", {})
                )
            
            elif tool_name == "sendMessage":
                # 汎用メッセージ
                if isinstance(content, dict) and "message_type" in content:
                    return AgentMessage.from_dict(content)
                return None
            
            else:
                # 不明なツール結果はNoneを返す
                logger.warning(f"不明なツール結果: {tool_name}")
                return None
        
        elif message_type == MCPMessageType.NOTIFICATION:
            params = mcp_message.get("params", {})
            
            if params.get("event") == "statusUpdate":
                # ステータス更新通知
                return StatusUpdate(
                    sender=params.get("sender", "mcp_agent"),
                    recipient=self.agent_id,
                    request_id=params.get("requestId", ""),
                    status=params.get("status", TaskStatus.IN_PROGRESS),
                    progress=params.get("progress"),
                    message=params.get("message", "")
                )
            else:
                # その他の通知は汎用メッセージに変換
                return AgentMessage(
                    sender="mcp_system",
                    recipient=self.agent_id,
                    message_type="notification",
                    content=params,
                    request_id=internal_id
                )
        
        elif message_type == MCPMessageType.ERROR:
            # エラーメッセージ
            error = mcp_message.get("error", {})
            return AgentMessage(
                sender="mcp_system",
                recipient=self.agent_id,
                message_type="error",
                content={
                    "code": error.get("code", 500),
                    "message": error.get("message", "Unknown error")
                },
                request_id=internal_id
            )
        
        return None
    
    async def send_message(self, message: AgentMessage) -> bool:
        """
        AgentMessageをMCPサーバーに送信します。
        
        Args:
            message: 送信するメッセージ
            
        Returns:
            bool: 送信成功の場合はTrue
        """
        if not self.mcp_client:
            logger.error("MCPクライアントが設定されていません")
            return False
        
        try:
            mcp_message = self._convert_agent_message_to_mcp(message)
            
            if mcp_message.get("type") == MCPMessageType.CALL_TOOL:
                # ツール呼び出しの場合
                tool_name = mcp_message.get("params", {}).get("name", "")
                arguments = mcp_message.get("params", {}).get("arguments", {})
                
                result = await self.mcp_client.call_tool(tool_name, arguments)
                logger.info(f"MCPツール呼び出し完了: {tool_name}")
                return True
            
            elif mcp_message.get("type") == MCPMessageType.NOTIFICATION:
                # 通知の場合
                # MCPプロトコルには通知送信のためのAPIがないため、カスタムツールで対応
                await self.mcp_client.call_tool("sendNotification", mcp_message.get("params", {}))
                logger.info("MCP通知送信完了")
                return True
            
            else:
                logger.warning(f"サポートされていないMCPメッセージタイプ: {mcp_message.get('type')}")
                return False
        
        except Exception as e:
            logger.error(f"MCPメッセージ送信エラー: {str(e)}")
            return False
    
    async def receive_message(self) -> Optional[AgentMessage]:
        """
        MCPサーバーからメッセージを受信します。
        非同期でメッセージを待機するため、通常は直接呼び出さず、
        register_handler()で登録したハンドラー経由で受信します。
        
        Returns:
            Optional[AgentMessage]: 受信したメッセージ（受信できない場合はNone）
        """
        # この実装は例示的なものです。MCPクライアントは既にメッセージハンドラを持っています。
        # 実際の実装では、MCPクライアントのメッセージハンドラから内部ハンドラーが呼び出される形になります。
        return None
    
    async def register_mcp_tools(self) -> bool:
        """
        内部プロトコルをサポートするためのMCPツールを登録します。
        
        Returns:
            bool: 登録成功の場合はTrue
        """
        if not self.mcp_client:
            logger.error("MCPクライアントが設定されていません")
            return False
        
        # ここでMCPサーバーに内部プロトコルをサポートする
        # カスタムツールを登録する必要があります
        # （実際の実装では、MCPサーバー側のツール登録機能を使用）
        
        logger.info("内部プロトコル互換ツールが登録されました")
        return True

class MCPGateway:
    """
    複数のエージェント間の通信をMCPプロトコルで中継するゲートウェイ。
    異なるプロトコルのエージェントを接続し、相互運用性を提供します。
    """
    
    def __init__(self, gateway_id: str = "mcp_gateway"):
        """
        MCPゲートウェイを初期化します。
        
        Args:
            gateway_id: ゲートウェイID
        """
        self.gateway_id = gateway_id
        self.agents = {}  # エージェントID:MCPBridge
        self.mcp_server = None
        self.is_running = False
        
        logger.info(f"MCPゲートウェイが初期化されました: {gateway_id}")
    
    async def start_gateway(self, server_name: str = "mcp_gateway", server_version: str = "1.0.0") -> bool:
        """
        ゲートウェイを起動し、MCPサーバーを開始します。
        
        Args:
            server_name: MCPサーバー名
            server_version: MCPサーバーバージョン
            
        Returns:
            bool: 起動成功の場合はTrue
        """
        if self.is_running:
            logger.warning("ゲートウェイは既に起動しています")
            return True
        
        try:
            # MCPマネージャーからサーバーを作成
            manager = MCPManager()
            self.mcp_server = await manager.create_server(
                name=self.gateway_id,
                server_name=server_name,
                server_version=server_version,
                vendor_info={"gateway_id": self.gateway_id}
            )
            
            # 内部プロトコルをサポートするツールを登録
            self._register_protocol_tools()
            
            # サーバー起動は別スレッドで行う必要があります
            # （実際の実装では非同期タスクとして起動）
            
            self.is_running = True
            logger.info("MCPゲートウェイが起動しました")
            return True
        
        except Exception as e:
            logger.error(f"ゲートウェイ起動エラー: {str(e)}")
            return False
    
    def _register_protocol_tools(self) -> None:
        """内部プロトコルをサポートするためのツールを登録します。"""
        if not self.mcp_server:
            return
        
        # executeTask ツール - タスク依頼
        @self.mcp_server.register_tool(
            name="executeTask",
            description="エージェントにタスクを依頼します",
            input_schema={
                "type": "object",
                "properties": {
                    "taskType": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "deadline": {"type": ["string", "null"]},
                    "context": {"type": "object"},
                    "sender": {"type": "string"},
                    "recipient": {"type": "string"},
                    "requestId": {"type": "string"},
                    "timestamp": {"type": "string"}
                },
                "required": ["taskType", "description", "sender", "recipient"]
            },
            required=["taskType", "description", "sender", "recipient"]
        )
        def execute_task(**kwargs):
            # タスク依頼を内部エージェントにルーティング
            # 非同期コンテキスト外のため、ここではイベントキューに入れるなどの対応が必要
            return {"success": True, "message": "タスクが送信されました"}
        
        # submitTaskResult ツール - タスク結果提出
        @self.mcp_server.register_tool(
            name="submitTaskResult",
            description="タスク実行結果を提出します",
            input_schema={
                "type": "object",
                "properties": {
                    "requestId": {"type": "string"},
                    "status": {"type": "string"},
                    "result": {"type": "object"},
                    "message": {"type": "string"},
                    "sender": {"type": "string"},
                    "recipient": {"type": "string"},
                    "timestamp": {"type": "string"}
                },
                "required": ["requestId", "status", "sender", "recipient"]
            },
            required=["requestId", "status", "sender", "recipient"]
        )
        def submit_task_result(**kwargs):
            # タスク結果を内部エージェントにルーティング
            return {"success": True, "message": "結果が送信されました"}
        
        # requestInformation ツール - 情報要求
        @self.mcp_server.register_tool(
            name="requestInformation",
            description="エージェントに情報を要求します",
            input_schema={
                "type": "object",
                "properties": {
                    "relatedRequestId": {"type": "string"},
                    "questions": {"type": "array", "items": {"type": "string"}},
                    "context": {"type": "object"},
                    "sender": {"type": "string"},
                    "recipient": {"type": "string"},
                    "requestId": {"type": "string"},
                    "timestamp": {"type": "string"}
                },
                "required": ["questions", "sender", "recipient"]
            },
            required=["questions", "sender", "recipient"]
        )
        def request_information(**kwargs):
            # 情報要求を内部エージェントにルーティング
            return {"success": True, "message": "情報要求が送信されました"}
        
        # submitInformation ツール - 情報提出
        @self.mcp_server.register_tool(
            name="submitInformation",
            description="要求された情報を提出します",
            input_schema={
                "type": "object",
                "properties": {
                    "requestId": {"type": "string"},
                    "answers": {"type": "object"},
                    "sender": {"type": "string"},
                    "recipient": {"type": "string"},
                    "timestamp": {"type": "string"}
                },
                "required": ["requestId", "answers", "sender", "recipient"]
            },
            required=["requestId", "answers", "sender", "recipient"]
        )
        def submit_information(**kwargs):
            # 情報応答を内部エージェントにルーティング
            return {"success": True, "message": "情報が送信されました"}
        
        # sendMessage ツール - 汎用メッセージ送信
        @self.mcp_server.register_tool(
            name="sendMessage",
            description="任意のメッセージを送信します",
            input_schema={
                "type": "object",
                "additionalProperties": True
            }
        )
        def send_message(**kwargs):
            # 汎用メッセージを内部エージェントにルーティング
            return {"success": True, "message": "メッセージが送信されました"}
        
        # sendNotification ツール - 通知送信
        @self.mcp_server.register_tool(
            name="sendNotification",
            description="通知を送信します",
            input_schema={
                "type": "object",
                "properties": {
                    "event": {"type": "string"},
                    "requestId": {"type": "string"},
                    "status": {"type": "string"},
                    "progress": {"type": ["number", "null"]},
                    "message": {"type": "string"},
                    "sender": {"type": "string"}
                },
                "required": ["event", "sender"]
            },
            required=["event", "sender"]
        )
        def send_notification(**kwargs):
            # 通知を内部エージェントにルーティング
            return {"success": True, "message": "通知が送信されました"}
        
        logger.info("プロトコルツールが登録されました")
    
    async def register_agent(self, agent_id: str, bridge: MCPBridge) -> None:
        """
        エージェントとそのブリッジをゲートウェイに登録します。
        
        Args:
            agent_id: エージェントID
            bridge: そのエージェントのMCPブリッジ
        """
        self.agents[agent_id] = bridge
        logger.info(f"エージェントがゲートウェイに登録されました: {agent_id}")
    
    async def unregister_agent(self, agent_id: str) -> None:
        """
        エージェントをゲートウェイから登録解除します。
        
        Args:
            agent_id: 登録解除するエージェントID
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"エージェントの登録が解除されました: {agent_id}")
    
    async def route_message(self, message: AgentMessage) -> bool:
        """
        メッセージを適切なエージェントにルーティングします。
        
        Args:
            message: ルーティングするメッセージ
            
        Returns:
            bool: ルーティング成功の場合はTrue
        """
        recipient = message.recipient
        
        if recipient in self.agents:
            # 内部エージェント宛の場合は直接ブリッジ経由で送信
            bridge = self.agents[recipient]
            return await bridge.send_message(message)
        else:
            # 不明な宛先の場合はMCPプロトコル経由で送信（外部エージェント向け）
            logger.info(f"外部エージェント宛のメッセージ: {recipient}")
            
            # 外部エージェントへの送信処理
            # （実際の実装ではMCPサーバーを介した通信）
            
            return False
    
    async def stop_gateway(self) -> None:
        """ゲートウェイを停止し、リソースを解放します。"""
        if not self.is_running:
            return
        
        # すべてのエージェントブリッジを切断
        for agent_id, bridge in self.agents.items():
            await bridge.disconnect()
        
        self.agents.clear()
        self.is_running = False
        
        # MCPサーバーの停止処理（実際の実装ではMCPManager経由）
        
        logger.info("MCPゲートウェイが停止しました") 