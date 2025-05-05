"""
デザイナーエージェントモジュール。
ユーザーインターフェース（UI）およびユーザーエクスペリエンス（UX）のデザイン仕様作成を担当します。
"""

import os
import json
import tempfile
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("designer")


class UISpecGeneratorTool(Tool):
    """UI仕様生成ツール"""
    
    name = "UI仕様生成"
    description = "要件に基づいてUI仕様を生成します。画面レイアウト、コンポーネント、スタイルガイドなどを含みます。"
    
    def _run(self, requirements: str) -> str:
        """
        UI仕様を生成します。
        
        Args:
            requirements: 要件情報
            
        Returns:
            str: UI仕様（Markdown形式）
        """
        logger.info("UI仕様生成ツールが呼び出されました。")
        
        # UIスペック生成
        # 実際のプロジェクトではLLMを使用してより詳細なUI仕様を生成
        ui_spec_template = """
        # UI仕様書

        ## 概要
        {summary}

        ## 画面一覧
        {screens}

        ## コンポーネント
        {components}

        ## 画面遷移
        {transitions}

        ## スタイルガイド
        {style_guide}

        ## アクセシビリティ要件
        {accessibility}

        ## レスポンシブデザイン対応
        {responsive}
        """
        
        return ui_spec_template.format(
            summary="本ドキュメントは、〜のUI仕様を定義します。",
            screens="- ホーム画面\n- 一覧画面\n- 詳細画面\n- 設定画面",
            components="- ヘッダー\n- フッター\n- ナビゲーションメニュー\n- カード\n- ボタン\n- フォーム",
            transitions="1. ホーム画面 → 一覧画面\n2. 一覧画面 → 詳細画面\n3. ホーム画面 → 設定画面",
            style_guide="- カラーパレット: プライマリ (#007BFF), セカンダリ (#6C757D)\n- タイポグラフィ: ヘッダー (Roboto 24px), 本文 (Open Sans 16px)",
            accessibility="- コントラスト比 4.5:1 以上\n- キーボード操作サポート\n- スクリーンリーダー対応",
            responsive="- モバイル: 320px〜767px\n- タブレット: 768px〜1023px\n- デスクトップ: 1024px以上"
        )


class WireframeGeneratorTool(Tool):
    """ワイヤーフレーム生成ツール"""
    
    name = "ワイヤーフレーム生成"
    description = "UI仕様に基づいて、画面のワイヤーフレームを生成します。"
    
def create_designer_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    デザイナーエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたデザイナーエージェント
    """
    logger.info("デザイナーエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # デザイナーエージェントの作成
    designer_agent = Agent(
        role="UIUXデザイナー",
        goal="ユーザーインターフェース（UI）およびユーザーエクスペリエンス（UX）のデザイン仕様を作成する。ワイヤーフレーム、モックアップ、プロトタイプを作成し、ユーザー中心のデザインを実現する。",
        backstory="""
        あなたは、ユーザー体験を最重視するUIUXデザイナーです。美的センスと使いやすさのバランスを取りながら、
        魅力的で機能的なインターフェースを設計する能力に長けています。ユーザー調査と行動パターンの分析に基づいて、
        直感的なナビゲーションフローとインタラクションを設計します。最新のデザイントレンドとベストプラクティスに
        精通しており、アクセシビリティにも配慮したインクルーシブデザインを心がけています。技術的な制約を理解した上で、
        実装可能な現実的なデザイン案を提案することができます。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=tools,
        allow_delegation=False,  # デザイナーは基本的に下位エージェントに委任しない
    )
    
    return designer_agent 