"""
テスターエージェントモジュール。
テスト計画、テストケースの作成、テスト実行、バグ報告を担当します。
"""

import json
import os
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("tester")


class TestCaseGeneratorTool(Tool):
    """テストケース生成ツール"""
    
    name = "テストケース生成"
    description = "機能仕様書やコードに基づいてテストケースを生成します。"
    
    def _run(self, specification: str, code: str = None) -> str:
        """
        テストケースを生成します。
        
        Args:
            specification: 機能仕様書
            code: テスト対象のコード（オプション）
            
        Returns:
            str: テストケース（JSON形式）
        """
        logger.info("テストケース生成ツールが呼び出されました。")
        
        # サンプルのテストケース
        test_cases = [
            {
                "id": "TC001",
                "title": "ユーザー登録の成功ケース",
                "description": "有効な入力データでユーザーが正常に登録できることを確認",
                "preconditions": "システムが稼働中であること",
                "steps": [
                    "ユーザー登録ページにアクセスする",
                    "名前に「テストユーザー」と入力する",
                    "メールアドレスに「test@example.com」と入力する",
                    "パスワードに「SecurePassword123」と入力する",
                    "パスワード確認に「SecurePassword123」と入力する",
                    "登録ボタンをクリックする"
                ],
                "expected_results": [
                    "ユーザーが正常に作成される",
                    "ユーザーに確認メールが送信される",
                    "登録完了メッセージが表示される",
                    "ログインページにリダイレクトされる"
                ],
                "test_data": {
                    "name": "テストユーザー",
                    "email": "test@example.com",
                    "password": "SecurePassword123"
                },
                "priority": "高",
                "category": "機能テスト"
            },
            {
                "id": "TC002",
                "title": "無効なメールアドレスでのユーザー登録失敗ケース",
                "description": "不正なメールアドレス形式ではユーザー登録が失敗することを確認",
                "preconditions": "システムが稼働中であること",
                "steps": [
                    "ユーザー登録ページにアクセスする",
                    "名前に「テストユーザー」と入力する",
                    "メールアドレスに「invalid-email」と入力する",
                    "パスワードに「SecurePassword123」と入力する",
                    "パスワード確認に「SecurePassword123」と入力する",
                    "登録ボタンをクリックする"
                ],
                "expected_results": [
                    "ユーザーが作成されない",
                    "「有効なメールアドレスを入力してください」というエラーメッセージが表示される"
                ],
                "test_data": {
                    "name": "テストユーザー",
                    "email": "invalid-email",
                    "password": "SecurePassword123"
                },
                "priority": "中",
                "category": "入力検証"
            },
            {
                "id": "TC003",
                "title": "パスワード不一致でのユーザー登録失敗ケース",
                "description": "パスワードと確認用パスワードが一致しない場合にユーザー登録が失敗することを確認",
                "preconditions": "システムが稼働中であること",
                "steps": [
                    "ユーザー登録ページにアクセスする",
                    "名前に「テストユーザー」と入力する",
                    "メールアドレスに「test@example.com」と入力する",
                    "パスワードに「SecurePassword123」と入力する",
                    "パスワード確認に「DifferentPassword456」と入力する",
                    "登録ボタンをクリックする"
                ],
                "expected_results": [
                    "ユーザーが作成されない",
                    "「パスワードが一致しません」というエラーメッセージが表示される"
                ],
                "test_data": {
                    "name": "テストユーザー",
                    "email": "test@example.com",
                    "password": "SecurePassword123",
                    "password_confirm": "DifferentPassword456"
                },
                "priority": "中",
                "category": "入力検証"
            }
        ]
        
        return json.dumps(test_cases, ensure_ascii=False, indent=2)


