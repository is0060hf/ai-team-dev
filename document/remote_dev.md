# リモート開発環境構築手順

このドキュメントでは、Webシステム開発AIエージェントチームのリモート開発環境を構築するための手順を説明します。

## 1. 前提条件

- Git がインストールされていること
- Docker および Docker Compose がインストールされていること
- VSCode（推奨）または他の開発IDE
- GCPアカウントへのアクセス権（GCP環境利用時）

## 2. リモート開発方法

### 2.1 SSH経由でのリモート開発

#### 2.1.1 リモートサーバーの準備

1. 開発用サーバー（GCE、AWS EC2など）を準備します
   ```bash
   # GCPの場合（例）
   gcloud compute instances create dev-instance \
     --project=your-project-id \
     --zone=asia-northeast1-a \
     --machine-type=e2-standard-4 \
     --image-family=ubuntu-2204-lts \
     --image-project=ubuntu-os-cloud \
     --boot-disk-size=50GB \
     --tags=http-server,https-server
   ```

2. リモートサーバーにSSH接続します
   ```bash
   gcloud compute ssh dev-instance --zone=asia-northeast1-a
   ```

3. 必要なツールをインストールします
   ```bash
   sudo apt update
   sudo apt install -y git docker.io docker-compose python3 python3-pip
   sudo systemctl enable docker
   sudo systemctl start docker
   sudo usermod -aG docker $USER
   # ログアウトして再接続して、dockerグループが有効になることを確認
   exit
   ```

4. 再接続してリポジトリをクローンします
   ```bash
   gcloud compute ssh dev-instance --zone=asia-northeast1-a
   git clone https://github.com/your-organization/ai-team-dev.git
   cd ai-team-dev
   ```

#### 2.1.2 VSCodeでのリモート開発設定

1. VSCodeに「Remote - SSH」拡張機能をインストールします
2. F1キーを押して「Remote-SSH: Connect to Host...」を選択します
3. 新しいSSHホストを追加：`user@hostname`または事前に設定したSSH設定を選択します
4. 接続後、リモートサーバー上のリポジトリを開きます

### 2.2 Docker Dev Containers を使った開発

#### 2.2.1 ローカルマシンでの準備

1. VSCodeに「Remote - Containers」拡張機能をインストールします
2. リポジトリをクローンします
   ```bash
   git clone https://github.com/your-organization/ai-team-dev.git
   cd ai-team-dev
   ```

3. VSCodeでプロジェクトを開き、F1キーを押して「Remote-Containers: Reopen in Container」を選択します

## 3. GCP環境との連携

### 3.1 GCP CLIの設定

1. GCP SDKをインストールしてログインします
   ```bash
   # インストール手順はOSによって異なります
   # https://cloud.google.com/sdk/docs/install

   # ログイン
   gcloud auth login
   
   # プロジェクトの設定
   gcloud config set project your-project-id
   ```

2. 必要なAPIを有効化します
   ```bash
   gcloud services enable container.googleapis.com \
     compute.googleapis.com \
     artifactregistry.googleapis.com \
     cloudbuild.googleapis.com
   ```

### 3.2 GKEとの接続

1. GKEクラスタの認証情報を取得します
   ```bash
   gcloud container clusters get-credentials ai-team-cluster \
     --zone asia-northeast1-a \
     --project your-project-id
   ```

2. Kubernetesリソースを確認します
   ```bash
   kubectl get pods -n ai-team
   ```

## 4. リモート開発のベストプラクティス

### 4.1 ソースコード同期

- **Git Flow**: 常にfeatureブランチを使用して作業し、mainブランチに直接変更を加えないようにします
- **定期的なコミット**: 小さな変更単位で定期的にコミットし、リモート作業の損失リスクを最小限に抑えます

### 4.2 環境変数管理

- 開発環境用の`.env.dev`ファイルを使用します
- 機密情報は`.env.dev`ファイルに直接記載せず、GCP Secret Managerなどの安全な方法で管理します

### 4.3 リモート開発のトラブルシューティング

#### 接続問題

- SSHキーが正しく設定されていることを確認します
- ファイアウォール設定でSSHポート（通常は22）が開放されていることを確認します

#### パフォーマンス問題

- 大きなファイル転送は`scp`または`rsync`を使用します
- リモートマシンのスペックが不足している場合はインスタンスタイプをアップグレードします

#### Docker関連の問題

- Dockerデーモンが実行されていることを確認します: `sudo systemctl status docker`
- ディスク容量を確認します: `df -h`
- 未使用のDockerリソースをクリーンアップします: `docker system prune -a`

## 5. チーム開発のためのコラボレーション

### 5.1 コード共有とレビュー

- プルリクエストを使用してコードレビューを行います
- コードの変更はIssueと関連付けます

### 5.2 ドキュメント共有

- プロジェクトのドキュメントは常に最新の状態を維持します
- 設計変更があった場合は、関連するドキュメントも更新します

## 6. 次のステップ

リモート開発環境の設定が完了したら、以下を確認してください：

1. [プロジェクト仕様書](仕様書.md) を読んで、システムの全体像を理解する
2. [ローカル開発環境](local_dev.md) の設定も確認する
3. リモート環境でテストを実行して、すべてが正常に動作することを確認する

---

質問や問題がある場合は、プロジェクトの管理者に連絡してください。 