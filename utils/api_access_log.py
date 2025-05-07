"""
APIアクセスログ管理モジュール。
APIへのアクセスを詳細に記録する機能を提供します。
"""

import os
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import ipaddress
import socket
import threading
import queue
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

try:
    from utils.logger import get_structured_logger
    logger = get_structured_logger("api_access_log")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("api_access_log")


class APIAccessLog:
    """APIアクセスログエントリ"""
    
    def __init__(
        self,
        request_id: str,
        timestamp: datetime,
        client_ip: str,
        method: str,
        path: str,
        query_params: Dict[str, Any],
        headers: Dict[str, str],
        user_agent: str,
        auth_info: Dict[str, Any],
        request_body: Optional[str],
        status_code: Optional[int] = None,
        response_time_ms: Optional[float] = None,
        response_size: Optional[int] = None,
        error_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            request_id: リクエストID
            timestamp: タイムスタンプ
            client_ip: クライアントIPアドレス
            method: HTTPメソッド
            path: リクエストパス
            query_params: クエリパラメータ
            headers: HTTPヘッダー（センシティブな情報は削除済み）
            user_agent: ユーザーエージェント
            auth_info: 認証情報（ユーザー名など、トークンや認証情報は含まない）
            request_body: リクエストボディ（センシティブな情報は削除済み）
            status_code: HTTPステータスコード
            response_time_ms: レスポンス時間（ミリ秒）
            response_size: レスポンスサイズ（バイト）
            error_info: エラー情報（エラーが発生した場合）
            metadata: 追加のメタデータ
        """
        self.request_id = request_id
        self.timestamp = timestamp
        self.client_ip = client_ip
        self.method = method
        self.path = path
        self.query_params = query_params
        self.headers = headers
        self.user_agent = user_agent
        self.auth_info = auth_info
        self.request_body = request_body
        self.status_code = status_code
        self.response_time_ms = response_time_ms
        self.response_size = response_size
        self.error_info = error_info or {}
        self.metadata = metadata or {}
        
        # 追加の解析情報
        self.parsed_info = self._parse_additional_info()
    
    def _parse_additional_info(self) -> Dict[str, Any]:
        """追加の解析情報を生成"""
        info = {}
        
        # IPの地理的情報（実際の実装ではGeoIPデータベースを使用）
        # info["geo_location"] = {"country": "??", "city": "??"}
        
        # リクエストのカテゴリを判定
        path_parts = self.path.strip("/").split("/")
        info["api_category"] = path_parts[0] if path_parts else "root"
        info["api_action"] = path_parts[1] if len(path_parts) > 1 else "index"
        
        return info
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "client_ip": self.client_ip,
            "method": self.method,
            "path": self.path,
            "query_params": self.query_params,
            "headers": self.headers,
            "user_agent": self.user_agent,
            "auth_info": self.auth_info,
            "request_body": self.request_body,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "response_size": self.response_size,
            "error_info": self.error_info,
            "metadata": self.metadata,
            "parsed_info": self.parsed_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIAccessLog':
        """辞書からインスタンスを作成"""
        timestamp = datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"]
        
        return cls(
            request_id=data["request_id"],
            timestamp=timestamp,
            client_ip=data["client_ip"],
            method=data["method"],
            path=data["path"],
            query_params=data["query_params"],
            headers=data["headers"],
            user_agent=data["user_agent"],
            auth_info=data["auth_info"],
            request_body=data["request_body"],
            status_code=data.get("status_code"),
            response_time_ms=data.get("response_time_ms"),
            response_size=data.get("response_size"),
            error_info=data.get("error_info", {}),
            metadata=data.get("metadata", {})
        )


class APIAccessLogManager:
    """APIアクセスログを管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/api_access_logs"):
        """
        Args:
            storage_path: ログを保存するディレクトリのパス
        """
        self.storage_path = os.path.abspath(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        
        # ログキュー（非同期書き込み用）
        self.log_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        
        # キャッシュ（最近のログをメモリに保持）
        self.recent_logs = []
        self.max_recent_logs = 1000  # メモリに保持する最近のログの最大数
        
        # 統計情報
        self.stats = defaultdict(int)
        self.anomaly_ips = set()  # 異常なアクセスを行ったIP
        
        # 設定
        self.sensitive_headers = {
            "authorization", "x-api-key", "cookie", "set-cookie", 
            "proxy-authorization", "x-csrf-token"
        }
        self.sensitive_body_fields = {
            "password", "token", "secret", "key", "api_key", "apikey", 
            "access_token", "refresh_token", "private_key", "credential"
        }
        
        logger.info(f"APIアクセスログマネージャーを初期化しました。保存先: {self.storage_path}")
    
    def _get_log_file_path(self, date: datetime) -> str:
        """日付に基づいてログファイルのパスを取得"""
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.storage_path, f"api_access_log_{date_str}.jsonl")
    
    def start_log_worker(self):
        """ログワーカースレッドを開始"""
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        
        self.running = True
        
        def _log_worker():
            """ログキューからログを取り出して保存するワーカー"""
            batch = []
            last_flush_time = time.time()
            
            while self.running:
                try:
                    # キューからログを取得（タイムアウト付き）
                    try:
                        log_entry = self.log_queue.get(timeout=1.0)
                        batch.append(log_entry)
                        self.log_queue.task_done()
                    except queue.Empty:
                        pass
                    
                    # バッチサイズが一定以上、または一定時間経過したらフラッシュ
                    current_time = time.time()
                    if len(batch) >= 100 or (batch and current_time - last_flush_time >= 5.0):
                        self._flush_log_batch(batch)
                        batch = []
                        last_flush_time = current_time
                
                except Exception as e:
                    logger.error(f"ログワーカーでエラーが発生しました: {str(e)}")
            
            # 残りのバッチをフラッシュ
            if batch:
                self._flush_log_batch(batch)
        
        self.worker_thread = threading.Thread(
            target=_log_worker,
            daemon=True,
            name="APIAccessLogWorker"
        )
        self.worker_thread.start()
        logger.info("APIアクセスログワーカーを開始しました")
    
    def stop_log_worker(self):
        """ログワーカースレッドを停止"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.running = False
            self.worker_thread.join(timeout=5.0)
            logger.info("APIアクセスログワーカーを停止しました")
    
    def _flush_log_batch(self, batch: List[APIAccessLog]):
        """ログバッチをファイルに書き込む"""
        logs_by_date = {}
        
        # 日付ごとにログをグループ化
        for log in batch:
            date = log.timestamp.date()
            if date not in logs_by_date:
                logs_by_date[date] = []
            logs_by_date[date].append(log)
        
        # 日付ごとにファイルに書き込み
        for date, logs in logs_by_date.items():
            try:
                log_file = self._get_log_file_path(date)
                with open(log_file, "a") as f:
                    for log in logs:
                        f.write(json.dumps(log.to_dict()) + "\n")
                
                logger.debug(f"{len(logs)} 件のアクセスログを {log_file} に書き込みました")
            
            except Exception as e:
                logger.error(f"アクセスログの書き込みに失敗しました: {str(e)}")
    
    def log_request(
        self,
        request: Request,
        auth_info: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        APIリクエストをログに記録する
        
        Args:
            request: FastAPIリクエスト
            auth_info: 認証情報（ユーザー名など、トークンは含まない）
            metadata: 追加のメタデータ
            
        Returns:
            str: リクエストID
        """
        try:
            # リクエストID生成
            request_id = str(uuid.uuid4())
            
            # クライアントIPの取得
            client_ip = request.client.host if request.client else "unknown"
            
            # HTTPヘッダーの処理（センシティブな情報を削除）
            headers = dict(request.headers)
            for header in self.sensitive_headers:
                if header.lower() in headers:
                    headers[header.lower()] = "[REDACTED]"
            
            # ユーザーエージェントの取得
            user_agent = request.headers.get("user-agent", "unknown")
            
            # リクエストに関連するデータを保存
            request.state.access_log = {
                "request_id": request_id,
                "start_time": time.time(),
                "client_ip": client_ip
            }
            
            # リクエストボディの処理は非同期で行われるため、
            # ここでは部分的なログエントリを作成
            log_entry = APIAccessLog(
                request_id=request_id,
                timestamp=datetime.now(),
                client_ip=client_ip,
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                headers=headers,
                user_agent=user_agent,
                auth_info=auth_info or {},
                request_body=None,  # レスポンス時に設定
                metadata=metadata or {}
            )
            
            # メモリキャッシュに追加
            self._add_to_recent_logs(log_entry)
            
            # 統計情報を更新
            self._update_stats(log_entry)
            
            return request_id
        
        except Exception as e:
            logger.error(f"リクエストログの記録に失敗しました: {str(e)}")
            return str(uuid.uuid4())  # エラー時はダミーのリクエストIDを返す
    
    async def log_response(
        self,
        request: Request,
        response: Response,
        request_body: Optional[str] = None,
        error_info: Optional[Dict[str, Any]] = None
    ):
        """
        APIレスポンスをログに記録する
        
        Args:
            request: FastAPIリクエスト
            response: FastAPIレスポンス
            request_body: リクエストボディ（センシティブな情報は削除済み）
            error_info: エラー情報（エラーが発生した場合）
        """
        try:
            # リクエスト情報を取得
            access_log_data = getattr(request.state, "access_log", None)
            if not access_log_data:
                logger.warning("リクエスト情報が見つかりません")
                return
            
            request_id = access_log_data.get("request_id", "unknown")
            start_time = access_log_data.get("start_time", time.time())
            client_ip = access_log_data.get("client_ip", "unknown")
            
            # レスポンス時間を計算
            response_time_ms = (time.time() - start_time) * 1000
            
            # リクエストボディのサニタイズ
            if request_body:
                try:
                    # JSONの場合はパースしてセンシティブフィールドを削除
                    if isinstance(request_body, str) and request_body.strip().startswith(("{", "[")):
                        body_data = json.loads(request_body)
                        self._sanitize_sensitive_data(body_data)
                        request_body = json.dumps(body_data)
                    elif isinstance(request_body, dict):
                        body_data = request_body.copy()
                        self._sanitize_sensitive_data(body_data)
                        request_body = json.dumps(body_data)
                except Exception:
                    # JSONでない場合はそのまま（機密情報があるかもしれないので注意）
                    pass
            
            # ログエントリを作成
            log_entry = APIAccessLog(
                request_id=request_id,
                timestamp=datetime.fromtimestamp(start_time),
                client_ip=client_ip,
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                headers=dict(request.headers),
                user_agent=request.headers.get("user-agent", "unknown"),
                auth_info={},  # レスポンス時には認証情報がないため空
                request_body=request_body,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                response_size=getattr(response, "content_length", None),
                error_info=error_info
            )
            
            # キューに追加
            self.log_queue.put(log_entry)
            
            # メモリキャッシュを更新
            self._update_recent_log(log_entry)
            
            # 統計情報を更新
            self._update_stats(log_entry)
            
            # 異常検知
            self._detect_anomalies(log_entry)
        
        except Exception as e:
            logger.error(f"レスポンスログの記録に失敗しました: {str(e)}")
    
    def _sanitize_sensitive_data(self, data: Any, path: str = ""):
        """
        データ内のセンシティブな情報を [REDACTED] に置き換える
        
        Args:
            data: サニタイズするデータ
            path: 現在のフィールドパス
        """
        if isinstance(data, dict):
            for key, value in list(data.items()):
                # キー名がセンシティブかチェック
                current_path = f"{path}.{key}" if path else key
                key_lower = key.lower()
                
                if any(sensitive in key_lower for sensitive in self.sensitive_body_fields):
                    data[key] = "[REDACTED]"
                else:
                    # 再帰的にチェック
                    self._sanitize_sensitive_data(value, current_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                self._sanitize_sensitive_data(item, current_path)
    
    def _add_to_recent_logs(self, log_entry: APIAccessLog):
        """最近のログリストにログを追加"""
        self.recent_logs.append(log_entry)
        
        # 最大数を超えた場合は古いログを削除
        if len(self.recent_logs) > self.max_recent_logs:
            self.recent_logs.pop(0)
    
    def _update_recent_log(self, log_entry: APIAccessLog):
        """既存のログエントリを更新"""
        for i, log in enumerate(self.recent_logs):
            if log.request_id == log_entry.request_id:
                self.recent_logs[i] = log_entry
                break
    
    def _update_stats(self, log_entry: APIAccessLog):
        """統計情報を更新"""
        self.stats["total_requests"] += 1
        
        # HTTPメソッド別カウント
        self.stats[f"method.{log_entry.method}"] += 1
        
        # パス別カウント
        path_key = log_entry.path
        if "?" in path_key:
            path_key = path_key.split("?")[0]
        self.stats[f"path.{path_key}"] += 1
        
        # ステータスコード別カウント
        if log_entry.status_code:
            status_category = f"{log_entry.status_code // 100}xx"
            self.stats[f"status.{status_category}"] += 1
            self.stats[f"status.{log_entry.status_code}"] += 1
        
        # クライアントIP別カウント
        self.stats[f"ip.{log_entry.client_ip}"] += 1
    
    def _detect_anomalies(self, log_entry: APIAccessLog):
        """
        異常なアクセスパターンを検知する
        
        Args:
            log_entry: 検査するログエントリ
        """
        # 短時間の大量アクセスを検知
        ip = log_entry.client_ip
        recent_time = datetime.now() - timedelta(minutes=5)
        
        # 最近5分間の同一IPからのアクセス数をカウント
        ip_count = sum(
            1 for log in self.recent_logs
            if log.client_ip == ip and log.timestamp >= recent_time
        )
        
        # 一定閾値を超えたら通知
        if ip_count > 50:  # 設定可能な閾値
            if ip not in self.anomaly_ips:
                logger.warning(f"異常なアクセスパターンを検知: {ip}からの{ip_count}件のリクエスト（5分間）")
                self.anomaly_ips.add(ip)
        
        # ステータスコードの異常を検知
        if log_entry.status_code and log_entry.status_code >= 400:
            # 特定のIPからの連続的なエラーをカウント
            error_count = sum(
                1 for log in self.recent_logs
                if log.client_ip == ip and log.status_code and log.status_code >= 400
                and log.timestamp >= recent_time
            )
            
            if error_count > 10:  # 設定可能な閾値
                logger.warning(f"異常なエラーパターンを検知: {ip}からの{error_count}件のエラー（5分間）")
    
    def get_recent_logs(self, limit: int = 100, filter_criteria: Dict[str, Any] = None) -> List[APIAccessLog]:
        """
        最近のログを取得する
        
        Args:
            limit: 取得するログの最大数
            filter_criteria: フィルター条件
            
        Returns:
            List[APIAccessLog]: ログエントリのリスト
        """
        logs = self.recent_logs
        
        # フィルタリング
        if filter_criteria:
            filtered_logs = []
            for log in logs:
                match = True
                
                for key, value in filter_criteria.items():
                    if key == "client_ip" and value != log.client_ip:
                        match = False
                        break
                    elif key == "method" and value != log.method:
                        match = False
                        break
                    elif key == "path" and value not in log.path:
                        match = False
                        break
                    elif key == "status_code" and log.status_code != value:
                        match = False
                        break
                    elif key == "min_time" and (not log.timestamp or log.timestamp < value):
                        match = False
                        break
                    elif key == "max_time" and (not log.timestamp or log.timestamp > value):
                        match = False
                        break
                
                if match:
                    filtered_logs.append(log)
            
            logs = filtered_logs
        
        # 最新順にソート
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)
        
        return logs[:limit]
    
    def search_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        filter_criteria: Dict[str, Any] = None,
        limit: int = 1000
    ) -> List[APIAccessLog]:
        """
        指定期間のログを検索する
        
        Args:
            start_date: 検索開始日
            end_date: 検索終了日
            filter_criteria: フィルター条件
            limit: 取得するログの最大数
            
        Returns:
            List[APIAccessLog]: ログエントリのリスト
        """
        logs = []
        
        # 検索対象の日付を生成
        current_date = start_date.date()
        end_date_value = end_date.date()
        
        while current_date <= end_date_value:
            log_file = self._get_log_file_path(current_date)
            
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            
                            log_data = json.loads(line)
                            log_entry = APIAccessLog.from_dict(log_data)
                            
                            # タイムスタンプでフィルタリング
                            if log_entry.timestamp < start_date or log_entry.timestamp > end_date:
                                continue
                            
                            # フィルター条件に一致するかチェック
                            if filter_criteria:
                                match = True
                                
                                for key, value in filter_criteria.items():
                                    if key == "client_ip" and value != log_entry.client_ip:
                                        match = False
                                        break
                                    elif key == "method" and value != log_entry.method:
                                        match = False
                                        break
                                    elif key == "path" and value not in log_entry.path:
                                        match = False
                                        break
                                    elif key == "status_code" and log_entry.status_code != value:
                                        match = False
                                        break
                                
                                if not match:
                                    continue
                            
                            logs.append(log_entry)
                            
                            # 最大数に達したら終了
                            if len(logs) >= limit:
                                return logs
                
                except Exception as e:
                    logger.error(f"ログファイル {log_file} の検索に失敗しました: {str(e)}")
            
            # 次の日へ
            current_date += timedelta(days=1)
        
        return logs
    
    def get_statistics(self, period: str = "day") -> Dict[str, Any]:
        """
        アクセス統計を取得する
        
        Args:
            period: 期間（"hour", "day", "week", "month"）
            
        Returns:
            Dict[str, Any]: 統計情報
        """
        stats = {
            "total_requests": self.stats["total_requests"],
            "methods": {},
            "status_codes": {},
            "paths": {},
            "top_ips": {},
            "anomalies": len(self.anomaly_ips)
        }
        
        # HTTPメソッド別統計
        for key, value in self.stats.items():
            if key.startswith("method."):
                method = key.replace("method.", "")
                stats["methods"][method] = value
        
        # ステータスコード別統計
        for key, value in self.stats.items():
            if key.startswith("status."):
                status = key.replace("status.", "")
                stats["status_codes"][status] = value
        
        # パス別統計（上位10件）
        path_stats = {}
        for key, value in self.stats.items():
            if key.startswith("path."):
                path = key.replace("path.", "")
                path_stats[path] = value
        
        stats["paths"] = dict(sorted(path_stats.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # IP別統計（上位10件）
        ip_stats = {}
        for key, value in self.stats.items():
            if key.startswith("ip."):
                ip = key.replace("ip.", "")
                ip_stats[ip] = value
        
        stats["top_ips"] = dict(sorted(ip_stats.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return stats
    
    def reset_statistics(self):
        """統計情報をリセットする"""
        self.stats = defaultdict(int)
        self.anomaly_ips.clear()
        logger.info("APIアクセス統計をリセットしました")


class APIAccessLogMiddleware(BaseHTTPMiddleware):
    """FastAPI用のAPIアクセスログミドルウェア"""
    
    def __init__(
        self, 
        app: ASGIApp, 
        log_manager: APIAccessLogManager = None,
        exclude_paths: List[str] = None
    ):
        """
        Args:
            app: ASGI アプリケーション
            log_manager: ログマネージャーインスタンス
            exclude_paths: ログから除外するパスのリスト
        """
        super().__init__(app)
        self.log_manager = log_manager or api_access_log_manager
        self.exclude_paths = exclude_paths or []
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """リクエストを処理し、ログを記録する"""
        # 除外パスかどうかをチェック
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # リクエストを記録
        auth_info = {}
        try:
            # 認証情報を取得（適切な方法で実装）
            # auth_header = request.headers.get("Authorization")
            # if auth_header and auth_header.startswith("Bearer "):
            #     token = auth_header.replace("Bearer ", "")
            #     # トークンを検証して認証情報を取得
            pass
        except Exception as e:
            logger.warning(f"認証情報の取得に失敗しました: {str(e)}")
        
        # リクエストログを記録
        self.log_manager.log_request(request, auth_info)
        
        # リクエストボディをコピー
        request_body = None
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                # リクエストボディをコピー
                body = await request.body()
                request_body = body.decode("utf-8")
                
                # リクエストボディをリセットして再利用可能にする
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
        except Exception as e:
            logger.warning(f"リクエストボディのコピーに失敗しました: {str(e)}")
        
        # レスポンスを処理
        error_info = None
        try:
            response = await call_next(request)
        except Exception as e:
            # エラー情報を記録
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            raise
        finally:
            # レスポンスログを記録
            await self.log_manager.log_response(
                request, 
                response if "response" in locals() else None,
                request_body, 
                error_info
            )
        
        return response


# シングルトンインスタンス
api_access_log_manager = APIAccessLogManager()

# ログワーカーを開始
api_access_log_manager.start_log_worker()


# ヘルパー関数
def get_access_log_middleware(
    exclude_paths: List[str] = None
) -> APIAccessLogMiddleware:
    """
    APIアクセスログミドルウェアを取得する
    
    Args:
        exclude_paths: ログから除外するパスのリスト
        
    Returns:
        APIAccessLogMiddleware: ミドルウェアインスタンス
    """
    return APIAccessLogMiddleware(
        app=None,  # FastAPIで初期化時に設定される
        log_manager=api_access_log_manager,
        exclude_paths=exclude_paths
    )


def get_recent_access_logs(
    limit: int = 100, 
    filter_criteria: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    最近のアクセスログを取得するヘルパー関数
    
    Args:
        limit: 取得するログの最大数
        filter_criteria: フィルター条件
        
    Returns:
        List[Dict[str, Any]]: ログエントリのリスト（辞書形式）
    """
    logs = api_access_log_manager.get_recent_logs(limit, filter_criteria)
    return [log.to_dict() for log in logs]


def search_access_logs(
    start_date: datetime,
    end_date: datetime,
    filter_criteria: Dict[str, Any] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    指定期間のアクセスログを検索するヘルパー関数
    
    Args:
        start_date: 検索開始日
        end_date: 検索終了日
        filter_criteria: フィルター条件
        limit: 取得するログの最大数
        
    Returns:
        List[Dict[str, Any]]: ログエントリのリスト（辞書形式）
    """
    logs = api_access_log_manager.search_logs(start_date, end_date, filter_criteria, limit)
    return [log.to_dict() for log in logs]


def get_access_statistics(period: str = "day") -> Dict[str, Any]:
    """
    アクセス統計を取得するヘルパー関数
    
    Args:
        period: 期間（"hour", "day", "week", "month"）
        
    Returns:
        Dict[str, Any]: 統計情報
    """
    return api_access_log_manager.get_statistics(period)


def reset_access_statistics():
    """統計情報をリセットするヘルパー関数"""
    api_access_log_manager.reset_statistics()


# アプリケーション終了時にログワーカーを停止するための関数
def shutdown_access_log_manager():
    """アプリケーション終了時にログマネージャーを適切にシャットダウン"""
    api_access_log_manager.stop_log_worker() 