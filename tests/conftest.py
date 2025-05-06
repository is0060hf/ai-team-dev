"""
テスト用の共通フィクスチャとヘルパー関数を提供するモジュール。
pytest実行時に自動的に読み込まれます。
"""

import os
import json
import datetime
import tempfile
import shutil
import pytest
from typing import Dict, List, Any, Callable
from unittest.mock import MagicMock, patch
import uuid

# テスト対象モジュールをインポート
from utils.agent_communication import (
    AgentMessage, TaskRequest, TaskResponse, InfoRequest, InfoResponse,
    StatusUpdate, MessageDispatcher, TaskPriority, TaskStatus, TaskType
)
from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, SpecialistTaskRegistry,
    SpecialistWorkflowAutomation
)
from utils.specialist_triggers import (
    SpecialistTriggerPatterns, SpecialistTriggerAnalyzer
)


# =====================
# 基本フィクスチャ
# =====================

@pytest.fixture
def temp_storage_dir():
    """一時的なストレージディレクトリを提供するフィクスチャ"""
    # テンポラリディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # テスト後にディレクトリを削除
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_timestamp():
    """テスト用のタイムスタンプを提供するフィクスチャ"""
    return datetime.datetime.now().isoformat()


# =====================
# エージェント通信フィクスチャ
# =====================

@pytest.fixture
def sample_agent_message():
    """サンプルのエージェントメッセージを提供するフィクスチャ"""
    return AgentMessage(
        sender="test_sender",
        recipient="test_recipient",
        message_type="test_message",
        content={"key": "value"},
        request_id="test_request_id",
        reference_id="test_reference_id"
    )


@pytest.fixture
def sample_task_request():
    """サンプルのタスク依頼メッセージを提供するフィクスチャ"""
    return TaskRequest(
        sender=CoreAgents.ENGINEER,
        recipient=SpecialistAgents.AI_ARCHITECT,
        task_type=TaskType.ARCHITECTURE_DESIGN,
        description="テスト用のアーキテクチャ設計タスク",
        priority=TaskPriority.MEDIUM,
        deadline=None,
        context={"project": "test_project"},
        attachments=None
    )


@pytest.fixture
def sample_task_response():
    """サンプルのタスク応答メッセージを提供するフィクスチャ"""
    return TaskResponse(
        sender=SpecialistAgents.AI_ARCHITECT,
        recipient=CoreAgents.ENGINEER,
        request_id="test_request_id",
        status=TaskStatus.COMPLETED,
        result={"recommendation": "テスト用のアーキテクチャ推奨事項"},
        message="タスクが完了しました",
        attachments=None
    )


@pytest.fixture
def clean_message_dispatcher():
    """クリーンなメッセージディスパッチャーを提供するフィクスチャ"""
    # 既存のシングルトンインスタンスをバックアップ
    original_instance = MessageDispatcher._instance
    
    # シングルトンインスタンスをリセット
    MessageDispatcher._instance = None
    
    # 新しいインスタンスを取得
    dispatcher = MessageDispatcher()
    
    yield dispatcher
    
    # テスト後に元のインスタンスを復元
    MessageDispatcher._instance = original_instance


# =====================
# ワークフロー自動化フィクスチャ
# =====================

@pytest.fixture
def clean_task_registry():
    """クリーンなタスクレジストリを提供するフィクスチャ"""
    # 既存のシングルトンインスタンスをバックアップ
    original_instance = SpecialistTaskRegistry._instance
    
    # シングルトンインスタンスをリセット
    SpecialistTaskRegistry._instance = None
    
    # 新しいインスタンスを取得
    registry = SpecialistTaskRegistry()
    
    yield registry
    
    # テスト後に元のインスタンスを復元
    SpecialistTaskRegistry._instance = original_instance


@pytest.fixture
def sample_task_info(sample_timestamp):
    """サンプルのタスク情報を提供するフィクスチャ"""
    return {
        "task_id": "test_task_id",
        "sender": CoreAgents.ENGINEER,
        "recipient": SpecialistAgents.AI_ARCHITECT,
        "task_type": TaskType.ARCHITECTURE_DESIGN.value,
        "description": "テスト用のアーキテクチャ設計タスク",
        "priority": TaskPriority.MEDIUM.value,
        "deadline": None,
        "context": {"project": "test_project"},
        "status": TaskStatus.PENDING.value,
        "created_at": sample_timestamp,
        "updated_at": sample_timestamp,
        "approved_by_pm": False
    }


