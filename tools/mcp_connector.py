"""
Model Context Protocol (MCP) コネクタモジュール。
エージェントがMCPプロトコルを通じて外部ツールやデータソースと連携するための機能を提供します。
MCP標準仕様: https://modelcontextprotocol.io/
"""

import os
import json
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import aiohttp
import logging
from pathlib import Path
import tempfile
import uuid

from utils.logger import get_logger
from utils.config import config

logger = get_logger("mcp_connector")

# MCPメッセージタイプの定義
class MCPMessageType:
    """MCPプロトコルで使用されるメッセージタイプ"""
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    LIST_TOOLS = "listTools"
    LIST_TOOLS_RESULT = "listToolsResult"
    CALL_TOOL = "callTool"
    CALL_TOOL_RESULT = "callToolResult"
    LIST_RESOURCES = "listResources"
    LIST_RESOURCES_RESULT = "listResourcesResult"
    READ_RESOURCE = "readResource"
    READ_RESOURCE_RESULT = "readResourceResult"
    LIST_PROMPTS = "listPrompts"
    LIST_PROMPTS_RESULT = "listPromptsResult"
    GET_PROMPT = "getPrompt"
    GET_PROMPT_RESULT = "getPromptResult"
    CREATE_MESSAGE = "createMessage"
    CREATE_MESSAGE_RESULT = "createMessageResult"
    NOTIFICATION = "notification"
    ERROR = "error"
    LOG = "log"

class MCPCapability:
    """MCPサーバーが提供する機能"""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    SAMPLING = "sampling"
    ROOTS = "roots"

class MCPTransport:
    """MCPトランスポート基底クラス"""
    
    def __init__(self):
        self.message_handlers = {}
        self.connected = False
    
    async def connect(self):
        """トランスポートを接続"""
        self.connected = True
    
    async def disconnect(self):
        """トランスポートを切断"""
        self.connected = False
    
    async def send_message(self, message: Dict[str, Any]):
        """メッセージを送信（サブクラスで実装）"""
        raise NotImplementedError
    
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """メッセージを受信（サブクラスで実装）"""
        raise NotImplementedError
    
    def register_handler(self, message_type: str, handler: Callable[[Dict[str, Any]], None]):
        """特定タイプのメッセージハンドラーを登録"""
        self.message_handlers[message_type] = handler
    
    async def handle_messages(self):
        """メッセージ処理ループ"""
        while self.connected:
            message = await self.receive_message()
            if not message:
                continue
            
            message_type = message.get("type")
            if not message_type:
                logger.warning(f"Received message without type: {message}")
                continue
            
            handler = self.message_handlers.get(message_type)
            if handler:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error handling message {message_type}: {str(e)}")
            else:
                logger.warning(f"No handler registered for message type: {message_type}")

class MCPStdIOTransport(MCPTransport):
    """標準入出力を使用したMCPトランスポート"""
    
    def __init__(self, cmd: List[str], env: Optional[Dict[str, str]] = None):
        super().__init__()
        self.cmd = cmd
        self.env = env or {}
        self.process = None
        self.reader = None
        self.writer = None
    
    async def connect(self):
        """プロセスを起動して標準入出力に接続"""
        merged_env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            *self.cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env
        )
        self.reader = self.process.stdout
        self.writer = self.process.stdin
        await super().connect()
        logger.info(f"Connected to MCP server: {' '.join(self.cmd)}")
    
    async def disconnect(self):
        """プロセスを終了して接続を切断"""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        
        self.reader = None
        self.writer = None
        await super().disconnect()
        logger.info("Disconnected from MCP server")
    
    async def send_message(self, message: Dict[str, Any]):
        """メッセージをJSON形式でプロセスの標準入力に送信"""
        if not self.writer:
            raise RuntimeError("Not connected to MCP server")
        
        data = json.dumps(message) + "\n"
        self.writer.write(data.encode("utf-8"))
        await self.writer.drain()
        logger.debug(f"Sent message: {message['type']}")
    
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """プロセスの標準出力からJSON形式のメッセージを受信"""
        if not self.reader:
            raise RuntimeError("Not connected to MCP server")
        
        line = await self.reader.readline()
        if not line:
            logger.info("End of stream received")
            self.connected = False
            return None
        
        try:
            message = json.loads(line.decode("utf-8"))
            logger.debug(f"Received message: {message.get('type')}")
            return message
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {str(e)}")
            return None

