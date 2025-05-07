"""
APIキーローテーション管理モジュール。
APIキーの自動ローテーション機能を提供します。
"""

import os
import time
import json
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple

from utils.logger import get_structured_logger
from utils.api_key_manager import (
    APIKey, api_key_manager, create_api_key, get_api_keys, revoke_api_key
)
from utils.notification import send_notification

# ロガーの設定
logger = get_structured_logger("api_key_rotation")


class APIKeyRotationManager:
    """APIキーの自動ローテーションを管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/api_key_rotation"):
        """
        Args:
            storage_path: ローテーション設定を保存するディレクトリのパス
        """
        self.storage_path = os.path.abspath(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        self.rotations = {}  # owner -> rotation_config
        self.rotation_scheduler = None
        self.load_rotations()
    
    def load_rotations(self):
        """保存されているローテーション設定を読み込む"""
        try:
            config_path = os.path.join(self.storage_path, "rotations.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
                    for owner, rotation_config in data.items():
                        self.rotations[owner] = rotation_config
                
                logger.info(f"{len(self.rotations)} 件のキーローテーション設定を読み込みました")
        except Exception as e:
            logger.error(f"キーローテーション設定の読み込みに失敗しました: {str(e)}")
    
    def save_rotations(self):
        """ローテーション設定を保存する"""
        try:
            config_path = os.path.join(self.storage_path, "rotations.json")
            with open(config_path, "w") as f:
                json.dump(self.rotations, f, indent=2)
            logger.info("キーローテーション設定を保存しました")
        except Exception as e:
            logger.error(f"キーローテーション設定の保存に失敗しました: {str(e)}")
    
    def setup_rotation(
        self, 
        owner: str, 
        interval_days: int, 
        permissions: List[str],
        overlap_days: int = 7,
        max_keys: int = 2,
        notify_emails: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        APIキーのローテーションを設定する
        
        Args:
            owner: キーの所有者
            interval_days: ローテーション間隔（日数）
            permissions: 新しいキーに付与する権限リスト
            overlap_days: 新旧キーの重複期間（日数）
            max_keys: 同時に有効にできるキーの最大数
            notify_emails: 通知先メールアドレスリスト
            metadata: キーのメタデータ
            
        Returns:
            bool: 成功したらTrue
        """
        try:
            # ローテーション設定を作成
            rotation_config = {
                "owner": owner,
                "interval_days": interval_days,
                "permissions": permissions,
                "overlap_days": overlap_days,
                "max_keys": max_keys,
                "notify_emails": notify_emails or [],
                "metadata": metadata or {},
                "next_rotation": datetime.now().isoformat(),
                "enabled": True,
                "last_rotation": None,
                "active_keys": []
            }
            
            # 設定を保存
            self.rotations[owner] = rotation_config
            self.save_rotations()
            
            # 初回のキーを生成
            result = self.rotate_key(owner)
            
            logger.info(f"{owner} のAPIキーローテーションを設定しました（間隔: {interval_days}日）")
            return result
        
        except Exception as e:
            logger.error(f"{owner} のAPIキーローテーション設定に失敗しました: {str(e)}")
            return False
    
    def rotate_key(self, owner: str) -> bool:
        """
        指定された所有者のAPIキーをローテーションする
        
        Args:
            owner: キーの所有者
            
        Returns:
            bool: 成功したらTrue
        """
        try:
            # ローテーション設定を取得
            if owner not in self.rotations or not self.rotations[owner]["enabled"]:
                logger.warning(f"{owner} のAPIキーローテーション設定がないか、無効化されています")
                return False
            
            rotation_config = self.rotations[owner]
            
            # 新しいキーを作成
            expires_in_days = rotation_config["interval_days"] + rotation_config["overlap_days"]
            metadata = rotation_config["metadata"].copy()
            metadata["rotation_source"] = "automated"
            metadata["rotation_timestamp"] = datetime.now().isoformat()
            
            api_key_str, api_key = create_api_key(
                owner=owner,
                permissions=rotation_config["permissions"],
                expires_in_days=expires_in_days,
                metadata=metadata
            )
            
            # アクティブキーリストを更新
            rotation_config["active_keys"].append(api_key.key_id)
            
            # 最大数を超えるキーを無効化
            active_keys = get_api_keys(owner)
            active_key_ids = [key.key_id for key in active_keys if key.is_valid()]
            
            if len(active_key_ids) > rotation_config["max_keys"]:
                # 最も古いキーを無効化
                keys_to_revoke = sorted(
                    active_keys, 
                    key=lambda k: k.created_at
                )[:len(active_key_ids) - rotation_config["max_keys"]]
                
                for key in keys_to_revoke:
                    revoke_api_key(key.key_id)
                    if key.key_id in rotation_config["active_keys"]:
                        rotation_config["active_keys"].remove(key.key_id)
            
            # 次回のローテーション日時を設定
            next_rotation = datetime.now() + timedelta(days=rotation_config["interval_days"])
            rotation_config["last_rotation"] = datetime.now().isoformat()
            rotation_config["next_rotation"] = next_rotation.isoformat()
            
            # 設定を保存
            self.save_rotations()
            
            # 通知を送信
            if rotation_config["notify_emails"]:
                self._send_rotation_notification(owner, api_key_str, api_key, rotation_config)
            
            logger.info(f"{owner} のAPIキーをローテーションしました（次回: {next_rotation.isoformat()}）")
            return True
        
        except Exception as e:
            logger.error(f"{owner} のAPIキーローテーションに失敗しました: {str(e)}")
            return False
    
    def _send_rotation_notification(
        self, 
        owner: str, 
        api_key_str: str, 
        api_key: APIKey, 
        rotation_config: Dict[str, Any]
    ):
        """
        ローテーション通知を送信する
        
        Args:
            owner: キーの所有者
            api_key_str: 平文のAPIキー
            api_key: APIKeyオブジェクト
            rotation_config: ローテーション設定
        """
        try:
            # 通知内容
            subject = f"[重要] {owner} のAPIキーがローテーションされました"
            
            # キーの有効期限を日付形式で表示
            expires_at = api_key.expires_at.strftime("%Y-%m-%d %H:%M:%S") if api_key.expires_at else "無期限"
            
            message = f"""
APIキーがローテーションされました。

所有者: {owner}
新しいAPIキー: {api_key_str}
有効期限: {expires_at}
権限: {', '.join(api_key.permissions)}

注意: このAPIキーは秘密情報です。安全に管理してください。
次回のローテーション予定日: {datetime.fromisoformat(rotation_config['next_rotation']).strftime('%Y-%m-%d')}

このメールは自動送信されています。
"""
            
            # 通知を送信
            for email in rotation_config["notify_emails"]:
                send_notification(
                    recipient=email,
                    subject=subject,
                    message=message,
                    notification_type="api_key_rotation"
                )
            
            logger.info(f"{owner} のAPIキーローテーション通知を送信しました")
        
        except Exception as e:
            logger.error(f"APIキーローテーション通知の送信に失敗しました: {str(e)}")
    
    def disable_rotation(self, owner: str) -> bool:
        """
        APIキーのローテーションを無効化する
        
        Args:
            owner: キーの所有者
            
        Returns:
            bool: 成功したらTrue
        """
        if owner not in self.rotations:
            logger.warning(f"{owner} のAPIキーローテーション設定が見つかりません")
            return False
        
        try:
            self.rotations[owner]["enabled"] = False
            self.save_rotations()
            logger.info(f"{owner} のAPIキーローテーションを無効化しました")
            return True
        
        except Exception as e:
            logger.error(f"{owner} のAPIキーローテーション無効化に失敗しました: {str(e)}")
            return False
    
    def enable_rotation(self, owner: str) -> bool:
        """
        APIキーのローテーションを有効化する
        
        Args:
            owner: キーの所有者
            
        Returns:
            bool: 成功したらTrue
        """
        if owner not in self.rotations:
            logger.warning(f"{owner} のAPIキーローテーション設定が見つかりません")
            return False
        
        try:
            self.rotations[owner]["enabled"] = True
            
            # 最後のローテーションから長時間経過している場合は即時ローテーション
            if self.rotations[owner]["last_rotation"]:
                last_rotation = datetime.fromisoformat(self.rotations[owner]["last_rotation"])
                interval = timedelta(days=self.rotations[owner]["interval_days"])
                
                if datetime.now() - last_rotation > interval:
                    # 次回のローテーションを今すぐに設定
                    self.rotations[owner]["next_rotation"] = datetime.now().isoformat()
            
            self.save_rotations()
            logger.info(f"{owner} のAPIキーローテーションを有効化しました")
            return True
        
        except Exception as e:
            logger.error(f"{owner} のAPIキーローテーション有効化に失敗しました: {str(e)}")
            return False
    
    def get_rotation(self, owner: str) -> Optional[Dict[str, Any]]:
        """
        ローテーション設定を取得する
        
        Args:
            owner: キーの所有者
            
        Returns:
            Optional[Dict[str, Any]]: ローテーション設定
        """
        if owner not in self.rotations:
            return None
        
        return self.rotations[owner].copy()
    
    def list_rotations(self) -> List[Dict[str, Any]]:
        """
        すべてのローテーション設定を取得する
        
        Returns:
            List[Dict[str, Any]]: ローテーション設定のリスト
        """
        return [config.copy() for owner, config in self.rotations.items()]
    
    def check_pending_rotations(self):
        """保留中のローテーションを確認して実行する"""
        now = datetime.now()
        
        for owner, config in self.rotations.items():
            if not config["enabled"]:
                continue
            
            next_rotation = datetime.fromisoformat(config["next_rotation"])
            
            if now >= next_rotation:
                logger.info(f"{owner} のAPIキーローテーション期限が到来しました")
                self.rotate_key(owner)
    
    def start_rotation_scheduler(self, interval_minutes: int = 60):
        """
        バックグラウンドでローテーションスケジューラを開始する
        
        Args:
            interval_minutes: チェック間隔（分）
        """
        def _scheduler_task():
            while True:
                try:
                    self.check_pending_rotations()
                except Exception as e:
                    logger.error(f"ローテーションスケジューラでエラーが発生しました: {str(e)}")
                
                time.sleep(interval_minutes * 60)
        
        if self.rotation_scheduler is None or not self.rotation_scheduler.is_alive():
            self.rotation_scheduler = threading.Thread(
                target=_scheduler_task, 
                daemon=True,
                name="APIKeyRotationScheduler"
            )
            self.rotation_scheduler.start()
            logger.info(f"APIキーローテーションスケジューラを開始しました（間隔: {interval_minutes}分）")
    
    def stop_rotation_scheduler(self):
        """ローテーションスケジューラを停止する"""
        if self.rotation_scheduler and self.rotation_scheduler.is_alive():
            # スケジューラを停止（デーモンスレッドなので自動的に終了）
            self.rotation_scheduler = None
            logger.info("APIキーローテーションスケジューラを停止しました")


