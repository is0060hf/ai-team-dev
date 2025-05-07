"""
メトリクス監視システムモジュール。
システムの各種メトリクスを収集、保存、分析するための機能を提供します。
外部メトリクスデータベースとの連携機能も含みます。
"""

import os
import time
import json
import uuid
import socket
import threading
import requests
import psutil
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from utils.logger import get_structured_logger
from utils.config import config
from utils.tracing import trace, trace_span, add_trace_event
from utils.caching import cache_result

# ロガーの取得
logger = get_structured_logger("monitoring")


class MetricType(Enum):
    """メトリクスの種類を定義する列挙型"""
    GAUGE = "gauge"         # 瞬間値（CPU使用率など）
    COUNTER = "counter"     # 単調増加する値（総リクエスト数など）
    HISTOGRAM = "histogram" # 値の分布（応答時間など）
    SUMMARY = "summary"     # 集計値（平均、パーセンタイルなど）


class MetricUnit(Enum):
    """メトリクスの単位を定義する列挙型"""
    PERCENTAGE = "percentage"  # パーセント値
    BYTES = "bytes"            # バイト
    SECONDS = "seconds"        # 秒
    MILLISECONDS = "ms"        # ミリ秒
    COUNT = "count"            # カウント数
    BYTES_PER_SECOND = "bps"   # バイト/秒
    REQUESTS_PER_SECOND = "rps" # リクエスト/秒
    CUSTOM = "custom"          # カスタム単位


class MetricDefinition:
    """メトリクスの定義を表すクラス"""
    
    def __init__(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        unit: MetricUnit = MetricUnit.CUSTOM,
        labels: Optional[List[str]] = None,
        aggregation_period: Optional[int] = None
    ):
        """
        Args:
            name: メトリクス名
            description: メトリクスの説明
            metric_type: メトリクスの種類
            unit: メトリクスの単位
            labels: メトリクスに付与するラベル（ディメンション）
            aggregation_period: 集計期間（秒単位、Noneの場合は集計なし）
        """
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.unit = unit
        self.labels = labels or []
        self.aggregation_period = aggregation_period
    
    def to_dict(self) -> Dict[str, Any]:
        """メトリクス定義を辞書形式で取得"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.metric_type.value,
            "unit": self.unit.value,
            "labels": self.labels,
            "aggregation_period": self.aggregation_period
        }


class MetricValue:
    """メトリクスの値を表すクラス"""
    
    def __init__(
        self,
        name: str,
        value: Union[float, int, List[float]],
        timestamp: Optional[float] = None,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            name: メトリクス名
            value: メトリクス値
            timestamp: タイムスタンプ（秒単位のエポック時間）
            labels: ラベル値の辞書
        """
        self.name = name
        self.value = value
        self.timestamp = timestamp or time.time()
        self.labels = labels or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """メトリクス値を辞書形式で取得"""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels
        }


