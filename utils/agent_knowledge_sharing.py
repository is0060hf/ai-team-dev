"""
エージェント間知識共有プロトコル実装モジュール。
ベクトルデータベースを活用して専門知識の共有と検索を行います。
"""

from typing import Dict, List, Any, Optional, Union, Tuple
import time
import uuid

from utils.agent_communication import (
    AgentMessage, TaskType, TaskPriority, TaskStatus,
    send_task_request, send_task_response,
    dispatcher, MessageDispatcher
)
from utils.vector_db import (
    get_vector_db_client, AgentKnowledgeBase, RAGHelper
)
from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, task_registry
)
from utils.logger import get_agent_logger

logger = get_agent_logger("agent_knowledge_sharing")


class KnowledgeType:
    """知識の種類を定義する定数クラス"""
    ARCHITECTURE = "architecture"  # アーキテクチャ関連知識
    PROMPT = "prompt"              # プロンプト関連知識
    DATA = "data"                  # データ関連知識
    CODE = "code"                  # コード関連知識
    TASK_RESULT = "task_result"    # タスク結果
    CONVERSATION = "conversation"  # 会話内容
    DOCUMENT = "document"          # ドキュメント
    GENERAL = "general"            # 一般的な知識


class KnowledgeSource:
    """知識の出所を定義する定数クラス"""
    TASK_RESULT = "task_result"    # タスク実行結果
    CONVERSATION = "conversation"  # エージェント間の会話
    DOCUMENT = "document"          # 外部ドキュメント
    GENERATED = "generated"        # 自動生成された知識
    USER_INPUT = "user_input"      # ユーザー入力
    EXPERT_AGENT = "expert_agent"  # 専門エージェントからの知識
    CORE_AGENT = "core_agent"      # コアエージェントからの知識


class KnowledgeSharingMessage(AgentMessage):
    """知識共有メッセージクラス"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        knowledge_text: str,
        knowledge_type: str,
        source: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        """
        知識共有メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID（'all'の場合は全エージェントへ）
            knowledge_text: 共有する知識のテキスト
            knowledge_type: 知識の種類（KnowledgeTypeクラスの定数）
            source: 知識の出所（KnowledgeSourceクラスの定数）
            importance: 知識の重要度（0.0〜1.0）
            metadata: 追加のメタデータ（オプション）
            request_id: リクエストID（省略時は自動生成）
        """
        content = {
            "knowledge_text": knowledge_text,
            "knowledge_type": knowledge_type,
            "source": source,
            "importance": importance,
            "metadata": metadata or {},
            "timestamp": int(time.time())
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="knowledge_sharing",
            content=content,
            request_id=request_id
        )


class KnowledgeQueryMessage(AgentMessage):
    """知識クエリメッセージクラス"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        query: str,
        knowledge_types: Optional[List[str]] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        """
        知識クエリメッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            query: 検索クエリ
            knowledge_types: 取得したい知識の種類のリスト（省略時は全種類）
            filter_metadata: メタデータによるフィルター条件（オプション）
            request_id: リクエストID（省略時は自動生成）
        """
        content = {
            "query": query,
            "knowledge_types": knowledge_types or [],
            "filter_metadata": filter_metadata or {},
            "timestamp": int(time.time())
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="knowledge_query",
            content=content,
            request_id=request_id
        )