@pytest.fixture
def populated_task_registry(clean_task_registry, sample_task_info):
    """サンプルタスクが登録されたタスクレジストリを提供するフィクスチャ"""
    registry = clean_task_registry
    
    # サンプルタスク情報から登録
    registry.register_task(
        task_id=sample_task_info["task_id"],
        sender=sample_task_info["sender"],
        recipient=sample_task_info["recipient"],
        task_type=sample_task_info["task_type"],
        description=sample_task_info["description"],
        priority=sample_task_info["priority"],
        deadline=sample_task_info["deadline"],
        context=sample_task_info["context"]
    )
    
    return registry


@pytest.fixture
def mock_workflow_automation():
    """モック化されたワークフロー自動化オブジェクトを提供するフィクスチャ"""
    with patch('utils.workflow_automation.SpecialistWorkflowAutomation') as mock_class:
        mock_instance = mock_class.return_value
        
        # 共通的なメソッドをモック化
        mock_instance.request_specialist_task.return_value = "test_task_id"
        mock_instance.is_specialist_needed.return_value = (True, SpecialistAgents.AI_ARCHITECT)
        mock_instance.get_specialist_dashboard_data.return_value = {
            "timestamp": datetime.datetime.now().isoformat(),
            "active_tasks_count": 1,
            "completed_tasks_count": 0,
            "agents": {
                SpecialistAgents.AI_ARCHITECT: {
                    "active_tasks": [],
                    "completed_tasks": [],
                    "stats": {}
                },
                SpecialistAgents.PROMPT_ENGINEER: {
                    "active_tasks": [],
                    "completed_tasks": [],
                    "stats": {}
                },
                SpecialistAgents.DATA_ENGINEER: {
                    "active_tasks": [],
                    "completed_tasks": [],
                    "stats": {}
                }
            },
            "recent_activities": []
        }
        
        yield mock_instance


# =====================
# トリガー分析フィクスチャ
# =====================

@pytest.fixture
def sample_request_texts():
    """サンプルのリクエストテキストを提供するフィクスチャ"""
    return {
        "ai_architect": "システムアーキテクチャの設計を手伝ってください。スケーラビリティを考慮した設計が必要です。",
        "prompt_engineer": "GPT-4のプロンプト最適化を支援してください。レスポンスの精度を上げたいです。",
        "data_engineer": "データ抽出とクリーニングのパイプラインを作りたいです。CSVからPostgreSQLへのETLが必要です。",
        "generic": "プロジェクトの進捗状況を教えてください。"
    }


@pytest.fixture
def mock_trigger_analyzer():
    """モック化されたトリガー分析オブジェクトを提供するフィクスチャ"""
    with patch('utils.specialist_triggers.SpecialistTriggerAnalyzer') as mock_class:
        mock_instance = mock_class.return_value
        
        # モックの応答を設定
        def mock_analyze_request(request_text, context=None):
            if "アーキテクチャ" in request_text or "設計" in request_text:
                return True, SpecialistAgents.AI_ARCHITECT, 0.8
            elif "プロンプト" in request_text or "GPT" in request_text:
                return True, SpecialistAgents.PROMPT_ENGINEER, 0.7
            elif "データ" in request_text or "ETL" in request_text:
                return True, SpecialistAgents.DATA_ENGINEER, 0.9
            else:
                return False, None, 0.3
        
        mock_instance.analyze_request.side_effect = mock_analyze_request
        
        yield mock_instance


# =====================
# API関連フィクスチャ
# =====================

@pytest.fixture
def sample_api_request_model():
    """サンプルのAPI要求モデルを提供するフィクスチャ"""
    return {
        "core_agent": CoreAgents.ENGINEER,
        "request_text": "テスト用のアーキテクチャ設計タスク",
        "specialist_type": SpecialistAgents.AI_ARCHITECT,
        "priority": TaskPriority.MEDIUM.value,
        "deadline": None,
        "context": {"project": "test_project"},
        "attachments": None
    }


@pytest.fixture
def mock_fastapi_client():
    """モック化されたFastAPIクライアントを提供するフィクスチャ"""
    from fastapi.testclient import TestClient
    from api.specialist_api import app
    
    client = TestClient(app)
    return client


# =====================
# ダッシュボード関連フィクスチャ
# =====================

