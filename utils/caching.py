"""
キャッシュシステムモジュール。
メモリキャッシュとディスクキャッシュを提供し、高コストな操作の結果を保存・再利用するための機能を提供します。
"""

import os
import time
import json
import pickle
import hashlib
import threading
import shutil
from typing import Dict, Any, Optional, Union, Callable, TypeVar, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import logging
import functools

from utils.logger import get_structured_logger
from utils.tracing import trace

# 型変数の定義
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# ロガーの設定
logger = get_structured_logger("caching")

# キャッシュの基本クラス
class Cache:
    """キャッシュの基本インターフェース"""
    
    def get(self, key: str) -> Optional[Any]:
        """
        キーに対応する値を取得
        
        Args:
            key: キャッシュキー
            
        Returns:
            Optional[Any]: キャッシュされた値（存在しない場合はNone）
        """
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        キーと値をキャッシュに設定
        
        Args:
            key: キャッシュキー
            value: キャッシュする値
            ttl: 有効期限（秒）、Noneの場合は無期限
        """
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        """
        キーをキャッシュから削除
        
        Args:
            key: 削除するキャッシュキー
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        raise NotImplementedError
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        raise NotImplementedError
    
    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報の辞書
        """
        raise NotImplementedError


class MemoryCache(Cache):
    """メモリ内キャッシュ"""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        """
        Args:
            max_size: キャッシュの最大エントリ数
            default_ttl: デフォルトの有効期限（秒）、Noneの場合は無期限
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "created_at": datetime.now()
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        キーに対応する値を取得
        
        Args:
            key: キャッシュキー
            
        Returns:
            Optional[Any]: キャッシュされた値（存在しない場合はNone）
        """
        with self.lock:
            if key not in self.cache:
                self.stats["misses"] += 1
                return None
            
            entry = self.cache[key]
            
            # TTLチェック
            if entry["expires_at"] is not None and datetime.now() > entry["expires_at"]:
                # 期限切れエントリを削除
                del self.cache[key]
                self.stats["misses"] += 1
                return None
            
            # 最終アクセス時間を更新
            entry["last_accessed_at"] = datetime.now()
            self.stats["hits"] += 1
            
            return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        キーと値をキャッシュに設定
        
        Args:
            key: キャッシュキー
            value: キャッシュする値
            ttl: 有効期限（秒）、Noneの場合はデフォルト値を使用
        """
        with self.lock:
            # キャッシュが最大サイズに達したら、最も古いエントリを削除
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_entry()
            
            # TTLの設定
            if ttl is None:
                ttl = self.default_ttl
            
            expires_at = None
            if ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            
            # キャッシュエントリを作成
            self.cache[key] = {
                "value": value,
                "created_at": datetime.now(),
                "last_accessed_at": datetime.now(),
                "expires_at": expires_at
            }
            
            self.stats["sets"] += 1
    
    def delete(self, key: str) -> bool:
        """
        キーをキャッシュから削除
        
        Args:
            key: 削除するキャッシュキー
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats["deletes"] += 1
                return True
            return False
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        with self.lock:
            self.cache.clear()
            # 統計情報をリセット
            self.stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "evictions": 0,
                "created_at": datetime.now()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報の辞書
        """
        with self.lock:
            stats = dict(self.stats)
            stats["size"] = len(self.cache)
            stats["max_size"] = self.max_size
            stats["hit_ratio"] = 0.0
            
            total_requests = stats["hits"] + stats["misses"]
            if total_requests > 0:
                stats["hit_ratio"] = stats["hits"] / total_requests
            
            stats["uptime_seconds"] = (datetime.now() - stats["created_at"]).total_seconds()
            
            # 有効期限切れのエントリ数
            now = datetime.now()
            expired_count = sum(
                1 for entry in self.cache.values()
                if entry["expires_at"] is not None and now > entry["expires_at"]
            )
            stats["expired_entries"] = expired_count
            
            return stats
    
    def _evict_entry(self) -> None:
        """
        キャッシュから最も古いエントリを削除（アクセス時間ベース）
        """
        if not self.cache:
            return
        
        # 最も古くアクセスされたエントリを特定
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k]["last_accessed_at"]
        )
        
        del self.cache[oldest_key]
        self.stats["evictions"] += 1


