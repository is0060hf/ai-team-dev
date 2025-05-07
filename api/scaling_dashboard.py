"""
動的エージェントスケーリングのダッシュボード。
スケーリングイベントと負荷メトリクスを可視化します。
"""

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

from utils.agent_scaling import get_scaling_history, get_scaling_summary, get_scaling_events, manual_scale_pool
from utils.agent_scaling import get_pool_manager, ScalingDirection, ScalingTrigger
from utils.load_detection import get_current_load, predict_future_load

# ダッシュボードアプリケーションの初期化
app = dash.Dash(__name__, title="動的エージェントスケーリングモニタリングダッシュボード")

# レイアウトの定義
app.layout = html.Div([
    # ヘッダー
    html.Div([
        html.H1("動的エージェントスケーリングモニタリングダッシュボード", style={'textAlign': 'center'}),
        html.Div([
            html.Button('更新', id='refresh-button', n_clicks=0, className='button'),
            dcc.Dropdown(
                id='pool-filter',
                placeholder='すべてのプールを表示',
                className='dropdown'
            ),
            dcc.Dropdown(
                id='time-range',
                options=[
                    {'label': '直近1時間', 'value': 1},
                    {'label': '直近6時間', 'value': 6},
                    {'label': '直近24時間', 'value': 24},
                    {'label': '直近7日間', 'value': 168}
                ],
                value=24,
                className='dropdown'
            )
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'})
    ], className='header'),
    
    # 概要統計
    html.Div([
        html.H2("スケーリング統計"),
        html.Div(id='summary-stats', className='stats-container')
    ], className='section'),
    
    # 現在のプール状態
    html.Div([
        html.H2("現在のプール状態"),
        html.Div(id='current-pools-status', className='pools-status')
    ], className='section'),
    
    # 手動スケーリングコントロール
    html.Div([
        html.H2("手動スケーリング"),
        html.Div([
            dcc.Dropdown(id='manual-scale-pool', placeholder='プールを選択', className='dropdown'),
            dcc.Input(id='manual-scale-count', type='number', min=1, placeholder='ワーカー数'),
            dcc.Input(id='manual-scale-reason', type='text', placeholder='スケーリング理由（任意）'),
            html.Button('スケール実行', id='manual-scale-button', n_clicks=0, className='button')
        ], className='manual-scaling-controls'),
        html.Div(id='manual-scale-result')
    ], className='section'),
    
    # スケーリングイベントの時系列グラフ
    html.Div([
        html.H2("スケーリングイベントの時系列"),
        dcc.Graph(id='scaling-events-timeline')
    ], className='section'),
    
    # 負荷メトリクスの時系列グラフ
    html.Div([
        html.H2("負荷メトリクスの時系列"),
        dcc.Graph(id='load-metrics-timeline')
    ], className='section'),
    
    # トリガー分析
    html.Div([
        html.H2("スケーリングトリガー分析"),
        dcc.Graph(id='trigger-analysis')
    ], className='section'),
    
    # 将来負荷予測
    html.Div([
        html.H2("負荷予測（今後1時間）"),
        dcc.Graph(id='load-prediction')
    ], className='section'),
    
    # スケーリングイベント詳細一覧
    html.Div([
        html.H2("スケーリングイベント詳細"),
        dash_table.DataTable(
            id='scaling-events-table',
            columns=[
                {'name': 'イベントID', 'id': 'id'},
                {'name': 'プール名', 'id': 'pool_name'},
                {'name': '方向', 'id': 'direction'},
                {'name': 'トリガー', 'id': 'trigger'},
                {'name': '変更数', 'id': 'change_count'},
                {'name': '成功', 'id': 'success'},
                {'name': '理由', 'id': 'reason'},
                {'name': '日時', 'id': 'timestamp_str'}
            ],
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left'},
            style_data_conditional=[
                {
                    'if': {'filter_query': '{direction} = "up"'},
                    'backgroundColor': 'rgba(0, 255, 0, 0.1)'
                },
                {
                    'if': {'filter_query': '{direction} = "down"'},
                    'backgroundColor': 'rgba(255, 0, 0, 0.1)'
                },
                {
                    'if': {'filter_query': '{success} = false'},
                    'backgroundColor': 'rgba(255, 165, 0, 0.2)'
                }
            ],
            page_size=10
        )
    ], className='section'),
    
    # 自動更新用の非表示インターバル
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # 30秒ごとに更新
        n_intervals=0
    )
], className='container')

# コールバック：プールフィルターのオプション更新
@app.callback(
    [Output('pool-filter', 'options'),
     Output('manual-scale-pool', 'options')],
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks')]
)
def update_pool_options(n_intervals, n_clicks):
    """プールフィルターのオプションを更新"""
    pool_manager = get_pool_manager()
    pools = pool_manager.list_pools()
    options = [{'label': pool, 'value': pool} for pool in pools]
    
    # 「すべて」の選択肢を追加
    all_option = {'label': 'すべてのプール', 'value': 'all'}
    return [[all_option] + options, options]

# コールバック：概要統計の更新
@app.callback(
    Output('summary-stats', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('time-range', 'value'),
     Input('pool-filter', 'value')]
)
def update_summary_stats(n_intervals, n_clicks, time_range, pool_filter):
    """概要統計を更新"""
    pool_name = None if pool_filter == 'all' or pool_filter is None else pool_filter
    summary = get_scaling_summary(pool_name=pool_name, period_hours=time_range)
    
    # 統計をカードとして表示
    cards = []
    
    # 合計イベント数
    cards.append(html.Div([
        html.H3(summary['total_events']),
        html.P("合計イベント数")
    ], className='stat-card'))
    
    # スケールアップ数
    cards.append(html.Div([
        html.H3(summary['scale_up_count']),
        html.P("スケールアップイベント")
    ], className='stat-card scale-up'))
    
    # スケールダウン数
    cards.append(html.Div([
        html.H3(summary['scale_down_count']),
        html.P("スケールダウンイベント")
    ], className='stat-card scale-down'))
    
    # ネットワーカー変更
    net_change = summary['scale_up_count'] - summary['scale_down_count']
    cards.append(html.Div([
        html.H3(f"{'+' if net_change > 0 else ''}{net_change}"),
        html.P("正味ワーカー変化")
    ], className=f'stat-card {"scale-up" if net_change > 0 else "scale-down" if net_change < 0 else ""}'))
    
    # トリガー別統計
    trigger_stats = []
    for trigger, data in summary.get('by_trigger', {}).items():
        if data['total'] > 0:
            trigger_stats.append(html.Div([
                html.H3(data['total']),
                html.P(f"{trigger} トリガー"),
                html.Div([
                    html.Span(f"↑ {data['up']}", className='scale-up-text'),
                    html.Span(" / "),
                    html.Span(f"↓ {data['down']}", className='scale-down-text')
                ])
            ], className='stat-card'))
    
    # すべてのカードを一つのコンテナに入れる
    return html.Div(cards + trigger_stats, className='stats-grid')

# コールバック：現在のプール状態の更新
@app.callback(
    Output('current-pools-status', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks')]
)
def update_current_pools_status(n_intervals, n_clicks):
    """現在のプール状態を更新"""
    pool_manager = get_pool_manager()
    status = pool_manager.get_pools_status()
    
    if not status:
        return html.Div("アクティブなプールがありません", className='no-data')
    
    # プールごとのカードを作成
    cards = []
    for pool_name, pool_status in status.items():
        # 利用率の計算
        utilization = pool_status.get('utilization', 0)
        utilization_style = {
            'width': f'{utilization * 100}%',
            'backgroundColor': 'green' if utilization < 0.7 else 'orange' if utilization < 0.9 else 'red'
        }
        
        # スケーリングポリシー情報
        scaling_policy = pool_status.get('scaling_policy', {})
        if scaling_policy:
            policy_info = [
                html.P(f"トリガー: {scaling_policy.get('trigger', 'N/A')}"),
                html.P(f"インスタンス範囲: {scaling_policy.get('min_instances', 0)} - {scaling_policy.get('max_instances', 0)}"),
                html.P(f"閾値: ↑{scaling_policy.get('scale_up_threshold', 0):.2f} / ↓{scaling_policy.get('scale_down_threshold', 0):.2f}"),
                html.P(f"クールダウン: {scaling_policy.get('cooldown_period', 0)}秒")
            ]
            
            # スケーリング可能かどうか
            can_scale = scaling_policy.get('can_scale_now', False)
            time_since_last = scaling_policy.get('time_since_last_scaling', 0)
            
            if can_scale:
                policy_info.append(html.P("スケーリング可能", className='status-available'))
            else:
                remaining = scaling_policy.get('cooldown_period', 0) - time_since_last
                policy_info.append(html.P(f"クールダウン中 (残り {remaining:.0f}秒)", className='status-cooldown'))
        else:
            policy_info = [html.P("スケーリングポリシー情報なし")]
        
        # プールカードを作成
        cards.append(html.Div([
            html.H3(pool_name),
            html.Div([
                html.Div([
                    html.P(f"ワーカー: {pool_status.get('worker_count', 0)}"),
                    html.P(f"ビジー: {pool_status.get('busy_workers', 0)}"),
                    html.P(f"アイドル: {pool_status.get('idle_workers', 0)}"),
                    html.P(f"キュー長: {pool_status.get('queue_size', 0)}")
                ], className='pool-metrics'),
                html.Div(policy_info, className='pool-policy')
            ], className='pool-details'),
            html.Div([
                html.P(f"利用率: {utilization:.1%}"),
                html.Div([
                    html.Div(className='utilization-bar-fill', style=utilization_style)
                ], className='utilization-bar')
            ], className='pool-utilization')
        ], className='pool-card'))
    
    return html.Div(cards, className='pools-grid')

# コールバック：スケーリングイベントの時系列グラフ更新
@app.callback(
    Output('scaling-events-timeline', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('time-range', 'value'),
     Input('pool-filter', 'value')]
)
def update_scaling_events_timeline(n_intervals, n_clicks, time_range, pool_filter):
    """スケーリングイベントの時系列グラフを更新"""
    pool_name = None if pool_filter == 'all' or pool_filter is None else pool_filter
    
    # 選択された時間範囲に基づいてスケーリングレートを取得
    history = get_scaling_history()
    interval_minutes = max(5, time_range // 24)  # 時間範囲に応じて間隔を調整
    scaling_rate = history.get_scaling_rate(
        pool_name=pool_name,
        period_hours=time_range,
        interval_minutes=interval_minutes
    )
    
    if not scaling_rate:
        # データがない場合は空のグラフを返す
        return {
            'data': [],
            'layout': {
                'title': 'スケーリングイベントの時系列',
                'xaxis': {'title': '時間'},
                'yaxis': {'title': 'イベント数'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': 'データがありません',
                    'showarrow': False,
                    'font': {'size': 20}
                }]
            }
        }
    
    # DataFrameに変換
    df = pd.DataFrame(scaling_rate)
    df['timestamp'] = pd.to_datetime(df['timestamp_str'])
    
    # グラフの作成
    fig = go.Figure()
    
    # スケールアップイベント
    fig.add_trace(go.Bar(
        x=df['timestamp'],
        y=df['up_count'],
        name='スケールアップ',
        marker_color='green'
    ))
    
    # スケールダウンイベント
    fig.add_trace(go.Bar(
        x=df['timestamp'],
        y=df['down_count'],
        name='スケールダウン',
        marker_color='red'
    ))
    
    # レイアウトの設定
    fig.update_layout(
        title='スケーリングイベントの時系列',
        xaxis_title='時間',
        yaxis_title='イベント数',
        barmode='group',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

# コールバック：負荷メトリクスの時系列グラフ更新
@app.callback(
    Output('load-metrics-timeline', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('pool-filter', 'value')]
)
def update_load_metrics_timeline(n_intervals, n_clicks, pool_filter):
    """負荷メトリクスの時系列グラフを更新"""
    try:
        # 現在の負荷情報を取得
        current_load = get_current_load()
        
        # メトリクス履歴を取得
        load_metrics = get_current_load()
        metrics_history = load_metrics.get('metrics_history', {})
        
        if not metrics_history:
            # データがない場合は空のグラフを返す
            return {
                'data': [],
                'layout': {
                    'title': '負荷メトリクスの時系列',
                    'xaxis': {'title': '時間'},
                    'yaxis': {'title': '値'},
                    'annotations': [{
                        'x': 0.5, 'y': 0.5,
                        'xref': 'paper', 'yref': 'paper',
                        'text': 'データがありません',
                        'showarrow': False,
                        'font': {'size': 20}
                    }]
                }
            }
        
        # データの準備
        time_data = []
        cpu_data = []
        memory_data = []
        queue_data = []
        combined_data = []
        
        # データがある場合は時系列グラフを作成
        for entry in metrics_history.get('combined_load', []):
            if 'timestamp' in entry:
                time_data.append(datetime.fromtimestamp(entry['timestamp']))
                combined_data.append(entry['value'])
        
        for entry in metrics_history.get('cpu_usage', []):
            if 'timestamp' in entry:
                cpu_data.append(entry['value'])
        
        for entry in metrics_history.get('memory_usage', []):
            if 'timestamp' in entry:
                memory_data.append(entry['value'])
        
        for entry in metrics_history.get('task_queue_length', []):
            if 'timestamp' in entry:
                queue_data.append(entry['value'])
        
        # グラフの作成
        fig = go.Figure()
        
        # 時間データがある場合のみトレースを追加
        if time_data:
            # 結合負荷
            if combined_data:
                fig.add_trace(go.Scatter(
                    x=time_data[-len(combined_data):],
                    y=combined_data,
                    mode='lines+markers',
                    name='結合負荷',
                    line=dict(color='purple', width=3)
                ))
            
            # CPU使用率
            if cpu_data:
                fig.add_trace(go.Scatter(
                    x=time_data[-len(cpu_data):],
                    y=cpu_data,
                    mode='lines',
                    name='CPU使用率 (%)',
                    line=dict(color='red')
                ))
            
            # メモリ使用率
            if memory_data:
                fig.add_trace(go.Scatter(
                    x=time_data[-len(memory_data):],
                    y=memory_data,
                    mode='lines',
                    name='メモリ使用率 (%)',
                    line=dict(color='blue')
                ))
            
            # タスクキュー長
            if queue_data:
                fig.add_trace(go.Scatter(
                    x=time_data[-len(queue_data):],
                    y=queue_data,
                    mode='lines',
                    name='タスクキュー長',
                    line=dict(color='green')
                ))
        
        # レイアウトの設定
        fig.update_layout(
            title='負荷メトリクスの時系列',
            xaxis_title='時間',
            yaxis_title='値',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    except Exception as e:
        # エラーが発生した場合は空のグラフを返す
        print(f"Error in update_load_metrics_timeline: {str(e)}")
        return {
            'data': [],
            'layout': {
                'title': '負荷メトリクスの時系列',
                'xaxis': {'title': '時間'},
                'yaxis': {'title': '値'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': f'データ取得エラー: {str(e)}',
                    'showarrow': False,
                    'font': {'size': 16}
                }]
            }
        }

# コールバック：トリガー分析グラフ更新
@app.callback(
    Output('trigger-analysis', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('time-range', 'value'),
     Input('pool-filter', 'value')]
)
def update_trigger_analysis(n_intervals, n_clicks, time_range, pool_filter):
    """トリガー分析グラフを更新"""
    pool_name = None if pool_filter == 'all' or pool_filter is None else pool_filter
    
    # トリガー分析データを取得
    history = get_scaling_history()
    analysis = history.analyze_triggers(pool_name=pool_name, period_hours=time_range)
    
    if not analysis or 'success_rates' not in analysis:
        # データがない場合は空のグラフを返す
        return {
            'data': [],
            'layout': {
                'title': 'スケーリングトリガー分析',
                'xaxis': {'title': 'トリガー'},
                'yaxis': {'title': '成功率'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': 'データがありません',
                    'showarrow': False,
                    'font': {'size': 20}
                }]
            }
        }
    
    # データの準備
    triggers = []
    success_rates = []
    total_counts = []
    
    for trigger, data in analysis['success_rates'].items():
        if data['total'] > 0:
            triggers.append(trigger)
            success_rates.append(data['success_rate'] * 100)  # パーセント表示に変換
            total_counts.append(data['total'])
    
    # トリガーごとのメトリクス統計情報
    metrics_stats = analysis.get('metrics_stats', {})
    
    # サブプロットの作成
    fig = go.Figure()
    
    # 成功率バー
    fig.add_trace(go.Bar(
        x=triggers,
        y=success_rates,
        name='成功率 (%)',
        marker_color='green',
        text=[f"{rate:.1f}% ({count}件)" for rate, count in zip(success_rates, total_counts)],
        textposition='outside'
    ))
    
    # トリガーごとのメトリクス値（利用可能な場合）
    for trigger in triggers:
        if trigger in metrics_stats and 'combined_load' in metrics_stats[trigger]:
            stat = metrics_stats[trigger]['combined_load']
            hover_text = f"平均: {stat['avg']:.2f}, 最小: {stat['min']:.2f}, 最大: {stat['max']:.2f}"
            fig.add_trace(go.Scatter(
                x=[trigger],
                y=[50],  # 中央に配置
                mode='markers',
                name=f'{trigger} メトリクス',
                marker=dict(
                    size=stat['count'] * 2,  # サンプル数に応じたサイズ
                    color='rgba(255, 165, 0, 0.6)'
                ),
                hovertext=hover_text,
                showlegend=False
            ))
    
    # レイアウトの設定
    fig.update_layout(
        title='スケーリングトリガー分析',
        xaxis_title='トリガー',
        yaxis_title='成功率 (%)',
        yaxis=dict(range=[0, 110])  # 0-100%のスケール + 余白
    )
    
    return fig

# コールバック：負荷予測グラフ更新
@app.callback(
    Output('load-prediction', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks')]
)
def update_load_prediction(n_intervals, n_clicks):
    """負荷予測グラフを更新"""
    try:
        # 現在の負荷と予測を取得
        current_load = get_current_load()
        predictions = []
        
        # 将来の時間ポイント
        time_points = [5, 15, 30, 60]  # 分
        
        for minutes in time_points:
            pred = predict_future_load(minutes_ahead=minutes)
            predictions.append(pred)
        
        if not current_load or not predictions:
            # データがない場合は空のグラフを返す
            return {
                'data': [],
                'layout': {
                    'title': '負荷予測',
                    'xaxis': {'title': '時間'},
                    'yaxis': {'title': '負荷値'},
                    'annotations': [{
                        'x': 0.5, 'y': 0.5,
                        'xref': 'paper', 'yref': 'paper',
                        'text': '予測データがありません',
                        'showarrow': False,
                        'font': {'size': 20}
                    }]
                }
            }
        
        # グラフデータの準備
        now = datetime.now()
        time_points_dt = [now + timedelta(minutes=m) for m in time_points]
        
        # 各メトリクスの予測値と信頼度
        combined_load_values = [current_load['metrics']['combined_load']]
        combined_load_conf = [1.0]  # 現在値の信頼度は100%
        
        cpu_values = [current_load['metrics']['cpu_usage']]
        cpu_conf = [1.0]
        
        queue_values = [current_load['metrics']['task_queue_length']]
        queue_conf = [1.0]
        
        for pred in predictions:
            pred_data = pred.get('predictions', {})
            
            # 結合負荷
            if 'combined_load' in pred_data:
                combined_load_values.append(pred_data['combined_load']['value'])
                combined_load_conf.append(pred_data['combined_load']['confidence'])
            
            # CPU使用率
            if 'cpu_usage' in pred_data:
                cpu_values.append(pred_data['cpu_usage']['value'])
                cpu_conf.append(pred_data['cpu_usage']['confidence'])
            
            # タスクキュー長
            if 'task_queue_length' in pred_data:
                queue_values.append(pred_data['task_queue_length']['value'])
                queue_conf.append(pred_data['task_queue_length']['confidence'])
        
        # 時間軸データ（現在 + 将来の時間ポイント）
        time_axis = [now] + time_points_dt
        
        # グラフの作成
        fig = go.Figure()
        
        # 結合負荷
        fig.add_trace(go.Scatter(
            x=time_axis,
            y=combined_load_values,
            mode='lines+markers',
            name='結合負荷',
            line=dict(color='purple', width=3),
            error_y=dict(
                type='data',
                array=[0] + [(1 - conf) * val * 0.5 for val, conf in zip(combined_load_values[1:], combined_load_conf[1:])],
                visible=True
            )
        ))
        
        # CPU使用率
        fig.add_trace(go.Scatter(
            x=time_axis,
            y=cpu_values,
            mode='lines+markers',
            name='CPU使用率 (%)',
            line=dict(color='red'),
            error_y=dict(
                type='data',
                array=[0] + [(1 - conf) * val * 0.5 for val, conf in zip(cpu_values[1:], cpu_conf[1:])],
                visible=True
            )
        ))
        
        # タスクキュー長
        fig.add_trace(go.Scatter(
            x=time_axis,
            y=queue_values,
            mode='lines+markers',
            name='タスクキュー長',
            line=dict(color='green'),
            error_y=dict(
                type='data',
                array=[0] + [(1 - conf) * val * 0.5 for val, conf in zip(queue_values[1:], queue_conf[1:])],
                visible=True
            )
        ))
        
        # 現在時刻の垂直線
        fig.add_shape(
            type="line",
            x0=now,
            y0=0,
            x1=now,
            y1=1,
            yref="paper",
            line=dict(
                color="black",
                width=2,
                dash="dot",
            )
        )
        
        # レイアウトの設定
        fig.update_layout(
            title='負荷予測（誤差範囲 = 信頼度に基づく）',
            xaxis_title='時間',
            yaxis_title='値',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            annotations=[
                dict(
                    x=now,
                    y=1.05,
                    xref="x",
                    yref="paper",
                    text="現在",
                    showarrow=False
                )
            ]
        )
        
        return fig
    except Exception as e:
        # エラーが発生した場合は空のグラフを返す
        print(f"Error in update_load_prediction: {str(e)}")
        return {
            'data': [],
            'layout': {
                'title': '負荷予測',
                'xaxis': {'title': '時間'},
                'yaxis': {'title': '負荷値'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': f'予測データ取得エラー: {str(e)}',
                    'showarrow': False,
                    'font': {'size': 16}
                }]
            }
        }

# コールバック：スケーリングイベント詳細テーブル更新
@app.callback(
    Output('scaling-events-table', 'data'),
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('time-range', 'value'),
     Input('pool-filter', 'value')]
)
def update_scaling_events_table(n_intervals, n_clicks, time_range, pool_filter):
    """スケーリングイベント詳細テーブルを更新"""
    pool_name = None if pool_filter == 'all' or pool_filter is None else pool_filter
    
    # 時間範囲の計算
    end_time = time.time()
    start_time = end_time - (time_range * 3600)
    
    # イベントデータを取得
    events = get_scaling_events(
        pool_name=pool_name,
        limit=1000,  # 十分大きな値
        start_time=start_time,
        end_time=end_time
    )
    
    if not events:
        return []
    
    # テーブル表示用にデータを整形
    table_data = []
    for event in events:
        # 変更数の計算
        change_count = event['new_count'] - event['prev_count']
        change_str = f"{'+' if change_count > 0 else ''}{change_count}"
        
        table_data.append({
            'id': event['id'],
            'pool_name': event['pool_name'],
            'direction': event['direction'],
            'trigger': event['trigger'],
            'change_count': change_str,
            'success': event['success'],
            'reason': event['reason'],
            'timestamp_str': event['timestamp_str']
        })
    
    return table_data

# コールバック：手動スケーリング実行
@app.callback(
    Output('manual-scale-result', 'children'),
    [Input('manual-scale-button', 'n_clicks')],
    [State('manual-scale-pool', 'value'),
     State('manual-scale-count', 'value'),
     State('manual-scale-reason', 'value')]
)
def execute_manual_scaling(n_clicks, pool_name, target_count, reason):
    """手動スケーリングを実行"""
    if n_clicks == 0 or not pool_name or not target_count:
        return ""
    
    # 理由が指定されていない場合はデフォルト値を使用
    if not reason:
        reason = "ダッシュボードからの手動操作"
    
    # スケーリング実行
    success = manual_scale_pool(pool_name, target_count, reason)
    
    if success:
        return html.Div(f"プール '{pool_name}' のワーカー数を {target_count} に変更しました", className='success-message')
    else:
        return html.Div(f"プール '{pool_name}' のスケーリングに失敗しました", className='error-message')

# スタイルシート
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            :root {
                --primary-color: #2c3e50;
                --secondary-color: #3498db;
                --success-color: #2ecc71;
                --warning-color: #f39c12;
                --danger-color: #e74c3c;
                --light-color: #ecf0f1;
                --dark-color: #34495e;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f7fa;
                color: var(--dark-color);
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header {
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #ddd;
            }
            
            .section {
                background-color: white;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            
            h1, h2, h3 {
                color: var(--primary-color);
                margin-top: 0;
            }
            
            h1 {
                font-size: 2em;
            }
            
            h2 {
                font-size: 1.5em;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 1px solid #eee;
            }
            
            .button {
                background-color: var(--secondary-color);
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            
            .button:hover {
                background-color: #2980b9;
            }
            
            .dropdown {
                min-width: 200px;
                margin-right: 10px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 20px;
            }
            
            .stat-card {
                background-color: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                text-align: center;
                border-top: 3px solid var(--secondary-color);
            }
            
            .stat-card h3 {
                font-size: 1.8em;
                margin: 0;
                margin-bottom: 5px;
                color: var(--dark-color);
            }
            
            .stat-card p {
                margin: 0;
                color: #7f8c8d;
                font-size: 0.9em;
            }
            
            .scale-up {
                border-top-color: var(--success-color);
            }
            
            .scale-down {
                border-top-color: var(--danger-color);
            }
            
            .scale-up-text {
                color: var(--success-color);
                font-weight: bold;
            }
            
            .scale-down-text {
                color: var(--danger-color);
                font-weight: bold;
            }
            
            .pools-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
            }
            
            .pool-card {
                background-color: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            
            .pool-details {
                display: flex;
                margin-bottom: 15px;
            }
            
            .pool-metrics, .pool-policy {
                flex: 1;
            }
            
            .pool-metrics p, .pool-policy p {
                margin: 5px 0;
            }
            
            .utilization-bar {
                width: 100%;
                height: 10px;
                background-color: #eee;
                border-radius: 5px;
                overflow: hidden;
                margin-top: 5px;
            }
            
            .utilization-bar-fill {
                height: 100%;
                border-radius: 5px;
            }
            
            .status-available {
                color: var(--success-color);
                font-weight: bold;
            }
            
            .status-cooldown {
                color: var(--warning-color);
                font-weight: bold;
            }
            
            .manual-scaling-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                align-items: center;
            }
            
            .manual-scaling-controls .dropdown,
            .manual-scaling-controls input {
                flex: 1;
                height: 36px;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px 10px;
            }
            
            .success-message {
                color: var(--success-color);
                margin-top: 10px;
                font-weight: bold;
            }
            
            .error-message {
                color: var(--danger-color);
                margin-top: 10px;
                font-weight: bold;
            }
            
            .no-data {
                text-align: center;
                padding: 20px;
                color: #7f8c8d;
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
'''

# サーバー起動（直接実行されたとき用）
if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050) 