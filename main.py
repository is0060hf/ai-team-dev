"""
メインアプリケーションのエントリーポイント。
AI開発エージェントチームのワークフローを実行します。
"""

import os
import sys
from typing import List

from utils.logger import logger
from utils.config import config
from tools import FileReadTool, FileWriteTool, JsonReadTool, JsonWriteTool, BasicWebSearchTool
from tools import CodeExecutionTool, UnitTestTool, CodeAnalysisTool
from processes import create_basic_workflow


def main():
    """
    アプリケーションのメインエントリーポイント。
    """
    logger.info("AI開発エージェントチームアプリケーションを開始します。")
    
    # 設定の検証
    if not config.validate():
        logger.error("設定の検証に失敗しました。アプリケーションを終了します。")
        sys.exit(1)
    
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
        
        # 簡易サンプルの実行
        logger.info(f"基本ワークフローを実行します（エンジニア: {agent_count}名, テスター: {agent_count}名）")
        
        # 基本ワークフローCrewの作成
        crew = create_basic_workflow(
            pdm_tools=basic_tools,
            pm_tools=basic_tools,
            designer_tools=basic_tools,
            pl_tools=basic_tools,
            engineer_tools=basic_tools,
            tester_tools=basic_tools,
            engineer_count=agent_count,
            tester_count=agent_count,
        )
        
        # 以下の部分は実際のプロジェクトでは人間（プロダクトオーナー）からの入力になります
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
        
        # Crewの実行（実際のプロダクトオーナーの要求を渡す）
        result = crew.kickoff(inputs={"request": example_request})
        
        logger.info("ワークフロー実行が完了しました。")
        logger.info(f"最終結果: {result}")
        
    except Exception as e:
        logger.error(f"アプリケーション実行中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 