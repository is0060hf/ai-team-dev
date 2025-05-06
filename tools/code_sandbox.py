"""
コード実行サンドボックスモジュール。
エージェントがコードを安全に実行・テストするための機能を提供します。
"""

import os
import sys
import subprocess
import tempfile
import traceback
import venv
import json
import shutil
import re
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager
from pathlib import Path

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


class DependencyManagedCodeSandbox(BaseTool):
    """依存関係管理を含むコード実行サンドボックス"""
    
    name: str = "依存関係管理コード実行"
    description: str = "Python依存関係を管理し、指定されたコードを仮想環境で実行します。"
    
    def __init__(self, sandbox_dir: Optional[str] = None, allowed_packages: Optional[List[str]] = None):
        """
        依存関係管理コード実行サンドボックスを初期化します。
        
        Args:
            sandbox_dir: サンドボックス環境のディレクトリパス（省略時は一時ディレクトリ）
            allowed_packages: インストールを許可するパッケージのリスト（省略時は安全なパッケージのみ）
        """
        super().__init__()
        
        self.sandbox_dir = sandbox_dir or tempfile.mkdtemp(prefix="aidevteam_sandbox_")
        self.venv_dir = os.path.join(self.sandbox_dir, "venv")
        self.code_dir = os.path.join(self.sandbox_dir, "code")
        self.pip_cache_dir = os.path.join(self.sandbox_dir, "pip_cache")
        
        # 許可するパッケージのリスト
        self.allowed_packages = allowed_packages or [
            "numpy", "pandas", "matplotlib", "seaborn", "scikit-learn", 
            "requests", "beautifulsoup4", "flask", "django", "fastapi", 
            "pytest", "sqlalchemy", "pillow", "plotly", "dash", "streamlit",
            "jinja2", "pyyaml", "toml", "rich", "tqdm", "uvicorn", "pytest-mock",
            "aiohttp", "pytest-asyncio", "httpx", "starlette", "arrow", "pendulum"
        ]
        
        # サンドボックス環境を初期化
        self._initialize_sandbox()
    
    def _initialize_sandbox(self) -> None:
        """サンドボックス環境を初期化する"""
        logger.info(f"サンドボックス環境を初期化しています: {self.sandbox_dir}")
        
        # 必要なディレクトリを作成
        os.makedirs(self.code_dir, exist_ok=True)
        os.makedirs(self.pip_cache_dir, exist_ok=True)
        
        # 仮想環境を作成
        if not os.path.exists(self.venv_dir):
            venv.create(self.venv_dir, with_pip=True)
            logger.info(f"仮想環境を作成しました: {self.venv_dir}")
    
    def _get_venv_python(self) -> str:
        """仮想環境のPythonインタプリタパスを取得"""
        if sys.platform == "win32":
            return os.path.join(self.venv_dir, "Scripts", "python.exe")
        return os.path.join(self.venv_dir, "bin", "python")
    
    def _get_venv_pip(self) -> str:
        """仮想環境のpipコマンドパスを取得"""
        if sys.platform == "win32":
            return os.path.join(self.venv_dir, "Scripts", "pip.exe")
        return os.path.join(self.venv_dir, "bin", "pip")
    
    def _install_dependencies(self, requirements: List[str]) -> Tuple[bool, str]:
        """
        依存パッケージをインストールする
        
        Args:
            requirements: インストールするパッケージのリスト
        
        Returns:
            bool: インストール成功したかどうか
            str: インストール結果メッセージ
        """
        # 安全でないパッケージをフィルタリング
        filtered_requirements = []
        skipped_packages = []
        
        for req in requirements:
            # バージョン指定をパースしてパッケージ名を取得
            package_name = re.split(r'[=<>]', req)[0].strip()
            
            if package_name in self.allowed_packages:
                filtered_requirements.append(req)
            else:
                skipped_packages.append(req)
        
        # 要件がない場合は早期リターン
        if not filtered_requirements:
            if skipped_packages:
                return False, f"エラー: 安全でないため、以下のパッケージはインストールされませんでした: {', '.join(skipped_packages)}"
            return True, "依存パッケージはありません。"
        
        # requirements.txtファイルを作成
        req_file_path = os.path.join(self.code_dir, "requirements.txt")
        with open(req_file_path, "w") as f:
            f.write("\n".join(filtered_requirements))
        
        # パッケージをインストール
        try:
            result = subprocess.run(
                [
                    self._get_venv_pip(),
                    "install",
                    "-r", req_file_path,
                    "--cache-dir", self.pip_cache_dir,
                    "--no-warn-script-location"
                ],
                capture_output=True,
                text=True,
                timeout=180,  # 3分のタイムアウト
                check=False
            )
            
            if result.returncode == 0:
                success_msg = f"以下のパッケージが正常にインストールされました: {', '.join(filtered_requirements)}"
                if skipped_packages:
                    success_msg += f"\n安全でないため、以下のパッケージはスキップされました: {', '.join(skipped_packages)}"
                return True, success_msg
            else:
                return False, f"パッケージのインストールに失敗しました:\n{result.stderr}"
        
        except subprocess.TimeoutExpired:
            return False, "パッケージインストールがタイムアウトしました（180秒）。"
        except Exception as e:
            return False, f"パッケージインストール中にエラーが発生しました: {str(e)}"
    
    def _run(self, code: str, requirements: str = "", timeout: int = 30) -> str:
        """
        依存関係を管理して、Pythonコードを仮想環境で実行します。
        
        Args:
            code: 実行するPythonコード
            requirements: 必要な依存パッケージのリスト（各行に1パッケージ）またはJSON形式の配列
            timeout: 実行タイムアウト秒数（デフォルト: 30秒）
            
        Returns:
            str: 実行結果または実行エラーメッセージ
        """
        logger.info("依存関係管理コード実行ツールが呼び出されました。")
        
        # 依存パッケージリストをパース
        try:
            if requirements.strip().startswith("[") and requirements.strip().endswith("]"):
                # JSON形式の場合
                packages = json.loads(requirements)
            else:
                # 単純なテキスト形式の場合
                packages = [pkg.strip() for pkg in requirements.split("\n") if pkg.strip()]
        except json.JSONDecodeError:
            # JSONのパースに失敗した場合は単純な行分割
            packages = [pkg.strip() for pkg in requirements.split("\n") if pkg.strip()]
        
        # 依存パッケージをインストール
        success, install_message = self._install_dependencies(packages)
        
        # コードを一時ファイルに書き込む
        code_file_path = os.path.join(self.code_dir, "script.py")
        with open(code_file_path, "w") as f:
            f.write(code)
        
        results = []
        results.append(f"==== 依存パッケージ管理 ====\n{install_message}\n")
        
        try:
            # 仮想環境でコードを実行
            result = subprocess.run(
                [self._get_venv_python(), code_file_path],
                cwd=self.code_dir,
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
                results.append(f"==== 実行成功（終了コード: 0）====\n{stdout}\n")
            else:
                results.append(f"==== 実行失敗（終了コード: {result.returncode}）====\n{stderr}\n\n==== 出力 ====\n{stdout}\n")
            
            return "\n".join(results)
        except subprocess.TimeoutExpired:
            results.append(f"エラー: コードの実行がタイムアウトしました（{timeout}秒を超過）。")
            return "\n".join(results)
        except Exception as e:
            results.append(f"エラー: コードの実行中に例外が発生しました: {str(e)}")
            return "\n".join(results)
    
    def cleanup(self) -> None:
        """サンドボックス環境を削除する"""
        try:
            shutil.rmtree(self.sandbox_dir)
            logger.info(f"サンドボックス環境を削除しました: {self.sandbox_dir}")
        except Exception as e:
            logger.error(f"サンドボックス環境の削除中にエラーが発生しました: {str(e)}")
    
    def __del__(self):
        """デストラクタ：インスタンス破棄時にクリーンアップ"""
        self.cleanup()


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


class DependencyManagedUnitTestTool(BaseTool):
    """依存関係管理を含むユニットテスト実行ツール"""
    
    name: str = "依存関係管理ユニットテスト実行"
    description: str = "依存関係を管理して、ユニットテストを仮想環境で実行します。"
    
    def __init__(self, sandbox_dir: Optional[str] = None, allowed_packages: Optional[List[str]] = None):
        """
        依存関係管理ユニットテスト実行ツールを初期化します。
        
        Args:
            sandbox_dir: サンドボックス環境のディレクトリパス（省略時は一時ディレクトリ）
            allowed_packages: インストールを許可するパッケージのリスト（省略時は安全なパッケージのみ）
        """
        super().__init__()
        
        # サンドボックス環境を共有するために、依存関係管理コード実行ツールを内部で使用
        self.sandbox = DependencyManagedCodeSandbox(sandbox_dir, allowed_packages)
    
    def _run(self, test_code: str, requirements: str = "", timeout: int = 30) -> str:
        """
        依存関係を管理して、ユニットテストを仮想環境で実行します。
        
        Args:
            test_code: 実行するユニットテストコード（unittest形式またはpytest形式）
            requirements: 必要な依存パッケージのリスト（各行に1パッケージ）またはJSON形式の配列
            timeout: 実行タイムアウト秒数（デフォルト: 30秒）
            
        Returns:
            str: テスト実行結果またはエラーメッセージ
        """
        logger.info("依存関係管理ユニットテスト実行ツールが呼び出されました。")
        
        # 依存パッケージリストをパース
        try:
            if requirements.strip().startswith("[") and requirements.strip().endswith("]"):
                # JSON形式の場合
                packages = json.loads(requirements)
            else:
                # 単純なテキスト形式の場合
                packages = [pkg.strip() for pkg in requirements.split("\n") if pkg.strip()]
        except json.JSONDecodeError:
            # JSONのパースに失敗した場合は単純な行分割
            packages = [pkg.strip() for pkg in requirements.split("\n") if pkg.strip()]
        
        # pytestを依存パッケージリストに追加
        if "pytest" not in packages:
            packages.append("pytest")
        
        # 依存パッケージをインストール
        success, install_message = self.sandbox._install_dependencies(packages)
        
        # テストコードを一時ファイルに書き込む
        test_file_path = os.path.join(self.sandbox.code_dir, "test_script.py")
        with open(test_file_path, "w") as f:
            f.write(test_code)
        
        results = []
        results.append(f"==== 依存パッケージ管理 ====\n{install_message}\n")
        
        try:
            # 仮想環境でpytestを実行
            result = subprocess.run(
                [
                    self.sandbox._get_venv_python(),
                    "-m", "pytest", "-v", test_file_path
                ],
                cwd=self.sandbox.code_dir,
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
                results.append(f"==== テスト成功（全テスト通過）====\n{stdout}\n")
            else:
                results.append(f"==== テスト失敗（一部テストに失敗）====\n{stdout}\n\n==== エラー ====\n{stderr}\n")
            
            return "\n".join(results)
        except subprocess.TimeoutExpired:
            results.append(f"エラー: テスト実行がタイムアウトしました（{timeout}秒を超過）。")
            return "\n".join(results)
        except Exception as e:
            results.append(f"エラー: テスト実行中に例外が発生しました: {str(e)}")
            return "\n".join(results)
    
    def cleanup(self) -> None:
        """サンドボックス環境を削除する"""
        self.sandbox.cleanup()
    
    def __del__(self):
        """デストラクタ：インスタンス破棄時にクリーンアップ"""
        self.cleanup()


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