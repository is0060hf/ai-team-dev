"""
PL（プロジェクトリード/テックリード）エージェントモジュール。
システムの機能仕様、技術仕様、アーキテクチャ設計を担当します。
実装タスクをエンジニアに割り当て、コードレビューや技術的な意思決定を行います。
"""

import json
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("pl")


class TechnicalSpecGeneratorTool(Tool):
    """技術仕様生成ツール"""
    
    name = "技術仕様生成"
    description = "機能要件とUIデザイン仕様から技術仕様書を生成します。"
    
    def _run(self, requirements: str, ui_design: str = None) -> str:
        """
        技術仕様書を生成します。
        
        Args:
            requirements: 機能要件
            ui_design: UIデザイン仕様（オプション）
            
        Returns:
            str: 技術仕様書（Markdown形式）
        """
        logger.info("技術仕様生成ツールが呼び出されました。")
        
        # 技術仕様書テンプレート
        tech_spec_template = """
        # 技術仕様書

        ## 概要
        {summary}

        ## アーキテクチャ
        {architecture}

        ## データモデル
        {data_model}

        ## API仕様
        {api_spec}

        ## 技術スタック
        {tech_stack}

        ## パフォーマンス要件
        {performance}

        ## セキュリティ要件
        {security}

        ## 技術的制約事項
        {constraints}

        ## テスト要件
        {testing}
        """
        
        # 実際のプロジェクトではLLMを使用してより詳細な技術仕様を生成する
        # 現段階ではサンプルテンプレートを返す
        return tech_spec_template.format(
            summary="本ドキュメントは、〜の技術仕様を定義します。",
            architecture="## バックエンド\n- Python/Flask RESTful API\n- PostgreSQLデータベース\n\n## フロントエンド\n- React / TypeScript\n- Material UI",
            data_model="```json\n{\n  \"User\": {\n    \"id\": \"string (UUID)\",\n    \"name\": \"string\",\n    \"email\": \"string\",\n    \"created_at\": \"datetime\"\n  }\n}\n```",
            api_spec="### ユーザーAPI\n#### GET /api/users\n- 説明: ユーザー一覧の取得\n- レスポンス: 200 OK\n```json\n[\n  {\n    \"id\": \"string\",\n    \"name\": \"string\"\n  }\n]\n```",
            tech_stack="- バックエンド: Python 3.9, Flask 2.0.1, SQLAlchemy 1.4\n- データベース: PostgreSQL 13\n- フロントエンド: React 17, TypeScript 4.4, Material UI 5",
            performance="- API応答時間: 200ms以内\n- 同時接続ユーザー: 1000人以上",
            security="- JWT認証\n- HTTPS通信\n- SQLインジェクション対策\n- クロスサイトスクリプティング対策",
            constraints="- APIレート制限: 1分間に100リクエストまで\n- ストレージ容量: ユーザーあたり最大100MB",
            testing="- ユニットテスト: Pytest\n- E2Eテスト: Cypress\n- 負荷テスト: Locust"
        )


