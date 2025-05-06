"""
APIキー管理モジュール。
APIキーの生成、検証、無効化などの機能を提供します。
"""

import os
import uuid
import time
import json
import hmac
import hashlib
import secrets
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import get_structured_logger

# ロガーの設定
logger = get_structured_logger("api_key_manager")


class APIKey:
    """APIキーを表すクラス"""
    
    def __init__(
        self,
        key_id: str,
        prefix: str,
        hashed_key: str,
        owner: str,
        permissions: List[str],
        created_at: datetime = None,
        expires_at: Optional[datetime] = None,
        last_used_at: Optional[datetime] = None,
        enabled: bool = True,
        metadata: Dict[str, Any] = None
    ):
        """
        Args:
            key_id: キーID（内部的に使用）
            prefix: キープレフィックス（公開部分）
            hashed_key: ハッシュ化されたキー（秘密部分）
            owner: キーの所有者
            permissions: キーの権限リスト
            created_at: 作成日時
            expires_at: 有効期限
            last_used_at: 最終使用日時
            enabled: 有効かどうか
            metadata: 追加のメタデータ
        """
        self.key_id = key_id
        self.prefix = prefix
        self.hashed_key = hashed_key
        self.owner = owner
        self.permissions = permissions
        self.created_at = created_at or datetime.now()
        self.expires_at = expires_at
        self.last_used_at = last_used_at
        self.enabled = enabled
        self.metadata = metadata or {}
    
    def is_valid(self) -> bool:
        """キーが有効かどうかをチェック"""
        if not self.enabled:
            return False
        
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        
        return True
    
    def has_permission(self, permission: str) -> bool:
        """指定された権限を持っているかどうかをチェック"""
        if "*" in self.permissions:
            return True
        
        return permission in self.permissions
    
    def update_last_used(self):
        """最終使用日時を更新"""
        self.last_used_at = datetime.now()
    
    def disable(self):
        """キーを無効化"""
        self.enabled = False
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "key_id": self.key_id,
            "prefix": self.prefix,
            "hashed_key": self.hashed_key,
            "owner": self.owner,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "enabled": self.enabled,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIKey':
        """辞書からインスタンスを作成"""
        return cls(
            key_id=data["key_id"],
            prefix=data["prefix"],
            hashed_key=data["hashed_key"],
            owner=data["owner"],
            permissions=data["permissions"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {})
        )


