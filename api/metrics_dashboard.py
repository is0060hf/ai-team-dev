"""
メトリクスモニタリングダッシュボード。
システムの各種メトリクスを可視化します。
"""

import dash
from dash import dcc, html, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import os
from pathlib import Path

from utils.config import config
from utils.monitoring import _get_metric_storage

# アプリケーションの初期化
app = dash.Dash(
    __name__,
    title="メトリクスモニタリングダッシュボード",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap"
    ]
)

# ストレージインスタンス
metric_storage = _get_metric_storage()

# レイアウト
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("メトリクスモニタリングダッシュボード", className="header-title"),
        html.Div([
            html.Button("更新", id="refresh-button", className="refresh-button"),
            dcc.Interval(id="auto-refresh", interval=30000, n_intervals=0)  # 30秒ごとに自動更新
        ], className="header-actions")
    ], className="header"),
    
    # フィルターと時間範囲選択
    html.Div([
        html.Div([
            html.H2("時間範囲"),
            dcc.RadioItems(
                id="time-range",
                options=[
                    {"label": "30分", "value": "30m"},
                    {"label": "1時間", "value": "1h"},
                    {"label": "3時間", "value": "3h"},
                    {"label": "12時間", "value": "12h"},
                    {"label": "24時間", "value": "24h"},
                    {"label": "3日間", "value": "3d"},
                    {"label": "7日間", "value": "7d"}
                ],
                value="1h",
                inline=True
            )
        ], className="time-filter"),
        
        html.Div([
            html.H2("メトリクスカテゴリ"),
            dcc.Checklist(
                id="metric-categories",
                options=[
                    {"label": "システムメトリクス", "value": "system"},
                    {"label": "APIメトリクス", "value": "api"},
                    {"label": "カスタムメトリクス", "value": "custom"}
                ],
                value=["system", "api", "custom"],
                inline=True
            )
        ], className="metric-filter")
    ], className="filters"),
    
    # メインコンテンツ
    html.Div([
        # 左側：サマリーと統計情報
        html.Div([
            # サマリーカード
            html.Div(id="summary-cards", className="summary-cards"),
            
            # システムメトリクス
            html.Div([
                html.H2("システムメトリクス"),
                html.Div(id="system-metrics-graphs", className="metrics-graphs")
            ], className="section", id="system-metrics-section"),
            
            # APIメトリクス
            html.Div([
                html.H2("APIメトリクス"),
                html.Div(id="api-metrics-graphs", className="metrics-graphs")
            ], className="section", id="api-metrics-section"),
            
            # カスタムメトリクス
            html.Div([
                html.H2("カスタムメトリクス"),
                html.Div(id="custom-metrics-graphs", className="metrics-graphs")
            ], className="section", id="custom-metrics-section")
        ], className="column main-column"),
        
        # 右側：メトリクスリストとディテール
        html.Div([
            # メトリクスフィルター
            html.Div([
                html.H2("メトリクスフィルター"),
                dcc.Input(
                    id="metric-search",
                    type="text",
                    placeholder="メトリクス名で検索...",
                    className="search-input"
                ),
                html.Div(id="metric-list", className="metric-list")
            ], className="section"),
            
            # メトリクス詳細
            html.Div([
                html.H2("メトリクス詳細", id="metric-detail-title"),
                html.Div(id="metric-detail", className="metric-detail")
            ], className="section")
        ], className="column side-column")
    ], className="main-content"),
    
    # 隠し要素：データストア
    dcc.Store(id="metrics-data"),
    dcc.Store(id="selected-metric-name")
])


