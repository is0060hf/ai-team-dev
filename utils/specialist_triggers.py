"""
専門エージェント起動判断ロジックモジュール。
コアエージェントからの要求を分析し、専門エージェントの起動が必要かどうかを判断します。
"""

from typing import Dict, Any, Tuple, Optional, List
import re

from utils.workflow_automation import (
    SpecialistAgents, CoreAgents, TaskType,
    request_ai_architect_task, request_prompt_engineer_task, request_data_engineer_task
)
from utils.logger import get_agent_logger

logger = get_agent_logger("specialist_triggers")


class SpecialistTriggerPatterns:
    """専門エージェント起動のためのパターン定義"""
    
    # AIアーキテクト起動パターン
    AI_ARCHITECT_PATTERNS = [
        # 技術選定・設計関連
        r"アーキテクチャ(?:設計|構築|検討|選定)",
        r"システム(?:設計|構築|構成|アーキテクチャ)",
        r"技術スタック(?:選定|検討|評価)",
        r"インフラ(?:設計|構築|構成)",
        r"(?:クラウド|サーバー|ネットワーク)構成",
        r"(?:スケーラビリティ|拡張性|可用性)の(?:設計|検討|確保)",
        r"AI(?:モデル|コンポーネント)(?:の|を)?(?:設計|構築|導入|評価)",
        r"分散システム(?:設計|構築)",
        
        # 評価・調査関連
        r"技術(?:検証|評価|調査|比較)",
        r"パフォーマンス(?:評価|最適化|テスト)",
        r"AI(?:モデル|システム)の性能評価",
        r"(?:ボトルネック|パフォーマンス問題)の(?:特定|分析)",
        
        # レビュー・コンサルティング関連
        r"(?:設計|技術的|アーキテクチャ)(?:レビュー|監査|助言)",
        r"アーキテクチャの(?:改善|最適化|見直し)",
    ]
    
    # プロンプトエンジニア起動パターン
    PROMPT_ENGINEER_PATTERNS = [
        # プロンプト設計関連
        r"プロンプト(?:設計|作成|開発)",
        r"LLM(?:への|の)?(?:指示|命令)(?:設計|作成|最適化)",
        r"(?:モデル|AI|LLM)の(?:プロンプト|指示)(?:設計|最適化)",
        r"(?:ユーザー|システム)(?:プロンプト|メッセージ)(?:の設計|を作成)",
        
        # プロンプト最適化関連
        r"プロンプト(?:最適化|改善|チューニング)",
        r"(?:プロンプト|指示)の(?:精度|効率)(?:向上|改善)",
        r"(?:AI|モデル|LLM)の(?:応答|出力)(?:精度|品質)(?:向上|改善)",
        r"(?:トークン|コスト)(?:最適化|削減)",
        
        # プロンプト評価関連
        r"プロンプト(?:評価|テスト|分析)",
        r"(?:モデル|AI|LLM)(?:応答|出力)の(?:評価|分析)",
        r"プロンプト(?:バージョン|案)の(?:比較|テスト)",
        
        # 特殊プロンプト技法関連
        r"(?:チェーンオブソート|思考連鎖|CoT)",
        r"(?:Few-shot|フューショット|例示)",
        r"(?:RAG|検索拡張生成)",
        r"(?:プロンプトエンジニアリング|プロンプト工学)"
    ]
    
    # データエンジニア起動パターン
    DATA_ENGINEER_PATTERNS = [
        # データ抽出関連
        r"データ(?:抽出|取得|収集|クロール)",
        r"(?:データベース|DB)(?:から|の)?(?:抽出|クエリ|検索)",
        r"(?:API|Web)(?:から|の)?データ(?:取得|抽出)",
        r"ETL(?:処理|パイプライン|ジョブ)",
        
        # データクリーニング関連
        r"データ(?:クリーニング|洗浄|前処理)",
        r"(?:ノイズ|異常値|欠損値)(?:処理|除去|補完)",
        r"データ(?:標準化|正規化|変換)",
        
        # データ変換関連
        r"特徴量(?:エンジニアリング|抽出|生成)",
        r"データ(?:変換|加工|整形)",
        r"(?:次元削減|次元圧縮)",
        r"データ(?:エンコーディング|符号化)",
        
        # パイプライン関連
        r"(?:データ|ETL)パイプライン(?:設計|構築|実装)",
        r"データ(?:フロー|処理フロー)(?:設計|構築)",
        r"バッチ処理(?:設計|実装)",
        r"ストリーム処理(?:設計|実装)",
        
        # データストア関連
        r"(?:データベース|DB)(?:設計|構築|最適化)",
        r"(?:データモデル|スキーマ)(?:設計|構築)",
        r"(?:ベクトルDB|ベクトルデータベース)(?:構築|設計|利用)",
        r"データ(?:保存|保管|アーカイブ)(?:方法|戦略)"
    ]


