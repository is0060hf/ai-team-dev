"""
専門エージェント連携APIサーバー起動スクリプト。
APIサーバーとダッシュボードサーバーを起動します。
"""

import os
import sys
import argparse
import subprocess
import time
import signal
import threading
from pathlib import Path

# プロジェクトルートへのパスを追加
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import get_agent_logger

logger = get_agent_logger("api_server")


def run_api_server(port: int = 8000, host: str = "0.0.0.0", debug: bool = False):
    """
    FastAPI APIサーバーを起動します。
    
    Args:
        port: 使用するポート番号
        host: ホストアドレス
        debug: デバッグモードで起動するかどうか
    """
    from api.specialist_api import app
    import uvicorn
    
    logger.info(f"専門エージェント連携APIサーバーを起動します: {host}:{port}")
    uvicorn.run(app, host=host, port=port, debug=debug)


def run_dashboard_server(port: int = 8050, host: str = "0.0.0.0", debug: bool = False):
    """
    Dashダッシュボードサーバーを起動します。
    
    Args:
        port: 使用するポート番号
        host: ホストアドレス
        debug: デバッグモードで起動するかどうか
    """
    from api.dashboard import app
    
    logger.info(f"専門エージェントモニタリングダッシュボードを起動します: {host}:{port}")
    app.run(debug=debug, host=host, port=port)


def run_servers_threaded(api_port: int = 8000, dashboard_port: int = 8050, debug: bool = False):
    """
    APIサーバーとダッシュボードサーバーを別々のスレッドで起動します。
    
    Args:
        api_port: APIサーバーのポート番号
        dashboard_port: ダッシュボードサーバーのポート番号
        debug: デバッグモードで起動するかどうか
    """
    # APIサーバーのスレッド
    api_thread = threading.Thread(
        target=run_api_server,
        kwargs={"port": api_port, "debug": debug},
        daemon=True
    )
    
    # ダッシュボードサーバーのスレッド
    dashboard_thread = threading.Thread(
        target=run_dashboard_server,
        kwargs={"port": dashboard_port, "debug": debug},
        daemon=True
    )
    
    try:
        # サーバー起動
        api_thread.start()
        dashboard_thread.start()
        
        logger.info("すべてのサーバーが起動しました。Ctrl+Cで終了します。")
        
        # メインスレッドは待機
        while api_thread.is_alive() and dashboard_thread.is_alive():
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("サーバーを終了します...")
    
    logger.info("すべてのサーバーを停止しました。")


def run_servers_subprocess(api_port: int = 8000, dashboard_port: int = 8050, debug: bool = False):
    """
    APIサーバーとダッシュボードサーバーを別々のサブプロセスで起動します。
    
    Args:
        api_port: APIサーバーのポート番号
        dashboard_port: ダッシュボードサーバーのポート番号
        debug: デバッグモードで起動するかどうか
    """
    # プロセスの保持
    processes = []
    
    # FastAPI APIサーバーのコマンド
    api_cmd = [
        sys.executable, "-m", "uvicorn", 
        "api.specialist_api:app", 
        "--host", "0.0.0.0", 
        "--port", str(api_port)
    ]
    
    if debug:
        api_cmd.append("--reload")
    
    # Dashダッシュボードサーバーのコマンド
    dashboard_cmd = [
        sys.executable, "api/dashboard.py"
    ]
    
    try:
        # APIサーバーを起動
        logger.info(f"専門エージェント連携APIサーバーを起動します: ポート {api_port}")
        api_process = subprocess.Popen(api_cmd)
        processes.append(api_process)
        
        # ダッシュボードサーバーを起動
        logger.info(f"専門エージェントモニタリングダッシュボードを起動します: ポート {dashboard_port}")
        dashboard_process = subprocess.Popen(dashboard_cmd)
        processes.append(dashboard_process)
        
        logger.info(f"""
サーバーが起動しました:
- API: http://localhost:{api_port}
- ダッシュボード: http://localhost:{dashboard_port}
Ctrl+Cで終了します。
        """)
        
        # 終了を待つ
        for process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        logger.info("サーバーを終了します...")
        
        # 全プロセスを終了
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    logger.info("すべてのサーバーを停止しました。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="専門エージェント連携APIサーバーとダッシュボードの起動")
    parser.add_argument("--api-port", type=int, default=8000, help="APIサーバーのポート番号")
    parser.add_argument("--dashboard-port", type=int, default=8050, help="ダッシュボードサーバーのポート番号")
    parser.add_argument("--debug", action="store_true", help="デバッグモードで起動")
    parser.add_argument("--method", choices=["thread", "subprocess"], default="subprocess", 
                       help="サーバー起動方法 (thread: スレッド, subprocess: サブプロセス)")
    
    args = parser.parse_args()
    
    if args.method == "thread":
        run_servers_threaded(args.api_port, args.dashboard_port, args.debug)
    else:
        run_servers_subprocess(args.api_port, args.dashboard_port, args.debug) 