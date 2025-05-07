"""
アラートモニタリングダッシュボード。
システムのアラートを表示・管理します。
"""

import dash
from dash import dcc, html, Input, Output, callback, State
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
from utils.alert_manager import get_alert_manager

# アプリケーションの初期化
app = dash.Dash(
    __name__,
    title="アラートモニタリングダッシュボード",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap"
    ]
)

# アラートマネージャーインスタンス
alert_manager = get_alert_manager()

# レイアウト
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("アラートモニタリングダッシュボード", className="header-title"),
        html.Div([
            html.Button("更新", id="refresh-button", className="refresh-button"),
            dcc.Interval(id="auto-refresh", interval=30000, n_intervals=0)  # 30秒ごとに自動更新
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
                value="24h",
                inline=True
            )
        ], className="time-filter"),
        
        html.Div([
            html.H2("重要度"),
            dcc.Checklist(
                id="severity-filter",
                options=[
                    {"label": "INFO", "value": "info"},
                    {"label": "WARNING", "value": "warning"},
                    {"label": "ERROR", "value": "error"},
                    {"label": "CRITICAL", "value": "critical"}
                ],
                value=["warning", "error", "critical"],
                inline=True
            )
        ], className="severity-filter"),
        
        html.Div([
            html.H2("ステータス"),
            dcc.Checklist(
                id="status-filter",
                options=[
                    {"label": "発生中", "value": "active"},
                    {"label": "確認済み", "value": "acknowledged"},
                    {"label": "解決済み", "value": "resolved"}
                ],
                value=["active", "acknowledged"],
                inline=True
            )
        ], className="status-filter"),
        
        html.Div([
            html.H2("検索"),
            dcc.Input(
                id="alert-search",
                type="text",
                placeholder="アラート名やルール名で検索...",
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
            html.Div(id="alert-summary-cards", className="summary-cards"),
            
            # アラート発生時系列
            html.Div([
                html.H2("アラート発生時系列"),
                html.Div(id="alert-timeline", className="alert-timeline")
            ], className="section"),
            
            # 重要度別アラート分布
            html.Div([
                html.H2("重要度別アラート分布"),
                html.Div(id="severity-chart", className="severity-chart")
            ], className="section"),
            
            # カテゴリ別アラート分布
            html.Div([
                html.H2("カテゴリ別アラート分布"),
                html.Div(id="category-chart", className="category-chart")
            ], className="section")
        ], className="column main-column"),
        
        # 右側：アラートリストと詳細
        html.Div([
            # アラートリスト
            html.Div([
                html.H2("アラート一覧"),
                html.Div(id="alert-list", className="alert-list")
            ], className="section"),
            
            # アラート詳細
            html.Div([
                html.H2("アラート詳細", id="alert-detail-title"),
                html.Div(id="alert-detail", className="alert-detail")
            ], className="section")
        ], className="column side-column")
    ], className="main-content"),
    
    # 隠し要素：データストア
    dcc.Store(id="alerts-data"),
    dcc.Store(id="selected-alert-id")
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
        start_time = (now - timedelta(hours=24)).timestamp()
    
    return start_time, end_time

def get_alerts(
    start_time=None, 
    end_time=None, 
    severities=None, 
    statuses=None, 
    search_text=None
):
    """アラート一覧を取得"""
    try:
        return alert_manager.get_alerts(
            start_time=start_time,
            end_time=end_time,
            severities=severities,
            statuses=statuses,
            search_text=search_text
        )
    except Exception as e:
        print(f"アラート取得エラー: {str(e)}")
        return []

def get_alert_detail(alert_id):
    """アラート詳細を取得"""
    try:
        return alert_manager.get_alert(alert_id)
    except Exception as e:
        print(f"アラート詳細取得エラー: {str(e)}")
        return None


# コールバック：データ更新
@app.callback(
    Output("alerts-data", "data"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals"),
     Input("time-range", "value"),
     Input("severity-filter", "value"),
     Input("status-filter", "value"),
     Input("search-button", "n_clicks")],
    [State("alert-search", "value")]
)
def update_alerts_data(
    n_clicks, 
    n_intervals, 
    time_range, 
    severities, 
    statuses, 
    search_clicks, 
    search_query
):
    """アラートデータを更新"""
    start_time, end_time = get_time_range_timestamps(time_range)
    
    # 検索クエリがある場合は検索
    search_text = search_query if search_clicks and search_query else None
    
    # アラート一覧を取得
    alerts = get_alerts(
        start_time=start_time,
        end_time=end_time,
        severities=severities,
        statuses=statuses,
        search_text=search_text
    )
    
    # カテゴリとルールの集計
    categories = {}
    rules = {}
    
    for alert in alerts:
        category = alert.get("category", "その他")
        if category in categories:
            categories[category] += 1
        else:
            categories[category] = 1
        
        rule = alert.get("rule_name", "不明")
        if rule in rules:
            rules[rule] += 1
        else:
            rules[rule] = 1
    
    return {
        "alerts": alerts,
        "categories": categories,
        "rules": rules,
        "timestamp": datetime.now().isoformat(),
        "time_range": time_range,
        "severities": severities,
        "statuses": statuses,
        "search_query": search_query if search_clicks else None
    }