class KnowledgeResponseMessage(AgentMessage):
    """知識応答メッセージクラス"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        request_id: str,
        results: List[Dict[str, Any]],
        query: str
    ):
        """
        知識応答メッセージを初期化します。
        
        Args:
            sender: 送信元エージェントID
            recipient: 受信先エージェントID
            request_id: 知識クエリのリクエストID
            results: 検索結果のリスト
            query: 元のクエリ
        """
        content = {
            "results": results,
            "query": query,
            "result_count": len(results),
            "timestamp": int(time.time())
        }
        
        super().__init__(
            sender=sender,
            recipient=recipient,
            message_type="knowledge_response",
            content=content,
            reference_id=request_id
        )


class AgentKnowledgeSharingManager:
    """
    エージェント知識共有マネージャークラス
    ベクトルDBを使用したエージェント間知識共有を管理します。
    """
    
    _instance = None
    
    def __new__(cls):
        """シングルトンパターンによるインスタンス生成"""
        if cls._instance is None:
            cls._instance = super(AgentKnowledgeSharingManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """マネージャーを初期化します"""
        # 各エージェントの知識ベースを保持する辞書
        self.knowledge_bases = {}
        
        # RAGヘルパー
        self.rag_helper = RAGHelper()
        
        # デフォルトコレクション名
        self.collection_name = "agent_knowledge"
        
        # メッセージハンドラーの登録
        self._register_handlers()
        
        logger.info("エージェント知識共有マネージャーを初期化しました")
    
    def _register_handlers(self) -> None:
        """メッセージハンドラーを登録します"""
        # コアエージェント用ハンドラー
        for agent_id in [CoreAgents.PDM, CoreAgents.PM, CoreAgents.DESIGNER, 
                        CoreAgents.PL, CoreAgents.ENGINEER, CoreAgents.TESTER]:
            dispatcher.register_handler(agent_id, "knowledge_sharing", self._handle_knowledge_sharing)
            dispatcher.register_handler(agent_id, "knowledge_query", self._handle_knowledge_query)
        
        # 専門エージェント用ハンドラー
        for agent_id in [SpecialistAgents.AI_ARCHITECT, SpecialistAgents.PROMPT_ENGINEER, 
                        SpecialistAgents.DATA_ENGINEER]:
            dispatcher.register_handler(agent_id, "knowledge_sharing", self._handle_knowledge_sharing)
            dispatcher.register_handler(agent_id, "knowledge_query", self._handle_knowledge_query)
    
    def _get_agent_knowledge_base(self, agent_id: str) -> AgentKnowledgeBase:
        """
        エージェントの知識ベースを取得します。なければ作成します。
        
        Args:
            agent_id: エージェントID
            
        Returns:
            AgentKnowledgeBase: エージェントの知識ベース
        """
        if agent_id not in self.knowledge_bases:
            self.knowledge_bases[agent_id] = AgentKnowledgeBase(
                agent_id=agent_id,
                collection_name=self.collection_name
            )
            logger.info(f"エージェント {agent_id} の知識ベースを作成しました")
        
        return self.knowledge_bases[agent_id]
    
    def _handle_knowledge_sharing(self, message: KnowledgeSharingMessage) -> None:
        """
        知識共有メッセージを処理するハンドラー
        
        Args:
            message: 知識共有メッセージ
        """
        sender = message.sender
        recipient = message.recipient
        knowledge_text = message.content.get("knowledge_text", "")
        knowledge_type = message.content.get("knowledge_type", KnowledgeType.GENERAL)
        source = message.content.get("source", KnowledgeSource.GENERATED)
        metadata = message.content.get("metadata", {})
        
        logger.info(f"知識共有メッセージを受信: {sender} -> {recipient}, タイプ: {knowledge_type}")
        
        # メタデータに送信元を記録
        metadata["sender"] = sender
        
        if recipient == "all":
            # 全エージェントへの知識共有の場合は各エージェントの知識ベースに追加
            # ただし現実的にはベクトルDBに1回だけ保存し、メタデータでエージェントごとにフィルタリングする方が効率的
            for agent_id in self.knowledge_bases.keys():
                self._store_knowledge_for_agent(agent_id, knowledge_text, knowledge_type, source, metadata)
        else:
            # 特定のエージェントへの知識共有
            self._store_knowledge_for_agent(recipient, knowledge_text, knowledge_type, source, metadata)
    
    def _store_knowledge_for_agent(self, agent_id: str, knowledge_text: str, 
                                 knowledge_type: str, source: str, 
                                 metadata: Dict[str, Any]) -> str:
        """
        エージェントの知識ベースに知識を保存します。
        
        Args:
            agent_id: エージェントID
            knowledge_text: 知識テキスト
            knowledge_type: 知識タイプ
            source: 知識ソース
            metadata: メタデータ
            
        Returns:
            str: 保存された知識のID
        """
        knowledge_base = self._get_agent_knowledge_base(agent_id)
        knowledge_id = knowledge_base.add_knowledge(
            text=knowledge_text,
            source=source,
            knowledge_type=knowledge_type,
            metadata=metadata
        )
        
        logger.info(f"エージェント {agent_id} の知識ベースに知識 {knowledge_id} を保存しました")
        return knowledge_id
    
    def _handle_knowledge_query(self, message: KnowledgeQueryMessage) -> None:
        """
        知識クエリメッセージを処理するハンドラー
        
        Args:
            message: 知識クエリメッセージ
        """
        sender = message.sender
        recipient = message.recipient
        query = message.content.get("query", "")
        knowledge_types = message.content.get("knowledge_types", [])
        filter_metadata = message.content.get("filter_metadata", {})
        
        logger.info(f"知識クエリメッセージを受信: {sender} -> {recipient}, クエリ: {query[:30]}...")
        
        # 知識タイプでフィルタリングする場合
        if knowledge_types:
            if "knowledge_type" not in filter_metadata:
                filter_metadata["knowledge_type"] = {"$in": knowledge_types}
        
        # 受信者の知識ベースを検索
        knowledge_base = self._get_agent_knowledge_base(recipient)
        results = knowledge_base.search_knowledge(
            query=query,
            n_results=5,
            filter_metadata=filter_metadata,
            score_threshold=0.6  # スコアの閾値
        )
        
        # 検索結果を送信者に返す
        response = KnowledgeResponseMessage(
            sender=recipient,
            recipient=sender,
            request_id=message.request_id,
            results=results,
            query=query
        )
        
        dispatcher.send_message(response)
        logger.info(f"知識クエリ応答を送信: {recipient} -> {sender}, 結果数: {len(results)}")


# マネージャーのシングルトンインスタンスを取得する関数
def get_knowledge_sharing_manager() -> AgentKnowledgeSharingManager:
    """
    知識共有マネージャーのシングルトンインスタンスを取得します。
    
    Returns:
        AgentKnowledgeSharingManager: マネージャーインスタンス
    """
    return AgentKnowledgeSharingManager()


# 以下はヘルパー関数群

def share_knowledge(
    sender: str,
    recipient: str,
    knowledge_text: str,
    knowledge_type: str,
    source: str,
    importance: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    知識を共有するヘルパー関数
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID（'all'の場合は全エージェントへ）
        knowledge_text: 共有する知識のテキスト
        knowledge_type: 知識の種類（KnowledgeTypeクラスの定数）
        source: 知識の出所（KnowledgeSourceクラスの定数）
        importance: 知識の重要度（0.0〜1.0）
        metadata: 追加のメタデータ（オプション）
        
    Returns:
        str: メッセージのリクエストID
    """
    message = KnowledgeSharingMessage(
        sender=sender,
        recipient=recipient,
        knowledge_text=knowledge_text,
        knowledge_type=knowledge_type,
        source=source,
        importance=importance,
        metadata=metadata
    )
    
    dispatcher.send_message(message)
    logger.info(f"知識共有メッセージを送信: {sender} -> {recipient}, タイプ: {knowledge_type}")
    
    return message.request_id


