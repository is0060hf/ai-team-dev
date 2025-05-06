"""
アラートシステムモジュール。
システムの状態を監視し、異常を検知した場合に通知するための機能を提供します。
"""

import os
import time
import json
import smtplib
import requests
import threading
import inspect
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from utils.logger import get_structured_logger
from utils.config import config
from utils.tracing import trace, trace_span, add_trace_event

# ロガーの取得
logger = get_structured_logger("alerting")


class AlertSeverity(Enum):
    """アラートの重大度を定義する列挙型"""
    INFO = "info"          # 情報提供
    WARNING = "warning"    # 警告
    ERROR = "error"        # エラー
    CRITICAL = "critical"  # 致命的


class AlertStatus(Enum):
    """アラートの状態を定義する列挙型"""
    ACTIVE = "active"      # アクティブ
    RESOLVED = "resolved"  # 解決済み
    ACKNOWLEDGED = "acknowledged"  # 確認済み
    SILENCED = "silenced"  # 一時停止


class NotificationType(Enum):
    """通知タイプを定義する列挙型"""
    EMAIL = "email"      # メール通知
    WEBHOOK = "webhook"  # Webhook通知
    SLACK = "slack"      # Slack通知
    CONSOLE = "console"  # コンソール通知


class AlertRule:
    """アラートルールを定義するクラス"""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        description: str,
        severity: AlertSeverity,
        condition: Callable[..., bool],
        check_interval: int = 60,  # 秒単位
        notification_types: List[NotificationType] = None,
        notification_config: Dict[str, Any] = None,
        cooldown_period: int = 300,  # 秒単位
        enabled: bool = True
    ):
        """
        Args:
            rule_id: ルールID
            name: ルール名
            description: ルールの説明
            severity: アラートの重大度
            condition: アラート条件（True/Falseを返す関数）
            check_interval: チェック間隔（秒）
            notification_types: 通知タイプ
            notification_config: 通知設定
            cooldown_period: クールダウン期間（秒）
            enabled: 有効/無効
        """
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.severity = severity
        self.condition = condition
        self.check_interval = check_interval
        self.notification_types = notification_types or [NotificationType.CONSOLE]
        self.notification_config = notification_config or {}
        self.cooldown_period = cooldown_period
        self.enabled = enabled
        self.last_triggered = None
        self.last_status = None
        self.trigger_count = 0
        
        # 条件関数の引数を取得
        self.condition_args = inspect.signature(condition).parameters.keys()
    
    def check_condition(self, **kwargs) -> bool:
        """
        アラート条件をチェック
        
        Args:
            **kwargs: 条件関数に渡す引数
            
        Returns:
            bool: 条件に一致すればTrue
        """
        try:
            # 条件関数に必要な引数のみを抽出
            condition_kwargs = {k: v for k, v in kwargs.items() if k in self.condition_args}
            return self.condition(**condition_kwargs)
        except Exception as e:
            logger.error(f"アラート条件のチェックに失敗しました: {str(e)}", context={
                "rule_id": self.rule_id,
                "error": str(e)
            })
            return False
    
    def can_trigger(self) -> bool:
        """クールダウン期間中でないかをチェック"""
        if not self.last_triggered:
            return True
        
        now = datetime.now()
        delta = now - self.last_triggered
        return delta.total_seconds() >= self.cooldown_period
    
    def trigger(self, context: Dict[str, Any] = None) -> bool:
        """
        アラートをトリガー
        
        Args:
            context: トリガー時のコンテキスト情報
            
        Returns:
            bool: 通知が成功すればTrue
        """
        if not self.enabled:
            return False
        
        if not self.can_trigger():
            logger.debug(f"アラート {self.rule_id} はクールダウン期間中です")
            return False
        
        self.last_triggered = datetime.now()
        self.trigger_count += 1
        self.last_status = AlertStatus.ACTIVE
        
        # アラート情報
        alert_info = {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "timestamp": self.last_triggered.isoformat(),
            "trigger_count": self.trigger_count,
            "context": context or {}
        }
        
        # ログに記録
        logger.warning(f"アラートがトリガーされました: {self.name}", context=alert_info)
        
        # 通知を送信
        notification_success = False
        for notification_type in self.notification_types:
            try:
                success = send_notification(
                    notification_type=notification_type,
                    alert_info=alert_info,
                    config=self.notification_config
                )
                notification_success = notification_success or success
            except Exception as e:
                logger.error(f"通知の送信に失敗しました: {str(e)}", context={
                    "rule_id": self.rule_id,
                    "notification_type": notification_type.value,
                    "error": str(e)
                })
        
        return notification_success
    
    def resolve(self):
        """アラートを解決済みとしてマーク"""
        if self.last_status == AlertStatus.ACTIVE:
            self.last_status = AlertStatus.RESOLVED
            
            # ログに記録
            logger.info(f"アラート {self.name} は解決されました", context={
                "rule_id": self.rule_id,
                "name": self.name,
                "resolved_at": datetime.now().isoformat()
            })
    
    def acknowledge(self):
        """アラートを確認済みとしてマーク"""
        if self.last_status == AlertStatus.ACTIVE:
            self.last_status = AlertStatus.ACKNOWLEDGED
            
            # ログに記録
            logger.info(f"アラート {self.name} は確認されました", context={
                "rule_id": self.rule_id,
                "name": self.name,
                "acknowledged_at": datetime.now().isoformat()
            })
    
    def silence(self, duration: int = 3600):
        """
        一定期間アラートを無効化
        
        Args:
            duration: 無効化する期間（秒）
        """
        self.enabled = False
        self.last_status = AlertStatus.SILENCED
        
        # 指定された期間後に再度有効化するタイマーを設定
        timer = threading.Timer(duration, self.enable)
        timer.daemon = True
        timer.start()
        
        # ログに記録
        logger.info(f"アラート {self.name} は {duration} 秒間無効化されました", context={
            "rule_id": self.rule_id,
            "name": self.name,
            "duration": duration,
            "silenced_at": datetime.now().isoformat(),
            "reactivate_at": (datetime.now() + timedelta(seconds=duration)).isoformat()
        })
    
    def enable(self):
        """アラートを有効化"""
        self.enabled = True
        
        # ログに記録
        logger.info(f"アラート {self.name} が有効化されました", context={
            "rule_id": self.rule_id,
            "name": self.name,
            "enabled_at": datetime.now().isoformat()
        })
    
    def disable(self):
        """アラートを無効化"""
        self.enabled = False
        
        # ログに記録
        logger.info(f"アラート {self.name} が無効化されました", context={
            "rule_id": self.rule_id,
            "name": self.name,
            "disabled_at": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """ルール情報を辞書形式で取得"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "check_interval": self.check_interval,
            "notification_types": [nt.value for nt in self.notification_types],
            "cooldown_period": self.cooldown_period,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "last_status": self.last_status.value if self.last_status else None,
            "trigger_count": self.trigger_count
        }


class AlertManager:
    """アラートを管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.check_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.metrics_collector = MetricsCollector()
    
    def add_rule(self, rule: AlertRule):
        """
        アラートルールを追加
        
        Args:
            rule: アラートルール
        """
        if rule.rule_id in self.rules:
            logger.warning(f"既存のアラートルール {rule.rule_id} を上書きします")
        
        self.rules[rule.rule_id] = rule
        
        # ルール追加をログに記録
        logger.info(f"アラートルール {rule.name} が追加されました", context={
            "rule_id": rule.rule_id,
            "name": rule.name,
            "severity": rule.severity.value
        })
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        アラートルールを削除
        
        Args:
            rule_id: ルールID
            
        Returns:
            bool: 削除に成功すればTrue
        """
        if rule_id not in self.rules:
            logger.warning(f"アラートルール {rule_id} は存在しません")
            return False
        
        # チェックスレッドが実行中なら停止
        if rule_id in self.check_threads and self.check_threads[rule_id].is_alive():
            self.stop_rule_check(rule_id)
        
        # ルールを削除
        rule = self.rules.pop(rule_id)
        
        # ルール削除をログに記録
        logger.info(f"アラートルール {rule.name} が削除されました", context={
            "rule_id": rule_id,
            "name": rule.name
        })
        
        return True
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """
        アラートルールを取得
        
        Args:
            rule_id: ルールID
            
        Returns:
            Optional[AlertRule]: アラートルール
        """
        return self.rules.get(rule_id)
    
    def get_all_rules(self) -> Dict[str, AlertRule]:
        """
        すべてのアラートルールを取得
        
        Returns:
            Dict[str, AlertRule]: ルールIDをキーとするアラートルール
        """
        return self.rules
    
    def start_rule_check(self, rule_id: str):
        """
        ルールのチェックを開始
        
        Args:
            rule_id: ルールID
        """
        if rule_id not in self.rules:
            logger.warning(f"アラートルール {rule_id} は存在しません")
            return
        
        # 既に実行中なら何もしない
        if rule_id in self.check_threads and self.check_threads[rule_id].is_alive():
            logger.debug(f"アラートルール {rule_id} のチェックは既に実行中です")
            return
        
        # 停止イベントを作成
        stop_event = threading.Event()
        self.stop_events[rule_id] = stop_event
        
        # チェックスレッドを作成して開始
        rule = self.rules[rule_id]
        thread = threading.Thread(
            target=self._rule_check_worker,
            args=(rule, stop_event),
            daemon=True
        )
        self.check_threads[rule_id] = thread
        thread.start()
        
        # チェック開始をログに記録
        logger.info(f"アラートルール {rule.name} のチェックを開始しました", context={
            "rule_id": rule_id,
            "name": rule.name,
            "check_interval": rule.check_interval
        })
    
    def stop_rule_check(self, rule_id: str):
        """
        ルールのチェックを停止
        
        Args:
            rule_id: ルールID
        """
        if rule_id not in self.stop_events:
            logger.warning(f"アラートルール {rule_id} のチェックは実行されていません")
            return
        
        # 停止イベントをセット
        self.stop_events[rule_id].set()
        
        # チェック停止をログに記録
        rule = self.rules.get(rule_id)
        if rule:
            logger.info(f"アラートルール {rule.name} のチェックを停止しました", context={
                "rule_id": rule_id,
                "name": rule.name
            })
    
    def start_all_rules(self):
        """すべてのルールのチェックを開始"""
        for rule_id in self.rules:
            self.start_rule_check(rule_id)
    
    def stop_all_rules(self):
        """すべてのルールのチェックを停止"""
        for rule_id in list(self.stop_events.keys()):
            self.stop_rule_check(rule_id)
    
    def check_rule_now(self, rule_id: str) -> bool:
        """
        ルールを即座にチェック
        
        Args:
            rule_id: ルールID
            
        Returns:
            bool: アラートがトリガーされたらTrue
        """
        if rule_id not in self.rules:
            logger.warning(f"アラートルール {rule_id} は存在しません")
            return False
        
        rule = self.rules[rule_id]
        if not rule.enabled:
            logger.debug(f"アラートルール {rule.name} は無効化されています")
            return False
        
        with trace_span("check_rule_now", {"rule_id": rule_id, "rule_name": rule.name}):
            # メトリクスを収集
            metrics = self.metrics_collector.collect_metrics()
            
            # 条件をチェック
            triggered = rule.check_condition(**metrics)
            
            if triggered:
                # アラートをトリガー
                context = {"metrics": metrics}
                notification_success = rule.trigger(context)
                
                # アクティブアラートに追加
                if rule.rule_id not in self.active_alerts:
                    self.active_alerts[rule.rule_id] = {
                        "rule": rule.to_dict(),
                        "triggered_at": datetime.now().isoformat(),
                        "context": context
                    }
                
                return notification_success
            else:
                # アラートが解決された場合
                if rule.rule_id in self.active_alerts:
                    rule.resolve()
                    del self.active_alerts[rule.rule_id]
                
                return False
    
    @trace
    def _rule_check_worker(self, rule: AlertRule, stop_event: threading.Event):
        """
        ルールを定期的にチェックするワーカー関数
        
        Args:
            rule: アラートルール
            stop_event: 停止イベント
        """
        logger.debug(f"アラートルール {rule.name} のチェックワーカーを開始しました")
        
        while not stop_event.is_set():
            if rule.enabled:
                try:
                    self.check_rule_now(rule.rule_id)
                except Exception as e:
                    logger.error(f"ルールチェック中にエラーが発生しました: {str(e)}", context={
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "error": str(e)
                    })
            
            # 次のチェックまで待機
            stop_event.wait(rule.check_interval)
        
        logger.debug(f"アラートルール {rule.name} のチェックワーカーを終了しました")
    
    def get_active_alerts(self) -> Dict[str, Dict[str, Any]]:
        """
        アクティブなアラートを取得
        
        Returns:
            Dict[str, Dict[str, Any]]: ルールIDをキーとするアクティブアラート
        """
        return self.active_alerts
    
    def acknowledge_alert(self, rule_id: str) -> bool:
        """
        アラートを確認済みとしてマーク
        
        Args:
            rule_id: ルールID
            
        Returns:
            bool: 成功すればTrue
        """
        if rule_id not in self.active_alerts:
            logger.warning(f"アクティブなアラート {rule_id} は存在しません")
            return False
        
        rule = self.rules.get(rule_id)
        if rule:
            rule.acknowledge()
            self.active_alerts[rule_id]["status"] = AlertStatus.ACKNOWLEDGED.value
            self.active_alerts[rule_id]["acknowledged_at"] = datetime.now().isoformat()
            return True
        
        return False
    
    def silence_alert(self, rule_id: str, duration: int = 3600) -> bool:
        """
        アラートを一時的に無効化
        
        Args:
            rule_id: ルールID
            duration: 無効化する期間（秒）
            
        Returns:
            bool: 成功すればTrue
        """
        rule = self.rules.get(rule_id)
        if not rule:
            logger.warning(f"アラートルール {rule_id} は存在しません")
            return False
        
        rule.silence(duration)
        
        if rule_id in self.active_alerts:
            self.active_alerts[rule_id]["status"] = AlertStatus.SILENCED.value
            self.active_alerts[rule_id]["silenced_at"] = datetime.now().isoformat()
            self.active_alerts[rule_id]["silenced_until"] = (
                datetime.now() + timedelta(seconds=duration)
            ).isoformat()
        
        return True


class MetricsCollector:
    """メトリクスを収集するクラス"""
    
    def __init__(self):
        """初期化"""
        self.custom_collectors = {}
    
    def register_collector(self, name: str, collector_func: Callable[[], Dict[str, Any]]):
        """
        カスタムメトリクスコレクターを登録
        
        Args:
            name: コレクター名
            collector_func: メトリクス収集関数
        """
        self.custom_collectors[name] = collector_func
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        メトリクスを収集
        
        Returns:
            Dict[str, Any]: 収集したメトリクス
        """
        metrics = {}
        
        with trace_span("collect_metrics"):
            # システムメトリクスを収集
            system_metrics = self._collect_system_metrics()
            metrics.update(system_metrics)
            
            # カスタムメトリクスを収集
            for name, collector_func in self.custom_collectors.items():
                try:
                    custom_metrics = collector_func()
                    metrics[name] = custom_metrics
                except Exception as e:
                    logger.error(f"カスタムメトリクス {name} の収集に失敗しました: {str(e)}")
        
        return metrics
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """
        システムメトリクスを収集
        
        Returns:
            Dict[str, Any]: 収集したシステムメトリクス
        """
        import psutil
        
        metrics = {
            "system": {
                "cpu": {
                    "percent": psutil.cpu_percent(interval=0.1),
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "percent": psutil.virtual_memory().percent,
                    "available_mb": psutil.virtual_memory().available / (1024 * 1024),
                    "total_mb": psutil.virtual_memory().total / (1024 * 1024)
                },
                "disk": {
                    "percent": psutil.disk_usage("/").percent,
                    "free_gb": psutil.disk_usage("/").free / (1024 * 1024 * 1024),
                    "total_gb": psutil.disk_usage("/").total / (1024 * 1024 * 1024)
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return metrics


@trace
def send_notification(
    notification_type: NotificationType,
    alert_info: Dict[str, Any],
    config: Dict[str, Any] = None
) -> bool:
    """
    通知を送信
    
    Args:
        notification_type: 通知タイプ
        alert_info: アラート情報
        config: 通知設定
        
    Returns:
        bool: 送信が成功すればTrue
    """
    config = config or {}
    
    try:
        if notification_type == NotificationType.EMAIL:
            return _send_email_notification(alert_info, config)
        elif notification_type == NotificationType.WEBHOOK:
            return _send_webhook_notification(alert_info, config)
        elif notification_type == NotificationType.SLACK:
            return _send_slack_notification(alert_info, config)
        elif notification_type == NotificationType.CONSOLE:
            return _send_console_notification(alert_info, config)
        else:
            logger.warning(f"不明な通知タイプ: {notification_type}")
            return False
    except Exception as e:
        logger.error(f"通知の送信に失敗しました: {str(e)}", context={
            "notification_type": notification_type.value,
            "error": str(e)
        })
        return False


def _send_email_notification(alert_info: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    メール通知を送信
    
    Args:
        alert_info: アラート情報
        config: 通知設定
        
    Returns:
        bool: 送信が成功すればTrue
    """
    # 設定チェック
    required_fields = ["smtp_server", "smtp_port", "from_addr", "to_addrs"]
    for field in required_fields:
        if field not in config:
            logger.error(f"メール通知の設定が不足しています: {field}")
            return False
    
    # メール作成
    msg = MIMEMultipart()
    msg["From"] = config["from_addr"]
    msg["To"] = ", ".join(config["to_addrs"]) if isinstance(config["to_addrs"], list) else config["to_addrs"]
    msg["Subject"] = f"【{alert_info['severity'].upper()}】{alert_info['name']}"
    
    # メール本文
    body = f"""
    アラート: {alert_info['name']}
    説明: {alert_info['description']}
    重大度: {alert_info['severity']}
    発生時刻: {alert_info['timestamp']}
    トリガー回数: {alert_info['trigger_count']}
    
    詳細情報:
    {json.dumps(alert_info.get('context', {}), indent=2, ensure_ascii=False)}
    """
    
    msg.attach(MIMEText(body, "plain"))
    
    # メール送信
    try:
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            # TLS暗号化
            if config.get("use_tls", False):
                server.starttls()
            
            # 認証
            if "username" in config and "password" in config:
                server.login(config["username"], config["password"])
            
            # 送信
            server.send_message(msg)
        
        logger.info(f"メール通知を送信しました: {alert_info['name']}")
        return True
    except Exception as e:
        logger.error(f"メール通知の送信に失敗しました: {str(e)}")
        return False


def _send_webhook_notification(alert_info: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    Webhook通知を送信
    
    Args:
        alert_info: アラート情報
        config: 通知設定
        
    Returns:
        bool: 送信が成功すればTrue
    """
    # 設定チェック
    if "webhook_url" not in config:
        logger.error("Webhook通知の設定が不足しています: webhook_url")
        return False
    
    # POSTデータ作成
    data = {
        "alert": alert_info,
        "timestamp": datetime.now().isoformat()
    }
    
    # ヘッダー設定
    headers = config.get("headers", {})
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    # リクエスト送信
    try:
        response = requests.post(
            config["webhook_url"],
            json=data,
            headers=headers,
            timeout=config.get("timeout", 10)
        )
        response.raise_for_status()
        
        logger.info(f"Webhook通知を送信しました: {alert_info['name']}, ステータスコード: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Webhook通知の送信に失敗しました: {str(e)}")
        return False


def _send_slack_notification(alert_info: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    Slack通知を送信
    
    Args:
        alert_info: アラート情報
        config: 通知設定
        
    Returns:
        bool: 送信が成功すればTrue
    """
    # 設定チェック
    if "webhook_url" not in config:
        logger.error("Slack通知の設定が不足しています: webhook_url")
        return False
    
    # 重大度に応じた色
    severity_colors = {
        "info": "#36a64f",  # 緑
        "warning": "#ffcc00",  # 黄
        "error": "#ff9900",  # オレンジ
        "critical": "#ff0000"  # 赤
    }
    
    # メッセージ作成
    message = {
        "attachments": [
            {
                "fallback": f"{alert_info['name']} - {alert_info['description']}",
                "color": severity_colors.get(alert_info['severity'], "#36a64f"),
                "title": f"【{alert_info['severity'].upper()}】{alert_info['name']}",
                "text": alert_info['description'],
                "fields": [
                    {
                        "title": "重大度",
                        "value": alert_info['severity'],
                        "short": True
                    },
                    {
                        "title": "発生時刻",
                        "value": alert_info['timestamp'],
                        "short": True
                    },
                    {
                        "title": "トリガー回数",
                        "value": str(alert_info['trigger_count']),
                        "short": True
                    }
                ],
                "footer": "AI Web開発エージェントチーム",
                "ts": int(time.time())
            }
        ]
    }
    
    # コンテキスト情報があれば追加
    if "context" in alert_info and alert_info["context"]:
        context_str = "\n".join([f"*{k}*: {v}" for k, v in alert_info["context"].items()])
        message["attachments"][0]["fields"].append({
            "title": "詳細情報",
            "value": context_str,
            "short": False
        })
    
    # リクエスト送信
    try:
        response = requests.post(
            config["webhook_url"],
            json=message,
            timeout=config.get("timeout", 10)
        )
        response.raise_for_status()
        
        logger.info(f"Slack通知を送信しました: {alert_info['name']}, ステータスコード: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Slack通知の送信に失敗しました: {str(e)}")
        return False


def _send_console_notification(alert_info: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    コンソール通知を送信（主にデバッグ用）
    
    Args:
        alert_info: アラート情報
        config: 通知設定
        
    Returns:
        bool: 常にTrue
    """
    # アラート情報をフォーマット
    alert_str = f"""
    ====== ALERT NOTIFICATION ======
    アラート: {alert_info['name']}
    説明: {alert_info['description']}
    重大度: {alert_info['severity']}
    発生時刻: {alert_info['timestamp']}
    トリガー回数: {alert_info['trigger_count']}
    
    詳細情報:
    {json.dumps(alert_info.get('context', {}), indent=2, ensure_ascii=False)}
    ================================
    """
    
    # コンソールに出力
    print(alert_str)
    
    logger.info(f"コンソール通知を送信しました: {alert_info['name']}")
    return True


# グローバルインスタンス（シングルトン）
alert_manager = AlertManager()


# よく使われるアラート条件関数
def cpu_usage_threshold(threshold: float = 90.0, system_metrics: Dict[str, Any] = None) -> bool:
    """
    CPU使用率がしきい値を超えているかをチェック
    
    Args:
        threshold: しきい値（%）
        system_metrics: システムメトリクス
        
    Returns:
        bool: しきい値を超えていればTrue
    """
    if not system_metrics or "system" not in system_metrics:
        return False
    
    cpu_percent = system_metrics["system"]["cpu"]["percent"]
    return cpu_percent > threshold


def memory_usage_threshold(threshold: float = 90.0, system_metrics: Dict[str, Any] = None) -> bool:
    """
    メモリ使用率がしきい値を超えているかをチェック
    
    Args:
        threshold: しきい値（%）
        system_metrics: システムメトリクス
        
    Returns:
        bool: しきい値を超えていればTrue
    """
    if not system_metrics or "system" not in system_metrics:
        return False
    
    memory_percent = system_metrics["system"]["memory"]["percent"]
    return memory_percent > threshold


def disk_usage_threshold(threshold: float = 90.0, system_metrics: Dict[str, Any] = None) -> bool:
    """
    ディスク使用率がしきい値を超えているかをチェック
    
    Args:
        threshold: しきい値（%）
        system_metrics: システムメトリクス
        
    Returns:
        bool: しきい値を超えていればTrue
    """
    if not system_metrics or "system" not in system_metrics:
        return False
    
    disk_percent = system_metrics["system"]["disk"]["percent"]
    return disk_percent > threshold


# 初期アラートルールの設定
def setup_default_alert_rules():
    """デフォルトのアラートルールを設定"""
    # CPU使用率アラート
    cpu_alert = AlertRule(
        rule_id="system_cpu_high",
        name="CPU使用率が高い",
        description="システムのCPU使用率が閾値を超えています",
        severity=AlertSeverity.WARNING,
        condition=lambda system_metrics: cpu_usage_threshold(threshold=85.0, system_metrics=system_metrics),
        check_interval=30,
        notification_types=[NotificationType.CONSOLE],
        cooldown_period=300,
        enabled=True
    )
    
    # メモリ使用率アラート
    memory_alert = AlertRule(
        rule_id="system_memory_high",
        name="メモリ使用率が高い",
        description="システムのメモリ使用率が閾値を超えています",
        severity=AlertSeverity.WARNING,
        condition=lambda system_metrics: memory_usage_threshold(threshold=85.0, system_metrics=system_metrics),
        check_interval=30,
        notification_types=[NotificationType.CONSOLE],
        cooldown_period=300,
        enabled=True
    )
    
    # ディスク使用率アラート
    disk_alert = AlertRule(
        rule_id="system_disk_high",
        name="ディスク使用率が高い",
        description="システムのディスク使用率が閾値を超えています",
        severity=AlertSeverity.WARNING,
        condition=lambda system_metrics: disk_usage_threshold(threshold=85.0, system_metrics=system_metrics),
        check_interval=60,
        notification_types=[NotificationType.CONSOLE],
        cooldown_period=600,
        enabled=True
    )
    
    # アラートルールを登録
    alert_manager.add_rule(cpu_alert)
    alert_manager.add_rule(memory_alert)
    alert_manager.add_rule(disk_alert)
    
    # メトリクスコレクターの登録（例）
    # カスタムメトリクスコレクターを作成して登録することができます
    
    # アラートチェックを開始
    alert_manager.start_all_rules()


# モジュール初期化時にデフォルトアラートルールを設定（オプション）
if config.ENABLE_DEFAULT_ALERTS:
    setup_default_alert_rules() 