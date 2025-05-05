"""
ファイル読み書きツールモジュール。
エージェントがファイルを読み書きするための機能を提供します。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from crewai.tools import BaseTool
from utils.logger import logger


class FileReadTool(BaseTool):
    """ファイル読み込みツール"""
    
    name: str = "ファイル読み込み"
    description: str = "指定されたパスのファイルを読み込み、内容を返します。"
    
    def _run(self, file_path: str) -> str:
        """
        ファイルを読み込み、内容を返します。
        
        Args:
            file_path: 読み込むファイルのパス
            
        Returns:
            str: ファイルの内容
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return f"エラー: ファイル '{file_path}' は存在しません。"
            
            logger.info(f"ファイル '{file_path}' を読み込みます。")
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            
            return content
        except Exception as e:
            error_msg = f"ファイル '{file_path}' の読み込み中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return error_msg


class FileWriteTool(BaseTool):
    """ファイル書き込みツール"""
    
    name: str = "ファイル書き込み"
    description: str = "指定されたパスにファイルを作成または上書きし、内容を書き込みます。"
    
    def _run(self, file_path: str, content: str, append: bool = False) -> str:
        """
        ファイルを書き込みます。
        
        Args:
            file_path: 書き込むファイルのパス
            content: 書き込む内容
            append: 追記モードで書き込むかどうか。Trueの場合は追記モード、Falseの場合は上書きモード。
            
        Returns:
            str: 操作結果メッセージ
        """
        try:
            file_path = Path(file_path)
            
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            mode = "a" if append else "w"
            logger.info(f"ファイル '{file_path}' に{mode}モードで書き込みます。")
            
            with open(file_path, mode, encoding="utf-8") as file:
                file.write(content)
            
            return f"ファイル '{file_path}' への書き込みが完了しました。"
        except Exception as e:
            error_msg = f"ファイル '{file_path}' への書き込み中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return error_msg


class JsonReadTool(BaseTool):
    """JSONファイル読み込みツール"""
    
    name: str = "JSONファイル読み込み"
    description: str = "指定されたパスのJSONファイルを読み込み、Pythonオブジェクトとして返します。"
    
    def _run(self, file_path: str) -> Dict[str, Any]:
        """
        JSONファイルを読み込み、Pythonオブジェクトとして返します。
        
        Args:
            file_path: 読み込むJSONファイルのパス
            
        Returns:
            Dict[str, Any]: JSONデータをパースしたPythonオブジェクト
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return {"error": f"ファイル '{file_path}' は存在しません。"}
            
            logger.info(f"JSONファイル '{file_path}' を読み込みます。")
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            
            return data
        except json.JSONDecodeError as e:
            error_msg = f"JSONファイル '{file_path}' の解析中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"JSONファイル '{file_path}' の読み込み中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}


class JsonWriteTool(BaseTool):
    """JSONファイル書き込みツール"""
    
    name: str = "JSONファイル書き込み"
    description: str = "指定されたパスにJSONファイルを作成または上書きし、Pythonオブジェクトをシリアライズして書き込みます。"
    
    def _run(self, file_path: str, data: Dict[str, Any], indent: int = 2) -> str:
        """
        PythonオブジェクトをJSONにシリアライズし、ファイルに書き込みます。
        
        Args:
            file_path: 書き込むファイルのパス
            data: 書き込むPythonオブジェクト
            indent: インデントのスペース数
            
        Returns:
            str: 操作結果メッセージ
        """
        try:
            file_path = Path(file_path)
            
            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            logger.info(f"JSONファイル '{file_path}' に書き込みます。")
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=indent)
            
            return f"JSONファイル '{file_path}' への書き込みが完了しました。"
        except Exception as e:
            error_msg = f"JSONファイル '{file_path}' への書き込み中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return error_msg 