class DiskCache(Cache):
    """ディスクベースのキャッシュ"""
    
    def __init__(self, cache_dir: str = "storage/cache", max_size_mb: int = 100, default_ttl: Optional[int] = None):
        """
        Args:
            cache_dir: キャッシュディレクトリのパス
            max_size_mb: キャッシュの最大サイズ（MB）
            default_ttl: デフォルトの有効期限（秒）、Noneの場合は無期限
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.max_size_mb = max_size_mb
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        
        # メタデータの初期化
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "created_at": datetime.now().isoformat()
        }
        
        # メタデータを読み込み
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """メタデータをディスクから読み込む"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    data = json.load(f)
                    self.metadata = data.get("entries", {})
                    self.stats = data.get("stats", self.stats)
                    
                    # created_atを日時オブジェクトに変換
                    if isinstance(self.stats["created_at"], str):
                        self.stats["created_at"] = datetime.fromisoformat(self.stats["created_at"])
            except Exception as e:
                logger.error(f"メタデータの読み込みに失敗しました: {str(e)}")
                # 破損していた場合は初期化
                self.metadata = {}
                self.stats = {
                    "hits": 0,
                    "misses": 0,
                    "sets": 0,
                    "deletes": 0,
                    "evictions": 0,
                    "created_at": datetime.now().isoformat()
                }
    
    def _save_metadata(self) -> None:
        """メタデータをディスクに保存"""
        try:
            # created_atを文字列に変換
            stats_copy = dict(self.stats)
            if isinstance(stats_copy["created_at"], datetime):
                stats_copy["created_at"] = stats_copy["created_at"].isoformat()
            
            with open(self.metadata_file, "w") as f:
                json.dump({
                    "entries": self.metadata,
                    "stats": stats_copy
                }, f)
        except Exception as e:
            logger.error(f"メタデータの保存に失敗しました: {str(e)}")
    
    def _get_cache_file_path(self, key: str) -> Path:
        """キャッシュファイルのパスを取得"""
        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed_key}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """
        キーに対応する値を取得
        
        Args:
            key: キャッシュキー
            
        Returns:
            Optional[Any]: キャッシュされた値（存在しない場合はNone）
        """
        with self.lock:
            if key not in self.metadata:
                self.stats["misses"] += 1
                return None
            
            entry = self.metadata[key]
            
            # TTLチェック
            if entry["expires_at"] is not None:
                expires_at = datetime.fromisoformat(entry["expires_at"])
                if datetime.now() > expires_at:
                    # 期限切れエントリを削除
                    self.delete(key)
                    self.stats["misses"] += 1
                    return None
            
            # ファイルからデータを読み込み
            cache_file = self._get_cache_file_path(key)
            if not cache_file.exists():
                # メタデータとファイルの不整合
                del self.metadata[key]
                self._save_metadata()
                self.stats["misses"] += 1
                return None
            
            try:
                with open(cache_file, "rb") as f:
                    value = pickle.load(f)
                
                # 最終アクセス時間を更新
                self.metadata[key]["last_accessed_at"] = datetime.now().isoformat()
                self._save_metadata()
                
                self.stats["hits"] += 1
                return value
            except Exception as e:
                logger.error(f"キャッシュファイルの読み込みに失敗しました: {str(e)}")
                # 破損したエントリを削除
                self.delete(key)
                self.stats["misses"] += 1
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        キーと値をキャッシュに設定
        
        Args:
            key: キャッシュキー
            value: キャッシュする値
            ttl: 有効期限（秒）、Noneの場合はデフォルト値を使用
        """
        with self.lock:
            # キャッシュが最大サイズに達したら、古いエントリを削除
            self._check_size_limit()
            
            # TTLの設定
            if ttl is None:
                ttl = self.default_ttl
            
            expires_at = None
            if ttl is not None:
                expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
            
            # データをファイルに保存
            cache_file = self._get_cache_file_path(key)
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(value, f)
                
                # メタデータを更新
                self.metadata[key] = {
                    "created_at": datetime.now().isoformat(),
                    "last_accessed_at": datetime.now().isoformat(),
                    "expires_at": expires_at,
                    "file_path": str(cache_file)
                }
                
                self._save_metadata()
                self.stats["sets"] += 1
            except Exception as e:
                logger.error(f"キャッシュファイルの保存に失敗しました: {str(e)}")
                # 失敗した場合、ファイルが存在したら削除
                if cache_file.exists():
                    cache_file.unlink()
    
    def delete(self, key: str) -> bool:
        """
        キーをキャッシュから削除
        
        Args:
            key: 削除するキャッシュキー
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        with self.lock:
            if key not in self.metadata:
                return False
            
            # ファイルを削除
            cache_file = self._get_cache_file_path(key)
            if cache_file.exists():
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.error(f"キャッシュファイルの削除に失敗しました: {str(e)}")
            
            # メタデータから削除
            del self.metadata[key]
            self._save_metadata()
            
            self.stats["deletes"] += 1
            return True
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        with self.lock:
            # すべてのキャッシュファイルを削除
            for file_path in self.cache_dir.glob("*.cache"):
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"キャッシュファイルの削除に失敗しました: {str(e)}")
            
            # メタデータをクリア
            self.metadata = {}
            
            # 統計情報をリセット
            self.stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "evictions": 0,
                "created_at": datetime.now().isoformat()
            }
            
            self._save_metadata()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報の辞書
        """
        with self.lock:
            stats = dict(self.stats)
            stats["size"] = len(self.metadata)
            stats["max_size_mb"] = self.max_size_mb
            stats["hit_ratio"] = 0.0
            
            total_requests = stats["hits"] + stats["misses"]
            if total_requests > 0:
                stats["hit_ratio"] = stats["hits"] / total_requests
            
            # 現在のディスク使用量を計算
            disk_usage = 0
            for file_path in self.cache_dir.glob("*.cache"):
                disk_usage += file_path.stat().st_size
            
            stats["disk_usage_bytes"] = disk_usage
            stats["disk_usage_mb"] = disk_usage / (1024 * 1024)
            
            # created_atが文字列の場合はdatetimeに変換
            if isinstance(stats["created_at"], str):
                created_at = datetime.fromisoformat(stats["created_at"])
            else:
                created_at = stats["created_at"]
            
            stats["uptime_seconds"] = (datetime.now() - created_at).total_seconds()
            
            # 有効期限切れのエントリ数
            now = datetime.now()
            expired_count = 0
            for entry in self.metadata.values():
                if entry["expires_at"] is not None:
                    expires_at = datetime.fromisoformat(entry["expires_at"])
                    if now > expires_at:
                        expired_count += 1
            
            stats["expired_entries"] = expired_count
            
            return stats
    
    def _check_size_limit(self) -> None:
        """
        キャッシュサイズを確認し、制限を超えていたら古いエントリを削除
        """
        # 現在のディスク使用量を計算
        disk_usage = 0
        for file_path in self.cache_dir.glob("*.cache"):
            disk_usage += file_path.stat().st_size
        
        disk_usage_mb = disk_usage / (1024 * 1024)
        
        # サイズ制限を超えていないか確認
        if disk_usage_mb <= self.max_size_mb:
            return
        
        # 削除するべきサイズを計算
        target_size_mb = disk_usage_mb * 0.8  # 20%削減
        
        # アクセス時間でソートしたエントリのリスト
        entries = []
        for key, entry in self.metadata.items():
            try:
                last_accessed_at = datetime.fromisoformat(entry["last_accessed_at"])
                entries.append((key, last_accessed_at))
            except:
                # 不正なエントリは削除対象に
                entries.append((key, datetime.min))
        
        # 古い順にソート
        entries.sort(key=lambda x: x[1])
        
        # サイズが制限内に収まるまで古いエントリを削除
        evicted_count = 0
        current_size_mb = disk_usage_mb
        
        for key, _ in entries:
            if current_size_mb <= target_size_mb:
                break
            
            # ファイルサイズを取得
            cache_file = self._get_cache_file_path(key)
            if cache_file.exists():
                file_size = cache_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                
                # エントリを削除
                self.delete(key)
                
                current_size_mb -= file_size_mb
                evicted_count += 1
        
        if evicted_count > 0:
            logger.info(f"{evicted_count} 件のキャッシュエントリを容量制限により削除しました")
            self.stats["evictions"] += evicted_count


class TwoLevelCache(Cache):
    """メモリとディスクの2階層キャッシュ"""
    
    def __init__(
        self,
        memory_max_size: int = 1000,
        disk_cache_dir: str = "storage/cache",
        disk_max_size_mb: int = 100,
        default_ttl: Optional[int] = None
    ):
        """
        Args:
            memory_max_size: メモリキャッシュの最大エントリ数
            disk_cache_dir: ディスクキャッシュのディレクトリパス
            disk_max_size_mb: ディスクキャッシュの最大サイズ（MB）
            default_ttl: デフォルトの有効期限（秒）、Noneの場合は無期限
        """
        self.memory_cache = MemoryCache(memory_max_size, default_ttl)
        self.disk_cache = DiskCache(disk_cache_dir, disk_max_size_mb, default_ttl)
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        キーに対応する値を取得（まずメモリから、なければディスクから）
        
        Args:
            key: キャッシュキー
            
        Returns:
            Optional[Any]: キャッシュされた値（存在しない場合はNone）
        """
        # まずメモリキャッシュをチェック
        value = self.memory_cache.get(key)
        if value is not None:
            return value
        
        # メモリになければディスクキャッシュをチェック
        value = self.disk_cache.get(key)
        if value is not None:
            # ディスクにあった場合、メモリにも保存
            self.memory_cache.set(key, value)
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        キーと値をキャッシュに設定（メモリとディスク両方）
        
        Args:
            key: キャッシュキー
            value: キャッシュする値
            ttl: 有効期限（秒）、Noneの場合はデフォルト値を使用
        """
        if ttl is None:
            ttl = self.default_ttl
        
        # メモリとディスクの両方に保存
        self.memory_cache.set(key, value, ttl)
        self.disk_cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """
        キーをキャッシュから削除（メモリとディスク両方）
        
        Args:
            key: 削除するキャッシュキー
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        # メモリとディスクの両方から削除
        memory_deleted = self.memory_cache.delete(key)
        disk_deleted = self.disk_cache.delete(key)
        
        # どちらかで成功すればTrueを返す
        return memory_deleted or disk_deleted
    
    def clear(self) -> None:
        """キャッシュをクリア（メモリとディスク両方）"""
        self.memory_cache.clear()
        self.disk_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報の辞書
        """
        memory_stats = self.memory_cache.get_stats()
        disk_stats = self.disk_cache.get_stats()
        
        return {
            "memory_cache": memory_stats,
            "disk_cache": disk_stats,
        }


@trace("cached")
def cached(
    cache_instance: Optional[Cache] = None,
    ttl: Optional[int] = None,
    key_fn: Optional[Callable[..., str]] = None
):
    """
    関数の結果をキャッシュするデコレータ
    
    Args:
        cache_instance: 使用するキャッシュインスタンス（Noneの場合はデフォルトを使用）
        ttl: 有効期限（秒）
        key_fn: キャッシュキー生成関数
        
    Returns:
        Callable: デコレータ関数
    """
    # デフォルトキャッシュを使用
    if cache_instance is None:
        cache_instance = default_cache
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # キャッシュキーの生成
            if key_fn is not None:
                cache_key = key_fn(*args, **kwargs)
            else:
                # デフォルトのキー生成
                arg_str = str(args) + str(kwargs)
                cache_key = f"{func.__module__}.{func.__name__}:{hashlib.md5(arg_str.encode()).hexdigest()}"
            
            # キャッシュをチェック
            cached_value = cache_instance.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # キャッシュになければ関数を実行
            result = func(*args, **kwargs)
            
            # 結果をキャッシュに保存
            cache_instance.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


# キャッシュクリーンアップスレッド
class CacheCleanupThread(threading.Thread):
    """期限切れのキャッシュエントリを定期的にクリーンアップするスレッド"""
    
    def __init__(self, cache_instance: Cache, interval: int = 3600):
        """
        Args:
            cache_instance: クリーンアップするキャッシュインスタンス
            interval: 実行間隔（秒）
        """
        super().__init__(daemon=True)
        self.cache = cache_instance
        self.interval = interval
        self.stop_event = threading.Event()
    
    def run(self):
        """スレッドの実行"""
        logger.info(f"キャッシュクリーンアップスレッドを開始しました（間隔: {self.interval}秒）")
        
        while not self.stop_event.is_set():
            # キャッシュタイプに応じたクリーンアップ
            if isinstance(self.cache, MemoryCache):
                self._cleanup_memory_cache()
            elif isinstance(self.cache, DiskCache):
                self._cleanup_disk_cache()
            elif isinstance(self.cache, TwoLevelCache):
                self._cleanup_memory_cache(self.cache.memory_cache)
                self._cleanup_disk_cache(self.cache.disk_cache)
            
            # 次の実行まで待機
            self.stop_event.wait(self.interval)
        
        logger.info("キャッシュクリーンアップスレッドを停止しました")
    
    def _cleanup_memory_cache(self, memory_cache: Optional[MemoryCache] = None):
        """メモリキャッシュをクリーンアップ"""
        try:
            cache = memory_cache or self.cache
            
            if not isinstance(cache, MemoryCache):
                return
            
            # 期限切れのエントリを削除
            now = datetime.now()
            expired_keys = []
            
            with cache.lock:
                for key, entry in list(cache.cache.items()):
                    if entry["expires_at"] is not None and now > entry["expires_at"]:
                        expired_keys.append(key)
            
            # 期限切れのエントリを削除
            for key in expired_keys:
                cache.delete(key)
            
            if expired_keys:
                logger.info(f"{len(expired_keys)} 件の期限切れメモリキャッシュエントリをクリーンアップしました")
        except Exception as e:
            logger.error(f"メモリキャッシュクリーンアップ中にエラーが発生しました: {str(e)}")
    
    def _cleanup_disk_cache(self, disk_cache: Optional[DiskCache] = None):
        """ディスクキャッシュをクリーンアップ"""
        try:
            cache = disk_cache or self.cache
            
            if not isinstance(cache, DiskCache):
                return
            
            # 期限切れのエントリを削除
            now = datetime.now()
            expired_keys = []
            
            with cache.lock:
                for key, entry in list(cache.metadata.items()):
                    if entry["expires_at"] is not None:
                        expires_at = datetime.fromisoformat(entry["expires_at"])
                        if now > expires_at:
                            expired_keys.append(key)
            
            # 期限切れのエントリを削除
            for key in expired_keys:
                cache.delete(key)
            
            if expired_keys:
                logger.info(f"{len(expired_keys)} 件の期限切れディスクキャッシュエントリをクリーンアップしました")
            
            # ファイルシステムの整合性を確認
            self._check_file_consistency(cache)
        except Exception as e:
            logger.error(f"ディスクキャッシュクリーンアップ中にエラーが発生しました: {str(e)}")
    
    def _check_file_consistency(self, disk_cache: DiskCache):
        """ファイルシステムの整合性をチェック"""
        try:
            # メタデータに存在するがファイルがないエントリを検出
            missing_files = []
            
            with disk_cache.lock:
                for key, entry in list(disk_cache.metadata.items()):
                    cache_file = disk_cache._get_cache_file_path(key)
                    if not cache_file.exists():
                        missing_files.append(key)
            
            # 不整合エントリを削除
            for key in missing_files:
                disk_cache.delete(key)
            
            if missing_files:
                logger.warning(f"{len(missing_files)} 件のキャッシュエントリでファイルが見つかりませんでした（メタデータから削除）")
            
            # ファイルは存在するがメタデータがないファイルを検出
            orphaned_files = []
            
            with disk_cache.lock:
                for file_path in disk_cache.cache_dir.glob("*.cache"):
                    file_name = file_path.name
                    if file_name != "metadata.json":
                        # キャッシュキーを特定
                        found = False
                        for key in disk_cache.metadata:
                            if disk_cache._get_cache_file_path(key).name == file_name:
                                found = True
                                break
                        
                        if not found:
                            orphaned_files.append(file_path)
            
            # 孤立ファイルを削除
            for file_path in orphaned_files:
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"孤立キャッシュファイルの削除に失敗しました: {str(e)}")
            
            if orphaned_files:
                logger.warning(f"{len(orphaned_files)} 件の孤立キャッシュファイルを削除しました")
        except Exception as e:
            logger.error(f"ファイルシステム整合性チェック中にエラーが発生しました: {str(e)}")
    
    def stop(self):
        """スレッドの停止"""
        self.stop_event.set()


# デフォルトキャッシュインスタンス
default_cache = TwoLevelCache()

# クリーンアップスレッドのインスタンス
_cleanup_thread = None


def start_cleanup_thread(cache_instance: Optional[Cache] = None, interval: int = 3600):
    """
    キャッシュクリーンアップスレッドを開始
    
    Args:
        cache_instance: クリーンアップするキャッシュインスタンス
        interval: 実行間隔（秒）
    """
    global _cleanup_thread
    
    if _cleanup_thread is not None and _cleanup_thread.is_alive():
        logger.warning("キャッシュクリーンアップスレッドは既に実行中です")
        return
    
    # クリーンアップ対象のキャッシュ
    if cache_instance is None:
        cache_instance = default_cache
    
    _cleanup_thread = CacheCleanupThread(cache_instance, interval)
    _cleanup_thread.start()


def stop_cleanup_thread():
    """キャッシュクリーンアップスレッドを停止"""
    global _cleanup_thread
    
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        logger.warning("キャッシュクリーンアップスレッドは実行されていません")
        return
    
    _cleanup_thread.stop()
    _cleanup_thread.join(timeout=5)
    _cleanup_thread = None


# アプリケーション起動時にクリーンアップスレッドを開始
start_cleanup_thread() 