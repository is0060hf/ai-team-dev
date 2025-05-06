"""
専門エージェント活用状況モニタリングダッシュボード。
専門エージェントのタスク状況、活動履歴、パフォーマンス指標を可視化します。
"""

import dash
from dash import dcc, html, Input, Output, callback, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
import datetime
import json
from typing import Dict, List, Any, Optional, Union
import os

# API URLの設定
API_BASE_URL = "http://localhost:8000"  # APIサーバーのURL

# アプリケーションの初期化
app = dash.Dash(
    __name__,
    title="専門エージェント活用状況モニタリングダッシュボード",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap"
    ]
)

# レイアウト
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("専門エージェント活用状況モニタリングダッシュボード", className="header-title"),
        html.Div([
            html.Button("更新", id="refresh-button", className="refresh-button"),
            dcc.Interval(id="auto-refresh", interval=30000, n_intervals=0)  # 30秒ごとに自動更新
        ], className="header-actions")
    ], className="header"),
    
    # メインコンテンツ
    html.Div([
        # 左側：サマリーと統計情報
        html.Div([
            # サマリーカード
            html.Div([
                html.Div(id="summary-cards", className="summary-cards"),
            ], className="section"),
            
            # グラフセクション
            html.Div([
                html.H2("活動分析"),
                # タブでグラフを切り替え
                dcc.Tabs([
                    dcc.Tab(label="タスクステータス分布", children=[
                        dcc.Graph(id="task-status-pie")
                    ]),
                    dcc.Tab(label="エージェント比較", children=[
                        dcc.Graph(id="agent-comparison-bar")
                    ]),
                    dcc.Tab(label="時系列活動", children=[
                        dcc.Graph(id="activity-timeline")
                    ])
                ])
            ], className="section")
        ], className="column left-column"),
        
        # 右側：タスクリストとディテール
        html.Div([
            # エージェント選択
            html.Div([
                html.H2("専門エージェントフィルター"),
                dcc.Dropdown(
                    id="agent-filter",
                    options=[
                        {"label": "全エージェント", "value": "all"},
                        {"label": "AIアーキテクト", "value": "ai_architect"},
                        {"label": "プロンプトエンジニア", "value": "prompt_engineer"},
                        {"label": "データエンジニア", "value": "data_engineer"}
                    ],
                    value="all",
                    clearable=False
                )
            ], className="section"),
            
            # タスクリスト
            html.Div([
                html.H2("タスク一覧"),
                html.Div(id="task-list", className="task-list")
            ], className="section"),
            
            # タスク詳細
            html.Div([
                html.H2("タスク詳細", id="task-detail-title"),
                html.Div(id="task-detail", className="task-detail")
            ], className="section")
        ], className="column right-column")
    ], className="main-content"),
    
    # 隠し要素：データストア
    dcc.Store(id="dashboard-data"),
    dcc.Store(id="selected-task-id")
])


# データ取得関数
def get_dashboard_data():
    """APIからダッシュボードデータを取得"""
    try:
        response = requests.get(f"{API_BASE_URL}/specialist/dashboard")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ダッシュボードデータ取得エラー: {str(e)}")
        return None


def get_tasks(specialist=None, status=None, limit=50):
    """APIからタスク一覧を取得"""
    try:
        params = {}
        if specialist and specialist != "all":
            params["specialist"] = specialist
        if status:
            params["status"] = status
        if limit:
            params["limit"] = limit
            
        response = requests.get(f"{API_BASE_URL}/specialist/tasks", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"タスク一覧取得エラー: {str(e)}")
        return []