def query_knowledge(
    sender: str,
    recipient: str,
    query: str,
    knowledge_types: Optional[List[str]] = None,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    知識を検索するヘルパー関数
    
    Args:
        sender: 送信元エージェントID
        recipient: 受信先エージェントID
        query: 検索クエリ
        knowledge_types: 取得したい知識の種類のリスト（省略時は全種類）
        filter_metadata: メタデータによるフィルター条件（オプション）
        
    Returns:
        str: メッセージのリクエストID
    """
    message = KnowledgeQueryMessage(
        sender=sender,
        recipient=recipient,
        query=query,
        knowledge_types=knowledge_types,
        filter_metadata=filter_metadata
    )
    
    dispatcher.send_message(message)
    logger.info(f"知識クエリメッセージを送信: {sender} -> {recipient}, クエリ: {query[:30]}...")
    
    return message.request_id


def get_agent_knowledge_base(agent_id: str) -> AgentKnowledgeBase:
    """
    エージェントの知識ベースを直接取得するヘルパー関数
    
    Args:
        agent_id: エージェントID
        
    Returns:
        AgentKnowledgeBase: エージェントの知識ベース
    """
    manager = get_knowledge_sharing_manager()
    return manager._get_agent_knowledge_base(agent_id)


def enhance_prompt_with_agent_knowledge(
    agent_id: str,
    prompt: str,
    query: str,
    knowledge_types: Optional[List[str]] = None,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    エージェントの知識ベースから関連情報を取得し、プロンプトを強化するヘルパー関数
    
    Args:
        agent_id: エージェントID
        prompt: 元のプロンプト
        query: 検索クエリ
        knowledge_types: 取得したい知識の種類のリスト（省略時は全種類）
        filter_metadata: メタデータによるフィルター条件（オプション）
        
    Returns:
        str: 強化されたプロンプト
    """
    knowledge_base = get_agent_knowledge_base(agent_id)
    
    # 知識タイプでフィルタリングする場合
    filter_dict = filter_metadata or {}
    if knowledge_types:
        filter_dict["knowledge_type"] = {"$in": knowledge_types}
    
    # 関連知識を検索
    results = knowledge_base.search_knowledge(
        query=query,
        n_results=3,
        filter_metadata=filter_dict,
        score_threshold=0.65
    )
    
    # 関連情報がなければ元のプロンプトをそのまま返す
    if not results:
        return prompt
    
    # 関連情報を抽出
    context_docs = []
    for result in results:
        metadata_str = ", ".join([f"{k}: {v}" for k, v in result["metadata"].items() 
                                if k not in ["agent_id", "timestamp"]])
        context_docs.append(f"--- 関連情報 (スコア: {result['score']:.2f}, {metadata_str}) ---\n{result['document']}")
    
    # コンテキストを結合
    context_text = "\n\n".join(context_docs)
    
    # プロンプトにコンテキストを追加
    enhanced_prompt = f"{prompt}\n\n次の関連知識を考慮してください：\n\n{context_text}"
    
    logger.info(f"エージェント {agent_id} の知識ベースから {len(results)} 件の関連情報でプロンプトを強化しました")
    return enhanced_prompt


# 初期化（モジュールインポート時に自動実行）
knowledge_sharing_manager = get_knowledge_sharing_manager() 