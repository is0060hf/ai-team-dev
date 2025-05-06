"""
パイロットプロジェクト管理モジュール。
AIエージェントチームを使った小規模Webプロジェクトの計画、実行、評価を管理するための機能を提供します。
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from pathlib import Path
import threading

from utils.logger import get_structured_logger
from utils.tracing import trace, trace_span
from utils.performance import time_function, collect_system_metrics
from utils.caching import cached

# ロガーの設定
logger = get_structured_logger("pilot_project")

class PilotProject:
    """パイロットプロジェクトを管理するクラス"""
    
    def __init__(
        self,
        project_id: str,
        title: str,
        description: str,
        requirements: List[str],
        storage_dir: str = "storage/pilot_projects"
    ):
        """
        Args:
            project_id: プロジェクトID
            title: プロジェクトタイトル
            description: プロジェクト説明
            requirements: 要件リスト
            storage_dir: ストレージディレクトリ
        """
        self.project_id = project_id
        self.title = title
        self.description = description
        self.requirements = requirements
        self.storage_dir = Path(storage_dir)
        self.project_dir = self.storage_dir / project_id
        
        # プロジェクト状態
        self.status = "planning"  # planning, in_progress, completed, evaluated
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # 評価メトリクス
        self.evaluation_metrics: Dict[str, Any] = {}
        
        # スレッドロック
        self.lock = threading.RLock()
        
        # ストレージディレクトリを作成
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # メタデータファイルのパス
        self.metadata_file = self.project_dir / "metadata.json"
        
        # 初期メタデータの保存
        self._save_metadata()
    
    def _save_metadata(self) -> None:
        """メタデータをディスクに保存"""
        metadata = {
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "requirements": self.requirements,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "evaluation_metrics": self.evaluation_metrics,
            "last_updated": datetime.now().isoformat()
        }
        
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_project(cls, project_id: str, storage_dir: str = "storage/pilot_projects") -> "PilotProject":
        """
        既存のプロジェクトを読み込む
        
        Args:
            project_id: プロジェクトID
            storage_dir: ストレージディレクトリ
            
        Returns:
            PilotProject: プロジェクトインスタンス
            
        Raises:
            FileNotFoundError: プロジェクトが見つからない場合
        """
        project_dir = Path(storage_dir) / project_id
        metadata_file = project_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"プロジェクト {project_id} が見つかりません")
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        project = cls(
            project_id=metadata["project_id"],
            title=metadata["title"],
            description=metadata["description"],
            requirements=metadata["requirements"],
            storage_dir=storage_dir
        )
        
        project.status = metadata["status"]
        
        if metadata["start_time"]:
            project.start_time = datetime.fromisoformat(metadata["start_time"])
        
        if metadata["end_time"]:
            project.end_time = datetime.fromisoformat(metadata["end_time"])
        
        project.evaluation_metrics = metadata["evaluation_metrics"]
        
        return project
    
    @staticmethod
    def list_projects(storage_dir: str = "storage/pilot_projects") -> List[Dict[str, Any]]:
        """
        利用可能なプロジェクトのリストを取得
        
        Args:
            storage_dir: ストレージディレクトリ
            
        Returns:
            List[Dict[str, Any]]: プロジェクトのリスト
        """
        projects = []
        storage_path = Path(storage_dir)
        
        if not storage_path.exists():
            return []
        
        for project_dir in storage_path.iterdir():
            if project_dir.is_dir():
                metadata_file = project_dir / "metadata.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        
                        projects.append({
                            "project_id": metadata["project_id"],
                            "title": metadata["title"],
                            "status": metadata["status"],
                            "last_updated": metadata.get("last_updated")
                        })
                    except Exception as e:
                        logger.error(f"プロジェクトメタデータの読み込みに失敗しました: {str(e)}")
        
        # 最終更新日時でソート
        projects.sort(key=lambda p: p.get("last_updated", ""), reverse=True)
        
        return projects
    
    @time_function(log_level="info")
    def start_project(self) -> None:
        """プロジェクトを開始"""
        with self.lock:
            if self.status != "planning":
                logger.warning(f"プロジェクト {self.project_id} は既に開始されています")
                return
            
            self.status = "in_progress"
            self.start_time = datetime.now()
            
            logger.info(f"プロジェクト {self.project_id} を開始しました")
            
            self._save_metadata()
    
    @time_function(log_level="info")
    def complete_project(self) -> None:
        """プロジェクトを完了"""
        with self.lock:
            if self.status != "in_progress":
                logger.warning(f"プロジェクト {self.project_id} は進行中ではありません")
                return
            
            self.status = "completed"
            self.end_time = datetime.now()
            
            logger.info(f"プロジェクト {self.project_id} を完了しました")
            
            self._save_metadata()
    
    def set_evaluation_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        評価メトリクスを設定
        
        Args:
            metrics: 評価メトリクス
        """
        with self.lock:
            self.evaluation_metrics = metrics
            self.status = "evaluated"
            
            logger.info(f"プロジェクト {self.project_id} の評価メトリクスを設定しました")
            
            self._save_metadata()
    
    def add_artifact(self, artifact_type: str, content: Any, filename: Optional[str] = None) -> str:
        """
        プロジェクトアーティファクトを追加
        
        Args:
            artifact_type: アーティファクトタイプ（code, design, documentation, evaluation等）
            content: アーティファクト内容
            filename: ファイル名（指定しない場合は自動生成）
            
        Returns:
            str: 保存したファイルのパス
        """
        # アーティファクトディレクトリを作成
        artifact_dir = self.project_dir / artifact_type
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル名が指定されていない場合は生成
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{artifact_type}_{timestamp}.json"
        
        # パスを構築
        file_path = artifact_dir / filename
        
        # 内容を保存（文字列またはJSONシリアライズ可能なオブジェクト）
        if isinstance(content, str):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        
        logger.info(f"プロジェクト {self.project_id} にアーティファクト {filename} を追加しました")
        
        return str(file_path)
    
    def get_artifacts(self, artifact_type: Optional[str] = None) -> Dict[str, List[str]]:
        """
        プロジェクトのアーティファクトを取得
        
        Args:
            artifact_type: アーティファクトタイプ（指定しない場合はすべて）
            
        Returns:
            Dict[str, List[str]]: アーティファクトのリスト（タイプごと）
        """
        artifacts = {}
        
        if artifact_type:
            # 特定タイプのみ
            artifact_dir = self.project_dir / artifact_type
            if artifact_dir.exists():
                artifacts[artifact_type] = [str(f.name) for f in artifact_dir.iterdir() if f.is_file()]
        else:
            # すべてのタイプ
            for dir_path in self.project_dir.iterdir():
                if dir_path.is_dir() and dir_path.name != "__pycache__":
                    artifacts[dir_path.name] = [str(f.name) for f in dir_path.iterdir() if f.is_file()]
        
        return artifacts
    
    def get_artifact_content(self, artifact_type: str, filename: str) -> Any:
        """
        アーティファクトの内容を取得
        
        Args:
            artifact_type: アーティファクトタイプ
            filename: ファイル名
            
        Returns:
            Any: アーティファクトの内容
            
        Raises:
            FileNotFoundError: アーティファクトが見つからない場合
        """
        file_path = self.project_dir / artifact_type / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"アーティファクト {filename} が見つかりません")
        
        # 拡張子に応じて読み込み方法を変更
        if file_path.suffix.lower() == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        プロジェクトの概要を取得
        
        Returns:
            Dict[str, Any]: プロジェクト概要
        """
        with self.lock:
            duration = None
            if self.start_time:
                if self.end_time:
                    duration = (self.end_time - self.start_time).total_seconds()
                else:
                    duration = (datetime.now() - self.start_time).total_seconds()
            
            # アーティファクトのカウント
            artifact_counts = {}
            for artifact_type, files in self.get_artifacts().items():
                artifact_counts[artifact_type] = len(files)
            
            return {
                "project_id": self.project_id,
                "title": self.title,
                "description": self.description,
                "status": self.status,
                "requirements_count": len(self.requirements),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": duration,
                "artifacts": artifact_counts,
                "evaluation_metrics": self.evaluation_metrics
            }


class PilotProjectManager:
    """パイロットプロジェクトを管理するマネージャークラス"""
    
    def __init__(self, storage_dir: str = "storage/pilot_projects"):
        """
        Args:
            storage_dir: ストレージディレクトリ
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_projects: Dict[str, PilotProject] = {}
    
    def create_project(
        self,
        title: str,
        description: str,
        requirements: List[str],
        project_id: Optional[str] = None
    ) -> PilotProject:
        """
        新しいプロジェクトを作成
        
        Args:
            title: プロジェクトタイトル
            description: プロジェクト説明
            requirements: 要件リスト
            project_id: プロジェクトID（指定しない場合は自動生成）
            
        Returns:
            PilotProject: 作成されたプロジェクト
        """
        # プロジェクトIDを生成（指定されていない場合）
        if project_id is None:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            project_id = f"pilot_{timestamp}"
        
        # プロジェクトを作成
        project = PilotProject(
            project_id=project_id,
            title=title,
            description=description,
            requirements=requirements,
            storage_dir=str(self.storage_dir)
        )
        
        # アクティブプロジェクトに追加
        self.active_projects[project_id] = project
        
        logger.info(f"新しいパイロットプロジェクト {project_id} を作成しました")
        
        return project
    
    def get_project(self, project_id: str) -> PilotProject:
        """
        プロジェクトを取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            PilotProject: プロジェクト
            
        Raises:
            FileNotFoundError: プロジェクトが見つからない場合
        """
        # アクティブプロジェクトにあるかチェック
        if project_id in self.active_projects:
            return self.active_projects[project_id]
        
        # ディスクから読み込み
        project = PilotProject.load_project(project_id, str(self.storage_dir))
        
        # アクティブプロジェクトに追加
        self.active_projects[project_id] = project
        
        return project
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        利用可能なプロジェクトのリストを取得
        
        Returns:
            List[Dict[str, Any]]: プロジェクトのリスト
        """
        return PilotProject.list_projects(str(self.storage_dir))
    
    def delete_project(self, project_id: str) -> bool:
        """
        プロジェクトを削除
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        # アクティブプロジェクトから削除
        if project_id in self.active_projects:
            del self.active_projects[project_id]
        
        # ディスクから削除
        project_dir = self.storage_dir / project_id
        
        if not project_dir.exists():
            return False
        
        try:
            # ディレクトリを再帰的に削除
            shutil.rmtree(project_dir)
            logger.info(f"プロジェクト {project_id} を削除しました")
            return True
        except Exception as e:
            logger.error(f"プロジェクト {project_id} の削除に失敗しました: {str(e)}")
            return False
    
    @time_function(log_level="info")
    def run_project_workflow(self, project_id: str) -> Dict[str, Any]:
        """
        プロジェクトワークフローを実行
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            Dict[str, Any]: 実行結果
        """
        project = self.get_project(project_id)
        
        # プロジェクトを開始
        project.start_project()
        
        try:
            # TODO: 実際のエージェントチームによるプロジェクト実行ロジックをここに実装
            # この部分はプロジェクトの実装に応じて変更する必要があります
            
            # 実行結果を記録
            result = {
                "status": "success",
                "message": "プロジェクトワークフローを実行しました",
                "timestamp": datetime.now().isoformat()
            }
            
            # プロジェクトを完了
            project.complete_project()
            
            # アーティファクトとして結果を保存
            project.add_artifact("workflow", result, "workflow_result.json")
            
            return result
        
        except Exception as e:
            logger.error(f"プロジェクトワークフロー実行中にエラーが発生しました: {str(e)}")
            
            # エラー情報を記録
            error_info = {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            # アーティファクトとしてエラーを保存
            project.add_artifact("errors", error_info, "workflow_error.json")
            
            return error_info


# グローバルインスタンス
pilot_project_manager = PilotProjectManager() 