"""
MCP (Model Context Protocol) マッパーモジュール。
内部エージェント役割とMCPで定義される標準ロールの間のマッピングを提供します。
これにより、外部MCPシステムとの互換性を確保します。
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple

from utils.logger import get_logger
from utils.agent_communication import TaskType

logger = get_logger("mcp_mapper")

# MCP標準ロールの定義
class MCPRole(Enum):
    """MCPプロトコルで定義される標準的なエージェント役割"""
    
    # 基本ロール
    USER = "user"                      # ユーザー
    SYSTEM = "system"                  # システム（メタ情報、制約等を提供）
    ASSISTANT = "assistant"            # アシスタント（主要なAI）
    
    # 拡張ロール
    FUNCTION = "function"              # 関数（特定の機能を提供）
    TOOL = "tool"                      # ツール（特定のタスクを実行）
    DATA_SOURCE = "data_source"        # データソース（情報提供）
    OBSERVER = "observer"              # オブザーバー（監視・ログ記録）
    VALIDATOR = "validator"            # バリデーター（結果検証）
    COORDINATOR = "coordinator"        # コーディネーター（タスク割り当て）
    
    # 特殊ロール
    KNOWLEDGE_BASE = "knowledge_base"  # 知識ベース（参照情報）
    GUI = "gui"                        # GUIエージェント（表示・入力）
    CRITIC = "critic"                  # 批評家（評価・改善提案）
    EXECUTOR = "executor"              # 実行者（コード実行など）
    PLANNER = "planner"                # 計画立案者
    MEMORY = "memory"                  # メモリ管理者（履歴・記憶）
    
    # 未定義のロールはCUSTOMとして扱う
    CUSTOM = "custom"                  # カスタムロール

# 内部エージェント役割とMCPロールのマッピング
AGENT_TO_MCP_ROLE_MAP = {
    # コアエージェント
    "プロダクトオーナー": MCPRole.USER,
    "PdM": MCPRole.PLANNER,
    "PM": MCPRole.COORDINATOR,
    "デザイナー": MCPRole.ASSISTANT,
    "PL": MCPRole.PLANNER,
    "エンジニア": MCPRole.EXECUTOR,
    "テスター": MCPRole.VALIDATOR,
    
    # 専門エージェント
    "AIアーキテクト": MCPRole.PLANNER,
    "プロンプトエンジニア": MCPRole.ASSISTANT,
    "データエンジニア": MCPRole.DATA_SOURCE,
    
    # その他
    "system": MCPRole.SYSTEM,
    "user": MCPRole.USER,
    "assistant": MCPRole.ASSISTANT,
    "mcp_gateway": MCPRole.SYSTEM,
    "mcp_system": MCPRole.SYSTEM
}

# MCPロールと内部タスク種別のマッピング
MCP_ROLE_TO_TASK_TYPES: Dict[MCPRole, List[TaskType]] = {
    MCPRole.PLANNER: [
        TaskType.ARCHITECTURE_DESIGN,
        TaskType.TECH_STACK_SELECTION,
        TaskType.DATA_PIPELINE_DESIGN,
        TaskType.KNOWLEDGE_BASE_DESIGN
    ],
    MCPRole.ASSISTANT: [
        TaskType.PROMPT_DESIGN,
        TaskType.PROMPT_OPTIMIZATION,
        TaskType.PROMPT_EVALUATION,
        TaskType.CONSULTATION
    ],
    MCPRole.VALIDATOR: [
        TaskType.REVIEW,
        TaskType.AI_MODEL_EVALUATION
    ],
    MCPRole.DATA_SOURCE: [
        TaskType.DATA_EXTRACTION,
        TaskType.DATA_CLEANING,
        TaskType.DATA_TRANSFORMATION,
        TaskType.EMBEDDING_GENERATION,
        TaskType.VECTOR_DB_SETUP,
        TaskType.VECTOR_DB_OPTIMIZATION
    ],
    MCPRole.EXECUTOR: [
        TaskType.SIMILARITY_SEARCH,
        TaskType.RAG_IMPLEMENTATION
    ]
}

class MCPMapper:
    """
    エージェント役割とMCPロール間のマッピングを管理するクラス。
    タスク種別に基づく役割推論機能も提供します。
    """
    
    def __init__(self):
        """MCPマッパーを初期化します。"""
        self.agent_to_mcp_map = AGENT_TO_MCP_ROLE_MAP.copy()
        self.mcp_role_to_tasks = MCP_ROLE_TO_TASK_TYPES.copy()
        self.custom_mappings: Dict[str, MCPRole] = {}
        
        logger.info("MCPマッパーが初期化されました")
    
    def add_mapping(self, agent_role: str, mcp_role: MCPRole) -> None:
        """
        新しいエージェント役割とMCPロールのマッピングを追加します。
        
        Args:
            agent_role: 内部エージェント役割名
            mcp_role: 対応するMCPロール
        """
        self.agent_to_mcp_map[agent_role] = mcp_role
        self.custom_mappings[agent_role] = mcp_role
        logger.info(f"マッピングが追加されました: {agent_role} -> {mcp_role.value}")
    
    def remove_mapping(self, agent_role: str) -> bool:
        """
        エージェント役割のマッピングを削除します。
        
        Args:
            agent_role: 削除する内部エージェント役割名
            
        Returns:
            bool: 削除成功の場合はTrue
        """
        if agent_role in self.custom_mappings:
            del self.custom_mappings[agent_role]
            
            # 基本マッピングは残しつつ、カスタムマッピングを削除
            if agent_role not in AGENT_TO_MCP_ROLE_MAP:
                del self.agent_to_mcp_map[agent_role]
            else:
                # 基本マッピングに戻す
                self.agent_to_mcp_map[agent_role] = AGENT_TO_MCP_ROLE_MAP[agent_role]
            
            logger.info(f"マッピングが削除されました: {agent_role}")
            return True
        
        logger.warning(f"マッピングが見つかりません: {agent_role}")
        return False
    
    def get_mcp_role(self, agent_role: str) -> MCPRole:
        """
        内部エージェント役割に対応するMCPロールを取得します。
        
        Args:
            agent_role: 内部エージェント役割名
            
        Returns:
            MCPRole: 対応するMCPロール（未定義の場合はCUSTOM）
        """
        return self.agent_to_mcp_map.get(agent_role, MCPRole.CUSTOM)
    
    def get_agent_roles(self, mcp_role: MCPRole) -> List[str]:
        """
        MCPロールに対応するすべての内部エージェント役割を取得します。
        
        Args:
            mcp_role: MCPロール
            
        Returns:
            List[str]: 対応する内部エージェント役割のリスト
        """
        return [
            agent_role for agent_role, role in self.agent_to_mcp_map.items()
            if role == mcp_role
        ]
    
    def infer_mcp_role_from_task(self, task_type: TaskType) -> MCPRole:
        """
        タスク種別からMCPロールを推論します。
        
        Args:
            task_type: タスク種別
            
        Returns:
            MCPRole: 推論されたMCPロール（対応するものがない場合はCUSTOM）
        """
        for role, task_types in self.mcp_role_to_tasks.items():
            if task_type in task_types:
                return role
        
        # デフォルトはASSISTANT
        return MCPRole.ASSISTANT
    
    def infer_agent_roles_from_task(self, task_type: TaskType) -> List[str]:
        """
        タスク種別から適切な内部エージェント役割を推論します。
        
        Args:
            task_type: タスク種別
            
        Returns:
            List[str]: 推論された内部エージェント役割のリスト
        """
        mcp_role = self.infer_mcp_role_from_task(task_type)
        return self.get_agent_roles(mcp_role)
    
    def add_task_type_to_role(self, mcp_role: MCPRole, task_type: TaskType) -> None:
        """
        MCPロールに対してタスク種別を関連付けます。
        
        Args:
            mcp_role: MCPロール
            task_type: 関連付けるタスク種別
        """
        if mcp_role not in self.mcp_role_to_tasks:
            self.mcp_role_to_tasks[mcp_role] = []
        
        if task_type not in self.mcp_role_to_tasks[mcp_role]:
            self.mcp_role_to_tasks[mcp_role].append(task_type)
            logger.info(f"タスク種別がロールに関連付けられました: {task_type.value} -> {mcp_role.value}")
    
    def remove_task_type_from_role(self, mcp_role: MCPRole, task_type: TaskType) -> bool:
        """
        MCPロールからタスク種別の関連付けを削除します。
        
        Args:
            mcp_role: MCPロール
            task_type: 削除するタスク種別
            
        Returns:
            bool: 削除成功の場合はTrue
        """
        if mcp_role in self.mcp_role_to_tasks and task_type in self.mcp_role_to_tasks[mcp_role]:
            self.mcp_role_to_tasks[mcp_role].remove(task_type)
            logger.info(f"タスク種別の関連付けが削除されました: {task_type.value} -> {mcp_role.value}")
            return True
        
        logger.warning(f"タスク種別の関連付けが見つかりません: {task_type.value} -> {mcp_role.value}")
        return False
    
    def get_task_types_for_role(self, mcp_role: MCPRole) -> List[TaskType]:
        """
        MCPロールに関連付けられているタスク種別を取得します。
        
        Args:
            mcp_role: MCPロール
            
        Returns:
            List[TaskType]: 関連付けられているタスク種別のリスト
        """
        return self.mcp_role_to_tasks.get(mcp_role, [])
    
    def get_roles_for_task_type(self, task_type: TaskType) -> List[MCPRole]:
        """
        タスク種別に関連付けられているMCPロールを取得します。
        
        Args:
            task_type: タスク種別
            
        Returns:
            List[MCPRole]: 関連付けられているMCPロールのリスト
        """
        roles = []
        for role, tasks in self.mcp_role_to_tasks.items():
            if task_type in tasks:
                roles.append(role)
        return roles
    
    def convert_message_roles(self, messages: List[Dict[str, Any]], to_mcp: bool = True) -> List[Dict[str, Any]]:
        """
        メッセージリスト内のロール表現を変換します。
        
        Args:
            messages: 変換するメッセージのリスト
            to_mcp: Trueの場合は内部→MCP、Falseの場合はMCP→内部に変換
            
        Returns:
            List[Dict[str, Any]]: 変換後のメッセージリスト
        """
        result = []
        
        for msg in messages:
            new_msg = msg.copy()
            
            if "role" in new_msg:
                role = new_msg["role"]
                
                if to_mcp:
                    # 内部役割 → MCPロール
                    mcp_role = self.get_mcp_role(role)
                    new_msg["role"] = mcp_role.value
                else:
                    # MCPロール → 内部役割（最初に見つかった対応する役割を使用）
                    try:
                        mcp_role = MCPRole(role)
                        agent_roles = self.get_agent_roles(mcp_role)
                        if agent_roles:
                            new_msg["role"] = agent_roles[0]
                    except ValueError:
                        # 不明なMCPロールはそのまま使用
                        pass
            
            result.append(new_msg)
        
        return result

# シングルトンインスタンス作成
mcp_mapper = MCPMapper()

def get_mcp_mapper() -> MCPMapper:
    """
    MCPマッパーのシングルトンインスタンスを取得します。
    
    Returns:
        MCPMapper: マッパーインスタンス
    """
    return mcp_mapper 