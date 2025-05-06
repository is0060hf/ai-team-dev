"""
utils/agent_communication.py のユニットテスト。
エージェント間メッセージの基本クラスとディスパッチャーのテストを行います。
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from utils.agent_communication import (
    AgentMessage, TaskRequest, TaskResponse, InfoRequest, InfoResponse,
    StatusUpdate, MessageDispatcher, TaskPriority, TaskStatus, TaskType,
    create_task_request, create_task_response, send_task_request,
    send_task_response, update_task_status, request_information,
    respond_to_information, get_task_status, dispatcher
)
from utils.workflow_automation import SpecialistAgents, CoreAgents


class TestAgentMessage:
    """AgentMessage基本クラスのテスト"""

    def test_agent_message_initialization(self):
        """AgentMessageの初期化と属性が正しく設定されることを確認"""
        message = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="test_type",
            content={"key": "value"},
            request_id="test_request_id",
            reference_id="test_reference_id"
        )
        
        assert message.sender == "test_sender"
        assert message.recipient == "test_recipient"
        assert message.message_type == "test_type"
        assert message.content == {"key": "value"}
        assert message.request_id == "test_request_id"
        assert message.reference_id == "test_reference_id"
        assert message.timestamp is not None  # タイムスタンプが設定されていることを確認
    
    def test_agent_message_to_dict(self):
        """AgentMessageをdictに変換できることを確認"""
        message = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="test_type",
            content={"key": "value"},
            request_id="test_request_id",
            reference_id="test_reference_id"
        )
        
        message_dict = message.to_dict()
        
        assert message_dict["sender"] == "test_sender"
        assert message_dict["recipient"] == "test_recipient"
        assert message_dict["message_type"] == "test_type"
        assert message_dict["content"] == {"key": "value"}
        assert message_dict["request_id"] == "test_request_id"
        assert message_dict["reference_id"] == "test_reference_id"
        assert "timestamp" in message_dict
    
    def test_agent_message_to_json(self):
        """AgentMessageをJSONに変換できることを確認"""
        message = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="test_type",
            content={"key": "value"},
            request_id="test_request_id",
            reference_id="test_reference_id"
        )
        
        json_str = message.to_json()
        
        # JSONとして解析できることを確認
        parsed = json.loads(json_str)
        assert parsed["sender"] == "test_sender"
        assert parsed["recipient"] == "test_recipient"
    
    def test_agent_message_from_dict(self):
        """dictからAgentMessageを作成できることを確認"""
        message_dict = {
            "sender": "test_sender",
            "recipient": "test_recipient",
            "message_type": "test_type",
            "content": {"key": "value"},
            "request_id": "test_request_id",
            "reference_id": "test_reference_id",
            "timestamp": "2023-01-01T00:00:00"
        }
        
        message = AgentMessage.from_dict(message_dict)
        
        assert message.sender == "test_sender"
        assert message.recipient == "test_recipient"
        assert message.message_type == "test_type"
        assert message.content == {"key": "value"}
        assert message.request_id == "test_request_id"
        assert message.reference_id == "test_reference_id"
    
    def test_agent_message_from_json(self):
        """JSONからAgentMessageを作成できることを確認"""
        json_str = json.dumps({
            "sender": "test_sender",
            "recipient": "test_recipient",
            "message_type": "test_type",
            "content": {"key": "value"},
            "request_id": "test_request_id",
            "reference_id": "test_reference_id",
            "timestamp": "2023-01-01T00:00:00"
        })
        
        message = AgentMessage.from_json(json_str)
        
        assert message.sender == "test_sender"
        assert message.recipient == "test_recipient"
        assert message.message_type == "test_type"
        assert message.content == {"key": "value"}
        assert message.request_id == "test_request_id"
        assert message.reference_id == "test_reference_id"


class TestTaskRequest:
    """TaskRequestクラスのテスト"""
    
    def test_task_request_initialization(self):
        """TaskRequestの初期化と属性が正しく設定されることを確認"""
        task_request = TaskRequest(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            task_type=TaskType.ARCHITECTURE_DESIGN,
            description="テスト用のアーキテクチャ設計タスク",
            priority=TaskPriority.MEDIUM,
            deadline="2023-12-31T23:59:59",
            context={"project": "test_project"},
            attachments=["file1.txt", "file2.txt"]
        )
        
        assert task_request.sender == CoreAgents.ENGINEER
        assert task_request.recipient == SpecialistAgents.AI_ARCHITECT
        assert task_request.message_type == "task_request"
        assert task_request.content["task_type"] == TaskType.ARCHITECTURE_DESIGN.value
        assert task_request.content["description"] == "テスト用のアーキテクチャ設計タスク"
        assert task_request.content["priority"] == TaskPriority.MEDIUM.value
        assert task_request.content["deadline"] == "2023-12-31T23:59:59"
        assert task_request.content["context"] == {"project": "test_project"}
        assert task_request.content["attachments"] == ["file1.txt", "file2.txt"]
        assert task_request.content["status"] == TaskStatus.PENDING.value
    
    def test_task_request_with_string_task_type(self):
        """文字列形式のタスク種別でTaskRequestを初期化できることを確認"""
        task_request = TaskRequest(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            task_type="カスタムタスク",
            description="テスト用カスタムタスク",
            priority=TaskPriority.MEDIUM
        )
        
        assert task_request.content["task_type"] == "カスタムタスク"
    
    def test_task_request_with_string_priority(self):
        """文字列形式の優先度でTaskRequestを初期化できることを確認"""
        task_request = TaskRequest(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            task_type=TaskType.ARCHITECTURE_DESIGN,
            description="テスト用のアーキテクチャ設計タスク",
            priority="カスタム優先度"
        )
        
        assert task_request.content["priority"] == "カスタム優先度"


class TestTaskResponse:
    """TaskResponseクラスのテスト"""
    
    def test_task_response_initialization(self):
        """TaskResponseの初期化と属性が正しく設定されることを確認"""
        task_response = TaskResponse(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            status=TaskStatus.COMPLETED,
            result={"recommendation": "テスト用のアーキテクチャ推奨事項"},
            message="タスクが完了しました",
            attachments=["result1.txt", "result2.txt"]
        )
        
        assert task_response.sender == SpecialistAgents.AI_ARCHITECT
        assert task_response.recipient == CoreAgents.ENGINEER
        assert task_response.message_type == "task_response"
        assert task_response.reference_id == "test_request_id"
        assert task_response.content["status"] == TaskStatus.COMPLETED.value
        assert task_response.content["result"] == {"recommendation": "テスト用のアーキテクチャ推奨事項"}
        assert task_response.content["message"] == "タスクが完了しました"
        assert task_response.content["attachments"] == ["result1.txt", "result2.txt"]
    
    def test_task_response_with_string_status(self):
        """文字列形式のステータスでTaskResponseを初期化できることを確認"""
        task_response = TaskResponse(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            status="カスタムステータス"
        )
        
        assert task_response.content["status"] == "カスタムステータス"


class TestInfoRequest:
    """InfoRequestクラスのテスト"""
    
    def test_info_request_initialization(self):
        """InfoRequestの初期化と属性が正しく設定されることを確認"""
        info_request = InfoRequest(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            questions=["質問1", "質問2"],
            context={"background": "テスト背景情報"}
        )
        
        assert info_request.sender == SpecialistAgents.AI_ARCHITECT
        assert info_request.recipient == CoreAgents.ENGINEER
        assert info_request.message_type == "info_request"
        assert info_request.reference_id == "test_request_id"
        assert info_request.content["questions"] == ["質問1", "質問2"]
        assert info_request.content["context"] == {"background": "テスト背景情報"}


class TestInfoResponse:
    """InfoResponseクラスのテスト"""
    
    def test_info_response_initialization(self):
        """InfoResponseの初期化と属性が正しく設定されることを確認"""
        info_response = InfoResponse(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            request_id="test_request_id",
            answers={"質問1": "回答1", "質問2": "回答2"},
            attachments=["info1.txt", "info2.txt"]
        )
        
        assert info_response.sender == CoreAgents.ENGINEER
        assert info_response.recipient == SpecialistAgents.AI_ARCHITECT
        assert info_response.message_type == "info_response"
        assert info_response.reference_id == "test_request_id"
        assert info_response.content["answers"] == {"質問1": "回答1", "質問2": "回答2"}
        assert info_response.content["attachments"] == ["info1.txt", "info2.txt"]


class TestStatusUpdate:
    """StatusUpdateクラスのテスト"""
    
    def test_status_update_initialization(self):
        """StatusUpdateの初期化と属性が正しく設定されることを確認"""
        status_update = StatusUpdate(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.PM,
            request_id="test_request_id",
            status=TaskStatus.IN_PROGRESS,
            progress=0.5,
            message="50%完了しました"
        )
        
        assert status_update.sender == SpecialistAgents.AI_ARCHITECT
        assert status_update.recipient == CoreAgents.PM
        assert status_update.message_type == "status_update"
        assert status_update.reference_id == "test_request_id"
        assert status_update.content["status"] == TaskStatus.IN_PROGRESS.value
        assert status_update.content["progress"] == 0.5
        assert status_update.content["message"] == "50%完了しました"
    
    def test_status_update_with_string_status(self):
        """文字列形式のステータスでStatusUpdateを初期化できることを確認"""
        status_update = StatusUpdate(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.PM,
            request_id="test_request_id",
            status="カスタムステータス"
        )
        
        assert status_update.content["status"] == "カスタムステータス"


class TestMessageDispatcher:
    """MessageDispatcherクラスのテスト"""
    
    def test_singleton_pattern(self):
        """MessageDispatcherがシングルトンパターンを実装していることを確認"""
        dispatcher1 = MessageDispatcher()
        dispatcher2 = MessageDispatcher()
        
        assert dispatcher1 is dispatcher2
    
    def test_register_agent(self, clean_message_dispatcher):
        """エージェントを登録できることを確認"""
        dispatcher = clean_message_dispatcher
        
        dispatcher.register_agent("test_agent")
        
        assert "test_agent" in dispatcher._message_queues
        assert dispatcher._message_queues["test_agent"] == []
    
    def test_register_handler(self, clean_message_dispatcher):
        """メッセージハンドラーを登録できることを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_agent")
        
        # ハンドラーを登録
        handler = MagicMock()
        dispatcher.register_handler("test_agent", "test_message", handler)
        
        assert "test_agent" in dispatcher._handlers
        assert "test_message" in dispatcher._handlers["test_agent"]
        assert dispatcher._handlers["test_agent"]["test_message"] == handler
    
    def test_send_message_success(self, clean_message_dispatcher, sample_agent_message):
        """メッセージを正常に送信できることを確認"""
        dispatcher = clean_message_dispatcher
        
        # 受信側エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # メッセージの受信先を設定
        message = sample_agent_message
        message.recipient = "test_recipient"
        
        # メッセージを送信
        result = dispatcher.send_message(message)
        
        assert result is True
        assert message in dispatcher._message_queues["test_recipient"]
    
    def test_send_message_failure(self, clean_message_dispatcher, sample_agent_message):
        """存在しないエージェントへのメッセージ送信が失敗することを確認"""
        dispatcher = clean_message_dispatcher
        
        # メッセージの受信先を存在しないエージェントに設定
        message = sample_agent_message
        message.recipient = "non_existent_agent"
        
        # メッセージを送信
        result = dispatcher.send_message(message)
        
        assert result is False
    
    def test_process_message_with_handler(self, clean_message_dispatcher, sample_agent_message):
        """ハンドラーが存在する場合にメッセージが処理されることを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # ハンドラーを登録
        handler = MagicMock()
        dispatcher.register_handler("test_recipient", "test_message", handler)
        
        # メッセージの受信先とタイプを設定
        message = sample_agent_message
        message.recipient = "test_recipient"
        message.message_type = "test_message"
        
        # メッセージを送信
        dispatcher.send_message(message)
        
        # ハンドラーが呼び出されたことを確認
        handler.assert_called_once_with(message)
    
    def test_process_message_without_handler(self, clean_message_dispatcher, sample_agent_message):
        """ハンドラーが存在しない場合にエラーが発生しないことを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # メッセージの受信先とタイプを設定
        message = sample_agent_message
        message.recipient = "test_recipient"
        message.message_type = "unknown_message_type"
        
        # メッセージを送信（例外が発生しないことを確認）
        dispatcher.send_message(message)
    
    def test_get_messages(self, clean_message_dispatcher, sample_agent_message):
        """エージェントのメッセージキューからメッセージを取得できることを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # メッセージの受信先を設定
        message1 = sample_agent_message
        message1.recipient = "test_recipient"
        message1.message_type = "type1"
        
        message2 = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="type2",
            content={"key": "value2"}
        )
        
        # メッセージを送信
        dispatcher.send_message(message1)
        dispatcher.send_message(message2)
        
        # 全てのメッセージを取得
        all_messages = dispatcher.get_messages("test_recipient")
        assert len(all_messages) == 2
        
        # タイプによるフィルタリング
        type1_messages = dispatcher.get_messages("test_recipient", "type1")
        assert len(type1_messages) == 1
        assert type1_messages[0].message_type == "type1"
        
        type2_messages = dispatcher.get_messages("test_recipient", "type2")
        assert len(type2_messages) == 1
        assert type2_messages[0].message_type == "type2"
    
    def test_get_task_status(self, clean_message_dispatcher):
        """タスクIDからタスクの状態を取得できることを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # タスク応答メッセージを作成して送信
        task_response = TaskResponse(
            sender="test_sender",
            recipient="test_recipient",
            request_id="test_task_id",
            status=TaskStatus.COMPLETED
        )
        dispatcher.send_message(task_response)
        
        # タスク状態を取得
        status = dispatcher.get_task_status("test_task_id")
        
        assert status == TaskStatus.COMPLETED.value
    
    def test_get_task_status_from_status_update(self, clean_message_dispatcher):
        """StatusUpdateメッセージからタスクの状態を取得できることを確認"""
        dispatcher = clean_message_dispatcher
        
        # エージェントを登録
        dispatcher.register_agent("test_recipient")
        
        # ステータス更新メッセージを作成して送信
        status_update = StatusUpdate(
            sender="test_sender",
            recipient="test_recipient",
            request_id="test_task_id",
            status=TaskStatus.IN_PROGRESS
        )
        dispatcher.send_message(status_update)
        
        # タスク状態を取得
        status = dispatcher.get_task_status("test_task_id")
        
        assert status == TaskStatus.IN_PROGRESS.value
    
    def test_get_task_status_not_found(self, clean_message_dispatcher):
        """存在しないタスクIDに対してNoneが返されることを確認"""
        dispatcher = clean_message_dispatcher
        
        # 存在しないタスクIDでタスク状態を取得
        status = dispatcher.get_task_status("non_existent_task_id")
        
        assert status is None


