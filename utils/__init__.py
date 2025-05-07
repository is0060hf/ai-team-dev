"""
ユーティリティパッケージの初期化モジュール。
設定とロギング機能をエクスポートします。
"""

from utils.config import config
from utils.logger import logger, get_agent_logger

# ベクトルDB関連のモジュールをエクスポート
from utils.vector_db import get_vector_db_client, AgentKnowledgeBase, RAGHelper
from utils.agent_knowledge_sharing import get_knowledge_sharing_manager, share_knowledge, query_knowledge
from utils.rag_system import get_rag_system, search_knowledge, enhance_prompt_with_knowledge, add_knowledge 