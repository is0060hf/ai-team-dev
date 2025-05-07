"""
ベクトルデータベース接続ユーティリティモジュール。
エンベディングモデルと連携し、ベクトル検索や類似性検索機能を提供します。
"""

import os
import uuid
import time
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from utils.logger import get_agent_logger

logger = get_agent_logger("vector_db")


class VectorDBConfig:
    """
    ベクトルデータベースの設定クラス
    """
    # デフォルト設定
    DEFAULT_DB_DIRECTORY = "storage/vector_db"
    DEFAULT_COLLECTION_NAME = "agent_knowledge"
    DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # sentence-transformersのデフォルトモデル

    @staticmethod
    def get_db_directory() -> str:
        """
        ベクトルDBのディレクトリパスを取得します。
        環境変数またはデフォルト値から設定されます。
        
        Returns:
            str: ディレクトリパス
        """
        return os.environ.get("VECTOR_DB_DIR", VectorDBConfig.DEFAULT_DB_DIRECTORY)
    
    @staticmethod
    def get_collection_name() -> str:
        """
        デフォルトのコレクション名を取得します。
        環境変数またはデフォルト値から設定されます。
        
        Returns:
            str: コレクション名
        """
        return os.environ.get("VECTOR_DB_COLLECTION", VectorDBConfig.DEFAULT_COLLECTION_NAME)
    
    @staticmethod
    def get_embedding_model() -> str:
        """
        エンベディングモデル名を取得します。
        環境変数またはデフォルト値から設定されます。
        
        Returns:
            str: エンベディングモデル名
        """
        return os.environ.get("VECTOR_DB_EMBEDDING_MODEL", VectorDBConfig.DEFAULT_EMBEDDING_MODEL)


