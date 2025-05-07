"""
トレースストレージモジュール。
トレースデータの永続化、検索、エクスポートを行うための機能を提供します。
"""

import os
import json
import time
import uuid
import sqlite3
import threading
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import requests

from utils.logger import get_structured_logger
from utils.config import config
from utils.tracing import SpanContext

# ロガーの取得
logger = get_structured_logger("trace_storage")


class SqliteTraceStorage:
    """SQLiteを使用したトレースの永続化ストレージ"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: データベースファイルのパス（Noneの場合はデフォルトパス）
        """
        # データベースファイルのパス設定
        if db_path is None:
            storage_dir = Path("storage/traces")
            storage_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(storage_dir / "traces.db")
        
        self.db_path = db_path
        
        # SQLiteの同時接続用のロック
        self._lock = threading.RLock()
        
        # データベース接続とテーブル初期化
        self._init_db()
    
    def _init_db(self):
        """データベースとテーブルの初期化"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # トレーステーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                start_time REAL,
                end_time REAL,
                root_span_id TEXT,
                service_name TEXT,
                attributes TEXT
            )
            ''')
            
            # スパンテーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS spans (
                span_id TEXT PRIMARY KEY,
                trace_id TEXT,
                parent_span_id TEXT,
                name TEXT,
                start_time REAL,
                end_time REAL,
                service_name TEXT,
                attributes TEXT,
                FOREIGN KEY (trace_id) REFERENCES traces (trace_id)
            )
            ''')
            
            # イベントテーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                span_id TEXT,
                name TEXT,
                timestamp REAL,
                attributes TEXT,
                FOREIGN KEY (span_id) REFERENCES spans (span_id)
            )
            ''')
            
            # インデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans (trace_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_spans_parent_id ON spans (parent_span_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_spans_service ON spans (service_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans (start_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_span_id ON events (span_id)')
            
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
    
    def store_trace(self, trace_id: str, root_span: SpanContext):
        """
        トレース情報を保存
        
        Args:
            trace_id: トレースID
            root_span: ルートスパン
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            attributes = json.dumps(root_span.attributes)
            
            # トレース情報を保存
            cursor.execute(
                '''
                INSERT OR REPLACE INTO traces
                (trace_id, start_time, end_time, root_span_id, service_name, attributes)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    trace_id,
                    root_span.start_time,
                    root_span.end_time,
                    root_span.span_id,
                    root_span.attributes.get("service.name", "unknown"),
                    attributes
                )
            )
            
            conn.commit()
    
    def store_span(self, span: SpanContext):
        """
        スパン情報を保存
        
        Args:
            span: スパンコンテキスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            attributes = json.dumps(span.attributes)
            
            # スパン情報を保存
            cursor.execute(
                '''
                INSERT OR REPLACE INTO spans
                (span_id, trace_id, parent_span_id, name, start_time, end_time, service_name, attributes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    span.span_id,
                    span.trace_id,
                    span.parent_span_id,
                    span.attributes.get("span.name", "unknown"),
                    span.start_time,
                    span.end_time,
                    span.attributes.get("service.name", "unknown"),
                    attributes
                )
            )
            
            # イベント情報を保存
            for event in span.events:
                event_id = str(uuid.uuid4())
                event_attributes = json.dumps(event.get("attributes", {}))
                
                cursor.execute(
                    '''
                    INSERT INTO events
                    (event_id, span_id, name, timestamp, attributes)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        event_id,
                        span.span_id,
                        event.get("name", "unknown"),
                        event.get("timestamp", span.start_time),
                        event_attributes
                    )
                )
            
            conn.commit()
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        トレース情報を取得
        
        Args:
            trace_id: トレースID
            
        Returns:
            Optional[Dict[str, Any]]: トレース情報
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # トレース情報を取得
            cursor.execute(
                "SELECT * FROM traces WHERE trace_id = ?",
                (trace_id,)
            )
            trace_row = cursor.fetchone()
            
            if not trace_row:
                return None
            
            # 辞書に変換
            trace_dict = dict(trace_row)
            trace_dict["attributes"] = json.loads(trace_dict["attributes"])
            
            # 関連するスパンを取得
            cursor.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                (trace_id,)
            )
            spans = []
            
            for span_row in cursor.fetchall():
                span_dict = dict(span_row)
                span_dict["attributes"] = json.loads(span_dict["attributes"])
                
                # スパンのイベントを取得
                cursor.execute(
                    "SELECT * FROM events WHERE span_id = ? ORDER BY timestamp",
                    (span_dict["span_id"],)
                )
                events = []
                
                for event_row in cursor.fetchall():
                    event_dict = dict(event_row)
                    event_dict["attributes"] = json.loads(event_dict["attributes"])
                    events.append(event_dict)
                
                span_dict["events"] = events
                spans.append(span_dict)
            
            trace_dict["spans"] = spans
            
            return trace_dict
    
    def get_traces(
        self,
        service_name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        トレース情報のリストを取得
        
        Args:
            service_name: サービス名でフィルタリング
            start_time: 開始時間でフィルタリング
            end_time: 終了時間でフィルタリング
            limit: 取得する最大件数
            offset: オフセット（ページネーション用）
            
        Returns:
            List[Dict[str, Any]]: トレース情報のリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # クエリとパラメータを構築
            query = "SELECT * FROM traces"
            params = []
            where_clauses = []
            
            if service_name:
                where_clauses.append("service_name = ?")
                params.append(service_name)
            
            if start_time:
                where_clauses.append("start_time >= ?")
                params.append(start_time)
            
            if end_time:
                where_clauses.append("start_time <= ?")
                params.append(end_time)
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # クエリを実行
            cursor.execute(query, params)
            traces = []
            
            for trace_row in cursor.fetchall():
                trace_dict = dict(trace_row)
                trace_dict["attributes"] = json.loads(trace_dict["attributes"])
                
                # スパン数をカウント
                cursor.execute(
                    "SELECT COUNT(*) FROM spans WHERE trace_id = ?",
                    (trace_dict["trace_id"],)
                )
                span_count = cursor.fetchone()[0]
                trace_dict["span_count"] = span_count
                
                traces.append(trace_dict)
            
            return traces
    
    def search_traces(
        self,
        query: str,
        service_name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        トレース情報を検索
        
        Args:
            query: 検索クエリ（スパン名やアトリビュートに含まれる文字列）
            service_name: サービス名でフィルタリング
            start_time: 開始時間でフィルタリング
            end_time: 終了時間でフィルタリング
            limit: 取得する最大件数
            
        Returns:
            List[Dict[str, Any]]: トレース情報のリスト
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # スパン名またはアトリビュートでマッチするスパンを検索
            sql_query = """
                SELECT DISTINCT s.trace_id
                FROM spans s
                WHERE (s.name LIKE ? OR s.attributes LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%"]
            
            if service_name:
                sql_query += " AND s.service_name = ?"
                params.append(service_name)
            
            if start_time:
                sql_query += " AND s.start_time >= ?"
                params.append(start_time)
            
            if end_time:
                sql_query += " AND s.start_time <= ?"
                params.append(end_time)
            
            sql_query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql_query, params)
            trace_ids = [row[0] for row in cursor.fetchall()]
            
            # トレース情報を取得
            traces = []
            for trace_id in trace_ids:
                trace = self.get_trace(trace_id)
                if trace:
                    traces.append(trace)
            
            return traces
    
    def delete_old_traces(self, retention_days: int = 30):
        """
        古いトレースデータを削除
        
        Args:
            retention_days: 保持する日数
        """
        retention_seconds = retention_days * 24 * 60 * 60
        cutoff_time = time.time() - retention_seconds
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 削除対象のトレースIDを取得
            cursor.execute(
                "SELECT trace_id FROM traces WHERE start_time < ?",
                (cutoff_time,)
            )
            trace_ids = [row[0] for row in cursor.fetchall()]
            
            if not trace_ids:
                return
            
            # トレースごとに関連データを削除
            for trace_id in trace_ids:
                # スパンIDを取得
                cursor.execute(
                    "SELECT span_id FROM spans WHERE trace_id = ?",
                    (trace_id,)
                )
                span_ids = [row[0] for row in cursor.fetchall()]
                
                # イベントの削除
                for span_id in span_ids:
                    cursor.execute(
                        "DELETE FROM events WHERE span_id = ?",
                        (span_id,)
                    )
                
                # スパンの削除
                cursor.execute(
                    "DELETE FROM spans WHERE trace_id = ?",
                    (trace_id,)
                )
                
                # トレースの削除
                cursor.execute(
                    "DELETE FROM traces WHERE trace_id = ?",
                    (trace_id,)
                )
            
            conn.commit()
            logger.info(f"{len(trace_ids)}件の古いトレースを削除しました（{retention_days}日以前）")


class JaegerExporter:
    """Jaegerにトレースを送信するエクスポーター"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 14268,
        endpoint: str = "/api/traces",
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Args:
            host: JaegerのHTTPコレクターのホスト
            port: JaegerのHTTPコレクターのポート
            endpoint: APIエンドポイント
            username: 基本認証のユーザー名
            password: 基本認証のパスワード
        """
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.url = f"http://{host}:{port}{endpoint}"
    
    def export_trace(self, trace: Dict[str, Any]) -> bool:
        """
        Jaegerにトレースを送信
        
        Args:
            trace: トレース情報
            
        Returns:
            bool: 送信が成功したらTrue
        """
        try:
            # Jaegerフォーマットに変換
            jaeger_trace = self._convert_to_jaeger(trace)
            
            # HTTPヘッダー
            headers = {
                "Content-Type": "application/json"
            }
            
            # 認証情報
            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)
            
            # 送信
            response = requests.post(
                self.url,
                json=jaeger_trace,
                headers=headers,
                auth=auth
            )
            response.raise_for_status()
            
            logger.info(f"トレース {trace['trace_id']} をJaegerに送信しました")
            return True
        except Exception as e:
            logger.error(f"Jaegerへのトレース送信に失敗しました: {str(e)}")
            return False
    
    def _convert_to_jaeger(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        """
        内部トレースフォーマットをJaegerフォーマットに変換
        
        Args:
            trace: 内部フォーマットのトレース
            
        Returns:
            Dict[str, Any]: Jaegerフォーマットのトレース
        """
        # サービス名を取得
        service_name = trace.get("service_name", "unknown")
        
        # プロセス情報
        process = {
            "serviceName": service_name,
            "tags": self._convert_attributes_to_tags(trace.get("attributes", {}))
        }
        
        # スパンの変換
        spans = []
        for span in trace.get("spans", []):
            jaeger_span = {
                "traceID": trace["trace_id"],
                "spanID": span["span_id"],
                "operationName": span["name"],
                "references": [],
                "startTime": int(span["start_time"] * 1_000_000),  # マイクロ秒に変換
                "duration": int((span["end_time"] - span["start_time"]) * 1_000_000) if span["end_time"] else 0,
                "tags": self._convert_attributes_to_tags(span.get("attributes", {})),
                "logs": []
            }
            
            # 親スパンの参照を追加
            if span.get("parent_span_id"):
                jaeger_span["references"].append({
                    "refType": "CHILD_OF",
                    "traceID": trace["trace_id"],
                    "spanID": span["parent_span_id"]
                })
            
            # イベントをログに変換
            for event in span.get("events", []):
                jaeger_span["logs"].append({
                    "timestamp": int(event["timestamp"] * 1_000_000),  # マイクロ秒に変換
                    "fields": [
                        {"key": "event", "value": event["name"]},
                        *self._convert_attributes_to_tags(event.get("attributes", {}))
                    ]
                })
            
            spans.append(jaeger_span)
        
        # Jaegerフォーマットのトレース
        return {
            "data": [
                {
                    "process": process,
                    "spans": spans
                }
            ]
        }
    
    def _convert_attributes_to_tags(self, attributes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        アトリビュートをJaegerのタグ形式に変換
        
        Args:
            attributes: アトリビュート辞書
            
        Returns:
            List[Dict[str, Any]]: タグのリスト
        """
        tags = []
        for key, value in attributes.items():
            tag = {"key": key}
            
            # 値の型に応じてタグタイプを設定
            if isinstance(value, bool):
                tag["type"] = "bool"
                tag["value"] = value
            elif isinstance(value, int):
                tag["type"] = "int64"
                tag["value"] = value
            elif isinstance(value, float):
                tag["type"] = "float64"
                tag["value"] = value
            else:
                tag["type"] = "string"
                tag["value"] = str(value)
            
            tags.append(tag)
        
        return tags


class ZipkinExporter:
    """Zipkinにトレースを送信するエクスポーター"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9411,
        endpoint: str = "/api/v2/spans",
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Args:
            host: ZipkinのAPIサーバーのホスト
            port: ZipkinのAPIサーバーのポート
            endpoint: APIエンドポイント
            username: 基本認証のユーザー名
            password: 基本認証のパスワード
        """
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.url = f"http://{host}:{port}{endpoint}"
    
    def export_trace(self, trace: Dict[str, Any]) -> bool:
        """
        Zipkinにトレースを送信
        
        Args:
            trace: トレース情報
            
        Returns:
            bool: 送信が成功したらTrue
        """
        try:
            # Zipkinフォーマットに変換
            zipkin_spans = self._convert_to_zipkin(trace)
            
            # HTTPヘッダー
            headers = {
                "Content-Type": "application/json"
            }
            
            # 認証情報
            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)
            
            # 送信
            response = requests.post(
                self.url,
                json=zipkin_spans,
                headers=headers,
                auth=auth
            )
            response.raise_for_status()
            
            logger.info(f"トレース {trace['trace_id']} をZipkinに送信しました")
            return True
        except Exception as e:
            logger.error(f"Zipkinへのトレース送信に失敗しました: {str(e)}")
            return False
    
    def _convert_to_zipkin(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        内部トレースフォーマットをZipkinフォーマットに変換
        
        Args:
            trace: 内部フォーマットのトレース
            
        Returns:
            List[Dict[str, Any]]: Zipkinフォーマットのスパンリスト
        """
        zipkin_spans = []
        
        for span in trace.get("spans", []):
            # サービス名を取得
            service_name = span.get("service_name", trace.get("service_name", "unknown"))
            
            # スパン情報
            zipkin_span = {
                "id": span["span_id"],
                "traceId": trace["trace_id"],
                "name": span["name"],
                "timestamp": int(span["start_time"] * 1_000_000),  # マイクロ秒に変換
                "duration": int((span["end_time"] - span["start_time"]) * 1_000_000) if span["end_time"] else 0,
                "localEndpoint": {
                    "serviceName": service_name
                },
                "tags": self._convert_attributes_to_tags(span.get("attributes", {})),
                "annotations": []
            }
            
            # 親スパンの参照を追加
            if span.get("parent_span_id"):
                zipkin_span["parentId"] = span["parent_span_id"]
            
            # イベントをアノテーションに変換
            for event in span.get("events", []):
                # イベント属性をJSONに変換
                event_value = event["name"]
                if event.get("attributes"):
                    event_value += ": " + json.dumps(event["attributes"])
                
                zipkin_span["annotations"].append({
                    "timestamp": int(event["timestamp"] * 1_000_000),  # マイクロ秒に変換
                    "value": event_value
                })
            
            zipkin_spans.append(zipkin_span)
        
        return zipkin_spans
    
    def _convert_attributes_to_tags(self, attributes: Dict[str, Any]) -> Dict[str, str]:
        """
        アトリビュートをZipkinのタグ形式に変換
        
        Args:
            attributes: アトリビュート辞書
            
        Returns:
            Dict[str, str]: タグ辞書
        """
        tags = {}
        for key, value in attributes.items():
            # Zipkinではすべての値を文字列に変換
            tags[key] = str(value)
        
        return tags


class OpenTelemetryExporter:
    """OpenTelemetry Collectorにトレースを送信するエクスポーター"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 4318,
        endpoint: str = "/v1/traces",
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            host: OpenTelemetry CollectorのHTTPレシーバーのホスト
            port: OpenTelemetry CollectorのHTTPレシーバーのポート
            endpoint: APIエンドポイント
            headers: カスタムHTTPヘッダー
        """
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.headers = headers or {}
        self.url = f"http://{host}:{port}{endpoint}"
    
    def export_trace(self, trace: Dict[str, Any]) -> bool:
        """
        OpenTelemetry Collectorにトレースを送信
        
        Args:
            trace: トレース情報
            
        Returns:
            bool: 送信が成功したらTrue
        """
        try:
            # OpenTelemetryフォーマットに変換
            otlp_trace = self._convert_to_otlp(trace)
            
            # HTTPヘッダー
            headers = {
                "Content-Type": "application/json"
            }
            headers.update(self.headers)
            
            # 送信
            response = requests.post(
                self.url,
                json=otlp_trace,
                headers=headers
            )
            response.raise_for_status()
            
            logger.info(f"トレース {trace['trace_id']} をOpenTelemetry Collectorに送信しました")
            return True
        except Exception as e:
            logger.error(f"OpenTelemetry Collectorへのトレース送信に失敗しました: {str(e)}")
            return False
    
    def _convert_to_otlp(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        """
        内部トレースフォーマットをOpenTelemetry Protocolフォーマットに変換
        
        Args:
            trace: 内部フォーマットのトレース
            
        Returns:
            Dict[str, Any]: OTLPフォーマットのトレース
        """
        # リソース属性の設定
        resource = {
            "attributes": self._convert_attributes_to_otlp_attributes(
                {"service.name": trace.get("service_name", "unknown")}
            )
        }
        
        # スパンの変換
        spans = []
        for span in trace.get("spans", []):
            # サービス名を取得
            service_name = span.get("service_name", trace.get("service_name", "unknown"))
            
            otlp_span = {
                "traceId": trace["trace_id"],
                "spanId": span["span_id"],
                "name": span["name"],
                "kind": self._get_span_kind(span),
                "startTimeUnixNano": int(span["start_time"] * 1_000_000_000),  # ナノ秒に変換
                "endTimeUnixNano": int(span["end_time"] * 1_000_000_000) if span["end_time"] else 0,
                "attributes": self._convert_attributes_to_otlp_attributes(span.get("attributes", {})),
                "events": [],
                "links": []
            }
            
            # 親スパンの参照を追加
            if span.get("parent_span_id"):
                otlp_span["parentSpanId"] = span["parent_span_id"]
            
            # イベントの変換
            for event in span.get("events", []):
                otlp_span["events"].append({
                    "timeUnixNano": int(event["timestamp"] * 1_000_000_000),  # ナノ秒に変換
                    "name": event["name"],
                    "attributes": self._convert_attributes_to_otlp_attributes(event.get("attributes", {}))
                })
            
            spans.append(otlp_span)
        
        # OTLPフォーマットのトレース
        return {
            "resourceSpans": [
                {
                    "resource": resource,
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": "ai_team_tracer"
                            },
                            "spans": spans
                        }
                    ]
                }
            ]
        }
    
    def _convert_attributes_to_otlp_attributes(self, attributes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        アトリビュートをOTLPのアトリビュート形式に変換
        
        Args:
            attributes: アトリビュート辞書
            
        Returns:
            List[Dict[str, Any]]: OTLPアトリビュートのリスト
        """
        otlp_attributes = []
        for key, value in attributes.items():
            attribute = {"key": key}
            
            # 値の型に応じてアトリビュートタイプを設定
            if isinstance(value, bool):
                attribute["value"] = {"boolValue": value}
            elif isinstance(value, int):
                attribute["value"] = {"intValue": value}
            elif isinstance(value, float):
                attribute["value"] = {"doubleValue": value}
            elif isinstance(value, list):
                if all(isinstance(x, str) for x in value):
                    attribute["value"] = {"arrayValue": {"values": [{"stringValue": x} for x in value]}}
                elif all(isinstance(x, bool) for x in value):
                    attribute["value"] = {"arrayValue": {"values": [{"boolValue": x} for x in value]}}
                elif all(isinstance(x, int) for x in value):
                    attribute["value"] = {"arrayValue": {"values": [{"intValue": x} for x in value]}}
                elif all(isinstance(x, float) for x in value):
                    attribute["value"] = {"arrayValue": {"values": [{"doubleValue": x} for x in value]}}
                else:
                    attribute["value"] = {"stringValue": json.dumps(value)}
            else:
                attribute["value"] = {"stringValue": str(value)}
            
            otlp_attributes.append(attribute)
        
        return otlp_attributes
    
    def _get_span_kind(self, span: Dict[str, Any]) -> int:
        """
        スパンの種類を取得
        
        Args:
            span: スパン情報
            
        Returns:
            int: OTLPスパン種別（1: INTERNAL, 2: SERVER, 3: CLIENT, 4: PRODUCER, 5: CONSUMER）
        """
        span_kind = span.get("attributes", {}).get("span.kind", "internal").lower()
        
        if span_kind == "server":
            return 2
        elif span_kind == "client":
            return 3
        elif span_kind == "producer":
            return 4
        elif span_kind == "consumer":
            return 5
        else:
            return 1  # INTERNAL


class CloudTraceExporter:
    """Google Cloud Traceにトレースを送信するエクスポーター"""
    
    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None
    ):
        """
        Args:
            project_id: Google CloudプロジェクトのプロジェクトID
            credentials_path: サービスアカウントキーのファイルパス（Noneの場合はデフォルト認証情報を使用）
        """
        try:
            from google.cloud import trace_v2
            from google.oauth2 import service_account
            
            self.project_id = project_id
            
            # クライアントの初期化
            if credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                self.client = trace_v2.TraceServiceClient(credentials=credentials)
            else:
                self.client = trace_v2.TraceServiceClient()
            
            self.project_name = f"projects/{project_id}"
            self._initialized = True
        except ImportError:
            logger.error("Google Cloud Traceをインポートできません。'google-cloud-trace'パッケージをインストールしてください。")
            self._initialized = False
    
    def export_trace(self, trace: Dict[str, Any]) -> bool:
        """
        Google Cloud Traceにトレースを送信
        
        Args:
            trace: トレース情報
            
        Returns:
            bool: 送信が成功したらTrue
        """
        if not self._initialized:
            logger.error("Google Cloud Traceクライアントが初期化されていません")
            return False
        
        try:
            from google.cloud import trace_v2
            from google.protobuf.timestamp_pb2 import Timestamp
            
            # Cloud Traceスパンの作成
            spans = []
            
            for span in trace.get("spans", []):
                # スパン名を設定
                span_name = f"{self.project_name}/traces/{trace['trace_id']}/spans/{span['span_id']}"
                
                # 開始時間と終了時間を設定
                start_time = Timestamp()
                start_time.FromSeconds(int(span["start_time"]))
                start_time.nanos = int((span["start_time"] % 1) * 1_000_000_000)
                
                end_time = Timestamp()
                if span["end_time"]:
                    end_time.FromSeconds(int(span["end_time"]))
                    end_time.nanos = int((span["end_time"] % 1) * 1_000_000_000)
                else:
                    # 終了時間がない場合は開始時間と同じに設定
                    end_time.CopyFrom(start_time)
                
                # スパンを作成
                cloud_span = trace_v2.Span(
                    name=span_name,
                    span_id=span["span_id"],
                    parent_span_id=span.get("parent_span_id", ""),
                    display_name=trace_v2.TruncatableString(
                        value=span["name"]
                    ),
                    start_time=start_time,
                    end_time=end_time
                )
                
                # アトリビュートを設定
                attributes = {}
                for key, value in span.get("attributes", {}).items():
                    if isinstance(value, str):
                        attributes[key] = trace_v2.AttributeValue(
                            string_value=trace_v2.TruncatableString(value=value)
                        )
                    elif isinstance(value, bool):
                        attributes[key] = trace_v2.AttributeValue(bool_value=value)
                    elif isinstance(value, int):
                        attributes[key] = trace_v2.AttributeValue(int_value=value)
                    elif isinstance(value, float):
                        # Cloudトレースは64ビット浮動小数点をサポートしていないため、文字列に変換
                        attributes[key] = trace_v2.AttributeValue(
                            string_value=trace_v2.TruncatableString(value=str(value))
                        )
                    else:
                        # それ以外は文字列に変換
                        attributes[key] = trace_v2.AttributeValue(
                            string_value=trace_v2.TruncatableString(value=str(value))
                        )
                
                cloud_span.attributes = trace_v2.Span.Attributes(
                    attribute_map=attributes
                )
                
                # イベントを時間イベントに変換
                time_events = []
                for event in span.get("events", []):
                    event_time = Timestamp()
                    event_time.FromSeconds(int(event["timestamp"]))
                    event_time.nanos = int((event["timestamp"] % 1) * 1_000_000_000)
                    
                    # アノテーションを作成
                    annotation = trace_v2.Span.TimeEvent.Annotation(
                        description=trace_v2.TruncatableString(value=event["name"]),
                        attributes=trace_v2.Span.Attributes(
                            attribute_map={
                                key: trace_v2.AttributeValue(
                                    string_value=trace_v2.TruncatableString(value=str(value))
                                )
                                for key, value in event.get("attributes", {}).items()
                            }
                        )
                    )
                    
                    time_event = trace_v2.Span.TimeEvent(
                        time=event_time,
                        annotation=annotation
                    )
                    
                    time_events.append(time_event)
                
                if time_events:
                    cloud_span.time_events = trace_v2.Span.TimeEvents(time_event=time_events)
                
                spans.append(cloud_span)
            
            # バッチ処理リクエストを作成
            request = trace_v2.BatchWriteSpansRequest(
                name=self.project_name,
                spans=spans
            )
            
            # スパンを送信
            self.client.batch_write_spans(request)
            
            logger.info(f"トレース {trace['trace_id']} をCloud Traceに送信しました")
            return True
        except Exception as e:
            logger.error(f"Cloud Traceへのトレース送信に失敗しました: {str(e)}")
            return False


# グローバルインスタンス（シングルトン）
trace_storage = SqliteTraceStorage()


def get_trace_storage() -> SqliteTraceStorage:
    """
    トレースストレージのインスタンスを取得
    
    Returns:
        SqliteTraceStorage: トレースストレージ
    """
    return trace_storage


def get_exporter(exporter_type: str, **kwargs) -> Optional[Union[JaegerExporter, ZipkinExporter, OpenTelemetryExporter, CloudTraceExporter]]:
    """
    指定されたタイプのエクスポーターを取得
    
    Args:
        exporter_type: エクスポーターの種類（"jaeger", "zipkin", "otlp", "cloud_trace"）
        **kwargs: エクスポーターの初期化パラメータ
        
    Returns:
        Optional[Union[JaegerExporter, ZipkinExporter, OpenTelemetryExporter, CloudTraceExporter]]: エクスポーター
    """
    if exporter_type.lower() == "jaeger":
        return JaegerExporter(**kwargs)
    elif exporter_type.lower() == "zipkin":
        return ZipkinExporter(**kwargs)
    elif exporter_type.lower() == "otlp":
        return OpenTelemetryExporter(**kwargs)
    elif exporter_type.lower() == "cloud_trace":
        return CloudTraceExporter(**kwargs)
    else:
        logger.error(f"不明なエクスポータータイプ: {exporter_type}")
        return None


def cleanup_old_traces(days: int = 30) -> None:
    """
    指定した日数より古いトレースを削除
    
    Args:
        days: 保持する日数
    """
    trace_storage.delete_old_traces(days) 