class TestHelperFunctions:
    """ヘルパー関数のテスト"""
    
    def test_create_task_request(self):
        """create_task_request関数が正しくTaskRequestオブジェクトを作成することを確認"""
        task_request = create_task_request(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            task_type=TaskType.ARCHITECTURE_DESIGN,
            description="テスト用のアーキテクチャ設計タスク",
            priority=TaskPriority.MEDIUM,
            deadline="2023-12-31T23:59:59",
            context={"project": "test_project"},
            attachments=["file1.txt", "file2.txt"]
        )
        
        assert isinstance(task_request, TaskRequest)
        assert task_request.sender == CoreAgents.ENGINEER
        assert task_request.recipient == SpecialistAgents.AI_ARCHITECT
        assert task_request.content["task_type"] == TaskType.ARCHITECTURE_DESIGN.value
        assert task_request.content["description"] == "テスト用のアーキテクチャ設計タスク"
    
    def test_create_task_response(self):
        """create_task_response関数が正しくTaskResponseオブジェクトを作成することを確認"""
        task_response = create_task_response(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            status=TaskStatus.COMPLETED,
            result={"recommendation": "テスト用のアーキテクチャ推奨事項"},
            message="タスクが完了しました",
            attachments=["result1.txt", "result2.txt"]
        )
        
        assert isinstance(task_response, TaskResponse)
        assert task_response.sender == SpecialistAgents.AI_ARCHITECT
        assert task_response.recipient == CoreAgents.ENGINEER
        assert task_response.reference_id == "test_request_id"
        assert task_response.content["status"] == TaskStatus.COMPLETED.value
    
    @patch("utils.agent_communication.dispatcher.send_message")
    def test_send_task_request(self, mock_send_message):
        """send_task_request関数が正しくタスク依頼を送信することを確認"""
        # モックの設定
        mock_send_message.return_value = True
        
        # 関数を呼び出し
        request_id = send_task_request(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            task_type=TaskType.ARCHITECTURE_DESIGN,
            description="テスト用のアーキテクチャ設計タスク",
            priority=TaskPriority.MEDIUM,
            deadline="2023-12-31T23:59:59",
            context={"project": "test_project"},
            attachments=["file1.txt", "file2.txt"]
        )
        
        # 結果を確認
        assert request_id is not None
        assert isinstance(request_id, str)
        assert mock_send_message.called
    
    @patch("utils.agent_communication.dispatcher.send_message")
    def test_send_task_response(self, mock_send_message):
        """send_task_response関数が正しくタスク応答を送信することを確認"""
        # モックの設定
        mock_send_message.return_value = True
        
        # 関数を呼び出し
        send_task_response(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            status=TaskStatus.COMPLETED,
            result={"recommendation": "テスト用のアーキテクチャ推奨事項"},
            message="タスクが完了しました",
            attachments=["result1.txt", "result2.txt"]
        )
        
        # 結果を確認
        assert mock_send_message.called
    
    @patch("utils.agent_communication.dispatcher.send_message")
    def test_update_task_status(self, mock_send_message):
        """update_task_status関数が正しくタスク状態を更新することを確認"""
        # モックの設定
        mock_send_message.return_value = True
        
        # 関数を呼び出し
        update_task_status(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.PM,
            request_id="test_request_id",
            status=TaskStatus.IN_PROGRESS,
            progress=0.5,
            message="50%完了しました"
        )
        
        # 結果を確認
        assert mock_send_message.called
    
    @patch("utils.agent_communication.dispatcher.send_message")
    def test_request_information(self, mock_send_message):
        """request_information関数が正しく情報要求を送信することを確認"""
        # モックの設定
        mock_send_message.return_value = True
        
        # 関数を呼び出し
        request_id = request_information(
            sender=SpecialistAgents.AI_ARCHITECT,
            recipient=CoreAgents.ENGINEER,
            request_id="test_request_id",
            questions=["質問1", "質問2"],
            context={"background": "テスト背景情報"}
        )
        
        # 結果を確認
        assert request_id is not None
        assert isinstance(request_id, str)
        assert mock_send_message.called
    
    @patch("utils.agent_communication.dispatcher.send_message")
    def test_respond_to_information(self, mock_send_message):
        """respond_to_information関数が正しく情報応答を送信することを確認"""
        # モックの設定
        mock_send_message.return_value = True
        
        # 関数を呼び出し
        respond_to_information(
            sender=CoreAgents.ENGINEER,
            recipient=SpecialistAgents.AI_ARCHITECT,
            request_id="test_request_id",
            answers={"質問1": "回答1", "質問2": "回答2"},
            attachments=["info1.txt", "info2.txt"]
        )
        
        # 結果を確認
        assert mock_send_message.called
    
    @patch("utils.agent_communication.dispatcher.get_task_status")
    def test_get_task_status(self, mock_get_task_status):
        """get_task_status関数が正しくタスク状態を取得することを確認"""
        # モックの設定
        mock_get_task_status.return_value = TaskStatus.COMPLETED.value
        
        # 関数を呼び出し
        status = get_task_status("test_request_id")
        
        # 結果を確認
        assert status == TaskStatus.COMPLETED.value
        mock_get_task_status.assert_called_once_with("test_request_id") 