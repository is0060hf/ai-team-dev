# ローカル開発環境構築手順

このドキュメントでは、Webシステム開発AIエージェントチームのローカル開発環境を構築するための手順を説明します。

## 前提条件

- Python 3.10以上がインストールされていること
- GitがインストールされていてGitの基本操作に慣れていること
- 仮想環境の作成とアクティブ化に慣れていること

## 開発環境のセットアップ

### 1. リポジトリのクローン

まず、プロジェクトのリポジトリをクローンします。

```bash
git clone https://github.com/your-organization/ai-team-dev.git
cd ai-team-dev
```

### 2. 仮想環境のセットアップ

Pythonの仮想環境を作成し、アクティブ化します。

#### Poetryを使用する場合：

```bash
# Poetryのインストール（まだ持っていない場合）
pip install poetry

# 依存関係のインストール
poetry install

# 仮想環境のアクティブ化
poetry shell
```

#### venvを使用する場合：

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境のアクティブ化（Windows）
venv\Scripts\activate

# 仮想環境のアクティブ化（macOS/Linux）
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトのルートディレクトリに`.env`ファイルを作成し、必要な環境変数を設定します。サンプル設定は`.env.example`ファイルを参照してください。

```bash
# .env.example から .env ファイルをコピー
cp .env.example .env

# .env ファイルを編集して実際の値を設定
nano .env  # または好みのテキストエディタを使用
```

主要な環境変数：

```
# LLM API設定
OPENAI_API_KEY=your_openai_api_key
MODEL_NAME=gpt-4o

# データベース設定
DATABASE_URL=your_database_url

# API認証
API_KEY_SECRET=your_secret_key

# ログ設定
LOG_LEVEL=INFO
```

### 4. ストレージディレクトリの作成

プロジェクトが使用するストレージディレクトリを作成します。

```bash
mkdir -p storage/pilot_projects
mkdir -p storage/logs
```

### 5. APIサーバーの起動

FastAPIサーバーを起動します。

```bash
# 開発モードでの起動
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

サーバーが起動したら、ブラウザで http://localhost:8000/docs にアクセスして、Swagger UIでAPIドキュメントを確認できます。

### 6. テストの実行

単体テストを実行するには：

```bash
# すべてのテストを実行
pytest

# 特定のテストファイルを実行
pytest tests/test_utils/test_performance.py

# 詳細なテスト結果を表示
pytest -v
```

## 開発ワークフロー

### コードスタイル

このプロジェクトでは、以下のコードスタイルツールを使用しています：

```bash
# コードスタイルチェック
flake8 .

# 自動フォーマット
black .
isort .
```

### ブランチ戦略

開発する際は、以下のブランチ戦略に従ってください：

1. 機能追加やバグ修正ごとに新しいブランチを作成
   ```bash
   git checkout -b feature/new-feature
   # または
   git checkout -b fix/bug-description
   ```

2. 変更をコミット
   ```bash
   git add .
   git commit -m "機能追加: 〇〇機能を実装"
   ```

3. プルリクエストを作成して変更をレビュー

## トラブルシューティング

### APIキーの問題

LLM API（OpenAIなど）への接続エラーが発生した場合：
- `.env`ファイルに正しいAPIキーが設定されているか確認
- APIキーの使用制限やクレジットが十分かチェック

### パッケージの問題

依存関係のエラーが発生した場合：
```bash
# 依存関係の更新
pip install -r requirements.txt --upgrade
# または
poetry update
```

### ログの確認

問題が発生した場合、ログを確認してエラーの詳細を把握しましょう：
```bash
cat storage/logs/app.log
```

## プロジェクト構造

主要なディレクトリとファイル：

```
ai-team-dev/
│
├── api/                  # APIモジュール
│   ├── main.py           # メインAPIアプリケーション
│   ├── routes/           # APIルート定義
│   └── ...
│
├── utils/                # ユーティリティモジュール
│   ├── performance.py    # パフォーマンスモニタリング
│   ├── error_recovery.py # エラー処理
│   ├── caching.py        # キャッシュ機構
│   └── ...
│
├── tests/                # テストコード
│
├── storage/              # データ保存ディレクトリ
│
├── static/               # 静的ファイル
│
├── templates/            # HTMLテンプレート
│
├── .env.example          # 環境変数サンプル
├── requirements.txt      # 依存パッケージリスト
└── README.md             # プロジェクト概要
```

## 次のステップ

開発環境のセットアップが完了したら、以下を確認することをお勧めします：

1. [プロジェクト仕様書](仕様書.md) を読んで、システムの全体像を理解する
2. APIドキュメント (http://localhost:8000/docs) を確認する
3. テストコードを実行して、システムの動作を把握する

---

質問や問題がある場合は、プロジェクトの管理者に連絡してください。 