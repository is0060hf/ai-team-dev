"""
MCP (Model Context Protocol) 互換性テスト。
MCPプロトコルの各機能が正しく動作するかを検証します。
"""

import os
import sys
import unittest
import asyncio
import uuid
import json
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# テストするモジュールを適切にインポートできるようにパスを設定
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.mcp_bridge import MCPBridge, MCPGateway
from utils.mcp_mapper import MCPRole, MCPMapper, get_mcp_mapper
from utils.mcp_conversation import (
    MCPMessage, MCPConversation, ConversationStatus,
    MCPConversationManager, get_conversation_manager
)
from utils.agent_communication import (
    AgentMessage, TaskRequest, TaskResponse, TaskStatus, TaskType, TaskPriority,
    InfoRequest, InfoResponse, StatusUpdate
)
from tools.mcp_connector import (
    MCPClient, MCPServer, MCPTransport, MCPStdIOTransport,
    MCPMessageType, MCPManager, MCPTool
)

class MCPCompatibilityTest(unittest.TestCase):
    """MCP互換性テストケース"""
    
    def setUp(self):
        """テスト前の準備"""
        # テスト用の一時ディレクトリを作成
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # テスト用のマッパーインスタンスを取得
        self.mcp_mapper = get_mcp_mapper()
        
        # テスト用の会話マネージャーインスタンスを取得
        self.conversation_manager = get_conversation_manager()
        
        # MCPブリッジのモック
        self.mock_mcp_client = MagicMock()
        self.mcp_bridge = MCPBridge("test_agent", self.mock_mcp_client)
        
        # MCPゲートウェイのモック
        self.mcp_gateway = MCPGateway("test_gateway")
        self.mcp_gateway.mcp_server = MagicMock()
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # 一時ディレクトリを削除
        self.temp_dir.cleanup()
        
        # 会話マネージャーをクリア
        self.conversation_manager.conversations.clear()
        self.conversation_manager.active_conversation_id = None
    
    def test_mcp_role_mapping(self):
        """MCPロールマッピングのテスト"""
        # 基本的なマッピングのテスト
        self.assertEqual(self.mcp_mapper.get_mcp_role("PdM"), MCPRole.PLANNER)
        self.assertEqual(self.mcp_mapper.get_mcp_role("PM"), MCPRole.COORDINATOR)
        self.assertEqual(self.mcp_mapper.get_mcp_role("エンジニア"), MCPRole.EXECUTOR)
        
        # 未知の役割はCUSTOMにマッピングされることを確認
        self.assertEqual(self.mcp_mapper.get_mcp_role("未知の役割"), MCPRole.CUSTOM)
        
        # カスタムマッピングの追加と削除
        self.mcp_mapper.add_mapping("カスタム役割", MCPRole.CRITIC)
        self.assertEqual(self.mcp_mapper.get_mcp_role("カスタム役割"), MCPRole.CRITIC)
        
        self.assertTrue(self.mcp_mapper.remove_mapping("カスタム役割"))
        self.assertEqual(self.mcp_mapper.get_mcp_role("カスタム役割"), MCPRole.CUSTOM)
    
    def test_task_type_to_role_inference(self):
        """タスク種別からロール推論のテスト"""
        # タスク種別からロールの推論
        self.assertEqual(
            self.mcp_mapper.infer_mcp_role_from_task(TaskType.ARCHITECTURE_DESIGN),
            MCPRole.PLANNER
        )
        self.assertEqual(
            self.mcp_mapper.infer_mcp_role_from_task(TaskType.PROMPT_OPTIMIZATION),
            MCPRole.ASSISTANT
        )
        
        # タスク種別から適切なエージェント役割の推論
        planner_roles = self.mcp_mapper.infer_agent_roles_from_task(TaskType.ARCHITECTURE_DESIGN)
        self.assertIn("PdM", planner_roles)
        self.assertIn("PL", planner_roles)
        self.assertIn("AIアーキテクト", planner_roles)
    
    def test_message_role_conversion(self):
        """メッセージロール変換のテスト"""
        # 内部ロール → MCP ロールの変換
        messages = [
            {"role": "PdM", "content": "テストメッセージ1"},
            {"role": "エンジニア", "content": "テストメッセージ2"},
            {"role": "未知の役割", "content": "テストメッセージ3"}
        ]
        
        converted = self.mcp_mapper.convert_message_roles(messages, to_mcp=True)
        
        self.assertEqual(converted[0]["role"], MCPRole.PLANNER.value)
        self.assertEqual(converted[1]["role"], MCPRole.EXECUTOR.value)
        self.assertEqual(converted[2]["role"], MCPRole.CUSTOM.value)
        
        # MCP ロール → 内部ロールの変換
        mcp_messages = [
            {"role": "planner", "content": "テストメッセージ1"},
            {"role": "executor", "content": "テストメッセージ2"},
            {"role": "unknown_role", "content": "テストメッセージ3"}
        ]
        
        back_converted = self.mcp_mapper.convert_message_roles(mcp_messages, to_mcp=False)
        
        # 最初に見つかった対応する役割に変換される
        self.assertEqual(back_converted[0]["role"], "PdM")  # または "PL", "AIアーキテクト"
        self.assertEqual(back_converted[1]["role"], "エンジニア")
        # 不明なロールはそのまま
        self.assertEqual(back_converted[2]["role"], "unknown_role")
    
    def test_mcp_message_format(self):
        """MCPメッセージ形式のテスト"""
        # 基本的なメッセージ作成
        message = MCPMessage(
            role="user",
            content="テストメッセージ",
            metadata={"source": "test"}
        )
        
        # 辞書への変換
        message_dict = message.to_dict()
        self.assertEqual(message_dict["role"], "user")
        self.assertEqual(message_dict["content"], "テストメッセージ")
        self.assertEqual(message_dict["metadata"]["source"], "test")
        
        # 辞書からの作成
        restored_message = MCPMessage.from_dict(message_dict)
        self.assertEqual(restored_message.role, "user")
        self.assertEqual(restored_message.content, "テストメッセージ")
        self.assertEqual(restored_message.metadata["source"], "test")
        
        # LLM形式への変換
        llm_format = message.to_llm_format()
        self.assertEqual(llm_format["role"], "user")
        self.assertEqual(llm_format["content"], "テストメッセージ")
        self.assertNotIn("metadata", llm_format)
    
    def test_mcp_conversation_management(self):
        """MCP会話管理のテスト"""
        # 会話の作成
        conversation = self.conversation_manager.create_conversation({"topic": "テスト会話"})
        self.assertEqual(conversation.metadata["topic"], "テスト会話")
        self.assertEqual(conversation.status, ConversationStatus.ACTIVE)
        
        # メッセージの追加
        message = self.conversation_manager.add_message_to_conversation(
            conversation.id,
            role="user",
            content="こんにちは",
            metadata={"source": "test"}
        )
        self.assertIsNotNone(message)
        self.assertEqual(message.role, "user")  # MCPマッパー経由で変換される
        
        # 会話履歴の取得
        history = self.conversation_manager.get_conversation_history(conversation.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "こんにちは")
        
        # 会話状態の更新
        self.assertTrue(self.conversation_manager.update_conversation_status(
            conversation.id,
            ConversationStatus.COMPLETED
        ))
        
        updated_conversation = self.conversation_manager.get_conversation(conversation.id)
        self.assertEqual(updated_conversation.status, ConversationStatus.COMPLETED)
        
        # 会話の保存と読み込み
        file_path = os.path.join(self.temp_dir.name, "conversation.json")
        self.assertTrue(self.conversation_manager.save_conversation(conversation.id, file_path))
        
        # 会話の削除
        self.assertTrue(self.conversation_manager.delete_conversation(conversation.id))
        self.assertIsNone(self.conversation_manager.get_conversation(conversation.id))
        
        # 保存した会話の読み込み
        loaded_id = self.conversation_manager.load_conversation(file_path)
        self.assertIsNotNone(loaded_id)
        
        loaded_conversation = self.conversation_manager.get_conversation(loaded_id)
        self.assertEqual(loaded_conversation.metadata["topic"], "テスト会話")
        self.assertEqual(loaded_conversation.status, ConversationStatus.COMPLETED)
        self.assertEqual(len(loaded_conversation.messages), 1)
    
    def test_agent_message_to_mcp_conversion(self):
        """内部エージェントメッセージ → MCP変換のテスト"""
        # タスク依頼の変換
        task_request = TaskRequest(
            sender="PdM",
            recipient="エンジニア",
            task_type=TaskType.ARCHITECTURE_DESIGN,
            description="アーキテクチャを設計してください",
            priority=TaskPriority.HIGH
        )
        
        mcp_message = self.mcp_bridge._convert_agent_message_to_mcp(task_request)
        
        self.assertEqual(mcp_message["type"], MCPMessageType.CALL_TOOL)
        self.assertEqual(mcp_message["params"]["name"], "executeTask")
        self.assertEqual(mcp_message["params"]["arguments"]["taskType"], TaskType.ARCHITECTURE_DESIGN.value)
        self.assertEqual(mcp_message["params"]["arguments"]["sender"], "PdM")
        self.assertEqual(mcp_message["params"]["arguments"]["recipient"], "エンジニア")
        
        # タスク応答の変換
        task_response = TaskResponse(
            sender="エンジニア",
            recipient="PdM",
            request_id=task_request.request_id,
            status=TaskStatus.COMPLETED,
            result={"design": "アーキテクチャ設計図"}
        )
        
        mcp_message = self.mcp_bridge._convert_agent_message_to_mcp(task_response)
        
        self.assertEqual(mcp_message["type"], MCPMessageType.CALL_TOOL)
        self.assertEqual(mcp_message["params"]["name"], "submitTaskResult")
        self.assertEqual(mcp_message["params"]["arguments"]["requestId"], task_request.request_id)
        self.assertEqual(mcp_message["params"]["arguments"]["status"], TaskStatus.COMPLETED.value)
        self.assertEqual(mcp_message["params"]["arguments"]["result"]["design"], "アーキテクチャ設計図")
    
    def test_mcp_to_agent_message_conversion(self):
        """MCP → 内部エージェントメッセージ変換のテスト"""
        # ツール結果 → タスク依頼の変換
        mcp_message = {
            "id": "test-id",
            "type": MCPMessageType.CALL_TOOL_RESULT,
            "params": {"name": "executeTask"},
            "result": {
                "content": {
                    "taskType": TaskType.ARCHITECTURE_DESIGN.value,
                    "description": "アーキテクチャを設計してください",
                    "sender": "PdM",
                    "recipient": "test_agent",
                    "requestId": "req-123"
                }
            }
        }
        
        agent_message = self.mcp_bridge._convert_mcp_to_agent_message(mcp_message)
        
        self.assertIsInstance(agent_message, TaskRequest)
        self.assertEqual(agent_message.sender, "PdM")
        self.assertEqual(agent_message.recipient, "test_agent")
        self.assertEqual(agent_message.content["task_type"], TaskType.ARCHITECTURE_DESIGN.value)
        
        # ツール結果 → タスク応答の変換
        mcp_message = {
            "id": "test-id",
            "type": MCPMessageType.CALL_TOOL_RESULT,
            "params": {"name": "submitTaskResult"},
            "result": {
                "content": {
                    "requestId": "req-123",
                    "status": TaskStatus.COMPLETED.value,
                    "result": {"design": "アーキテクチャ設計図"},
                    "sender": "エンジニア",
                    "recipient": "test_agent"
                }
            }
        }
        
        agent_message = self.mcp_bridge._convert_mcp_to_agent_message(mcp_message)
        
        self.assertIsInstance(agent_message, TaskResponse)
        self.assertEqual(agent_message.sender, "エンジニア")
        self.assertEqual(agent_message.request_id, "req-123")
        self.assertEqual(agent_message.content["status"], TaskStatus.COMPLETED.value)
        self.assertEqual(agent_message.content["result"]["design"], "アーキテクチャ設計図")
    
    @patch('asyncio.create_subprocess_exec')
    async def test_mcp_bridge_connect(self, mock_create_subprocess_exec):
        """MCPブリッジ接続テスト"""
        # asyncioのサブプロセスのモックを設定
        mock_process = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdin = AsyncMock()
        mock_create_subprocess_exec.return_value = mock_process
        
        # MCPクライアントのconnectメソッドをモック
        mock_connect = AsyncMock(return_value={"name": "test-server"})
        
        # 新しいブリッジインスタンスを作成（モックMCPクライアントなし）
        bridge = MCPBridge("test_agent")
        
        with patch.object(bridge, 'mcp_client', AsyncMock()) as mock_client:
            mock_client.connect = mock_connect
            
            # 接続テスト（既存のクライアントがある場合）
            result = await bridge.connect_to_mcp_server(["echo", "test"])
            self.assertTrue(result)
            mock_connect.assert_called_once()
    
    @unittest.skip("This test requires the actual implementation of MCPServer")
    async def test_mcp_gateway_start(self):
        """MCPゲートウェイ起動テスト"""
        # MCPマネージャーのcreate_serverメソッドをモック
        with patch('utils.mcp_bridge.MCPManager') as mock_manager_class:
            mock_manager = mock_manager_class.return_value
            mock_server = MagicMock()
            mock_manager.create_server = AsyncMock(return_value=mock_server)
            
            # ゲートウェイを起動
            gateway = MCPGateway("test_gateway")
            result = await gateway.start_gateway()
            
            self.assertTrue(result)
            mock_manager.create_server.assert_called_once()
            self.assertEqual(gateway.mcp_server, mock_server)
            
            # プロトコルツールが登録されたことを確認
            self.assertTrue(hasattr(gateway, '_register_protocol_tools'))
            gateway._register_protocol_tools.assert_called_once()
    
    def test_mcp_gateway_protocol_tools(self):
        """MCPゲートウェイプロトコルツール登録テスト"""
        # ツール登録メソッドをモック
        self.mcp_gateway.mcp_server.register_tool = MagicMock(return_value=lambda **kwargs: None)
        
        # プロトコルツールを登録
        self.mcp_gateway._register_protocol_tools()
        
        # 必要なツールが登録されたことを確認
        self.mcp_gateway.mcp_server.register_tool.assert_any_call(
            name="executeTask",
            description=unittest.mock.ANY,
            input_schema=unittest.mock.ANY,
            required=unittest.mock.ANY
        )
        self.mcp_gateway.mcp_server.register_tool.assert_any_call(
            name="submitTaskResult",
            description=unittest.mock.ANY,
            input_schema=unittest.mock.ANY,
            required=unittest.mock.ANY
        )
        self.mcp_gateway.mcp_server.register_tool.assert_any_call(
            name="requestInformation",
            description=unittest.mock.ANY,
            input_schema=unittest.mock.ANY,
            required=unittest.mock.ANY
        )
        self.mcp_gateway.mcp_server.register_tool.assert_any_call(
            name="submitInformation",
            description=unittest.mock.ANY,
            input_schema=unittest.mock.ANY,
            required=unittest.mock.ANY
        )


