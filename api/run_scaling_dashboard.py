"""
動的エージェントスケーリングダッシュボードを起動するモジュール。
"""

import os
import sys
import signal
import threading
import argparse
from pathlib import Path

# パスの調整（必要に応じて）
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from api.scaling_dashboard import app
from utils.load_detection import start_load_monitoring, stop_load_monitoring
from utils.logger import get_structured_logger

# ロガーの設定
logger = get_structured_logger("scaling_dashboard_server")

def run_dashboard(host='0.0.0.0', port=8050, debug=False):
    """
    スケーリングダッシュボードを実行
    
    Args:
        host: ホスト名
        port: ポート番号
        debug: デバッグモードフラグ
    """
    try:
        logger.info(f"スケーリングダッシュボードを起動: {host}:{port}")
        
        # 負荷モニタリングを開始
        logger.info("負荷メトリクスモニタリングを開始")
        start_load_monitoring(interval=5)  # 5秒ごとにシステムメトリクスを収集
        
        # ダッシュボードの実行
        app.run_server(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        logger.info("キーボード割り込みによりサーバーを終了")
    except Exception as e:
        logger.error(f"ダッシュボード実行中にエラーが発生: {str(e)}")
    finally:
        # 負荷モニタリングを停止
        stop_load_monitoring()
        logger.info("負荷メトリクスモニタリングを停止")
        logger.info("スケーリングダッシュボードサーバーを終了")

def run_dashboard_in_thread(host='0.0.0.0', port=8050):
    """
    別スレッドでスケーリングダッシュボードを実行
    
    Args:
        host: ホスト名
        port: ポート番号
        
    Returns:
        threading.Thread: ダッシュボードスレッド
    """
    thread = threading.Thread(
        target=run_dashboard,
        args=(host, port, False),
        daemon=True
    )
    thread.start()
    logger.info(f"スケーリングダッシュボードをバックグラウンドで起動: {host}:{port}")
    return thread

def signal_handler(sig, frame):
    """シグナルハンドラー"""
    logger.info(f"シグナル {sig} を受信: サーバーを終了")
    # 負荷モニタリングを停止
    stop_load_monitoring()
    sys.exit(0)

if __name__ == "__main__":
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="動的エージェントスケーリングダッシュボードサーバー")
    parser.add_argument('--host', default='0.0.0.0', help='ホスト名（デフォルト: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=8050, help='ポート番号（デフォルト: 8050）')
    parser.add_argument('--debug', action='store_true', help='デバッグモードで実行')
    args = parser.parse_args()
    
    # シグナルハンドラーの登録
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # サーバーの実行
    run_dashboard(host=args.host, port=args.port, debug=args.debug) 