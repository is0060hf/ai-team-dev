"""
専門エージェントとのタスク依頼や結果共有のためのAPIエンドポイント。
UIからの要求を受け付け、専門エージェントとの連携を行います。
"""

from fastapi import FastAPI, HTTPException, Depends, Request, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import uuid
import datetime
import os

from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, TaskType, TaskPriority, TaskStatus,
    task_registry, get_dashboard_data
)
from utils.specialist_triggers import request_specialist_if_needed, analyze_specialist_need

app = FastAPI(
    title="専門エージェントAPI",
    description="専門エージェント（AIアーキテクト、プロンプトエンジニア、データエンジニア）との連携APIです。",
    version="1.0.0"
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では特定のオリジンに制限すべき
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# リクエストモデル
class SpecialistRequestModel(BaseModel):
    """専門エージェントへのリクエストモデル"""
    core_agent: str = Field(..., description="依頼元コアエージェント")
    request_text: str = Field(..., description="依頼内容テキスト")
    specialist_type: Optional[str] = Field(None, description="専門エージェントタイプ（指定がない場合は自動判断）")
    priority: Optional[str] = Field(None, description="優先度")
    deadline: Optional[str] = Field(None, description="期限（ISO 8601形式）")
    context: Optional[Dict[str, Any]] = Field(None, description="コンテキスト情報")
    attachments: Optional[List[str]] = Field(None, description="添付ファイルパスのリスト")


class TaskStatusUpdateModel(BaseModel):
    """タスクステータス更新モデル"""
    task_id: str = Field(..., description="タスクID")
    status: str = Field(..., description="新しいステータス")
    message: Optional[str] = Field(None, description="メッセージ")
    progress: Optional[float] = Field(None, description="進捗率（0.0-1.0）")


class TaskApprovalModel(BaseModel):
    """タスク承認モデル"""
    task_id: str = Field(..., description="タスクID")
    approved: bool = Field(..., description="承認するかどうか")
    approver: str = Field(CoreAgents.PM, description="承認者（デフォルト：PM）")
    message: Optional[str] = Field(None, description="メッセージ")
    rejection_reason: Optional[str] = Field(None, description="拒否理由（拒否の場合）")


class AnalyzeRequestModel(BaseModel):
    """要求分析モデル"""
    request_text: str = Field(..., description="分析対象テキスト")
    context: Optional[Dict[str, Any]] = Field(None, description="コンテキスト情報")


# レスポンスモデル
class SpecialistResponseModel(BaseModel):
    """専門エージェントからのレスポンスモデル"""
    task_id: str = Field(..., description="タスクID")
    specialist: str = Field(..., description="担当専門エージェント")
    status: str = Field(..., description="タスク状態")
    created_at: str = Field(..., description="タスク作成日時")
    message: str = Field(..., description="メッセージ")


class AnalysisResultModel(BaseModel):
    """要求分析結果モデル"""
    needed: bool = Field(..., description="専門エージェントが必要かどうか")
    specialist: Optional[str] = Field(None, description="必要な専門エージェント")
    confidence: float = Field(..., description="信頼度")
    analysis_detail: Dict[str, Any] = Field(..., description="詳細分析結果")


class TaskInfoModel(BaseModel):
    """タスク情報モデル"""
    task_id: str = Field(..., description="タスクID")
    sender: str = Field(..., description="送信元エージェント")
    recipient: str = Field(..., description="受信先エージェント")
    task_type: str = Field(..., description="タスク種別")
    description: str = Field(..., description="タスク詳細")
    status: str = Field(..., description="タスク状態")
    priority: str = Field(..., description="優先度")
    created_at: str = Field(..., description="作成日時")
    updated_at: str = Field(..., description="更新日時")
    deadline: Optional[str] = Field(None, description="期限")
    approved_by_pm: bool = Field(False, description="PM承認済み")
    context: Dict[str, Any] = Field({}, description="コンテキスト情報")
    result: Optional[Dict[str, Any]] = Field(None, description="タスク結果")
    progress: Optional[float] = Field(None, description="進捗率")
    attachments: Optional[List[str]] = Field(None, description="添付ファイル")


class DashboardDataModel(BaseModel):
    """ダッシュボードデータモデル"""
    timestamp: str = Field(..., description="データの取得時刻")
    active_tasks_count: int = Field(..., description="アクティブなタスク数")
    completed_tasks_count: int = Field(..., description="完了したタスク数")
    agents: Dict[str, Any] = Field(..., description="エージェントごとのデータ")
    recent_activities: List[Dict[str, Any]] = Field(..., description="最近のアクティビティ")


# エンドポイント
@app.post("/specialist/request", response_model=SpecialistResponseModel)
async def request_specialist(request: SpecialistRequestModel):
    """
    専門エージェントにタスクを依頼します。
    専門エージェントタイプが指定されていない場合は要求内容から自動判断します。
    """
    try:
        # コンテキスト情報の準備
        context = request.context or {}
        if request.specialist_type:
            context["specialist_type"] = request.specialist_type
        
        # 専門エージェントにタスクを依頼
        task_id = request_specialist_if_needed(
            core_agent=request.core_agent,
            request_text=request.request_text,
            context=context,
            force_type=request.specialist_type,
            priority=request.priority
        )
        
        if not task_id:
            raise HTTPException(
                status_code=400,
                detail="専門エージェントは不要と判断されました。要求内容を見直すか、専門エージェントタイプを明示的に指定してください。"
            )
        
        # タスク情報を取得
        task_info = task_registry.get_task_info(task_id)
        if not task_info:
            raise HTTPException(
                status_code=500,
                detail="タスク情報の取得に失敗しました。"
            )
        
        return SpecialistResponseModel(
            task_id=task_id,
            specialist=task_info["recipient"],
            status=task_info["status"],
            created_at=task_info["created_at"],
            message="専門エージェントにタスクを依頼しました。PMによる承認後に処理が開始されます。"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"エラーが発生しました: {str(e)}"
        )


@app.post("/specialist/analyze", response_model=AnalysisResultModel)
async def analyze_request(request: AnalyzeRequestModel):
    """
    要求テキストを分析し、専門エージェントが必要かどうかを判断します。
    """
    try:
        # 要求分析
        needed, specialist, confidence = analyze_specialist_need(
            request_text=request.request_text,
            context=request.context
        )
        
        # 分析詳細
        analysis_detail = {
            "request_text": request.request_text,
            "context": request.context,
            "result": {
                "needed": needed,
                "specialist": specialist,
                "confidence": confidence
            }
        }
        
        return AnalysisResultModel(
            needed=needed,
            specialist=specialist,
            confidence=confidence,
            analysis_detail=analysis_detail
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"分析中にエラーが発生しました: {str(e)}"
        )


@app.get("/specialist/tasks", response_model=List[TaskInfoModel])
async def get_tasks(specialist: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    """
    専門エージェントタスクのリストを取得します。
    """
    try:
        # アクティブタスクの取得
        active_tasks = task_registry.get_active_tasks(specialist)
        
        # 完了タスクの取得
        completed_tasks = task_registry.get_completed_tasks(specialist)
        
        # 全タスクの統合
        all_tasks = active_tasks + completed_tasks
        
        # ステータスによるフィルタリング
        if status:
            all_tasks = [task for task in all_tasks if task.get("status") == status]
        
        # 作成日時順にソート
        all_tasks = sorted(all_tasks, key=lambda x: x.get("created_at", ""), reverse=True)
        
        # 上限数に制限
        all_tasks = all_tasks[:limit]
        
        # TaskInfoModelのリストに変換
        result = []
        for task in all_tasks:
            task_info = TaskInfoModel(
                task_id=task.get("task_id", ""),
                sender=task.get("sender", ""),
                recipient=task.get("recipient", ""),
                task_type=task.get("task_type", ""),
                description=task.get("description", ""),
                status=task.get("status", ""),
                priority=task.get("priority", ""),
                created_at=task.get("created_at", ""),
                updated_at=task.get("updated_at", ""),
                deadline=task.get("deadline"),
                approved_by_pm=task.get("approved_by_pm", False),
                context=task.get("context", {}),
                result=task.get("result"),
                progress=task.get("progress"),
                attachments=task.get("attachments")
            )
            result.append(task_info)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク取得中にエラーが発生しました: {str(e)}"
        )


@app.get("/specialist/task/{task_id}", response_model=TaskInfoModel)
async def get_task(task_id: str):
    """
    特定のタスク情報を取得します。
    """
    try:
        task_info = task_registry.get_task_info(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"タスクID {task_id} が見つかりません。"
            )
        
        return TaskInfoModel(
            task_id=task_info.get("task_id", ""),
            sender=task_info.get("sender", ""),
            recipient=task_info.get("recipient", ""),
            task_type=task_info.get("task_type", ""),
            description=task_info.get("description", ""),
            status=task_info.get("status", ""),
            priority=task_info.get("priority", ""),
            created_at=task_info.get("created_at", ""),
            updated_at=task_info.get("updated_at", ""),
            deadline=task_info.get("deadline"),
            approved_by_pm=task_info.get("approved_by_pm", False),
            context=task_info.get("context", {}),
            result=task_info.get("result"),
            progress=task_info.get("progress"),
            attachments=task_info.get("attachments")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク情報取得中にエラーが発生しました: {str(e)}"
        )


@app.post("/specialist/task/{task_id}/update", response_model=TaskInfoModel)
async def update_task_status(task_id: str, update: TaskStatusUpdateModel):
    """
    タスクのステータスを更新します。
    """
    try:
        task_info = task_registry.get_task_info(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"タスクID {task_id} が見つかりません。"
            )
        
        # タスク状態を更新
        task_registry.update_task_status(task_id, update.status, update.progress)
        
        # 更新後のタスク情報を取得
        updated_task_info = task_registry.get_task_info(task_id)
        
        return TaskInfoModel(
            task_id=updated_task_info.get("task_id", ""),
            sender=updated_task_info.get("sender", ""),
            recipient=updated_task_info.get("recipient", ""),
            task_type=updated_task_info.get("task_type", ""),
            description=updated_task_info.get("description", ""),
            status=updated_task_info.get("status", ""),
            priority=updated_task_info.get("priority", ""),
            created_at=updated_task_info.get("created_at", ""),
            updated_at=updated_task_info.get("updated_at", ""),
            deadline=updated_task_info.get("deadline"),
            approved_by_pm=updated_task_info.get("approved_by_pm", False),
            context=updated_task_info.get("context", {}),
            result=updated_task_info.get("result"),
            progress=updated_task_info.get("progress"),
            attachments=updated_task_info.get("attachments")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク状態更新中にエラーが発生しました: {str(e)}"
        )


@app.post("/specialist/task/{task_id}/approve", response_model=TaskInfoModel)
async def approve_task(task_id: str, approval: TaskApprovalModel):
    """
    PMがタスクを承認または拒否します。
    """
    try:
        task_info = task_registry.get_task_info(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"タスクID {task_id} が見つかりません。"
            )
        
        # 承認または拒否
        if approval.approved:
            task_registry.approve_task(task_id, approval.approver)
        else:
            if not approval.rejection_reason:
                raise HTTPException(
                    status_code=400,
                    detail="タスクを拒否する場合は拒否理由を指定してください。"
                )
            task_registry.reject_task(task_id, approval.rejection_reason, approval.approver)
        
        # 更新後のタスク情報を取得
        updated_task_info = task_registry.get_task_info(task_id)
        
        return TaskInfoModel(
            task_id=updated_task_info.get("task_id", ""),
            sender=updated_task_info.get("sender", ""),
            recipient=updated_task_info.get("recipient", ""),
            task_type=updated_task_info.get("task_type", ""),
            description=updated_task_info.get("description", ""),
            status=updated_task_info.get("status", ""),
            priority=updated_task_info.get("priority", ""),
            created_at=updated_task_info.get("created_at", ""),
            updated_at=updated_task_info.get("updated_at", ""),
            deadline=updated_task_info.get("deadline"),
            approved_by_pm=updated_task_info.get("approved_by_pm", False),
            context=updated_task_info.get("context", {}),
            result=updated_task_info.get("result"),
            progress=updated_task_info.get("progress"),
            attachments=updated_task_info.get("attachments")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク承認中にエラーが発生しました: {str(e)}"
        )


@app.get("/specialist/dashboard", response_model=DashboardDataModel)
async def get_dashboard():
    """
    専門エージェントのダッシュボードデータを取得します。
    """
    try:
        dashboard_data = get_dashboard_data()
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ダッシュボードデータ取得中にエラーが発生しました: {str(e)}"
        )


@app.post("/specialist/save")
async def save_tasks():
    """
    タスク情報をファイルに保存します。
    """
    try:
        task_registry.save_to_file()
        return {"message": "タスク情報を保存しました。"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク情報保存中にエラーが発生しました: {str(e)}"
        )


@app.post("/specialist/load")
async def load_tasks():
    """
    ファイルからタスク情報を読み込みます。
    """
    try:
        success = task_registry.load_from_file()
        if success:
            return {"message": "タスク情報を読み込みました。"}
        else:
            return {"message": "タスク情報の読み込みに失敗しました。"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"タスク情報読み込み中にエラーが発生しました: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 