# データ取得関数
def get_available_metrics():
    """利用可能なメトリクスの定義を取得"""
    try:
        conn = sqlite3.connect(metric_storage.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metric_definitions")
        
        metrics = []
        for row in cursor.fetchall():
            metrics.append({
                "name": row[0],
                "description": row[1],
                "type": row[2],
                "unit": row[3],
                "labels": json.loads(row[4]) if row[4] else [],
                "aggregation_period": row[5]
            })
        
        conn.close()
        return metrics
    except Exception as e:
        print(f"メトリクス定義取得エラー: {str(e)}")
        return []

def get_metric_values(name, start_time=None, end_time=None, limit=1000):
    """メトリクス値を取得"""
    try:
        return metric_storage.get_metric_values(
            name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    except Exception as e:
        print(f"メトリクス値取得エラー: {str(e)}")
        return []

def get_aggregated_metrics(name, aggregation="avg", interval="5m", start_time=None, end_time=None):
    """集約されたメトリクス値を取得"""
    try:
        return metric_storage.get_aggregated_metrics(
            name,
            aggregation=aggregation,
            interval=interval,
            start_time=start_time,
            end_time=end_time
        )
    except Exception as e:
        print(f"集約メトリクス取得エラー: {str(e)}")
        return []

def get_time_range_timestamps(time_range):
    """時間範囲の開始時刻と終了時刻を取得"""
    now = datetime.now()
    end_time = now.timestamp()
    
    if time_range == "30m":
        start_time = (now - timedelta(minutes=30)).timestamp()
    elif time_range == "1h":
        start_time = (now - timedelta(hours=1)).timestamp()
    elif time_range == "3h":
        start_time = (now - timedelta(hours=3)).timestamp()
    elif time_range == "12h":
        start_time = (now - timedelta(hours=12)).timestamp()
    elif time_range == "24h":
        start_time = (now - timedelta(hours=24)).timestamp()
    elif time_range == "3d":
        start_time = (now - timedelta(days=3)).timestamp()
    elif time_range == "7d":
        start_time = (now - timedelta(days=7)).timestamp()
    else:
        start_time = (now - timedelta(hours=1)).timestamp()
    
    return start_time, end_time

def get_appropriate_interval(time_range):
    """時間範囲に応じた適切な集約間隔を取得"""
    if time_range == "30m":
        return "30s"
    elif time_range == "1h":
        return "1m"
    elif time_range == "3h":
        return "5m"
    elif time_range == "12h":
        return "15m"
    elif time_range == "24h":
        return "30m"
    elif time_range == "3d":
        return "2h"
    elif time_range == "7d":
        return "6h"
    else:
        return "5m"


# コールバック：データ更新
@app.callback(
    Output("metrics-data", "data"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals"),
     Input("time-range", "value")]
)
def update_metrics_data(n_clicks, n_intervals, time_range):
    """メトリクスデータを更新"""
    start_time, end_time = get_time_range_timestamps(time_range)
    
    # 利用可能なメトリクス定義を取得
    metrics = get_available_metrics()
    if not metrics:
        return {"metrics": [], "values": {}, "timestamp": datetime.now().isoformat()}
    
    # メトリクスのカテゴリー分類
    system_metrics = []
    api_metrics = []
    custom_metrics = []
    
    for metric in metrics:
        if metric["name"].startswith("system_"):
            system_metrics.append(metric)
        elif metric["name"].startswith("api_"):
            api_metrics.append(metric)
        else:
            custom_metrics.append(metric)
    
    # メトリクス値を取得
    values = {}
    interval = get_appropriate_interval(time_range)
    
    for metric in metrics:
        if metric["type"] == "counter":
            # カウンターは集約せずに生の値を取得
            values[metric["name"]] = get_metric_values(
                metric["name"],
                start_time=start_time,
                end_time=end_time
            )
        else:
            # 他のタイプは集約値を取得
            values[metric["name"]] = get_aggregated_metrics(
                metric["name"],
                aggregation="avg",
                interval=interval,
                start_time=start_time,
                end_time=end_time
            )
    
    return {
        "metrics": {
            "system": system_metrics,
            "api": api_metrics,
            "custom": custom_metrics
        },
        "values": values,
        "timestamp": datetime.now().isoformat(),
        "time_range": time_range,
        "interval": interval
    }


# コールバック：サマリーカード更新
@app.callback(
    Output("summary-cards", "children"),
    [Input("metrics-data", "data")]
)
def update_summary_cards(data):
    """サマリーカードを更新"""
    if not data:
        return html.Div("データの読み込み中...")
    
    # タイムスタンプをフォーマット
    timestamp = datetime.fromisoformat(data["timestamp"])
    formatted_time = timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # 最新のシステムメトリクス値を取得
    cpu_usage = None
    memory_usage = None
    disk_usage = None
    
    values = data.get("values", {})
    
    if "system_cpu_usage" in values and values["system_cpu_usage"]:
        metrics = values["system_cpu_usage"]
        if metrics:
            cpu_usage = metrics[0]["value"]
    
    if "system_memory_usage" in values and values["system_memory_usage"]:
        metrics = values["system_memory_usage"]
        if metrics:
            memory_usage = metrics[0]["value"]
    
    if "system_disk_usage" in values and values["system_disk_usage"]:
        metrics = values["system_disk_usage"]
        if metrics:
            disk_usage = metrics[0]["value"]
    
    # APIリクエスト数
    api_requests = None
    if "api_requests_total" in values and values["api_requests_total"]:
        metrics = values["api_requests_total"]
        if metrics:
            api_requests = sum(m["value"] for m in metrics)
    
    # カードの生成
    cards = [
        # 更新時間
        html.Div([
            html.H3("最終更新"),
            html.P(formatted_time)
        ], className="summary-card update-time"),
        
        # CPU
        html.Div([
            html.H3("CPU使用率"),
            html.Div([
                html.Div([
                    html.H4(f"{cpu_usage:.1f}%" if cpu_usage is not None else "N/A")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card cpu"),
        
        # メモリ
        html.Div([
            html.H3("メモリ使用率"),
            html.Div([
                html.Div([
                    html.H4(f"{memory_usage:.1f}%" if memory_usage is not None else "N/A")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card memory"),
        
        # ディスク
        html.Div([
            html.H3("ディスク使用率"),
            html.Div([
                html.Div([
                    html.H4(f"{disk_usage:.1f}%" if disk_usage is not None else "N/A")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card disk"),
        
        # APIリクエスト
        html.Div([
            html.H3("APIリクエスト累計"),
            html.Div([
                html.Div([
                    html.H4(f"{int(api_requests):,}" if api_requests is not None else "N/A")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card api")
    ]
    
    return cards


# コールバック：システムメトリクスグラフの更新
@app.callback(
    Output("system-metrics-graphs", "children"),
    [Input("metrics-data", "data"),
     Input("metric-categories", "value")]
)
def update_system_metrics_graphs(data, categories):
    """システムメトリクスグラフを更新"""
    if not data or "system" not in categories:
        return html.Div("システムメトリクスが選択されていません")
    
    system_metrics = data.get("metrics", {}).get("system", [])
    values = data.get("values", {})
    
    graphs = []
    
    for metric in system_metrics:
        name = metric["name"]
        if name not in values or not values[name]:
            continue
        
        # データフレームを作成
        df_data = []
        for entry in values[name]:
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            df_data.append({
                "時間": timestamp,
                "値": entry["value"],
                "メトリクス": name
            })
        
        if not df_data:
            continue
        
        df = pd.DataFrame(df_data)
        
        # グラフを作成
        fig = px.line(
            df,
            x="時間",
            y="値",
            title=f"{metric['description']} ({metric['unit']})"
        )
        
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor="#f9f9f9",
            plot_bgcolor="#f9f9f9",
            font_family="Noto Sans JP"
        )
        
        # 単位に応じたY軸の書式設定
        if metric["unit"] == "percentage":
            fig.update_layout(yaxis_ticksuffix="%")
        
        graphs.append(dcc.Graph(figure=fig))
    
    if not graphs:
        return html.Div("表示可能なシステムメトリクスがありません")
    
    return graphs


# コールバック：APIメトリクスグラフの更新
@app.callback(
    Output("api-metrics-graphs", "children"),
    [Input("metrics-data", "data"),
     Input("metric-categories", "value")]
)
def update_api_metrics_graphs(data, categories):
    """APIメトリクスグラフを更新"""
    if not data or "api" not in categories:
        return html.Div("APIメトリクスが選択されていません")
    
    api_metrics = data.get("metrics", {}).get("api", [])
    values = data.get("values", {})
    
    graphs = []
    
    for metric in api_metrics:
        name = metric["name"]
        if name not in values or not values[name]:
            continue
        
        # データフレームを作成
        df_data = []
        for entry in values[name]:
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            df_data.append({
                "時間": timestamp,
                "値": entry["value"],
                "メトリクス": name
            })
        
        if not df_data:
            continue
        
        df = pd.DataFrame(df_data)
        
        # グラフを作成
        if metric["type"] == "counter":
            # カウンターの場合は累積値ではなく差分を表示
            df = df.sort_values("時間")
            df["差分"] = df["値"].diff().fillna(0)
            
            fig = px.bar(
                df,
                x="時間",
                y="差分",
                title=f"{metric['description']} ({metric['unit']})"
            )
        elif metric["type"] == "histogram":
            # ヒストグラムの場合は分布を表示
            fig = px.box(
                df,
                x="時間",
                y="値",
                title=f"{metric['description']} ({metric['unit']})"
            )
        else:
            # その他のタイプは通常の折れ線グラフ
            fig = px.line(
                df,
                x="時間",
                y="値",
                title=f"{metric['description']} ({metric['unit']})"
            )
        
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor="#f9f9f9",
            plot_bgcolor="#f9f9f9",
            font_family="Noto Sans JP"
        )
        
        # 単位に応じたY軸の書式設定
        if metric["unit"] == "ms":
            fig.update_layout(yaxis_title="ミリ秒")
        
        graphs.append(dcc.Graph(figure=fig))
    
    if not graphs:
        return html.Div("表示可能なAPIメトリクスがありません")
    
    return graphs


# コールバック：カスタムメトリクスグラフの更新
@app.callback(
    Output("custom-metrics-graphs", "children"),
    [Input("metrics-data", "data"),
     Input("metric-categories", "value")]
)
def update_custom_metrics_graphs(data, categories):
    """カスタムメトリクスグラフを更新"""
    if not data or "custom" not in categories:
        return html.Div("カスタムメトリクスが選択されていません")
    
    custom_metrics = data.get("metrics", {}).get("custom", [])
    values = data.get("values", {})
    
    graphs = []
    
    for metric in custom_metrics:
        name = metric["name"]
        if name not in values or not values[name]:
            continue
        
        # データフレームを作成
        df_data = []
        for entry in values[name]:
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            df_data.append({
                "時間": timestamp,
                "値": entry["value"],
                "メトリクス": name
            })
        
        if not df_data:
            continue
        
        df = pd.DataFrame(df_data)
        
        # グラフを作成
        fig = px.line(
            df,
            x="時間",
            y="値",
            title=f"{metric['description']} ({metric['unit']})"
        )
        
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor="#f9f9f9",
            plot_bgcolor="#f9f9f9",
            font_family="Noto Sans JP"
        )
        
        graphs.append(dcc.Graph(figure=fig))
    
    if not graphs:
        return html.Div("表示可能なカスタムメトリクスがありません")
    
    return graphs


# コールバック：メトリクスリスト更新
@app.callback(
    Output("metric-list", "children"),
    [Input("metrics-data", "data"),
     Input("metric-search", "value")]
)
def update_metric_list(data, search_query):
    """メトリクスリストを更新"""
    if not data:
        return html.Div("データの読み込み中...")
    
    all_metrics = []
    metrics_data = data.get("metrics", {})
    
    for category, metrics in metrics_data.items():
        all_metrics.extend(metrics)
    
    # 検索クエリでフィルタリング
    if search_query:
        filtered_metrics = [
            m for m in all_metrics 
            if search_query.lower() in m["name"].lower() or search_query.lower() in m["description"].lower()
        ]
    else:
        filtered_metrics = all_metrics
    
    # リストアイテムの作成
    items = []
    for metric in filtered_metrics:
        item = html.Div([
            html.H3(metric["name"]),
            html.P(metric["description"]),
            html.P(f"タイプ: {metric['type']}, 単位: {metric['unit']}")
        ], className="metric-item", id={"type": "metric-item", "name": metric["name"]})
        
        items.append(item)
    
    if not items:
        return html.Div("一致するメトリクスがありません")
    
    return items


# コールバック：メトリクス詳細表示
@app.callback(
    [Output("metric-detail-title", "children"),
     Output("metric-detail", "children"),
     Output("selected-metric-name", "data")],
    [Input({"type": "metric-item", "name": dash.dependencies.ALL}, "n_clicks")],
    [dash.dependencies.State("metrics-data", "data")]
)
def show_metric_detail(n_clicks_list, data):
    """選択されたメトリクスの詳細を表示"""
    if not n_clicks_list or not data:
        return "メトリクス詳細", html.Div("メトリクスを選択してください"), None
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return "メトリクス詳細", html.Div("メトリクスを選択してください"), None
    
    # クリックされたメトリクスを特定
    trigger_id = ctx.triggered[0]["prop_id"]
    if not trigger_id or "{" not in trigger_id:
        return "メトリクス詳細", html.Div("メトリクスを選択してください"), None
    
    triggered_props = json.loads(trigger_id.split(".")[0])
    metric_name = triggered_props["name"]
    
    # メトリクス情報を取得
    all_metrics = []
    for category, metrics in data.get("metrics", {}).items():
        all_metrics.extend(metrics)
    
    metric_info = next((m for m in all_metrics if m["name"] == metric_name), None)
    if not metric_info:
        return f"メトリクス詳細: {metric_name}", html.Div("メトリクス情報が見つかりません"), metric_name
    
    # メトリクス値を取得
    values = data.get("values", {}).get(metric_name, [])
    
    # 詳細情報の表示
    detail = html.Div([
        html.Div([
            html.H3("基本情報"),
            html.Table([
                html.Tr([html.Td("名前"), html.Td(metric_info["name"])]),
                html.Tr([html.Td("説明"), html.Td(metric_info["description"])]),
                html.Tr([html.Td("タイプ"), html.Td(metric_info["type"])]),
                html.Tr([html.Td("単位"), html.Td(metric_info["unit"])]),
                html.Tr([html.Td("集計期間"), html.Td(str(metric_info["aggregation_period"] or "なし"))]),
                html.Tr([html.Td("ラベル"), html.Td(", ".join(metric_info["labels"]) or "なし")])
            ], className="metric-info-table")
        ], className="metric-basic-info"),
        
        html.Div([
            html.H3("最新の値"),
            html.Table([
                html.Tr([
                    html.Th("タイムスタンプ"),
                    html.Th("値"),
                    html.Th("ラベル")
                ])
            ] + [
                html.Tr([
                    html.Td(datetime.fromtimestamp(v["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")),
                    html.Td(f"{v['value']:.4f}" if isinstance(v["value"], float) else str(v["value"])),
                    html.Td(json.dumps(v.get("labels", {})))
                ]) for v in values[:10]  # 最新の10件を表示
            ], className="metric-values-table")
        ], className="metric-latest-values")
    ])
    
    return f"メトリクス詳細: {metric_name}", detail, metric_name


# サーバー起動（直接実行時）
if __name__ == "__main__":
    app.run_server(debug=True, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT + 1) 