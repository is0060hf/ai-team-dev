"""
ログモニタリングダッシュボード。
システムのログデータを可視化します。
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
from utils.log_storage import get_log_storage

# アプリケーションの初期化
app = dash.Dash(
    __name__,
    title="ログモニタリングダッシュボード",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap"
    ]
)

# ログストレージインスタンス
log_storage = get_log_storage()

# レイアウト
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("ログモニタリングダッシュボード", className="header-title"),
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
            html.H2("ログレベル"),
            dcc.Checklist(
                id="log-level-filter",
                options=[
                    {"label": "DEBUG", "value": "DEBUG"},
                    {"label": "INFO", "value": "INFO"},
                    {"label": "WARNING", "value": "WARNING"},
                    {"label": "ERROR", "value": "ERROR"},
                    {"label": "CRITICAL", "value": "CRITICAL"}
                ],
                value=["INFO", "WARNING", "ERROR", "CRITICAL"],
                inline=True
            )
        ], className="level-filter"),
        
        html.Div([
            html.H2("ロガー"),
            dcc.Dropdown(
                id="logger-filter",
                options=[
                    {"label": "すべて", "value": "all"}
                ],  # 動的に更新される
                value="all",
                clearable=False
            )
        ], className="logger-filter"),
        
        html.Div([
            html.H2("検索"),
            dcc.Input(
                id="log-search",
                type="text",
                placeholder="ログメッセージで検索...",
                className="search-input"
            ),
            html.Button("検索", id="search-button", className="search-button")
        ], className="search-filter")
    ], className="filters"),
    
    # メインコンテンツ
    html.Div([
        # 左側：サマリーとチャート
        html.Div([
            # サマリーカード
            html.Div(id="log-summary-cards", className="summary-cards"),
            
            # ログレベル分布
            html.Div([
                html.H2("ログレベル分布"),
                html.Div(id="log-level-chart", className="log-level-chart")
            ], className="section"),
            
            # 時間別ログ量
            html.Div([
                html.H2("時間別ログ量"),
                html.Div(id="log-time-chart", className="log-time-chart")
            ], className="section"),
            
            # ロガー別ログ量
            html.Div([
                html.H2("ロガー別ログ量"),
                html.Div(id="logger-chart", className="logger-chart")
            ], className="section")
        ], className="column main-column"),
        
        # 右側：ログリストと詳細
        html.Div([
            # ログリスト
            html.Div([
                html.H2("ログ一覧"),
                html.Div(id="log-list", className="log-list")
            ], className="section"),
            
            # ログ詳細
            html.Div([
                html.H2("ログ詳細", id="log-detail-title"),
                html.Div(id="log-detail", className="log-detail")
            ], className="section")
        ], className="column side-column")
    ], className="main-content"),
    
    # 隠し要素：データストア
    dcc.Store(id="logs-data"),
    dcc.Store(id="selected-log-id"),
    dcc.Store(id="log-stats")
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

def get_logs(
    start_time=None,
    end_time=None,
    level=None,
    logger_name=None,
    search_text=None,
    limit=100,
    offset=0
):
    """ログデータを取得"""
    try:
        return log_storage.get_logs(
            start_time=start_time,
            end_time=end_time,
            level=level,
            logger_name=None if logger_name == "all" else logger_name,
            search_text=search_text,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        print(f"ログ取得エラー: {str(e)}")
        return []

def get_log_stats(start_time=None, end_time=None):
    """ログの統計情報を取得"""
    try:
        return log_storage.get_log_stats(
            start_time=start_time,
            end_time=end_time
        )
    except Exception as e:
        print(f"ログ統計取得エラー: {str(e)}")
        return {
            "total_count": 0,
            "level_counts": {},
            "logger_counts": {},
            "time_buckets": {}
        }

def get_loggers():
    """ロガー一覧を取得"""
    try:
        conn = sqlite3.connect(log_storage.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT logger_name FROM logs")
        loggers = [row[0] for row in cursor.fetchall()]
        conn.close()
        return loggers
    except Exception as e:
        print(f"ロガー一覧取得エラー: {str(e)}")
        return []


# コールバック：ロガーフィルターの選択肢を更新
@app.callback(
    Output("logger-filter", "options"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals")]
)
def update_logger_options(n_clicks, n_intervals):
    """ロガーフィルターの選択肢を更新"""
    loggers = get_loggers()
    options = [{"label": "すべて", "value": "all"}]
    
    for logger in loggers:
        if logger:
            options.append({"label": logger, "value": logger})
    
    return options


# コールバック：データと統計情報の更新
@app.callback(
    [Output("logs-data", "data"),
     Output("log-stats", "data")],
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals"),
     Input("time-range", "value"),
     Input("log-level-filter", "value"),
     Input("logger-filter", "value"),
     Input("search-button", "n_clicks")],
    [dash.dependencies.State("log-search", "value")]
)
def update_logs_data(n_clicks, n_intervals, time_range, levels, logger, search_clicks, search_query):
    """ログデータと統計情報を更新"""
    start_time, end_time = get_time_range_timestamps(time_range)
    
    # 統計情報を取得
    stats = get_log_stats(start_time, end_time)
    
    # 複数のログレベルを処理
    all_logs = []
    
    if levels:
        for level in levels:
            # 検索クエリがある場合は検索
            if search_clicks and search_query:
                level_logs = get_logs(
                    start_time=start_time,
                    end_time=end_time,
                    level=level,
                    logger_name=logger,
                    search_text=search_query
                )
            else:
                level_logs = get_logs(
                    start_time=start_time,
                    end_time=end_time,
                    level=level,
                    logger_name=logger
                )
            
            all_logs.extend(level_logs)
    
    # タイムスタンプでソート（新しい順）
    all_logs.sort(key=lambda log: log.get("timestamp", 0), reverse=True)
    
    # JSONシリアライズ可能な形式に変換
    serializable_logs = []
    for log in all_logs:
        serializable_log = {
            k: v for k, v in log.items() 
            if k != "context" or isinstance(v, (dict, list, str, int, float, bool, type(None)))
        }
        
        # コンテキストオブジェクトの処理
        if "context" in log:
            try:
                # すでに辞書の場合はそのまま、そうでなければJSON文字列として保存
                if isinstance(log["context"], dict):
                    serializable_log["context"] = log["context"]
                else:
                    serializable_log["context"] = json.dumps(log["context"], default=str)
            except:
                serializable_log["context"] = str(log["context"])
        
        serializable_logs.append(serializable_log)
    
    return {
        "logs": serializable_logs,
        "loggers": get_loggers(),
        "timestamp": datetime.now().isoformat(),
        "time_range": time_range,
        "levels": levels,
        "logger": logger,
        "search_query": search_query if search_clicks else None
    }, stats


# コールバック：サマリーカード更新
@app.callback(
    Output("log-summary-cards", "children"),
    [Input("logs-data", "data"),
     Input("log-stats", "data")]
)
def update_log_summary_cards(data, stats):
    """サマリーカードを更新"""
    if not data or not stats:
        return html.Div("データの読み込み中...")
    
    # タイムスタンプをフォーマット
    timestamp = datetime.fromisoformat(data["timestamp"])
    formatted_time = timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # ログの総数
    total_count = stats.get("total_count", 0)
    
    # エラーログの数
    error_count = stats.get("level_counts", {}).get("ERROR", 0) + stats.get("level_counts", {}).get("CRITICAL", 0)
    
    # ロガーの数
    logger_count = len(stats.get("logger_counts", {}))
    
    # 表示している期間のログ数
    displayed_logs = len(data.get("logs", []))
    
    # カードの生成
    cards = [
        # 更新時間
        html.Div([
            html.H3("最終更新"),
            html.P(formatted_time)
        ], className="summary-card update-time"),
        
        # 総ログ数
        html.Div([
            html.H3("総ログ数"),
            html.Div([
                html.Div([
                    html.H4(f"{total_count:,}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card total-logs"),
        
        # エラーログ数
        html.Div([
            html.H3("エラーログ数"),
            html.Div([
                html.Div([
                    html.H4(f"{error_count:,}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card error-logs"),
        
        # ロガー数
        html.Div([
            html.H3("ロガー数"),
            html.Div([
                html.Div([
                    html.H4(f"{logger_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card loggers"),
        
        # 表示ログ数
        html.Div([
            html.H3("表示ログ数"),
            html.Div([
                html.Div([
                    html.H4(f"{displayed_logs:,}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card displayed-logs")
    ]
    
    return cards


# コールバック：ログレベル分布チャート更新
@app.callback(
    Output("log-level-chart", "children"),
    [Input("log-stats", "data")]
)
def update_log_level_chart(stats):
    """ログレベル分布チャートを更新"""
    if not stats:
        return html.Div("データがありません")
    
    level_counts = stats.get("level_counts", {})
    
    if not level_counts:
        return html.Div("表示可能なログレベルデータがありません")
    
    # データフレームを作成
    levels = []
    counts = []
    
    # レベルの順序を定義
    level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    # 順序に従ってデータを追加
    for level in level_order:
        if level in level_counts:
            levels.append(level)
            counts.append(level_counts[level])
    
    df = pd.DataFrame({
        "レベル": levels,
        "ログ数": counts
    })
    
    # レベルごとの色を定義
    colors = {
        "DEBUG": "#6c757d",    # グレー
        "INFO": "#17a2b8",     # 青
        "WARNING": "#ffc107",  # 黄色
        "ERROR": "#fd7e14",    # オレンジ
        "CRITICAL": "#dc3545"  # 赤
    }
    
    color_map = [colors.get(level, "#6c757d") for level in df["レベル"]]
    
    # 棒グラフを作成
    fig = px.bar(
        df,
        x="レベル",
        y="ログ数",
        title="ログレベル分布",
        category_orders={"レベル": level_order},
        color="レベル",
        color_discrete_map={level: colors.get(level, "#6c757d") for level in df["レベル"]}
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP"
    )
    
    return dcc.Graph(figure=fig)


# コールバック：時間別ログ量チャート更新
@app.callback(
    Output("log-time-chart", "children"),
    [Input("log-stats", "data"),
     Input("time-range", "value")]
)
def update_log_time_chart(stats, time_range):
    """時間別ログ量チャートを更新"""
    if not stats:
        return html.Div("データがありません")
    
    time_buckets = stats.get("time_buckets", {})
    
    if not time_buckets:
        return html.Div("表示可能な時間別ログデータがありません")
    
    # データフレームを作成
    times = []
    counts = []
    
    # 時間順にソート
    sorted_buckets = sorted(time_buckets.items(), key=lambda x: float(x[0]))
    
    for timestamp_str, count in sorted_buckets:
        timestamp = float(timestamp_str)
        dt = datetime.fromtimestamp(timestamp)
        times.append(dt)
        counts.append(count)
    
    df = pd.DataFrame({
        "時間": times,
        "ログ数": counts
    })
    
    # 折れ線グラフを作成
    fig = px.line(
        df,
        x="時間",
        y="ログ数",
        title="時間別ログ量",
        markers=True
    )
    
    # 時間間隔に応じたX軸の書式設定
    if time_range in ["30m", "1h"]:
        tick_format = "%H:%M:%S"
    elif time_range in ["3h", "12h", "24h"]:
        tick_format = "%H:%M"
    else:
        tick_format = "%m/%d %H:%M"
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP",
        xaxis_tickformat=tick_format
    )
    
    return dcc.Graph(figure=fig)


# コールバック：ロガー別ログ量チャート更新
@app.callback(
    Output("logger-chart", "children"),
    [Input("log-stats", "data")]
)
def update_logger_chart(stats):
    """ロガー別ログ量チャートを更新"""
    if not stats:
        return html.Div("データがありません")
    
    logger_counts = stats.get("logger_counts", {})
    
    if not logger_counts:
        return html.Div("表示可能なロガーデータがありません")
    
    # データフレームを作成
    loggers = []
    counts = []
    
    # ログ数でソート（多い順）
    sorted_loggers = sorted(logger_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 上位10個のロガーを取得
    for logger, count in sorted_loggers[:10]:
        loggers.append(logger)
        counts.append(count)
    
    df = pd.DataFrame({
        "ロガー": loggers,
        "ログ数": counts
    })
    
    # 水平棒グラフを作成
    fig = px.bar(
        df,
        y="ロガー",
        x="ログ数",
        title="ロガー別ログ量（上位10）",
        orientation="h",
        color="ログ数",
        color_continuous_scale="Viridis"
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP",
        yaxis_categoryorder="total ascending"  # ログ数の昇順でソート
    )
    
    return dcc.Graph(figure=fig)


# コールバック：ログリスト更新
@app.callback(
    Output("log-list", "children"),
    [Input("logs-data", "data")]
)
def update_log_list(data):
    """ログリストを更新"""
    if not data or not data.get("logs"):
        return html.Div("データがありません")
    
    logs = data["logs"]
    
    # ログリストの作成
    items = []
    for i, log in enumerate(logs):
        # タイムスタンプのフォーマット
        timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        
        # ログレベルに応じたスタイルクラスを設定
        log_level = log.get("level", "INFO")
        level_class = f"log-level-{log_level.lower()}"
        
        # メッセージを取得（長いメッセージは省略）
        message = log.get("message", "")
        if len(message) > 100:
            message = message[:97] + "..."
        
        # リストアイテムを作成
        item = html.Div([
            html.Div([
                html.Span(log_level, className=f"log-level {level_class}"),
                html.Span(timestamp, className="log-timestamp")
            ], className="log-item-header"),
            html.P(message, className="log-message"),
            html.Div([
                html.Span(f"ロガー: {log.get('logger_name', 'unknown')}"),
                html.Span(f"モジュール: {log.get('module', '-')}")
            ], className="log-item-details")
        ], className="log-item", id={"type": "log-item", "index": i})
        
        items.append(item)
    
    if not items:
        return html.Div("表示可能なログがありません")
    
    return items


# コールバック：ログ詳細表示
@app.callback(
    [Output("log-detail-title", "children"),
     Output("log-detail", "children"),
     Output("selected-log-id", "data")],
    [Input({"type": "log-item", "index": dash.dependencies.ALL}, "n_clicks")],
    [dash.dependencies.State("logs-data", "data")]
)
def show_log_detail(n_clicks_list, data):
    """選択されたログの詳細を表示"""
    if not n_clicks_list or not data:
        return "ログ詳細", html.Div("ログを選択してください"), None
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return "ログ詳細", html.Div("ログを選択してください"), None
    
    # クリックされたログを特定
    trigger_id = ctx.triggered[0]["prop_id"]
    if not trigger_id or "{" not in trigger_id:
        return "ログ詳細", html.Div("ログを選択してください"), None
    
    triggered_props = json.loads(trigger_id.split(".")[0])
    log_index = triggered_props["index"]
    
    # ログデータを取得
    logs = data.get("logs", [])
    if log_index >= len(logs):
        return "ログ詳細", html.Div("ログが見つかりません"), log_index
    
    log = logs[log_index]
    
    # タイムスタンプのフォーマット
    timestamp = datetime.fromtimestamp(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # ログレベルに応じたスタイルクラスを設定
    log_level = log.get("level", "INFO")
    level_class = f"log-level-{log_level.lower()}"
    
    # コンテキスト情報を文字列化
    context_str = ""
    if "context" in log and log["context"]:
        if isinstance(log["context"], str):
            try:
                context_dict = json.loads(log["context"])
                context_str = json.dumps(context_dict, indent=2, ensure_ascii=False)
            except:
                context_str = log["context"]
        else:
            context_str = json.dumps(log["context"], indent=2, ensure_ascii=False)
    
    # トレース情報
    trace_id = log.get("trace_id", "")
    span_id = log.get("span_id", "")
    parent_span_id = log.get("parent_span_id", "")
    
    # 詳細情報の表示
    detail = html.Div([
        html.Div([
            html.H3("基本情報"),
            html.Table([
                html.Tr([html.Td("タイムスタンプ"), html.Td(timestamp)]),
                html.Tr([html.Td("レベル"), html.Td(html.Span(log_level, className=f"log-level {level_class}"))]),
                html.Tr([html.Td("ロガー"), html.Td(log.get("logger_name", "-"))]),
                html.Tr([html.Td("モジュール"), html.Td(log.get("module", "-"))]),
                html.Tr([html.Td("関数"), html.Td(log.get("function", "-"))]),
                html.Tr([html.Td("行"), html.Td(log.get("line", "-"))]),
                html.Tr([html.Td("プロセスID"), html.Td(log.get("process_id", "-"))]),
                html.Tr([html.Td("スレッドID"), html.Td(log.get("thread_id", "-"))]),
                html.Tr([html.Td("スレッド名"), html.Td(log.get("thread_name", "-"))]),
                html.Tr([html.Td("ホスト名"), html.Td(log.get("hostname", "-"))])
            ], className="log-info-table")
        ], className="log-basic-info"),
        
        html.Div([
            html.H3("メッセージ"),
            html.Pre(log.get("message", ""), className="log-message-detail")
        ], className="log-message-section"),
        
        html.Div([
            html.H3("トレース情報"),
            html.Table([
                html.Tr([html.Td("トレースID"), html.Td(trace_id or "-")]),
                html.Tr([html.Td("スパンID"), html.Td(span_id or "-")]),
                html.Tr([html.Td("親スパンID"), html.Td(parent_span_id or "-")])
            ], className="log-trace-table")
        ], className="log-trace-section") if trace_id or span_id or parent_span_id else html.Div(),
        
        html.Div([
            html.H3("コンテキスト情報"),
            html.Pre(context_str, className="log-context-detail")
        ], className="log-context-section") if context_str else html.Div()
    ])
    
    return f"ログ詳細: {timestamp}", detail, log_index


# サーバー起動（直接実行時）
if __name__ == "__main__":
    app.run_server(debug=True, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT + 3) 