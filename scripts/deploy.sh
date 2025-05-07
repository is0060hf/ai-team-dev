#!/bin/bash

# AIエージェントチーム開発用デプロイスクリプト

set -e

# スクリプトが存在するディレクトリからプロジェクトルートへ移動
cd "$(dirname "$0")/.."

# 引数の処理
REGISTRY_URL=${1:-"gcr.io/ai-team-dev-project"}
ENVIRONMENT=${2:-"production"}
NAMESPACE="ai-team-dev"

# デプロイメント実行関数
deploy_k8s_manifests() {
  echo "🚀 Kubernetesマニフェストをデプロイします (環境: $ENVIRONMENT)..."
  
  # 名前空間の作成（既に存在する場合はスキップ）
  kubectl apply -f kubernetes/namespace.yaml
  
  # ConfigMapとSecretの適用
  echo "📦 ConfigMapとSecretをデプロイします..."
  kubectl apply -f kubernetes/configmaps/
  kubectl apply -f kubernetes/secrets/
  
  # 永続ボリューム要求の作成
  echo "💾 永続ボリューム要求をデプロイします..."
  kubectl apply -f kubernetes/persistentvolumeclaims/
  
  # StatefulSetの適用（依存サービス）
  echo "🗄️ StatefulSet (ベクトルDBなど) をデプロイします..."
  kubectl apply -f kubernetes/statefulsets/
  
  # 基本サービスの適用
  echo "🔌 サービスをデプロイします..."
  kubectl apply -f kubernetes/services/
  
  # Deploymentの適用
  echo "🏗️ アプリケーションをデプロイします..."
  kubectl apply -f kubernetes/deployments/
  
  # HPAの適用
  echo "⚖️ HPAをデプロイします..."
  kubectl apply -f kubernetes/autoscalers/
  
  # NetworkPolicyの適用
  echo "🔒 ネットワークポリシーをデプロイします..."
  kubectl apply -f kubernetes/networkpolicies/
  
  # Ingressの適用
  echo "🌐 Ingressをデプロイします..."
  kubectl apply -f kubernetes/ingress/
  
  echo "✅ デプロイメントが完了しました。"
}

# イメージのビルドとプッシュ
build_and_push_images() {
  echo "🏭 Dockerイメージをビルド・プッシュします..."
  
  # メインアプリケーション
  docker build -t ${REGISTRY_URL}/ai-team-main-app:latest .
  docker push ${REGISTRY_URL}/ai-team-main-app:latest
  
  # APIサーバー
  docker build -t ${REGISTRY_URL}/ai-team-api-server:latest -f docker/api/Dockerfile .
  docker push ${REGISTRY_URL}/ai-team-api-server:latest
  
  # ダッシュボード
  docker build -t ${REGISTRY_URL}/ai-team-dashboard:latest -f docker/dashboard/Dockerfile .
  docker push ${REGISTRY_URL}/ai-team-dashboard:latest
  
  # オブザーバビリティ
  docker build -t ${REGISTRY_URL}/ai-team-observability:latest -f docker/observability/Dockerfile .
  docker push ${REGISTRY_URL}/ai-team-observability:latest
  
  echo "✅ イメージのビルド・プッシュが完了しました。"
}

# マニフェストの変数置換
prepare_manifests() {
  echo "📝 Kubernetesマニフェストを準備します..."
  
  # 一時ディレクトリの作成
  mkdir -p .tmp_manifests
  
  # すべてのマニフェストをコピー
  cp -r kubernetes/* .tmp_manifests/
  
  # 変数置換
  find .tmp_manifests -type f -name "*.yaml" -exec sed -i "s/\${REGISTRY_URL}/${REGISTRY_URL//\//\\/}/g" {} \;
  
  # 元のディレクトリ名を保持したまま、中身を移動
  find .tmp_manifests -type f -name "*.yaml" | while read file; do
    target_file=${file/.tmp_manifests/kubernetes}
    mkdir -p $(dirname "$target_file")
    mv "$file" "$target_file"
  done
  
  # 一時ディレクトリの削除
  rm -rf .tmp_manifests
  
  echo "✅ マニフェストの準備が完了しました。"
}

# メイン処理
main() {
  echo "🚀 AIエージェントチーム開発環境デプロイを開始します..."
  
  # Docker認証確認
  if ! docker info > /dev/null 2>&1; then
    echo "❌ Dockerが起動していない、またはアクセス権限がありません。"
    exit 1
  fi
  
  # GCPログイン確認
  if ! gcloud auth print-access-token > /dev/null 2>&1; then
    echo "❌ GCPにログインしていません。'gcloud auth login'を実行してください。"
    exit 1
  fi
  
  # GCRログイン
  gcloud auth configure-docker gcr.io
  
  # イメージのビルドとプッシュ
  build_and_push_images
  
  # マニフェストの準備
  prepare_manifests
  
  # Kubernetesクラスタへの認証情報設定
  gcloud container clusters get-credentials ai-team-dev-cluster --region asia-northeast1
  
  # マニフェストのデプロイ
  deploy_k8s_manifests
  
  echo "✨ デプロイが正常に完了しました！"
  echo "📊 ダッシュボードは http://dashboard.ai-team-dev.example.com でアクセスできます"
  echo "🔑 APIサーバーは http://api.ai-team-dev.example.com でアクセスできます"
}

# スクリプト実行
main 