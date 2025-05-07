"""
外部シークレットマネージャー連携モジュール。
GCP Secret Managerなどの外部シークレットマネージャーとの連携機能を提供します。
"""

import os
import json
import base64
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import logging

# 将来の拡張性のためにABCを使用
from abc import ABC, abstractmethod

# ロギング設定
try:
    from utils.logger import get_structured_logger
    logger = get_structured_logger("secret_manager")
except ImportError:
    # フォールバックロガー
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("secret_manager")


class SecretManagerBase(ABC):
    """シークレットマネージャーのベースクラス"""
    
    @abstractmethod
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """シークレットを取得する"""
        pass
    
    @abstractmethod
    def create_secret(self, secret_name: str, secret_value: str, labels: Dict[str, str] = None) -> bool:
        """シークレットを作成する"""
        pass
    
    @abstractmethod
    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを更新する"""
        pass
    
    @abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除する"""
        pass
    
    @abstractmethod
    def list_secrets(self, filter_criteria: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """シークレットの一覧を取得する"""
        pass


class LocalSecretManager(SecretManagerBase):
    """ローカルファイルシステムを使用したシークレットマネージャー"""
    
    def __init__(self, storage_path: str = "storage/secrets"):
        """
        Args:
            storage_path: シークレットを保存するディレクトリのパス
        """
        self.storage_path = os.path.abspath(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        logger.info(f"ローカルシークレットマネージャーを初期化しました。保存先: {self.storage_path}")
    
    def _get_secret_path(self, secret_name: str) -> str:
        """シークレットファイルのパスを取得する"""
        # シークレット名にパス区切り文字やドットが含まれている場合、安全な形式に変換
        safe_name = base64.urlsafe_b64encode(secret_name.encode()).decode()
        return os.path.join(self.storage_path, f"{safe_name}.json")
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """シークレットを取得する"""
        try:
            secret_path = self._get_secret_path(secret_name)
            
            if not os.path.exists(secret_path):
                logger.warning(f"シークレット {secret_name} が見つかりません")
                return None
            
            with open(secret_path, "r") as f:
                secret_data = json.load(f)
            
            # バージョン管理
            if version == "latest":
                # 最新バージョンを返す
                versions = sorted(secret_data["versions"], key=lambda x: x["created_at"], reverse=True)
                if not versions:
                    return None
                return versions[0]["value"]
            else:
                # 指定したバージョンを返す
                for ver in secret_data["versions"]:
                    if ver["version"] == version:
                        return ver["value"]
                
                logger.warning(f"シークレット {secret_name} のバージョン {version} が見つかりません")
                return None
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の取得に失敗しました: {str(e)}")
            return None
    
    def create_secret(self, secret_name: str, secret_value: str, labels: Dict[str, str] = None) -> bool:
        """シークレットを作成する"""
        try:
            secret_path = self._get_secret_path(secret_name)
            
            # 既存のシークレットをチェック
            if os.path.exists(secret_path):
                with open(secret_path, "r") as f:
                    secret_data = json.load(f)
            else:
                # 新しいシークレットを作成
                secret_data = {
                    "name": secret_name,
                    "created_at": datetime.now().isoformat(),
                    "labels": labels or {},
                    "versions": []
                }
            
            # 新しいバージョンを追加
            version_id = f"v{len(secret_data['versions']) + 1}"
            version_data = {
                "version": version_id,
                "value": secret_value,
                "created_at": datetime.now().isoformat()
            }
            
            secret_data["versions"].append(version_data)
            secret_data["updated_at"] = datetime.now().isoformat()
            
            # シークレットを保存
            with open(secret_path, "w") as f:
                json.dump(secret_data, f, indent=2)
            
            logger.info(f"シークレット {secret_name} を作成/更新しました（バージョン: {version_id}）")
            return True
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の作成に失敗しました: {str(e)}")
            return False
    
    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを更新する（新しいバージョンを作成）"""
        return self.create_secret(secret_name, secret_value)
    
    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除する"""
        try:
            secret_path = self._get_secret_path(secret_name)
            
            if not os.path.exists(secret_path):
                logger.warning(f"シークレット {secret_name} が見つかりません")
                return False
            
            # ファイルを削除
            os.remove(secret_path)
            logger.info(f"シークレット {secret_name} を削除しました")
            return True
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の削除に失敗しました: {str(e)}")
            return False
    
    def list_secrets(self, filter_criteria: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """シークレットの一覧を取得する"""
        try:
            secrets = []
            
            for filename in os.listdir(self.storage_path):
                if not filename.endswith(".json"):
                    continue
                
                try:
                    with open(os.path.join(self.storage_path, filename), "r") as f:
                        secret_data = json.load(f)
                    
                    # フィルター条件に一致するかチェック
                    if filter_criteria:
                        match = True
                        for key, value in filter_criteria.items():
                            if key == "name":
                                if value not in secret_data["name"]:
                                    match = False
                                    break
                            elif key == "label":
                                label_key, label_value = value.split(":", 1)
                                if label_key not in secret_data["labels"] or secret_data["labels"][label_key] != label_value:
                                    match = False
                                    break
                        
                        if not match:
                            continue
                    
                    # バージョン情報を除外（値自体は返さない）
                    secret_info = {
                        "name": secret_data["name"],
                        "created_at": secret_data["created_at"],
                        "updated_at": secret_data.get("updated_at", secret_data["created_at"]),
                        "labels": secret_data["labels"],
                        "version_count": len(secret_data["versions"]),
                        "latest_version": f"v{len(secret_data['versions'])}" if secret_data["versions"] else None
                    }
                    
                    secrets.append(secret_info)
                
                except Exception as e:
                    logger.warning(f"シークレットファイル {filename} の読み込みに失敗しました: {str(e)}")
            
            return secrets
        
        except Exception as e:
            logger.error(f"シークレット一覧の取得に失敗しました: {str(e)}")
            return []


class GCPSecretManager(SecretManagerBase):
    """Google Cloud Secret Managerを使用したシークレットマネージャー"""
    
    def __init__(self, project_id: str = None):
        """
        Args:
            project_id: GCPプロジェクトID（None の場合は環境変数から取得）
        """
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID環境変数またはproject_idパラメータを設定してください")
        
        try:
            # GCPクライアントライブラリをインポート
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
            logger.info(f"GCP Secret Managerを初期化しました。プロジェクト: {self.project_id}")
        except ImportError:
            logger.error("google-cloud-secret-managerパッケージがインストールされていません")
            raise ImportError("GCP Secret Managerを使用するには 'pip install google-cloud-secret-manager' を実行してください")
    
    def _get_secret_path(self, secret_name: str) -> str:
        """シークレットのフルパスを取得する"""
        return f"projects/{self.project_id}/secrets/{secret_name}"
    
    def _get_secret_version_path(self, secret_name: str, version: str) -> str:
        """シークレットバージョンのフルパスを取得する"""
        return f"{self._get_secret_path(secret_name)}/versions/{version}"
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """シークレットを取得する"""
        try:
            name = self._get_secret_version_path(secret_name, version)
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"シークレット {secret_name} の取得に失敗しました: {str(e)}")
            return None
    
    def create_secret(self, secret_name: str, secret_value: str, labels: Dict[str, str] = None) -> bool:
        """シークレットを作成する"""
        try:
            parent = f"projects/{self.project_id}"
            
            # シークレットが存在するかチェック
            try:
                self.client.get_secret(request={"name": self._get_secret_path(secret_name)})
                # 既に存在する場合は新しいバージョンを追加
                return self.update_secret(secret_name, secret_value)
            except Exception:
                # シークレットが存在しない場合は新規作成
                pass
            
            # シークレットを作成
            secret = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {
                        "replication": {"automatic": {}},
                        "labels": labels or {},
                    },
                }
            )
            
            # シークレット値を設定
            self.client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"シークレット {secret_name} を作成しました")
            return True
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の作成に失敗しました: {str(e)}")
            return False
    
    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """シークレットを更新する（新しいバージョンを作成）"""
        try:
            parent = self._get_secret_path(secret_name)
            
            # 新しいバージョンを追加
            self.client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"シークレット {secret_name} を更新しました")
            return True
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の更新に失敗しました: {str(e)}")
            return False
    
    def delete_secret(self, secret_name: str) -> bool:
        """シークレットを削除する"""
        try:
            name = self._get_secret_path(secret_name)
            self.client.delete_secret(request={"name": name})
            logger.info(f"シークレット {secret_name} を削除しました")
            return True
        
        except Exception as e:
            logger.error(f"シークレット {secret_name} の削除に失敗しました: {str(e)}")
            return False
    
    def list_secrets(self, filter_criteria: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """シークレットの一覧を取得する"""
        try:
            parent = f"projects/{self.project_id}"
            
            # フィルター文字列を構築
            filter_str = ""
            if filter_criteria:
                conditions = []
                for key, value in filter_criteria.items():
                    if key == "name":
                        conditions.append(f"name:{value}")
                    elif key == "label":
                        conditions.append(f"labels.{value}")
                
                if conditions:
                    filter_str = " AND ".join(conditions)
            
            # シークレット一覧を取得
            response = self.client.list_secrets(request={"parent": parent, "filter": filter_str})
            
            secrets = []
            for secret in response:
                # バージョン情報を取得
                versions_response = self.client.list_secret_versions(request={"parent": secret.name})
                version_count = sum(1 for _ in versions_response)
                
                secret_info = {
                    "name": secret.name.split("/")[-1],
                    "created_at": secret.create_time.isoformat() if hasattr(secret, "create_time") else None,
                    "labels": dict(secret.labels) if hasattr(secret, "labels") else {},
                    "version_count": version_count,
                }
                
                secrets.append(secret_info)
            
            return secrets
        
        except Exception as e:
            logger.error(f"シークレット一覧の取得に失敗しました: {str(e)}")
            return []


# シークレットマネージャーの選択
def get_secret_manager() -> SecretManagerBase:
    """
    設定に基づいて適切なシークレットマネージャーを返す
    
    Returns:
        SecretManagerBase: シークレットマネージャーのインスタンス
    """
    # 環境変数から設定を取得
    secret_manager_type = os.environ.get("SECRET_MANAGER_TYPE", "local").lower()
    
    if secret_manager_type == "gcp":
        try:
            return GCPSecretManager()
        except (ImportError, ValueError) as e:
            logger.warning(f"GCP Secret Managerの初期化に失敗しました: {str(e)}。ローカルシークレットマネージャーにフォールバックします。")
            return LocalSecretManager()
    else:
        return LocalSecretManager()


# シングルトンインスタンス
secret_manager = get_secret_manager()


# ヘルパー関数
def get_secret(secret_name: str, version: str = "latest") -> Optional[str]:
    """
    シークレットを取得するヘルパー関数
    
    Args:
        secret_name: シークレット名
        version: バージョン（"latest"または具体的なバージョン番号）
        
    Returns:
        Optional[str]: シークレット値
    """
    return secret_manager.get_secret(secret_name, version)


def create_secret(secret_name: str, secret_value: str, labels: Dict[str, str] = None) -> bool:
    """
    シークレットを作成するヘルパー関数
    
    Args:
        secret_name: シークレット名
        secret_value: シークレット値
        labels: ラベル（キーと値のマッピング）
        
    Returns:
        bool: 成功したらTrue
    """
    return secret_manager.create_secret(secret_name, secret_value, labels)


def update_secret(secret_name: str, secret_value: str) -> bool:
    """
    シークレットを更新するヘルパー関数
    
    Args:
        secret_name: シークレット名
        secret_value: 新しいシークレット値
        
    Returns:
        bool: 成功したらTrue
    """
    return secret_manager.update_secret(secret_name, secret_value)


def delete_secret(secret_name: str) -> bool:
    """
    シークレットを削除するヘルパー関数
    
    Args:
        secret_name: シークレット名
        
    Returns:
        bool: 成功したらTrue
    """
    return secret_manager.delete_secret(secret_name)


def list_secrets(filter_criteria: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    シークレットの一覧を取得するヘルパー関数
    
    Args:
        filter_criteria: フィルター条件
        
    Returns:
        List[Dict[str, Any]]: シークレット情報のリスト
    """
    return secret_manager.list_secrets(filter_criteria) 