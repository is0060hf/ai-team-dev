"""
MCP (Model Context Protocol) 会話管理モジュール。
MCP準拠の会話状態とメッセージの管理機能を提供します。
メッセージの追加、取得、変換、履歴の管理などを担当します。
"""

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
import copy

from utils.logger import get_logger
from utils.mcp_mapper import MCPRole, get_mcp_mapper

logger = get_logger("mcp_conversation")

# 会話ステータスの定義
class ConversationStatus(Enum):
    """会話の状態を表す列挙型"""
    ACTIVE = "active"           # アクティブな会話
    WAITING = "waiting"         # 応答待ち状態
    PAUSED = "paused"           # 一時停止状態
    COMPLETED = "completed"     # 完了状態
    FAILED = "failed"           # 失敗状態
    ARCHIVED = "archived"       # アーカイブ状態

@dataclass
class MCPMessage:
    """MCP形式のメッセージを表すデータクラス"""
    
    role: str                   # メッセージの役割（user, assistant, system, tool等）
    content: Union[str, Dict[str, Any]]  # メッセージ内容（文字列またはJSON対応の辞書）
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # メッセージID
    timestamp: float = field(default_factory=time.time)  # タイムスタンプ
    metadata: Dict[str, Any] = field(default_factory=dict)  # メタデータ
    
    def to_dict(self) -> Dict[str, Any]:
        """メッセージを辞書形式に変換"""
        return {
            "role": self.role,
            "content": self.content,
            "id": self.id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPMessage':
        """辞書からメッセージオブジェクトを作成"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            id=data.get("id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )
    
    def to_llm_format(self) -> Dict[str, Union[str, Dict[str, Any]]]:
        """LLMに送信するためのフォーマットに変換"""
        return {
            "role": self.role,
            "content": self.content
        }
    
    def clone(self) -> 'MCPMessage':
        """メッセージのコピーを作成"""
        return MCPMessage(
            role=self.role,
            content=copy.deepcopy(self.content),
            id=self.id,
            timestamp=self.timestamp,
            metadata=copy.deepcopy(self.metadata)
        )

@dataclass
class MCPConversation:
    """MCP準拠の会話を表すデータクラス"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 会話ID
    messages: List[MCPMessage] = field(default_factory=list)  # メッセージリスト
    metadata: Dict[str, Any] = field(default_factory=dict)  # メタデータ
    status: ConversationStatus = ConversationStatus.ACTIVE  # 会話状態
    created_at: float = field(default_factory=time.time)  # 作成日時
    updated_at: float = field(default_factory=time.time)  # 更新日時
    
    def add_message(self, message: Union[MCPMessage, Dict[str, Any]]) -> MCPMessage:
        """
        会話にメッセージを追加します。
        
        Args:
            message: 追加するメッセージ（MCPMessageまたは辞書）
            
        Returns:
            MCPMessage: 追加されたメッセージ
        """
        if not isinstance(message, MCPMessage):
            message = MCPMessage.from_dict(message)
        
        self.messages.append(message)
        self.updated_at = time.time()
        
        logger.debug(f"会話 {self.id} にメッセージが追加されました: {message.role}")
        return message
    
    def get_messages(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        会話内のすべてのメッセージを取得します。
        
        Args:
            include_metadata: メタデータを含めるかどうか
            
        Returns:
            List[Dict[str, Any]]: メッセージのリスト
        """
        if include_metadata:
            return [m.to_dict() for m in self.messages]
        else:
            return [m.to_llm_format() for m in self.messages]
    
    def get_last_message(self) -> Optional[MCPMessage]:
        """
        最後のメッセージを取得します。
        
        Returns:
            Optional[MCPMessage]: 最後のメッセージ（ない場合はNone）
        """
        if self.messages:
            return self.messages[-1]
        return None
    
    def get_llm_messages(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        LLM用フォーマットのメッセージを取得します。
        
        Args:
            include_metadata: メタデータを含めるかどうか（通常はFalse）
            
        Returns:
            List[Dict[str, Any]]: LLM用フォーマットのメッセージリスト
        """
        if include_metadata:
            return [m.to_dict() for m in self.messages]
        else:
            return [m.to_llm_format() for m in self.messages]
    
    def clear_messages(self) -> None:
        """会話のメッセージをすべて削除します。"""
        self.messages.clear()
        self.updated_at = time.time()
        logger.debug(f"会話 {self.id} のメッセージがクリアされました")
    
    def update_status(self, status: ConversationStatus) -> None:
        """
        会話の状態を更新します。
        
        Args:
            status: 新しい状態
        """
        self.status = status
        self.updated_at = time.time()
        logger.debug(f"会話 {self.id} の状態が {status.value} に更新されました")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        会話を辞書形式に変換します。
        
        Returns:
            Dict[str, Any]: 辞書形式の会話
        """
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPConversation':
        """
        辞書から会話オブジェクトを作成します。
        
        Args:
            data: 辞書形式の会話データ
            
        Returns:
            MCPConversation: 作成された会話オブジェクト
        """
        messages = [MCPMessage.from_dict(m) for m in data.get("messages", [])]
        
        try:
            status = ConversationStatus(data.get("status", "active"))
        except ValueError:
            status = ConversationStatus.ACTIVE
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            messages=messages,
            metadata=data.get("metadata", {}),
            status=status,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )
    
    def clone(self) -> 'MCPConversation':
        """
        会話のコピーを作成します。
        
        Returns:
            MCPConversation: コピーされた会話
        """
        return MCPConversation(
            id=self.id,
            messages=[m.clone() for m in self.messages],
            metadata=copy.deepcopy(self.metadata),
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

class MCPConversationManager:
    """
    MCP準拠の会話管理クラス。
    複数の会話を管理し、会話の作成・取得・保存などの機能を提供します。
    """
    
    def __init__(self):
        """会話マネージャーを初期化します。"""
        self.conversations: Dict[str, MCPConversation] = {}
        self.active_conversation_id: Optional[str] = None
        self.mcp_mapper = get_mcp_mapper()
        
        logger.info("MCPConversationManagerが初期化されました")
    
    def create_conversation(self, metadata: Dict[str, Any] = None) -> MCPConversation:
        """
        新しい会話を作成します。
        
        Args:
            metadata: 会話に関連付けるメタデータ
            
        Returns:
            MCPConversation: 作成された会話
        """
        conversation = MCPConversation(metadata=metadata or {})
        self.conversations[conversation.id] = conversation
        self.active_conversation_id = conversation.id
        
        logger.info(f"新しい会話が作成されました: {conversation.id}")
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[MCPConversation]:
        """
        IDで会話を取得します。
        
        Args:
            conversation_id: 取得する会話のID
            
        Returns:
            Optional[MCPConversation]: 会話（存在しない場合はNone）
        """
        return self.conversations.get(conversation_id)
    
    def get_active_conversation(self) -> Optional[MCPConversation]:
        """
        現在アクティブな会話を取得します。
        
        Returns:
            Optional[MCPConversation]: アクティブな会話（ない場合はNone）
        """
        if self.active_conversation_id:
            return self.conversations.get(self.active_conversation_id)
        return None
    
    def set_active_conversation(self, conversation_id: str) -> bool:
        """
        アクティブな会話を設定します。
        
        Args:
            conversation_id: アクティブにする会話のID
            
        Returns:
            bool: 成功した場合はTrue
        """
        if conversation_id in self.conversations:
            self.active_conversation_id = conversation_id
            logger.info(f"アクティブな会話が設定されました: {conversation_id}")
            return True
        
        logger.warning(f"会話が見つかりません: {conversation_id}")
        return False
    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        role: str,
        content: Union[str, Dict[str, Any]],
        metadata: Dict[str, Any] = None
    ) -> Optional[MCPMessage]:
        """
        会話にメッセージを追加します。
        
        Args:
            conversation_id: メッセージを追加する会話のID
            role: メッセージの役割
            content: メッセージ内容
            metadata: メッセージに関連付けるメタデータ
            
        Returns:
            Optional[MCPMessage]: 追加されたメッセージ（失敗時はNone）
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return None
        
        # 内部役割をMCPロールに変換
        mcp_role = self.mcp_mapper.get_mcp_role(role)
        message = MCPMessage(
            role=mcp_role.value,
            content=content,
            metadata=metadata or {}
        )
        
        return conversation.add_message(message)
    
    def add_message_to_active_conversation(
        self,
        role: str,
        content: Union[str, Dict[str, Any]],
        metadata: Dict[str, Any] = None
    ) -> Optional[MCPMessage]:
        """
        アクティブな会話にメッセージを追加します。
        
        Args:
            role: メッセージの役割
            content: メッセージ内容
            metadata: メッセージに関連付けるメタデータ
            
        Returns:
            Optional[MCPMessage]: 追加されたメッセージ（失敗時はNone）
        """
        if not self.active_conversation_id:
            logger.warning("アクティブな会話がありません")
            return None
        
        return self.add_message_to_conversation(
            self.active_conversation_id, role, content, metadata
        )
    
    def get_conversation_history(
        self,
        conversation_id: str,
        llm_format: bool = True,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        会話の履歴を取得します。
        
        Args:
            conversation_id: 履歴を取得する会話のID
            llm_format: LLM用フォーマットにするかどうか
            include_metadata: メタデータを含めるかどうか
            
        Returns:
            List[Dict[str, Any]]: 会話履歴
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return []
        
        if llm_format:
            return conversation.get_llm_messages(include_metadata)
        else:
            return [m.to_dict() for m in conversation.messages]
    
    def update_conversation_status(
        self,
        conversation_id: str,
        status: ConversationStatus
    ) -> bool:
        """
        会話の状態を更新します。
        
        Args:
            conversation_id: 更新する会話のID
            status: 新しい状態
            
        Returns:
            bool: 成功した場合はTrue
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return False
        
        conversation.update_status(status)
        return True
    
    def save_conversation(self, conversation_id: str, file_path: str) -> bool:
        """
        会話をJSONファイルに保存します。
        
        Args:
            conversation_id: 保存する会話のID
            file_path: 保存先ファイルパス
            
        Returns:
            bool: 成功した場合はTrue
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return False
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"会話が保存されました: {file_path}")
            return True
        except Exception as e:
            logger.error(f"会話の保存に失敗しました: {str(e)}")
            return False
    
    def load_conversation(self, file_path: str) -> Optional[str]:
        """
        JSONファイルから会話を読み込みます。
        
        Args:
            file_path: 読み込むファイルパス
            
        Returns:
            Optional[str]: 読み込まれた会話のID（失敗時はNone）
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            conversation = MCPConversation.from_dict(data)
            self.conversations[conversation.id] = conversation
            
            logger.info(f"会話が読み込まれました: {conversation.id}")
            return conversation.id
        except Exception as e:
            logger.error(f"会話の読み込みに失敗しました: {str(e)}")
            return None
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        会話を削除します。
        
        Args:
            conversation_id: 削除する会話のID
            
        Returns:
            bool: 成功した場合はTrue
        """
        if conversation_id not in self.conversations:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return False
        
        del self.conversations[conversation_id]
        
        if self.active_conversation_id == conversation_id:
            self.active_conversation_id = None
        
        logger.info(f"会話が削除されました: {conversation_id}")
        return True
    
    def get_all_conversations(self) -> Dict[str, MCPConversation]:
        """
        すべての会話を取得します。
        
        Returns:
            Dict[str, MCPConversation]: 会話のIDと会話オブジェクトの辞書
        """
        return self.conversations.copy()
    
    def convert_roles_in_history(
        self,
        conversation_id: str,
        to_mcp: bool = True,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        会話履歴内のロールを変換します（内部⇔MCP）。
        
        Args:
            conversation_id: 変換する会話のID
            to_mcp: Trueの場合は内部→MCP、Falseの場合はMCP→内部
            include_metadata: メタデータを含めるかどうか
            
        Returns:
            List[Dict[str, Any]]: 変換された会話履歴
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            logger.warning(f"会話が見つかりません: {conversation_id}")
            return []
        
        messages = conversation.get_messages(include_metadata)
        return self.mcp_mapper.convert_message_roles(messages, to_mcp)

# シングルトンインスタンス作成
conversation_manager = MCPConversationManager()

def get_conversation_manager() -> MCPConversationManager:
    """
    会話マネージャーのシングルトンインスタンスを取得します。
    
    Returns:
        MCPConversationManager: 会話マネージャーインスタンス
    """
    return conversation_manager 