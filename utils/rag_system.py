"""
RAG（検索拡張生成）システム実装モジュール。
ベクトルデータベースとLLMを連携させ、検索拡張生成機能を提供します。
"""

import os
import json
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import re

from utils.vector_db import (
    get_vector_db_client, AgentKnowledgeBase, RAGHelper
)
from utils.agent_knowledge_sharing import (
    get_agent_knowledge_base, KnowledgeType, KnowledgeSource
)
from utils.logger import get_agent_logger

logger = get_agent_logger("rag_system")


class RAGConfiguration:
    """RAGシステムの設定クラス"""
    
    # デフォルト設定
    DEFAULT_RESULT_COUNT = 5            # デフォルトの検索結果数
    DEFAULT_SCORE_THRESHOLD = 0.65      # デフォルトのスコア閾値
    DEFAULT_CONTEXT_WINDOW = 8000       # デフォルトのコンテキストウィンドウサイズ
    DEFAULT_COLLECTION_NAME = "agent_knowledge"  # デフォルトのコレクション名
    
    @staticmethod
    def get_result_count() -> int:
        """
        検索結果数を取得します。
        
        Returns:
            int: 検索結果数
        """
        return int(os.environ.get("RAG_RESULT_COUNT", RAGConfiguration.DEFAULT_RESULT_COUNT))
    
    @staticmethod
    def get_score_threshold() -> float:
        """
        スコア閾値を取得します。
        
        Returns:
            float: スコア閾値
        """
        return float(os.environ.get("RAG_SCORE_THRESHOLD", RAGConfiguration.DEFAULT_SCORE_THRESHOLD))
    
    @staticmethod
    def get_context_window() -> int:
        """
        コンテキストウィンドウサイズを取得します。
        
        Returns:
            int: コンテキストウィンドウサイズ
        """
        return int(os.environ.get("RAG_CONTEXT_WINDOW", RAGConfiguration.DEFAULT_CONTEXT_WINDOW))
    
    @staticmethod
    def get_collection_name() -> str:
        """
        コレクション名を取得します。
        
        Returns:
            str: コレクション名
        """
        return os.environ.get("RAG_COLLECTION_NAME", RAGConfiguration.DEFAULT_COLLECTION_NAME)