# シングルトンインスタンス
api_key_rotation_manager = APIKeyRotationManager()


# ヘルパー関数
def setup_key_rotation(
    owner: str, 
    interval_days: int, 
    permissions: List[str],
    overlap_days: int = 7,
    max_keys: int = 2,
    notify_emails: List[str] = None,
    metadata: Dict[str, Any] = None
) -> bool:
    """
    APIキーのローテーションを設定するヘルパー関数
    
    Args:
        owner: キーの所有者
        interval_days: ローテーション間隔（日数）
        permissions: 新しいキーに付与する権限リスト
        overlap_days: 新旧キーの重複期間（日数）
        max_keys: 同時に有効にできるキーの最大数
        notify_emails: 通知先メールアドレスリスト
        metadata: キーのメタデータ
        
    Returns:
        bool: 成功したらTrue
    """
    return api_key_rotation_manager.setup_rotation(
        owner, interval_days, permissions, overlap_days, max_keys, notify_emails, metadata
    )


def rotate_api_key(owner: str) -> bool:
    """
    指定された所有者のAPIキーを手動でローテーションするヘルパー関数
    
    Args:
        owner: キーの所有者
        
    Returns:
        bool: 成功したらTrue
    """
    return api_key_rotation_manager.rotate_key(owner)


def disable_key_rotation(owner: str) -> bool:
    """
    APIキーのローテーションを無効化するヘルパー関数
    
    Args:
        owner: キーの所有者
        
    Returns:
        bool: 成功したらTrue
    """
    return api_key_rotation_manager.disable_rotation(owner)


