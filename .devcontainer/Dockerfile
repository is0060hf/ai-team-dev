FROM python:3.10-slim

# 必要なパッケージをインストール
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    git curl wget build-essential libffi-dev libssl-dev zlib1g-dev \
    sudo vim nano less jq unzip procps lsb-release \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Google Cloud SDKのインストール
RUN curl -sSL https://sdk.cloud.google.com | bash
ENV PATH $PATH:/root/google-cloud-sdk/bin

# Dockerとkubectl のインストール
RUN curl -fsSL https://get.docker.com | sh \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# 開発用ユーザー作成
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Docker グループに追加
RUN groupadd docker || true \
    && usermod -aG docker $USERNAME

# Python/開発ツールのセットアップ
RUN pip install --upgrade pip setuptools wheel \
    && pip install flake8 black isort pytest pytest-cov coverage \
    && pip install nodemon

# 作業ディレクトリ
WORKDIR /workspace

# ユーザー切り替え
USER $USERNAME

# 環境変数の設定
ENV PYTHONUNBUFFERED=1 