class RAGSystem:
    """
    RAG（検索拡張生成）システムクラス
    ベクトルデータベースを活用した検索拡張生成を実装します。
    """
    
    def __init__(self, agent_id: Optional[str] = None, collection_name: Optional[str] = None):
        """
        RAGシステムを初期化します。
        
        Args:
            agent_id: エージェントID（特定のエージェントの知識に限定する場合）
            collection_name: コレクション名（省略時はデフォルト）
        """
        self.agent_id = agent_id
        self.collection_name = collection_name or RAGConfiguration.get_collection_name()
        self.rag_helper = RAGHelper(get_vector_db_client())
        
        # エージェント固有の知識ベースを使用するか
        if agent_id:
            self.knowledge_base = get_agent_knowledge_base(agent_id)
            logger.info(f"エージェント {agent_id} の知識ベースを使用するRAGシステムを初期化しました")
        else:
            # 共有知識ベース
            self.knowledge_base = None
            logger.info("共有知識ベースを使用するRAGシステムを初期化しました")
        
        # 結果整形関数の登録
        self.result_formatters = {
            "text": self._format_results_as_text,
            "markdown": self._format_results_as_markdown,
            "json": self._format_results_as_json,
            "context": self._format_results_as_context,
        }
    
    def add_document(self, 
                    text: str, 
                    metadata: Optional[Dict[str, Any]] = None,
                    source: Optional[str] = None,
                    knowledge_type: Optional[str] = None) -> str:
        """
        ドキュメントを追加します。
        
        Args:
            text: ドキュメントテキスト
            metadata: メタデータ（オプション）
            source: ドキュメントの出所（オプション）
            knowledge_type: 知識の種類（オプション）
            
        Returns:
            str: ドキュメントID
        """
        # エージェント固有の知識ベースを使用する場合
        if self.agent_id:
            doc_id = self.knowledge_base.add_knowledge(
                text=text,
                source=source or KnowledgeSource.GENERATED,
                knowledge_type=knowledge_type or KnowledgeType.GENERAL,
                metadata=metadata
            )
        else:
            # 共有知識ベースの場合
            vector_db = get_vector_db_client()
            
            # メタデータの設定
            full_metadata = metadata or {}
            if source:
                full_metadata["source"] = source
            if knowledge_type:
                full_metadata["knowledge_type"] = knowledge_type
            
            # ドキュメントを追加
            ids = vector_db.add_documents(
                documents=[text],
                metadatas=[full_metadata],
                collection_name=self.collection_name
            )
            doc_id = ids[0]
        
        logger.info(f"ドキュメントを追加しました: {doc_id}")
        return doc_id
    
    def search(self,
              query: str,
              n_results: Optional[int] = None,
              filter_metadata: Optional[Dict[str, Any]] = None,
              score_threshold: Optional[float] = None,
              format_as: str = "text") -> Union[str, List[Dict[str, Any]]]:
        """
        ベクトルDBから関連情報を検索します。
        
        Args:
            query: 検索クエリ
            n_results: 取得する結果数（省略時はデフォルト）
            filter_metadata: メタデータによるフィルター（オプション）
            score_threshold: スコア閾値（省略時はデフォルト）
            format_as: 結果の形式（"text", "markdown", "json", "context"）
            
        Returns:
            Union[str, List[Dict[str, Any]]]: 検索結果（形式によって異なる）
        """
        # デフォルト値の設定
        n_results = n_results or RAGConfiguration.get_result_count()
        score_threshold = score_threshold or RAGConfiguration.get_score_threshold()
        
        # エージェント固有の知識ベースを使用する場合
        if self.agent_id:
            results = self.knowledge_base.search_knowledge(
                query=query,
                n_results=n_results,
                filter_metadata=filter_metadata,
                score_threshold=score_threshold
            )
        else:
            # 共有知識ベースの場合
            results = self.rag_helper.vector_db.similarity_search(
                query_text=query,
                n_results=n_results,
                collection_name=self.collection_name,
                filter_metadata=filter_metadata,
                score_threshold=score_threshold
            )
        
        logger.info(f"検索結果: {len(results)} 件見つかりました")
        
        # 結果の形式に応じて整形
        if format_as in self.result_formatters:
            return self.result_formatters[format_as](results, query)
        else:
            # デフォルトはjson形式
            return results
    
    def enhance_prompt(self,
                       prompt: str,
                       query: str,
                       n_results: Optional[int] = None,
                       filter_metadata: Optional[Dict[str, Any]] = None,
                       score_threshold: Optional[float] = None) -> str:
        """
        プロンプトを検索結果のコンテキストで拡張します。
        
        Args:
            prompt: 元のプロンプト
            query: 検索クエリ
            n_results: 取得する結果数（省略時はデフォルト）
            filter_metadata: メタデータによるフィルター（オプション）
            score_threshold: スコア閾値（省略時はデフォルト）
            
        Returns:
            str: 拡張されたプロンプト
        """
        # デフォルト値の設定
        n_results = n_results or RAGConfiguration.get_result_count()
        score_threshold = score_threshold or RAGConfiguration.get_score_threshold()
        
        # プロンプトの拡張
        if self.agent_id:
            # エージェント固有の知識ベースを使用
            results = self.knowledge_base.search_knowledge(
                query=query,
                n_results=n_results,
                filter_metadata=filter_metadata,
                score_threshold=score_threshold
            )
        else:
            # 共有知識ベースを使用
            results = self.rag_helper.vector_db.similarity_search(
                query_text=query,
                n_results=n_results,
                collection_name=self.collection_name,
                filter_metadata=filter_metadata,
                score_threshold=score_threshold
            )
        
        # 結果がなければ元のプロンプトをそのまま返す
        if not results:
            return prompt
        
        # コンテキストの構築
        context = self._format_results_as_context(results, query)
        
        # 拡張プロンプトの作成
        enhanced_prompt = f"{prompt}\n\n次の関連情報を考慮してください：\n\n{context}"
        
        # コンテキストウィンドウサイズを考慮してプロンプトをトリミング
        max_context_len = RAGConfiguration.get_context_window()
        if len(enhanced_prompt) > max_context_len:
            logger.warning(f"プロンプトが長すぎるため、{max_context_len}文字にトリミングします")
            # プロンプトと指示部分を優先し、コンテキスト部分をトリミング
            prompt_parts = enhanced_prompt.split("次の関連情報を考慮してください：\n\n")
            if len(prompt_parts) == 2:
                base_prompt = prompt_parts[0] + "次の関連情報を考慮してください：\n\n"
                available_len = max_context_len - len(base_prompt)
                if available_len > 200:  # 最低200文字は確保
                    enhanced_prompt = base_prompt + prompt_parts[1][:available_len]
                else:
                    # コンテキストが入らない場合は元のプロンプトをトリミング
                    enhanced_prompt = prompt[:max_context_len]
        
        logger.info(f"プロンプトを {len(results)} 件の関連情報で拡張しました")
        return enhanced_prompt
    
    def create_chunked_documents(self,
                              text: str,
                              chunk_size: int = 1000,
                              chunk_overlap: int = 200,
                              metadata: Optional[Dict[str, Any]] = None,
                              source: Optional[str] = None,
                              knowledge_type: Optional[str] = None) -> List[str]:
        """
        長いテキストを適切なサイズのチャンクに分割して保存します。
        
        Args:
            text: 元のテキスト
            chunk_size: チャンクサイズ（文字数）
            chunk_overlap: チャンク間のオーバーラップ（文字数）
            metadata: メタデータ（オプション）
            source: ドキュメントの出所（オプション）
            knowledge_type: 知識の種類（オプション）
            
        Returns:
            List[str]: 保存されたドキュメントIDのリスト
        """
        # メタデータの初期化
        base_metadata = metadata or {}
        
        # チャンクに分割
        chunks = self._split_text_into_chunks(text, chunk_size, chunk_overlap)
        
        # 各チャンクを保存
        doc_ids = []
        for i, chunk in enumerate(chunks):
            # チャンク固有のメタデータを作成
            chunk_metadata = base_metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["chunk_count"] = len(chunks)
            if "title" not in chunk_metadata:
                chunk_metadata["title"] = f"Chunk {i+1} of {len(chunks)}"
            
            # チャンクを保存
            doc_id = self.add_document(
                text=chunk,
                metadata=chunk_metadata,
                source=source,
                knowledge_type=knowledge_type
            )
            doc_ids.append(doc_id)
        
        logger.info(f"テキストを {len(chunks)} チャンクに分割して保存しました")
        return doc_ids
    
    def _split_text_into_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """
        テキストをチャンクに分割します。
        
        Args:
            text: 元のテキスト
            chunk_size: チャンクサイズ（文字数）
            chunk_overlap: チャンク間のオーバーラップ（文字数）
            
        Returns:
            List[str]: チャンクのリスト
        """
        # チャンク間のオーバーラップはチャンクサイズより小さくする必要がある
        if chunk_overlap >= chunk_size:
            chunk_overlap = chunk_size // 2
        
        # 段落や文単位での分割を試みる
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            # 段落が大きすぎる場合は文で分割
            if len(para) > chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                        current_chunk += (" " if current_chunk else "") + sentence
                    else:
                        # チャンクを保存し、オーバーラップを考慮して新しいチャンクを開始
                        chunks.append(current_chunk)
                        
                        # オーバーラップ部分を新しいチャンクの開始点にする
                        if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                            current_chunk = current_chunk[-chunk_overlap:] + " " + sentence
                        else:
                            current_chunk = sentence
            else:
                # 段落全体が収まる場合
                if len(current_chunk) + len(para) + 1 <= chunk_size:
                    current_chunk += ("\n\n" if current_chunk else "") + para
                else:
                    # チャンクを保存し、オーバーラップを考慮して新しいチャンクを開始
                    chunks.append(current_chunk)
                    
                    # オーバーラップ部分を新しいチャンクの開始点にする
                    if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                        current_chunk = current_chunk[-chunk_overlap:] + "\n\n" + para
                    else:
                        current_chunk = para
        
        # 最後のチャンクを追加
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _format_results_as_text(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        検索結果をテキスト形式に整形します。
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            str: 整形されたテキスト
        """
        if not results:
            return "検索結果はありません。"
        
        text_blocks = [f"クエリ: {query}\n検索結果数: {len(results)}\n"]
        
        for i, result in enumerate(results):
            # メタデータの整形
            metadata_str = ", ".join([f"{k}: {v}" for k, v in result.get("metadata", {}).items() 
                                    if k not in ["vector", "embedding"]])
            
            # 結果ブロックの作成
            result_block = f"[{i+1}] スコア: {result['score']:.2f}"
            if metadata_str:
                result_block += f" ({metadata_str})"
            result_block += f"\n{result['document']}"
            
            text_blocks.append(result_block)
        
        return "\n\n".join(text_blocks)
    
    def _format_results_as_markdown(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        検索結果をMarkdown形式に整形します。
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            str: 整形されたMarkdown
        """
        if not results:
            return "**検索結果はありません。**"
        
        md_blocks = [f"## 検索結果: {query}\n\n**{len(results)}件の結果が見つかりました**\n"]
        
        for i, result in enumerate(results):
            # メタデータの整形
            metadata_items = []
            for k, v in result.get("metadata", {}).items():
                if k not in ["vector", "embedding"]:
                    metadata_items.append(f"**{k}**: {v}")
            
            metadata_str = " | ".join(metadata_items)
            
            # 結果ブロックの作成
            md_blocks.append(f"### {i+1}. 関連情報 (スコア: {result['score']:.2f})\n")
            if metadata_str:
                md_blocks.append(f"{metadata_str}\n")
            md_blocks.append(f"```\n{result['document']}\n```\n")
        
        return "\n".join(md_blocks)
    
    def _format_results_as_json(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        検索結果をJSON形式に整形します。
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            str: 整形されたJSON文字列
        """
        # 不要なデータを除去（ベクトルなど）
        clean_results = []
        for result in results:
            clean_result = {
                "id": result.get("id", ""),
                "score": result.get("score", 0.0),
                "document": result.get("document", ""),
                "metadata": {}
            }
            
            # メタデータをコピー（ベクトル情報は除外）
            for k, v in result.get("metadata", {}).items():
                if k not in ["vector", "embedding"]:
                    clean_result["metadata"][k] = v
            
            clean_results.append(clean_result)
        
        # 検索情報を含むJSONオブジェクトを作成
        search_results = {
            "query": query,
            "result_count": len(results),
            "results": clean_results
        }
        
        return json.dumps(search_results, ensure_ascii=False, indent=2)
    
    def _format_results_as_context(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        検索結果をコンテキスト形式（プロンプト拡張用）に整形します。
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            str: 整形されたコンテキスト
        """
        if not results:
            return ""
        
        context_blocks = []
        
        for i, result in enumerate(results):
            # メタデータからコンテキストに必要な情報を抽出
            metadata = result.get("metadata", {})
            
            # タイトルを取得（メタデータから、または生成）
            title = metadata.get("title", f"関連情報 {i+1}")
            
            # 出所情報の取得
            source = metadata.get("source", "")
            if "chunk_index" in metadata and "chunk_count" in metadata:
                source += f" (チャンク {metadata['chunk_index']+1}/{metadata['chunk_count']})"
            
            # コンテキストブロックの作成
            context_block = f"### {title}"
            if source:
                context_block += f" ({source})"
            context_block += f" - 関連度: {result['score']:.2f}\n\n{result['document']}"
            
            context_blocks.append(context_block)
        
        return "\n\n".join(context_blocks)


# シングルトンインスタンスを提供する関数
def get_rag_system(agent_id: Optional[str] = None, collection_name: Optional[str] = None) -> RAGSystem:
    """
    RAGシステムのインスタンスを取得します。
    
    Args:
        agent_id: エージェントID（特定のエージェントの知識に限定する場合）
        collection_name: コレクション名（省略時はデフォルト）
        
    Returns:
        RAGSystem: RAGシステムのインスタンス
    """
    return RAGSystem(agent_id, collection_name)


# ヘルパー関数

def search_knowledge(query: str, 
                    agent_id: Optional[str] = None, 
                    format_as: str = "text",
                    n_results: Optional[int] = None,
                    filter_metadata: Optional[Dict[str, Any]] = None) -> Union[str, List[Dict[str, Any]]]:
    """
    知識ベースを検索するヘルパー関数
    
    Args:
        query: 検索クエリ
        agent_id: エージェントID（特定のエージェントの知識に限定する場合）
        format_as: 結果の形式（"text", "markdown", "json", "context"）
        n_results: 取得する結果数
        filter_metadata: メタデータによるフィルター
        
    Returns:
        Union[str, List[Dict[str, Any]]]: 検索結果
    """
    rag = get_rag_system(agent_id)
    return rag.search(
        query=query,
        n_results=n_results,
        filter_metadata=filter_metadata,
        format_as=format_as
    )


def enhance_prompt_with_knowledge(prompt: str, 
                                query: str,
                                agent_id: Optional[str] = None,
                                n_results: Optional[int] = None,
                                filter_metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    プロンプトを知識ベースのコンテキストで拡張するヘルパー関数
    
    Args:
        prompt: 元のプロンプト
        query: 検索クエリ
        agent_id: エージェントID（特定のエージェントの知識に限定する場合）
        n_results: 取得する結果数
        filter_metadata: メタデータによるフィルター
        
    Returns:
        str: 拡張されたプロンプト
    """
    rag = get_rag_system(agent_id)
    return rag.enhance_prompt(
        prompt=prompt,
        query=query,
        n_results=n_results,
        filter_metadata=filter_metadata
    )


def add_knowledge(text: str,
                agent_id: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None,
                source: Optional[str] = None,
                knowledge_type: Optional[str] = None) -> str:
    """
    知識をベクトルDBに追加するヘルパー関数
    
    Args:
        text: 知識テキスト
        agent_id: エージェントID（特定のエージェントの知識として追加する場合）
        metadata: メタデータ
        source: 知識の出所
        knowledge_type: 知識の種類
        
    Returns:
        str: 追加された知識のID
    """
    rag = get_rag_system(agent_id)
    return rag.add_document(
        text=text,
        metadata=metadata,
        source=source,
        knowledge_type=knowledge_type
    )


def add_chunked_document(text: str,
                        agent_id: Optional[str] = None,
                        chunk_size: int = 1000,
                        chunk_overlap: int = 200,
                        metadata: Optional[Dict[str, Any]] = None,
                        source: Optional[str] = None,
                        knowledge_type: Optional[str] = None) -> List[str]:
    """
    長いテキストをチャンクに分割して知識ベースに追加するヘルパー関数
    
    Args:
        text: 元のテキスト
        agent_id: エージェントID（特定のエージェントの知識として追加する場合）
        chunk_size: チャンクサイズ（文字数）
        chunk_overlap: チャンク間のオーバーラップ（文字数）
        metadata: メタデータ
        source: 知識の出所
        knowledge_type: 知識の種類
        
    Returns:
        List[str]: 追加された知識IDのリスト
    """
    rag = get_rag_system(agent_id)
    return rag.create_chunked_documents(
        text=text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        metadata=metadata,
        source=source,
        knowledge_type=knowledge_type
    ) 