class SpecialistTriggerAnalyzer:
    """
    専門エージェント起動判断を行うクラス。
    コアエージェントからの要求を分析し、専門エージェントの必要性と種類を判断します。
    """
    
    def __init__(self):
        """分析器を初期化します。"""
        # 正規表現パターンのコンパイル
        self.ai_architect_patterns = [re.compile(pattern) for pattern in SpecialistTriggerPatterns.AI_ARCHITECT_PATTERNS]
        self.prompt_engineer_patterns = [re.compile(pattern) for pattern in SpecialistTriggerPatterns.PROMPT_ENGINEER_PATTERNS]
        self.data_engineer_patterns = [re.compile(pattern) for pattern in SpecialistTriggerPatterns.DATA_ENGINEER_PATTERNS]
        
        # エージェント固有の閾値（0.0〜1.0）
        self.ai_architect_threshold = 0.6
        self.prompt_engineer_threshold = 0.6
        self.data_engineer_threshold = 0.6
    
    def analyze_request(self, request_text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], float]:
        """
        要求テキストを分析し、専門エージェントの必要性を判断します。
        
        Args:
            request_text: 分析対象の要求テキスト
            context: 追加のコンテキスト情報（オプション）
            
        Returns:
            Tuple[bool, Optional[str], float]: (専門エージェントが必要か, 必要なエージェント, 確信度)
        """
        # 各専門エージェントの信頼度スコアを計算
        ai_architect_score = self._calculate_confidence(request_text, self.ai_architect_patterns)
        prompt_engineer_score = self._calculate_confidence(request_text, self.prompt_engineer_patterns)
        data_engineer_score = self._calculate_confidence(request_text, self.data_engineer_patterns)
        
        logger.debug(f"信頼度スコア - AIアーキテクト: {ai_architect_score:.2f}, プロンプトエンジニア: {prompt_engineer_score:.2f}, データエンジニア: {data_engineer_score:.2f}")
        
        # コンテキスト情報による調整
        if context:
            ai_architect_score = self._adjust_score_by_context(ai_architect_score, context, "ai_architect")
            prompt_engineer_score = self._adjust_score_by_context(prompt_engineer_score, context, "prompt_engineer")
            data_engineer_score = self._adjust_score_by_context(data_engineer_score, context, "data_engineer")
        
        # 最高スコアと対応するエージェントを特定
        scores = [
            (SpecialistAgents.AI_ARCHITECT, ai_architect_score, self.ai_architect_threshold),
            (SpecialistAgents.PROMPT_ENGINEER, prompt_engineer_score, self.prompt_engineer_threshold),
            (SpecialistAgents.DATA_ENGINEER, data_engineer_score, self.data_engineer_threshold)
        ]
        
        # スコア順にソート
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
        top_agent, top_score, threshold = sorted_scores[0]
        
        # 閾値を超えていれば専門エージェントを起動
        if top_score >= threshold:
            logger.info(f"専門エージェント起動判断: {top_agent} (信頼度: {top_score:.2f})")
            return True, top_agent, top_score
        else:
            logger.info(f"専門エージェント起動不要 (最高信頼度: {top_score:.2f}, エージェント: {top_agent})")
            return False, None, top_score
    
    def _calculate_confidence(self, text: str, patterns: List[re.Pattern]) -> float:
        """
        テキストに対するパターンマッチングの信頼度を計算します。
        
        Args:
            text: 分析対象テキスト
            patterns: 正規表現パターンのリスト
            
        Returns:
            float: 信頼度スコア（0.0〜1.0）
        """
        if not text:
            return 0.0
        
        # パターンマッチの数をカウント
        match_count = 0
        for pattern in patterns:
            if pattern.search(text):
                match_count += 1
        
        # 単純なスコア計算：一致パターン数 / 総パターン数
        confidence = min(1.0, match_count / 3)  # 3つ以上のパターンに一致すれば最高スコア
        
        return confidence
    
    def _adjust_score_by_context(self, score: float, context: Dict[str, Any], agent_type: str) -> float:
        """
        コンテキスト情報に基づいてスコアを調整します。
        
        Args:
            score: 元のスコア
            context: コンテキスト情報
            agent_type: 専門エージェントの種類
            
        Returns:
            float: 調整後のスコア
        """
        # 明示的な専門エージェント指定があれば、スコアを大幅に調整
        if context.get("specialist_type") == agent_type:
            return max(0.8, score)  # 最低でも0.8に引き上げる
        
        # 優先度による調整
        priority_boost = {
            "ai_architect": context.get("architecture_priority", 0),
            "prompt_engineer": context.get("prompt_priority", 0),
            "data_engineer": context.get("data_priority", 0)
        }
        
        adjusted_score = score + priority_boost.get(agent_type, 0) * 0.2  # 優先度に応じて最大0.2ずつブースト
        
        return min(1.0, adjusted_score)  # 1.0を超えないように制限
    
    def get_probable_task_type(self, agent: str, request_text: str) -> TaskType:
        """
        要求テキストからタスク種別を推定します。
        
        Args:
            agent: 専門エージェント識別子
            request_text: 要求テキスト
            
        Returns:
            TaskType: 推定されたタスク種別
        """
        lower_text = request_text.lower()
        
        if agent == SpecialistAgents.AI_ARCHITECT:
            if "アーキテクチャ" in lower_text or "設計" in lower_text:
                return TaskType.ARCHITECTURE_DESIGN
            elif "技術スタック" in lower_text or "選定" in lower_text:
                return TaskType.TECH_STACK_SELECTION
            elif "評価" in lower_text or "分析" in lower_text:
                return TaskType.AI_MODEL_EVALUATION
            else:
                return TaskType.CONSULTATION
                
        elif agent == SpecialistAgents.PROMPT_ENGINEER:
            if "設計" in lower_text or "作成" in lower_text:
                return TaskType.PROMPT_DESIGN
            elif "最適化" in lower_text or "改善" in lower_text:
                return TaskType.PROMPT_OPTIMIZATION
            elif "評価" in lower_text or "テスト" in lower_text:
                return TaskType.PROMPT_EVALUATION
            else:
                return TaskType.CONSULTATION
                
        elif agent == SpecialistAgents.DATA_ENGINEER:
            if "抽出" in lower_text or "取得" in lower_text:
                return TaskType.DATA_EXTRACTION
            elif "クリーニング" in lower_text or "洗浄" in lower_text:
                return TaskType.DATA_CLEANING
            elif "変換" in lower_text or "加工" in lower_text:
                return TaskType.DATA_TRANSFORMATION
            elif "パイプライン" in lower_text or "フロー" in lower_text:
                return TaskType.DATA_PIPELINE_DESIGN
            else:
                return TaskType.CONSULTATION
        
        return TaskType.CONSULTATION


