# CI/CD環境構築手順

このドキュメントでは、Webシステム開発AIエージェントチームのCI/CD（継続的インテグレーション/継続的デリバリー）環境を構築するための手順を説明します。

## 1. 概要

本プロジェクトでは以下のCI/CD環境を構築します：

- **GitHub Actions**: コードのテスト、ビルド、デプロイを自動化
- **Google Kubernetes Engine (GKE)**: バックエンドアプリケーションの実行環境
- **Vercel**: フロントエンド（HITL UI）のホスティング環境
- **Neon**: PostgreSQL互換データベース

## 2. 前提条件

- GitHubリポジトリのAdmin権限
- Google Cloudアカウントとプロジェクト作成権限
- Vercelアカウント
- Neonアカウント

## 3. GitHub Actionsの設定

### 3.1 シークレットの設定

GitHub リポジトリの Settings > Secrets and variables > Actions で、以下のシークレットを設定します：

1. `GCP_SA_KEY`: GCPサービスアカウントのJSONキー
2. `OPENAI_API_KEY`: OpenAI APIキー
3. `API_KEY_SECRET`: APIサーバーの認証シークレット
4. `VERCEL_TOKEN`: Vercel APIトークン
5. `CODECOV_TOKEN`: コードカバレッジ測定用APIトークン（オプション）

### 3.2 リポジトリ変数の設定

GitHub リポジトリの Settings > Secrets and variables > Actions > Variables で、以下の変数を設定します：

1. `GCP_PROJECT_ID`: Google CloudプロジェクトのプロジェクトID

### 3.3 ワークフローファイルの配置

リポジトリの `.github/workflows/` ディレクトリに以下のワークフローファイルが配置されています：

- `ci.yml`: プッシュ・プルリクエスト時にリント、テスト、ビルドを実行
- `cd.yml`: mainブランチへのマージ時またはタグ作成時にGKEとVercelへデプロイ

## 4. Google Cloud環境のセットアップ

### 4.1 プロジェクト作成

```bash
# 新規プロジェクト作成
gcloud projects create ai-team-project

# プロジェクトの設定
gcloud config set project ai-team-project
```

### 4.2 APIの有効化

```bash
gcloud services enable container.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com
```

### 4.3 サービスアカウントの作成

```bash
# CIサービスアカウント作成
gcloud iam service-accounts create github-actions-ci

# 権限付与
gcloud projects add-iam-policy-binding ai-team-project \
  --member="serviceAccount:github-actions-ci@ai-team-project.iam.gserviceaccount.com" \
  --role="roles/container.admin"

gcloud projects add-iam-policy-binding ai-team-project \
  --member="serviceAccount:github-actions-ci@ai-team-project.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ai-team-project \
  --member="serviceAccount:github-actions-ci@ai-team-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"

# キーのダウンロード（GitHubシークレットに使用）
gcloud iam service-accounts keys create gcp-sa-key.json \
  --iam-account=github-actions-ci@ai-team-project.iam.gserviceaccount.com
```

### 4.4 GKEクラスタの作成

```bash
# クラスタ作成
gcloud container clusters create ai-team-cluster \
  --zone asia-northeast1-a \
  --num-nodes 3 \
  --machine-type e2-standard-4

# クラスタ認証情報の取得
gcloud container clusters get-credentials ai-team-cluster \
  --zone asia-northeast1-a
```

### 4.5 ネットワーク設定

```bash
# VPCネットワーク設定
gcloud compute networks create ai-team-vpc --subnet-mode=auto

# Cloud NATの設定
gcloud compute routers create ai-team-router \
  --network ai-team-vpc \
  --region asia-northeast1

gcloud compute routers nats create ai-team-nat \
  --router ai-team-router \
  --nat-all-subnet-ip-ranges \
  --auto-allocate-nat-external-ips
```

## 5. Vercel環境のセットアップ

### 5.1 Vercelプロジェクト作成

1. Vercelダッシュボードにログイン
2. 「New Project」ボタンをクリック
3. GitHubリポジトリを連携
4. フレームワークプリセットとして「Other」を選択
5. 環境変数を設定：
   - `API_URL`: GKEにデプロイされるAPIのURL
   - `API_KEY`: APIの認証キー

### 5.2 Vercel APIトークンの発行

1. Vercelダッシュボードの「Settings」 > 「Tokens」
2. 「Create」ボタンをクリック
3. トークン名とスコープを設定して作成
4. 生成されたトークンをGitHubシークレット `VERCEL_TOKEN` に設定

## 6. Neonデータベースのセットアップ

### 6.1 Neonプロジェクト作成

1. Neonダッシュボードにログイン
2. 「New Project」ボタンをクリック
3. プロジェクト名を入力し、リージョンを選択
4. データベース名を入力
5. 接続情報をコピー

### 6.2 データベース接続情報の設定

Kubernetesシークレットに接続情報を設定：

```bash
kubectl create secret generic ai-team-db-credentials \
  --from-literal=DB_HOST="<Neonホスト>" \
  --from-literal=DB_PORT="5432" \
  --from-literal=DB_NAME="<DB名>" \
  --from-literal=DB_USER="<ユーザー名>" \
  --from-literal=DB_PASSWORD="<パスワード>" \
  -n ai-team
```

## 7. CI/CDパイプラインのテスト

### 7.1 CI機能のテスト

1. 開発ブランチを作成
   ```bash
   git checkout -b feature/test-ci
   ```

2. テストコードを変更してプッシュ
   ```bash
   # ファイル編集後
   git add .
   git commit -m "テスト: CI機能のテスト"
   git push origin feature/test-ci
   ```

3. GitHub Actionsのワークフロー実行を確認
   - リポジトリの「Actions」タブでCIワークフローが実行されていることを確認

### 7.2 CD機能のテスト

1. プルリクエストを作成してマージ
   - GitHubでプルリクエストを作成
   - レビュー後、mainブランチにマージ

2. デプロイの確認
   - GitHub Actionsの「Actions」タブでCDワークフローの実行を確認
   - GKEクラスタにデプロイされたアプリケーションを確認
   ```bash
   kubectl get pods -n ai-team
   ```
   - Vercelにデプロイされたフロントエンドを確認

## 8. 次のステップ

- モニタリングとアラートの設定
- バックアップ戦略の実装
- ローリングアップデート戦略の最適化

---

質問や問題がある場合は、プロジェクトの管理者に連絡してください。 