"""
プロジェクト評価モジュール。
AIエージェントチームが開発したプロジェクトを多角的に評価するための機能を提供します。
"""

import json
import time
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Set, Callable
from pathlib import Path
import threading

from utils.logger import get_structured_logger
from utils.tracing import trace, trace_span
from utils.performance import time_function, get_performance_metrics
from utils.pilot_project import PilotProject

# ロガーの設定
logger = get_structured_logger("project_evaluation")

# 評価カテゴリとメトリクス
EVALUATION_CATEGORIES = {
    "performance": [
        "response_time",
        "resource_usage",
        "code_efficiency",
        "execution_speed"
    ],
    "quality": [
        "code_quality",
        "architecture",
        "test_coverage",
        "documentation",
        "user_experience"
    ],
    "collaboration": [
        "task_distribution",
        "communication",
        "conflict_resolution",
        "decision_making"
    ],
    "outcome": [
        "requirements_fulfillment",
        "innovation",
        "maintainability",
        "user_satisfaction"
    ]
}


class ProjectEvaluator:
    """プロジェクト評価を行うクラス"""
    
    def __init__(self, project: PilotProject):
        """
        Args:
            project: 評価対象のプロジェクト
        """
        self.project = project
        self.evaluations: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        
        # 評価履歴ディレクトリの作成
        self.evaluation_dir = project.project_dir / "evaluation"
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)
    
    @time_function(log_level="info")
    def evaluate_performance(
        self,
        response_time: float,
        resource_usage: Dict[str, float],
        code_metrics: Dict[str, Any],
        execution_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        パフォーマンス評価を実行
        
        Args:
            response_time: 平均応答時間（ミリ秒）
            resource_usage: リソース使用状況（メモリ、CPU等）
            code_metrics: コードメトリクス（複雑度、行数等）
            execution_metrics: 実行時メトリクス（処理時間等）
            
        Returns:
            Dict[str, Any]: 評価結果
        """
        # リソース使用率の計算（0〜100のスコア、低いほど良い）
        resource_score = 100 - (
            0.3 * resource_usage.get("memory_percent", 0) +
            0.5 * resource_usage.get("cpu_percent", 0) +
            0.2 * resource_usage.get("io_percent", 0)
        )
        
        # コード効率性の計算（0〜100のスコア、高いほど良い）
        code_efficiency = (
            100 - min(100, code_metrics.get("cyclomatic_complexity", 0) / 5) * 0.4 +
            min(100, 1000 / max(1, code_metrics.get("loc", 1))) * 0.3 +
            (100 - min(100, code_metrics.get("function_count", 0) / 50)) * 0.3
        )
        
        # 実行速度の計算（0〜100のスコア、高いほど良い）
        execution_speed = 100 - min(100, (
            execution_metrics.get("avg_execution_time_ms", 0) / 100
        ))
        
        # 応答時間のスコア（0〜100、低いほど良い）
        response_score = 100 - min(100, response_time / 200)
        
        # 総合パフォーマンススコアの計算（0〜100）
        overall_score = (
            response_score * 0.3 +
            resource_score * 0.2 +
            code_efficiency * 0.3 +
            execution_speed * 0.2
        )
        
        # 評価結果の構築
        evaluation_result = {
            "category": "performance",
            "timestamp": datetime.now().isoformat(),
            "scores": {
                "response_time": response_score,
                "resource_usage": resource_score,
                "code_efficiency": code_efficiency,
                "execution_speed": execution_speed,
                "overall": overall_score
            },
            "raw_metrics": {
                "response_time_ms": response_time,
                "resource_usage": resource_usage,
                "code_metrics": code_metrics,
                "execution_metrics": execution_metrics
            },
            "summary": self._generate_performance_summary(overall_score)
        }
        
        # 評価結果を保存
        with self.lock:
            self.evaluations["performance"] = evaluation_result
            self._save_evaluation("performance", evaluation_result)
        
        return evaluation_result
    
    def _generate_performance_summary(self, score: float) -> str:
        """パフォーマンス評価のサマリーを生成"""
        if score >= 90:
            return "優れたパフォーマンス。ほとんどの指標が期待を上回っています。"
        elif score >= 75:
            return "良好なパフォーマンス。いくつかの最適化の余地があります。"
        elif score >= 60:
            return "許容範囲内のパフォーマンス。いくつかの重要な改善が必要です。"
        elif score >= 40:
            return "改善が必要なパフォーマンス。複数の問題が見つかりました。"
        else:
            return "深刻なパフォーマンス問題。根本的な再設計が必要です。"
    
    @time_function(log_level="info")
    def evaluate_code_quality(
        self,
        static_analysis: Dict[str, Any],
        code_review_results: Dict[str, Any],
        test_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        コード品質評価を実行
        
        Args:
            static_analysis: 静的解析結果
            code_review_results: コードレビュー結果
            test_results: テスト結果
            
        Returns:
            Dict[str, Any]: 評価結果
        """
        # 静的解析のスコア計算（0〜100）
        linting_score = 100 - min(100, static_analysis.get("error_count", 0) * 2 + static_analysis.get("warning_count", 0))
        
        # アーキテクチャスコアの計算
        architecture_score = (
            code_review_results.get("architecture_score", 0) * 0.7 +
            (100 - min(100, static_analysis.get("dependency_count", 0) / 10)) * 0.3
        )
        
        # テストカバレッジスコアの計算
        test_coverage = test_results.get("coverage_percent", 0)
        test_score = (
            test_coverage * 0.6 +
            (100 - min(100, test_results.get("failing_tests", 0) * 5)) * 0.4
        )
        
        # ドキュメンテーションスコアの計算
        documentation_score = code_review_results.get("documentation_score", 0)
        
        # ユーザーエクスペリエンススコア
        ux_score = code_review_results.get("ux_score", 0)
        
        # 総合品質スコアの計算
        overall_score = (
            linting_score * 0.2 +
            architecture_score * 0.25 +
            test_score * 0.25 +
            documentation_score * 0.15 +
            ux_score * 0.15
        )
        
        # 評価結果の構築
        evaluation_result = {
            "category": "quality",
            "timestamp": datetime.now().isoformat(),
            "scores": {
                "code_quality": linting_score,
                "architecture": architecture_score,
                "test_coverage": test_score,
                "documentation": documentation_score,
                "user_experience": ux_score,
                "overall": overall_score
            },
            "raw_metrics": {
                "static_analysis": static_analysis,
                "code_review": code_review_results,
                "test_results": test_results
            },
            "summary": self._generate_quality_summary(overall_score)
        }
        
        # 評価結果を保存
        with self.lock:
            self.evaluations["quality"] = evaluation_result
            self._save_evaluation("quality", evaluation_result)
        
        return evaluation_result
    
    def _generate_quality_summary(self, score: float) -> str:
        """品質評価のサマリーを生成"""
        if score >= 90:
            return "優れたコード品質。高い保守性と拡張性があります。"
        elif score >= 75:
            return "良好なコード品質。小さな改善点が見られます。"
        elif score >= 60:
            return "許容範囲内のコード品質。いくつかの技術的負債があります。"
        elif score >= 40:
            return "改善が必要なコード品質。リファクタリングを検討すべきです。"
        else:
            return "深刻なコード品質の問題。多くの技術的負債があります。"
    
    @time_function(log_level="info")
    def evaluate_collaboration(
        self,
        communication_logs: List[Dict[str, Any]],
        task_distribution: Dict[str, List[str]],
        decision_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        協働プロセスの評価を実行
        
        Args:
            communication_logs: コミュニケーションログ
            task_distribution: タスク分配状況
            decision_history: 意思決定履歴
            
        Returns:
            Dict[str, Any]: 評価結果
        """
        # タスク分配のバランスを評価（0〜100、高いほど良い）
        task_counts = [len(tasks) for tasks in task_distribution.values()]
        if task_counts:
            task_std_dev = statistics.stdev(task_counts) if len(task_counts) > 1 else 0
            max_tasks = max(task_counts)
            task_balance = 100 - min(100, (task_std_dev / max(1, max_tasks / 10)) * 100)
        else:
            task_balance = 0
        
        # コミュニケーション頻度とクオリティを評価
        if communication_logs:
            comm_frequency = min(100, len(communication_logs) / 10 * 100)
            comm_quality = sum(log.get("quality_score", 0) for log in communication_logs) / len(communication_logs)
        else:
            comm_frequency = 0
            comm_quality = 0
        
        communication_score = (comm_frequency * 0.4 + comm_quality * 0.6)
        
        # 紛争解決能力を評価
        conflict_logs = [log for log in communication_logs if log.get("type") == "conflict"]
        if conflict_logs:
            conflict_resolution = sum(log.get("resolution_score", 0) for log in conflict_logs) / len(conflict_logs)
        else:
            conflict_resolution = 100  # 紛争がなければ満点
        
        # 意思決定プロセスを評価
        if decision_history:
            decision_quality = sum(d.get("quality_score", 0) for d in decision_history) / len(decision_history)
            decision_speed = sum(d.get("speed_score", 0) for d in decision_history) / len(decision_history)
            decision_score = (decision_quality * 0.7 + decision_speed * 0.3)
        else:
            decision_score = 0
        
        # 総合協働スコアの計算
        overall_score = (
            task_balance * 0.25 +
            communication_score * 0.3 +
            conflict_resolution * 0.2 +
            decision_score * 0.25
        )
        
        # 評価結果の構築
        evaluation_result = {
            "category": "collaboration",
            "timestamp": datetime.now().isoformat(),
            "scores": {
                "task_distribution": task_balance,
                "communication": communication_score,
                "conflict_resolution": conflict_resolution,
                "decision_making": decision_score,
                "overall": overall_score
            },
            "raw_metrics": {
                "communication_count": len(communication_logs),
                "task_distribution": task_distribution,
                "decision_count": len(decision_history),
                "conflict_count": len(conflict_logs)
            },
            "summary": self._generate_collaboration_summary(overall_score)
        }
        
        # 評価結果を保存
        with self.lock:
            self.evaluations["collaboration"] = evaluation_result
            self._save_evaluation("collaboration", evaluation_result)
        
        return evaluation_result
    
    def _generate_collaboration_summary(self, score: float) -> str:
        """協働評価のサマリーを生成"""
        if score >= 90:
            return "優れた協働プロセス。効率的なコミュニケーションと適切なタスク分配が行われています。"
        elif score >= 75:
            return "良好な協働プロセス。いくつかの軽微な連携の課題があります。"
        elif score >= 60:
            return "許容範囲内の協働プロセス。コミュニケーションとタスク分配に改善の余地があります。"
        elif score >= 40:
            return "改善が必要な協働プロセス。重要な連携の問題が見つかりました。"
        else:
            return "深刻な協働の問題。協働モデルの再構築が必要です。"
    
    @time_function(log_level="info")
    def evaluate_project_outcome(
        self,
        requirements_fulfillment: Dict[str, bool],
        user_feedback: List[Dict[str, Any]],
        maintainability_metrics: Dict[str, Any],
        innovation_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        プロジェクト成果の評価を実行
        
        Args:
            requirements_fulfillment: 要件の充足状況
            user_feedback: ユーザーフィードバック
            maintainability_metrics: 保守性メトリクス
            innovation_assessment: 革新性評価
            
        Returns:
            Dict[str, Any]: 評価結果
        """
        # 要件充足率の計算
        if requirements_fulfillment:
            fulfilled = sum(1 for fulfilled in requirements_fulfillment.values() if fulfilled)
            requirements_score = (fulfilled / len(requirements_fulfillment)) * 100
        else:
            requirements_score = 0
        
        # ユーザー満足度の計算
        if user_feedback:
            satisfaction_scores = [feedback.get("satisfaction", 0) for feedback in user_feedback]
            user_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)
        else:
            user_satisfaction = 0
        
        # 保守性のスコア計算
        maintainability_score = (
            maintainability_metrics.get("modularity", 0) * 0.3 +
            maintainability_metrics.get("documentation", 0) * 0.3 +
            maintainability_metrics.get("complexity", 0) * 0.4
        )
        
        # 革新性のスコア計算
        innovation_score = (
            innovation_assessment.get("novelty", 0) * 0.4 +
            innovation_assessment.get("usefulness", 0) * 0.4 +
            innovation_assessment.get("adoption", 0) * 0.2
        )
        
        # 総合成果スコアの計算
        overall_score = (
            requirements_score * 0.4 +
            user_satisfaction * 0.3 +
            maintainability_score * 0.2 +
            innovation_score * 0.1
        )
        
        # 評価結果の構築
        evaluation_result = {
            "category": "outcome",
            "timestamp": datetime.now().isoformat(),
            "scores": {
                "requirements_fulfillment": requirements_score,
                "user_satisfaction": user_satisfaction,
                "maintainability": maintainability_score,
                "innovation": innovation_score,
                "overall": overall_score
            },
            "raw_metrics": {
                "requirements": {
                    "total": len(requirements_fulfillment),
                    "fulfilled": sum(1 for fulfilled in requirements_fulfillment.values() if fulfilled)
                },
                "user_feedback_count": len(user_feedback),
                "maintainability_metrics": maintainability_metrics,
                "innovation_assessment": innovation_assessment
            },
            "summary": self._generate_outcome_summary(overall_score)
        }
        
        # 評価結果を保存
        with self.lock:
            self.evaluations["outcome"] = evaluation_result
            self._save_evaluation("outcome", evaluation_result)
        
        return evaluation_result
    
    def _generate_outcome_summary(self, score: float) -> str:
        """プロジェクト成果のサマリーを生成"""
        if score >= 90:
            return "優れた成果。要件を完全に満たし、ユーザーからの高い評価を得ています。"
        elif score >= 75:
            return "良好な成果。ほとんどの要件を満たし、ユーザーからの良好な評価があります。"
        elif score >= 60:
            return "許容範囲内の成果。いくつかの要件が不完全で、ユーザー満足度に課題があります。"
        elif score >= 40:
            return "改善が必要な成果。多くの要件が満たされていません。"
        else:
            return "プロジェクトの成果は期待を大きく下回っています。"
    
    def _save_evaluation(self, category: str, evaluation: Dict[str, Any]) -> None:
        """評価結果をファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{category}_evaluation_{timestamp}.json"
        file_path = self.evaluation_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(evaluation, f, ensure_ascii=False, indent=2)
        
        logger.info(f"評価結果を保存しました: {file_path}")
    
    @time_function(log_level="info")
    def generate_comprehensive_evaluation(self) -> Dict[str, Any]:
        """
        包括的なプロジェクト評価レポートを生成
        
        Returns:
            Dict[str, Any]: 評価レポート
        """
        with self.lock:
            # すべてのカテゴリが評価されているか確認
            if len(self.evaluations) < 4:
                missing = set(EVALUATION_CATEGORIES.keys()) - set(self.evaluations.keys())
                logger.warning(f"いくつかの評価カテゴリが未評価です: {missing}")
            
            # 各カテゴリの総合スコアを収集
            category_scores = {}
            for category, evaluation in self.evaluations.items():
                category_scores[category] = evaluation["scores"]["overall"]
            
            # 総合スコアの計算
            overall_score = 0
            weights = {
                "performance": 0.25,
                "quality": 0.3,
                "collaboration": 0.2,
                "outcome": 0.25
            }
            
            # カテゴリごとの重み付き平均を計算
            for category, score in category_scores.items():
                overall_score += score * weights.get(category, 0)
            
            # 未評価のカテゴリがある場合はスコアを調整
            if len(category_scores) < 4:
                # 評価されたカテゴリの重みの合計を計算
                evaluated_weights_sum = sum(weights[cat] for cat in category_scores.keys())
                # 正規化
                if evaluated_weights_sum > 0:
                    overall_score = overall_score / evaluated_weights_sum * 100
            
            # 強みと弱みの特定
            strengths = []
            weaknesses = []
            
            for category, subcategories in EVALUATION_CATEGORIES.items():
                if category in self.evaluations:
                    scores = self.evaluations[category]["scores"]
                    
                    # サブカテゴリのスコアをチェック
                    for subcategory in subcategories:
                        if subcategory in scores:
                            subcategory_score = scores[subcategory]
                            if subcategory_score >= 80:
                                strengths.append({
                                    "category": category,
                                    "subcategory": subcategory,
                                    "score": subcategory_score
                                })
                            elif subcategory_score <= 60:
                                weaknesses.append({
                                    "category": category,
                                    "subcategory": subcategory,
                                    "score": subcategory_score
                                })
            
            # スコアでソート
            strengths.sort(key=lambda x: x["score"], reverse=True)
            weaknesses.sort(key=lambda x: x["score"])
            
            # 改善提案の生成
            improvement_suggestions = self._generate_improvement_suggestions(weaknesses)
            
            # 評価レポートの構築
            evaluation_report = {
                "project_id": self.project.project_id,
                "title": self.project.title,
                "evaluation_date": datetime.now().isoformat(),
                "overall_score": overall_score,
                "category_scores": category_scores,
                "strengths": strengths[:5],  # 上位5つ
                "weaknesses": weaknesses[:5],  # 上位5つ
                "improvement_suggestions": improvement_suggestions,
                "summary": self._generate_overall_summary(overall_score)
            }
            
            # ファイルに保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_evaluation_{timestamp}.json"
            file_path = self.evaluation_dir / filename
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(evaluation_report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"包括的評価レポートを保存しました: {file_path}")
            
            # プロジェクトの評価メトリクスを更新
            self.project.set_evaluation_metrics({
                "overall_score": overall_score,
                "category_scores": category_scores,
                "evaluation_date": datetime.now().isoformat()
            })
            
            return evaluation_report
    
    def _generate_improvement_suggestions(self, weaknesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """弱点に基づいて改善提案を生成"""
        suggestions = []
        
        for weakness in weaknesses:
            category = weakness["category"]
            subcategory = weakness["subcategory"]
            score = weakness["score"]
            
            suggestion = {
                "category": category,
                "subcategory": subcategory,
                "score": score,
                "priority": "high" if score <= 40 else "medium" if score <= 60 else "low",
                "suggestion": ""
            }
            
            # カテゴリとサブカテゴリに応じた具体的な改善提案
            if category == "performance":
                if subcategory == "response_time":
                    suggestion["suggestion"] = "応答時間を改善するために、クエリの最適化、キャッシュの導入、非同期処理の検討を行ってください。"
                elif subcategory == "resource_usage":
                    suggestion["suggestion"] = "リソース使用量を削減するために、メモリリークを特定し、リソース使用量が多いプロセスを最適化してください。"
                elif subcategory == "code_efficiency":
                    suggestion["suggestion"] = "コードの効率性を高めるために、アルゴリズムの改善、ループの最適化、不要な処理の削除を検討してください。"
                elif subcategory == "execution_speed":
                    suggestion["suggestion"] = "実行速度を向上させるために、ボトルネックを特定し、パフォーマンスプロファイリングを行い、計算量の多い処理を最適化してください。"
            
            elif category == "quality":
                if subcategory == "code_quality":
                    suggestion["suggestion"] = "コード品質を向上させるために、リンターとコード規約の適用、コードレビューの強化、リファクタリングを定期的に行ってください。"
                elif subcategory == "architecture":
                    suggestion["suggestion"] = "アーキテクチャを改善するために、責任範囲の明確化、モジュール間の依存関係の整理、デザインパターンの適切な適用を検討してください。"
                elif subcategory == "test_coverage":
                    suggestion["suggestion"] = "テストカバレッジを向上させるために、単体テスト、統合テスト、エンドツーエンドテストの追加、テスト駆動開発の検討を行ってください。"
                elif subcategory == "documentation":
                    suggestion["suggestion"] = "ドキュメントを充実させるために、コメントの追加、APIドキュメントの整備、アーキテクチャと設計判断の記録を行ってください。"
                elif subcategory == "user_experience":
                    suggestion["suggestion"] = "ユーザーエクスペリエンスを向上させるために、ユーザビリティテストの実施、UI/UXのベストプラクティスの適用、アクセシビリティの向上を検討してください。"
            
            elif category == "collaboration":
                if subcategory == "task_distribution":
                    suggestion["suggestion"] = "タスク分配を改善するために、スキルとワークロードのバランスを考慮したタスク割り当て、明確なタスク定義と期限設定を行ってください。"
                elif subcategory == "communication":
                    suggestion["suggestion"] = "コミュニケーションを向上させるために、定期的な進捗共有、コミュニケーションツールの適切な使用、透明性の向上を図ってください。"
                elif subcategory == "conflict_resolution":
                    suggestion["suggestion"] = "紛争解決プロセスを改善するために、早期の問題特定、明確な解決プロセスの確立、建設的なフィードバックの促進を行ってください。"
                elif subcategory == "decision_making":
                    suggestion["suggestion"] = "意思決定プロセスを向上させるために、データに基づく意思決定の促進、利害関係者の適切な関与、決定の記録と共有を行ってください。"
            
            elif category == "outcome":
                if subcategory == "requirements_fulfillment":
                    suggestion["suggestion"] = "要件の充足率を向上させるために、要件の明確化、優先順位付け、定期的なレビューと検証を行ってください。"
                elif subcategory == "user_satisfaction":
                    suggestion["suggestion"] = "ユーザー満足度を向上させるために、ユーザーフィードバックの収集と分析、ユーザー中心設計の強化、定期的な改善サイクルの実施を検討してください。"
                elif subcategory == "maintainability":
                    suggestion["suggestion"] = "保守性を向上させるために、技術的負債の削減、コードの標準化、モジュール化の促進、適切な抽象化を行ってください。"
                elif subcategory == "innovation":
                    suggestion["suggestion"] = "革新性を高めるために、新しい技術やアプローチの探求、創造的な問題解決の奨励、実験のための時間と環境の確保を検討してください。"
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_overall_summary(self, score: float) -> str:
        """総合評価のサマリーを生成"""
        if score >= 90:
            return "優れたプロジェクト。ほとんどすべての評価カテゴリで高いスコアを達成し、成果物の品質と協働プロセスが非常に良好です。"
        elif score >= 75:
            return "良好なプロジェクト。いくつかの改善点はありますが、全体的に良好な成果を上げています。"
        elif score >= 60:
            return "許容範囲内のプロジェクト。いくつかの重要な改善点があり、特定の分野に注力する必要があります。"
        elif score >= 40:
            return "改善が必要なプロジェクト。複数の重要な問題があり、主要な分野での改善が必要です。"
        else:
            return "期待を下回るプロジェクト。多くの深刻な問題が見つかり、プロセスと成果物の大幅な改善が必要です。"


class EvaluationMetricsCollector:
    """プロジェクト評価のためのメトリクス収集を行うクラス"""
    
    @staticmethod
    @time_function(log_level="info")
    def collect_performance_metrics() -> Dict[str, Any]:
        """
        パフォーマンスメトリクスを収集
        
        Returns:
            Dict[str, Any]: 収集したメトリクス
        """
        # システムメトリクスを取得
        system_metrics = get_performance_metrics()
        
        # 応答時間のサンプルを取得（例としてダミーデータ）
        response_time_samples = [
            {"endpoint": "/api/v1/users", "method": "GET", "response_time_ms": 120},
            {"endpoint": "/api/v1/projects", "method": "GET", "response_time_ms": 180},
            {"endpoint": "/api/v1/data", "method": "POST", "response_time_ms": 210}
        ]
        
        # 平均応答時間を計算
        avg_response_time = statistics.mean(sample["response_time_ms"] for sample in response_time_samples)
        
        # コードメトリクス（静的解析）
        code_metrics = {
            "loc": 5000,  # コード行数
            "cyclomatic_complexity": 250,  # 循環的複雑度の合計
            "function_count": 120,  # 関数の数
            "class_count": 25,  # クラスの数
            "duplication_percentage": 4.5  # コードの重複率
        }
        
        # 実行メトリクス
        execution_metrics = {
            "avg_execution_time_ms": 150,  # 平均実行時間
            "max_execution_time_ms": 500,  # 最大実行時間
            "slow_operations_count": system_metrics["slow_operations"]
        }
        
        # リソース使用状況
        resource_usage = {
            "memory_percent": system_metrics["current_system_metrics"]["system"]["memory_percent"],
            "cpu_percent": system_metrics["current_system_metrics"]["system"]["cpu_percent"],
            "io_percent": 35.0  # ダミー値
        }
        
        return {
            "response_time": avg_response_time,
            "resource_usage": resource_usage,
            "code_metrics": code_metrics,
            "execution_metrics": execution_metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    @time_function(log_level="info")
    def collect_code_quality_metrics() -> Dict[str, Any]:
        """
        コード品質メトリクスを収集
        
        Returns:
            Dict[str, Any]: 収集したメトリクス
        """
        # 静的解析結果
        static_analysis = {
            "error_count": 5,
            "warning_count": 25,
            "info_count": 120,
            "dependency_count": 15,
            "complexity_metrics": {
                "avg_function_complexity": 5.2,
                "max_function_complexity": 25,
                "complex_functions_ratio": 0.15
            }
        }
        
        # コードレビュー結果
        code_review_results = {
            "architecture_score": 78,
            "documentation_score": 65,
            "code_style_score": 85,
            "best_practices_score": 80,
            "ux_score": 72
        }
        
        # テスト結果
        test_results = {
            "coverage_percent": 75.5,
            "passing_tests": 250,
            "failing_tests": 5,
            "skipped_tests": 10,
            "test_execution_time_ms": 3500
        }
        
        return {
            "static_analysis": static_analysis,
            "code_review_results": code_review_results,
            "test_results": test_results,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    @time_function(log_level="info")
    def collect_collaboration_metrics() -> Dict[str, Any]:
        """
        協働メトリクスを収集
        
        Returns:
            Dict[str, Any]: 収集したメトリクス
        """
        # コミュニケーションログ
        communication_logs = [
            {"type": "discussion", "topic": "アーキテクチャ設計", "participants": 4, "quality_score": 85},
            {"type": "conflict", "topic": "技術選定", "participants": 3, "quality_score": 75, "resolution_score": 80},
            {"type": "status_update", "topic": "進捗報告", "participants": 5, "quality_score": 90},
            {"type": "problem_solving", "topic": "バグ対応", "participants": 2, "quality_score": 85}
        ]
        
        # タスク分配
        task_distribution = {
            "agent_1": ["要件分析", "アーキテクチャ設計", "API設計", "ドキュメント作成"],
            "agent_2": ["フロントエンド開発", "UIテスト", "UX設計"],
            "agent_3": ["バックエンド開発", "データベース設計", "セキュリティ対応"],
            "agent_4": ["テスト計画", "自動テスト作成", "品質保証", "CI/CD設定"]
        }
        
        # 意思決定履歴
        decision_history = [
            {"topic": "フレームワーク選定", "quality_score": 90, "speed_score": 85, "consensus_level": "high"},
            {"topic": "データベース設計", "quality_score": 85, "speed_score": 75, "consensus_level": "medium"},
            {"topic": "APIデザイン", "quality_score": 80, "speed_score": 90, "consensus_level": "high"}
        ]
        
        return {
            "communication_logs": communication_logs,
            "task_distribution": task_distribution,
            "decision_history": decision_history,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    @time_function(log_level="info")
    def collect_outcome_metrics(project: PilotProject) -> Dict[str, Any]:
        """
        プロジェクト成果メトリクスを収集
        
        Args:
            project: 評価対象のプロジェクト
            
        Returns:
            Dict[str, Any]: 収集したメトリクス
        """
        # 要件充足状況（プロジェクトの要件から生成）
        requirements_fulfillment = {}
        for i, req in enumerate(project.requirements):
            # 80%の確率で要件を満たしているとする（デモ用）
            requirements_fulfillment[f"req_{i+1}"] = (i % 5 != 0)  # 5の倍数のインデックスのみFalse
        
        # ユーザーフィードバック
        user_feedback = [
            {"user_type": "一般ユーザー", "satisfaction": 85, "usability": 80, "comments": "使いやすいインターフェース"},
            {"user_type": "管理者", "satisfaction": 75, "usability": 70, "comments": "一部の管理機能が見つけにくい"},
            {"user_type": "開発者", "satisfaction": 90, "usability": 85, "comments": "APIドキュメントが充実している"}
        ]
        
        # 保守性メトリクス
        maintainability_metrics = {
            "modularity": 80,
            "documentation": 75,
            "complexity": 70,
            "test_coverage": 75.5,
            "dependency_management": 85
        }
        
        # 革新性評価
        innovation_assessment = {
            "novelty": 65,
            "usefulness": 85,
            "adoption": 70,
            "market_potential": 75
        }
        
        return {
            "requirements_fulfillment": requirements_fulfillment,
            "user_feedback": user_feedback,
            "maintainability_metrics": maintainability_metrics,
            "innovation_assessment": innovation_assessment,
            "timestamp": datetime.now().isoformat()
        }


def evaluate_project_automatically(project: PilotProject) -> Dict[str, Any]:
    """
    プロジェクトを自動的に評価
    
    Args:
        project: 評価対象のプロジェクト
        
    Returns:
        Dict[str, Any]: 評価レポート
    """
    logger.info(f"プロジェクト {project.project_id} の自動評価を開始します")
    
    # 評価対象がまだ完了していない場合は警告
    if project.status not in ["completed", "evaluated"]:
        logger.warning(f"プロジェクト {project.project_id} はまだ完了していません (status: {project.status})")
    
    # 評価器を初期化
    evaluator = ProjectEvaluator(project)
    
    # メトリクス収集
    performance_metrics = EvaluationMetricsCollector.collect_performance_metrics()
    code_quality_metrics = EvaluationMetricsCollector.collect_code_quality_metrics()
    collaboration_metrics = EvaluationMetricsCollector.collect_collaboration_metrics()
    outcome_metrics = EvaluationMetricsCollector.collect_outcome_metrics(project)
    
    # カテゴリ別評価を実行
    evaluator.evaluate_performance(
        performance_metrics["response_time"],
        performance_metrics["resource_usage"],
        performance_metrics["code_metrics"],
        performance_metrics["execution_metrics"]
    )
    
    evaluator.evaluate_code_quality(
        code_quality_metrics["static_analysis"],
        code_quality_metrics["code_review_results"],
        code_quality_metrics["test_results"]
    )
    
    evaluator.evaluate_collaboration(
        collaboration_metrics["communication_logs"],
        collaboration_metrics["task_distribution"],
        collaboration_metrics["decision_history"]
    )
    
    evaluator.evaluate_project_outcome(
        outcome_metrics["requirements_fulfillment"],
        outcome_metrics["user_feedback"],
        outcome_metrics["maintainability_metrics"],
        outcome_metrics["innovation_assessment"]
    )
    
    # 包括的な評価レポートを生成
    evaluation_report = evaluator.generate_comprehensive_evaluation()
    
    logger.info(f"プロジェクト {project.project_id} の自動評価が完了しました")
    
    return evaluation_report 