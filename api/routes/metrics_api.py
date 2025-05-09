"""
カスタムメトリクス管理API。
カスタムメトリクスの定義、更新、削除、取得のためのエンドポイントを提供します。
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
import time
from enum import Enum

from utils.monitoring import (
    MetricsCollector, MetricType, MetricUnit, 
    metrics_collector, _get_metric_storage
)
from utils.logger import get_structured_logger
from api.auth import get_current_user, verify_api_key

# ロガーの取得
logger = get_structured_logger("metrics_api")

# APIルーターの初期化
router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# リクエスト/レスポンスモデル定義
class MetricTypeEnum(str, Enum):
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricUnitEnum(str, Enum):
    PERCENTAGE = "percentage"
    BYTES = "bytes"
    SECONDS = "seconds"
    MILLISECONDS = "ms"
    COUNT = "count"
    BYTES_PER_SECOND = "bps"
    REQUESTS_PER_SECOND = "rps"
    CUSTOM = "custom"


class CreateMetricRequest(BaseModel):
    name: str = Field(..., description="メトリクス名", example="app_active_users")
    description: str = Field(..., description="メトリクスの説明", example="アクティブユーザー数")
    metric_type: MetricTypeEnum = Field(..., description="メトリクスの種類")
    unit: MetricUnitEnum = Field(MetricUnitEnum.CUSTOM, description="メトリクスの単位")
    labels: Optional[List[str]] = Field(None, description="メトリクスラベル", example=["region", "device"])
    aggregation_period: Optional[int] = Field(None, description="集計期間（秒）", example=300)
    collection_interval: Optional[int] = Field(60, description="収集間隔（秒）", example=60)


class UpdateMetricRequest(BaseModel):
    description: Optional[str] = Field(None, description="メトリクスの説明", example="アクティブユーザー数")
    metric_type: Optional[MetricTypeEnum] = Field(None, description="メトリクスの種類")
    unit: Optional[MetricUnitEnum] = Field(None, description="メトリクスの単位")
    labels: Optional[List[str]] = Field(None, description="メトリクスラベル", example=["region", "device"])
    aggregation_period: Optional[int] = Field(None, description="集計期間（秒）", example=300)
    collection_interval: Optional[int] = Field(None, description="収集間隔（秒）", example=60)


class RecordMetricRequest(BaseModel):
    value: Union[float, int, List[float]] = Field(..., description="メトリクス値", example=42.5)
    labels: Optional[Dict[str, str]] = Field(None, description="メトリクスラベル", example={"region": "tokyo", "device": "mobile"})
    timestamp: Optional[float] = Field(None, description="タイムスタンプ（秒）", example=1625097600)


class MetricDefinitionResponse(BaseModel):
    name: str = Field(..., description="メトリクス名")
    description: str = Field(..., description="メトリクスの説明")
    metric_type: str = Field(..., description="メトリクスの種類")
    unit: str = Field(..., description="メトリクスの単位")
    labels: List[str] = Field(..., description="メトリクスラベル")
    aggregation_period: Optional[int] = Field(None, description="集計期間（秒）")
    has_collector: bool = Field(..., description="収集関数が設定されているか")


# ヘルパー関数
def _map_metric_type(type_enum: MetricTypeEnum) -> MetricType:
    """MetricTypeEnumからMetricTypeへの変換"""
    mapping = {
        MetricTypeEnum.GAUGE: MetricType.GAUGE,
        MetricTypeEnum.COUNTER: MetricType.COUNTER,
        MetricTypeEnum.HISTOGRAM: MetricType.HISTOGRAM,
        MetricTypeEnum.SUMMARY: MetricType.SUMMARY
    }
    return mapping[type_enum]


def _map_metric_unit(unit_enum: MetricUnitEnum) -> MetricUnit:
    """MetricUnitEnumからMetricUnitへの変換"""
    mapping = {
        MetricUnitEnum.PERCENTAGE: MetricUnit.PERCENTAGE,
        MetricUnitEnum.BYTES: MetricUnit.BYTES,
        MetricUnitEnum.SECONDS: MetricUnit.SECONDS,
        MetricUnitEnum.MILLISECONDS: MetricUnit.MILLISECONDS,
        MetricUnitEnum.COUNT: MetricUnit.COUNT,
        MetricUnitEnum.BYTES_PER_SECOND: MetricUnit.BYTES_PER_SECOND,
        MetricUnitEnum.REQUESTS_PER_SECOND: MetricUnit.REQUESTS_PER_SECOND,
        MetricUnitEnum.CUSTOM: MetricUnit.CUSTOM
    }
    return mapping[unit_enum]


# APIエンドポイント
@router.post("/custom", response_model=MetricDefinitionResponse, status_code=201)
async def create_custom_metric(
    request: CreateMetricRequest,
    current_user: dict = Depends(get_current_user)
):
    """カスタムメトリクスを作成します"""
    try:
        # すでに同じ名前のメトリクスが存在するか確認
        existing_metrics = metrics_collector.get_custom_metric_definitions()
        if request.name in existing_metrics:
            raise HTTPException(
                status_code=409,
                detail=f"メトリクス {request.name} は既に存在します"
            )
        
        # メトリクス定義を作成
        metric_definition = metrics_collector.define_custom_metric(
            name=request.name,
            description=request.description,
            metric_type=_map_metric_type(request.metric_type),
            unit=_map_metric_unit(request.unit),
            labels=request.labels,
            aggregation_period=request.aggregation_period,
            collection_interval=request.collection_interval
        )
        
        # レスポンスを生成
        return {
            "name": metric_definition.name,
            "description": metric_definition.description,
            "metric_type": metric_definition.metric_type.value,
            "unit": metric_definition.unit.value,
            "labels": metric_definition.labels or [],
            "aggregation_period": metric_definition.aggregation_period,
            "has_collector": request.name in metrics_collector.collectors
        }
    except Exception as e:
        logger.error(f"カスタムメトリクス作成エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクスの作成中にエラーが発生しました: {str(e)}"
        )


@router.put("/custom/{name}", response_model=MetricDefinitionResponse)
async def update_custom_metric(
    name: str = Path(..., description="メトリクス名"),
    request: UpdateMetricRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """カスタムメトリクスを更新します"""
    try:
        # メトリクスが存在するか確認
        existing_metrics = metrics_collector.get_custom_metric_definitions()
        if name not in existing_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"メトリクス {name} が見つかりません"
            )
        
        # 更新に必要なパラメータを準備
        update_params = {}
        
        if request.description is not None:
            update_params["description"] = request.description
        
        if request.metric_type is not None:
            update_params["metric_type"] = _map_metric_type(request.metric_type)
        
        if request.unit is not None:
            update_params["unit"] = _map_metric_unit(request.unit)
        
        if request.labels is not None:
            update_params["labels"] = request.labels
        
        if request.aggregation_period is not None:
            update_params["aggregation_period"] = request.aggregation_period
        
        # 収集間隔の更新（存在する場合のみ）
        if request.collection_interval is not None and name in metrics_collector.collectors:
            metrics_collector.collection_intervals[name] = request.collection_interval
            
            # 実行中のコレクターがあれば再起動
            if name in metrics_collector.stop_events:
                metrics_collector.stop_collector(name)
                metrics_collector.start_collector(name)
        
        # メトリクス定義を更新
        success = metrics_collector.update_custom_metric_definition(name, **update_params)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"メトリクス {name} の更新に失敗しました"
            )
        
        # 更新後の定義を取得
        updated_metrics = metrics_collector.get_custom_metric_definitions()
        updated_definition = updated_metrics[name]
        
        # レスポンスを生成
        return {
            "name": updated_definition.name,
            "description": updated_definition.description,
            "metric_type": updated_definition.metric_type.value,
            "unit": updated_definition.unit.value,
            "labels": updated_definition.labels or [],
            "aggregation_period": updated_definition.aggregation_period,
            "has_collector": name in metrics_collector.collectors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"カスタムメトリクス更新エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクスの更新中にエラーが発生しました: {str(e)}"
        )


@router.delete("/custom/{name}", status_code=204)
async def delete_custom_metric(
    name: str = Path(..., description="メトリクス名"),
    current_user: dict = Depends(get_current_user)
):
    """カスタムメトリクスを削除します"""
    try:
        # メトリクスが存在するか確認
        existing_metrics = metrics_collector.get_custom_metric_definitions()
        if name not in existing_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"メトリクス {name} が見つかりません"
            )
        
        # メトリクスを削除
        success = metrics_collector.delete_custom_metric(name)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"メトリクス {name} の削除に失敗しました"
            )
        
        return None  # 204 No Content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"カスタムメトリクス削除エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクスの削除中にエラーが発生しました: {str(e)}"
        )


@router.get("/custom", response_model=List[MetricDefinitionResponse])
async def list_custom_metrics(
    current_user: dict = Depends(verify_api_key)
):
    """すべてのカスタムメトリクスを取得します"""
    try:
        # カスタムメトリクス定義を取得
        custom_metrics = metrics_collector.get_custom_metric_definitions()
        
        # レスポンスを生成
        result = []
        for name, definition in custom_metrics.items():
            result.append({
                "name": definition.name,
                "description": definition.description,
                "metric_type": definition.metric_type.value,
                "unit": definition.unit.value,
                "labels": definition.labels or [],
                "aggregation_period": definition.aggregation_period,
                "has_collector": name in metrics_collector.collectors
            })
        
        return result
    except Exception as e:
        logger.error(f"カスタムメトリクス一覧取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクス一覧の取得中にエラーが発生しました: {str(e)}"
        )


@router.get("/custom/{name}", response_model=MetricDefinitionResponse)
async def get_custom_metric(
    name: str = Path(..., description="メトリクス名"),
    current_user: dict = Depends(verify_api_key)
):
    """指定されたカスタムメトリクスの定義を取得します"""
    try:
        # カスタムメトリクス定義を取得
        custom_metrics = metrics_collector.get_custom_metric_definitions()
        
        if name not in custom_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"メトリクス {name} が見つかりません"
            )
        
        definition = custom_metrics[name]
        
        # レスポンスを生成
        return {
            "name": definition.name,
            "description": definition.description,
            "metric_type": definition.metric_type.value,
            "unit": definition.unit.value,
            "labels": definition.labels or [],
            "aggregation_period": definition.aggregation_period,
            "has_collector": name in metrics_collector.collectors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"カスタムメトリクス取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクスの取得中にエラーが発生しました: {str(e)}"
        )


@router.post("/custom/{name}/record", status_code=201)
async def record_custom_metric(
    name: str = Path(..., description="メトリクス名"),
    request: RecordMetricRequest = Body(...),
    current_user: dict = Depends(verify_api_key)
):
    """カスタムメトリクスに値を記録します"""
    try:
        # メトリクスが存在するか確認
        custom_metrics = metrics_collector.get_custom_metric_definitions()
        if name not in custom_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"メトリクス {name} が見つかりません"
            )
        
        # タイムスタンプの処理
        if request.timestamp:
            # タイムスタンプが指定されている場合は直接ストレージを使用
            from utils.monitoring import MetricValue
            
            metric = MetricValue(
                name=name,
                value=request.value,
                timestamp=request.timestamp,
                labels=request.labels or {}
            )
            
            storage = _get_metric_storage()
            storage.store_metric_value(metric)
        else:
            # 現在時刻で記録
            success = metrics_collector.record_custom_metric_value(
                name=name,
                value=request.value,
                labels=request.labels
            )
            
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"メトリクス {name} の値記録に失敗しました"
                )
        
        return {"status": "success", "message": f"メトリクス {name} に値を記録しました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"カスタムメトリクス値記録エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"メトリクス値の記録中にエラーが発生しました: {str(e)}"
        ) 