class VectorDBClient:
    """
    ベクトルデータベースクライアントクラス
    ChromaDBを使用したベクトルデータベースの操作を提供します。
    """
    _instance = None

    def __new__(cls):
        """シングルトンパターンによるインスタンス生成"""
        if cls._instance is None:
            cls._instance = super(VectorDBClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """クライアントを初期化します"""
        # DBディレクトリがなければ作成
        db_directory = VectorDBConfig.get_db_directory()
        os.makedirs(db_directory, exist_ok=True)
        
        # ChromaDBクライアントの初期化
        self.client = chromadb.PersistentClient(
            path=db_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # 埋め込み関数の設定
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=VectorDBConfig.get_embedding_model()
        )
        
        # デフォルトコレクションの取得（または作成）
        self._get_or_create_collection(VectorDBConfig.get_collection_name())
        
        logger.info(f"VectorDBClient initialized with db_directory: {db_directory}")
    
    def _get_or_create_collection(self, collection_name: str) -> chromadb.Collection:
        """
        コレクションを取得または作成します。
        
        Args:
            collection_name: コレクション名
            
        Returns:
            chromadb.Collection: コレクションオブジェクト
        """
        try:
            # 既存のコレクションがあれば取得
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Retrieved existing collection: {collection_name}")
        except ValueError:
            # 存在しない場合は新規作成
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Created new collection: {collection_name}")
        
        return collection
    
    def get_collection(self, collection_name: Optional[str] = None) -> chromadb.Collection:
        """
        コレクションを取得します。
        
        Args:
            collection_name: コレクション名（省略時はデフォルト）
            
        Returns:
            chromadb.Collection: コレクションオブジェクト
        """
        if collection_name is None:
            collection_name = VectorDBConfig.get_collection_name()
        
        return self._get_or_create_collection(collection_name)
    
    def add_documents(self, 
                      documents: List[str], 
                      metadatas: Optional[List[Dict[str, Any]]] = None,
                      ids: Optional[List[str]] = None,
                      collection_name: Optional[str] = None) -> List[str]:
        """
        ドキュメントをベクトルDBに追加します。
        
        Args:
            documents: ドキュメントテキストのリスト
            metadatas: 各ドキュメントのメタデータのリスト（オプション）
            ids: 各ドキュメントのID（省略時は自動生成）
            collection_name: コレクション名（省略時はデフォルト）
            
        Returns:
            List[str]: 追加されたドキュメントのIDリスト
        """
        collection = self.get_collection(collection_name)
        
        # IDが指定されていなければ生成
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # メタデータが指定されていなければ空のディクショナリで初期化
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        # ドキュメントを追加
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(documents)} documents to collection {collection.name}")
        return ids
    
    def query(self,
              query_text: str,
              n_results: int = 5,
              collection_name: Optional[str] = None,
              filter_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        クエリテキストに類似したドキュメントを検索します。
        
        Args:
            query_text: 検索クエリテキスト
            n_results: 返す結果の最大数
            collection_name: コレクション名（省略時はデフォルト）
            filter_metadata: メタデータによるフィルター条件（オプション）
            
        Returns:
            Dict[str, Any]: 検索結果（ids, documents, metadatas, distances）
        """
        collection = self.get_collection(collection_name)
        
        # 検索を実行
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=filter_metadata
        )
        
        logger.info(f"Queried '{query_text[:30]}...' and found {len(results['ids'][0])} results")
        return results
    
    def similarity_search(self, 
                        query_text: str,
                        n_results: int = 5,
                        collection_name: Optional[str] = None,
                        filter_metadata: Optional[Dict[str, Any]] = None,
                        score_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        類似性検索を行い、結果を整形して返します。
        
        Args:
            query_text: 検索クエリテキスト
            n_results: 返す結果の最大数
            collection_name: コレクション名（省略時はデフォルト）
            filter_metadata: メタデータによるフィルター条件（オプション）
            score_threshold: スコアの閾値（このスコア以上の結果のみ返す、オプション）
            
        Returns:
            List[Dict[str, Any]]: 検索結果のリスト [{"id": ..., "document": ..., "metadata": ..., "score": ...}, ...]
        """
        # クエリを実行
        results = self.query(query_text, n_results, collection_name, filter_metadata)
        
        # 結果を整形
        formatted_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # ドキュメント、メタデータ、スコアを取得
                document = results["documents"][0][i]
                metadata = results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {}
                # ChromaDBは距離を返すので、類似度スコアに変換（1 - 距離）
                score = 1.0 - results["distances"][0][i] if results["distances"] and results["distances"][0] else 0.0
                
                # スコアの閾値がある場合はフィルタリング
                if score_threshold is not None and score < score_threshold:
                    continue
                
                formatted_results.append({
                    "id": doc_id,
                    "document": document,
                    "metadata": metadata,
                    "score": score
                })
        
        return formatted_results
    
    def update_document(self,
                        doc_id: str,
                        document: str,
                        metadata: Optional[Dict[str, Any]] = None,
                        collection_name: Optional[str] = None) -> None:
        """
        ドキュメントを更新します。
        
        Args:
            doc_id: 更新するドキュメントのID
            document: 新しいドキュメントテキスト
            metadata: 新しいメタデータ（オプション）
            collection_name: コレクション名（省略時はデフォルト）
        """
        collection = self.get_collection(collection_name)
        
        update_args = {
            "ids": [doc_id],
            "documents": [document]
        }
        
        if metadata:
            update_args["metadatas"] = [metadata]
        
        collection.update(**update_args)
        logger.info(f"Updated document {doc_id} in collection {collection.name}")
    
    def delete_documents(self,
                        ids: List[str],
                        collection_name: Optional[str] = None) -> None:
        """
        ドキュメントを削除します。
        
        Args:
            ids: 削除するドキュメントのIDリスト
            collection_name: コレクション名（省略時はデフォルト）
        """
        collection = self.get_collection(collection_name)
        collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} documents from collection {collection.name}")
    
    def get_collection_stats(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        コレクションの統計情報を取得します。
        
        Args:
            collection_name: コレクション名（省略時はデフォルト）
            
        Returns:
            Dict[str, Any]: 統計情報
        """
        collection = self.get_collection(collection_name)
        
        # ドキュメント数を取得
        count = collection.count()
        
        # コレクションに含まれる最初の数件のドキュメントを取得
        sample_results = collection.peek(limit=3)
        
        # 統計情報を返す
        stats = {
            "name": collection.name,
            "count": count,
            "sample_ids": sample_results["ids"] if "ids" in sample_results else []
        }
        
        logger.info(f"Collection stats - {collection.name}: {count} documents")
        return stats


# クライアントのシングルトンインスタンスを取得する関数
def get_vector_db_client() -> VectorDBClient:
    """
    ベクトルDBクライアントのシングルトンインスタンスを取得します。
    
    Returns:
        VectorDBClient: クライアントインスタンス
    """
    return VectorDBClient()


class AgentKnowledgeBase:
    """
    エージェント知識ベースクラス
    専門知識のベクトル化と検索機能を提供します。
    """
    
    def __init__(self, agent_id: str, collection_name: Optional[str] = None):
        """
        エージェント知識ベースを初期化します。
        
        Args:
            agent_id: エージェントID
            collection_name: 使用するコレクション名（省略時はデフォルト）
        """
        self.agent_id = agent_id
        self.collection_name = collection_name or VectorDBConfig.get_collection_name()
        self.vector_db = get_vector_db_client()
        logger.info(f"Agent knowledge base initialized for agent {agent_id}")
    
    def add_knowledge(self, 
                     text: str, 
                     source: str, 
                     knowledge_type: str,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        知識をベクトルDBに追加します。
        
        Args:
            text: 知識のテキスト
            source: 知識の出所（例: "task_result", "conversation", "document"）
            knowledge_type: 知識の種類（例: "architecture", "prompt", "data"）
            metadata: 追加のメタデータ（オプション）
            
        Returns:
            str: 追加された知識のID
        """
        # メタデータの構築
        full_metadata = {
            "agent_id": self.agent_id,
            "source": source,
            "knowledge_type": knowledge_type,
            "timestamp": str(int(time.time()))
        }
        
        # 追加のメタデータがあれば統合
        if metadata:
            full_metadata.update(metadata)
        
        # ベクトルDBに追加
        ids = self.vector_db.add_documents(
            documents=[text],
            metadatas=[full_metadata],
            collection_name=self.collection_name
        )
        
        logger.info(f"Added knowledge from {source} of type {knowledge_type} for agent {self.agent_id}")
        return ids[0]
    
    def search_knowledge(self, 
                        query: str, 
                        n_results: int = 5,
                        filter_metadata: Optional[Dict[str, Any]] = None,
                        score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        知識ベースから関連情報を検索します。
        
        Args:
            query: 検索クエリ
            n_results: 返す結果の最大数
            filter_metadata: メタデータによるフィルター条件（オプション）
            score_threshold: スコアの閾値（このスコア以上の結果のみ返す）
            
        Returns:
            List[Dict[str, Any]]: 検索結果のリスト
        """
        # エージェント固有のフィルターを構築
        agent_filter = {"agent_id": self.agent_id}
        
        # 追加のフィルターがあれば統合
        if filter_metadata:
            agent_filter.update(filter_metadata)
        
        # 検索を実行
        results = self.vector_db.similarity_search(
            query_text=query,
            n_results=n_results,
            collection_name=self.collection_name,
            filter_metadata=agent_filter,
            score_threshold=score_threshold
        )
        
        logger.info(f"Searched knowledge for query '{query[:30]}...' and found {len(results)} results")
        return results


class RAGHelper:
    """
    検索拡張生成（RAG）ヘルパークラス
    コンテキスト最適化や関連情報自動取得機能を提供します。
    """
    
    def __init__(self, vector_db: Optional[VectorDBClient] = None):
        """
        RAGヘルパーを初期化します。
        
        Args:
            vector_db: ベクトルDBクライアント（省略時は自動取得）
        """
        self.vector_db = vector_db or get_vector_db_client()
        logger.info("RAG helper initialized")
    
    def enhance_prompt_with_context(self, 
                                   prompt: str, 
                                   query: str,
                                   collection_name: Optional[str] = None,
                                   n_results: int = 3,
                                   filter_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        プロンプトを関連コンテキストで拡張します。
        
        Args:
            prompt: 元のプロンプトテンプレート
            query: 検索クエリ
            collection_name: コレクション名（省略時はデフォルト）
            n_results: 取得する関連ドキュメントの数
            filter_metadata: メタデータによるフィルター条件（オプション）
            
        Returns:
            str: コンテキスト拡張されたプロンプト
        """
        # 関連ドキュメントを検索
        results = self.vector_db.similarity_search(
            query_text=query,
            n_results=n_results,
            collection_name=collection_name,
            filter_metadata=filter_metadata
        )
        
        # 関連情報がなければ元のプロンプトをそのまま返す
        if not results:
            return prompt
        
        # 関連情報を抽出
        context_docs = []
        for result in results:
            context_docs.append(f"--- 関連情報 (スコア: {result['score']:.2f}) ---\n{result['document']}")
        
        # コンテキストを結合
        context_text = "\n\n".join(context_docs)
        
        # プロンプトにコンテキストを追加
        enhanced_prompt = f"{prompt}\n\n次の関連情報を考慮してください：\n\n{context_text}"
        
        logger.info(f"Enhanced prompt with {len(results)} context documents")
        return enhanced_prompt
    
    def retrieve_relevant_information(self,
                                     query: str,
                                     collection_name: Optional[str] = None,
                                     n_results: int = 5,
                                     filter_metadata: Optional[Dict[str, Any]] = None,
                                     format_as_text: bool = True) -> Union[str, List[Dict[str, Any]]]:
        """
        クエリに関連する情報を取得します。
        
        Args:
            query: 検索クエリ
            collection_name: コレクション名（省略時はデフォルト）
            n_results: 取得する関連ドキュメントの数
            filter_metadata: メタデータによるフィルター条件（オプション）
            format_as_text: テキスト形式で整形するかどうか
            
        Returns:
            Union[str, List[Dict[str, Any]]]: 関連情報（テキスト形式または辞書のリスト）
        """
        # 関連ドキュメントを検索
        results = self.vector_db.similarity_search(
            query_text=query,
            n_results=n_results,
            collection_name=collection_name,
            filter_metadata=filter_metadata
        )
        
        if not format_as_text:
            return results
        
        # テキスト形式で整形
        if not results:
            return "関連情報は見つかりませんでした。"
        
        text_sections = []
        for i, result in enumerate(results):
            metadata_str = ", ".join([f"{k}: {v}" for k, v in result["metadata"].items() if k != "agent_id"])
            text_sections.append(f"[{i+1}] スコア: {result['score']:.2f}, メタデータ: {metadata_str}\n{result['document']}")
        
        return "\n\n".join(text_sections)
    
    def optimize_query(self, original_query: str) -> str:
        """
        検索クエリを最適化します。
        
        Args:
            original_query: 元のクエリ
            
        Returns:
            str: 最適化されたクエリ
        """
        # ここでは単純なクエリの正規化を行う
        # より高度な実装では、LLMを使用してクエリを拡張・精緻化することも可能
        optimized_query = original_query.strip()
        
        # クエリが短すぎる場合は調整
        if len(optimized_query.split()) < 3:
            optimized_query = f"詳細情報: {optimized_query}"
        
        logger.info(f"Optimized query: '{original_query}' -> '{optimized_query}'")
        return optimized_query


# モジュールレベルでクライアントを初期化
vector_db_client = get_vector_db_client() 