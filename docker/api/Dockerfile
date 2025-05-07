FROM python:3.10-slim

WORKDIR /app

# 依存関係のコピー
COPY requirements.txt .

# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ログディレクトリの作成
RUN mkdir -p /app/logs

# ヘルスチェック用のエンドポイント
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# エントリーポイント
CMD ["python", "-m", "api.run_api", "--api-port", "8000", "--dashboard-port", "8050"] 