class ImplementationGuideTool(Tool):
    """実装指示生成ツール"""
    
    name = "実装指示生成"
    description = "技術仕様書に基づいて、エンジニア向けの実装指示書を生成します。"
    
    def _run(self, tech_spec: str, task_description: str) -> str:
        """
        実装指示書を生成します。
        
        Args:
            tech_spec: 技術仕様書
            task_description: タスクの説明
            
        Returns:
            str: 実装指示書（Markdown形式）
        """
        logger.info("実装指示生成ツールが呼び出されました。")
        
        # 実装指示書テンプレート
        guide_template = """
        # 実装指示書: {task_title}

        ## 概要
        {summary}

        ## 実装すべき機能
        {features}

        ## 技術的アプローチ
        {approach}

        ## コード構成
        {structure}

        ## テスト要件
        {testing}

        ## 参考資料
        {references}

        ## 注意事項
        {notes}
        """
        
        # タスク名を抽出
        task_title = task_description.split("\n")[0] if "\n" in task_description else task_description
        
        # 実際のプロジェクトではLLMを使用してより詳細な実装指示を生成する
        # 現段階ではサンプルテンプレートを返す
        return guide_template.format(
            task_title=task_title,
            summary="このタスクでは〜の機能を実装します。",
            features="1. ユーザーログイン機能\n2. ユーザープロファイル表示\n3. プロファイル編集機能",
            approach="Flask-Loginを使用してユーザー認証を実装します。ユーザー情報はPostgreSQLに保存し、SQLAlchemyを用いてアクセスします。",
            structure="```\nsrc/\n  ├── auth/\n  │   ├── __init__.py\n  │   ├── models.py\n  │   ├── routes.py\n  │   └── utils.py\n  ├── templates/\n  │   ├── login.html\n  │   └── profile.html\n  └── app.py\n```",
            testing="- ユーザー登録の正常系テスト\n- 不正な入力に対するバリデーション\n- 認証失敗のケーステスト",
            references="- [Flask-Login ドキュメント](https://flask-login.readthedocs.io/)\n- [SQLAlchemy ドキュメント](https://docs.sqlalchemy.org/)",
            notes="- パスワードは必ずハッシュ化して保存すること\n- SQLインジェクション対策を忘れずに実装すること"
        )


class CodeReviewTool(Tool):
    """コードレビューツール"""
    
    name = "コードレビュー"
    description = "提出されたコードを技術仕様書と照らし合わせてレビューし、フィードバックを提供します。"
    
    def _run(self, code: str, tech_spec: str = None) -> str:
        """
        コードレビューを実施し、フィードバックを生成します。
        
        Args:
            code: レビュー対象のコード
            tech_spec: 技術仕様書（オプション）
            
        Returns:
            str: レビュー結果（Markdown形式）
        """
        logger.info("コードレビューツールが呼び出されました。")
        
        # コードレビューテンプレート
        review_template = """
        # コードレビュー結果

        ## 概評
        {overview}

        ## 良い点
        {pros}

        ## 改善点
        {cons}

        ## セキュリティレビュー
        {security}

        ## パフォーマンスレビュー
        {performance}

        ## コーディング規約適合性
        {coding_standards}

        ## 推奨修正
        {recommendations}
        """
        
        # 実際のプロジェクトではLLMを使用してより詳細なコードレビューを生成する
        # 現段階ではサンプルテンプレートを返す
        return review_template.format(
            overview="コード全体として機能要件を満たしていますが、いくつかの改善点があります。",
            pros="- コード構造が明確で理解しやすい\n- 適切なエラーハンドリングが実装されている\n- 変数名が分かりやすい",
            cons="- 一部の関数が長すぎるため、分割を検討すべき\n- コメントが不足している箇所がある\n- 重複コードが見られる箇所がある",
            security="- SQLインジェクション対策が適切に実装されている\n- パスワードのハッシュ化が行われている\n- CSRF対策が実装されている",
            performance="- データベースクエリの最適化が必要な箇所がある\n- N+1問題が発生する可能性がある箇所を修正すべき",
            coding_standards="- PEP 8に準拠しているが、一部行長が80文字を超えている\n- 関数のドキュメント文字列が一部不足している",
            recommendations="1. `user_service.py`の`get_all_users`関数をページネーション対応にする\n2. バリデーション処理を共通関数に抽出する\n3. エラーメッセージをより具体的にする"
        )