class TestExecutionTool(Tool):
    """テスト実行ツール"""
    
    name = "テスト実行"
    description = "テストケースを実行し、結果をレポートします。"
    
    def _run(self, test_cases_json: str, app_url: str = "http://localhost:5000") -> str:
        """
        テストケースを実行します。
        
        Args:
            test_cases_json: テストケース（JSON形式）
            app_url: テスト対象のアプリケーションURL（オプション）
            
        Returns:
            str: テスト結果（JSON形式）
        """
        logger.info("テスト実行ツールが呼び出されました。")
        
        try:
            test_cases = json.loads(test_cases_json)
            
            # テスト実行結果のシミュレーション
            test_results = []
            for test_case in test_cases:
                # 実際のプロジェクトでは実際にテストを実行する
                # 現段階ではシミュレーション結果を返す
                
                # 80%の確率で成功、20%の確率で失敗するシミュレーション
                import random
                is_success = random.random() < 0.8
                
                result = {
                    "test_id": test_case["id"],
                    "title": test_case["title"],
                    "result": "成功" if is_success else "失敗",
                    "execution_time": random.uniform(0.1, 2.0),
                    "timestamp": "2023-08-01T14:30:00Z",
                    "details": []
                }
                
                # 成功/失敗に応じた詳細を追加
                if is_success:
                    for expected in test_case["expected_results"]:
                        result["details"].append({
                            "step": expected,
                            "status": "成功",
                            "actual_result": expected
                        })
                else:
                    # 失敗の場合は、いずれかのステップでランダムに失敗
                    failed_step_index = random.randint(0, len(test_case["expected_results"]) - 1)
                    
                    for i, expected in enumerate(test_case["expected_results"]):
                        if i < failed_step_index:
                            result["details"].append({
                                "step": expected,
                                "status": "成功",
                                "actual_result": expected
                            })
                        elif i == failed_step_index:
                            result["details"].append({
                                "step": expected,
                                "status": "失敗",
                                "actual_result": f"期待結果とは異なる動作: {expected}が実行されませんでした。"
                            })
                            break
                
                test_results.append(result)
            
            # テスト概要の追加
            summary = {
                "total": len(test_results),
                "passed": sum(1 for r in test_results if r["result"] == "成功"),
                "failed": sum(1 for r in test_results if r["result"] == "失敗"),
                "pass_rate": f"{sum(1 for r in test_results if r['result'] == '成功') / len(test_results) * 100:.1f}%"
            }
            
            response = {
                "summary": summary,
                "results": test_results
            }
            
            return json.dumps(response, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"エラー: テスト実行に失敗しました: {str(e)}"


class BugReportTool(Tool):
    """バグ報告ツール"""
    
    name = "バグ報告"
    description = "テスト実行で検出されたバグを詳細に報告します。"
    
    def _run(self, test_result_json: str) -> str:
        """
        テスト結果からバグレポートを生成します。
        
        Args:
            test_result_json: テスト結果（JSON形式）
            
        Returns:
            str: バグレポート（Markdown形式）
        """
        logger.info("バグ報告ツールが呼び出されました。")
        
        try:
            test_result = json.loads(test_result_json)
            
            # バグレポートの作成
            bug_reports = []
            
            for result in test_result.get("results", []):
                if result["result"] == "失敗":
                    # 失敗したテストケースからバグレポートを作成
                    failed_steps = [d for d in result.get("details", []) if d["status"] == "失敗"]
                    
                    for i, step in enumerate(failed_steps):
                        bug_id = f"BUG-{result['test_id']}-{i+1}"
                        
                        bug_report = f"""
# バグレポート: {bug_id}

## 概要
**タイトル**: {result['title']}での失敗
**重要度**: 中
**優先度**: 中
**発見日**: {result.get('timestamp', '不明').split('T')[0]}
**ステータス**: 未対応

## 詳細
**再現条件**: {result['title']}のテストケース実行
**失敗ステップ**: {step['step']}
**期待結果**: {step['step']}
**実際の結果**: {step['actual_result']}

## 再現手順
1. テストケース {result['test_id']} の手順に従って操作
2. {step['step']} の段階で失敗

## 環境情報
- テスト環境: 開発環境
- ブラウザ/クライアント: 自動テスト
- バージョン: 最新

## 追加情報
このバグは自動テスト実行中に検出されました。
システムのコア機能に影響する可能性があるため、優先的に対応することを推奨します。

## スクリーンショット
[スクリーンショットをここに添付]
"""
                        bug_reports.append(bug_report)
            
            if bug_reports:
                return "\n\n---\n\n".join(bug_reports)
            else:
                return "## バグレポート\n\nテスト実行で検出されたバグはありません。全てのテストは正常に完了しました。"
        except Exception as e:
            return f"エラー: バグレポートの生成に失敗しました: {str(e)}"


def create_tester_agent(tools: Optional[List[Tool]] = None, agent_id: int = 1) -> Agent:
    """
    テスターエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        agent_id: エージェントの識別子（複数のテスターエージェントを区別するため）
        
    Returns:
        Agent: 設定されたテスターエージェント
    """
    logger.info(f"テスターエージェント {agent_id} を作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # テスター固有のツールを追加
    tester_specific_tools = [
        TestCaseGeneratorTool(),
        TestExecutionTool(),
        BugReportTool(),
    ]
    
    all_tools = tools + tester_specific_tools
    
    # テスターエージェントの作成
    tester_agent = Agent(
        role=f"QAエンジニア/テスター {agent_id}",
        goal="テスト計画、テストケースを作成し、テストを実行する。バグ報告と再現手順の記録を行う。自動テストコードを作成・実行する。",
        backstory=f"""
        あなたは、品質保証に情熱を持つQAエンジニア/テスター {agent_id} です。
        手動テストと自動テストの両方に精通し、システムの隅々まで探索して潜在的な問題を発見する能力に長けています。
        ユーザーの視点に立ったテスト設計を心がけ、エッジケースやエラー処理も徹底的に検証します。
        バグを見つけた際は、再現手順を明確に記録し、開発者がすぐに対応できるよう詳細な報告書を作成します。
        テスト自動化フレームワークにも精通しており、継続的インテグレーション/継続的デリバリー（CI/CD）
        パイプラインに組み込まれるテストの開発経験もあります。品質基準に妥協せず、常にシステムの改善点を
        見つけることを使命としています。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=False,  # テスターは基本的に下位エージェントに委任しない
    )
    
    return tester_agent


def generate_test_cases(agent: Agent, specification: str, code: str = None) -> Dict[str, Any]:
    """
    テストケースを生成します。
    
    Args:
        agent: テスターエージェント
        specification: 機能仕様書
        code: テスト対象のコード（オプション）
        
    Returns:
        Dict[str, Any]: テストケース
    """
    logger.info("テストケース生成を開始します。")
    
    # テストケース生成タスクの実行
    test_case_task = Task(
        description="機能仕様書に基づいて、包括的なテストケースを作成してください。正常系、異常系、エッジケースを含め、機能が仕様通りに動作することを確認するテストを設計してください。",
        expected_output="テストケース（JSON形式）",
        agent=agent
    )
    
    context = {"specification": specification}
    if code:
        context["code"] = code
    
    test_case_result = agent.execute_task(test_case_task, context=context)
    
    # JSONの場合はパースする
    try:
        test_cases = json.loads(test_case_result)
        test_case_result = test_cases
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("テストケース生成が完了しました。")
    return {"test_cases": test_case_result}


def execute_tests(agent: Agent, test_cases: str, app_url: str = "http://localhost:5000") -> Dict[str, Any]:
    """
    テストを実行します。
    
    Args:
        agent: テスターエージェント
        test_cases: テストケース
        app_url: テスト対象のアプリケーションURL
        
    Returns:
        Dict[str, Any]: テスト結果
    """
    logger.info("テスト実行を開始します。")
    
    # テストケースがJSON文字列でない場合、JSON文字列に変換
    if not isinstance(test_cases, str):
        test_cases_json = json.dumps(test_cases, ensure_ascii=False)
    else:
        test_cases_json = test_cases
    
    # テスト実行タスクの実行
    test_execution_task = Task(
        description="テストケースに基づいてテストを実行し、結果をレポートしてください。各テストの成功/失敗、実行時間、詳細な結果情報を含めてください。",
        expected_output="テスト結果（JSON形式）",
        agent=agent
    )
    
    test_result = agent.execute_task(test_execution_task, context={
        "test_cases": test_cases_json,
        "app_url": app_url
    })
    
    # JSONの場合はパースする
    try:
        results = json.loads(test_result)
        test_result = results
    except:
        # JSON形式でない場合はテキストとして扱う
        pass
    
    logger.info("テスト実行が完了しました。")
    return {"test_results": test_result}


def generate_bug_report(agent: Agent, test_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    バグレポートを生成します。
    
    Args:
        agent: テスターエージェント
        test_result: テスト結果
        
    Returns:
        Dict[str, Any]: バグレポート
    """
    logger.info("バグレポート生成を開始します。")
    
    # テスト結果がJSON文字列でない場合、JSON文字列に変換
    if not isinstance(test_result, str):
        test_result_json = json.dumps(test_result, ensure_ascii=False)
    else:
        test_result_json = test_result
    
    # バグレポート生成タスクの実行
    bug_report_task = Task(
        description="テスト結果から、検出されたバグに関する詳細なレポートを作成してください。バグの再現手順、期待される動作と実際の動作、影響範囲を含めてください。",
        expected_output="バグレポート（Markdown形式）",
        agent=agent
    )
    
    bug_report_result = agent.execute_task(bug_report_task, context={"test_result": test_result_json})
    
    logger.info("バグレポート生成が完了しました。")
    return {"bug_report": bug_report_result} 