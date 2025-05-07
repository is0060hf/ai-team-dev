# コンテナ・クラウド環境マニュアル

このドキュメントでは、AIエージェントチーム開発環境のコンテナ化およびクラウド環境（GCP/Kubernetes）へのデプロイ方法について説明します。

## 目次

- [コンテナ化概要](#コンテナ化概要)
- [ローカル環境での実行方法](#ローカル環境での実行方法)
- [GCPプロジェクトのセットアップ](#gcpプロジェクトのセットアップ)
- [Kubernetes環境へのデプロイ方法](#kubernetes環境へのデプロイ方法)
- [各種サービスの監視・運用方法](#各種サービスの監視運用方法)
- [トラブルシューティング](#トラブルシューティング)

## コンテナ化概要

本プロジェクトは以下のコンポーネントがコンテナ化されています：

1. **メインアプリケーション**：AIエージェントチームのコア機能
   - コンテナイメージ：`ai-team-main-app`
   - 説明：CrewAIフレームワークを使用したAIエージェントチームのコアアプリケーション

2. **APIサーバー**：専門エージェント連携API
   - コンテナイメージ：`ai-team-api-server`
   - 説明：専門エージェント連携APIを提供するFastAPIサーバー

3. **ダッシュボード**：管理モニタリングUI
   - コンテナイメージ：`ai-team-dashboard`
   - 説明：Dashアプリケーションによるエージェント活動の可視化ダッシュボード

4. **オブザーバビリティサービス**：メトリクス、トレース、ログの収集・表示
   - コンテナイメージ：`ai-team-observability`
   - 説明：環境変数により、メトリクス、トレース、ログ、アラートの各サービスを切り替え可能

5. **ベクトルデータベース**：エージェント知識共有用DB
   - コンテナイメージ：`ghcr.io/chroma-core/chroma:latest`
   - 説明：ChromaDBによるエージェント間の知識共有と検索

## ローカル環境での実行方法

### 前提条件

- Docker Desktop がインストールされていること
- Docker Compose がインストールされていること（Docker Desktop に含まれている場合が多い）
- 十分なリソース（CPU、メモリ）が利用可能であること

### 実行手順

1. リポジトリのクローン
   ```bash
   git clone https://github.com/yourusername/ai-team-dev.git
   cd ai-team-dev
   ```

2. 環境変数ファイルの作成
   ```bash
   cp .env.example .env
   # .envファイルを編集し、必要なAPIキーなどを設定
   ```

3. Docker Composeによるサービス起動
   ```bash
   docker-compose up -d
   ```

4. アクセス方法
   - APIサーバー: http://localhost:8000
   - メインダッシュボード: http://localhost:8050
   - スケーリングダッシュボード: http://localhost:8051
   - メトリクスダッシュボード: http://localhost:8052
   - トレースダッシュボード: http://localhost:8053
   - ログダッシュボード: http://localhost:8054
   - アラートダッシュボード: http://localhost:8055
   - ベクトルDB API: http://localhost:8080

5. サービスの停止
   ```bash
   docker-compose down
   ```

## GCPプロジェクトのセットアップ

### 前提条件

- gcloud CLIがインストールされていること
- GCPアカウントが有効であること
- 請求先アカウントが設定されていること

### セットアップ手順

1. `scripts/setup_gcp.sh`スクリプトの編集
   ```bash
   # スクリプトを開いて、PROJECT_IDとBILLING_ACCOUNTを設定
   # BILLING_ACCOUNTは `gcloud billing accounts list` コマンドで確認可能
   vim scripts/setup_gcp.sh
   ```

2. スクリプトの実行
   ```bash
   chmod +x scripts/setup_gcp.sh
   ./scripts/setup_gcp.sh
   ```

3. 実行されるステップ
   - GCPプロジェクトの作成
   - 必要なAPIの有効化
   - サービスアカウントの作成と権限付与
   - ストレージバケットの作成
   - GKEクラスタの作成
   - Nginx Ingressコントローラーのインストール

## Kubernetes環境へのデプロイ方法

### 前提条件

- GCPプロジェクトがセットアップ済みであること
- kubectl CLIがインストールされていること
- GKEクラスタへのアクセス権が設定されていること

### デプロイ手順

1. Kubernetesクラスタへの接続設定
   ```bash
   gcloud container clusters get-credentials ai-team-dev-cluster --region asia-northeast1
   ```

2. デプロイスクリプトの実行
   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh gcr.io/ai-team-dev-project production
   ```

3. デプロイ後のURLアクセス
   - APIサーバー: https://api.ai-team-dev.example.com
   - ダッシュボード: https://dashboard.ai-team-dev.example.com
   - メトリクスダッシュボード: https://metrics.ai-team-dev.example.com
   - トレースダッシュボード: https://traces.ai-team-dev.example.com
   - ログダッシュボード: https://logs.ai-team-dev.example.com
   - アラートダッシュボード: https://alerts.ai-team-dev.example.com

   注: 実際のドメイン設定は環境によって異なります。上記URLは例示です。

## 各種サービスの監視・運用方法

### リソース使用状況の確認

```bash
# ポッド一覧の確認
kubectl get pods -n ai-team-dev

# 特定のポッドの詳細情報
kubectl describe pod <pod-name> -n ai-team-dev

# リソース使用状況
kubectl top pods -n ai-team-dev
kubectl top nodes
```

### ログの確認

```bash
# 特定のポッドのログを表示
kubectl logs <pod-name> -n ai-team-dev

# 特定のポッドの以前のコンテナのログを表示
kubectl logs <pod-name> -n ai-team-dev --previous

# 複数のポッドからログを集約（labelセレクターを使用）
kubectl logs -l app=ai-team-api-server -n ai-team-dev
```

### スケーリング操作

```bash
# 手動でレプリカ数を変更
kubectl scale deployment ai-team-api-server --replicas=3 -n ai-team-dev

# HPA設定の確認
kubectl get hpa -n ai-team-dev
```

### ロールアウトの管理

```bash
# デプロイメントのステータス確認
kubectl rollout status deployment/ai-team-api-server -n ai-team-dev

# ロールバック
kubectl rollout undo deployment/ai-team-api-server -n ai-team-dev

# 特定のリビジョンにロールバック
kubectl rollout undo deployment/ai-team-api-server --to-revision=2 -n ai-team-dev
```

## トラブルシューティング

### 一般的な問題と解決策

#### ポッドがPendingステータスで停滞する
- **原因**: リソース不足、PVCの問題など
- **確認方法**: `kubectl describe pod <pod-name> -n ai-team-dev`
- **解決策**: ノードのリソースを確認、PVCを確認

#### サービスにアクセスできない
- **原因**: Service設定の問題、Ingressの問題など
- **確認方法**:
  ```bash
  kubectl get svc -n ai-team-dev
  kubectl describe svc <service-name> -n ai-team-dev
  kubectl get ingress -n ai-team-dev
  ```
- **解決策**: Service、Endpointsの確認、Ingressの確認

#### イメージのプル失敗
- **原因**: イメージ名の誤り、認証の問題など
- **確認方法**: `kubectl describe pod <pod-name> -n ai-team-dev`
- **解決策**: イメージ名の確認、GCRへの認証設定

### イメージの再ビルドとデプロイ

特定のコンポーネントだけを再ビルド・デプロイしたい場合：

```bash
# 例: APIサーバーのみ再ビルド・デプロイ

# イメージビルド
docker build -t gcr.io/ai-team-dev-project/ai-team-api-server:latest -f docker/api/Dockerfile .

# イメージプッシュ
docker push gcr.io/ai-team-dev-project/ai-team-api-server:latest

# デプロイメントの更新（変更がない場合はrollout restartを使用）
kubectl rollout restart deployment/ai-team-api-server -n ai-team-dev
```

### クラスタリソースの確認と調整

```bash
# ノードの確認
kubectl get nodes

# ノードの詳細情報
kubectl describe node <node-name>

# リソースクォータの確認
kubectl get resourcequota -n ai-team-dev
``` 