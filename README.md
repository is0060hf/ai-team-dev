# Webシステム開発AIエージェントチーム

## プロジェクト概要

CrewAIフレームワークを技術基盤とし、Webシステム開発を行うAIエージェントチームを構築するプロジェクトです。PdM、PM、デザイナー、PL、エンジニア、テスターといった役割を持つAIエージェントが協調して、Webシステムの設計、実装、テストを行います。

## 主な特徴

- ロールベースのエージェントアーキテクチャ（PdM, PM, デザイナー, PL, エンジニア, テスター）
- 動的なエージェントスケーリング（プロジェクト負荷に応じたエージェント数調整）
- Human-in-the-Loop（HITL）設計による人間との効果的な連携
- CrewAIによる高度なタスク管理とプロセス制御

## 技術スタック

- 言語: Python 3.10以上
- AIフレームワーク: CrewAI
- LLM: GPT-4o (OpenAI API)
- データベース: PostgreSQL (Neon)
- インフラ: GCP (GKE, Cloud Storage), Vercel
- フロントエンド: React/Next.js (HITL UI)

## インストール方法

### 前提条件

- Python 3.10以上
- pip または Poetry
- OpenAI API キー

### インストール手順

1. リポジトリのクローン:
```bash
git clone [repository_url]
cd ai-team-dev
```

2. Python仮想環境(venv)のセットアップ:
```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
## macOSおよびLinux:
source venv/bin/activate
## Windows:
venv\Scripts\activate
```

3. 依存パッケージのインストール:
```bash
pip install -r requirements.txt
```

4. 環境変数の設定:
```bash
cp .env.example .env
# .envファイルに必要なAPIキーなどを設定してください
```

## 使用方法

### 基本的な実行

```bash
python main.py
```

### APIサーバー実行

```bash
python api/run_api.py
```

これでAPIサーバー（ポート8000）とダッシュボード（ポート8050）が起動します。

### 仮想環境の停止

作業終了後、仮想環境を停止するには以下のコマンドを実行します：

```bash
deactivate
```

### 設定オプション

環境変数または`.env`ファイルで以下の設定が可能です：

- `OPENAI_API_KEY`: OpenAI APIキー
- `LOG_LEVEL`: ログレベル（DEBUG, INFO, WARNING, ERROR）
- `AGENT_COUNT`: エンジニア/テスターエージェントの初期数

## プロジェクト構造

```
ai-team-dev/
├── agents/              # エージェント定義
│   ├── pdm.py           # PdMエージェント
│   ├── pm.py            # PMエージェント
│   ├── designer.py      # デザイナーエージェント
│   ├── pl.py            # PLエージェント
│   ├── engineer.py      # エンジニアエージェント
│   └── tester.py        # テスターエージェント
├── tools/               # ツール実装
│   ├── file_io.py       # ファイル読み書きツール
│   ├── web_search.py    # Web検索ツール
│   └── code_sandbox.py  # コード実行サンドボックス
├── processes/           # プロセス定義
│   └── core_workflow.py # コアワークフロー
├── utils/               # ユーティリティ
│   ├── logger.py        # ロギング機能
│   └── config.py        # 設定管理
├── main.py              # メインエントリーポイント
├── requirements.txt     # 依存パッケージ
└── .env                 # 環境変数設定ファイル
```

## ライセンス

[ライセンス情報]

## 貢献ガイド

[貢献方法の説明]

# オブザーバビリティダッシュボード

オブザーバビリティダッシュボードは、システムのメトリクス、トレース、ログ、アラートを包括的に監視・管理するための統合ダッシュボードです。

## 機能

このダッシュボードシステムは、以下の4つの主要なコンポーネントから構成されています：

1. **メトリクスダッシュボード** - システムおよびアプリケーションのパフォーマンスメトリクスを可視化
2. **トレースダッシュボード** - 分散トレーシングデータを表示し、リクエストフローを視覚化
3. **ログダッシュボード** - ログデータの検索、フィルタリング、分析
4. **アラートダッシュボード** - システムアラートの管理と通知設定

## セットアップ

### 必要条件

- Python 3.8以上
- 必要なパッケージ（requirements.txtに記載）

### インストール