@pytest.fixture
def sample_dashboard_data():
    """ダッシュボードテスト用サンプルデータ"""
    # 現在時刻をISO形式で取得
    now = datetime.datetime.now().isoformat()
    
    # AI アーキテクトのデータ
    ai_architect_active = [
        {
            "task_id": str(uuid.uuid4()),
            "sender": CoreAgents.ENGINEER,
            "recipient": SpecialistAgents.AI_ARCHITECT,
            "task_type": TaskType.ARCHITECTURE_DESIGN.value,
            "description": "システムアーキテクチャの設計",
            "status": TaskStatus.IN_PROGRESS.value,
            "created_at": now,
            "updated_at": now,
            "progress": 0.5
        }
    ]
    
    ai_architect_completed = [
        {
            "task_id": str(uuid.uuid4()),
            "sender": CoreAgents.PL,
            "recipient": SpecialistAgents.AI_ARCHITECT,
            "task_type": TaskType.TECH_STACK_SELECTION.value,
            "description": "技術スタックの選定",
            "final_status": TaskStatus.COMPLETED.value,
            "created_at": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
            "completed_at": now
        }
    ]
    
    # プロンプトエンジニアのデータ
    prompt_engineer_active = [
        {
            "task_id": str(uuid.uuid4()),
            "sender": CoreAgents.ENGINEER,
            "recipient": SpecialistAgents.PROMPT_ENGINEER,
            "task_type": TaskType.PROMPT_OPTIMIZATION.value,
            "description": "プロンプトの最適化",
            "status": TaskStatus.PENDING.value,
            "created_at": now,
            "updated_at": now
        }
    ]
    
    prompt_engineer_completed = [
        {
            "task_id": str(uuid.uuid4()),
            "sender": CoreAgents.PL,
            "recipient": SpecialistAgents.PROMPT_ENGINEER,
            "task_type": TaskType.PROMPT_DESIGN.value,
            "description": "プロンプトの設計",
            "final_status": TaskStatus.COMPLETED.value,
            "created_at": (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(),
            "completed_at": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        }
    ]
    
    # データエンジニアのデータ
    data_engineer_active = []
    
    data_engineer_completed = [
        {
            "task_id": str(uuid.uuid4()),
            "sender": CoreAgents.PL,
            "recipient": SpecialistAgents.DATA_ENGINEER,
            "task_type": TaskType.DATA_PIPELINE_DESIGN.value,
            "description": "データパイプラインの設計",
            "final_status": TaskStatus.COMPLETED.value,
            "created_at": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat(),
            "completed_at": (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat()
        }
    ]
    
    # 最近のアクティビティ
    recent_activities = [
        {
            "event_type": "status_update",
            "task_id": ai_architect_active[0]["task_id"],
            "sender": SpecialistAgents.AI_ARCHITECT,
            "recipient": ai_architect_active[0]["sender"],
            "status": TaskStatus.IN_PROGRESS.value,
            "updated_at": now
        },
        {
            "event_type": "task_approval",
            "task_id": prompt_engineer_active[0]["task_id"],
            "approver": CoreAgents.PM,
            "updated_at": now
        }
    ]
    
    # ダッシュボードデータ
    dashboard_data = {
        "timestamp": now,
        "active_tasks_count": len(ai_architect_active) + len(prompt_engineer_active) + len(data_engineer_active),
        "completed_tasks_count": len(ai_architect_completed) + len(prompt_engineer_completed) + len(data_engineer_completed),
        "agents": {
            SpecialistAgents.AI_ARCHITECT: {
                "active_tasks": ai_architect_active,
                "completed_tasks": ai_architect_completed,
                "stats": {
                    "active_count": len(ai_architect_active),
                    "completed_count": len(ai_architect_completed),
                    "success_rate": 1.0,
                    "status_distribution": {TaskStatus.IN_PROGRESS.value: 1},
                    "avg_response_time_minutes": 60.0
                }
            },
            SpecialistAgents.PROMPT_ENGINEER: {
                "active_tasks": prompt_engineer_active,
                "completed_tasks": prompt_engineer_completed,
                "stats": {
                    "active_count": len(prompt_engineer_active),
                    "completed_count": len(prompt_engineer_completed),
                    "success_rate": 1.0,
                    "status_distribution": {TaskStatus.PENDING.value: 1},
                    "avg_response_time_minutes": 120.0
                }
            },
            SpecialistAgents.DATA_ENGINEER: {
                "active_tasks": data_engineer_active,
                "completed_tasks": data_engineer_completed,
                "stats": {
                    "active_count": len(data_engineer_active),
                    "completed_count": len(data_engineer_completed),
                    "success_rate": 1.0,
                    "status_distribution": {},
                    "avg_response_time_minutes": 180.0
                }
            }
        },
        "recent_activities": recent_activities
    }
    
    return dashboard_data


@pytest.fixture
def mock_api_requests():
    """APIリクエストをモック化するフィクスチャ"""
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        yield mock_get, mock_post 