def get_task_detail(task_id):
    """APIから特定のタスク詳細を取得"""
    try:
        response = requests.get(f"{API_BASE_URL}/specialist/task/{task_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"タスク詳細取得エラー: {str(e)}")
        return None


# コールバック：データ更新
@app.callback(
    Output("dashboard-data", "data"),
    [Input("refresh-button", "n_clicks"),
     Input("auto-refresh", "n_intervals")]
)
def update_dashboard_data(n_clicks, n_intervals):
    """ダッシュボードデータを更新"""
    data = get_dashboard_data()
    if data:
        return data
    return dash.no_update


# コールバック：サマリーカード更新
@app.callback(
    Output("summary-cards", "children"),
    [Input("dashboard-data", "data")]
)
def update_summary_cards(data):
    """サマリーカードを更新"""
    if not data:
        return html.Div("データの読み込みに失敗しました。")
    
    # タイムスタンプをフォーマット
    timestamp = datetime.datetime.fromisoformat(data["timestamp"])
    formatted_time = timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # エージェントごとのアクティブタスク数
    ai_architect_active = len(data["agents"]["ai_architect"]["active_tasks"])
    prompt_engineer_active = len(data["agents"]["prompt_engineer"]["active_tasks"])
    data_engineer_active = len(data["agents"]["data_engineer"]["active_tasks"])
    
    # エージェントごとの完了タスク数
    ai_architect_stats = data["agents"]["ai_architect"]["stats"]
    prompt_engineer_stats = data["agents"]["prompt_engineer"]["stats"]
    data_engineer_stats = data["agents"]["data_engineer"]["stats"]
    
    # カードの生成
    cards = [
        # 更新時間
        html.Div([
            html.H3("最終更新"),
            html.P(formatted_time)
        ], className="summary-card update-time"),
        
        # 全体サマリー
        html.Div([
            html.H3("全体サマリー"),
            html.Div([
                html.Div([
                    html.P("アクティブタスク"),
                    html.H4(data["active_tasks_count"])
                ], className="stat"),
                html.Div([
                    html.P("完了タスク"),
                    html.H4(data["completed_tasks_count"])
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card overall-summary"),
        
        # AIアーキテクト
        html.Div([
            html.H3("AIアーキテクト"),
            html.Div([
                html.Div([
                    html.P("アクティブ"),
                    html.H4(ai_architect_active)
                ], className="stat"),
                html.Div([
                    html.P("完了"),
                    html.H4(ai_architect_stats.get("completed_count", 0))
                ], className="stat"),
                html.Div([
                    html.P("成功率"),
                    html.H4(f"{ai_architect_stats.get('success_rate', 0) * 100:.0f}%")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card ai-architect"),
        
        # プロンプトエンジニア
        html.Div([
            html.H3("プロンプトエンジニア"),
            html.Div([
                html.Div([
                    html.P("アクティブ"),
                    html.H4(prompt_engineer_active)
                ], className="stat"),
                html.Div([
                    html.P("完了"),
                    html.H4(prompt_engineer_stats.get("completed_count", 0))
                ], className="stat"),
                html.Div([
                    html.P("成功率"),
                    html.H4(f"{prompt_engineer_stats.get('success_rate', 0) * 100:.0f}%")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card prompt-engineer"),
        
        # データエンジニア
        html.Div([
            html.H3("データエンジニア"),
            html.Div([
                html.Div([
                    html.P("アクティブ"),
                    html.H4(data_engineer_active)
                ], className="stat"),
                html.Div([
                    html.P("完了"),
                    html.H4(data_engineer_stats.get("completed_count", 0))
                ], className="stat"),
                html.Div([
                    html.P("成功率"),
                    html.H4(f"{data_engineer_stats.get('success_rate', 0) * 100:.0f}%")
                ], className="stat")
            ], className="stats-row")
        ], className="summary-card data-engineer")
    ]
    
    return cards


# コールバック：タスクステータス円グラフ
@app.callback(
    Output("task-status-pie", "figure"),
    [Input("dashboard-data", "data")]
)
def update_task_status_pie(data):
    """タスクステータス分布の円グラフを更新"""
    if not data:
        return go.Figure()
    
    # 全タスクのステータス分布を集計
    status_counts = {}
    
    # AIアーキテクト
    for task in data["agents"]["ai_architect"]["active_tasks"]:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
    # プロンプトエンジニア
    for task in data["agents"]["prompt_engineer"]["active_tasks"]:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
    # データエンジニア
    for task in data["agents"]["data_engineer"]["active_tasks"]:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # ステータスの日本語表示
    status_labels = {
        "保留中": "保留中",
        "受理済": "受理済",
        "処理中": "処理中",
        "情報待ち": "情報待ち",
        "完了": "完了",
        "失敗": "失敗",
        "拒否": "拒否"
    }
    
    # データフレーム作成
    status_df = pd.DataFrame({
        "ステータス": [status_labels.get(s, s) for s in status_counts.keys()],
        "タスク数": list(status_counts.values())
    })
    
    # 円グラフ作成
    fig = px.pie(
        status_df,
        names="ステータス",
        values="タスク数",
        title="現在のタスクステータス分布",
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        font=dict(family="Noto Sans JP"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    
    return fig


# コールバック：エージェント比較棒グラフ
@app.callback(
    Output("agent-comparison-bar", "figure"),
    [Input("dashboard-data", "data")]
)
def update_agent_comparison_bar(data):
    """エージェント比較の棒グラフを更新"""
    if not data:
        return go.Figure()
    
    # エージェントごとのデータ集計
    agents = ["AIアーキテクト", "プロンプトエンジニア", "データエンジニア"]
    agent_keys = ["ai_architect", "prompt_engineer", "data_engineer"]
    
    active_counts = []
    completed_counts = []
    avg_response_times = []
    
    for key in agent_keys:
        agent_data = data["agents"][key]
        active_counts.append(len(agent_data["active_tasks"]))
        completed_counts.append(agent_data["stats"].get("completed_count", 0))
        avg_response_times.append(agent_data["stats"].get("avg_response_time_minutes", 0))
    
    # 複数指標を表示する棒グラフ
    fig = go.Figure()
    
    # アクティブタスク
    fig.add_trace(go.Bar(
        x=agents,
        y=active_counts,
        name="アクティブタスク",
        marker_color="#1f77b4"
    ))
    
    # 完了タスク
    fig.add_trace(go.Bar(
        x=agents,
        y=completed_counts,
        name="完了タスク",
        marker_color="#ff7f0e"
    ))
    
    # 平均応答時間（分単位）を副軸で表示
    fig.add_trace(go.Scatter(
        x=agents,
        y=avg_response_times,
        name="平均応答時間（分）",
        mode="markers+lines",
        marker=dict(size=10, color="#2ca02c"),
        line=dict(width=2, dash="dot"),
        yaxis="y2"
    ))
    
    # レイアウト設定
    fig.update_layout(
        title="専門エージェント比較",
        xaxis_title="エージェント",
        yaxis_title="タスク数",
        font=dict(family="Noto Sans JP"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        barmode="group",
        yaxis2=dict(
            title="平均応答時間（分）",
            overlaying="y",
            side="right"
        )
    )
    
    return fig


# コールバック：活動タイムライン
@app.callback(
    Output("activity-timeline", "figure"),
    [Input("dashboard-data", "data")]
)
def update_activity_timeline(data):
    """活動タイムラインのグラフを更新"""
    if not data:
        return go.Figure()
    
    # 最近のアクティビティを取得
    activities = data.get("recent_activities", [])
    
    if not activities:
        return go.Figure().update_layout(title="アクティビティデータがありません")
    
    # アクティビティをデータフレームに変換
    records = []
    for activity in activities:
        # タイムスタンプをDatetime型に変換
        timestamp = datetime.datetime.fromisoformat(activity.get("updated_at", ""))
        
        # イベントタイプ
        event_type = activity.get("event_type", "unknown")
        
        # ステータス
        status = activity.get("status", "unknown")
        
        # エージェント
        recipient = activity.get("recipient", "unknown")
        
        # タスクID
        task_id = activity.get("task_id", "unknown")
        
        # タスク種別
        task_type = activity.get("task_type", "unknown")
        
        records.append({
            "時間": timestamp,
            "エージェント": recipient,
            "イベント": event_type,
            "ステータス": status,
            "タスクID": task_id,
            "タスク種別": task_type
        })
    
    # データフレーム作成
    df = pd.DataFrame(records)
    
    # 時間でソート
    df = df.sort_values("時間")
    
    # エージェント名を日本語化
    agent_names = {
        "ai_architect": "AIアーキテクト",
        "prompt_engineer": "プロンプトエンジニア",
        "data_engineer": "データエンジニア",
        "pm": "PM",
        "pdm": "PdM",
        "pl": "PL",
        "engineer": "エンジニア",
        "designer": "デザイナー",
        "tester": "テスター"
    }
    
    df["エージェント"] = df["エージェント"].map(lambda x: agent_names.get(x, x))
    
    # イベント種別を日本語化
    event_names = {
        "status_update": "状態更新",
        "task_approval": "タスク承認",
        "task_rejection": "タスク拒否",
        "result_set": "結果設定"
    }
    
    df["イベント"] = df["イベント"].map(lambda x: event_names.get(x, x))
    
    # 散布図で時系列を表現
    fig = px.scatter(
        df,
        x="時間",
        y="エージェント",
        color="ステータス",
        hover_name="タスク種別",
        hover_data=["イベント", "タスクID"],
        size_max=10,
        title="最近のエージェント活動履歴"
    )
    
    # エージェントの活動を線で結ぶ
    for agent in df["エージェント"].unique():
        agent_df = df[df["エージェント"] == agent]
        fig.add_trace(go.Scatter(
            x=agent_df["時間"],
            y=agent_df["エージェント"],
            mode="lines",
            line=dict(width=1, color="rgba(0,0,0,0.3)"),
            showlegend=False
        ))
    
    fig.update_layout(
        xaxis_title="時間",
        yaxis_title="エージェント",
        font=dict(family="Noto Sans JP"),
        yaxis=dict(categoryorder="array", categoryarray=list(agent_names.values()))
    )
    
    return fig


# コールバック：タスクリスト更新
@app.callback(
    Output("task-list", "children"),
    [Input("agent-filter", "value"),
     Input("dashboard-data", "data")]
)
def update_task_list(selected_agent, dashboard_data):
    """タスクリストを更新"""
    # APIからタスク一覧を取得
    specialist = None if selected_agent == "all" else selected_agent
    tasks = get_tasks(specialist=specialist)
    
    if not tasks:
        return html.Div("タスクが見つかりません。", className="no-data")
    
    # タスク種別のマッピング
    task_type_icons = {
        "アーキテクチャ設計": "🏗️",
        "技術スタック選定": "🔧",
        "AIモデル評価": "📊",
        "プロンプト設計": "✍️",
        "プロンプト最適化": "⚡",
        "プロンプト評価": "📈",
        "データ抽出": "🔍",
        "データクリーニング": "🧹",
        "データ変換": "🔄",
        "データパイプライン設計": "🚿",
        "相談・アドバイス": "💬",
        "レビュー": "🔎",
        "調査・リサーチ": "🔬"
    }
    
    # ステータスのスタイルマッピング
    status_styles = {
        "保留中": {"background": "#fff3cd", "color": "#856404"},
        "受理済": {"background": "#cce5ff", "color": "#004085"},
        "処理中": {"background": "#d4edda", "color": "#155724"},
        "情報待ち": {"background": "#d1ecf1", "color": "#0c5460"},
        "完了": {"background": "#c3e6cb", "color": "#155724"},
        "失敗": {"background": "#f8d7da", "color": "#721c24"},
        "拒否": {"background": "#f5c6cb", "color": "#721c24"}
    }
    
    # エージェントのマッピング
    agent_icons = {
        "ai_architect": "🧠 AIアーキテクト",
        "prompt_engineer": "📝 プロンプトエンジニア",
        "data_engineer": "📊 データエンジニア",
        "pm": "📋 PM",
        "pdm": "👨‍💼 PdM",
        "pl": "👨‍💻 PL",
        "engineer": "🔧 エンジニア",
        "designer": "🎨 デザイナー",
        "tester": "🔍 テスター"
    }
    
    # タスクリストアイテムの生成
    task_items = []
    for task in tasks:
        # タスク種別アイコン
        task_type = task.get("task_type", "")
        task_icon = task_type_icons.get(task_type, "❓")
        
        # ステータスバッジのスタイル
        status = task.get("status", "")
        status_style = status_styles.get(status, {"background": "#e2e3e5", "color": "#383d41"})
        
        # エージェント
        recipient = agent_icons.get(task.get("recipient", ""), task.get("recipient", ""))
        sender = agent_icons.get(task.get("sender", ""), task.get("sender", ""))
        
        # タイムスタンプ
        created_at = datetime.datetime.fromisoformat(task.get("created_at", ""))
        created_str = created_at.strftime("%m/%d %H:%M")
        
        # 進捗表示
        progress = task.get("progress", 0) or 0
        progress_str = f"{progress * 100:.0f}%" if progress else ""
        
        # タスクアイテム
        task_item = html.Div([
            # ヘッダー行
            html.Div([
                # 左側：タイプとID
                html.Div([
                    html.Span(task_icon, className="task-icon"),
                    html.Span(task.get("task_id", "")[:8], className="task-id"),
                ], className="task-header-left"),
                
                # 右側：ステータスと日時
                html.Div([
                    html.Span(status, className="task-status", style=status_style),
                    html.Span(created_str, className="task-time")
                ], className="task-header-right")
            ], className="task-header"),
            
            # 説明
            html.Div(task.get("description", "")[:100] + ("..." if len(task.get("description", "")) > 100 else ""), 
                    className="task-description"),
            
            # フッター行
            html.Div([
                # 左側：担当者
                html.Div([
                    html.Span("From: ", className="task-from-label"),
                    html.Span(sender, className="task-from"),
                    html.Span(" → ", className="task-arrow"),
                    html.Span(recipient, className="task-to")
                ], className="task-footer-left"),
                
                # 右側：進捗
                html.Div([
                    html.Div([
                        html.Div(
                            style={"width": f"{progress * 100}%"},
                            className="progress-bar"
                        )
                    ], className="progress-track"),
                    html.Span(progress_str, className="progress-text")
                ], className="task-footer-right")
            ], className="task-footer")
        ], 
        id=f"task-item-{task.get('task_id', '')}",
        className="task-item",
        n_clicks=0)
        
        task_items.append(task_item)
    
    return task_items


# コールバック：タスクアイテムクリック処理
@app.callback(
    [Output("selected-task-id", "data"),
     Output("task-detail-title", "children")],
    [Input("task-list", "children")]
)
def handle_task_click(task_items):
    """タスクアイテムのクリックを処理"""
    if not dash.callback_context.triggered:
        return dash.no_update, dash.no_update
    
    # クリックされた要素のID
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    
    if trigger_id.startswith("task-item-"):
        task_id = trigger_id.replace("task-item-", "")
        return task_id, f"タスク詳細: {task_id[:8]}"
    
    return dash.no_update, dash.no_update


# コールバック：タスク詳細更新
@app.callback(
    Output("task-detail", "children"),
    [Input("selected-task-id", "data")]
)
def update_task_detail(task_id):
    """タスク詳細を更新"""
    if not task_id:
        return html.Div("タスクを選択してください", className="no-selection")
    
    # APIからタスク詳細を取得
    task = get_task_detail(task_id)
    
    if not task:
        return html.Div("タスク情報の取得に失敗しました", className="error-message")
    
    # タスク詳細の描画
    detail_sections = [
        # 基本情報セクション
        html.Div([
            html.H3("基本情報"),
            html.Table([
                html.Tr([html.Td("タスクID"), html.Td(task.get("task_id", ""))]),
                html.Tr([html.Td("種別"), html.Td(task.get("task_type", ""))]),
                html.Tr([html.Td("ステータス"), html.Td(task.get("status", ""))]),
                html.Tr([html.Td("優先度"), html.Td(task.get("priority", ""))]),
                html.Tr([html.Td("依頼元"), html.Td(task.get("sender", ""))]),
                html.Tr([html.Td("担当者"), html.Td(task.get("recipient", ""))]),
                html.Tr([html.Td("作成日時"), html.Td(task.get("created_at", ""))]),
                html.Tr([html.Td("更新日時"), html.Td(task.get("updated_at", ""))]),
                html.Tr([html.Td("PM承認"), html.Td("✅ 承認済み" if task.get("approved_by_pm") else "❌ 未承認")])
            ], className="detail-table")
        ], className="detail-section"),
        
        # 詳細説明セクション
        html.Div([
            html.H3("タスク説明"),
            html.P(task.get("description", "説明なし"))
        ], className="detail-section"),
    ]
    
    # 結果セクション（結果がある場合のみ）
    if task.get("result"):
        result_section = html.Div([
            html.H3("タスク結果"),
            html.Pre(json.dumps(task.get("result"), indent=2, ensure_ascii=False))
        ], className="detail-section")
        detail_sections.append(result_section)
    
    # 添付ファイルセクション（添付ファイルがある場合のみ）
    if task.get("attachments"):
        attachment_list = html.Ul([
            html.Li(file) for file in task.get("attachments", [])
        ])
        attachment_section = html.Div([
            html.H3("添付ファイル"),
            attachment_list
        ], className="detail-section")
        detail_sections.append(attachment_section)
    
    # コンテキストセクション（コンテキストがある場合のみ）
    if task.get("context") and task.get("context") != {}:
        context_section = html.Div([
            html.H3("コンテキスト情報"),
            html.Pre(json.dumps(task.get("context"), indent=2, ensure_ascii=False))
        ], className="detail-section")
        detail_sections.append(context_section)
    
    return detail_sections


# CSSスタイル
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                font-family: 'Noto Sans JP', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f7fa;
                color: #333;
            }
            
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 15px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .header-title {
                margin: 0;
                font-size: 1.8rem;
            }
            
            .refresh-button {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
            }
            
            .refresh-button:hover {
                background-color: #2980b9;
            }
            
            .main-content {
                display: flex;
                padding: 20px;
                gap: 20px;
            }
            
            .column {
                flex: 1;
            }
            
            .left-column {
                flex: 3;
            }
            
            .right-column {
                flex: 2;
            }
            
            .section {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            
            .section h2 {
                margin-top: 0;
                margin-bottom: 15px;
                font-size: 1.2rem;
                color: #2c3e50;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            
            .summary-cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }
            
            .summary-card {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                border-top: 3px solid;
            }
            
            .update-time {
                border-top-color: #7f8c8d;
            }
            
            .overall-summary {
                border-top-color: #3498db;
            }
            
            .ai-architect {
                border-top-color: #e74c3c;
            }
            
            .prompt-engineer {
                border-top-color: #2ecc71;
            }
            
            .data-engineer {
                border-top-color: #f39c12;
            }
            
            .summary-card h3 {
                margin-top: 0;
                margin-bottom: 10px;
                font-size: 1rem;
                color: #2c3e50;
            }
            
            .stats-row {
                display: flex;
                justify-content: space-between;
            }
            
            .stat {
                text-align: center;
            }
            
            .stat p {
                margin: 0;
                font-size: 0.8rem;
                color: #7f8c8d;
            }
            
            .stat h4 {
                margin: 5px 0 0;
                font-size: 1.5rem;
                color: #2c3e50;
            }
            
            .task-list {
                max-height: 500px;
                overflow-y: auto;
            }
            
            .task-item {
                background-color: white;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 10px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                border-left: 3px solid #3498db;
            }
            
            .task-item:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            
            .task-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            
            .task-header-left, .task-header-right {
                display: flex;
                align-items: center;
            }
            
            .task-icon {
                margin-right: 5px;
                font-size: 1.2rem;
            }
            
            .task-id {
                font-family: monospace;
                color: #7f8c8d;
            }
            
            .task-status {
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.7rem;
                margin-right: 8px;
            }
            
            .task-time {
                font-size: 0.8rem;
                color: #7f8c8d;
            }
            
            .task-description {
                margin-bottom: 8px;
                font-size: 0.9rem;
                line-height: 1.4;
            }
            
            .task-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 0.8rem;
            }
            
            .task-footer-left {
                color: #7f8c8d;
            }
            
            .progress-track {
                width: 80px;
                height: 6px;
                background-color: #ecf0f1;
                border-radius: 3px;
                overflow: hidden;
                margin-right: 5px;
            }
            
            .progress-bar {
                height: 100%;
                background-color: #3498db;
                border-radius: 3px;
            }
            
            .progress-text {
                font-size: 0.7rem;
                color: #7f8c8d;
            }
            
            .task-detail {
                max-height: 600px;
                overflow-y: auto;
            }
            
            .detail-section {
                margin-bottom: 20px;
            }
            
            .detail-section h3 {
                margin-top: 0;
                font-size: 1rem;
                color: #2c3e50;
                border-bottom: 1px solid #eee;
                padding-bottom: 5px;
                margin-bottom: 10px;
            }
            
            .detail-table {
                width: 100%;
                border-collapse: collapse;
            }
            
            .detail-table td {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            
            .detail-table td:first-child {
                width: 30%;
                font-weight: bold;
                color: #7f8c8d;
            }
            
            .no-data, .no-selection, .error-message {
                color: #7f8c8d;
                text-align: center;
                padding: 20px;
                font-style: italic;
            }
            
            .error-message {
                color: #e74c3c;
            }
            
            pre {
                background-color: #f8f9fa;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
                font-size: 0.8rem;
            }
            
            @media (max-width: 992px) {
                .main-content {
                    flex-direction: column;
                }
                
                .left-column, .right-column {
                    flex: auto;
                }
                
                .summary-cards {
                    grid-template-columns: 1fr 1fr;
                }
            }
            
            @media (max-width: 576px) {
                .summary-cards {
                    grid-template-columns: 1fr;
                }
                
                .header-title {
                    font-size: 1.2rem;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


# アプリケーション起動
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050) 