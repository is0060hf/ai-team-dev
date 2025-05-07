#!/bin/bash

# AIエージェントチーム開発用GCPプロジェクト/リソース作成スクリプト

set -e

# 変数定義
PROJECT_ID="ai-team-dev-project"
PROJECT_NAME="AI Team Development"
BILLING_ACCOUNT=""  # --billing-account=XXXXXX-XXXXXX-XXXXXX を設定してください
REGION="asia-northeast1"
ZONE="${REGION}-a"

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘルパー関数
print_step() {
  echo -e "${BLUE}===> $1${NC}"
}

print_info() {
  echo -e "${GREEN}INFO: $1${NC}"
}

print_warn() {
  echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
  echo -e "${RED}ERROR: $1${NC}"
}

check_command() {
  if ! command -v $1 &> /dev/null; then
    print_error "$1 コマンドが見つかりません。インストールしてください。"
    exit 1
  fi
}

# 前提条件の確認
check_requirements() {
  print_step "前提条件を確認しています..."
  
  check_command "gcloud"
  check_command "gsutil"
  check_command "kubectl"
  
  # 請求先アカウントの確認
  if [ -z "$BILLING_ACCOUNT" ]; then
    print_error "請求先アカウントが設定されていません。スクリプトを編集して BILLING_ACCOUNT を設定してください。"
    print_info "利用可能な請求先アカウントは以下のコマンドで確認できます: gcloud billing accounts list"
    exit 1
  fi
  
  print_info "前提条件の確認が完了しました。"
}

# GCPプロジェクトの作成
create_project() {
  print_step "GCPプロジェクトを作成しています..."
  
  # プロジェクトが存在するか確認
  if gcloud projects describe "$PROJECT_ID" &> /dev/null; then
    print_warn "プロジェクト '$PROJECT_ID' は既に存在します。"
  else
    gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME" --labels="purpose=ai-team-development"
    print_info "プロジェクト '$PROJECT_ID' を作成しました。"
  fi
  
  # プロジェクトを有効化
  gcloud config set project "$PROJECT_ID"
  
  # 請求先アカウントをリンク
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
  
  print_info "GCPプロジェクトの作成が完了しました。"
}

# 必要なAPIの有効化
enable_apis() {
  print_step "必要なAPIを有効化しています..."
  
  APIS=(
    "compute.googleapis.com"               # Compute Engine
    "container.googleapis.com"             # Google Kubernetes Engine
    "containerregistry.googleapis.com"     # Container Registry
    "artifactregistry.googleapis.com"      # Artifact Registry
    "cloudbuild.googleapis.com"            # Cloud Build
    "cloudresourcemanager.googleapis.com"  # Cloud Resource Manager
    "iam.googleapis.com"                   # Identity and Access Management
    "secretmanager.googleapis.com"         # Secret Manager
    "cloudkms.googleapis.com"              # Cloud KMS
    "storage.googleapis.com"               # Cloud Storage
    "logging.googleapis.com"               # Cloud Logging
    "monitoring.googleapis.com"            # Cloud Monitoring
    "cloudtrace.googleapis.com"            # Cloud Trace
    "cloudfunctions.googleapis.com"        # Cloud Functions
    "run.googleapis.com"                   # Cloud Run
  )
  
  for api in "${APIS[@]}"; do
    print_info "APIを有効化しています: $api"
    gcloud services enable "$api" --project="$PROJECT_ID"
  done
  
  print_info "必要なAPIの有効化が完了しました。"
}

