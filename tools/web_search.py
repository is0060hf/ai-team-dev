"""
Web検索ツールモジュール。
エージェントがWebから情報を検索するための機能を提供します。
"""

import json
import requests
from typing import Dict, Any, List, Optional

from crewai.tools import BaseTool
from utils.logger import logger
from utils.config import config


class WebSearchTool(BaseTool):
    """Web検索ツール"""
    
    name: str = "Web検索"
    description: str = "指定されたクエリでWeb検索を実行し、検索結果を返します。"
    
    def _run(self, query: str, result_count: int = 5) -> str:
        """
        Web検索を実行し、結果を返します。
        
        Args:
            query: 検索クエリ
            result_count: 取得する結果の数（最大10）
            
        Returns:
            str: 検索結果の文字列表現
        """
        try:
            # API設定の確認
            if not config.SERPER_API_KEY:
                return "エラー: Web検索APIキー（SERPER_API_KEY）が設定されていません。"
            
            # 結果数の検証
            if result_count > 10:
                result_count = 10
                logger.warning("result_countは最大10です。10に制限されます。")
            
            logger.info(f"Web検索を実行します: {query}")
            
            # Serper API リクエスト
            url = "https://google.serper.dev/search"
            payload = json.dumps({
                "q": query,
                "num": result_count
            })
            headers = {
                'X-API-KEY': config.SERPER_API_KEY,
                'Content-Type': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            response.raise_for_status()  # エラーレスポンスの場合は例外を発生
            
            search_results = response.json()
            
            # 結果の整形
            formatted_results = self._format_search_results(search_results)
            return formatted_results
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Web検索中にリクエストエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Web検索中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _format_search_results(self, search_results: Dict[str, Any]) -> str:
        """
        検索結果を読みやすい形式にフォーマットします。
        
        Args:
            search_results: API応答からの検索結果
            
        Returns:
            str: フォーマットされた検索結果
        """
        formatted_text = "【検索結果】\n\n"
        
        # 通常の検索結果
        if "organic" in search_results:
            for i, result in enumerate(search_results["organic"], 1):
                title = result.get("title", "タイトルなし")
                link = result.get("link", "")
                snippet = result.get("snippet", "説明なし")
                
                formatted_text += f"{i}. {title}\n"
                formatted_text += f"   URL: {link}\n"
                formatted_text += f"   {snippet}\n\n"
        
        # 知識パネル（Knowledge Graph）があれば追加
        if "knowledgeGraph" in search_results:
            kg = search_results["knowledgeGraph"]
            title = kg.get("title", "")
            description = kg.get("description", "")
            formatted_text += f"【知識パネル】\n{title}: {description}\n\n"
        
        # 回答ボックス（Answer Box）があれば追加
        if "answerBox" in search_results:
            ab = search_results["answerBox"]
            title = ab.get("title", "")
            answer = ab.get("answer", ab.get("snippet", ""))
            formatted_text += f"【回答ボックス】\n{title}\n{answer}\n\n"
        
        return formatted_text


class BasicWebSearchTool(BaseTool):
    """
    基本的なWeb検索ツール
    SerperのAPIキーがない場合にも動作する簡易版の検索ツール
    注意: この実装は教育目的であり、本番環境では適切なAPIを使用すべきです
    """
    
    name: str = "基本Web検索"
    description: str = "指定されたクエリで簡易的なWeb検索を実行し、検索結果の説明を返します。"
    
    def _run(self, query: str) -> str:
        """
        簡易的なWeb検索の説明を返します。
        
        Args:
            query: 検索クエリ
            
        Returns:
            str: 検索結果の説明
        """
        logger.info(f"基本Web検索（シミュレーション）: {query}")
        
        # 実際のAPI呼び出しではなく、検索方法の説明を返す
        return (
            f"検索クエリ '{query}' のWeb検索結果（シミュレーション）:\n\n"
            "注意: これは実際の検索結果ではなく、検索方法の説明です。\n\n"
            "実際のWeb検索を有効にするには、SerperなどのAPIサービスに登録し、\n"
            "APIキーを取得して環境変数 'SERPER_API_KEY' に設定してください。\n\n"
            "Web検索が有効になると、このツールは現在のWeb情報にアクセスできるようになります。"
        ) 