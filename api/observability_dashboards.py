"""
オブザーバビリティダッシュボード起動スクリプト。
メトリクス、トレース、ログ、アラートのダッシュボードをまとめて起動します。
"""

import argparse
import subprocess
import sys
import os
import threading
import signal
import time
from pathlib import Path

from utils.config import config
from utils.logger import get_structured_logger

# ロガーの取得
logger = get_structured_logger("observability")

# ダッシュボードの設定
DASHBOARDS = [
    {
        "name": "メトリクスダッシュボード",
        "module": "api.metrics_dashboard",
        "enabled_config": "ENABLE_METRICS_DASHBOARD",
        "port_offset": 1
    },
    {
        "name": "トレースダッシュボード",
        "module": "api.traces_dashboard",
        "enabled_config": "ENABLE_TRACES_DASHBOARD",
        "port_offset": 2
    },
    {
        "name": "ログダッシュボード",
        "module": "api.logs_dashboard",
        "enabled_config": "ENABLE_LOGS_DASHBOARD",
        "port_offset": 3
    },
    {
        "name": "アラートダッシュボード",
        "module": "api.alerts_dashboard",
        "enabled_config": "ENABLE_ALERTS_DASHBOARD",
        "port_offset": 4
    }
]

# 実行中のプロセスを格納する辞書
running_processes = {}


def start_dashboard(module, port):
    """
    指定されたモジュールのDashアプリケーションを起動
    
    Args:
        module: 起動するモジュール名
        port: 使用するポート番号
    
    Returns:
        subprocess.Popen: 起動したプロセス
    """
    cmd = [sys.executable, "-m", module]
    
    # 環境変数を設定（ポート番号など）
    env = os.environ.copy()
    env["DASHBOARD_PORT"] = str(port)
    
    # プロセスを起動
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    return process


def monitor_process(process, name, output_lock):
    """
    プロセスの出力を監視し、ログに出力
    
    Args:
        process: 監視するプロセス
        name: ダッシュボード名
        output_lock: 出力用のロック
    """
    for line in process.stdout:
        with output_lock:
            logger.info(f"[{name}] {line.strip()}")
    
    for line in process.stderr:
        with output_lock:
            logger.error(f"[{name}] {line.strip()}")


def start_all_dashboards():
    """すべてのダッシュボードを起動"""
    base_port = config.DASHBOARD_PORT
    output_lock = threading.Lock()
    
    logger.info("オブザーバビリティダッシュボードを起動します...")
    
    for dashboard in DASHBOARDS:
        # 設定で有効になっているか確認
        enabled_config = dashboard["enabled_config"]
        if not getattr(config, enabled_config, True):
            logger.info(f"{dashboard['name']}は設定で無効化されています")
            continue
        
        # ポート番号を計算
        port = base_port + dashboard["port_offset"]
        
        try:
            # ダッシュボードを起動
            process = start_dashboard(dashboard["module"], port)
            running_processes[dashboard["name"]] = process
            
            # 出力を監視するスレッドを起動
            monitor_thread = threading.Thread(
                target=monitor_process,
                args=(process, dashboard["name"], output_lock),
                daemon=True
            )
            monitor_thread.start()
            
            logger.info(f"{dashboard['name']}を起動しました (http://localhost:{port}/)")
            
        except Exception as e:
            logger.error(f"{dashboard['name']}の起動に失敗しました: {str(e)}")
    
    if not running_processes:
        logger.warning("起動中のダッシュボードがありません")
        return
    
    # すべてのダッシュボードのURLを表示
    logger.info("\nオブザーバビリティダッシュボードのURL:")
    for dashboard in DASHBOARDS:
        if dashboard["name"] in running_processes:
            port = base_port + dashboard["port_offset"]
            logger.info(f"- {dashboard['name']}: http://localhost:{port}/")


def stop_all_dashboards():
    """すべてのダッシュボードを停止"""
    logger.info("オブザーバビリティダッシュボードを停止します...")
    
    for name, process in running_processes.items():
        try:
            process.terminate()
            # 少し待ってからKILLシグナルを送信
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            logger.info(f"{name}を停止しました")
        except Exception as e:
            logger.error(f"{name}の停止に失敗しました: {str(e)}")
    
    running_processes.clear()
    logger.info("すべてのダッシュボードを停止しました")


def signal_handler(sig, frame):
    """シグナルハンドラ（Ctrl+Cなどの割り込み処理）"""
    logger.info("終了シグナルを受信しました。ダッシュボードを停止します...")
    stop_all_dashboards()
    sys.exit(0)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="オブザーバビリティダッシュボード（メトリクス、トレース、ログ、アラート）を起動します。"
    )
    
    parser.add_argument(
        "--host", 
        default=config.DASHBOARD_HOST,
        help=f"ホスト名 (デフォルト: {config.DASHBOARD_HOST})"
    )
    
    parser.add_argument(
        "--port", 
        type=int,
        default=config.DASHBOARD_PORT,
        help=f"ベースポート番号 (デフォルト: {config.DASHBOARD_PORT})"
    )
    
    args = parser.parse_args()
    
    # 設定を更新
    config.update("DASHBOARD_HOST", args.host)
    config.update("DASHBOARD_PORT", args.port)
    
    # シグナルハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ダッシュボードを起動
    start_all_dashboards()
    
    # メインスレッドは停止しないようにする
    try:
        while True:
            # 定期的にプロセスの状態を確認
            for name, process in list(running_processes.items()):
                if process.poll() is not None:
                    # プロセスが終了した場合は再起動
                    logger.warning(f"{name}が終了しました。再起動します...")
                    
                    # ダッシュボード情報を取得
                    dashboard = next(d for d in DASHBOARDS if d["name"] == name)
                    port = config.DASHBOARD_PORT + dashboard["port_offset"]
                    
                    # 再起動
                    process = start_dashboard(dashboard["module"], port)
                    running_processes[name] = process
                    
                    # 出力を監視するスレッドを起動
                    output_lock = threading.Lock()
                    monitor_thread = threading.Thread(
                        target=monitor_process,
                        args=(process, name, output_lock),
                        daemon=True
                    )
                    monitor_thread.start()
                    
                    logger.info(f"{name}を再起動しました")
            
            time.sleep(5)
    except KeyboardInterrupt:
        # Ctrl+Cが押されたら停止
        stop_all_dashboards()


if __name__ == "__main__":
    main() 