class SqliteMetricStorage:
    """SQLiteを使用したメトリクスの永続化ストレージ"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: データベースファイルのパス（Noneの場合はデフォルトパス）
        """
        # データベースファイルのパス設定
        if db_path is None:
            storage_dir = Path("storage/metrics")
            storage_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(storage_dir / "metrics.db")
        
        self.db_path = db_path
        
        # データベース接続とテーブル初期化
        self._init_db()
    
    def _init_db(self):
        """データベースとテーブルの初期化"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # メトリクス定義テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS metric_definitions (
                name TEXT PRIMARY KEY,
                description TEXT,
                type TEXT,
                unit TEXT,
                labels TEXT,
                aggregation_period INTEGER
            )
            ''')
            
            # メトリクス値テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS metric_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                value REAL,
                timestamp REAL,
                labels TEXT,
                FOREIGN KEY (name) REFERENCES metric_definitions (name)
            )
            ''')
            
            # メトリクス値テーブルのインデックス作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metric_values_name ON metric_values (name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metric_values_timestamp ON metric_values (timestamp)')
            
            # ヒストグラム値テーブル（ヒストグラムタイプのメトリクス用）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS histogram_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_id INTEGER,
                bucket REAL,
                count INTEGER,
                FOREIGN KEY (metric_id) REFERENCES metric_values (id)
            )
            ''')
            
            conn.commit()
        except Exception as e:
            logger.error(f"データベース初期化エラー: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def store_metric_definition(self, definition: MetricDefinition):
        """
        メトリクス定義を保存
        
        Args:
            definition: メトリクス定義オブジェクト
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT OR REPLACE INTO metric_definitions
                (name, description, type, unit, labels, aggregation_period)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    definition.name,
                    definition.description,
                    definition.metric_type.value,
                    definition.unit.value,
                    json.dumps(definition.labels),
                    definition.aggregation_period
                )
            )
            conn.commit()
        except Exception as e:
            logger.error(f"メトリクス定義保存エラー: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
    
    def store_metric_value(self, metric: MetricValue) -> int:
        """
        メトリクス値を保存
        
        Args:
            metric: メトリクス値オブジェクト
            
        Returns:
            int: 挿入されたレコードのID（ヒストグラム値の関連付けに使用）
        """
        conn = sqlite3.connect(self.db_path)
        record_id = None
        try:
            cursor = conn.cursor()
            
            # メトリクス値の保存
            # ヒストグラムタイプの場合は、主エントリのvalueには代表値（平均など）を保存
            cursor.execute(
                '''
                INSERT INTO metric_values (name, value, timestamp, labels)
                VALUES (?, ?, ?, ?)
                ''',
                (
                    metric.name,
                    float(metric.value) if not isinstance(metric.value, list) else sum(metric.value) / len(metric.value),
                    metric.timestamp,
                    json.dumps(metric.labels)
                )
            )
            
            # 挿入されたレコードのIDを取得
            record_id = cursor.lastrowid
            
            # ヒストグラム値の場合は追加テーブルに保存
            if isinstance(metric.value, list):
                # バケットカウントを計算（値の出現回数）
                buckets = {}
                for val in metric.value:
                    if val in buckets:
                        buckets[val] += 1
                    else:
                        buckets[val] = 1
                
                # ヒストグラムデータを保存
                for bucket, count in buckets.items():
                    cursor.execute(
                        '''
                        INSERT INTO histogram_values (metric_id, bucket, count)
                        VALUES (?, ?, ?)
                        ''',
                        (record_id, bucket, count)
                    )
            
            conn.commit()
            return record_id
        except Exception as e:
            logger.error(f"メトリクス値保存エラー: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_metric_values(
        self,
        name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000,
        label_filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        メトリクス値を取得
        
        Args:
            name: メトリクス名
            start_time: 取得開始時間（秒単位のエポック時間）
            end_time: 取得終了時間（秒単位のエポック時間）
            limit: 取得する最大レコード数
            label_filters: ラベルによるフィルタリング条件
            
        Returns:
            List[Dict[str, Any]]: メトリクス値のリスト
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # クエリ構築
            query = "SELECT id, name, value, timestamp, labels FROM metric_values WHERE name = ?"
            params = [name]
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                record_id, metric_name, value, timestamp, labels_json = row
                labels = json.loads(labels_json)
                
                # ラベルフィルタリング
                if label_filters:
                    match = True
                    for key, val in label_filters.items():
                        if key not in labels or labels[key] != val:
                            match = False
                            break
                    
                    if not match:
                        continue
                
                # ヒストグラムデータを取得
                histogram_data = None
                cursor.execute(
                    "SELECT bucket, count FROM histogram_values WHERE metric_id = ?",
                    (record_id,)
                )
                histogram_rows = cursor.fetchall()
                if histogram_rows:
                    histogram_data = {float(bucket): count for bucket, count in histogram_rows}
                
                metric_data = {
                    "name": metric_name,
                    "value": value,
                    "timestamp": timestamp,
                    "labels": labels
                }
                
                if histogram_data:
                    metric_data["histogram"] = histogram_data
                
                results.append(metric_data)
            
            return results
        except Exception as e:
            logger.error(f"メトリクス値取得エラー: {str(e)}")
            return []
        finally:
            conn.close()
    
    def get_aggregated_metrics(
        self,
        name: str,
        aggregation: str = "avg",
        interval: str = "1h",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        label_filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        集約されたメトリクス値を取得
        
        Args:
            name: メトリクス名
            aggregation: 集約方法（avg, min, max, sum）
            interval: 集約間隔（5m, 1h, 1d など）
            start_time: 取得開始時間（秒単位のエポック時間）
            end_time: 取得終了時間（秒単位のエポック時間）
            label_filters: ラベルによるフィルタリング条件
            
        Returns:
            List[Dict[str, Any]]: 集約されたメトリクス値のリスト
        """
        # 集約間隔をパースする（例: 5m → 300秒）
        interval_seconds = self._parse_interval(interval)
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 集約関数の選択
            if aggregation == "avg":
                agg_func = "AVG(value)"
            elif aggregation == "min":
                agg_func = "MIN(value)"
            elif aggregation == "max":
                agg_func = "MAX(value)"
            elif aggregation == "sum":
                agg_func = "SUM(value)"
            else:
                agg_func = "AVG(value)"
            
            # 時間間隔でグループ化するためのSQLite関数（切り捨て）
            query = f"""
            SELECT
                (timestamp / {interval_seconds}) * {interval_seconds} as time_bucket,
                {agg_func} as agg_value,
                COUNT(*) as count
            FROM
                metric_values
            WHERE
                name = ?
            """
            params = [name]
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            # ラベルフィルタリングはここではできないので、結果を後処理する
            
            query += " GROUP BY time_bucket ORDER BY time_bucket"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                time_bucket, agg_value, count = row
                
                results.append({
                    "name": name,
                    "value": agg_value,
                    "timestamp": time_bucket,
                    "count": count,
                    "aggregation": aggregation,
                    "interval": interval
                })
            
            return results
        except Exception as e:
            logger.error(f"集約メトリクス取得エラー: {str(e)}")
            return []
        finally:
            conn.close()
    
    def delete_old_metrics(self, retention_days: int = 30):
        """
        古いメトリクスデータを削除
        
        Args:
            retention_days: 保持する日数
        """
        retention_seconds = retention_days * 24 * 60 * 60
        cutoff_time = time.time() - retention_seconds
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 削除対象のメトリクス値IDを特定
            cursor.execute(
                "SELECT id FROM metric_values WHERE timestamp < ?",
                (cutoff_time,)
            )
            ids_to_delete = [row[0] for row in cursor.fetchall()]
            
            if not ids_to_delete:
                return
            
            # ヒストグラム値の削除
            if ids_to_delete:
                # SQLiteのIN句の制限に対応するため、一度に1000件ずつ処理
                for i in range(0, len(ids_to_delete), 1000):
                    batch = ids_to_delete[i:i + 1000]
                    placeholders = ",".join("?" for _ in batch)
                    cursor.execute(
                        f"DELETE FROM histogram_values WHERE metric_id IN ({placeholders})",
                        batch
                    )
            
            # メトリクス値の削除
            cursor.execute(
                "DELETE FROM metric_values WHERE timestamp < ?",
                (cutoff_time,)
            )
            
            conn.commit()
            logger.info(f"{len(ids_to_delete)}件の古いメトリクスを削除しました（{retention_days}日以前）")
        except Exception as e:
            logger.error(f"メトリクス削除エラー: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
    
    def _parse_interval(self, interval: str) -> int:
        """
        間隔文字列をパースして秒数に変換
        
        Args:
            interval: 間隔文字列（例: 5m, 1h, 1d）
            
        Returns:
            int: 秒数
        """
        value = int(interval[:-1])
        unit = interval[-1].lower()
        
        if unit == 's':
            return value
        elif unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 60 * 60
        elif unit == 'd':
            return value * 24 * 60 * 60
        else:
            logger.warning(f"不明な間隔単位: {unit}, 秒として解釈します")
            return value


class PrometheusMetricExporter:
    """Prometheusフォーマットでメトリクスをエクスポートするクラス"""
    
    def __init__(self, storage: SqliteMetricStorage):
        """
        Args:
            storage: メトリクスストレージ
        """
        self.storage = storage
        self.metric_definitions = {}
    
    def register_metric(self, definition: MetricDefinition):
        """
        メトリクスを登録
        
        Args:
            definition: メトリクス定義
        """
        self.metric_definitions[definition.name] = definition
    
    def generate_prometheus_metrics(self) -> str:
        """
        Prometheusフォーマットでメトリクスを生成
        
        Returns:
            str: Prometheusフォーマットのメトリクス
        """
        output_lines = []
        
        for name, definition in self.metric_definitions.items():
            # メトリクスの説明とタイプをコメントとして追加
            output_lines.append(f"# HELP {name} {definition.description}")
            output_lines.append(f"# TYPE {name} {self._map_metric_type(definition.metric_type)}")
            
            # 最新のメトリクス値を取得
            metrics = self.storage.get_metric_values(name, limit=100)
            
            for metric in metrics:
                # ラベルの作成
                labels_str = self._format_labels(metric["labels"])
                
                # メトリクス行の生成
                output_lines.append(f"{name}{labels_str} {metric['value']} {int(metric['timestamp'] * 1000)}")
        
        return "\n".join(output_lines)
    
    def _map_metric_type(self, metric_type: MetricType) -> str:
        """
        内部メトリクスタイプをPrometheusタイプにマッピング
        
        Args:
            metric_type: 内部メトリクスタイプ
            
        Returns:
            str: Prometheusメトリクスタイプ
        """
        mapping = {
            MetricType.GAUGE: "gauge",
            MetricType.COUNTER: "counter",
            MetricType.HISTOGRAM: "histogram",
            MetricType.SUMMARY: "summary"
        }
        return mapping.get(metric_type, "untyped")
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """
        ラベルをPrometheus形式にフォーマット
        
        Args:
            labels: ラベル辞書
            
        Returns:
            str: フォーマットされたラベル文字列
        """
        if not labels:
            return ""
        
        # ラベルキーと値のペアを整形
        label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(label_pairs) + "}"


class InfluxDBMetricExporter:
    """InfluxDBにメトリクスをエクスポートするクラス"""
    
    def __init__(
        self, 
        storage: SqliteMetricStorage,
        url: str = "http://localhost:8086",
        token: Optional[str] = None,
        org: str = "ai_team",
        bucket: str = "metrics"
    ):
        """
        Args:
            storage: メトリクスストレージ
            url: InfluxDBのURL
            token: InfluxDB APIトークン
            org: 組織名
            bucket: バケット名
        """
        self.storage = storage
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
    
    def export_metrics(
        self,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> bool:
        """
        指定されたメトリクスをInfluxDBにエクスポート
        
        Args:
            metric_names: エクスポートするメトリクス名（Noneの場合はすべて）
            start_time: エクスポート開始時間
            end_time: エクスポート終了時間
            
        Returns:
            bool: エクスポートが成功したらTrue
        """
        if not self.token:
            logger.error("InfluxDB APIトークンが設定されていません")
            return False
        
        try:
            # メトリクス値を取得
            metrics = []
            
            if metric_names:
                for name in metric_names:
                    metrics.extend(self.storage.get_metric_values(
                        name, start_time=start_time, end_time=end_time
                    ))
            else:
                # すべてのメトリクス定義を取得
                conn = sqlite3.connect(self.storage.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM metric_definitions")
                all_metrics = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                for name in all_metrics:
                    metrics.extend(self.storage.get_metric_values(
                        name, start_time=start_time, end_time=end_time
                    ))
            
            if not metrics:
                logger.warning("エクスポートするメトリクスがありません")
                return True  # データがないのはエラーではない
            
            # Line Protocolフォーマットに変換
            lines = []
            for metric in metrics:
                name = metric["name"]
                value = metric["value"]
                timestamp = int(metric["timestamp"] * 1_000_000_000)  # ナノ秒に変換
                
                # タグとフィールドの作成
                tags = []
                for tag_key, tag_value in metric["labels"].items():
                    # スペースとコンマを含むタグ値はエスケープ
                    tag_value = tag_value.replace(" ", "\\ ").replace(",", "\\,")
                    tags.append(f"{tag_key}={tag_value}")
                
                tags_str = "," + ",".join(tags) if tags else ""
                
                # 行の生成
                line = f"{name}{tags_str} value={value} {timestamp}"
                lines.append(line)
            
            # InfluxDBに送信
            url = f"{self.url}/api/v2/write"
            headers = {
                "Authorization": f"Token {self.token}",
                "Content-Type": "text/plain"
            }
            params = {
                "org": self.org,
                "bucket": self.bucket,
                "precision": "ns"
            }
            
            # 一度に送信するサイズを制限（5MBを超えないように）
            chunk_size = 5000  # 一度に送信する行数
            
            for i in range(0, len(lines), chunk_size):
                chunk = lines[i:i + chunk_size]
                data = "\n".join(chunk)
                
                response = requests.post(url, headers=headers, params=params, data=data)
                response.raise_for_status()
            
            logger.info(f"{len(metrics)}件のメトリクスをInfluxDBにエクスポートしました")
            return True
        except Exception as e:
            logger.error(f"InfluxDBエクスポートエラー: {str(e)}")
            return False


class MetricsCollector:
    """システムメトリクスを収集するクラス"""
    
    def __init__(self, storage: SqliteMetricStorage):
        """
        Args:
            storage: メトリクスストレージ
        """
        self.storage = storage
        self.collectors = {}
        self.collection_intervals = {}
        self.stop_events = {}
        self.collection_threads = {}
        self.hostname = socket.gethostname()
        
        # システムメトリクス定義を登録
        self._register_system_metrics()
    
    def register_collector(
        self,
        name: str,
        collector_func: Callable[[], Union[float, int, List[float]]],
        metric_definition: MetricDefinition,
        collection_interval: int = 60
    ):
        """
        カスタムメトリクスコレクターを登録
        
        Args:
            name: コレクター名
            collector_func: メトリクス収集関数
            metric_definition: メトリクス定義
            collection_interval: 収集間隔（秒）
        """
        self.collectors[name] = collector_func
        self.storage.store_metric_definition(metric_definition)
        self.collection_intervals[name] = collection_interval
    
    def start_collector(self, name: str):
        """
        コレクターの収集を開始
        
        Args:
            name: コレクター名
        """
        if name not in self.collectors:
            logger.warning(f"コレクター {name} は登録されていません")
            return
        
        # 既に実行中なら何もしない
        if name in self.collection_threads and self.collection_threads[name].is_alive():
            logger.debug(f"コレクター {name} は既に実行中です")
            return
        
        # 停止イベントを作成
        stop_event = threading.Event()
        self.stop_events[name] = stop_event
        
        # 収集スレッドを作成して開始
        interval = self.collection_intervals.get(name, 60)
        thread = threading.Thread(
            target=self._collector_worker,
            args=(name, self.collectors[name], interval, stop_event),
            daemon=True
        )
        self.collection_threads[name] = thread
        thread.start()
        
        logger.info(f"メトリクスコレクター {name} を開始しました（間隔: {interval}秒）")
    
    def stop_collector(self, name: str):
        """
        コレクターの収集を停止
        
        Args:
            name: コレクター名
        """
        if name not in self.stop_events:
            logger.warning(f"コレクター {name} は実行されていません")
            return
        
        # 停止イベントをセット
        self.stop_events[name].set()
        
        logger.info(f"メトリクスコレクター {name} を停止しました")
    
    def start_all_collectors(self):
        """すべてのコレクターの収集を開始"""
        for name in self.collectors:
            self.start_collector(name)
    
    def stop_all_collectors(self):
        """すべてのコレクターの収集を停止"""
        for name in list(self.stop_events.keys()):
            self.stop_collector(name)
    
    def collect_now(self, name: str) -> Optional[MetricValue]:
        """
        指定したコレクターで即座にメトリクスを収集
        
        Args:
            name: コレクター名
            
        Returns:
            Optional[MetricValue]: 収集したメトリクス値
        """
        if name not in self.collectors:
            logger.warning(f"コレクター {name} は登録されていません")
            return None
        
        try:
            # メトリクスを収集
            value = self.collectors[name]()
            
            # ラベルを作成
            labels = {"host": self.hostname, "collector": name}
            
            # メトリクス値を作成
            metric = MetricValue(name=name, value=value, labels=labels)
            
            # ストレージに保存
            self.storage.store_metric_value(metric)
            
            return metric
        except Exception as e:
            logger.error(f"メトリクス {name} の収集に失敗しました: {str(e)}")
            return None
    
    def _collector_worker(
        self,
        name: str,
        collector_func: Callable[[], Union[float, int, List[float]]],
        interval: int,
        stop_event: threading.Event
    ):
        """
        コレクターワーカー関数
        
        Args:
            name: コレクター名
            collector_func: メトリクス収集関数
            interval: 収集間隔（秒）
            stop_event: 停止イベント
        """
        with trace_span(f"metrics_collector.{name}"):
            logger.debug(f"メトリクスコレクター {name} のワーカーを開始しました")
            
            # 最初のサンプルを収集
            self.collect_now(name)
            
            # 定期的に収集
            while not stop_event.is_set():
                # 次の収集まで待機
                if stop_event.wait(interval):
                    break
                
                # メトリクスを収集
                self.collect_now(name)
            
            logger.debug(f"メトリクスコレクター {name} のワーカーを終了しました")
    
    def _register_system_metrics(self):
        """システムメトリクス定義を登録"""
        
        # CPU使用率
        cpu_metric = MetricDefinition(
            name="system_cpu_usage",
            description="システムのCPU使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["host", "collector"]
        )
        self.register_collector(
            name="system_cpu_usage",
            collector_func=lambda: psutil.cpu_percent(interval=1),
            metric_definition=cpu_metric,
            collection_interval=30
        )
        
        # メモリ使用率
        memory_metric = MetricDefinition(
            name="system_memory_usage",
            description="システムのメモリ使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["host", "collector"]
        )
        self.register_collector(
            name="system_memory_usage",
            collector_func=lambda: psutil.virtual_memory().percent,
            metric_definition=memory_metric,
            collection_interval=30
        )
        
        # ディスク使用率
        disk_metric = MetricDefinition(
            name="system_disk_usage",
            description="システムのディスク使用率",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.PERCENTAGE,
            labels=["host", "collector"]
        )
        self.register_collector(
            name="system_disk_usage",
            collector_func=lambda: psutil.disk_usage("/").percent,
            metric_definition=disk_metric,
            collection_interval=60
        )
        
        # ネットワーク送信速度
        net_sent_metric = MetricDefinition(
            name="system_network_sent",
            description="ネットワーク送信バイト数（1秒あたり）",
            metric_type=MetricType.GAUGE,
            unit=MetricUnit.BYTES_PER_SECOND,
            labels=["host", "collector"]
        )
        
        # 前回のネットワーク統計を保持する辞書
        last_net_stats = {"time": time.time(), "stats": psutil.net_io_counters()}
        
        def get_net_sent_rate():
            nonlocal last_net_stats
            current_time = time.time()
            current_stats = psutil.net_io_counters()
            
            # 前回の測定からの経過秒数
            elapsed = current_time - last_net_stats["time"]
            if elapsed < 1:
                # 最低1秒の間隔が必要
                time.sleep(1 - elapsed)
                current_time = time.time()
                current_stats = psutil.net_io_counters()
                elapsed = current_time - last_net_stats["time"]
            
            # 差分を計算
            bytes_sent = current_stats.bytes_sent - last_net_stats["stats"].bytes_sent
            
            # 1秒あたりのレートを計算
            rate = bytes_sent / elapsed if elapsed > 0 else 0
            
            # 現在の値を保存
            last_net_stats = {"time": current_time, "stats": current_stats}
            
            return rate
        
        self.register_collector(
            name="system_network_sent",
            collector_func=get_net_sent_rate,
            metric_definition=net_sent_metric,
            collection_interval=60
        )
        
        # APIリクエスト数（カウンターメトリクス）
        api_requests_metric = MetricDefinition(
            name="api_requests_total",
            description="APIリクエスト総数",
            metric_type=MetricType.COUNTER,
            unit=MetricUnit.COUNT,
            labels=["host", "collector", "method", "path", "status"]
        )
        
        # リクエスト数は他のモジュールから増分されるため、ここでは初期値0を返す
        self.register_collector(
            name="api_requests_total",
            collector_func=lambda: 0,  # 初期値は0
            metric_definition=api_requests_metric,
            collection_interval=300  # このコレクターは自動収集せず、APIから直接更新される
        )
        
        # APIレスポンスタイム（ヒストグラムメトリクス）
        api_response_time_metric = MetricDefinition(
            name="api_response_time",
            description="APIレスポンス時間（ミリ秒）",
            metric_type=MetricType.HISTOGRAM,
            unit=MetricUnit.MILLISECONDS,
            labels=["host", "collector", "method", "path"]
        )
        
        # レスポンスタイムも他のモジュールから設定されるため、ここでは空リストを返す
        self.register_collector(
            name="api_response_time",
            collector_func=lambda: [],  # 空のヒストグラム
            metric_definition=api_response_time_metric,
            collection_interval=300  # このコレクターは自動収集せず、APIから直接更新される
        )


def increment_counter(
    name: str,
    labels: Optional[Dict[str, str]] = None,
    value: int = 1
) -> None:
    """
    カウンタータイプのメトリクスをインクリメント
    
    Args:
        name: メトリクス名
        labels: ラベル
        value: 増分値（デフォルト: 1）
    """
    if not hasattr(increment_counter, 'last_values'):
        increment_counter.last_values = {}
    
    # ラベルをキーに変換
    labels_key = json.dumps(labels or {}, sort_keys=True)
    key = f"{name}:{labels_key}"
    
    # 前回の値を取得
    last_value = increment_counter.last_values.get(key, 0)
    
    # 新しい値を計算
    new_value = last_value + value
    
    # メトリクス値を作成
    metric = MetricValue(name=name, value=new_value, labels=labels or {})
    
    # ストレージに保存
    try:
        # SQLiteストレージのインスタンスを取得
        storage = _get_metric_storage()
        storage.store_metric_value(metric)
        
        # 最新値を更新
        increment_counter.last_values[key] = new_value
    except Exception as e:
        logger.error(f"カウンターメトリクス更新エラー: {str(e)}")


def record_gauge(
    name: str,
    value: Union[float, int],
    labels: Optional[Dict[str, str]] = None
) -> None:
    """
    ゲージタイプのメトリクスを記録
    
    Args:
        name: メトリクス名
        value: メトリクス値
        labels: ラベル
    """
    # メトリクス値を作成
    metric = MetricValue(name=name, value=value, labels=labels or {})
    
    # ストレージに保存
    try:
        storage = _get_metric_storage()
        storage.store_metric_value(metric)
    except Exception as e:
        logger.error(f"ゲージメトリクス記録エラー: {str(e)}")


def record_histogram(
    name: str,
    value: Union[float, int],
    labels: Optional[Dict[str, str]] = None
) -> None:
    """
    ヒストグラムタイプのメトリクスに値を追加
    
    Args:
        name: メトリクス名
        value: メトリクス値
        labels: ラベル
    """
    # 既存のヒストグラムデータを取得
    if not hasattr(record_histogram, 'histograms'):
        record_histogram.histograms = {}
    
    # ラベルをキーに変換
    labels_key = json.dumps(labels or {}, sort_keys=True)
    key = f"{name}:{labels_key}"
    
    # ヒストグラムデータを取得または初期化
    if key not in record_histogram.histograms:
        record_histogram.histograms[key] = []
    
    # 値を追加
    record_histogram.histograms[key].append(value)
    
    # バッファサイズが一定を超えたら保存
    if len(record_histogram.histograms[key]) >= 100:
        # メトリクス値を作成
        metric = MetricValue(
            name=name,
            value=record_histogram.histograms[key],
            labels=labels or {}
        )
        
        # ストレージに保存
        try:
            storage = _get_metric_storage()
            storage.store_metric_value(metric)
            
            # バッファをクリア
            record_histogram.histograms[key] = []
        except Exception as e:
            logger.error(f"ヒストグラムメトリクス記録エラー: {str(e)}")


def time_metric(
    name: str,
    labels: Optional[Dict[str, str]] = None
):
    """
    メトリクスの実行時間を測定するコンテキストマネージャ
    
    Args:
        name: メトリクス名
        labels: ラベル
    
    Returns:
        コンテキストマネージャ
    """
    class TimeMetricContext:
        def __init__(self, metric_name, metric_labels):
            self.metric_name = metric_name
            self.metric_labels = metric_labels or {}
            self.start_time = None
        
        def __enter__(self):
            self.start_time = time.time()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time:
                elapsed_ms = (time.time() - self.start_time) * 1000
                record_histogram(self.metric_name, elapsed_ms, self.metric_labels)
    
    return TimeMetricContext(name, labels)


@cache_result(ttl=60)
def _get_metric_storage() -> SqliteMetricStorage:
    """
    メトリクスストレージのシングルトンインスタンスを取得
    
    Returns:
        SqliteMetricStorage: ストレージインスタンス
    """
    return SqliteMetricStorage()


# グローバルインスタンス（シングルトン）
metric_storage = _get_metric_storage()
metrics_collector = MetricsCollector(metric_storage)
prometheus_exporter = PrometheusMetricExporter(metric_storage)

# モジュール初期化時にシステムメトリクス収集を開始（オプション）
if config.ENABLE_METRICS_COLLECTION:
    metrics_collector.start_all_collectors() 