class MCPVersionCompatibilityTest(unittest.TestCase):
    """MCP バージョン互換性テストケース"""
    
    def setUp(self):
        """テスト前の準備"""
        # 現在のMCPバージョンとテスト用のダミーバージョン
        self.current_version = "1.0.0"
        self.future_version = "2.0.0"
        self.backward_compatible_version = "1.1.0"
        self.incompatible_version = "0.5.0"
    
    def test_version_compatibility_check(self):
        """バージョン互換性チェックのテスト"""
        # バージョン互換性チェック関数の仮実装
        def is_compatible(client_version, server_version):
            """バージョン互換性を確認する簡易関数"""
            client_major = int(client_version.split('.')[0])
            server_major = int(server_version.split('.')[0])
            
            # メジャーバージョンが同じであれば互換性あり
            return client_major == server_major
        
        # 同一バージョン間の互換性
        self.assertTrue(is_compatible(self.current_version, self.current_version))
        
        # マイナーバージョンが異なる場合の互換性
        self.assertTrue(is_compatible(self.current_version, self.backward_compatible_version))
        
        # メジャーバージョンが異なる場合の互換性（なし）
        self.assertFalse(is_compatible(self.current_version, self.future_version))
        self.assertFalse(is_compatible(self.current_version, self.incompatible_version))
    
    @patch('tools.mcp_connector.MCPClient')
    def test_fallback_mechanism(self, mock_client_class):
        """互換性がない場合のフォールバック機構のテスト"""
        # クライアント接続エラーをシミュレート
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(side_effect=Exception("Version incompatible"))
        
        # フォールバック機構の仮実装
        async def connect_with_fallback(version_list):
            """複数バージョンを試行する接続関数"""
            for version in version_list:
                try:
                    # このバージョンで接続試行
                    client = mock_client_class()
                    await client.connect()
                    return client, version
                except Exception:
                    # 接続失敗、次のバージョンを試行
                    continue
            
            # すべてのバージョンで失敗
            return None, None
        
        # フォールバック機構のテスト（すべて失敗するケース）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 接続が失敗するケースを確認
        client, version = loop.run_until_complete(
            connect_with_fallback([self.current_version, self.future_version])
        )
        self.assertIsNone(client)
        self.assertIsNone(version)
        
        loop.close()


# テストの実行
if __name__ == "__main__":
    unittest.main() 