class MCPWebSocketTransport(MCPTransport):
    """WebSocketを使用したMCPトランスポート"""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        super().__init__()
        self.url = url
        self.headers = headers or {}
        self.session = None
        self.ws = None
    
    async def connect(self):
        """WebSocketに接続"""
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(self.url, headers=self.headers)
        await super().connect()
        logger.info(f"Connected to MCP server via WebSocket: {self.url}")
    
    async def disconnect(self):
        """WebSocket接続を切断"""
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        if self.session:
            await self.session.close()
            self.session = None
        
        await super().disconnect()
        logger.info("Disconnected from MCP server")
    
    async def send_message(self, message: Dict[str, Any]):
        """メッセージをJSON形式でWebSocketに送信"""
        if not self.ws:
            raise RuntimeError("Not connected to MCP server")
        
        data = json.dumps(message)
        await self.ws.send_str(data)
        logger.debug(f"Sent message: {message['type']}")
    
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """WebSocketからJSON形式のメッセージを受信"""
        if not self.ws:
            raise RuntimeError("Not connected to MCP server")
        
        msg = await self.ws.receive()
        
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                message = json.loads(msg.data)
                logger.debug(f"Received message: {message.get('type')}")
                return message
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {str(e)}")
                return None
        elif msg.type == aiohttp.WSMsgType.CLOSED:
            logger.info("WebSocket closed")
            self.connected = False
            return None
        elif msg.type == aiohttp.WSMsgType.ERROR:
            logger.error(f"WebSocket error: {self.ws.exception()}")
            self.connected = False
            return None
        
        return None

class MCPTool:
    """MCPツール定義"""
    
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        required: List[str] = None
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.required = required or []
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "required": self.required
        }

class MCPResource:
    """MCPリソース定義"""
    
    def __init__(
        self,
        name: str,
        description: str,
        uri_template: str,
        media_type: str = "text/plain"
    ):
        self.name = name
        self.description = description
        self.uri_template = uri_template
        self.media_type = media_type
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "name": self.name,
            "description": self.description,
            "uriTemplate": self.uri_template,
            "mediaType": self.media_type
        }