class APIKeyManager:
    """APIキーを管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/api_keys"):
        """
        Args:
            storage_path: APIキーを保存するディレクトリのパス
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.keys: Dict[str, APIKey] = {}
        self.load_keys()
    
    def load_keys(self):
        """保存されているAPIキーを読み込む"""
        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        api_key = APIKey.from_dict(data)
                        self.keys[api_key.key_id] = api_key
                except Exception as e:
                    logger.error(f"APIキーファイル {file_path} の読み込みに失敗しました: {str(e)}")
            
            logger.info(f"{len(self.keys)} 件のAPIキーを読み込みました")
        except Exception as e:
            logger.error(f"APIキーの読み込みに失敗しました: {str(e)}")
    
    def save_key(self, api_key: APIKey):
        """APIキーを保存する"""
        try:
            file_path = self.storage_path / f"{api_key.key_id}.json"
            with open(file_path, "w") as f:
                json.dump(api_key.to_dict(), f, indent=2)
            logger.info(f"APIキー {api_key.key_id} を保存しました")
        except Exception as e:
            logger.error(f"APIキー {api_key.key_id} の保存に失敗しました: {str(e)}")
    
    def create_key(
        self,
        owner: str,
        permissions: List[str],
        expires_in_days: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[str, APIKey]:
        """
        新しいAPIキーを作成して保存する
        
        Args:
            owner: キーの所有者
            permissions: キーの権限リスト
            expires_in_days: 有効期限（日数）
            metadata: 追加のメタデータ
            
        Returns:
            Tuple[str, APIKey]: 平文のAPIキーとAPIKeyオブジェクト
        """
        # キーIDを生成
        key_id = str(uuid.uuid4())
        
        # プレフィックスを生成（最初の8文字）
        prefix = "sk_" + secrets.token_hex(4)
        
        # 秘密キーを生成
        secret_key = secrets.token_hex(32)
        
        # キーのハッシュ化
        hashed_key = self._hash_key(secret_key)
        
        # 有効期限を設定
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        # APIKeyオブジェクトを作成
        api_key = APIKey(
            key_id=key_id,
            prefix=prefix,
            hashed_key=hashed_key,
            owner=owner,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=expires_at,
            enabled=True,
            metadata=metadata
        )
        
        # キーをメモリとディスクに保存
        self.keys[key_id] = api_key
        self.save_key(api_key)
        
        # 平文のAPIキーを作成（プレフィックス + 秘密キー）
        full_key = f"{prefix}_{secret_key}"
        
        logger.info(f"{owner} 用の新しいAPIキーを作成しました（ID: {key_id}）")
        
        return full_key, api_key
    
    def validate_key(self, api_key: str) -> Tuple[bool, Optional[APIKey]]:
        """
        APIキーを検証する
        
        Args:
            api_key: 検証するAPIキー
            
        Returns:
            Tuple[bool, Optional[APIKey]]: 検証結果とAPIKeyオブジェクト
        """
        try:
            # キーの形式をチェック
            parts = api_key.split("_")
            if len(parts) < 2 or parts[0] != "sk":
                logger.warning("不正な形式のAPIキーが使用されました")
                return False, None
            
            # プレフィックスと秘密キーを取得
            prefix = f"{parts[0]}_{parts[1]}"
            secret_key = "_".join(parts[2:])
            
            # プレフィックスが一致するキーを検索
            matching_key = None
            for key in self.keys.values():
                if key.prefix == prefix:
                    matching_key = key
                    break
            
            if not matching_key:
                logger.warning(f"プレフィックス {prefix} に一致するAPIキーが見つかりません")
                return False, None
            
            # キーが有効かチェック
            if not matching_key.is_valid():
                logger.warning(f"APIキー {matching_key.key_id} は無効か有効期限切れです")
                return False, None
            
            # ハッシュ値を比較
            hashed_secret = self._hash_key(secret_key)
            if not hmac.compare_digest(hashed_secret, matching_key.hashed_key):
                logger.warning(f"APIキー {matching_key.key_id} のハッシュ値が一致しません")
                return False, None
            
            # 最終使用日時を更新
            matching_key.update_last_used()
            self.save_key(matching_key)
            
            logger.info(f"APIキー {matching_key.key_id} の検証に成功しました")
            return True, matching_key
        except Exception as e:
            logger.error(f"APIキーの検証中にエラーが発生しました: {str(e)}")
            return False, None
    
    def revoke_key(self, key_id: str) -> bool:
        """
        APIキーを無効化する
        
        Args:
            key_id: 無効化するキーのID
            
        Returns:
            bool: 成功したらTrue
        """
        if key_id not in self.keys:
            logger.warning(f"キーID {key_id} は存在しません")
            return False
        
        try:
            # キーを無効化
            self.keys[key_id].disable()
            self.save_key(self.keys[key_id])
            logger.info(f"APIキー {key_id} を無効化しました")
            return True
        except Exception as e:
            logger.error(f"APIキー {key_id} の無効化に失敗しました: {str(e)}")
            return False
    
    def get_keys(self, owner: Optional[str] = None) -> List[APIKey]:
        """
        APIキーの一覧を取得する
        
        Args:
            owner: 特定の所有者のキーのみを取得する場合は指定
            
        Returns:
            List[APIKey]: APIキーのリスト
        """
        if owner:
            return [key for key in self.keys.values() if key.owner == owner]
        else:
            return list(self.keys.values())
    
    def cleanup_expired_keys(self) -> int:
        """
        有効期限切れのキーをクリーンアップする
        
        Returns:
            int: クリーンアップされたキーの数
        """
        now = datetime.now()
        cleanup_count = 0
        
        for key_id, api_key in list(self.keys.items()):
            if api_key.expires_at and now > api_key.expires_at:
                api_key.disable()
                self.save_key(api_key)
                cleanup_count += 1
        
        logger.info(f"{cleanup_count} 件の有効期限切れAPIキーをクリーンアップしました")
        return cleanup_count
    
    def _hash_key(self, secret_key: str) -> str:
        """
        秘密キーをハッシュ化する
        
        Args:
            secret_key: ハッシュ化する秘密キー
            
        Returns:
            str: ハッシュ化されたキー
        """
        return hashlib.sha256(secret_key.encode()).hexdigest()


# シングルトンインスタンス
api_key_manager = APIKeyManager()


# ヘルパー関数
def create_api_key(
    owner: str,
    permissions: List[str],
    expires_in_days: Optional[int] = None,
    metadata: Dict[str, Any] = None
) -> Tuple[str, APIKey]:
    """
    新しいAPIキーを作成するヘルパー関数
    
    Args:
        owner: キーの所有者
        permissions: キーの権限リスト
        expires_in_days: 有効期限（日数）
        metadata: 追加のメタデータ
        
    Returns:
        Tuple[str, APIKey]: 平文のAPIキーとAPIKeyオブジェクト
    """
    return api_key_manager.create_key(owner, permissions, expires_in_days, metadata)


def validate_api_key(api_key: str) -> Tuple[bool, Optional[APIKey]]:
    """
    APIキーを検証するヘルパー関数
    
    Args:
        api_key: 検証するAPIキー
        
    Returns:
        Tuple[bool, Optional[APIKey]]: 検証結果とAPIKeyオブジェクト
    """
    return api_key_manager.validate_key(api_key)


def revoke_api_key(key_id: str) -> bool:
    """
    APIキーを無効化するヘルパー関数
    
    Args:
        key_id: 無効化するキーのID
        
    Returns:
        bool: 成功したらTrue
    """
    return api_key_manager.revoke_key(key_id)


def get_api_keys(owner: Optional[str] = None) -> List[APIKey]:
    """
    APIキーの一覧を取得するヘルパー関数
    
    Args:
        owner: 特定の所有者のキーのみを取得する場合は指定
        
    Returns:
        List[APIKey]: APIキーのリスト
    """
    return api_key_manager.get_keys(owner)


def cleanup_expired_api_keys() -> int:
    """
    有効期限切れのキーをクリーンアップするヘルパー関数
    
    Returns:
        int: クリーンアップされたキーの数
    """
    return api_key_manager.cleanup_expired_keys() 