# サービスアカウントの作成
create_service_accounts() {
  print_step "サービスアカウントを作成しています..."
  
  # GKE用サービスアカウント
  SA_NAME="ai-team-gke-sa"
  SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  
  if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &> /dev/null; then
    print_warn "サービスアカウント '$SA_EMAIL' は既に存在します。"
  else
    gcloud iam service-accounts create "$SA_NAME" \
      --display-name="AI Team GKE Service Account" \
      --project="$PROJECT_ID"
    print_info "サービスアカウント '$SA_EMAIL' を作成しました。"
  fi
  
  # 必要な権限を付与
  print_info "サービスアカウントに権限を付与しています..."
  
  ROLES=(
    "roles/container.admin"            # Kubernetes Engine管理者
    "roles/storage.admin"              # Storageの管理者権限
    "roles/secretmanager.admin"        # Secret Managerの管理者権限
    "roles/cloudkms.admin"             # Cloud KMSの管理者権限
    "roles/monitoring.admin"           # Monitoring管理者
    "roles/logging.admin"              # ログ管理者
    "roles/iam.serviceAccountUser"     # サービスアカウントユーザー
  )
  
  for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="$role"
  done
  
  print_info "サービスアカウントの作成が完了しました。"
}

# ストレージバケットの作成
create_storage_buckets() {
  print_step "ストレージバケットを作成しています..."
  
  BUCKETS=(
    "gs://${PROJECT_ID}-artifacts"
    "gs://${PROJECT_ID}-logs"
  )
  
  for bucket in "${BUCKETS[@]}"; do
    if gsutil ls -b "$bucket" &> /dev/null; then
      print_warn "バケット '$bucket' は既に存在します。"
    else
      gsutil mb -l "$REGION" "$bucket"
      print_info "バケット '$bucket' を作成しました。"
    fi
  done
  
  print_info "ストレージバケットの作成が完了しました。"
}

# GKEクラスタの作成
create_gke_cluster() {
  print_step "GKEクラスタを作成しています..."
  
  CLUSTER_NAME="ai-team-dev-cluster"
  
  if gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID" &> /dev/null; then
    print_warn "GKEクラスタ '$CLUSTER_NAME' は既に存在します。"
  else
    gcloud container clusters create "$CLUSTER_NAME" \
      --region="$REGION" \
      --num-nodes=3 \
      --machine-type="e2-standard-4" \
      --disk-size=100 \
      --release-channel=regular \
      --enable-ip-alias \
      --enable-autoscaling \
      --min-nodes=1 \
      --max-nodes=5 \
      --service-account="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
      --enable-network-policy \
      --enable-autoupgrade \
      --enable-autorepair \
      --scopes="cloud-platform" \
      --project="$PROJECT_ID"
    
    print_info "GKEクラスタ '$CLUSTER_NAME' を作成しました。"
  fi
  
  # クラスタの認証情報を取得
  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID"
  
  print_info "GKEクラスタの作成が完了しました。"
}

# クラスタにNginx Ingressコントローラをインストール
install_ingress_controller() {
  print_step "Nginx Ingressコントローラをインストールしています..."
  
  # Helmがインストールされているか確認
  if ! command -v helm &> /dev/null; then
    print_error "Helmコマンドが見つかりません。Helmをインストールしてください。"
    exit 1
  fi
  
  # Helmリポジトリ追加
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
  helm repo update
  
  # Ingress Nginxをインストール
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx \
    --create-namespace \
    --set controller.replicaCount=2 \
    --set controller.nodeSelector."kubernetes\.io/os"=linux \
    --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux
  
  print_info "Nginx Ingressコントローラのインストールが完了しました。"
}

# メイン処理
main() {
  print_step "AIエージェントチーム開発用GCPリソース作成を開始します..."
  
  check_requirements
  create_project
  enable_apis
  create_service_accounts
  create_storage_buckets
  create_gke_cluster
  install_ingress_controller
  
  print_step "セットアップが完了しました！"
  echo ""
  print_info "プロジェクトID: $PROJECT_ID"
  print_info "GKEクラスタ: ai-team-dev-cluster (リージョン: $REGION)"
  print_info "サービスアカウント: ${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  echo ""
  print_info "これでKubernetesマニフェストをデプロイできます。"
  print_info "次のステップ: ./scripts/deploy.sh を実行してアプリケーションをデプロイしてください。"
}

# スクリプト実行
main 