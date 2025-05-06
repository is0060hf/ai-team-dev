#!/bin/bash

# 仮想環境が有効でない場合は有効化
if [ -z "$VIRTUAL_ENV" ]; then
    echo "仮想環境を有効化します..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "Error: venv ディレクトリが見つかりません。仮想環境を作成してください。"
        echo "python3 -m venv venv"
        exit 1
    fi
fi

# PYTHONPATHにカレントディレクトリを追加
export PYTHONPATH=$PYTHONPATH:.
echo "PYTHONPATH=$PYTHONPATH"

# pytestがインストールされているか確認
if ! command -v pytest &> /dev/null; then
    echo "pytestをインストールします..."
    pip install pytest pytest-cov pytest-mock
fi

# 引数がない場合のデフォルト動作
if [ $# -eq 0 ]; then
    echo "すべてのテストを実行します..."
    pytest -v
    exit $?
fi

# 引数に基づいたテスト実行
case "$1" in
    "unit")
        echo "単体テストを実行します..."
        pytest -v -m "unit or not integration"
        ;;
    "integration")
        echo "統合テストを実行します..."
        pytest -v -m "integration"
        ;;
    "api")
        echo "APIテストを実行します..."
        pytest -v tests/test_api/
        ;;
    "utils")
        echo "ユーティリティテストを実行します..."
        pytest -v tests/test_utils/
        ;;
    "coverage")
        echo "カバレッジレポート付きでテストを実行します..."
        pytest --cov=utils --cov=api --cov-report=term --cov-report=html
        echo "HTMLレポートが htmlcov/ ディレクトリに生成されました"
        ;;
    *)
        echo "特定のテストファイルまたはディレクトリを実行します: $1"
        pytest -v "$1"
        ;;
esac

exit $? 