class MCPPrompt:
    """MCPプロンプト定義"""
    
    def __init__(
        self,
        name: str,
        description: str,
        arguments: List[Dict[str, Any]] = None,
        messages: List[Dict[str, Any]] = None
    ):
        self.name = name
        self.description = description
        self.arguments = arguments or []
        self.messages = messages or []
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }
    
    def get_messages(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """引数を適用したメッセージリストを取得"""
        result = []
        for message in self.messages:
            content = message.get("content", "")
            # 引数を内容に埋め込む
            for key, value in args.items():
                content = content.replace(f"{{{key}}}", str(value))
            
            result.append({
                "role": message.get("role", "user"),
                "content": content
            })
        
        return result

class MCPClient:
    """MCPクライアント実装"""
    
    def __init__(
        self,
        transport: MCPTransport,
        client_name: str = "python-mcp-client",
        client_version: str = "1.0.0"
    ):
        self.transport = transport
        self.client_name = client_name
        self.client_version = client_version
        self.server_info = {}
        self.capabilities = {}
        self.initialized = False
        self.pending_requests = {}
        self._setup_handlers()
    
    def _setup_handlers(self):
        """メッセージハンドラーを設定"""
        self.transport.register_handler(MCPMessageType.INITIALIZED, self._handle_initialized)
        self.transport.register_handler(MCPMessageType.ERROR, self._handle_error)
        self.transport.register_handler(MCPMessageType.LIST_TOOLS_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.CALL_TOOL_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.LIST_RESOURCES_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.READ_RESOURCE_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.LIST_PROMPTS_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.GET_PROMPT_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.CREATE_MESSAGE_RESULT, self._handle_result)
        self.transport.register_handler(MCPMessageType.LOG, self._handle_log)
    
    async def _handle_initialized(self, message: Dict[str, Any]):
        """initialize応答処理"""
        self.server_info = {
            "name": message.get("serverName", ""),
            "version": message.get("serverVersion", ""),
            "vendorInfo": message.get("vendorInfo", {})
        }
        self.capabilities = message.get("capabilities", {})
        self.initialized = True
        
        req_id = message.get("id")
        if req_id in self.pending_requests:
            future = self.pending_requests.pop(req_id)
            future.set_result(self.server_info)
    
    async def _handle_error(self, message: Dict[str, Any]):
        """エラー応答処理"""
        req_id = message.get("id")
        error = message.get("error", {})
        error_msg = error.get("message", "Unknown error")
        logger.error(f"MCP Server error: {error_msg}")
        
        if req_id in self.pending_requests:
            future = self.pending_requests.pop(req_id)
            future.set_exception(Exception(error_msg))
    
    async def _handle_result(self, message: Dict[str, Any]):
        """リクエスト結果処理"""
        req_id = message.get("id")
        if req_id in self.pending_requests:
            future = self.pending_requests.pop(req_id)
            future.set_result(message.get("result", {}))
    
    async def _handle_log(self, message: Dict[str, Any]):
        """ログメッセージ処理"""
        log_message = message.get("message", "")
        log_level = message.get("level", "info")
        
        if log_level == "error":
            logger.error(f"MCP Server: {log_message}")
        elif log_level == "warn":
            logger.warning(f"MCP Server: {log_message}")
        else:
            logger.info(f"MCP Server: {log_message}")
    
    async def _send_request(self, req_type: str, params: Dict[str, Any] = None) -> Any:
        """リクエストを送信し結果を待機"""
        req_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        request = {
            "id": req_id,
            "type": req_type
        }
        
        if params:
            request["params"] = params
        
        await self.transport.send_message(request)
        return await future
    
    async def connect(self):
        """サーバーに接続して初期化"""
        await self.transport.connect()
        
        # メッセージ処理タスクを開始
        asyncio.create_task(self.transport.handle_messages())
        
        # 初期化リクエスト送信
        initialize_params = {
            "clientName": self.client_name,
            "clientVersion": self.client_version,
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True, "subscribeListChanged": True},
                "prompts": {"listChanged": True},
                "sampling": {}
            }
        }
        
        await self._send_request(MCPMessageType.INITIALIZE, initialize_params)
        
        # 初期化が完了するまで待機
        timeout = 30  # 30秒タイムアウト
        start_time = asyncio.get_event_loop().time()
        while not self.initialized:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("MCP server initialization timeout")
            await asyncio.sleep(0.1)
        
        return self.server_info
    
    async def disconnect(self):
        """サーバーから切断"""
        await self.transport.disconnect()
        self.initialized = False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """利用可能なツール一覧を取得"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request(MCPMessageType.LIST_TOOLS)
        return result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Any:
        """ツールを呼び出し"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        params = {
            "name": name,
            "arguments": arguments or {}
        }
        
        result = await self._send_request(MCPMessageType.CALL_TOOL, params)
        return result.get("content")
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """利用可能なリソース一覧を取得"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request(MCPMessageType.LIST_RESOURCES)
        return result.get("resources", [])
    
    async def read_resource(self, uri: str) -> Tuple[str, str]:
        """リソースを読み込み"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        params = {"uri": uri}
        result = await self._send_request(MCPMessageType.READ_RESOURCE, params)
        
        content = result.get("content", "")
        media_type = result.get("mediaType", "text/plain")
        return content, media_type
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """利用可能なプロンプト一覧を取得"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        result = await self._send_request(MCPMessageType.LIST_PROMPTS)
        return result.get("prompts", [])
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """プロンプトを取得"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        params = {
            "name": name,
            "arguments": arguments or {}
        }
        
        return await self._send_request(MCPMessageType.GET_PROMPT, params)
    
    async def create_message(self, prompt: str) -> Dict[str, Any]:
        """メッセージ生成（サンプリング）"""
        if not self.initialized:
            raise RuntimeError("MCP client not initialized")
        
        if "sampling" not in self.capabilities:
            raise RuntimeError("Server does not support sampling capability")
        
        params = {"messages": [{"role": "user", "content": prompt}]}
        return await self._send_request(MCPMessageType.CREATE_MESSAGE, params)

