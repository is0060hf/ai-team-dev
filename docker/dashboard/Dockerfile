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
ENV DASHBOARD_TYPE=main

# ログディレクトリの作成
RUN mkdir -p /app/logs

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8050/ || exit 1

# エントリーポイント（環境変数によって起動するダッシュボードを切り替え）
CMD ["sh", "-c", "python -m api.run_${DASHBOARD_TYPE}_dashboard"] 