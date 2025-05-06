"""
モニタリングダッシュボード用のAPIルートモジュール。
システムのパフォーマンスメトリクス、アラート情報、トレース情報などを提供するAPIエンドポイントを定義します。
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query, Path, status, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from utils.logger import get_structured_logger
from utils.tracing import tracer, trace, add_trace_event
from utils.alerting import alert_manager, AlertSeverity, AlertStatus, AlertRule
from utils.config import config
from api.auth import get_current_active_user, User

# ルーターの設定
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# ロガーの取得
logger = get_structured_logger("api.monitoring")

# テンプレートの設定
templates = Jinja2Templates(directory="templates")


# モデル定義
class MetricDataPoint(BaseModel):
    """メトリクスデータポイントのモデル"""
    timestamp: str
    value: float


class MetricSeries(BaseModel):
    """メトリクス系列のモデル"""
    name: str
    data: List[MetricDataPoint]
    unit: str = ""
    description: str = ""


class MetricsResponse(BaseModel):
    """メトリクス応答のモデル"""
    metrics: Dict[str, MetricSeries]
    timestamp: str


class AlertInfo(BaseModel):
    """アラート情報のモデル"""
    rule_id: str
    name: str
    description: str
    severity: str
    status: str
    triggered_at: str
    last_triggered: Optional[str] = None
    trigger_count: int
    context: Dict[str, Any] = {}


class AlertsResponse(BaseModel):
    """アラート応答のモデル"""
    active_alerts: List[AlertInfo]
    alert_history: List[AlertInfo] = []
    timestamp: str


class TraceInfo(BaseModel):
    """トレース情報のモデル"""
    trace_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    total_spans: int
    error: bool = False
    attributes: Dict[str, Any] = {}


class TracesResponse(BaseModel):
    """トレース応答のモデル"""
    traces: List[TraceInfo]
    timestamp: str


class SystemStatusResponse(BaseModel):
    """システム状態の応答モデル"""
    status: str
    uptime: int  # 秒単位
    active_alerts_count: int
    recent_traces_count: int
    memory_usage_percent: float
    cpu_usage_percent: float
    disk_usage_percent: float
    timestamp: str


# グローバル変数
_start_time = time.time()  # アプリケーションの起動時間
_metric_history: Dict[str, List[Dict[str, Any]]] = {
    "cpu": [],
    "memory": [],
    "disk": [],
    "api_requests": [],
    "error_rate": []
}


# モック用のメトリクスデータ生成関数（実際の実装では実際のシステムメトリクスを収集）
def _collect_current_metrics() -> Dict[str, Any]:
    """現在のメトリクスを収集"""
    try:
        # システムメトリクスの収集
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        metrics = {
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "percent": memory.percent,
                "available_mb": memory.available / (1024 * 1024),
                "total_mb": memory.total / (1024 * 1024)
            },
            "disk": {
                "percent": disk.percent,
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "total_gb": disk.total / (1024 * 1024 * 1024)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return metrics
    except ImportError:
        # psutilがインストールされていない場合はモックデータを返す
        import random
        
        return {
            "cpu": {
                "percent": random.uniform(5, 80),
                "count": 4
            },
            "memory": {
                "percent": random.uniform(20, 90),
                "available_mb": 2048,
                "total_mb": 8192
            },
            "disk": {
                "percent": random.uniform(30, 70),
                "free_gb": 50,
                "total_gb": 100
            },
            "timestamp": datetime.now().isoformat()
        }


def _update_metric_history():
    """メトリクス履歴を更新"""
    # 現在のメトリクスを取得
    current_metrics = _collect_current_metrics()
    timestamp = datetime.now().isoformat()
    
    # 履歴に追加
    _metric_history["cpu"].append({
        "timestamp": timestamp,
        "value": current_metrics["cpu"]["percent"]
    })
    
    _metric_history["memory"].append({
        "timestamp": timestamp,
        "value": current_metrics["memory"]["percent"]
    })
    
    _metric_history["disk"].append({
        "timestamp": timestamp,
        "value": current_metrics["disk"]["percent"]
    })
    
    # APIリクエスト数とエラー率はモックデータ
    import random
    _metric_history["api_requests"].append({
        "timestamp": timestamp,
        "value": random.randint(1, 100)
    })
    
    _metric_history["error_rate"].append({
        "timestamp": timestamp,
        "value": random.uniform(0, 5)
    })
    
    # 履歴サイズを制限（最新の100データポイントのみ保持）
    max_history = 100
    for key in _metric_history:
        if len(_metric_history[key]) > max_history:
            _metric_history[key] = _metric_history[key][-max_history:]


@router.get("/metrics", response_model=MetricsResponse)
@trace("get_metrics_api")
async def get_metrics(
    minutes: int = Query(30, description="取得する履歴の分数"),
    current_user: User = Depends(get_current_active_user)
):
    """
    システムメトリクスを取得するエンドポイント
    
    Args:
        minutes: 取得する履歴の分数
        current_user: 現在のユーザー
        
    Returns:
        MetricsResponse: メトリクスデータ
    """
    # リクエストをトレース情報に記録
    add_trace_event("get_metrics_request", {"minutes": minutes, "user": current_user.username})
    
    # 現在のメトリクスを取得して履歴を更新
    _update_metric_history()
    
    # 指定された時間範囲内のデータを抽出
    cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    
    metrics_response = {
        "metrics": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # CPU使用率
    metrics_response["metrics"]["cpu_usage"] = {
        "name": "CPU使用率",
        "data": [
            point for point in _metric_history["cpu"] 
            if point["timestamp"] >= cutoff_time
        ],
        "unit": "%",
        "description": "システム全体のCPU使用率"
    }
    
    # メモリ使用率
    metrics_response["metrics"]["memory_usage"] = {
        "name": "メモリ使用率",
        "data": [
            point for point in _metric_history["memory"] 
            if point["timestamp"] >= cutoff_time
        ],
        "unit": "%",
        "description": "システム全体のメモリ使用率"
    }
    
    # ディスク使用率
    metrics_response["metrics"]["disk_usage"] = {
        "name": "ディスク使用率",
        "data": [
            point for point in _metric_history["disk"] 
            if point["timestamp"] >= cutoff_time
        ],
        "unit": "%",
        "description": "システム全体のディスク使用率"
    }
    
    # APIリクエスト数
    metrics_response["metrics"]["api_requests"] = {
        "name": "APIリクエスト数",
        "data": [
            point for point in _metric_history["api_requests"] 
            if point["timestamp"] >= cutoff_time
        ],
        "unit": "件/分",
        "description": "1分あたりのAPIリクエスト数"
    }
    
    # エラー率
    metrics_response["metrics"]["error_rate"] = {
        "name": "エラー率",
        "data": [
            point for point in _metric_history["error_rate"] 
            if point["timestamp"] >= cutoff_time
        ],
        "unit": "%",
        "description": "APIリクエストのエラー率"
    }
    
    logger.info("メトリクスデータを取得しました", context={"user": current_user.username, "minutes": minutes})
    return metrics_response


@router.get("/alerts", response_model=AlertsResponse)
@trace("get_alerts_api")
async def get_alerts(
    include_history: bool = Query(False, description="履歴アラートを含めるかどうか"),
    current_user: User = Depends(get_current_active_user)
):
    """
    アラート情報を取得するエンドポイント
    
    Args:
        include_history: 履歴アラートを含めるかどうか
        current_user: 現在のユーザー
        
    Returns:
        AlertsResponse: アラート情報
    """
    # アクティブなアラートを取得
    active_alerts = alert_manager.get_active_alerts()
    
    # レスポンス形式に変換
    alerts_response = {
        "active_alerts": [],
        "alert_history": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # アクティブアラートを追加
    for rule_id, alert_info in active_alerts.items():
        rule_dict = alert_info.get("rule", {})
        alerts_response["active_alerts"].append({
            "rule_id": rule_id,
            "name": rule_dict.get("name", "Unknown"),
            "description": rule_dict.get("description", ""),
            "severity": rule_dict.get("severity", "unknown"),
            "status": rule_dict.get("last_status", "active"),
            "triggered_at": alert_info.get("triggered_at", ""),
            "last_triggered": rule_dict.get("last_triggered", ""),
            "trigger_count": rule_dict.get("trigger_count", 0),
            "context": alert_info.get("context", {})
        })
    
    # 履歴アラートを追加（現在は実装なし、将来的に履歴機能を追加予定）
    if include_history:
        # ここで履歴アラートを取得する（実装例はスキップ）
        pass
    
    logger.info("アラート情報を取得しました", context={
        "user": current_user.username,
        "active_alert_count": len(alerts_response["active_alerts"]),
        "include_history": include_history
    })
    
    return alerts_response


@router.get("/traces", response_model=TracesResponse)
@trace("get_traces_api")
async def get_traces(
    minutes: int = Query(30, description="取得する履歴の分数"),
    limit: int = Query(20, description="取得する最大トレース数"),
    current_user: User = Depends(get_current_active_user)
):
    """
    トレース情報を取得するエンドポイント
    
    Args:
        minutes: 取得する履歴の分数
        limit: 取得する最大トレース数
        current_user: 現在のユーザー
        
    Returns:
        TracesResponse: トレース情報
    """
    # トレース情報を取得
    # 注意: 現在のトレーサー実装では履歴保存機能が限定的なので、モックデータで代用
    # 実際の実装では、トレーサーの機能を拡張して履歴を取得するか、外部のトレースストレージから取得する
    
    # モックデータ
    import random
    
    traces_response = {
        "traces": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # 現在保存されているトレースを取得（モックデータ）
    for i in range(min(limit, 10)):  # モックデータでは最大10件
        start_time = time.time() - random.uniform(0, minutes * 60)
        duration = random.uniform(0.01, 5.0)  # 10ms～5000ms
        
        trace_info = {
            "trace_id": f"trace-{i+1}",
            "name": f"sample-operation-{i+1}",
            "start_time": start_time,
            "end_time": start_time + duration,
            "duration_ms": duration * 1000,
            "total_spans": random.randint(1, 20),
            "error": random.random() < 0.2,  # 20%の確率でエラー
            "attributes": {
                "service": "ai_team",
                "operation": f"operation-{i+1}",
                "user": current_user.username
            }
        }
        
        traces_response["traces"].append(trace_info)
    
    logger.info("トレース情報を取得しました", context={
        "user": current_user.username,
        "minutes": minutes,
        "limit": limit,
        "trace_count": len(traces_response["traces"])
    })
    
    return traces_response


@router.get("/status", response_model=SystemStatusResponse)
@trace("get_system_status_api")
async def get_system_status(current_user: User = Depends(get_current_active_user)):
    """
    システム全体の状態を取得するエンドポイント
    
    Args:
        current_user: 現在のユーザー
        
    Returns:
        SystemStatusResponse: システム状態
    """
    # 現在のメトリクスを取得
    current_metrics = _collect_current_metrics()
    
    # アクティブなアラート数を取得
    active_alerts = alert_manager.get_active_alerts()
    
    # システム状態を判断
    if len(active_alerts) > 0 and any(
        alert.get("rule", {}).get("severity") in ["error", "critical"] 
        for alert in active_alerts.values()
    ):
        status = "error"
    elif current_metrics["cpu"]["percent"] > 80 or current_metrics["memory"]["percent"] > 80:
        status = "warning"
    else:
        status = "healthy"
    
    # 稼働時間を計算
    uptime = int(time.time() - _start_time)
    
    # レスポンスを作成
    response = {
        "status": status,
        "uptime": uptime,
        "active_alerts_count": len(active_alerts),
        "recent_traces_count": len(tracer.spans),  # スパン数として代用
        "memory_usage_percent": current_metrics["memory"]["percent"],
        "cpu_usage_percent": current_metrics["cpu"]["percent"],
        "disk_usage_percent": current_metrics["disk"]["percent"],
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info("システム状態を取得しました", context={
        "user": current_user.username,
        "status": status,
        "active_alerts_count": len(active_alerts)
    })
    
    return response


@router.post("/alerts/{rule_id}/acknowledge")
@trace("acknowledge_alert_api")
async def acknowledge_alert(
    rule_id: str = Path(..., description="アラートルールID"),
    current_user: User = Depends(get_current_active_user)
):
    """
    アラートを確認済みとしてマークするエンドポイント
    
    Args:
        rule_id: アラートルールID
        current_user: 現在のユーザー
        
    Returns:
        Dict: 処理結果
    """
    result = alert_manager.acknowledge_alert(rule_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"アラートルール {rule_id} が見つかりません"
        )
    
    logger.info(f"アラート {rule_id} を確認済みとしてマークしました", context={
        "user": current_user.username,
        "rule_id": rule_id
    })
    
    return {"status": "success", "message": f"アラート {rule_id} を確認済みとしてマークしました"}


@router.post("/alerts/{rule_id}/silence")
@trace("silence_alert_api")
async def silence_alert(
    rule_id: str = Path(..., description="アラートルールID"),
    duration: int = Query(3600, description="無効化する期間（秒）"),
    current_user: User = Depends(get_current_active_user)
):
    """
    アラートを一時的に無効化するエンドポイント
    
    Args:
        rule_id: アラートルールID
        duration: 無効化する期間（秒）
        current_user: 現在のユーザー
        
    Returns:
        Dict: 処理結果
    """
    result = alert_manager.silence_alert(rule_id, duration)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"アラートルール {rule_id} が見つかりません"
        )
    
    logger.info(f"アラート {rule_id} を {duration} 秒間無効化しました", context={
        "user": current_user.username,
        "rule_id": rule_id,
        "duration": duration
    })
    
    return {
        "status": "success", 
        "message": f"アラート {rule_id} を {duration} 秒間無効化しました",
        "silenced_until": (datetime.now() + timedelta(seconds=duration)).isoformat()
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    モニタリングダッシュボードUIを提供するエンドポイント
    
    Args:
        request: リクエスト
        
    Returns:
        HTMLResponse: ダッシュボードUI
    """
    # テンプレートを返す
    try:
        return templates.TemplateResponse(
            "monitoring_dashboard.html",
            {"request": request, "title": "システムモニタリングダッシュボード"}
        )
    except Exception as e:
        logger.error(f"ダッシュボードテンプレートの読み込みに失敗しました: {str(e)}")
        return HTMLResponse(content=f"""
        <html>
            <head><title>モニタリングダッシュボード</title></head>
            <body>
                <h1>モニタリングダッシュボード</h1>
                <p>テンプレートの読み込みに失敗しました: {str(e)}</p>
                <p>templates/monitoring_dashboard.html が存在することを確認してください。</p>
            </body>
        </html>
        """)


# 初期化時にメトリクス履歴を更新
_update_metric_history() 