# コールバック：サマリーカード更新
@app.callback(
    Output("alert-summary-cards", "children"),
    [Input("alerts-data", "data")]
)
def update_alert_summary_cards(data):
    """サマリーカードを更新"""
    if not data:
        return html.Div("データの読み込み中...")
    
    # タイムスタンプをフォーマット
    timestamp = datetime.fromisoformat(data["timestamp"])
    formatted_time = timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # アラートの総数
    alerts = data.get("alerts", [])
    total_count = len(alerts)
    
    # アクティブな（未解決の）アラート数
    active_count = len([a for a in alerts if a.get("status") == "active"])
    
    # 重要度別カウント
    critical_count = len([a for a in alerts if a.get("severity") == "critical"])
    error_count = len([a for a in alerts if a.get("severity") == "error"])
    warning_count = len([a for a in alerts if a.get("severity") == "warning"])
    
    # カードの生成
    cards = [
        # 更新時間
        html.Div([
            html.H3("最終更新"),
            html.P(formatted_time)
        ], className="summary-card update-time"),
        
        # アラート総数
        html.Div([
            html.H3("総アラート数"),
            html.Div([
                html.Div([
                    html.H4(f"{total_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card total-alerts"),
        
        # アクティブなアラート
        html.Div([
            html.H3("アクティブなアラート"),
            html.Div([
                html.Div([
                    html.H4(f"{active_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card active-alerts"),
        
        # 重大なアラート
        html.Div([
            html.H3("重大なアラート"),
            html.Div([
                html.Div([
                    html.H4(f"{critical_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card critical-alerts"),
        
        # エラーアラート
        html.Div([
            html.H3("エラーアラート"),
            html.Div([
                html.Div([
                    html.H4(f"{error_count + warning_count}")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card error-alerts")
    ]
    
    return cards


# コールバック：アラート時系列チャート更新
@app.callback(
    Output("alert-timeline", "children"),
    [Input("alerts-data", "data")]
)
def update_alert_timeline(data):
    """アラート時系列チャートを更新"""
    if not data or not data.get("alerts"):
        return html.Div("データがありません")
    
    alerts = data.get("alerts", [])
    
    # 時系列データを作成
    timeline_data = []
    for alert in alerts:
        alert_time = datetime.fromtimestamp(alert.get("timestamp", 0))
        severity = alert.get("severity", "info")
        category = alert.get("category", "その他")
        
        timeline_data.append({
            "時間": alert_time,
            "重要度": severity,
            "カテゴリ": category
        })
    
    if not timeline_data:
        return html.Div("表示可能なアラートがありません")
    
    # データフレームを作成
    df = pd.DataFrame(timeline_data)
    
    # 重要度に応じた色を定義
    color_map = {
        "info": "#17a2b8",      # 青
        "warning": "#ffc107",   # 黄色
        "error": "#fd7e14",     # オレンジ
        "critical": "#dc3545"   # 赤
    }
    
    # 時系列チャートを作成
    fig = px.scatter(
        df,
        x="時間",
        y="カテゴリ",
        color="重要度",
        color_discrete_map=color_map,
        size_max=10,
        title="アラート発生時系列"
    )
    
    fig.update_traces(marker=dict(size=12))
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP",
        xaxis_title="時間",
        yaxis_title="カテゴリ"
    )
    
    return dcc.Graph(figure=fig)


# コールバック：重要度別アラート分布更新
@app.callback(
    Output("severity-chart", "children"),
    [Input("alerts-data", "data")]
)
def update_severity_chart(data):
    """重要度別アラート分布チャートを更新"""
    if not data or not data.get("alerts"):
        return html.Div("データがありません")
    
    alerts = data.get("alerts", [])
    
    # 重要度別にカウント
    severity_counts = {
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0
    }
    
    for alert in alerts:
        severity = alert.get("severity", "info")
        if severity in severity_counts:
            severity_counts[severity] += 1
    
    # データフレームを作成
    df = pd.DataFrame({
        "重要度": list(severity_counts.keys()),
        "アラート数": list(severity_counts.values())
    })
    
    # 重要度の順序を定義
    severity_order = ["info", "warning", "error", "critical"]
    df["重要度"] = pd.Categorical(df["重要度"], categories=severity_order, ordered=True)
    df = df.sort_values("重要度")
    
    # 重要度の日本語名を設定
    severity_names = {
        "info": "情報",
        "warning": "警告",
        "error": "エラー",
        "critical": "重大"
    }
    df["重要度"] = df["重要度"].map(severity_names)
    
    # 重要度に応じた色を定義
    color_map = {
        "情報": "#17a2b8",      # 青
        "警告": "#ffc107",      # 黄色
        "エラー": "#fd7e14",    # オレンジ
        "重大": "#dc3545"       # 赤
    }
    
    # 円グラフを作成
    fig = px.pie(
        df,
        values="アラート数",
        names="重要度",
        title="重要度別アラート分布",
        color="重要度",
        color_discrete_map=color_map,
        hole=0.4
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP"
    )
    
    return dcc.Graph(figure=fig)


# コールバック：カテゴリ別アラート分布更新
@app.callback(
    Output("category-chart", "children"),
    [Input("alerts-data", "data")]
)
def update_category_chart(data):
    """カテゴリ別アラート分布チャートを更新"""
    if not data or not data.get("categories"):
        return html.Div("データがありません")
    
    categories = data.get("categories", {})
    
    if not categories:
        return html.Div("表示可能なカテゴリデータがありません")
    
    # データフレームを作成
    df = pd.DataFrame({
        "カテゴリ": list(categories.keys()),
        "アラート数": list(categories.values())
    })
    
    # 降順でソート
    df = df.sort_values("アラート数", ascending=False)
    
    # 棒グラフを作成
    fig = px.bar(
        df,
        y="カテゴリ",
        x="アラート数",
        title="カテゴリ別アラート分布",
        orientation="h",
        color="アラート数",
        color_continuous_scale="Viridis"
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#f9f9f9",
        plot_bgcolor="#f9f9f9",
        font_family="Noto Sans JP",
        yaxis_categoryorder="total ascending"  # アラート数の昇順でソート
    )
    
    return dcc.Graph(figure=fig)


# コールバック：アラートリスト更新
@app.callback(
    Output("alert-list", "children"),
    [Input("alerts-data", "data")]
)
def update_alert_list(data):
    """アラートリストを更新"""
    if not data or not data.get("alerts"):
        return html.Div("データがありません")
    
    alerts = data.get("alerts", [])
    
    # アラートリストの作成
    items = []
    for alert in alerts:
        # タイムスタンプのフォーマット
        timestamp = datetime.fromtimestamp(alert.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M:%S")
        
        # 重要度に応じたスタイルクラスを設定
        severity = alert.get("severity", "info")
        severity_class = f"alert-severity-{severity}"
        
        # ステータスに応じたスタイルクラスを設定
        status = alert.get("status", "active")
        status_class = f"alert-status-{status}"
        
        # ステータスの日本語表記
        status_text = {
            "active": "発生中",
            "acknowledged": "確認済み",
            "resolved": "解決済み"
        }.get(status, status)
        
        # リストアイテムを作成
        item = html.Div([
            html.Div([
                html.Span(severity.upper(), className=f"alert-severity {severity_class}"),
                html.Span(status_text, className=f"alert-status {status_class}"),
                html.Span(timestamp, className="alert-timestamp")
            ], className="alert-item-header"),
            html.H3(alert.get("name", "名称なし"), className="alert-name"),
            html.P(alert.get("description", "説明なし"), className="alert-description"),
            html.Div([
                html.Span(f"カテゴリ: {alert.get('category', 'その他')}"),
                html.Span(f"ルール: {alert.get('rule_name', '不明')}")
            ], className="alert-item-details")
        ], className="alert-item", id={"type": "alert-item", "id": alert.get("id", "")})
        
        items.append(item)
    
    if not items:
        return html.Div("表示可能なアラートがありません")
    
    return items


# コールバック：アラート詳細表示
@app.callback(
    [Output("alert-detail-title", "children"),
     Output("alert-detail", "children"),
     Output("selected-alert-id", "data")],
    [Input({"type": "alert-item", "id": dash.dependencies.ALL}, "n_clicks")],
    [State("alerts-data", "data")]
)
def show_alert_detail(n_clicks_list, data):
    """選択されたアラートの詳細を表示"""
    if not n_clicks_list or not data:
        return "アラート詳細", html.Div("アラートを選択してください"), None
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return "アラート詳細", html.Div("アラートを選択してください"), None
    
    # クリックされたアラートを特定
    trigger_id = ctx.triggered[0]["prop_id"]
    if not trigger_id or "{" not in trigger_id:
        return "アラート詳細", html.Div("アラートを選択してください"), None
    
    triggered_props = json.loads(trigger_id.split(".")[0])
    alert_id = triggered_props["id"]
    
    # アラート詳細を取得
    alerts = data.get("alerts", [])
    alert = next((a for a in alerts if a.get("id") == alert_id), None)
    
    if not alert:
        return f"アラート詳細: {alert_id}", html.Div("アラート情報が見つかりません"), alert_id
    
    # タイムスタンプのフォーマット
    timestamp = datetime.fromtimestamp(alert.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # 重要度に応じたスタイルクラスを設定
    severity = alert.get("severity", "info")
    severity_class = f"alert-severity-{severity}"
    
    # ステータスに応じたスタイルクラスを設定
    status = alert.get("status", "active")
    status_class = f"alert-status-{status}"
    
    # ステータスの日本語表記
    status_text = {
        "active": "発生中",
        "acknowledged": "確認済み",
        "resolved": "解決済み"
    }.get(status, status)
    
    # 詳細情報の表示
    detail = html.Div([
        html.Div([
            html.H3("基本情報"),
            html.Table([
                html.Tr([html.Td("アラートID"), html.Td(alert.get("id", ""))]),
                html.Tr([html.Td("名前"), html.Td(alert.get("name", ""))]),
                html.Tr([html.Td("説明"), html.Td(alert.get("description", ""))]),
                html.Tr([html.Td("重要度"), html.Td(html.Span(severity.upper(), className=f"alert-severity {severity_class}"))]),
                html.Tr([html.Td("ステータス"), html.Td(html.Span(status_text, className=f"alert-status {status_class}"))]),
                html.Tr([html.Td("カテゴリ"), html.Td(alert.get("category", "その他"))]),
                html.Tr([html.Td("タイムスタンプ"), html.Td(timestamp)]),
                html.Tr([html.Td("ルール名"), html.Td(alert.get("rule_name", ""))]),
                html.Tr([html.Td("発生元"), html.Td(alert.get("source", ""))])
            ], className="alert-info-table")
        ], className="alert-basic-info"),
        
        html.Div([
            html.H3("詳細情報"),
            html.Pre(json.dumps(alert.get("details", {}), indent=2, ensure_ascii=False), className="alert-details-json")
        ], className="alert-details-section") if alert.get("details") else html.Div(),
        
        html.Div([
            html.H3("関連メトリクス"),
            html.Pre(json.dumps(alert.get("metrics", {}), indent=2, ensure_ascii=False), className="alert-metrics-json")
        ], className="alert-metrics-section") if alert.get("metrics") else html.Div(),
        
        html.Div([
            html.H3("アクション"),
            html.Div([
                html.Button("確認済みにする", id="acknowledge-button", className="action-button"),
                html.Button("解決済みにする", id="resolve-button", className="action-button")
            ], className="alert-actions")
        ], className="alert-actions-section")
    ])
    
    return f"アラート詳細: {alert.get('name', '')}", detail, alert_id


# コールバック：アラートアクション
@app.callback(
    Output("selected-alert-id", "data", allow_duplicate=True),
    [Input("acknowledge-button", "n_clicks"),
     Input("resolve-button", "n_clicks")],
    [State("selected-alert-id", "data")],
    prevent_initial_call=True
)
def handle_alert_action(acknowledge_clicks, resolve_clicks, alert_id):
    """アラートアクションを処理"""
    if not alert_id:
        return alert_id
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return alert_id
    
    # クリックされたボタンを特定
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if button_id == "acknowledge-button" and acknowledge_clicks:
        try:
            alert_manager.acknowledge_alert(alert_id)
        except Exception as e:
            print(f"アラート確認エラー: {str(e)}")
    
    elif button_id == "resolve-button" and resolve_clicks:
        try:
            alert_manager.resolve_alert(alert_id)
        except Exception as e:
            print(f"アラート解決エラー: {str(e)}")
    
    return alert_id


# サーバー起動（直接実行時）
if __name__ == "__main__":
    app.run_server(debug=True, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT + 4) 