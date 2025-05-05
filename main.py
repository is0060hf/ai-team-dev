"""
メインアプリケーションのエントリーポイント。
AI開発エージェントチームのワークフローを実行します。
"""

import os
import sys
import json
from typing import List, Dict, Any

from utils.logger import logger
from utils.config import config
from tools import FileReadTool, FileWriteTool, JsonReadTool, JsonWriteTool, BasicWebSearchTool
from tools import CodeExecutionTool, UnitTestTool, CodeAnalysisTool
from processes import create_basic_workflow, create_full_development_workflow, execute_and_monitor_workflow


def setup_environment():
    """環境のセットアップを行います"""
    # artifactsディレクトリの確認・作成
    artifacts_dir = os.path.join(os.getcwd(), "artifacts")
    if not os.path.exists(artifacts_dir):
        logger.info("artifactsディレクトリを作成します。")
        os.makedirs(artifacts_dir)


def run_basic_workflow(tools: List, agent_count: int, request: str) -> Dict[str, Any]:
    """基本的なワークフローを実行します"""
    logger.info(f"基本ワークフローを実行します（エンジニア: {agent_count}名, テスター: {agent_count}名）")
    
    # 基本ワークフローCrewの作成
    crew = create_basic_workflow(
        pdm_tools=tools,
        pm_tools=tools,
        designer_tools=tools,
        pl_tools=tools,
        engineer_tools=tools,
        tester_tools=tools,
        engineer_count=agent_count,
        tester_count=agent_count,
    )
    
    # Crewの実行
    result = crew.kickoff(inputs={"request": request})
    
    return {"success": True, "result": result}


def run_full_workflow(tools: List, agent_count: int, request: str) -> Dict[str, Any]:
    """完全なワークフローを実行します"""
    logger.info(f"完全な開発ワークフローを実行します（エンジニア: {agent_count}名, テスター: {agent_count}名）")
    
    # 完全なワークフローCrewの作成
    crew, context = create_full_development_workflow(
        request=request,
        pdm_tools=tools,
        pm_tools=tools,
        designer_tools=tools,
        pl_tools=tools,
        engineer_tools=tools,
        tester_tools=tools,
        engineer_count=agent_count,
        tester_count=agent_count,
    )
    
    # Crewの実行と監視
    result = execute_and_monitor_workflow(crew, context)
    
    # ワークフローコンテキストの保存
    context_json = context.to_json()
    with open(os.path.join("artifacts", "workflow_context.json"), "w", encoding="utf-8") as f:
        f.write(context_json)
    
    return {"success": True, "result": result}


def main():
    """
    アプリケーションのメインエントリーポイント。
    """
    logger.info("AI開発エージェントチームアプリケーションを開始します。")
    
    # 設定の検証
    if not config.validate():
        logger.error("設定の検証に失敗しました。アプリケーションを終了します。")
        sys.exit(1)
    
    # 環境のセットアップ
    setup_environment()
    
    try:
        # ツールの初期化
        file_read_tool = FileReadTool()
        file_write_tool = FileWriteTool()
        json_read_tool = JsonReadTool()
        json_write_tool = JsonWriteTool()
        web_search_tool = BasicWebSearchTool()
        code_execution_tool = CodeExecutionTool()
        unit_test_tool = UnitTestTool()
        code_analysis_tool = CodeAnalysisTool()
        
        # 基本ツールパッケージ
        basic_tools = [
            file_read_tool,
            file_write_tool,
            json_read_tool,
            json_write_tool,
            web_search_tool,
            code_execution_tool,
            unit_test_tool,
            code_analysis_tool,
        ]
        
        # エージェント数の取得
        agent_count = config.AGENT_COUNT
        
        # サンプル要求
        example_request = """
        簡単なタスク管理Webアプリケーションを開発したいと考えています。主な機能は以下の通りです：
        
        1. ユーザーはタスクを作成、編集、削除できること
        2. タスクにはタイトル、説明、期限、優先度を設定できること
        3. タスクをカテゴリごとに分類できること
        4. タスクをドラッグアンドドロップで並べ替えられること
        5. 完了したタスクにはチェックを入れられること
        6. レスポンシブデザインで、スマートフォンでも使いやすいこと
        
        技術的な要件は特にありませんが、使いやすさとシンプルさを重視しています。
        最初のバージョンでは、ユーザー認証は不要です。
        """
        
        # ワークフロータイプの選択（環境変数またはコマンドライン引数から取得可能）
        workflow_type = os.environ.get("WORKFLOW_TYPE", "full").lower()
        
        if workflow_type == "basic":
            # 基本ワークフローの実行
            result = run_basic_workflow(basic_tools, agent_count, example_request)
        else:
            # 完全なワークフローの実行
            result = run_full_workflow(basic_tools, agent_count, example_request)
        
        logger.info("ワークフロー実行が完了しました。")
        logger.info(f"実行結果の概要: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # 結果の保存
        with open(os.path.join("artifacts", "execution_result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"アプリケーション実行中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 