"""
HITL（Human-in-the-loop）インターフェースのUI提供用ルーター。
プロダクトオーナー向けの要求入力UI、開発者向けの監視・介入UI、PMと
プロダクトオーナー間の承認フローを実装します。
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import json
import datetime

from api.auth import User, get_current_active_user, has_role, Roles
from utils.workflow_automation import task_registry
from utils.error_recovery import get_task_error_history


# テンプレートディレクトリの設定
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
templates = Jinja2Templates(directory=templates_dir)

# ルーターの設定
router = APIRouter(
    prefix="/hitl-ui",
    tags=["HITL UI"],
    responses={401: {"description": "認証エラー"}},
)


# モデル定義
class RequirementInputModel(BaseModel):
    """要求入力モデル"""
    title: str
    description: str
    priority: str
    deadline: Optional[str] = None
    tags: List[str] = []
    attachments: List[str] = []


class InterventionRequestModel(BaseModel):
    """開発者介入リクエストモデル"""
    task_id: str
    action: str
    comment: str
    details: Optional[Dict[str, Any]] = None


# ビュー関数
@router.get("/", response_class=HTMLResponse)
async def hitl_dashboard(request: Request, current_user: User = Depends(get_current_active_user)):
    """HITLダッシュボードを表示"""
    return templates.TemplateResponse(
        "hitl_dashboard.html",
        {
            "request": request,
            "user": current_user,
            "title": "HITL ダッシュボード",
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.get("/product-owner", response_class=HTMLResponse)
async def product_owner_ui(request: Request, current_user: User = Depends(has_role([Roles.PRODUCT_OWNER, Roles.ADMIN]))):
    """プロダクトオーナー向けのUIを表示"""
    # 最近のタスク
    recent_tasks = task_registry.get_recent_tasks(10)
    
    return templates.TemplateResponse(
        "product_owner.html",
        {
            "request": request,
            "user": current_user,
            "title": "プロダクトオーナーインターフェース",
            "recent_tasks": recent_tasks,
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.get("/developer", response_class=HTMLResponse)
async def developer_ui(request: Request, current_user: User = Depends(has_role([Roles.DEVELOPER, Roles.ADMIN]))):
    """開発者向けのUIを表示"""
    # アクティブなタスク
    active_tasks = task_registry.get_active_tasks()
    
    # エラー履歴
    error_history = get_task_error_history()
    
    return templates.TemplateResponse(
        "developer.html",
        {
            "request": request,
            "user": current_user,
            "title": "開発者モニタリングインターフェース",
            "active_tasks": active_tasks,
            "error_history": error_history,
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.get("/approval-flow", response_class=HTMLResponse)
async def approval_flow_ui(request: Request, current_user: User = Depends(has_role([Roles.PM, Roles.PRODUCT_OWNER, Roles.ADMIN]))):
    """承認フロー向けのUIを表示"""
    # 承認待ちのタスク
    pending_approvals = [
        task for task in task_registry.get_active_tasks() 
        if not task.get("approved_by_pm", False) and not task.get("rejected_by_pm", False)
    ]
    
    # 最近承認されたタスク
    recent_approved = [
        task for task in task_registry.get_recent_tasks(20)
        if task.get("approved_by_pm", False)
    ]
    
    return templates.TemplateResponse(
        "approval_flow.html",
        {
            "request": request,
            "user": current_user,
            "title": "承認フローインターフェース",
            "pending_approvals": pending_approvals,
            "recent_approved": recent_approved,
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail_ui(task_id: str, request: Request, current_user: User = Depends(get_current_active_user)):
    """タスク詳細画面を表示"""
    # タスク情報を取得
    task_info = task_registry.get_task_info(task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {task_id} が見つかりません。"
        )
    
    # このタスクのエラー履歴を取得
    error_history = get_task_error_history(task_id)
    
    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "user": current_user,
            "title": f"タスク詳細: {task_id}",
            "task": task_info,
            "error_history": error_history.get(task_id, []),
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.post("/submit-requirement")
async def submit_requirement(requirement: RequirementInputModel, current_user: User = Depends(has_role([Roles.PRODUCT_OWNER, Roles.ADMIN]))):
    """プロダクトオーナーからの要求を提出"""
    # 要求をPdMエージェントに送信するためのタスクを作成
    task_data = {
        "title": requirement.title,
        "description": requirement.description,
        "priority": requirement.priority,
        "tags": requirement.tags,
        "attachments": requirement.attachments,
        "submitted_by": current_user.username,
        "submission_time": datetime.datetime.now().isoformat()
    }
    
    if requirement.deadline:
        task_data["deadline"] = requirement.deadline
    
    # PdM向けタスクを登録
    task_id = task_registry.register_task(
        task_type="requirement_analysis",
        sender=current_user.username,
        recipient="PdM",
        description=requirement.description,
        context=task_data
    )
    
    return {
        "status": "success",
        "message": "要求が正常に提出されました",
        "task_id": task_id
    }


@router.post("/developer-intervention")
async def developer_intervention(intervention: InterventionRequestModel, current_user: User = Depends(has_role([Roles.DEVELOPER, Roles.ADMIN]))):
    """開発者による介入を処理"""
    # タスク情報を取得して存在確認
    task_info = task_registry.get_task_info(intervention.task_id)
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"タスクID {intervention.task_id} が見つかりません。"
        )
    
    # 介入アクションに応じた処理
    if intervention.action == "stop":
        # タスクを停止
        task_registry.update_task_status(
            task_id=intervention.task_id,
            status="stopped",
            message=f"開発者 {current_user.username} により停止: {intervention.comment}"
        )
        
        # 介入記録
        task_registry.add_task_history(
            task_id=intervention.task_id,
            event_type="intervention",
            data={
                "action": "stop",
                "by": current_user.username,
                "comment": intervention.comment,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
        
        return {"status": "success", "message": "タスクを停止しました"}
        
    elif intervention.action == "restart":
        # タスクを再開
        task_registry.update_task_status(
            task_id=intervention.task_id,
            status="in_progress",
            message=f"開発者 {current_user.username} により再開: {intervention.comment}"
        )
        
        # 介入記録
        task_registry.add_task_history(
            task_id=intervention.task_id,
            event_type="intervention",
            data={
                "action": "restart",
                "by": current_user.username,
                "comment": intervention.comment,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
        
        return {"status": "success", "message": "タスクを再開しました"}
        
    elif intervention.action == "modify":
        # タスク内容を変更
        if not intervention.details:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="変更内容が指定されていません"
            )
        
        # 変更内容を適用
        task_registry.update_task(
            task_id=intervention.task_id,
            update_data=intervention.details
        )
        
        # 介入記録
        task_registry.add_task_history(
            task_id=intervention.task_id,
            event_type="intervention",
            data={
                "action": "modify",
                "by": current_user.username,
                "comment": intervention.comment,
                "details": intervention.details,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
        
        return {"status": "success", "message": "タスク内容を変更しました"}
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不明なアクション: {intervention.action}"
        )


@router.post("/approve-task/{task_id}")
async def approve_task_ui(task_id: str, comment: str = Form(None), current_user: User = Depends(has_role([Roles.PM, Roles.ADMIN]))):
    """タスク承認処理（UI用）"""
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
        task_registry.add_task_history(
            task_id=task_id,
            event_type="comment",
            data={
                "by": current_user.username,
                "comment": comment,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
    
    # リダイレクト
    response = {
        "status": "success",
        "message": f"タスク {task_id} を承認しました。",
        "redirect": f"/hitl-ui/approval-flow"
    }
    
    return response


@router.post("/reject-task/{task_id}")
async def reject_task_ui(task_id: str, reason: str = Form(...), current_user: User = Depends(has_role([Roles.PM, Roles.ADMIN]))):
    """タスク拒否処理（UI用）"""
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
    
    # リダイレクト
    response = {
        "status": "success",
        "message": f"タスク {task_id} を拒否しました。",
        "redirect": f"/hitl-ui/approval-flow"
    }
    
    return response 