```bash
# 仮想環境を作成（任意）
python -m venv venv
source venv/bin/activate  # Unix/MacOS
# または
venv\Scripts\activate  # Windows

# 依存パッケージのインストール
pip install -r requirements.txt

# データディレクトリの作成
mkdir -p data
```

## 使用方法

### ダッシュボードの起動

すべてのダッシュボードを同時に起動するには：

```bash
python -m api.observability_dashboards
```

個別のダッシュボードを起動することも可能です：

```bash
# メトリクスダッシュボードのみ
python -m api.metrics_dashboard

# トレースダッシュボードのみ
python -m api.traces_dashboard

# ログダッシュボードのみ
python -m api.logs_dashboard

# アラートダッシュボードのみ
python -m api.alerts_dashboard
```

### アクセス方法

起動後、以下のURLでダッシュボードにアクセスできます：

- メトリクスダッシュボード: http://localhost:8051/
- トレースダッシュボード: http://localhost:8052/
- ログダッシュボード: http://localhost:8053/
- アラートダッシュボード: http://localhost:8054/

## ダッシュボードの特徴

### メトリクスダッシュボード

- CPU、メモリ、ディスク使用率などのシステムメトリクスの視覚化
- APIリクエスト数、レスポンス時間などのアプリケーションメトリクスのモニタリング
- カスタムメトリクスの追加と追跡
- 時系列グラフとリアルタイムの統計情報

### トレースダッシュボード

- 分散トレースの可視化
- リクエストフローのエンドツーエンドの追跡
- サービス間の依存関係の分析
- パフォーマンスボトルネックの特定

### ログダッシュボード

- 構造化ログデータの検索とフィルタリング
- ログレベル別の分析
- 時間別ログ量の視覚化
- ロガー別のログ分布の確認

### アラートダッシュボード

- システムアラートの管理
- 重要度別のアラート表示
- アラートルールの設定
- アラート対応（確認済み、解決済みなど）の記録

## 設定

設定は環境変数または `utils/config.py` ファイルで管理されています。主な設定項目：

### 共通設定

- `DATA_DIR` - データ保存ディレクトリ
- `DASHBOARD_HOST` - ダッシュボードのホスト（デフォルト: 0.0.0.0）
- `DASHBOARD_PORT` - ダッシュボードのベースポート（デフォルト: 8050）

### メトリクス関連

- `ENABLE_METRICS` - メトリクス収集の有効化
- `ENABLE_METRICS_DASHBOARD` - メトリクスダッシュボードの有効化
- `METRICS_DB_PATH` - メトリクスDBのパス

### トレース関連

- `ENABLE_TRACING` - トレース収集の有効化
- `ENABLE_TRACES_DASHBOARD` - トレースダッシュボードの有効化
- `TRACES_DB_PATH` - トレースDBのパス

### ログ関連

- `ENABLE_STRUCTURED_LOGGING` - 構造化ログの有効化
- `ENABLE_LOGS_DASHBOARD` - ログダッシュボードの有効化
- `LOGS_DB_PATH` - ログDBのパス

### アラート関連

- `ENABLE_ALERTS` - アラート機能の有効化
- `ENABLE_ALERTS_DASHBOARD` - アラートダッシュボードの有効化
- `ALERTS_DB_PATH` - アラートDBのパス
- `ALERT_CHECK_INTERVAL` - アラートチェック間隔（秒）

## アラートルールの設定

アラートルールは以下のように設定できます：

```python
from utils.alert_manager import get_alert_manager

alert_manager = get_alert_manager()

# CPU使用率が90%を超えたらアラートを発生させるルール
alert_manager.create_rule(
    name="CPU使用率過剰",
    description="CPU使用率が90%を超えています",
    severity="critical",
    category="system",
    condition="system_cpu_usage > threshold",
    threshold=90.0,
    duration=300,  # 5分間継続で発生
    frequency=1800,  # 30分に1回のみ通知
    enabled=True
)
```

## 外部システムとの連携

このダッシュボードシステムは、以下の外部システムと連携できます：

- **メトリクス**：Prometheus、InfluxDB
- **トレース**：Jaeger、Zipkin
- **ログ**：Elasticsearch、Loki
- **アラート**：Eメール通知

連携方法の詳細は、各コンポーネントのドキュメントを参照してください。

## ライセンス

MIT 