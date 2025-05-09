"""
トレースサンプリングモジュール。
分散トレーシングのサンプリングレートを設定・管理するための機能を提供します。
"""

import random
import threading
from typing import Dict, Any, Optional, List, Callable
import time
import re

from utils.logger import get_structured_logger
from utils.config import config

# ロガーの取得
logger = get_structured_logger("trace_sampling")


class SamplingRule:
    """
    トレースサンプリングのルールを定義するクラス
    
    Attributes:
        name (str): ルール名
        pattern (str): マッチングパターン（正規表現）
        rate (float): サンプリングレート（0.0〜1.0）
        ttl (int): 有効期限（秒）
        created_at (float): 作成時刻
    """
    
    def __init__(
        self,
        name: str,
        pattern: str,
        rate: float = 1.0,
        ttl: Optional[int] = None
    ):
        """
        初期化
        
        Args:
            name: ルール名
            pattern: マッチングパターン（正規表現）
            rate: サンプリングレート（0.0〜1.0）
            ttl: 有効期限（秒）
        """
        self.name = name
        self.pattern = pattern
        self.rate = max(0.0, min(1.0, rate))  # 0.0〜1.0の範囲に制限
        self.ttl = ttl
        self.created_at = time.time()
        
        # パターンの正規表現をコンパイル
        self.regex = re.compile(pattern)
    
    def is_expired(self) -> bool:
        """
        ルールが有効期限切れかどうかをチェック
        
        Returns:
            bool: 有効期限切れならTrue
        """
        if self.ttl is None:
            return False
        
        return time.time() - self.created_at > self.ttl
    
    def matches(self, name: str) -> bool:
        """
        名前がパターンにマッチするかどうかをチェック
        
        Args:
            name: チェックする名前
            
        Returns:
            bool: マッチすればTrue
        """
        return bool(self.regex.search(name))
    
    def should_sample(self) -> bool:
        """
        サンプリングすべきかどうかをランダムに決定
        
        Returns:
            bool: サンプリングすべきならTrue
        """
        return random.random() < self.rate
    
    def to_dict(self) -> Dict[str, Any]:
        """
        ルール情報を辞書形式で取得
        
        Returns:
            Dict[str, Any]: ルール情報
        """
        return {
            "name": self.name,
            "pattern": self.pattern,
            "rate": self.rate,
            "ttl": self.ttl,
            "created_at": self.created_at,
            "expires_at": self.created_at + self.ttl if self.ttl else None
        }


