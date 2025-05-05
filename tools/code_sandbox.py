"""
コード実行サンドボックスモジュール。
エージェントがコードを安全に実行・テストするための機能を提供します。
"""

import os
import sys
import subprocess
import tempfile
import traceback
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager

from crewai.tools import BaseTool
from utils.logger import logger


class CodeExecutionTool(BaseTool):
    """コード実行ツール"""
    
    name: str = "コード実行"
    description: str = "指定されたPythonコードを安全な環境で実行し、結果を返します。"
    
    def _run(self, code: str, timeout: int = 10) -> str:
        """
        Pythonコードを安全な環境で実行し、結果を返します。
        
        Args:
            code: 実行するPythonコード
            timeout: 実行タイムアウト秒数（デフォルト: 10秒）
            
        Returns:
            str: 実行結果または実行エラーメッセージ
        """
        logger.info("コード実行ツールが呼び出されました。")
        
        # コードを一時ファイルに書き込む
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)
        
        try:
            # サブプロセスでコードを実行
            result = subprocess.run(
                [sys.executable, temp_file_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            # 標準出力と標準エラー出力を取得
            stdout = result.stdout
            stderr = result.stderr
            
            # 実行結果のフォーマット
            if result.returncode == 0:
                output = f"実行成功（終了コード: 0）\n\n==== 出力 ====\n{stdout}\n"
            else:
                output = f"実行失敗（終了コード: {result.returncode}）\n\n==== エラー ====\n{stderr}\n\n==== 出力 ====\n{stdout}\n"
            
            return output
        except subprocess.TimeoutExpired:
            return f"エラー: コードの実行がタイムアウトしました（{timeout}秒を超過）。"
        except Exception as e:
            return f"エラー: コードの実行中に例外が発生しました: {str(e)}"
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


class UnitTestTool(BaseTool):
    """ユニットテスト実行ツール"""
    
    name: str = "ユニットテスト実行"
    description: str = "指定されたユニットテストコードを実行し、テスト結果を返します。"
    
    def _run(self, test_code: str, timeout: int = 20) -> str:
        """
        ユニットテストコードを実行し、結果を返します。
        
        Args:
            test_code: 実行するユニットテストコード（unittest形式またはpytest形式）
            timeout: 実行タイムアウト秒数（デフォルト: 20秒）
            
        Returns:
            str: テスト実行結果またはエラーメッセージ
        """
        logger.info("ユニットテスト実行ツールが呼び出されました。")
        
        # テストコードを一時ファイルに書き込む
        with tempfile.NamedTemporaryFile(suffix='_test.py', mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(test_code)
        
        try:
            # pytest コマンドが利用可能かチェック
            pytest_available = self._check_command_available("pytest")
            
            if pytest_available:
                # pytestを使用してテストを実行
                result = subprocess.run(
                    ["pytest", "-v", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )
            else:
                # pytestが利用できない場合はPython標準のunittestを使用
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )
            
            # 標準出力と標準エラー出力を取得
            stdout = result.stdout
            stderr = result.stderr
            
            # テスト結果のフォーマット
            if result.returncode == 0:
                output = f"テスト成功（全テスト通過）\n\n==== テスト結果 ====\n{stdout}\n"
            else:
                output = f"テスト失敗（一部テストに失敗）\n\n==== テスト結果 ====\n{stdout}\n\n==== エラー ====\n{stderr}\n"
            
            return output
        except subprocess.TimeoutExpired:
            return f"エラー: テスト実行がタイムアウトしました（{timeout}秒を超過）。"
        except Exception as e:
            return f"エラー: テスト実行中に例外が発生しました: {str(e)}"
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
    
    def _check_command_available(self, command: str) -> bool:
        """コマンドが利用可能かチェックする"""
        try:
            subprocess.run(
                [command, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            return True
        except Exception:
            return False


class CodeAnalysisTool(BaseTool):
    """コード分析ツール"""
    
    name: str = "コード分析"
    description: str = "指定されたコードを静的に分析し、コードの品質、潜在的な問題、改善点を識別します。"
    
    def _run(self, code: str, analyze_complexity: bool = True, analyze_style: bool = True) -> str:
        """
        コードを静的に分析し、結果を返します。
        
        Args:
            code: 分析するPythonコード
            analyze_complexity: コードの複雑さを分析するかどうか
            analyze_style: コードスタイルを分析するかどうか
            
        Returns:
            str: 分析結果またはエラーメッセージ
        """
        logger.info("コード分析ツールが呼び出されました。")
        
        analysis_results = []
        
        # コードを一時ファイルに書き込む
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)
        
        try:
            # コードスタイル分析 (flake8が利用可能な場合)
            if analyze_style and self._check_command_available("flake8"):
                style_result = subprocess.run(
                    ["flake8", temp_file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if style_result.stdout or style_result.stderr:
                    style_issues = style_result.stdout or style_result.stderr
                    analysis_results.append(f"==== スタイル分析 ====\n{style_issues}\n")
                else:
                    analysis_results.append("==== スタイル分析 ====\nスタイルの問題は検出されませんでした。\n")
            
            # コード複雑さ分析 (radonが利用可能な場合)
            if analyze_complexity and self._check_command_available("radon"):
                # 循環的複雑度の分析
                cc_result = subprocess.run(
                    ["radon", "cc", "-s", temp_file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if cc_result.stdout:
                    analysis_results.append(f"==== 複雑度分析 ====\n{cc_result.stdout}\n")
                else:
                    analysis_results.append("==== 複雑度分析 ====\n複雑度情報を取得できませんでした。\n")
                
                # 保守性の分析
                mi_result = subprocess.run(
                    ["radon", "mi", "-s", temp_file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if mi_result.stdout:
                    analysis_results.append(f"==== 保守性分析 ====\n{mi_result.stdout}\n")
            
            # ツールがインストールされていない場合
            if not analysis_results:
                simple_analysis = self._perform_simple_analysis(code)
                analysis_results.append(simple_analysis)
            
            return "\n".join(analysis_results)
        except Exception as e:
            return f"エラー: コード分析中に例外が発生しました: {str(e)}"
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
    
    def _check_command_available(self, command: str) -> bool:
        """コマンドが利用可能かチェックする"""
        try:
            subprocess.run(
                [command, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            return True
        except Exception:
            return False
    
    def _perform_simple_analysis(self, code: str) -> str:
        """
        外部ツールが利用できない場合の簡易的なコード分析
        """
        lines = code.splitlines()
        line_count = len(lines)
        empty_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        max_line_length = max(len(line) for line in lines) if lines else 0
        
        analysis = f"""==== 基本コード分析 ====
コード行数: {line_count}
空行数: {empty_lines}
コメント行数: {comment_lines}
最大行長: {max_line_length}文字

注意:
- 詳細な分析を行うには、flake8 (スタイル分析) とradon (複雑度分析) をインストールしてください。
- pip install flake8 radon
"""
        return analysis 