def create_pl_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    PL（プロジェクトリード/テックリード）エージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたPLエージェント
    """
    logger.info("PLエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # PL固有のツールを追加
    pl_specific_tools = [
        TechnicalSpecGeneratorTool(),
        ImplementationGuideTool(),
        CodeReviewTool(),
    ]
    
    all_tools = tools + pl_specific_tools
    
    # PLエージェントの作成
    pl_agent = Agent(
        role="プロジェクトリード/テックリード",
        goal="システムの機能仕様、技術仕様、アーキテクチャ設計を作成する。実装タスクをエンジニアエージェントに割り当て、コードレビューや技術的な意思決定を行う。",
        backstory="""
        あなたは、深い技術知識と優れたリーダーシップスキルを併せ持つプロジェクトリード/テックリードです。
        ソフトウェアアーキテクチャ設計に精通し、複雑なシステムを効率的かつスケーラブルな形で構築する能力に長けています。
        最新の技術トレンドや開発ベストプラクティスに精通しており、技術選定や開発標準の策定を担当してきました。
        複数のエンジニアからなるチームをリードし、実装ガイダンスの提供やコードレビューを通じて高品質なソフトウェア開発を
        実現してきた実績があります。技術的な課題に対する問題解決能力が高く、PMと緊密に連携してプロジェクトの技術的側面を管理します。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=True,  # PLはエンジニアに委任可能
    )
    
    return pl_agent


def generate_technical_spec(agent: Agent, requirements: str, ui_design: str = None) -> Dict[str, Any]:
    """
    技術仕様書を生成します。
    
    Args:
        agent: PLエージェント
        requirements: 機能要件
        ui_design: UIデザイン仕様（オプション）
        
    Returns:
        Dict[str, Any]: 技術仕様書
    """
    logger.info("技術仕様書生成を開始します。")
    
    # 技術仕様書生成タスクの実行
    tech_spec_task = Task(
        description="機能要件とUIデザイン仕様に基づいて、技術仕様書を作成してください。アーキテクチャ設計、データモデル、APIインターフェース、技術スタックの選定を含めてください。",
        expected_output="技術仕様書（Markdown形式）",
        agent=agent
    )
    
    context = {"requirements": requirements}
    if ui_design:
        context["ui_design"] = ui_design
    
    tech_spec_result = agent.execute_task(tech_spec_task, context=context)
    
    logger.info("技術仕様書生成が完了しました。")
    return {"technical_spec": tech_spec_result}


def create_implementation_guide(agent: Agent, tech_spec: str, task_description: str) -> Dict[str, Any]:
    """
    実装指示書を生成します。
    
    Args:
        agent: PLエージェント
        tech_spec: 技術仕様書
        task_description: タスクの説明
        
    Returns:
        Dict[str, Any]: 実装指示書
    """
    logger.info("実装指示書生成を開始します。")
    
    # 実装指示書生成タスクの実行
    guide_task = Task(
        description="技術仕様書に基づいて、エンジニア向けの実装指示書を作成してください。タスクの詳細、実装アプローチ、コード構造、テスト要件を含めてください。",
        expected_output="実装指示書（Markdown形式）",
        agent=agent
    )
    
    guide_result = agent.execute_task(guide_task, context={
        "tech_spec": tech_spec,
        "task_description": task_description
    })
    
    logger.info("実装指示書生成が完了しました。")
    return {"implementation_guide": guide_result}


def review_code(agent: Agent, code: str, tech_spec: str = None) -> Dict[str, Any]:
    """
    コードレビューを実施します。
    
    Args:
        agent: PLエージェント
        code: レビュー対象のコード
        tech_spec: 技術仕様書（オプション）
        
    Returns:
        Dict[str, Any]: レビュー結果
    """
    logger.info("コードレビューを開始します。")
    
    # コードレビュータスクの実行
    review_task = Task(
        description="提出されたコードをレビューし、フィードバックを提供してください。コードの品質、セキュリティ、パフォーマンス、コーディング規約への準拠を評価してください。",
        expected_output="コードレビュー結果（Markdown形式）",
        agent=agent
    )
    
    context = {"code": code}
    if tech_spec:
        context["tech_spec"] = tech_spec
    
    review_result = agent.execute_task(review_task, context=context)
    
    logger.info("コードレビューが完了しました。")
    return {"code_review": review_result} 