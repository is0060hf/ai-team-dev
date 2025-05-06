"""
プロジェクト反復プロセス管理モジュール。
AIエージェントチームを使用した開発プロジェクトの反復的な改善サイクルを管理するための機能を提供します。
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from pathlib import Path
import threading
import copy

from utils.logger import get_structured_logger
from utils.tracing import trace, trace_span
from utils.performance import time_function
from utils.pilot_project import PilotProject, pilot_project_manager
from utils.project_evaluation import evaluate_project_automatically

# ロガーの設定
logger = get_structured_logger("project_iteration")

class IterationCycle:
    """プロジェクトの反復サイクルを管理するクラス"""
    
    def __init__(
        self,
        project: PilotProject,
        iteration_number: int,
        goals: List[str],
        focus_areas: List[str]
    ):
        """
        Args:
            project: 反復対象のプロジェクト
            iteration_number: 反復サイクル番号
            goals: 反復の目標リスト
            focus_areas: 注力分野リスト
        """
        self.project = project
        self.iteration_number = iteration_number
        self.goals = goals
        self.focus_areas = focus_areas
        
        # 反復サイクルの状態
        self.status = "planned"  # planned, in_progress, completed, evaluated
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # 評価結果
        self.evaluation_results: Dict[str, Any] = {}
        
        # 変更点と学習した教訓
        self.changes: List[Dict[str, Any]] = []
        self.lessons_learned: List[Dict[str, Any]] = []
        
        # 反復サイクルのディレクトリを作成
        self.iteration_dir = project.project_dir / "iterations" / f"iteration_{iteration_number}"
        self.iteration_dir.mkdir(parents=True, exist_ok=True)
        
        # メタデータファイルのパス
        self.metadata_file = self.iteration_dir / "metadata.json"
        
        # 初期メタデータの保存
        self._save_metadata()
    
    def _save_metadata(self) -> None:
        """メタデータをディスクに保存"""
        metadata = {
            "project_id": self.project.project_id,
            "iteration_number": self.iteration_number,
            "goals": self.goals,
            "focus_areas": self.focus_areas,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "changes_count": len(self.changes),
            "lessons_learned_count": len(self.lessons_learned),
            "last_updated": datetime.now().isoformat()
        }
        
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_iteration(cls, project: PilotProject, iteration_number: int) -> "IterationCycle":
        """
        既存の反復サイクルを読み込む
        
        Args:
            project: プロジェクト
            iteration_number: 反復サイクル番号
            
        Returns:
            IterationCycle: 反復サイクルインスタンス
            
        Raises:
            FileNotFoundError: 反復サイクルが見つからない場合
        """
        iteration_dir = project.project_dir / "iterations" / f"iteration_{iteration_number}"
        metadata_file = iteration_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"反復サイクル {iteration_number} が見つかりません")
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        iteration = cls(
            project=project,
            iteration_number=metadata["iteration_number"],
            goals=metadata["goals"],
            focus_areas=metadata["focus_areas"]
        )
        
        iteration.status = metadata["status"]
        
        if metadata["start_time"]:
            iteration.start_time = datetime.fromisoformat(metadata["start_time"])
        
        if metadata["end_time"]:
            iteration.end_time = datetime.fromisoformat(metadata["end_time"])
        
        # 変更点と教訓を読み込み
        changes_file = iteration_dir / "changes.json"
        if changes_file.exists():
            with open(changes_file, "r", encoding="utf-8") as f:
                iteration.changes = json.load(f)
        
        lessons_file = iteration_dir / "lessons_learned.json"
        if lessons_file.exists():
            with open(lessons_file, "r", encoding="utf-8") as f:
                iteration.lessons_learned = json.load(f)
        
        # 評価結果を読み込み
        evaluation_file = iteration_dir / "evaluation_results.json"
        if evaluation_file.exists():
            with open(evaluation_file, "r", encoding="utf-8") as f:
                iteration.evaluation_results = json.load(f)
        
        return iteration
    
    @time_function(log_level="info")
    def start_iteration(self) -> None:
        """反復サイクルを開始"""
        if self.status != "planned":
            logger.warning(f"反復サイクル {self.iteration_number} は既に開始されています")
            return
        
        self.status = "in_progress"
        self.start_time = datetime.now()
        
        logger.info(f"反復サイクル {self.iteration_number} を開始しました")
        
        # 変更リストのファイルを初期化
        changes_file = self.iteration_dir / "changes.json"
        with open(changes_file, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        
        # 教訓リストのファイルを初期化
        lessons_file = self.iteration_dir / "lessons_learned.json"
        with open(lessons_file, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        
        self._save_metadata()
    
    @time_function(log_level="info")
    def complete_iteration(self) -> None:
        """反復サイクルを完了"""
        if self.status != "in_progress":
            logger.warning(f"反復サイクル {self.iteration_number} は進行中ではありません")
            return
        
        self.status = "completed"
        self.end_time = datetime.now()
        
        logger.info(f"反復サイクル {self.iteration_number} を完了しました")
        
        self._save_metadata()
    
    def add_change(self, change: Dict[str, Any]) -> None:
        """
        変更を追加
        
        Args:
            change: 変更の詳細（component, description, reason, impact など）
        """
        # タイムスタンプを追加
        change["timestamp"] = datetime.now().isoformat()
        
        # 変更リストに追加
        self.changes.append(change)
        
        # ファイルに保存
        changes_file = self.iteration_dir / "changes.json"
        with open(changes_file, "w", encoding="utf-8") as f:
            json.dump(self.changes, f, ensure_ascii=False, indent=2)
        
        logger.info(f"反復サイクル {self.iteration_number} に変更を追加しました: {change.get('description', '')}")
        
        self._save_metadata()
    
    def add_lesson_learned(self, lesson: Dict[str, Any]) -> None:
        """
        学習した教訓を追加
        
        Args:
            lesson: 教訓の詳細（category, description, application など）
        """
        # タイムスタンプを追加
        lesson["timestamp"] = datetime.now().isoformat()
        
        # 教訓リストに追加
        self.lessons_learned.append(lesson)
        
        # ファイルに保存
        lessons_file = self.iteration_dir / "lessons_learned.json"
        with open(lessons_file, "w", encoding="utf-8") as f:
            json.dump(self.lessons_learned, f, ensure_ascii=False, indent=2)
        
        logger.info(f"反復サイクル {self.iteration_number} に教訓を追加しました: {lesson.get('description', '')}")
        
        self._save_metadata()
    
    @time_function(log_level="info")
    def evaluate_iteration(self) -> Dict[str, Any]:
        """
        反復サイクルを評価
        
        Returns:
            Dict[str, Any]: 評価結果
        """
        if self.status != "completed":
            logger.warning(f"反復サイクル {self.iteration_number} はまだ完了していません")
        
        # プロジェクトの自動評価を実行
        evaluation_results = evaluate_project_automatically(self.project)
        
        # 以前の反復サイクルの評価結果と比較（あれば）
        if self.iteration_number > 1:
            try:
                previous_iteration = IterationCycle.load_iteration(self.project, self.iteration_number - 1)
                previous_evaluation = previous_iteration.evaluation_results
                
                if previous_evaluation:
                    # 比較結果を追加
                    evaluation_results["comparison"] = self._compare_with_previous_evaluation(
                        evaluation_results, previous_evaluation
                    )
            except FileNotFoundError:
                logger.warning(f"前回の反復サイクル {self.iteration_number - 1} の評価結果が見つかりません")
        
        # 目標に対する達成度を評価
        evaluation_results["goals_achievement"] = self._evaluate_goals_achievement(evaluation_results)
        
        # 評価結果を保存
        self.evaluation_results = evaluation_results
        evaluation_file = self.iteration_dir / "evaluation_results.json"
        with open(evaluation_file, "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, ensure_ascii=False, indent=2)
        
        # ステータスを更新
        self.status = "evaluated"
        self._save_metadata()
        
        logger.info(f"反復サイクル {self.iteration_number} の評価が完了しました")
        
        return evaluation_results
    
    def _compare_with_previous_evaluation(
        self, current_evaluation: Dict[str, Any], previous_evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """前回の評価結果と比較"""
        comparison = {
            "overall_score": {
                "current": current_evaluation.get("overall_score", 0),
                "previous": previous_evaluation.get("overall_score", 0),
                "difference": current_evaluation.get("overall_score", 0) - previous_evaluation.get("overall_score", 0)
            },
            "category_scores": {}
        }
        
        # カテゴリごとのスコア比較
        current_categories = current_evaluation.get("category_scores", {})
        previous_categories = previous_evaluation.get("category_scores", {})
        
        for category in set(list(current_categories.keys()) + list(previous_categories.keys())):
            current_score = current_categories.get(category, 0)
            previous_score = previous_categories.get(category, 0)
            
            comparison["category_scores"][category] = {
                "current": current_score,
                "previous": previous_score,
                "difference": current_score - previous_score
            }
        
        # 改善した点と悪化した点を特定
        improvements = []
        regressions = []
        
        for category, scores in comparison["category_scores"].items():
            diff = scores["difference"]
            if diff >= 5:  # 5ポイント以上の改善
                improvements.append({
                    "category": category,
                    "difference": diff
                })
            elif diff <= -5:  # 5ポイント以上の悪化
                regressions.append({
                    "category": category,
                    "difference": diff
                })
        
        # スコア差でソート
        improvements.sort(key=lambda x: x["difference"], reverse=True)
        regressions.sort(key=lambda x: x["difference"])
        
        comparison["improvements"] = improvements
        comparison["regressions"] = regressions
        
        # 総合的な傾向を判定
        if comparison["overall_score"]["difference"] >= 5:
            comparison["trend"] = "significant_improvement"
        elif comparison["overall_score"]["difference"] > 0:
            comparison["trend"] = "improvement"
        elif comparison["overall_score"]["difference"] == 0:
            comparison["trend"] = "stable"
        elif comparison["overall_score"]["difference"] > -5:
            comparison["trend"] = "regression"
        else:
            comparison["trend"] = "significant_regression"
        
        return comparison
    
    def _evaluate_goals_achievement(self, evaluation_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """目標の達成度を評価"""
        goals_achievement = []
        
        for goal in self.goals:
            achievement = {
                "goal": goal,
                "achieved": False,
                "score": 0,
                "evidence": ""
            }
            
            # 目標の内容に基づいて達成度を評価
            # 注: 実際の実装では、目標の性質に応じた評価ロジックが必要
            
            # 例: パフォーマンス関連の目標
            if "パフォーマンス" in goal or "速度" in goal or "応答時間" in goal:
                category_score = evaluation_results.get("category_scores", {}).get("performance", 0)
                achievement["score"] = category_score
                achievement["achieved"] = category_score >= 75
                achievement["evidence"] = f"パフォーマンススコア: {category_score}"
            
            # 例: 品質関連の目標
            elif "品質" in goal or "バグ" in goal or "テスト" in goal:
                category_score = evaluation_results.get("category_scores", {}).get("quality", 0)
                achievement["score"] = category_score
                achievement["achieved"] = category_score >= 75
                achievement["evidence"] = f"品質スコア: {category_score}"
            
            # 例: 協働関連の目標
            elif "協働" in goal or "コミュニケーション" in goal or "チーム" in goal:
                category_score = evaluation_results.get("category_scores", {}).get("collaboration", 0)
                achievement["score"] = category_score
                achievement["achieved"] = category_score >= 75
                achievement["evidence"] = f"協働スコア: {category_score}"
            
            # 例: 成果関連の目標
            elif "要件" in goal or "機能" in goal or "ユーザー" in goal:
                category_score = evaluation_results.get("category_scores", {}).get("outcome", 0)
                achievement["score"] = category_score
                achievement["achieved"] = category_score >= 75
                achievement["evidence"] = f"成果スコア: {category_score}"
            
            # デフォルト: 総合スコアで評価
            else:
                overall_score = evaluation_results.get("overall_score", 0)
                achievement["score"] = overall_score
                achievement["achieved"] = overall_score >= 75
                achievement["evidence"] = f"総合スコア: {overall_score}"
            
            goals_achievement.append(achievement)
        
        return goals_achievement
    
    def generate_report(self) -> Dict[str, Any]:
        """
        反復サイクルのレポートを生成
        
        Returns:
            Dict[str, Any]: レポート内容
        """
        # 反復サイクルの期間を計算
        duration = None
        if self.start_time:
            if self.end_time:
                duration = (self.end_time - self.start_time).total_seconds() / 3600  # 時間単位
            else:
                duration = (datetime.now() - self.start_time).total_seconds() / 3600
        
        # 変更の概要を構築
        changes_summary = {}
        for change in self.changes:
            component = change.get("component", "その他")
            if component not in changes_summary:
                changes_summary[component] = []
            changes_summary[component].append(change.get("description", ""))
        
        # 教訓の概要を構築
        lessons_summary = {}
        for lesson in self.lessons_learned:
            category = lesson.get("category", "その他")
            if category not in lessons_summary:
                lessons_summary[category] = []
            lessons_summary[category].append(lesson.get("description", ""))
        
        # 評価結果のサマリー
        evaluation_summary = {}
        if self.evaluation_results:
            evaluation_summary = {
                "overall_score": self.evaluation_results.get("overall_score", 0),
                "category_scores": self.evaluation_results.get("category_scores", {}),
                "strengths": [item.get("subcategory", "") for item in self.evaluation_results.get("strengths", [])[:3]],
                "weaknesses": [item.get("subcategory", "") for item in self.evaluation_results.get("weaknesses", [])[:3]],
                "goals_achievement": self.evaluation_results.get("goals_achievement", [])
            }
        
        # 反復レポートを構築
        report = {
            "project_id": self.project.project_id,
            "project_title": self.project.title,
            "iteration_number": self.iteration_number,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_hours": duration,
            "goals": self.goals,
            "focus_areas": self.focus_areas,
            "changes_summary": changes_summary,
            "total_changes": len(self.changes),
            "lessons_summary": lessons_summary,
            "total_lessons": len(self.lessons_learned),
            "evaluation_summary": evaluation_summary,
            "generation_time": datetime.now().isoformat()
        }
        
        # 前の反復との比較（あれば）
        if "comparison" in self.evaluation_results:
            report["comparison"] = self.evaluation_results["comparison"]
        
        # レポートをファイルに保存
        report_file = self.iteration_dir / "iteration_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"反復サイクル {self.iteration_number} のレポートを生成しました")
        
        return report
    

class IterationManager:
    """プロジェクトの反復サイクルを管理するマネージャークラス"""
    
    def __init__(self, project: PilotProject):
        """
        Args:
            project: 管理対象のプロジェクト
        """
        self.project = project
        self.lock = threading.RLock()
        
        # 反復ディレクトリを作成
        self.iterations_dir = project.project_dir / "iterations"
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
    
    def list_iterations(self) -> List[Dict[str, Any]]:
        """
        プロジェクトの反復サイクルのリストを取得
        
        Returns:
            List[Dict[str, Any]]: 反復サイクルのリスト
        """
        iterations = []
        
        with self.lock:
            for dir_path in self.iterations_dir.iterdir():
                if dir_path.is_dir() and dir_path.name.startswith("iteration_"):
                    metadata_file = dir_path / "metadata.json"
                    
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, "r", encoding="utf-8") as f:
                                metadata = json.load(f)
                            
                            iterations.append({
                                "iteration_number": metadata["iteration_number"],
                                "status": metadata["status"],
                                "goals": metadata["goals"],
                                "start_time": metadata["start_time"],
                                "end_time": metadata["end_time"],
                                "last_updated": metadata.get("last_updated")
                            })
                        except Exception as e:
                            logger.error(f"反復メタデータの読み込みに失敗しました: {str(e)}")
        
        # 反復番号でソート
        iterations.sort(key=lambda x: x["iteration_number"])
        
        return iterations
    
    def get_current_iteration_number(self) -> int:
        """
        現在の反復サイクル番号を取得
        
        Returns:
            int: 反復サイクル番号
        """
        iterations = self.list_iterations()
        
        if not iterations:
            return 0
        
        # 最新の反復サイクル番号を取得
        return max(iteration["iteration_number"] for iteration in iterations)
    
    def get_iteration(self, iteration_number: int) -> IterationCycle:
        """
        指定された番号の反復サイクルを取得
        
        Args:
            iteration_number: 反復サイクル番号
            
        Returns:
            IterationCycle: 反復サイクルインスタンス
            
        Raises:
            FileNotFoundError: 反復サイクルが見つからない場合
        """
        return IterationCycle.load_iteration(self.project, iteration_number)
    
    @time_function(log_level="info")
    def create_new_iteration(
        self,
        goals: List[str],
        focus_areas: List[str]
    ) -> IterationCycle:
        """
        新しい反復サイクルを作成
        
        Args:
            goals: 反復の目標リスト
            focus_areas: 注力分野リスト
            
        Returns:
            IterationCycle: 作成された反復サイクル
        """
        with self.lock:
            current_number = self.get_current_iteration_number()
            new_number = current_number + 1
            
            iteration = IterationCycle(
                project=self.project,
                iteration_number=new_number,
                goals=goals,
                focus_areas=focus_areas
            )
            
            logger.info(f"プロジェクト {self.project.project_id} の新しい反復サイクル {new_number} を作成しました")
            
            return iteration
    
    @time_function(log_level="info")
    def run_iteration_workflow(self, iteration: IterationCycle) -> Dict[str, Any]:
        """
        反復サイクルのワークフローを実行
        
        Args:
            iteration: 実行する反復サイクル
            
        Returns:
            Dict[str, Any]: 実行結果
        """
        # 反復サイクルを開始
        iteration.start_iteration()
        
        try:
            # TODO: 実際の反復プロセスの実装
            # この部分はプロジェクトの実装に応じて変更する必要があります
            
            # 以下は模擬的な処理
            
            # 1. いくつかの変更を追加
            iteration.add_change({
                "component": "アーキテクチャ",
                "description": "マイクロサービスアーキテクチャに移行",
                "reason": "スケーラビリティと保守性の向上",
                "impact": "high"
            })
            
            iteration.add_change({
                "component": "パフォーマンス",
                "description": "データベースインデックスの最適化",
                "reason": "クエリ応答時間の短縮",
                "impact": "medium"
            })
            
            # 2. いくつかの教訓を追加
            iteration.add_lesson_learned({
                "category": "アーキテクチャ",
                "description": "早期のパフォーマンステストが重要",
                "application": "次回はプロトタイプ段階でパフォーマンステストを実施"
            })
            
            iteration.add_lesson_learned({
                "category": "協働",
                "description": "頻繁なコードレビューが品質向上に効果的",
                "application": "プルリクエストごとに最低2人のレビュアーを設定"
            })
            
            # 反復サイクルを完了
            iteration.complete_iteration()
            
            # 評価を実行
            iteration.evaluate_iteration()
            
            # レポート生成
            report = iteration.generate_report()
            
            return {
                "status": "success",
                "iteration_number": iteration.iteration_number,
                "report": report
            }
        
        except Exception as e:
            logger.error(f"反復ワークフロー実行中にエラーが発生しました: {str(e)}")
            return {
                "status": "error",
                "iteration_number": iteration.iteration_number,
                "message": str(e)
            }
    
    @time_function(log_level="info")
    def analyze_iteration_trends(self) -> Dict[str, Any]:
        """
        プロジェクトの反復サイクルの傾向を分析
        
        Returns:
            Dict[str, Any]: 傾向分析結果
        """
        iterations = self.list_iterations()
        
        if not iterations:
            return {
                "status": "error",
                "message": "反復サイクルがありません"
            }
        
        # 評価されたサイクルのみを対象
        evaluated_iterations = []
        
        for iteration_info in iterations:
            try:
                iteration = self.get_iteration(iteration_info["iteration_number"])
                if iteration.status == "evaluated" and iteration.evaluation_results:
                    evaluated_iterations.append(iteration)
            except Exception as e:
                logger.error(f"反復サイクルの読み込みに失敗しました: {str(e)}")
        
        if not evaluated_iterations:
            return {
                "status": "error",
                "message": "評価された反復サイクルがありません"
            }
        
        # 総合スコアの傾向
        overall_scores = [
            {
                "iteration": iteration.iteration_number,
                "score": iteration.evaluation_results.get("overall_score", 0)
            }
            for iteration in evaluated_iterations
        ]
        
        # カテゴリ別スコアの傾向
        category_scores = {}
        
        for iteration in evaluated_iterations:
            for category, score in iteration.evaluation_results.get("category_scores", {}).items():
                if category not in category_scores:
                    category_scores[category] = []
                
                category_scores[category].append({
                    "iteration": iteration.iteration_number,
                    "score": score
                })
        
        # 傾向分析レポートを構築
        trend_report = {
            "project_id": self.project.project_id,
            "project_title": self.project.title,
            "total_iterations": len(iterations),
            "evaluated_iterations": len(evaluated_iterations),
            "overall_score_trend": overall_scores,
            "category_score_trends": category_scores,
            "analysis_time": datetime.now().isoformat()
        }
        
        # 全体的な進捗を判定
        if len(overall_scores) >= 2:
            first_score = overall_scores[0]["score"]
            last_score = overall_scores[-1]["score"]
            score_diff = last_score - first_score
            
            if score_diff >= 15:
                trend_report["progress_assessment"] = "significant_improvement"
            elif score_diff >= 5:
                trend_report["progress_assessment"] = "improvement"
            elif score_diff > -5:
                trend_report["progress_assessment"] = "stable"
            elif score_diff >= -15:
                trend_report["progress_assessment"] = "regression"
            else:
                trend_report["progress_assessment"] = "significant_regression"
        
        # トレンドレポートをファイルに保存
        trend_file = self.iterations_dir / "iteration_trends.json"
        with open(trend_file, "w", encoding="utf-8") as f:
            json.dump(trend_report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"プロジェクト {self.project.project_id} の反復傾向分析を完了しました")
        
        return trend_report
    
    @time_function(log_level="info")
    def recommend_next_iteration_focus(self) -> Dict[str, Any]:
        """
        次の反復サイクルでの注力すべき分野を推奨
        
        Returns:
            Dict[str, Any]: 推奨事項
        """
        # 最新の反復サイクルを取得
        current_number = self.get_current_iteration_number()
        
        if current_number == 0:
            return {
                "status": "error",
                "message": "反復サイクルがありません"
            }
        
        try:
            latest_iteration = self.get_iteration(current_number)
            
            if latest_iteration.status != "evaluated" or not latest_iteration.evaluation_results:
                return {
                    "status": "error",
                    "message": "最新の反復サイクルがまだ評価されていません"
                }
            
            # 弱点から改善が必要な分野を特定
            weaknesses = latest_iteration.evaluation_results.get("weaknesses", [])
            
            # 改善提案から目標と注力分野を特定
            suggestions = latest_iteration.evaluation_results.get("improvement_suggestions", [])
            
            recommended_goals = []
            recommended_focus_areas = []
            
            # 弱点から目標を生成
            for weakness in weaknesses[:3]:  # 上位3つの弱点に対応
                category = weakness.get("category", "")
                subcategory = weakness.get("subcategory", "")
                
                if category and subcategory:
                    recommended_goals.append(f"{subcategory}の改善による{category}スコアの向上")
                    recommended_focus_areas.append(subcategory)
            
            # 改善提案から追加の目標を生成
            for suggestion in suggestions[:3]:  # 上位3つの提案に対応
                category = suggestion.get("category", "")
                subcategory = suggestion.get("subcategory", "")
                
                if category and subcategory and subcategory not in recommended_focus_areas:
                    recommended_goals.append(f"{subcategory}の最適化")
                    recommended_focus_areas.append(subcategory)
            
            # 次の反復サイクルの推奨を構築
            recommendation = {
                "project_id": self.project.project_id,
                "current_iteration": current_number,
                "recommended_goals": recommended_goals,
                "recommended_focus_areas": recommended_focus_areas,
                "reasoning": "最近の評価で特定された弱点と改善提案に基づいて、次の反復サイクルでの注力分野を推奨しています。",
                "generation_time": datetime.now().isoformat()
            }
            
            # 推奨をファイルに保存
            recommendation_file = self.iterations_dir / "next_iteration_recommendation.json"
            with open(recommendation_file, "w", encoding="utf-8") as f:
                json.dump(recommendation, f, ensure_ascii=False, indent=2)
            
            logger.info(f"プロジェクト {self.project.project_id} の次の反復サイクル推奨を生成しました")
            
            return recommendation
        
        except Exception as e:
            logger.error(f"次の反復サイクル推奨の生成に失敗しました: {str(e)}")
            return {
                "status": "error",
                "message": f"推奨生成中にエラーが発生しました: {str(e)}"
            }
    
    def create_iteration_from_recommendation(self) -> Optional[IterationCycle]:
        """
        推奨に基づいて新しい反復サイクルを作成
        
        Returns:
            Optional[IterationCycle]: 作成された反復サイクル（失敗した場合はNone）
        """
        # 推奨ファイルを読み込み
        recommendation_file = self.iterations_dir / "next_iteration_recommendation.json"
        
        if not recommendation_file.exists():
            logger.error("次の反復サイクル推奨が見つかりません")
            return None
        
        try:
            with open(recommendation_file, "r", encoding="utf-8") as f:
                recommendation = json.load(f)
            
            # 推奨に基づいて新しい反復サイクルを作成
            goals = recommendation.get("recommended_goals", [])
            focus_areas = recommendation.get("recommended_focus_areas", [])
            
            if not goals or not focus_areas:
                logger.error("推奨に目標または注力分野が含まれていません")
                return None
            
            # 新しい反復サイクルを作成
            new_iteration = self.create_new_iteration(goals, focus_areas)
            
            logger.info(f"推奨に基づいて新しい反復サイクル {new_iteration.iteration_number} を作成しました")
            
            return new_iteration
        
        except Exception as e:
            logger.error(f"推奨からの反復サイクル作成に失敗しました: {str(e)}")
            return None


def get_iteration_manager(project: PilotProject) -> IterationManager:
    """
    プロジェクトの反復マネージャーを取得
    
    Args:
        project: 対象プロジェクト
        
    Returns:
        IterationManager: 反復マネージャー
    """
    return IterationManager(project)


def run_iteration_cycle(
    project_id: str,
    goals: Optional[List[str]] = None,
    focus_areas: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    プロジェクトに対して反復サイクルを実行
    
    Args:
        project_id: プロジェクトID
        goals: 反復の目標リスト（指定しない場合は推奨を使用）
        focus_areas: 注力分野リスト（指定しない場合は推奨を使用）
        
    Returns:
        Dict[str, Any]: 実行結果
    """
    try:
        # プロジェクトを取得
        project = pilot_project_manager.get_project(project_id)
        
        # 反復マネージャーを取得
        manager = get_iteration_manager(project)
        
        # 目標と注力分野が指定されていない場合は推奨を使用
        if not goals or not focus_areas:
            # 既存の反復サイクルがあるか確認
            current_number = manager.get_current_iteration_number()
            
            if current_number > 0:
                # 推奨を取得
                recommendation = manager.recommend_next_iteration_focus()
                
                if recommendation.get("status") != "error":
                    goals = recommendation.get("recommended_goals", [])
                    focus_areas = recommendation.get("recommended_focus_areas", [])
            
            # 推奨が取得できなかった場合はデフォルト値を使用
            if not goals:
                goals = ["全体的なプロジェクト品質の向上", "ユーザー満足度の改善"]
            
            if not focus_areas:
                focus_areas = ["品質", "パフォーマンス", "ユーザーエクスペリエンス"]
        
        # 新しい反復サイクルを作成
        iteration = manager.create_new_iteration(goals, focus_areas)
        
        # 反復ワークフローを実行
        result = manager.run_iteration_workflow(iteration)
        
        # 反復傾向分析を実行
        manager.analyze_iteration_trends()
        
        return result
    
    except Exception as e:
        logger.error(f"反復サイクルの実行に失敗しました: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        } 