# MCP Server 実装
class MCPServer:
    """MCP Server実装（ローカルモデルとツールを提供）"""
    
    def __init__(
        self,
        server_name: str = "python-mcp-server",
        server_version: str = "1.0.0",
        vendor_info: Dict[str, Any] = None
    ):
        self.server_name = server_name
        self.server_version = server_version
        self.vendor_info = vendor_info or {}
        
        # 登録されたツール、リソース、プロンプト
        self.tools: Dict[str, Callable] = {}
        self.tool_descriptions: Dict[str, MCPTool] = {}
        self.resources: Dict[str, Callable] = {}
        self.resource_descriptions: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self.sampling_handler = None
        
        # クライアント情報
        self.client_info = {}
        self.client_capabilities = {}
    
    def register_tool(
        self, 
        name: str, 
        description: str, 
        input_schema: Dict[str, Any],
        required: List[str] = None
    ) -> Callable:
        """ツールをデコレータで登録"""
        def decorator(func: Callable):
            self.tools[name] = func
            self.tool_descriptions[name] = MCPTool(name, description, input_schema, required)
            return func
        return decorator
    
    def register_resource(
        self,
        name: str,
        description: str,
        uri_template: str,
        media_type: str = "text/plain"
    ) -> Callable:
        """リソースをデコレータで登録"""
        def decorator(func: Callable):
            self.resources[uri_template] = func
            self.resource_descriptions[name] = MCPResource(name, description, uri_template, media_type)
            return func
        return decorator
    
    def register_prompt(
        self,
        name: str,
        description: str,
        arguments: List[Dict[str, Any]] = None,
        messages: List[Dict[str, Any]] = None
    ):
        """プロンプトを登録"""
        self.prompts[name] = MCPPrompt(name, description, arguments, messages)
    
    def register_sampling_handler(self, handler: Callable):
        """サンプリングハンドラを登録"""
        self.sampling_handler = handler
    
    async def handle_initialize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """初期化リクエスト処理"""
        self.client_info = {
            "name": request.get("params", {}).get("clientName", ""),
            "version": request.get("params", {}).get("clientVersion", "")
        }
        self.client_capabilities = request.get("params", {}).get("capabilities", {})
        
        # 対応可能な機能を判断
        capabilities = {}
        
        if self.tools:
            capabilities[MCPCapability.TOOLS] = {"listChanged": True}
        
        if self.resources:
            capabilities[MCPCapability.RESOURCES] = {
                "listChanged": True, 
                "subscribeListChanged": True
            }
        
        if self.prompts:
            capabilities[MCPCapability.PROMPTS] = {"listChanged": True}
        
        if self.sampling_handler:
            capabilities[MCPCapability.SAMPLING] = {}
        
        # 初期化応答送信
        return {
            "id": request.get("id"),
            "type": MCPMessageType.INITIALIZED,
            "serverName": self.server_name,
            "serverVersion": self.server_version,
            "vendorInfo": self.vendor_info,
            "capabilities": capabilities
        }
    
    async def handle_list_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """ツール一覧リクエスト処理"""
        tools = [tool.to_dict() for tool in self.tool_descriptions.values()]
        
        return {
            "id": request.get("id"),
            "type": MCPMessageType.LIST_TOOLS_RESULT,
            "result": {"tools": tools}
        }
    
    async def handle_call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """ツール呼び出しリクエスト処理"""
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return self._create_error_response(
                request.get("id"),
                code=404,
                message=f"Tool not found: {tool_name}"
            )
        
        tool_func = self.tools[tool_name]
        
        try:
            result = await asyncio.to_thread(tool_func, **arguments)
            return {
                "id": request.get("id"),
                "type": MCPMessageType.CALL_TOOL_RESULT,
                "result": {"content": result}
            }
        except Exception as e:
            return self._create_error_response(
                request.get("id"),
                code=500,
                message=f"Tool execution error: {str(e)}"
            )
    
    async def handle_list_resources(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """リソース一覧リクエスト処理"""
        resources = [res.to_dict() for res in self.resource_descriptions.values()]
        
        return {
            "id": request.get("id"),
            "type": MCPMessageType.LIST_RESOURCES_RESULT,
            "result": {"resources": resources}
        }
    
    async def handle_read_resource(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """リソース読み込みリクエスト処理"""
        params = request.get("params", {})
        uri = params.get("uri")
        
        # URIに対応する関数を探す
        resource_func = None
        uri_params = {}
        
        for template, func in self.resources.items():
            # 単純なパターンマッチングの例（実際はより複雑なURI Templateのパースが必要）
            if template == uri or template.split("{")[0] == uri.split("/")[0]:
                resource_func = func
                # URI Templateからパラメータを抽出
                if "{" in template:
                    parts = template.split("/")
                    uri_parts = uri.split("/")
                    
                    if len(parts) == len(uri_parts):
                        for i, part in enumerate(parts):
                            if part.startswith("{") and part.endswith("}"):
                                param_name = part[1:-1]
                                uri_params[param_name] = uri_parts[i]
                break
        
        if not resource_func:
            return self._create_error_response(
                request.get("id"),
                code=404,
                message=f"Resource not found: {uri}"
            )
        
        try:
            content, media_type = await asyncio.to_thread(resource_func, **uri_params)
            
            # リソース記述から適切なメディアタイプを取得
            for resource in self.resource_descriptions.values():
                if resource.uri_template == template:
                    media_type = resource.media_type
                    break
            
            return {
                "id": request.get("id"),
                "type": MCPMessageType.READ_RESOURCE_RESULT,
                "result": {
                    "content": content,
                    "mediaType": media_type
                }
            }
        except Exception as e:
            return self._create_error_response(
                request.get("id"),
                code=500,
                message=f"Resource read error: {str(e)}"
            )
    
    async def handle_list_prompts(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """プロンプト一覧リクエスト処理"""
        prompts = [prompt.to_dict() for prompt in self.prompts.values()]
        
        return {
            "id": request.get("id"),
            "type": MCPMessageType.LIST_PROMPTS_RESULT,
            "result": {"prompts": prompts}
        }
    
    async def handle_get_prompt(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """プロンプト取得リクエスト処理"""
        params = request.get("params", {})
        prompt_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if prompt_name not in self.prompts:
            return self._create_error_response(
                request.get("id"),
                code=404,
                message=f"Prompt not found: {prompt_name}"
            )
        
        prompt = self.prompts[prompt_name]
        try:
            messages = prompt.get_messages(arguments)
            
            return {
                "id": request.get("id"),
                "type": MCPMessageType.GET_PROMPT_RESULT,
                "result": {
                    "messages": messages,
                    "description": prompt.description
                }
            }
        except Exception as e:
            return self._create_error_response(
                request.get("id"),
                code=500,
                message=f"Prompt processing error: {str(e)}"
            )
    
    async def handle_create_message(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """メッセージ生成（サンプリング）リクエスト処理"""
        if not self.sampling_handler:
            return self._create_error_response(
                request.get("id"),
                code=400,
                message="Sampling not supported"
            )
        
        params = request.get("params", {})
        messages = params.get("messages", [])
        
        try:
            result = await asyncio.to_thread(self.sampling_handler, messages)
            
            return {
                "id": request.get("id"),
                "type": MCPMessageType.CREATE_MESSAGE_RESULT,
                "result": result
            }
        except Exception as e:
            return self._create_error_response(
                request.get("id"),
                code=500,
                message=f"Message creation error: {str(e)}"
            )
    
    def _create_error_response(self, req_id: str, code: int, message: str) -> Dict[str, Any]:
        """エラーレスポンスを生成"""
        return {
            "id": req_id,
            "type": MCPMessageType.ERROR,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """リクエスト処理のルーティング"""
        request_type = request.get("type")
        
        if request_type == MCPMessageType.INITIALIZE:
            return await self.handle_initialize(request)
        elif request_type == MCPMessageType.LIST_TOOLS:
            return await self.handle_list_tools(request)
        elif request_type == MCPMessageType.CALL_TOOL:
            return await self.handle_call_tool(request)
        elif request_type == MCPMessageType.LIST_RESOURCES:
            return await self.handle_list_resources(request)
        elif request_type == MCPMessageType.READ_RESOURCE:
            return await self.handle_read_resource(request)
        elif request_type == MCPMessageType.LIST_PROMPTS:
            return await self.handle_list_prompts(request)
        elif request_type == MCPMessageType.GET_PROMPT:
            return await self.handle_get_prompt(request)
        elif request_type == MCPMessageType.CREATE_MESSAGE:
            return await self.handle_create_message(request)
        else:
            return self._create_error_response(
                request.get("id", "0"),
                code=400,
                message=f"Unsupported request type: {request_type}"
            )
    
    async def start_stdio_server(self):
        """標準入出力を使用してサーバーを起動"""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, input)
                if not line:
                    continue
                
                request = json.loads(line)
                response = await self.handle_request(request)
                
                # レスポンス送信
                print(json.dumps(response))
            except json.JSONDecodeError:
                # 無効なJSONを受信した場合はスキップ
                continue
            except EOFError:
                # 入力ストリームが閉じられた場合は終了
                break
            except Exception as e:
                # 例外が発生した場合はエラーレスポンス送信
                error_response = self._create_error_response(
                    "0",  # リクエストIDが不明の場合
                    code=500,
                    message=f"Internal server error: {str(e)}"
                )
                print(json.dumps(error_response))

# MCPをツールとして使用するためのマネージャークラス
class MCPManager:
    """MCPサーバーとクライアントを管理するシングルトンクラス"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPManager, cls).__new__(cls)
            cls._instance.servers = {}  # 名前:サーバーインスタンス
            cls._instance.clients = {}  # 名前:クライアントインスタンス
            cls._instance.server_processes = {}  # 名前:プロセス
        return cls._instance
    
    async def create_server(
        self,
        name: str,
        server_name: str = "python-mcp-server",
        server_version: str = "1.0.0",
        vendor_info: Dict[str, Any] = None
    ) -> MCPServer:
        """新しいMCPサーバーを作成"""
        if name in self.servers:
            return self.servers[name]
        
        server = MCPServer(server_name, server_version, vendor_info)
        self.servers[name] = server
        return server
    
    async def start_server(self, name: str, interface: str = "stdio"):
        """サーバーを起動"""
        if name not in self.servers:
            raise KeyError(f"Server not found: {name}")
        
        server = self.servers[name]
        
        if interface == "stdio":
            await server.start_stdio_server()
        else:
            raise ValueError(f"Unsupported interface: {interface}")
    
    async def connect_to_server(
        self,
        name: str,
        command: List[str],
        env: Dict[str, str] = None,
        client_name: str = "python-mcp-client",
        transport_type: str = "stdio"
    ) -> MCPClient:
        """サーバーに接続するクライアントを作成"""
        if name in self.clients:
            return self.clients[name]
        
        if transport_type == "stdio":
            transport = MCPStdIOTransport(command, env)
        elif transport_type == "websocket":
            # URLはコマンドの最初の要素
            url = command[0]
            headers = env if env else {}
            transport = MCPWebSocketTransport(url, headers)
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")
        
        client = MCPClient(transport, client_name)
        await client.connect()
        
        self.clients[name] = client
        return client
    
    async def start_external_server(
        self,
        name: str,
        command: List[str],
        env: Dict[str, str] = None
    ) -> subprocess.Popen:
        """外部MCP互換サーバーを起動"""
        if name in self.server_processes:
            return self.server_processes[name]
        
        merged_env = {**os.environ, **(env or {})}
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            text=True
        )
        
        self.server_processes[name] = process
        return process
    
    async def stop_external_server(self, name: str):
        """外部サーバーを停止"""
        if name in self.server_processes:
            process = self.server_processes[name]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            del self.server_processes[name]
    
    async def disconnect_client(self, name: str):
        """クライアントを切断"""
        if name in self.clients:
            client = self.clients[name]
            await client.disconnect()
            del self.clients[name]
    
    async def cleanup(self):
        """すべてのサーバーとクライアントをクリーンアップ"""
        # クライアント切断
        for name in list(self.clients.keys()):
            await self.disconnect_client(name)
        
        # 外部サーバー停止
        for name in list(self.server_processes.keys()):
            await self.stop_external_server(name)


# ヘルパー関数
async def create_mcp_client(
    server_cmd: List[str],
    env: Dict[str, str] = None,
    client_name: str = "python-mcp-client"
) -> MCPClient:
    """MCPクライアントを作成して接続"""
    manager = MCPManager()
    return await manager.connect_to_server(
        name=f"client-{uuid.uuid4()}",
        command=server_cmd,
        env=env,
        client_name=client_name
    )

def create_mcp_tool_adapter(tool_name: str, description: str, server_cmd: List[str], env: Dict[str, str] = None):
    """MCPサーバーを利用したツールアダプター関数を作成"""
    async def _mcp_tool_wrapper(**kwargs):
        """MCPサーバーに接続してツールを呼び出す"""
        client = await create_mcp_client(server_cmd, env)
        try:
            return await client.call_tool(tool_name, kwargs)
        finally:
            await client.disconnect()
    
    return _mcp_tool_wrapper 