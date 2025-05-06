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