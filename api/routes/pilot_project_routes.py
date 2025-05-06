"""
パイロットプロジェクトとプロジェクト反復サイクルのAPIルーター。
プロジェクト管理と反復プロセスに関連するエンドポイントを提供します。
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from utils.logger import get_structured_logger
from utils.pilot_project import PilotProject, pilot_project_manager
from utils.project_iteration import get_iteration_manager, run_iteration_cycle
from utils.project_evaluation import evaluate_project_automatically
from utils.tracing import trace
from utils.access_control import validate_api_key, RoleRequirement

# ロガーの設定
logger = get_structured_logger("pilot_project_routes")

# ルーターの設定
router = APIRouter(
    prefix="/api/v1/pilot-projects",
    tags=["pilot-projects"],
    dependencies=[Depends(validate_api_key)]
)


# リクエストモデル
class ProjectCreate(BaseModel):
    """プロジェクト作成リクエスト"""
    title: str = Field(..., description="プロジェクトのタイトル")
    description: str = Field(..., description="プロジェクトの説明")
    requirements: List[str] = Field(..., description="プロジェクトの要件リスト")


class IterationCreate(BaseModel):
    """反復サイクル作成リクエスト"""
    goals: List[str] = Field(..., description="反復サイクルの目標リスト")
    focus_areas: List[str] = Field(..., description="反復サイクルの注力分野リスト")


class ChangeRecord(BaseModel):
    """変更記録"""
    component: str = Field(..., description="変更されたコンポーネント")
    description: str = Field(..., description="変更の説明")
    reason: str = Field(..., description="変更の理由")
    impact: str = Field(..., description="変更の影響度（high, medium, low）")


class LessonLearned(BaseModel):
    """学習した教訓"""
    category: str = Field(..., description="教訓のカテゴリ")
    description: str = Field(..., description="教訓の説明")
    application: str = Field(..., description="教訓の適用方法")


# レスポンスモデル
class ProjectSummary(BaseModel):
    """プロジェクト概要"""
    project_id: str
    title: str
    description: str
    status: str
    requirements_count: int
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    artifacts: Dict[str, int]
    evaluation_metrics: Dict[str, Any]


class IterationSummary(BaseModel):
    """反復サイクル概要"""
    iteration_number: int
    status: str
    goals: List[str]
    focus_areas: List[str]
    start_time: Optional[str]
    end_time: Optional[str]
    changes_count: int
    lessons_learned_count: int


# エンドポイント: プロジェクト管理
@router.post("", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager"]))])
@trace("create_pilot_project")
async def create_pilot_project(project_data: ProjectCreate = Body(...)):
    """新しいパイロットプロジェクトを作成"""
    try:
        project = pilot_project_manager.create_project(
            title=project_data.title,
            description=project_data.description,
            requirements=project_data.requirements
        )
        
        logger.info(f"新しいパイロットプロジェクトを作成しました: {project.project_id}")
        
        return {
            "status": "success",
            "message": "パイロットプロジェクトを作成しました",
            "project_id": project.project_id
        }
    
    except Exception as e:
        logger.error(f"パイロットプロジェクト作成中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクト作成に失敗しました: {str(e)}")


@router.get("", response_model=List[Dict[str, Any]])
@trace("list_pilot_projects")
async def list_pilot_projects():
    """利用可能なパイロットプロジェクトの一覧を取得"""
    try:
        projects = pilot_project_manager.list_projects()
        return projects
    
    except Exception as e:
        logger.error(f"プロジェクト一覧取得中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクト一覧の取得に失敗しました: {str(e)}")


@router.get("/{project_id}", response_model=ProjectSummary)
@trace("get_pilot_project")
async def get_pilot_project(project_id: str = Path(..., description="プロジェクトID")):
    """指定されたIDのパイロットプロジェクトを取得"""
    try:
        project = pilot_project_manager.get_project(project_id)
        summary = project.get_summary()
        return summary
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の取得中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクトの取得に失敗しました: {str(e)}")


@router.post("/{project_id}/start", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager"]))])
@trace("start_pilot_project")
async def start_pilot_project(project_id: str = Path(..., description="プロジェクトID")):
    """パイロットプロジェクトを開始"""
    try:
        project = pilot_project_manager.get_project(project_id)
        project.start_project()
        
        return {
            "status": "success",
            "message": f"プロジェクト {project_id} を開始しました",
            "project_id": project_id,
            "start_time": project.start_time.isoformat() if project.start_time else None
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の開始中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクトの開始に失敗しました: {str(e)}")


@router.post("/{project_id}/complete", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager"]))])
@trace("complete_pilot_project")
async def complete_pilot_project(project_id: str = Path(..., description="プロジェクトID")):
    """パイロットプロジェクトを完了"""
    try:
        project = pilot_project_manager.get_project(project_id)
        project.complete_project()
        
        return {
            "status": "success",
            "message": f"プロジェクト {project_id} を完了しました",
            "project_id": project_id,
            "end_time": project.end_time.isoformat() if project.end_time else None
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の完了中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクトの完了に失敗しました: {str(e)}")


@router.delete("/{project_id}", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin"]))])
@trace("delete_pilot_project")
async def delete_pilot_project(project_id: str = Path(..., description="プロジェクトID")):
    """パイロットプロジェクトを削除"""
    try:
        result = pilot_project_manager.delete_project(project_id)
        
        if result:
            return {
                "status": "success",
                "message": f"プロジェクト {project_id} を削除しました"
            }
        else:
            raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の削除中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクトの削除に失敗しました: {str(e)}")


@router.post("/{project_id}/evaluate", response_model=Dict[str, Any])
@trace("evaluate_pilot_project")
async def evaluate_pilot_project(project_id: str = Path(..., description="プロジェクトID")):
    """パイロットプロジェクトを評価"""
    try:
        project = pilot_project_manager.get_project(project_id)
        
        if project.status != "completed":
            logger.warning(f"完了していないプロジェクト {project_id} の評価を試みました")
        
        # プロジェクトの自動評価を実行
        evaluation_results = evaluate_project_automatically(project)
        
        return {
            "status": "success",
            "message": f"プロジェクト {project_id} の評価が完了しました",
            "project_id": project_id,
            "evaluation_summary": {
                "overall_score": evaluation_results.get("overall_score", 0),
                "category_scores": evaluation_results.get("category_scores", {}),
                "evaluation_date": evaluation_results.get("evaluation_date", datetime.now().isoformat())
            }
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の評価中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロジェクトの評価に失敗しました: {str(e)}")


# エンドポイント: 反復サイクル管理
@router.get("/{project_id}/iterations", response_model=List[IterationSummary])
@trace("list_iterations")
async def list_iterations(project_id: str = Path(..., description="プロジェクトID")):
    """プロジェクトの反復サイクル一覧を取得"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        iterations = manager.list_iterations()
        
        return iterations
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の反復サイクル一覧取得中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクル一覧の取得に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager", "developer"]))])
@trace("create_iteration")
async def create_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_data: IterationCreate = Body(...)
):
    """新しい反復サイクルを作成"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        iteration = manager.create_new_iteration(
            goals=iteration_data.goals,
            focus_areas=iteration_data.focus_areas
        )
        
        return {
            "status": "success",
            "message": f"新しい反復サイクル {iteration.iteration_number} を作成しました",
            "project_id": project_id,
            "iteration_number": iteration.iteration_number
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"プロジェクト {project_id} の反復サイクル作成中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクルの作成に失敗しました: {str(e)}")


@router.get("/{project_id}/iterations/{iteration_number}", response_model=Dict[str, Any])
@trace("get_iteration")
async def get_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号")
):
    """指定された反復サイクルの詳細を取得"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        # レポートを生成（存在する場合はそれを使用）
        try:
            report = iteration.generate_report()
        except Exception as e:
            logger.error(f"反復サイクル {iteration_number} のレポート生成中にエラーが発生しました: {str(e)}")
            report = {
                "project_id": project_id,
                "iteration_number": iteration_number,
                "status": iteration.status,
                "goals": iteration.goals,
                "focus_areas": iteration.focus_areas,
                "error": f"レポート生成に失敗しました: {str(e)}"
            }
        
        return report
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"反復サイクル情報取得中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクル情報の取得に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations/{iteration_number}/start", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager", "developer"]))])
@trace("start_iteration")
async def start_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号")
):
    """反復サイクルを開始"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        iteration.start_iteration()
        
        return {
            "status": "success",
            "message": f"反復サイクル {iteration_number} を開始しました",
            "project_id": project_id,
            "iteration_number": iteration_number,
            "start_time": iteration.start_time.isoformat() if iteration.start_time else None
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"反復サイクル開始中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクルの開始に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations/{iteration_number}/complete", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager", "developer"]))])
@trace("complete_iteration")
async def complete_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号")
):
    """反復サイクルを完了"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        iteration.complete_iteration()
        
        return {
            "status": "success",
            "message": f"反復サイクル {iteration_number} を完了しました",
            "project_id": project_id,
            "iteration_number": iteration_number,
            "end_time": iteration.end_time.isoformat() if iteration.end_time else None
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"反復サイクル完了中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクルの完了に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations/{iteration_number}/change", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager", "developer"]))])
@trace("add_iteration_change")
async def add_iteration_change(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号"),
    change_data: ChangeRecord = Body(...)
):
    """反復サイクルに変更を追加"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        if iteration.status != "in_progress":
            raise HTTPException(status_code=400, detail=f"反復サイクル {iteration_number} は進行中ではありません")
        
        change = {
            "component": change_data.component,
            "description": change_data.description,
            "reason": change_data.reason,
            "impact": change_data.impact
        }
        
        iteration.add_change(change)
        
        return {
            "status": "success",
            "message": "変更を追加しました",
            "project_id": project_id,
            "iteration_number": iteration_number,
            "changes_count": len(iteration.changes)
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"変更追加中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"変更の追加に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations/{iteration_number}/lesson", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager", "developer"]))])
@trace("add_iteration_lesson")
async def add_iteration_lesson(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号"),
    lesson_data: LessonLearned = Body(...)
):
    """反復サイクルに学習した教訓を追加"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        if iteration.status != "in_progress":
            raise HTTPException(status_code=400, detail=f"反復サイクル {iteration_number} は進行中ではありません")
        
        lesson = {
            "category": lesson_data.category,
            "description": lesson_data.description,
            "application": lesson_data.application
        }
        
        iteration.add_lesson_learned(lesson)
        
        return {
            "status": "success",
            "message": "教訓を追加しました",
            "project_id": project_id,
            "iteration_number": iteration_number,
            "lessons_count": len(iteration.lessons_learned)
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"教訓追加中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"教訓の追加に失敗しました: {str(e)}")


@router.post("/{project_id}/iterations/{iteration_number}/evaluate", response_model=Dict[str, Any])
@trace("evaluate_iteration")
async def evaluate_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_number: int = Path(..., description="反復サイクル番号")
):
    """反復サイクルを評価"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        try:
            iteration = manager.get_iteration(iteration_number)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"反復サイクル {iteration_number} が見つかりません")
        
        evaluation_results = iteration.evaluate_iteration()
        
        return {
            "status": "success",
            "message": f"反復サイクル {iteration_number} の評価が完了しました",
            "project_id": project_id,
            "iteration_number": iteration_number,
            "evaluation_summary": {
                "overall_score": evaluation_results.get("overall_score", 0),
                "category_scores": evaluation_results.get("category_scores", {}),
                "goals_achievement": evaluation_results.get("goals_achievement", [])
            }
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except Exception as e:
        logger.error(f"反復サイクル評価中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクルの評価に失敗しました: {str(e)}")


@router.get("/{project_id}/iterations/trends", response_model=Dict[str, Any])
@trace("get_iteration_trends")
async def get_iteration_trends(project_id: str = Path(..., description="プロジェクトID")):
    """反復サイクルの傾向分析を取得"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        trends = manager.analyze_iteration_trends()
        
        if trends.get("status") == "error":
            raise HTTPException(status_code=400, detail=trends.get("message", "傾向分析に失敗しました"))
        
        return trends
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"反復サイクル傾向分析中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"傾向分析に失敗しました: {str(e)}")


@router.get("/{project_id}/iterations/recommendations", response_model=Dict[str, Any])
@trace("get_next_iteration_recommendations")
async def get_next_iteration_recommendations(project_id: str = Path(..., description="プロジェクトID")):
    """次の反復サイクルの推奨事項を取得"""
    try:
        project = pilot_project_manager.get_project(project_id)
        manager = get_iteration_manager(project)
        
        recommendations = manager.recommend_next_iteration_focus()
        
        if recommendations.get("status") == "error":
            raise HTTPException(status_code=400, detail=recommendations.get("message", "推奨生成に失敗しました"))
        
        return recommendations
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"次の反復サイクル推奨生成中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"推奨生成に失敗しました: {str(e)}")


@router.post("/{project_id}/run-iteration", response_model=Dict[str, Any], dependencies=[Depends(RoleRequirement(["admin", "project_manager"]))])
@trace("run_project_iteration")
async def run_project_iteration(
    project_id: str = Path(..., description="プロジェクトID"),
    iteration_data: Optional[IterationCreate] = Body(None)
):
    """プロジェクトの反復サイクルを自動実行"""
    try:
        # 目標と注力分野が指定されている場合はそれを使用
        goals = None
        focus_areas = None
        
        if iteration_data:
            goals = iteration_data.goals
            focus_areas = iteration_data.focus_areas
        
        # 反復サイクルを実行
        result = run_iteration_cycle(project_id, goals, focus_areas)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "反復サイクルの実行に失敗しました"))
        
        return {
            "status": "success",
            "message": "反復サイクルを実行しました",
            "project_id": project_id,
            "iteration_number": result.get("iteration_number"),
            "report": result.get("report")
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"プロジェクト {project_id} が見つかりません")
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"反復サイクル実行中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=f"反復サイクルの実行に失敗しました: {str(e)}") 