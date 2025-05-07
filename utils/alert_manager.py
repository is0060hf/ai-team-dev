"""
アラート管理モジュール。
システムアラートの作成、取得、更新、削除機能を提供します。
"""

import json
import sqlite3
import time
import uuid
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import threading
import logging

from utils.config import config
from utils.logger import get_structured_logger

# ロガーの取得
logger = get_structured_logger("alert_manager")


class AlertManager:
    """
    アラートマネージャークラス。
    アラートの作成、取得、更新、削除を行います。
    
    Attributes:
        db_path (str): アラートDBのパス
        alerts_table (str): アラートテーブル名
        rules_table (str): ルールテーブル名
    """
    
    def __init__(self, db_path=None):
        """
        アラートマネージャーの初期化
        
        Args:
            db_path (str, optional): DB保存先のパス
        """
        # DBパスの設定
        if db_path:
            self.db_path = db_path
        else:
            data_dir = config.DATA_DIR or "data"
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "alerts.db")
        
        # テーブル名の設定
        self.alerts_table = "alerts"
        self.rules_table = "alert_rules"
        
        # DBの初期化
        self._init_db()
        
        # アラートチェックのスレッド
        self.check_thread = None
        self.stop_checking = False
    
    def _init_db(self):
        """データベースの初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # アラートテーブルの作成
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.alerts_table} (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            category TEXT,
            timestamp REAL NOT NULL,
            rule_id TEXT,
            source TEXT,
            details TEXT,
            metrics TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """)
        
        # アラートルールテーブルの作成
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.rules_table} (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL,
            category TEXT,
            condition TEXT NOT NULL,
            threshold REAL,
            duration INTEGER,
            frequency INTEGER,
            enabled INTEGER NOT NULL,
            actions TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """)
        
        # インデックスの作成
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON {self.alerts_table} (timestamp)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_alerts_severity ON {self.alerts_table} (severity)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_alerts_status ON {self.alerts_table} (status)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_alerts_category ON {self.alerts_table} (category)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_alerts_rule_id ON {self.alerts_table} (rule_id)")
        
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_rules_severity ON {self.rules_table} (severity)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_rules_category ON {self.rules_table} (category)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_rules_enabled ON {self.rules_table} (enabled)")
        
        conn.commit()
        conn.close()
    
    # アラート関連のメソッド
    def create_alert(
        self,
        name: str,
        description: str = "",
        severity: str = "info",
        category: str = "system",
        rule_id: Optional[str] = None,
        source: str = "system",
        details: Optional[Dict] = None,
        metrics: Optional[Dict] = None
    ) -> str:
        """
        新しいアラートを作成
        
        Args:
            name: アラート名
            description: アラートの詳細説明
            severity: 重要度 (info, warning, error, critical)
            category: カテゴリ
            rule_id: 関連するルールID
            source: アラートの発生元
            details: 追加の詳細情報
            metrics: 関連するメトリクス情報
            
        Returns:
            str: 作成されたアラートのID
        """
        alert_id = str(uuid.uuid4())
        now = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"""
            INSERT INTO {self.alerts_table} (
                id, name, description, severity, status, category, 
                timestamp, rule_id, source, details, metrics, 
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id, name, description, severity, "active", category,
                now, rule_id, source, 
                json.dumps(details) if details else None,
                json.dumps(metrics) if metrics else None,
                now, now
            )
        )
        
        conn.commit()
        conn.close()
        
        # ログに記録
        logger.info(
            f"アラート作成: {name}",
            extra={
                "alert_id": alert_id,
                "severity": severity,
                "category": category
            }
        )
        
        return alert_id
    
    def get_alert(self, alert_id: str) -> Optional[Dict]:
        """
        指定されたIDのアラートを取得
        
        Args:
            alert_id: アラートID
            
        Returns:
            Dict: アラート情報
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            f"SELECT * FROM {self.alerts_table} WHERE id = ?",
            (alert_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        alert = dict(row)
        
        # JSON文字列をPythonオブジェクトに変換
        if alert["details"]:
            alert["details"] = json.loads(alert["details"])
        
        if alert["metrics"]:
            alert["metrics"] = json.loads(alert["metrics"])
        
        return alert
    
    def get_alerts(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        severities: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        category: Optional[str] = None,
        rule_id: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        条件に一致するアラートの一覧を取得
        
        Args:
            start_time: 開始時刻（タイムスタンプ）
            end_time: 終了時刻（タイムスタンプ）
            severities: 重要度のリスト (info, warning, error, critical)
            statuses: ステータスのリスト (active, acknowledged, resolved)
            category: カテゴリ
            rule_id: ルールID
            search_text: 検索テキスト
            limit: 取得する最大数
            offset: オフセット（ページング用）
            
        Returns:
            List[Dict]: アラート情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WHERE句の条件と引数を構築
        conditions = []
        args = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            args.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            args.append(end_time)
        
        if severities:
            placeholders = ", ".join(["?"] * len(severities))
            conditions.append(f"severity IN ({placeholders})")
            args.extend(severities)
        
        if statuses:
            placeholders = ", ".join(["?"] * len(statuses))
            conditions.append(f"status IN ({placeholders})")
            args.extend(statuses)
        
        if category:
            conditions.append("category = ?")
            args.append(category)
        
        if rule_id:
            conditions.append("rule_id = ?")
            args.append(rule_id)
        
        if search_text:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            args.extend([f"%{search_text}%", f"%{search_text}%"])
        
        # WHERE句を構築
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # ORDER BY句を追加
        order_clause = " ORDER BY timestamp DESC"
        
        # LIMITとOFFSETを追加
        limit_clause = f" LIMIT {limit} OFFSET {offset}"
        
        # クエリを実行
        cursor.execute(
            f"SELECT * FROM {self.alerts_table}{where_clause}{order_clause}{limit_clause}",
            args
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        # 結果を変換
        alerts = []
        for row in rows:
            alert = dict(row)
            
            # JSON文字列をPythonオブジェクトに変換
            if alert["details"]:
                try:
                    alert["details"] = json.loads(alert["details"])
                except:
                    alert["details"] = {}
            
            if alert["metrics"]:
                try:
                    alert["metrics"] = json.loads(alert["metrics"])
                except:
                    alert["metrics"] = {}
            
            alerts.append(alert)
        
        return alerts
    
    def update_alert(
        self,
        alert_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[Dict] = None,
        metrics: Optional[Dict] = None
    ) -> bool:
        """
        アラートを更新
        
        Args:
            alert_id: アラートID
            status: 新しいステータス
            severity: 新しい重要度
            description: 新しい説明
            details: 新しい詳細情報
            metrics: 新しいメトリクス情報
            
        Returns:
            bool: 更新に成功したかどうか
        """
        # 変更するフィールドと値を収集
        update_fields = []
        args = []
        
        if status:
            update_fields.append("status = ?")
            args.append(status)
        
        if severity:
            update_fields.append("severity = ?")
            args.append(severity)
        
        if description:
            update_fields.append("description = ?")
            args.append(description)
        
        if details is not None:
            update_fields.append("details = ?")
            args.append(json.dumps(details))
        
        if metrics is not None:
            update_fields.append("metrics = ?")
            args.append(json.dumps(metrics))
        
        # 更新するフィールドがなければ終了
        if not update_fields:
            return False
        
        # 更新日時を追加
        update_fields.append("updated_at = ?")
        args.append(time.time())
        
        # アラートIDを引数に追加
        args.append(alert_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"UPDATE {self.alerts_table} SET {', '.join(update_fields)} WHERE id = ?",
            args
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"アラート更新: {alert_id}", extra={"status": status})
        
        return success
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        アラートを確認済みにする
        
        Args:
            alert_id: アラートID
            
        Returns:
            bool: 更新に成功したかどうか
        """
        return self.update_alert(alert_id, status="acknowledged")
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        アラートを解決済みにする
        
        Args:
            alert_id: アラートID
            
        Returns:
            bool: 更新に成功したかどうか
        """
        return self.update_alert(alert_id, status="resolved")
    
    def delete_alert(self, alert_id: str) -> bool:
        """
        アラートを削除
        
        Args:
            alert_id: アラートID
            
        Returns:
            bool: 削除に成功したかどうか
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"DELETE FROM {self.alerts_table} WHERE id = ?",
            (alert_id,)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"アラート削除: {alert_id}")
        
        return success
    
    # アラートルール関連のメソッド
    def create_rule(
        self,
        name: str,
        condition: str,
        description: str = "",
        severity: str = "warning",
        category: str = "system",
        threshold: Optional[float] = None,
        duration: Optional[int] = None,
        frequency: Optional[int] = None,
        enabled: bool = True,
        actions: Optional[List[Dict]] = None
    ) -> str:
        """
        新しいアラートルールを作成
        
        Args:
            name: ルール名
            condition: 条件式
            description: ルールの説明
            severity: アラートの重要度
            category: カテゴリ
            threshold: しきい値
            duration: 持続時間（秒）
            frequency: 頻度（秒ごと）
            enabled: 有効かどうか
            actions: アラート発生時のアクション
            
        Returns:
            str: 作成されたルールのID
        """
        rule_id = str(uuid.uuid4())
        now = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"""
            INSERT INTO {self.rules_table} (
                id, name, description, severity, category, 
                condition, threshold, duration, frequency, enabled, 
                actions, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id, name, description, severity, category,
                condition, threshold, duration, frequency, 1 if enabled else 0,
                json.dumps(actions) if actions else None,
                now, now
            )
        )
        
        conn.commit()
        conn.close()
        
        logger.info(
            f"アラートルール作成: {name}",
            extra={
                "rule_id": rule_id,
                "severity": severity,
                "category": category
            }
        )
        
        return rule_id
    
    def get_rule(self, rule_id: str) -> Optional[Dict]:
        """
        指定されたIDのルールを取得
        
        Args:
            rule_id: ルールID
            
        Returns:
            Dict: ルール情報
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            f"SELECT * FROM {self.rules_table} WHERE id = ?",
            (rule_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        rule = dict(row)
        
        # 論理値に変換
        rule["enabled"] = bool(rule["enabled"])
        
        # JSON文字列をPythonオブジェクトに変換
        if rule["actions"]:
            rule["actions"] = json.loads(rule["actions"])
        
        return rule
    
    def get_rules(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        enabled: Optional[bool] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        条件に一致するルールの一覧を取得
        
        Args:
            category: カテゴリ
            severity: 重要度
            enabled: 有効かどうか
            search_text: 検索テキスト
            limit: 取得する最大数
            offset: オフセット（ページング用）
            
        Returns:
            List[Dict]: ルール情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WHERE句の条件と引数を構築
        conditions = []
        args = []
        
        if category:
            conditions.append("category = ?")
            args.append(category)
        
        if severity:
            conditions.append("severity = ?")
            args.append(severity)
        
        if enabled is not None:
            conditions.append("enabled = ?")
            args.append(1 if enabled else 0)
        
        if search_text:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            args.extend([f"%{search_text}%", f"%{search_text}%"])
        
        # WHERE句を構築
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # ORDER BY句を追加
        order_clause = " ORDER BY created_at DESC"
        
        # LIMITとOFFSETを追加
        limit_clause = f" LIMIT {limit} OFFSET {offset}"
        
        # クエリを実行
        cursor.execute(
            f"SELECT * FROM {self.rules_table}{where_clause}{order_clause}{limit_clause}",
            args
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        # 結果を変換
        rules = []
        for row in rows:
            rule = dict(row)
            
            # 論理値に変換
            rule["enabled"] = bool(rule["enabled"])
            
            # JSON文字列をPythonオブジェクトに変換
            if rule["actions"]:
                try:
                    rule["actions"] = json.loads(rule["actions"])
                except:
                    rule["actions"] = []
            
            rules.append(rule)
        
        return rules
    
    def update_rule(
        self,
        rule_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        severity: Optional[str] = None,
        condition: Optional[str] = None,
        threshold: Optional[float] = None,
        duration: Optional[int] = None,
        frequency: Optional[int] = None,
        enabled: Optional[bool] = None,
        actions: Optional[List[Dict]] = None
    ) -> bool:
        """
        ルールを更新
        
        Args:
            rule_id: ルールID
            name: 新しい名前
            description: 新しい説明
            severity: 新しい重要度
            condition: 新しい条件式
            threshold: 新しいしきい値
            duration: 新しい持続時間
            frequency: 新しい頻度
            enabled: 有効/無効
            actions: 新しいアクション
            
        Returns:
            bool: 更新に成功したかどうか
        """
        # 変更するフィールドと値を収集
        update_fields = []
        args = []
        
        if name:
            update_fields.append("name = ?")
            args.append(name)
        
        if description is not None:
            update_fields.append("description = ?")
            args.append(description)
        
        if severity:
            update_fields.append("severity = ?")
            args.append(severity)
        
        if condition:
            update_fields.append("condition = ?")
            args.append(condition)
        
        if threshold is not None:
            update_fields.append("threshold = ?")
            args.append(threshold)
        
        if duration is not None:
            update_fields.append("duration = ?")
            args.append(duration)
        
        if frequency is not None:
            update_fields.append("frequency = ?")
            args.append(frequency)
        
        if enabled is not None:
            update_fields.append("enabled = ?")
            args.append(1 if enabled else 0)
        
        if actions is not None:
            update_fields.append("actions = ?")
            args.append(json.dumps(actions))
        
        # 更新するフィールドがなければ終了
        if not update_fields:
            return False
        
        # 更新日時を追加
        update_fields.append("updated_at = ?")
        args.append(time.time())
        
        # ルールIDを引数に追加
        args.append(rule_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"UPDATE {self.rules_table} SET {', '.join(update_fields)} WHERE id = ?",
            args
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"アラートルール更新: {rule_id}")
        
        return success
    
    def delete_rule(self, rule_id: str) -> bool:
        """
        ルールを削除
        
        Args:
            rule_id: ルールID
            
        Returns:
            bool: 削除に成功したかどうか
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"DELETE FROM {self.rules_table} WHERE id = ?",
            (rule_id,)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"アラートルール削除: {rule_id}")
        
        return success
    
    # アラート評価と通知のメソッド
    def start_alert_checker(self, check_interval=60):
        """
        アラートチェッカーを開始
        
        Args:
            check_interval: チェック間隔（秒）
        """
        if self.check_thread and self.check_thread.is_alive():
            logger.warning("アラートチェッカーは既に実行中です")
            return
        
        self.stop_checking = False
        self.check_thread = threading.Thread(
            target=self._alert_checker_loop,
            args=(check_interval,),
            daemon=True
        )
        self.check_thread.start()
        
        logger.info(f"アラートチェッカーを開始しました（間隔: {check_interval}秒）")
    
    def stop_alert_checker(self):
        """アラートチェッカーを停止"""
        if not self.check_thread or not self.check_thread.is_alive():
            logger.warning("アラートチェッカーは実行されていません")
            return
        
        self.stop_checking = True
        self.check_thread.join(timeout=10)
        
        logger.info("アラートチェッカーを停止しました")
    
    def _alert_checker_loop(self, check_interval):
        """
        アラートチェックのメインループ
        
        Args:
            check_interval: チェック間隔（秒）
        """
        while not self.stop_checking:
            try:
                self._check_alert_rules()
            except Exception as e:
                logger.error(f"アラートチェック中にエラーが発生しました: {str(e)}")
            
            # 次のチェックまで待機
            for _ in range(check_interval):
                if self.stop_checking:
                    break
                time.sleep(1)
    
    def _check_alert_rules(self):
        """有効なアラートルールを評価"""
        # 有効なルールを取得
        rules = self.get_rules(enabled=True)
        
        for rule in rules:
            try:
                self._evaluate_rule(rule)
            except Exception as e:
                logger.error(
                    f"ルール評価中にエラーが発生: {rule['name']}",
                    extra={
                        "rule_id": rule["id"],
                        "error": str(e)
                    }
                )
    
    def _evaluate_rule(self, rule):
        """
        ルールを評価
        
        Args:
            rule: 評価するルール
        """
        # ここでは単純なデモ用のダミー実装
        # 実際のアプリケーションでは、メトリクスデータを取得して条件を評価する
        
        # 最後のアラートから頻度以上経過しているか確認
        if "frequency" in rule and rule["frequency"]:
            # 最後に作成されたアラートを取得
            recent_alerts = self.get_alerts(
                rule_id=rule["id"],
                limit=1
            )
            
            if recent_alerts:
                last_alert_time = recent_alerts[0]["timestamp"]
                elapsed = time.time() - last_alert_time
                
                # 頻度チェック - 前回のアラートからの経過時間が頻度より短い場合はスキップ
                if elapsed < rule["frequency"]:
                    return
        
        # ここでメトリクスデータを取得し、ルールの条件を評価
        # 本来はモニタリングシステムと連携して条件を評価する
        # この例では、ランダムにアラートを生成
        
        # デモ用のダミー実装
        import random
        if random.random() < 0.01:  # 1%の確率でアラート発生
            self.create_alert(
                name=f"アラート: {rule['name']}",
                description=f"ルール '{rule['name']}' による自動生成アラート",
                severity=rule["severity"],
                category=rule.get("category", "system"),
                rule_id=rule["id"],
                source="alert_checker",
                details={
                    "condition": rule["condition"],
                    "threshold": rule["threshold"],
                    "evaluated_at": time.time()
                }
            )


# シングルトンインスタンス
_alert_manager_instance = None


def get_alert_manager() -> AlertManager:
    """
    AlertManagerのシングルトンインスタンスを取得
    
    Returns:
        AlertManager: アラートマネージャーインスタンス
    """
    global _alert_manager_instance
    
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    
    return _alert_manager_instance 