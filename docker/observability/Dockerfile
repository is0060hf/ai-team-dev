FROM python:3.10-slim

WORKDIR /app

# 依存関係のコピー
COPY requirements.txt .

# 追加で必要なパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements.txt \
    prometheus-client \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    elasticsearch \
    influxdb-client \
    python-json-logger

# アプリケーションのコピー
COPY . .

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
# 起動するサービス: metrics, traces, logs, alerts のいずれか
ENV OBSERVABILITY_SERVICE=metrics

# ログとデータディレクトリの作成
RUN mkdir -p /app/logs /app/data/metrics /app/data/traces /app/data/logs

# ヘルスチェック用のエンドポイント
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

# エントリーポイント（環境変数によって起動するサービスを切り替え）
CMD ["sh", "-c", "python -m api.${OBSERVABILITY_SERVICE}_dashboard"] 