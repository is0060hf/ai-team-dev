"""
ログストレージモジュール。
ログデータの永続化、検索、エクスポートを行うための機能を提供します。
"""

import os
import json
import time
import uuid
import sqlite3
import threading
import gzip
import shutil
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import requests

from utils.logger import get_structured_logger
from utils.config import config

# ロガーの取得
logger = get_structured_logger("log_storage")


class SqliteLogStorage:
    """SQLiteを使用したログの永続化ストレージ"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: データベースファイルのパス（Noneの場合はデフォルトパス）
        """
        # データベースファイルのパス設定
        if db_path is None:
            storage_dir = Path("storage/logs")
            storage_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(storage_dir / "logs.db")
        
        self.db_path = db_path
        
        # SQLiteの同時接続用のロック
        self._lock = threading.RLock()
        
        # データベース接続とテーブル初期化
        self._init_db()
    
    def _init_db(self):
        """データベースとテーブルの初期化"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # ログテーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                level TEXT,
                logger_name TEXT,
                message TEXT,
                module TEXT,
                function TEXT,
                line INTEGER,
                process_id INTEGER,
                thread_id INTEGER,
                thread_name TEXT,
                hostname TEXT,
                trace_id TEXT,
                span_id TEXT,
                parent_span_id TEXT,
                context TEXT
            )
            ''')
            
            # インデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_level ON logs (level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_logger ON logs (logger_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_trace_id ON logs (trace_id)')
            
            conn.commit()
    
    def _get_connection(self):
        """
        スレッドセーフなデータベース接続を取得
        
        Returns:
            sqlite3.Connection: データベース接続オブジェクト
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 辞書形式で結果を取得
            return conn
    
    def store_log(self, log_entry: Dict[str, Any]) -> int:
        """
        ログエントリを保存
        
        Args:
            log_entry: ログエントリ辞書
            
        Returns:
            int: 挿入されたレコードのID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # コンテキスト情報をJSON形式に変換
            context = json.dumps(log_entry.get("context", {})) if "context" in log_entry else None
            
            # ログエントリを保存
            cursor.execute(
                '''
                INSERT INTO logs
                (timestamp, level, logger_name, message, module, function, line,
                 process_id, thread_id, thread_name, hostname, trace_id, span_id,
                 parent_span_id, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    log_entry.get("timestamp", time.time()),
                    log_entry.get("level", "INFO"),
                    log_entry.get("logger", "root"),
                    log_entry.get("message", ""),
                    log_entry.get("module", ""),
                    log_entry.get("function", ""),
                    log_entry.get("line", 0),
                    log_entry.get("process_id", 0),
                    log_entry.get("thread_id", 0),
                    log_entry.get("thread_name", ""),
                    log_entry.get("hostname", ""),
                    log_entry.get("trace_id", ""),
                    log_entry.get("span_id", ""),
                    log_entry.get("parent_span_id", ""),
                    context
                )
            )
            
            conn.commit()
            return cursor.lastrowid
    
    def get_logs(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        level: Optional[str] = None,
        logger_name: Optional[str] = None,
        trace_id: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        ログエントリを検索して取得
        
        Args:
            start_time: 開始時間（秒単位のエポック時間）
            end_time: 終了時間（秒単位のエポック時間）
            level: ログレベル
            logger_name: ロガー名
            trace_id: トレースID
            search_text: メッセージ内の検索テキスト
            limit: 取得する最大レコード数
            offset: オフセット（ページネーション用）
            
        Returns:
            List[Dict[str, Any]]: ログエントリのリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # クエリとパラメータを構築
            query = "SELECT * FROM logs"
            params = []
            where_clauses = []
            
            if start_time is not None:
                where_clauses.append("timestamp >= ?")
                params.append(start_time)
            
            if end_time is not None:
                where_clauses.append("timestamp <= ?")
                params.append(end_time)
            
            if level is not None:
                where_clauses.append("level = ?")
                params.append(level)
            
            if logger_name is not None:
                where_clauses.append("logger_name = ?")
                params.append(logger_name)
            
            if trace_id is not None:
                where_clauses.append("trace_id = ?")
                params.append(trace_id)
            
            if search_text is not None:
                where_clauses.append("message LIKE ?")
                params.append(f"%{search_text}%")
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # クエリを実行
            cursor.execute(query, params)
            logs = []
            
            for row in cursor.fetchall():
                log_dict = dict(row)
                
                # コンテキスト情報をJSONからデコード
                if log_dict["context"]:
                    try:
                        log_dict["context"] = json.loads(log_dict["context"])
                    except json.JSONDecodeError:
                        log_dict["context"] = {}
                else:
                    log_dict["context"] = {}
                
                logs.append(log_dict)
            
            return logs
    
    def get_log_count(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        level: Optional[str] = None,
        logger_name: Optional[str] = None
    ) -> int:
        """
        条件に一致するログエントリの数を取得
        
        Args:
            start_time: 開始時間（秒単位のエポック時間）
            end_time: 終了時間（秒単位のエポック時間）
            level: ログレベル
            logger_name: ロガー名
            
        Returns:
            int: ログエントリの数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # クエリとパラメータを構築
            query = "SELECT COUNT(*) FROM logs"
            params = []
            where_clauses = []
            
            if start_time is not None:
                where_clauses.append("timestamp >= ?")
                params.append(start_time)
            
            if end_time is not None:
                where_clauses.append("timestamp <= ?")
                params.append(end_time)
            
            if level is not None:
                where_clauses.append("level = ?")
                params.append(level)
            
            if logger_name is not None:
                where_clauses.append("logger_name = ?")
                params.append(logger_name)
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            # クエリを実行
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    def get_log_stats(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        ログの統計情報を取得
        
        Args:
            start_time: 開始時間（秒単位のエポック時間）
            end_time: 終了時間（秒単位のエポック時間）
            
        Returns:
            Dict[str, Any]: 統計情報
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 時間範囲の条件を構築
            time_condition = ""
            params = []
            
            if start_time is not None and end_time is not None:
                time_condition = "WHERE timestamp BETWEEN ? AND ?"
                params = [start_time, end_time]
            elif start_time is not None:
                time_condition = "WHERE timestamp >= ?"
                params = [start_time]
            elif end_time is not None:
                time_condition = "WHERE timestamp <= ?"
                params = [end_time]
            
            # レベル別のログ数を取得
            cursor.execute(
                f"SELECT level, COUNT(*) as count FROM logs {time_condition} GROUP BY level",
                params
            )
            level_counts = {row["level"]: row["count"] for row in cursor.fetchall()}
            
            # ロガー別のログ数を取得
            cursor.execute(
                f"SELECT logger_name, COUNT(*) as count FROM logs {time_condition} GROUP BY logger_name",
                params
            )
            logger_counts = {row["logger_name"]: row["count"] for row in cursor.fetchall()}
            
            # 時間間隔ごとのログ数を取得（1時間単位）
            if start_time and end_time:
                # 1時間ごとのバケットを作成
                bucket_size = 3600  # 1時間（秒）
                cursor.execute(
                    f"""
                    SELECT
                        (timestamp / {bucket_size}) * {bucket_size} as bucket,
                        COUNT(*) as count
                    FROM logs
                    {time_condition}
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    params
                )
                time_buckets = {row["bucket"]: row["count"] for row in cursor.fetchall()}
            else:
                time_buckets = {}
            
            # 総ログ数を取得
            cursor.execute(f"SELECT COUNT(*) as count FROM logs {time_condition}", params)
            total_count = cursor.fetchone()["count"]
            
            return {
                "total_count": total_count,
                "level_counts": level_counts,
                "logger_counts": logger_counts,
                "time_buckets": time_buckets
            }
    
    def delete_old_logs(self, retention_days: int = 30) -> int:
        """
        指定した日数より古いログを削除
        
        Args:
            retention_days: 保持する日数
            
        Returns:
            int: 削除されたログの数
        """
        retention_seconds = retention_days * 24 * 60 * 60
        cutoff_time = time.time() - retention_seconds
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 削除前のログ数を取得
            cursor.execute("SELECT COUNT(*) FROM logs WHERE timestamp < ?", (cutoff_time,))
            delete_count = cursor.fetchone()[0]
            
            # 古いログを削除
            cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_time,))
            conn.commit()
            
            logger.info(f"{delete_count}件の古いログを削除しました（{retention_days}日以前）")
            return delete_count
    
    def archive_old_logs(
        self,
        archive_dir: Optional[str] = None,
        retention_days: int = 30,
        delete_after_archive: bool = True
    ) -> Tuple[int, str]:
        """
        古いログをアーカイブファイルに保存
        
        Args:
            archive_dir: アーカイブディレクトリのパス（Noneの場合はデフォルトパス）
            retention_days: 保持する日数
            delete_after_archive: アーカイブ後に元のログを削除するかどうか
            
        Returns:
            Tuple[int, str]: アーカイブされたログの数とアーカイブファイルのパス
        """
        # アーカイブディレクトリの設定
        if archive_dir is None:
            archive_dir = Path("storage/logs/archives")
            archive_dir.mkdir(parents=True, exist_ok=True)
        else:
            archive_dir = Path(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
        
        retention_seconds = retention_days * 24 * 60 * 60
        cutoff_time = time.time() - retention_seconds
        
        # アーカイブファイル名の生成
        archive_date = datetime.fromtimestamp(cutoff_time).strftime("%Y%m%d")
        archive_file = archive_dir / f"logs_{archive_date}.json.gz"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # アーカイブ対象のログを取得
            cursor.execute("SELECT * FROM logs WHERE timestamp < ?", (cutoff_time,))
            logs = []
            
            for row in cursor.fetchall():
                log_dict = dict(row)
                
                # コンテキスト情報をJSONからデコード
                if log_dict["context"]:
                    try:
                        log_dict["context"] = json.loads(log_dict["context"])
                    except json.JSONDecodeError:
                        log_dict["context"] = {}
                else:
                    log_dict["context"] = {}
                
                logs.append(log_dict)
            
            # ログがない場合は終了
            if not logs:
                return 0, ""
            
            # ログをJSONとして保存し、gzipで圧縮
            with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, default=str)
            
            # アーカイブ後に元のログを削除
            if delete_after_archive:
                cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_time,))
                conn.commit()
            
            logger.info(f"{len(logs)}件のログをアーカイブしました: {archive_file}")
            return len(logs), str(archive_file)


class ElasticsearchExporter:
    """Elasticsearchにログをエクスポートするクラス"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_prefix: str = "ai_team_logs",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = False
    ):
        """
        Args:
            host: Elasticsearchのホスト
            port: Elasticsearchのポート
            index_prefix: インデックスのプレフィックス
            username: 基本認証のユーザー名
            password: 基本認証のパスワード
            use_ssl: SSLを使用するかどうか
        """
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}"
        self.index_prefix = index_prefix
        self.auth = (username, password) if username and password else None
    
    def export_logs(
        self,
        logs: List[Dict[str, Any]],
        index_suffix: Optional[str] = None
    ) -> bool:
        """
        ログをElasticsearchにエクスポート
        
        Args:
            logs: ログエントリのリスト
            index_suffix: インデックスの接尾辞（省略時は現在の日付）
            
        Returns:
            bool: エクスポートが成功したらTrue
        """
        if not logs:
            return True
        
        try:
            # インデックス名を生成
            if not index_suffix:
                index_suffix = datetime.now().strftime("%Y.%m.%d")
            index_name = f"{self.index_prefix}-{index_suffix}"
            
            # インデックスが存在するか確認
            response = requests.head(
                f"{self.base_url}/{index_name}",
                auth=self.auth
            )
            
            # インデックスが存在しない場合は作成
            if response.status_code == 404:
                mapping = {
                    "mappings": {
                        "properties": {
                            "timestamp": {"type": "date"},
                            "level": {"type": "keyword"},
                            "logger_name": {"type": "keyword"},
                            "message": {"type": "text"},
                            "module": {"type": "keyword"},
                            "function": {"type": "keyword"},
                            "line": {"type": "integer"},
                            "process_id": {"type": "integer"},
                            "thread_id": {"type": "integer"},
                            "thread_name": {"type": "keyword"},
                            "hostname": {"type": "keyword"},
                            "trace_id": {"type": "keyword"},
                            "span_id": {"type": "keyword"},
                            "parent_span_id": {"type": "keyword"},
                            "context": {"type": "object", "enabled": False}
                        }
                    }
                }
                
                response = requests.put(
                    f"{self.base_url}/{index_name}",
                    json=mapping,
                    auth=self.auth,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
            
            # Bulk APIを使用してログをエクスポート
            bulk_data = []
            for log in logs:
                # インデックスアクション
                bulk_data.append(json.dumps({
                    "index": {"_index": index_name}
                }))
                
                # ドキュメント
                log_copy = log.copy()
                
                # タイムスタンプをISO形式に変換
                if "timestamp" in log_copy and isinstance(log_copy["timestamp"], (int, float)):
                    log_copy["@timestamp"] = datetime.fromtimestamp(log_copy["timestamp"]).isoformat()
                
                bulk_data.append(json.dumps(log_copy, default=str))
            
            # Bulk APIにリクエスト
            bulk_body = "\n".join(bulk_data) + "\n"
            response = requests.post(
                f"{self.base_url}/_bulk",
                data=bulk_body,
                auth=self.auth,
                headers={"Content-Type": "application/x-ndjson"}
            )
            response.raise_for_status()
            
            # レスポンスをチェック
            result = response.json()
            if result.get("errors", False):
                errors = [item["index"]["error"] for item in result["items"] if "error" in item["index"]]
                logger.error(f"Elasticsearchへのログエクスポート中にエラーが発生しました: {errors}")
                return False
            
            logger.info(f"{len(logs)}件のログをElasticsearchにエクスポートしました: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearchへのログエクスポートに失敗しました: {str(e)}")
            return False


class LokiExporter:
    """Lokiにログをエクスポートするクラス"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3100,
        path: str = "/loki/api/v1/push",
        username: Optional[str] = None,
        password: Optional[str] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Args:
            host: Lokiのホスト
            port: Lokiのポート
            path: APIパス
            username: 基本認証のユーザー名
            password: 基本認証のパスワード
            tenant_id: テナントID（X-Scope-OrgIDヘッダー）
        """
        self.url = f"http://{host}:{port}{path}"
        self.auth = (username, password) if username and password else None
        self.tenant_id = tenant_id
    
    def export_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """
        ログをLokiにエクスポート
        
        Args:
            logs: ログエントリのリスト
            
        Returns:
            bool: エクスポートが成功したらTrue
        """
        if not logs:
            return True
        
        try:
            # ログをLokiフォーマットに変換
            streams = {}
            
            for log in logs:
                # ラベルの作成
                labels = {
                    "level": log.get("level", "INFO"),
                    "logger": log.get("logger_name", "root"),
                    "module": log.get("module", "unknown"),
                    "hostname": log.get("hostname", "unknown")
                }
                
                # トレース情報があれば追加
                if "trace_id" in log and log["trace_id"]:
                    labels["trace_id"] = log["trace_id"]
                
                # ラベル文字列の作成
                labels_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
                
                # ログエントリの作成
                timestamp_ns = int(log.get("timestamp", time.time()) * 1_000_000_000)
                
                # メッセージの作成
                message = log.get("message", "")
                
                # コンテキスト情報があれば追加
                if "context" in log and log["context"]:
                    context_str = json.dumps(log["context"], ensure_ascii=False)
                    message += f" - Context: {context_str}"
                
                # ストリームに追加
                if labels_str not in streams:
                    streams[labels_str] = []
                
                streams[labels_str].append([str(timestamp_ns), message])
            
            # Lokiフォーマットのデータを作成
            loki_data = {
                "streams": [
                    {
                        "stream": json.loads("{" + labels_str + "}"),
                        "values": values
                    }
                    for labels_str, values in streams.items()
                ]
            }
            
            # ヘッダーの設定
            headers = {"Content-Type": "application/json"}
            if self.tenant_id:
                headers["X-Scope-OrgID"] = self.tenant_id
            
            # Lokiにリクエスト
            response = requests.post(
                self.url,
                json=loki_data,
                auth=self.auth,
                headers=headers
            )
            response.raise_for_status()
            
            logger.info(f"{len(logs)}件のログをLokiにエクスポートしました")
            return True
        except Exception as e:
            logger.error(f"Lokiへのログエクスポートに失敗しました: {str(e)}")
            return False


# グローバルインスタンス（シングルトン）
log_storage = SqliteLogStorage()


def get_log_storage() -> SqliteLogStorage:
    """
    ログストレージのインスタンスを取得
    
    Returns:
        SqliteLogStorage: ログストレージ
    """
    return log_storage


def get_exporter(exporter_type: str, **kwargs) -> Optional[Union[ElasticsearchExporter, LokiExporter]]:
    """
    指定されたタイプのエクスポーターを取得
    
    Args:
        exporter_type: エクスポーターの種類（"elasticsearch", "loki"）
        **kwargs: エクスポーターの初期化パラメータ
        
    Returns:
        Optional[Union[ElasticsearchExporter, LokiExporter]]: エクスポーター
    """
    if exporter_type.lower() == "elasticsearch":
        return ElasticsearchExporter(**kwargs)
    elif exporter_type.lower() == "loki":
        return LokiExporter(**kwargs)
    else:
        logger.error(f"不明なエクスポータータイプ: {exporter_type}")
        return None


def cleanup_old_logs(days: int = 30) -> int:
    """
    指定した日数より古いログを削除
    
    Args:
        days: 保持する日数
        
    Returns:
        int: 削除されたログの数
    """
    return log_storage.delete_old_logs(days)


def archive_logs(days: int = 30) -> Tuple[int, str]:
    """
    古いログをアーカイブ
    
    Args:
        days: アーカイブする日数
        
    Returns:
        Tuple[int, str]: アーカイブされたログの数とアーカイブファイルのパス
    """
    return log_storage.archive_old_logs(retention_days=days) 