class TraceSampler:
    """
    トレースサンプリングを管理するクラス
    
    Attributes:
        rules (Dict[str, SamplingRule]): 名前でインデックス付けされたサンプリングルール
        default_rate (float): デフォルトのサンプリングレート
        cleanup_interval (int): クリーンアップ間隔（秒）
        cleanup_thread (threading.Thread): クリーンアップスレッド
        stop_cleanup (threading.Event): クリーンアップ停止イベント
    """
    
    def __init__(self, default_rate: float = 1.0, cleanup_interval: int = 3600):
        """
        初期化
        
        Args:
            default_rate: デフォルトのサンプリングレート（0.0〜1.0）
            cleanup_interval: 期限切れルールのクリーンアップ間隔（秒）
        """
        self.rules: Dict[str, SamplingRule] = {}
        self.default_rate = max(0.0, min(1.0, default_rate))
        self.cleanup_interval = cleanup_interval
        self.cleanup_thread = None
        self.stop_cleanup = threading.Event()
        self.lock = threading.RLock()
        
        # クリーンアップスレッドを開始
        self._start_cleanup_thread()
    
    def add_rule(self, rule: SamplingRule) -> bool:
        """
        サンプリングルールを追加
        
        Args:
            rule: サンプリングルール
            
        Returns:
            bool: 追加に成功したらTrue
        """
        with self.lock:
            if rule.name in self.rules:
                logger.warning(f"同名のサンプリングルール '{rule.name}' が既に存在します。上書きします。")
            
            self.rules[rule.name] = rule
            logger.info(f"サンプリングルール '{rule.name}' を追加しました（レート: {rule.rate}, パターン: '{rule.pattern}'）")
            return True
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        サンプリングルールを削除
        
        Args:
            rule_name: ルール名
            
        Returns:
            bool: 削除に成功したらTrue
        """
        with self.lock:
            if rule_name not in self.rules:
                logger.warning(f"サンプリングルール '{rule_name}' が見つかりません")
                return False
            
            del self.rules[rule_name]
            logger.info(f"サンプリングルール '{rule_name}' を削除しました")
            return True
    
    def update_rule_rate(self, rule_name: str, rate: float) -> bool:
        """
        サンプリングルールのレートを更新
        
        Args:
            rule_name: ルール名
            rate: 新しいサンプリングレート（0.0〜1.0）
            
        Returns:
            bool: 更新に成功したらTrue
        """
        with self.lock:
            if rule_name not in self.rules:
                logger.warning(f"サンプリングルール '{rule_name}' が見つかりません")
                return False
            
            rate = max(0.0, min(1.0, rate))  # 0.0〜1.0の範囲に制限
            self.rules[rule_name].rate = rate
            logger.info(f"サンプリングルール '{rule_name}' のレートを {rate} に更新しました")
            return True
    
    def get_rule(self, rule_name: str) -> Optional[SamplingRule]:
        """
        サンプリングルールを取得
        
        Args:
            rule_name: ルール名
            
        Returns:
            Optional[SamplingRule]: サンプリングルール（存在しない場合はNone）
        """
        with self.lock:
            return self.rules.get(rule_name)
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """
        すべてのサンプリングルールを取得
        
        Returns:
            List[Dict[str, Any]]: ルール情報のリスト
        """
        with self.lock:
            return [rule.to_dict() for rule in self.rules.values()]
    
    def set_default_rate(self, rate: float):
        """
        デフォルトのサンプリングレートを設定
        
        Args:
            rate: サンプリングレート（0.0〜1.0）
        """
        rate = max(0.0, min(1.0, rate))  # 0.0〜1.0の範囲に制限
        self.default_rate = rate
        logger.info(f"デフォルトのサンプリングレートを {rate} に設定しました")
    
    def should_sample(self, name: str) -> bool:
        """
        指定された名前のトレースをサンプリングすべきかを判断
        
        Args:
            name: トレース名
            
        Returns:
            bool: サンプリングすべきならTrue
        """
        with self.lock:
            # 期限切れルールを除外
            active_rules = {k: v for k, v in self.rules.items() if not v.is_expired()}
            
            # パターンにマッチするルールを検索
            for rule in active_rules.values():
                if rule.matches(name):
                    return rule.should_sample()
            
            # マッチするルールがなければデフォルトレートを使用
            return random.random() < self.default_rate
    
    def _start_cleanup_thread(self):
        """クリーンアップスレッドを開始"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        self.stop_cleanup.clear()
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def _cleanup_loop(self):
        """期限切れルールのクリーンアップループ"""
        logger.debug("サンプリングルールクリーンアップスレッドを開始しました")
        
        while not self.stop_cleanup.wait(self.cleanup_interval):
            self._cleanup_expired_rules()
        
        logger.debug("サンプリングルールクリーンアップスレッドを終了しました")
    
    def _cleanup_expired_rules(self):
        """期限切れルールを削除"""
        with self.lock:
            # 期限切れルールのリストを作成
            expired_rules = [name for name, rule in self.rules.items() if rule.is_expired()]
            
            # 期限切れルールを削除
            for name in expired_rules:
                del self.rules[name]
            
            if expired_rules:
                logger.info(f"{len(expired_rules)}件の期限切れサンプリングルールを削除しました")
    
    def stop(self):
        """
        サンプラーを停止
        """
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.stop_cleanup.set()
            self.cleanup_thread.join(timeout=5)
            self.cleanup_thread = None


# シングルトンインスタンス
_trace_sampler = None


def get_trace_sampler() -> TraceSampler:
    """
    TraceSamplerのシングルトンインスタンスを取得
    
    Returns:
        TraceSampler: トレースサンプラー
    """
    global _trace_sampler
    
    if _trace_sampler is None:
        default_rate = getattr(config, "DEFAULT_TRACE_SAMPLING_RATE", 1.0)
        cleanup_interval = getattr(config, "TRACE_SAMPLING_CLEANUP_INTERVAL", 3600)
        
        _trace_sampler = TraceSampler(
            default_rate=default_rate,
            cleanup_interval=cleanup_interval
        )
        
        # 設定からルールを読み込む
        sampling_rules = getattr(config, "TRACE_SAMPLING_RULES", [])
        for rule_config in sampling_rules:
            rule = SamplingRule(
                name=rule_config.get("name", f"rule_{len(_trace_sampler.rules) + 1}"),
                pattern=rule_config.get("pattern", ".*"),
                rate=rule_config.get("rate", default_rate),
                ttl=rule_config.get("ttl")
            )
            _trace_sampler.add_rule(rule)
    
    return _trace_sampler


def should_sample_trace(name: str) -> bool:
    """
    指定された名前のトレースをサンプリングすべきかを判断する便利関数
    
    Args:
        name: トレース名
        
    Returns:
        bool: サンプリングすべきならTrue
    """
    sampler = get_trace_sampler()
    return sampler.should_sample(name)


def create_sampling_rule(
    name: str,
    pattern: str,
    rate: float = 1.0,
    ttl: Optional[int] = None
) -> bool:
    """
    サンプリングルールを作成する便利関数
    
    Args:
        name: ルール名
        pattern: マッチングパターン（正規表現）
        rate: サンプリングレート（0.0〜1.0）
        ttl: 有効期限（秒）
        
    Returns:
        bool: 作成に成功したらTrue
    """
    sampler = get_trace_sampler()
    rule = SamplingRule(name=name, pattern=pattern, rate=rate, ttl=ttl)
    return sampler.add_rule(rule)


def set_sampling_rate(rate: float):
    """
    デフォルトのサンプリングレートを設定する便利関数
    
    Args:
        rate: サンプリングレート（0.0〜1.0）
    """
    sampler = get_trace_sampler()
    sampler.set_default_rate(rate) 