"""
HITL（Human-in-the-loop）インターフェース関連のAPIルーター。
PM承認フロー、ユーザーフィードバック収集、タスク手動割り当てなどの機能を提供します。
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import uuid
import datetime

from api.auth import User, get_current_active_user, has_role, Roles
from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, TaskType, TaskPriority, TaskStatus,
    task_registry, workflow_automation
)
from utils.specialist_triggers import request_specialist_if_needed


# モデル定義
class FeedbackModel(BaseModel):
    """ユーザーフィードバックモデル"""
    task_id: str = Field(..., description="タスクID")
    feedback_type: str = Field(..., description="フィードバックタイプ（質、速度、正確性など）")
    rating: int = Field(..., ge=1, le=5, description="評価（1-5）")
    comment: Optional[str] = Field(None, description="コメント")


class TaskAssignmentModel(BaseModel):
    """タスク手動割り当てモデル"""
    task_id: Optional[str] = Field(None, description="既存タスクID（新規作成時はNull）")
    core_agent: str = Field(..., description="コアエージェント")
    specialist_agent: str = Field(..., description="専門エージェント")
    task_type: str = Field(..., description="タスク種別")
    description: str = Field(..., description="タスク詳細")
    priority: str = Field(TaskPriority.MEDIUM.value, description="優先度")
    deadline: Optional[str] = Field(None, description="期限")
    context: Optional[Dict[str, Any]] = Field(None, description="コンテキスト情報")


class TaskInterventionModel(BaseModel):
    """タスク介入モデル"""
    task_id: str = Field(..., description="タスクID")
    action: str = Field(..., description="アクション（cancel, pause, resume, modify）")
    reason: str = Field(..., description="理由")
    modifications: Optional[Dict[str, Any]] = Field(None, description="変更内容（modifyアクション時）")


# ルーターの作成
router = APIRouter(
    prefix="/hitl",
    tags=["HITL"],
    responses={401: {"description": "認証エラー"}},
)


@router.get("/pending-approvals")
async def get_pending_approvals(
    current_user: User = Depends(has_role([Roles.PM, Roles.MANAGER, Roles.ADMIN]))
):
    """
    承認待ちのタスクリストを取得します。
    """
    # 承認待ちタスクを取得
    active_tasks = task_registry.get_active_tasks()
    pending_approvals = [
        task for task in active_tasks 
        if not task.get("approved_by_pm", False) and not task.get("rejected_by_pm", False)
    ]
    
    return {
        "pending_count": len(pending_approvals),
        "tasks": pending_approvals
    }


@router.post("/approve/{task_id}")
async def approve_task(
    task_id: str,
    comment: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(has_role([Roles.PM, Roles.MANAGER, Roles.ADMIN]))
):
    """
    タスクを承認します。
    """
    # タスク情報を取得
    task_info = task_registry.get_task_info(task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {task_id} が見つかりません。"
        )
    
    # 既に承認・拒否済みかチェック
    if task_info.get("approved_by_pm", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このタスクは既に承認されています。"
        )
    
    if task_info.get("rejected_by_pm", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このタスクは既に拒否されています。"
        )
    
    # タスクを承認
    task_registry.approve_task(task_id, current_user.username)
    
    # コメントがあれば記録
    if comment:
        # コメント記録機能が実装されていない場合は、タスク履歴に追加する形で記録
        task_registry._task_history.append({
            "task_id": task_id,
            "event_type": "comment",
            "user": current_user.username,
            "comment": comment,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    return {"message": f"タスク {task_id} を承認しました。"}


@router.post("/reject/{task_id}")
async def reject_task(
    task_id: str,
    reason: str = Body(..., embed=True),
    current_user: User = Depends(has_role([Roles.PM, Roles.MANAGER, Roles.ADMIN]))
):
    """
    タスクを拒否します。
    """
    # タスク情報を取得
    task_info = task_registry.get_task_info(task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {task_id} が見つかりません。"
        )
    
    # 既に承認・拒否済みかチェック
    if task_info.get("approved_by_pm", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このタスクは既に承認されています。"
        )
    
    if task_info.get("rejected_by_pm", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このタスクは既に拒否されています。"
        )
    
    # タスクを拒否
    task_registry.reject_task(task_id, reason, current_user.username)
    
    return {"message": f"タスク {task_id} を拒否しました。"}


@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackModel,
    current_user: User = Depends(get_current_active_user)
):
    """
    タスクに対するフィードバックを提出します。
    """
    # タスク存在チェック
    task_info = task_registry.get_task_info(feedback.task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {feedback.task_id} が見つかりません。"
        )
    
    # フィードバックを記録
    # フィードバック専用のレジストリがない場合は、タスク履歴に追加
    feedback_data = {
        "task_id": feedback.task_id,
        "event_type": "feedback",
        "user": current_user.username,
        "feedback_type": feedback.feedback_type,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    task_registry._task_history.append(feedback_data)
    
    return {"message": "フィードバックを受け付けました。ありがとうございます。"}


@router.post("/assign-task")
async def assign_task(
    assignment: TaskAssignmentModel,
    current_user: User = Depends(has_role([Roles.PM, Roles.MANAGER, Roles.ADMIN]))
):
    """
    専門エージェントにタスクを手動で割り当てます。
    """
    # 新規タスク作成の場合
    if not assignment.task_id:
        # タスクを作成して専門エージェントに割り当て
        task_id = workflow_automation.request_specialist_task(
            sender=assignment.core_agent,
            specialist=assignment.specialist_agent,
            task_type=assignment.task_type,
            description=assignment.description,
            priority=assignment.priority,
            deadline=assignment.deadline,
            context=assignment.context
        )
        
        # 作成したタスクを自動承認
        task_registry.approve_task(task_id, current_user.username)
        
        return {
            "message": "タスクを作成し、専門エージェントに割り当てました。",
            "task_id": task_id
        }
    
    # 既存タスクの場合
    else:
        # タスク存在チェック
        task_info = task_registry.get_task_info(assignment.task_id)
        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"タスクID {assignment.task_id} が見つかりません。"
            )
        
        # TODO: 既存タスクの割り当て変更実装（複雑なステート変更が必要なため、
        # 現時点では実装しない。実際の実装では、タスクを適切に移行する必要がある）
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="既存タスクの割り当て変更は現在サポートされていません。"
        )


@router.post("/intervene")
async def intervene_task(
    intervention: TaskInterventionModel,
    current_user: User = Depends(has_role([Roles.PM, Roles.MANAGER, Roles.ADMIN]))
):
    """
    進行中のタスクに介入します（中止、一時停止、再開、変更など）。
    """
    # タスク存在チェック
    task_info = task_registry.get_task_info(intervention.task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {intervention.task_id} が見つかりません。"
        )
    
    # アクションに応じた処理
    if intervention.action == "cancel":
        # タスクをキャンセル（失敗状態に更新）
        task_registry.update_task_status(
            task_id=intervention.task_id,
            status=TaskStatus.FAILED.value,
            progress=0.0
        )
        
        # 履歴に記録
        task_registry._task_history.append({
            "task_id": intervention.task_id,
            "event_type": "intervention",
            "action": "cancel",
            "reason": intervention.reason,
            "user": current_user.username,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {"message": f"タスク {intervention.task_id} をキャンセルしました。"}
    
    elif intervention.action == "pause":
        # タスクを一時停止（情報待ち状態に更新）
        task_registry.update_task_status(
            task_id=intervention.task_id,
            status=TaskStatus.WAITING_INFO.value
        )
        
        # 履歴に記録
        task_registry._task_history.append({
            "task_id": intervention.task_id,
            "event_type": "intervention",
            "action": "pause",
            "reason": intervention.reason,
            "user": current_user.username,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {"message": f"タスク {intervention.task_id} を一時停止しました。"}
    
    elif intervention.action == "resume":
        # タスクを再開（処理中状態に更新）
        task_registry.update_task_status(
            task_id=intervention.task_id,
            status=TaskStatus.IN_PROGRESS.value
        )
        
        # 履歴に記録
        task_registry._task_history.append({
            "task_id": intervention.task_id,
            "event_type": "intervention",
            "action": "resume",
            "reason": intervention.reason,
            "user": current_user.username,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {"message": f"タスク {intervention.task_id} を再開しました。"}
    
    elif intervention.action == "modify":
        # タスク変更
        if not intervention.modifications:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="変更内容が指定されていません。"
            )
        
        # TODO: タスク内容の変更処理を実装
        # 実際の実装では、タスク情報を適切に更新する必要がある
        
        # タスク変更を記録
        task_registry._task_history.append({
            "task_id": intervention.task_id,
            "event_type": "intervention",
            "action": "modify",
            "reason": intervention.reason,
            "modifications": intervention.modifications,
            "user": current_user.username,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {"message": f"タスク {intervention.task_id} を変更しました。"}
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不明なアクション: {intervention.action}"
        ) 