"""
トレースモニタリングダッシュボード。
分散トレーシングデータを可視化します。
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
from utils.trace_storage import get_trace_storage

# アプリケーションの初期化
app = dash.Dash(
    __name__,
    title="トレースモニタリングダッシュボード",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap"
    ]
)

# トレースストレージインスタンス
trace_storage = get_trace_storage()

# レイアウト
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("トレースモニタリングダッシュボード", className="header-title"),
        html.Div([
            html.Button("更新", id="refresh-button", className="refresh-button"),
            dcc.Interval(id="auto-refresh", interval=60000, n_intervals=0)  # 60秒ごとに自動更新
        ], className="header-actions")
    ], className="header"),
    
    # フィルターと検索
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
            html.H2("サービス"),
            dcc.Dropdown(
                id="service-filter",
                options=[
                    {"label": "すべて", "value": "all"}
                ],  # 動的に更新される
                value="all",
                clearable=False
            )
        ], className="service-filter"),
        
        html.Div([
            html.H2("検索"),
            dcc.Input(
                id="trace-search",
                type="text",
                placeholder="トレースID、スパン名、属性で検索...",
                className="search-input"
            ),
            html.Button("検索", id="search-button", className="search-button")
        ], className="search-filter")
    ], className="filters"),
    
    # メインコンテンツ
    html.Div([
        # 左側：サマリーと統計情報
        html.Div([
            # サマリーカード
            html.Div(id="trace-summary-cards", className="summary-cards"),
            
            # トレースタイムライン
            html.Div([
                html.H2("トレースタイムライン"),
                html.Div(id="trace-timeline", className="trace-timeline")
            ], className="section"),
            
            # サービスパフォーマンス
            html.Div([
                html.H2("サービスパフォーマンス"),
                html.Div(id="service-performance", className="service-performance")
            ], className="section")
        ], className="column main-column"),
        
        # 右側：トレースリストと詳細
        html.Div([
            # トレースリスト
            html.Div([
                html.H2("トレース一覧"),
                html.Div(id="trace-list", className="trace-list")
            ], className="section"),
            
            # トレース詳細
            html.Div([
                html.H2("トレース詳細", id="trace-detail-title"),
                html.Div(id="trace-detail", className="trace-detail")
            ], className="section")
        ], className="column side-column")
    ], className="main-content"),
    
    # 隠し要素：データストア
    dcc.Store(id="traces-data"),
    dcc.Store(id="selected-trace-id")
])


# データ取得関数
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

def get_traces(service_name=None, start_time=None, end_time=None, limit=100, offset=0):
    """トレース一覧を取得"""
    try:
        return trace_storage.get_traces(
            service_name=None if service_name == "all" else service_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        print(f"トレース取得エラー: {str(e)}")
        return []

def search_traces(query, service_name=None, start_time=None, end_time=None, limit=100):
    """トレースを検索"""
    try:
        return trace_storage.search_traces(
            query=query,
            service_name=None if service_name == "all" else service_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    except Exception as e:
        print(f"トレース検索エラー: {str(e)}")
        return []

def get_trace_detail(trace_id):
    """トレース詳細を取得"""
    try:
        return trace_storage.get_trace(trace_id)
    except Exception as e:
        print(f"トレース詳細取得エラー: {str(e)}")
        return None

def get_services():
    """サービス一覧を取得"""
    try:
        conn = sqlite3.connect(trace_storage.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT service_name FROM traces")
        services = [row[0] for row in cursor.fetchall()]
        conn.close()
        return services
    except Exception as e:
        print(f"サービス一覧取得エラー: {str(e)}")
        return []


# コールバック：サービスフィルターの選択肢を更新
@app.callback(
    Output("service-filter", "options"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals")]
)
def update_service_options(n_clicks, n_intervals):
    """サービスフィルターの選択肢を更新"""
    services = get_services()
    options = [{"label": "すべて", "value": "all"}]
    
    for service in services:
        if service:
            options.append({"label": service, "value": service})
    
    return options


# コールバック：データ更新
@app.callback(
    Output("traces-data", "data"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals"),
     Input("time-range", "value"),
     Input("service-filter", "value"),
     Input("search-button", "n_clicks")],
    [dash.dependencies.State("trace-search", "value")]
)
def update_traces_data(n_clicks, n_intervals, time_range, service, search_clicks, search_query):
    """トレースデータを更新"""
    start_time, end_time = get_time_range_timestamps(time_range)
    
    # 検索クエリがある場合は検索、なければ通常の取得
    if search_clicks and search_query:
        traces = search_traces(
            query=search_query,
            service_name=service,
            start_time=start_time,
            end_time=end_time
        )
    else:
        traces = get_traces(
            service_name=service,
            start_time=start_time,
            end_time=end_time
        )
    
    # トレースがない場合は空のデータを返す
    if not traces:
        return {
            "traces": [],
            "services": get_services(),
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "traces": traces,
        "services": get_services(),
        "timestamp": datetime.now().isoformat(),
        "time_range": time_range,
        "service": service,
        "search_query": search_query if search_clicks else None
    }


# コールバック：サマリーカード更新
@app.callback(
    Output("trace-summary-cards", "children"),
    [Input("traces-data", "data")]
)
def update_trace_summary_cards(data):
    """サマリーカードを更新"""
    if not data or not data.get("traces"):
        return html.Div("データの読み込み中...")
    
    # タイムスタンプをフォーマット
    timestamp = datetime.fromisoformat(data["timestamp"])
    formatted_time = timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # トレース数
    total_traces = len(data["traces"])
    
    # 平均スパン数
    span_counts = [trace.get("span_count", 0) for trace in data["traces"]]
    avg_spans = sum(span_counts) / len(span_counts) if span_counts else 0
    
    # 平均実行時間
    durations = []
    for trace in data["traces"]:
        if "start_time" in trace and "end_time" in trace and trace["end_time"]:
            duration = (trace["end_time"] - trace["start_time"]) * 1000  # ms単位
            durations.append(duration)
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # サービス数
    services = set(trace.get("service_name", "") for trace in data["traces"] if trace.get("service_name"))
    service_count = len(services)
    
    # カードの生成
    cards = [
        # 更新時間
        html.Div([
            html.H3("最終更新"),
            html.P(formatted_time)
        ], className="summary-card update-time"),
        
        # トレース数
        html.Div([
            html.H3("トレース数"),
            html.Div([
                html.Div([
                    html.H4(f"{total_traces}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card traces"),
        
        # 平均スパン数
        html.Div([
            html.H3("平均スパン数"),
            html.Div([
                html.Div([
                    html.H4(f"{avg_spans:.1f}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card spans"),
        
        # 平均実行時間
        html.Div([
            html.H3("平均実行時間"),
            html.Div([
                html.Div([
                    html.H4(f"{avg_duration:.1f} ms")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card duration"),
        
        # サービス数
        html.Div([
            html.H3("サービス数"),
            html.Div([
                html.Div([
                    html.H4(f"{service_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card services")
    ]
    
    return cards


# コールバック：トレースタイムライン更新
@app.callback(
    Output("trace-timeline", "children"),
    [Input("traces-data", "data")]
)
def update_trace_timeline(data):
    """トレースタイムラインを更新"""
    if not data or not data.get("traces"):
        return html.Div("データがありません")
    
    # トレースデータからタイムラインデータを作成
    timeline_data = []
    for trace in data["traces"]:
        if "start_time" not in trace or "end_time" not in trace or not trace["end_time"]:
            continue
        
        start_time = datetime.fromtimestamp(trace["start_time"])
        end_time = datetime.fromtimestamp(trace["end_time"])
        duration = (trace["end_time"] - trace["start_time"]) * 1000  # ms単位
        
        timeline_data.append({
            "trace_id": trace["trace_id"],
            "service": trace.get("service_name", "unknown"),
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "span_count": trace.get("span_count", 0)
        })
    
    if not timeline_data:
        return html.Div("表示可能なトレースがありません")
    
    # データフレームを作成
    df = pd.DataFrame(timeline_data)
    
    # トレースを開始時間でソート
    df = df.sort_values("start_time")
    
    # ガントチャートを作成
    fig = px.timeline(
        df,
        x_start="start_time",
        x_end="end_time",
        y="trace_id",
        color="service",
        hover_data=["duration", "span_count"],
        labels={
            "start_time": "開始時間",
            "end_time": "終了時間",
            "trace_id": "トレースID",
            "service": "サービス",
            "duration": "実行時間(ms)",
            "span_count": "スパン数"
        },
        title="トレースタイムライン"
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP",
        yaxis_title="",
        xaxis_title="時間"
    )
    
    return dcc.Graph(figure=fig)


# コールバック：サービスパフォーマンス更新
@app.callback(
    Output("service-performance", "children"),
    [Input("traces-data", "data")]
)
def update_service_performance(data):
    """サービスパフォーマンスを更新"""
    if not data or not data.get("traces"):
        return html.Div("データがありません")
    
    # サービスごとのパフォーマンスデータを集計
    service_data = {}
    
    for trace in data["traces"]:
        if "start_time" not in trace or "end_time" not in trace or not trace["end_time"]:
            continue
        
        service_name = trace.get("service_name", "unknown")
        duration = (trace["end_time"] - trace["start_time"]) * 1000  # ms単位
        
        if service_name not in service_data:
            service_data[service_name] = {
                "durations": [],
                "span_counts": [],
                "trace_count": 0
            }
        
        service_data[service_name]["durations"].append(duration)
        service_data[service_name]["span_counts"].append(trace.get("span_count", 0))
        service_data[service_name]["trace_count"] += 1
    
    if not service_data:
        return html.Div("表示可能なサービスパフォーマンスデータがありません")
    
    # 平均値を計算
    performance_data = []
    for service, data in service_data.items():
        avg_duration = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0
        avg_spans = sum(data["span_counts"]) / len(data["span_counts"]) if data["span_counts"] else 0
        trace_count = data["trace_count"]
        
        performance_data.append({
            "service": service,
            "avg_duration": avg_duration,
            "avg_spans": avg_spans,
            "trace_count": trace_count
        })
    
    # データフレームを作成
    df = pd.DataFrame(performance_data)
    
    # グラフを作成
    graphs = []
    
    # 平均実行時間のグラフ
    fig1 = px.bar(
        df,
        x="service",
        y="avg_duration",
        title="サービス別平均実行時間",
        labels={
            "service": "サービス",
            "avg_duration": "平均実行時間(ms)"
        },
        color="service"
    )
    
    fig1.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP"
    )
    
    graphs.append(dcc.Graph(figure=fig1))
    
    # トレース数のグラフ
    fig2 = px.pie(
        df,
        values="trace_count",
        names="service",
        title="サービス別トレース数",
        hole=0.4
    )
    
    fig2.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP"
    )
    
    graphs.append(dcc.Graph(figure=fig2))
    
    return html.Div(graphs)


# コールバック：トレースリスト更新
@app.callback(
    Output("trace-list", "children"),
    [Input("traces-data", "data")]
)
def update_trace_list(data):
    """トレースリストを更新"""
    if not data or not data.get("traces"):
        return html.Div("データがありません")
    
    traces = data["traces"]
    
    # トレースリストの作成
    items = []
    for trace in traces:
        # 開始・終了時間と実行時間を計算
        start_time = datetime.fromtimestamp(trace["start_time"]).strftime("%H:%M:%S") if "start_time" in trace else "N/A"
        
        duration = "N/A"
        if "start_time" in trace and "end_time" in trace and trace["end_time"]:
            duration_ms = (trace["end_time"] - trace["start_time"]) * 1000
            duration = f"{duration_ms:.1f} ms"
        
        # サービス名を取得
        service_name = trace.get("service_name", "unknown")
        
        # リストアイテムを作成
        item = html.Div([
            html.H3(trace["trace_id"][:8] + "..."),  # トレースIDの短縮表示
            html.Div([
                html.Span(f"サービス: {service_name}"),
                html.Span(f"開始時間: {start_time}"),
                html.Span(f"実行時間: {duration}"),
                html.Span(f"スパン数: {trace.get('span_count', 0)}")
            ], className="trace-item-details")
        ], className="trace-item", id={"type": "trace-item", "id": trace["trace_id"]})
        
        items.append(item)
    
    if not items:
        return html.Div("表示可能なトレースがありません")
    
    return items


# コールバック：トレース詳細表示
@app.callback(
    [Output("trace-detail-title", "children"),
     Output("trace-detail", "children"),
     Output("selected-trace-id", "data")],
    [Input({"type": "trace-item", "id": dash.dependencies.ALL}, "n_clicks")]
)
def show_trace_detail(n_clicks_list):
    """選択されたトレースの詳細を表示"""
    if not n_clicks_list:
        return "トレース詳細", html.Div("トレースを選択してください"), None
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return "トレース詳細", html.Div("トレースを選択してください"), None
    
    # クリックされたトレースを特定
    trigger_id = ctx.triggered[0]["prop_id"]
    if not trigger_id or "{" not in trigger_id:
        return "トレース詳細", html.Div("トレースを選択してください"), None
    
    triggered_props = json.loads(trigger_id.split(".")[0])
    trace_id = triggered_props["id"]
    
    # トレース詳細を取得
    trace = get_trace_detail(trace_id)
    if not trace:
        return f"トレース詳細: {trace_id[:8]}...", html.Div("トレース情報が見つかりません"), trace_id
    
    # スパン情報の表示
    spans = trace.get("spans", [])
    
    # スパンタイムラインデータを作成
    timeline_data = []
    for span in spans:
        if "start_time" not in span or "end_time" not in span or not span["end_time"]:
            continue
        
        start_time = datetime.fromtimestamp(span["start_time"])
        end_time = datetime.fromtimestamp(span["end_time"])
        duration = (span["end_time"] - span["start_time"]) * 1000  # ms単位
        
        # スパン名を取得
        span_name = span.get("name", "unknown")
        
        # スパンタイプを取得（root, childなど）
        span_type = span.get("attributes", {}).get("span.type", "unknown")
        
        timeline_data.append({
            "span_id": span["span_id"],
            "name": span_name,
            "type": span_type,
            "service": span.get("service_name", "unknown"),
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "parent": span.get("parent_span_id", "")
        })
    
    # 詳細情報の表示
    detail = html.Div([
        html.Div([
            html.H3("基本情報"),
            html.Table([
                html.Tr([html.Td("トレースID"), html.Td(trace["trace_id"])]),
                html.Tr([html.Td("サービス"), html.Td(trace.get("service_name", "unknown"))]),
                html.Tr([html.Td("開始時間"), html.Td(
                    datetime.fromtimestamp(trace["start_time"]).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    if "start_time" in trace else "N/A"
                )]),
                html.Tr([html.Td("終了時間"), html.Td(
                    datetime.fromtimestamp(trace["end_time"]).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    if "end_time" in trace else "N/A"
                )]),
                html.Tr([html.Td("実行時間"), html.Td(
                    f"{(trace['end_time'] - trace['start_time']) * 1000:.3f} ms"
                    if "start_time" in trace and "end_time" in trace and trace["end_time"] else "N/A"
                )]),
                html.Tr([html.Td("スパン数"), html.Td(len(spans))])
            ], className="trace-info-table")
        ], className="trace-basic-info"),
        
        html.Div([
            html.H3("スパンタイムライン"),
            html.Div([
                dcc.Graph(figure=px.timeline(
                    pd.DataFrame(timeline_data) if timeline_data else pd.DataFrame(),
                    x_start="start_time",
                    x_end="end_time",
                    y="name",
                    color="service",
                    hover_data=["span_id", "duration", "type", "parent"],
                    labels={
                        "start_time": "開始時間",
                        "end_time": "終了時間",
                        "name": "スパン名",
                        "service": "サービス",
                        "duration": "実行時間(ms)",
                        "type": "タイプ",
                        "parent": "親スパン"
                    }
                ).update_layout(
                    height=400,
                    margin=dict(l=20, r=20, t=30, b=20),
                    paper_bgcolor="#f9f9f9",
                    plot_bgcolor="#f9f9f9",
                    font_family="Noto Sans JP",
                    yaxis_title="",
                    xaxis_title="時間"
                ))
            ]) if timeline_data else html.Div("表示可能なスパンがありません")
        ], className="trace-span-timeline"),
        
        html.Div([
            html.H3("スパン詳細"),
            html.Table([
                html.Tr([
                    html.Th("スパンID"),
                    html.Th("名前"),
                    html.Th("サービス"),
                    html.Th("実行時間"),
                    html.Th("タイプ"),
                    html.Th("親スパン")
                ])
            ] + [
                html.Tr([
                    html.Td(span["span_id"][:8] + "..."),
                    html.Td(span.get("name", "unknown")),
                    html.Td(span.get("service_name", "unknown")),
                    html.Td(
                        f"{(span['end_time'] - span['start_time']) * 1000:.3f} ms"
                        if "start_time" in span and "end_time" in span and span["end_time"] else "N/A"
                    ),
                    html.Td(span.get("attributes", {}).get("span.type", "unknown")),
                    html.Td(span.get("parent_span_id", "")[:8] + "..." if span.get("parent_span_id") else "なし")
                ]) for span in spans
            ], className="span-details-table")
        ], className="trace-span-details")
    ])
    
    return f"トレース詳細: {trace_id[:8]}...", detail, trace_id


# サーバー起動（直接実行時）
if __name__ == "__main__":
    app.run_server(debug=True, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT + 2) 