# 分析器のインスタンスを作成
trigger_analyzer = SpecialistTriggerAnalyzer()


def analyze_specialist_need(request_text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], float]:
    """
    要求テキストを分析し、専門エージェントの必要性を判断するヘルパー関数。
    
    Args:
        request_text: 分析対象の要求テキスト
        context: 追加のコンテキスト情報（オプション）
        
    Returns:
        Tuple[bool, Optional[str], float]: (専門エージェントが必要か, 必要なエージェント, 確信度)
    """
    return trigger_analyzer.analyze_request(request_text, context)


def request_specialist_if_needed(
    core_agent: str,
    request_text: str,
    context: Optional[Dict[str, Any]] = None,
    force_type: Optional[str] = None,
    priority: Optional[str] = None
) -> Optional[str]:
    """
    必要に応じて専門エージェントにタスクを依頼するヘルパー関数。
    
    Args:
        core_agent: コアエージェント識別子
        request_text: 要求テキスト
        context: 追加のコンテキスト情報（オプション）
        force_type: 強制的に起動する専門エージェント（オプション）
        priority: タスク優先度（オプション）
        
    Returns:
        Optional[str]: タスクID（専門エージェントが不要な場合はNone）
    """
    # 強制的に特定の専門エージェントを起動する場合
    if force_type:
        specialist = force_type
        needed = True
        logger.info(f"専門エージェントを強制起動: {specialist}")
    else:
        # 専門エージェントの必要性を分析
        needed, specialist, confidence = analyze_specialist_need(request_text, context)
    
    if not needed or specialist is None:
        return None
    
    # タスク種別を推定
    task_type = trigger_analyzer.get_probable_task_type(specialist, request_text)
    
    # 適切な専門エージェントにタスクを依頼
    if specialist == SpecialistAgents.AI_ARCHITECT:
        return request_ai_architect_task(
            sender=core_agent,
            task_type=task_type,
            description=request_text,
            priority=priority,
            context=context
        )
    elif specialist == SpecialistAgents.PROMPT_ENGINEER:
        return request_prompt_engineer_task(
            sender=core_agent,
            task_type=task_type,
            description=request_text,
            priority=priority,
            context=context
        )
    elif specialist == SpecialistAgents.DATA_ENGINEER:
        return request_data_engineer_task(
            sender=core_agent,
            task_type=task_type,
            description=request_text,
            priority=priority,
            context=context
        )
    
    return None 