def enable_key_rotation(owner: str) -> bool:
    """
    APIキーのローテーションを有効化するヘルパー関数
    
    Args:
        owner: キーの所有者
        
    Returns:
        bool: 成功したらTrue
    """
    return api_key_rotation_manager.enable_rotation(owner)


def get_key_rotation(owner: str) -> Optional[Dict[str, Any]]:
    """
    ローテーション設定を取得するヘルパー関数
    
    Args:
        owner: キーの所有者
        
    Returns:
        Optional[Dict[str, Any]]: ローテーション設定
    """
    return api_key_rotation_manager.get_rotation(owner)


def list_key_rotations() -> List[Dict[str, Any]]:
    """
    すべてのローテーション設定を取得するヘルパー関数
    
    Returns:
        List[Dict[str, Any]]: ローテーション設定のリスト
    """
    return api_key_rotation_manager.list_rotations()


def start_key_rotation_scheduler(interval_minutes: int = 60):
    """
    バックグラウンドでローテーションスケジューラを開始するヘルパー関数
    
    Args:
        interval_minutes: チェック間隔（分）
    """
    api_key_rotation_manager.start_rotation_scheduler(interval_minutes)


# アプリケーション起動時にスケジューラを自動的に開始（必要に応じて有効化）
# start_key_rotation_scheduler() 