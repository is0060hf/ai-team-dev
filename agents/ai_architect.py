"""
AIアーキテクトエージェントモジュール。
システムアーキテクチャ設計、AIコンポーネント設計、技術スタック選択などのツールを持つエージェントです。
"""

import json
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("ai_architect")


class SystemArchitectureTool(Tool):
    """システムアーキテクチャ設計ツール"""
    
    name = "システムアーキテクチャ設計"
    description = "システム全体のアーキテクチャを設計します。コンポーネント構成、インフラ設計、通信方式など。"
    
    def _run(self, requirements: str, scale_requirements: str = None, security_requirements: str = None) -> str:
        """
        システムアーキテクチャを設計します。
        
        Args:
            requirements: システム要件
            scale_requirements: スケーラビリティ要件（オプション）
            security_requirements: セキュリティ要件（オプション）
            
        Returns:
            str: アーキテクチャ設計書（Markdown形式）
        """
        logger.info("システムアーキテクチャ設計ツールが呼び出されました。")
        
        # アーキテクチャ設計書テンプレート
        architecture_template = """
        # システムアーキテクチャ設計書

        ## 概要
        {summary}

        ## システム構成図
        {system_diagram}

        ## コンポーネント構成
        {components}

        ## データフロー
        {data_flow}

        ## インフラストラクチャ設計
        {infrastructure}

        ## スケーラビリティ設計
        {scalability}

        ## セキュリティ設計
        {security}

        ## 障害対策・可用性設計
        {availability}

        ## 監視・運用設計
        {monitoring}
        """
        
        # 実際のプロジェクトではLLMを使用してより詳細なアーキテクチャを生成する
        # 現段階ではサンプルテンプレートを返す
        return architecture_template.format(
            summary="本ドキュメントは、システム全体のアーキテクチャを定義します。マイクロサービスアーキテクチャを採用し、スケーラビリティ、可用性、保守性を重視した設計となっています。",
            system_diagram="```\n[ユーザー] --> [API Gateway] --> [認証サービス]\n                          |--> [コアサービス] <--> [データベース]\n                          |--> [AIサービス] <--> [モデルストア]\n                          |--> [ストレージサービス] <--> [オブジェクトストレージ]\n```",
            components="### フロントエンド\n- Webアプリケーション（React/TypeScript）\n- モバイルアプリケーション（React Native）\n\n### バックエンド\n- API Gateway（AWS API Gateway）\n- 認証サービス（Python/FastAPI）\n- コアサービス（Python/FastAPI）\n- AIサービス（Python/Flask）\n- ストレージサービス（Node.js/Express）",
            data_flow="1. ユーザーがフロントエンドからリクエストを送信\n2. API Gatewayがリクエストを受け取り、認証サービスで認証\n3. 認証後、適切なサービスにリクエストを転送\n4. サービスがデータベースやストレージとやり取り\n5. レスポンスがユーザーに返される",
            infrastructure="### クラウド環境\n- AWS（主要インフラストラクチャ）\n\n### コンピューティング\n- コンテナ環境：Kubernetes（EKS）\n- サーバーレス：AWS Lambda（一部機能）\n\n### データストア\n- プライマリデータベース：PostgreSQL（RDS）\n- キャッシュ：Redis（ElastiCache）\n- オブジェクトストレージ：S3\n- ベクトルデータベース：Pinecone",
            scalability="### 水平スケーリング\n- Kubernetesの自動スケーリング機能（HPA）を活用\n- 各マイクロサービスを独立してスケール可能に設計\n\n### データベーススケーリング\n- 読み取りレプリカの活用\n- シャーディング戦略の採用（将来的に）\n\n### キャッシュ戦略\n- Redisを用いたデータキャッシング\n- CDNによる静的コンテンツ配信",
            security="### 認証・認可\n- OAuth 2.0 / OpenID Connect\n- JWTトークンベースの認証\n\n### データ保護\n- 保存データの暗号化（AES-256）\n- 転送中のデータにはTLS 1.3\n\n### ネットワークセキュリティ\n- VPC内でのサービス間通信\n- WAFによる保護\n- レートリミッティング",
            availability="### 多重化\n- 複数のアベイラビリティゾーンにデプロイ\n- データベースの自動バックアップと障害時自動フェイルオーバー\n\n### 障害検知・回復\n- ヘルスチェックによる自動回復\n- Kubernetesのセルフヒーリング機能\n\n### DR（災害復旧）\n- 別リージョンへのバックアップと復旧手順",
            monitoring="### 監視\n- Prometheus & Grafanaによるメトリクス監視\n- ELK（Elasticsearch, Logstash, Kibana）によるログ分析\n\n### アラート\n- 異常検知によるアラート設定\n- オンコール体制\n\n### パフォーマンス監視\n- APMツールによるパフォーマンス監視\n- トレーシング（Jaeger/X-Ray）"
        )


class AIComponentDesignTool(Tool):
    """AIコンポーネント設計ツール"""
    
    name = "AIコンポーネント設計"
    description = "AIコンポーネントの詳細設計を行います。モデル選定、学習・推論パイプライン、データフローなど。"
    
    def _run(self, requirements: str, data_description: str = None, performance_requirements: str = None) -> str:
        """
        AIコンポーネントを設計します。
        
        Args:
            requirements: AI機能要件
            data_description: 扱うデータの説明（オプション）
            performance_requirements: パフォーマンス要件（オプション）
            
        Returns:
            str: AIコンポーネント設計書（Markdown形式）
        """
        logger.info("AIコンポーネント設計ツールが呼び出されました。")
        
        # AIコンポーネント設計書テンプレート
        ai_design_template = """
        # AIコンポーネント設計書

        ## 概要
        {summary}

        ## AIタスク定義
        {tasks}

        ## モデル選定
        {models}

        ## データパイプライン
        {data_pipeline}

        ## 学習パイプライン
        {training_pipeline}

        ## 推論パイプライン
        {inference_pipeline}

        ## モデルデプロイメント
        {deployment}

        ## パフォーマンス指標と監視
        {metrics}

        ## スケーラビリティ設計
        {scalability}

        ## 品質保証・テスト計画
        {qa}
        """
        
        # 実際のプロジェクトではLLMを使用してより詳細な設計を生成する
        # 現段階ではサンプルテンプレートを返す
        return ai_design_template.format(
            summary="本ドキュメントでは、システム内のAIコンポーネントの詳細設計を定義します。テキスト分析、レコメンデーション、画像認識の3つの主要AIタスクを実装します。",
            tasks="1. **テキスト分析**：ユーザーレビューの感情分析と要約\n2. **レコメンデーション**：ユーザー行動履歴に基づく商品推奨\n3. **画像認識**：アップロードされた商品画像の自動カテゴリ分類",
            models="### テキスト分析\n- 感情分析：BERT-Base Fine-tuned モデル\n- 要約：T5-Small モデル\n\n### レコメンデーション\n- Matrix Factorization + Neural Collaborative Filtering hybrid\n\n### 画像認識\n- EfficientNet-B3（転移学習による微調整）",
            data_pipeline="1. データ収集：APIを通じたデータ取得と定期バッチ処理\n2. 前処理：クリーニング、正規化、特徴抽出\n3. 拡張：テキストデータの拡張、画像データの拡張\n4. ストレージ：処理済みデータをFeature Storeに保存\n5. バージョン管理：MLflowによるデータバージョン管理",
            training_pipeline="1. データ準備：Feature Storeからの取得\n2. モデル設定：ハイパーパラメータ設定、アーキテクチャ定義\n3. 訓練実行：GPU環境での分散訓練\n4. 評価：定義された評価指標による検証\n5. モデル登録：MLflowへの登録と版管理",
            inference_pipeline="1. リアルタイム推論：\n   - API経由でのリクエスト受付\n   - モデルサービングによる推論実行\n   - 結果のキャッシング\n\n2. バッチ推論：\n   - 定期的なバッチジョブ実行\n   - 大量データに対する効率的な推論処理\n   - 結果のデータベース保存",
            deployment="### デプロイメントストラテジー\n- ブルー/グリーンデプロイメント\n- カナリアリリース\n\n### インフラストラクチャ\n- モデルサービング：TorchServe / TensorFlow Serving\n- コンテナ化：Docker\n- オーケストレーション：Kubernetes\n\n### スケジュール\n- 定期的な再訓練：週次バッチジョブ",
            metrics="### パフォーマンス指標\n- 精度（Accuracy）、適合率（Precision）、再現率（Recall）、F1スコア\n- 推論レイテンシ、スループット\n- 計算リソース使用率\n\n### 監視システム\n- モデルドリフト検出\n- 異常値アラート\n- パフォーマンスダッシュボード",
            scalability="### 水平スケーリング\n- 複数のモデルサービングインスタンス\n- ロードバランシング\n\n### リソース最適化\n- モデル量子化\n- プルーニング\n- モデル蒸留\n\n### キャッシング\n- 頻出クエリ結果のキャッシュ\n- 特徴量のキャッシュ",
            qa="### テスト戦略\n- ユニットテスト：各パイプラインコンポーネントのテスト\n- 統合テスト：エンドツーエンドパイプラインテスト\n- A/Bテスト：新モデルの段階的導入\n\n### 品質管理\n- 定期的なモデル評価\n- バイアス検出と公平性テスト\n- エッジケーステスト"
        )


class TechStackSelectorTool(Tool):
    """技術スタック選択ツール"""
    
    name = "技術スタック選択"
    description = "システム要件に基づいて最適な技術スタックを選択します。"
    
    def _run(self, requirements: str, constraints: str = None, preferences: str = None) -> str:
        """
        技術スタックを選択します。
        
        Args:
            requirements: システム要件
            constraints: 制約条件（オプション）
            preferences: 技術的な好み/方針（オプション）
            
        Returns:
            str: 技術スタック選定レポート（Markdown形式）
        """
        logger.info("技術スタック選択ツールが呼び出されました。")
        
        # 技術スタック選定レポートテンプレート
        tech_stack_template = """
        # 技術スタック選定レポート

        ## 概要
        {summary}

        ## 選定基準
        {criteria}

        ## バックエンド技術
        {backend}

        ## フロントエンド技術
        {frontend}

        ## データストレージ
        {storage}

        ## AI/ML技術
        {ai_ml}

        ## インフラストラクチャ
        {infrastructure}

        ## DevOps/CI/CD
        {devops}

        ## モニタリング・ログ
        {monitoring}

        ## セキュリティ
        {security}

        ## 代替案と比較
        {alternatives}

        ## 移行・導入計画
        {migration}
        """
        
        # 実際のプロジェクトではLLMを使用してより詳細な技術スタック選定を行う
        # 現段階ではサンプルテンプレートを返す
        return tech_stack_template.format(
            summary="本レポートでは、要件に基づいて選定された技術スタックを詳細に説明します。スケーラビリティ、パフォーマンス、開発効率、長期的な保守性を考慮して選定しています。",
            criteria="1. **スケーラビリティ**：大規模ユーザー対応能力\n2. **パフォーマンス**：低レイテンシと高スループット\n3. **開発効率**：開発速度と学習曲線\n4. **コミュニティ活性度**：サポートとエコシステム\n5. **セキュリティ**：脆弱性対応と更新頻度\n6. **コスト効率**：ライセンスと運用コスト",
            backend="### プログラミング言語\n- **Python 3.10+**：ML統合の容易さ、開発速度\n\n### APIフレームワーク\n- **FastAPI**：非同期処理、高パフォーマンス、自動ドキュメント生成\n\n### ORM\n- **SQLAlchemy**：柔軟性、多様なDBサポート\n\n### タスク処理\n- **Celery**：非同期タスク処理\n- **Redis**：メッセージブローカー",
            frontend="### フレームワーク\n- **React 18**：コンポーネントベース、広いエコシステム\n- **TypeScript**：型安全性と開発効率\n\n### 状態管理\n- **Redux Toolkit**：予測可能な状態管理\n\n### UIフレームワーク\n- **Material UI**：高品質コンポーネント、カスタマイズ性\n\n### ビルドツール\n- **Vite**：高速開発体験",
            storage="### リレーショナルデータベース\n- **PostgreSQL 14+**：JSON対応、拡張性、信頼性\n\n### キャッシュ\n- **Redis**：高速キャッシュ、パブサブ機能\n\n### オブジェクトストレージ\n- **AWS S3**：大規模ファイルストレージ\n\n### ベクトルデータベース\n- **Pinecone**：AI埋め込みの効率的な保存と検索",
            ai_ml="### ML/DLフレームワーク\n- **PyTorch**：研究から本番まで柔軟に対応\n- **Hugging Face Transformers**：NLPモデル活用\n\n### 特徴量管理\n- **Feature Store**：特徴量の一元管理\n\n### モデル管理\n- **MLflow**：実験追跡、モデル登録\n\n### モデルサービング\n- **TorchServe**：モデルのスケーラブルなデプロイ",
            infrastructure="### クラウドプロバイダー\n- **AWS**：包括的なサービス、高い信頼性\n\n### コンテナ化\n- **Docker**：一貫した環境\n- **Kubernetes（EKS）**：コンテナオーケストレーション\n\n### サーバーレス\n- **AWS Lambda**：イベント駆動処理\n\n### CDN\n- **CloudFront**：グローバル配信",
            devops="### CI/CD\n- **GitHub Actions**：コード連携の容易さ\n\n### IaC\n- **Terraform**：インフラの再現性\n\n### コンフィギュレーション管理\n- **AWS Parameter Store**：設定の一元管理\n\n### アーティファクト管理\n- **AWS ECR**：Dockerイメージ管理",
            monitoring="### メトリクス監視\n- **Prometheus**：メトリクス収集\n- **Grafana**：可視化ダッシュボード\n\n### ログ管理\n- **ELK Stack**：ログ収集・分析\n\n### APM\n- **New Relic**：アプリケーションパフォーマンス監視\n\n### アラート\n- **PagerDuty**：インシデント管理",
            security="### 認証・認可\n- **Auth0**：IDaaS、複数認証方式対応\n\n### シークレット管理\n- **AWS Secrets Manager**：機密情報管理\n\n### セキュリティスキャン\n- **SonarQube**：コード品質・脆弱性スキャン\n- **OWASP ZAP**：アプリケーションセキュリティテスト",
            alternatives="### バックエンド代替案\n- **Node.js/Express** vs **FastAPI**：\n  - FastAPIは型安全性、自動ドキュメント生成、非同期処理に優れる\n  - Node.jsはJavaScriptエコシステムとの統合が優れる\n\n### データベース代替案\n- **MongoDB** vs **PostgreSQL**：\n  - PostgreSQLはJSONB対応でスキーマ柔軟性も確保\n  - トランザクション一貫性とSQLの標準化が決め手",
            migration="### 段階的導入計画\n1. 開発環境セットアップ（2週間）\n2. CI/CD構築（1週間）\n3. コアインフラストラクチャ展開（2週間）\n4. バックエンドサービス開発（6週間）\n5. フロントエンド連携（4週間）\n6. AIコンポーネント統合（3週間）\n7. テスト・最適化（2週間）\n\n### トレーニング計画\n- 開発チーム向けFastAPI/React研修\n- インフラチーム向けKubernetes/Terraform研修"
        )


class AIModelEvaluationTool(Tool):
    """AIモデル評価ツール"""
    
    name = "AIモデル評価"
    description = "AIモデルの評価を行い、最適なモデルを選定します。"
    
    def _run(self, task_description: str, models_to_evaluate: List[str] = None, evaluation_criteria: Dict[str, float] = None) -> str:
        """
        AIモデルの評価を行います。
        
        Args:
            task_description: AIタスクの説明
            models_to_evaluate: 評価対象のモデルリスト（オプション）
            evaluation_criteria: 評価基準と重み付け（オプション）
            
        Returns:
            str: モデル評価レポート（Markdown形式）
        """
        logger.info("AIモデル評価ツールが呼び出されました。")
        
        # デフォルトのモデルリスト
        if models_to_evaluate is None:
            models_to_evaluate = [
                "BERT-Base",
                "BERT-Large",
                "RoBERTa-Base",
                "RoBERTa-Large",
                "GPT-3.5-Turbo",
                "GPT-4",
                "LLaMA 2",
                "Claude 2"
            ]
        
        # デフォルトの評価基準
        if evaluation_criteria is None:
            evaluation_criteria = {
                "精度": 0.3,
                "レイテンシ": 0.2,
                "コスト": 0.2,
                "スケーラビリティ": 0.15,
                "説明可能性": 0.15
            }
        
        # モデル評価レポートテンプレート
        evaluation_template = """
        # AIモデル評価レポート

        ## 評価対象タスク
        {task}

        ## 評価基準と重み付け
        {criteria}

        ## モデル概要
        {models_overview}

        ## 評価結果
        {results}

        ## 詳細分析
        {analysis}

        ## 推奨モデル
        {recommendation}

        ## 導入計画
        {implementation}
        """
        
        # クライアントサイトでは各モデルの評価結果を計算し、レポートを作成
        # ここではサンプルデータを基にしたテンプレートを返す
        
        # モデル評価結果の生成（サンプル）
        models_data = {}
        import random
        random.seed(42)  # 再現性のため
        
        for model in models_to_evaluate:
            models_data[model] = {
                "精度": round(random.uniform(0.7, 0.95), 2),
                "レイテンシ": round(random.uniform(50, 500), 0),  # ms
                "コスト": round(random.uniform(0.5, 10), 2),  # $単位
                "スケーラビリティ": round(random.uniform(0.6, 0.9), 2),
                "説明可能性": round(random.uniform(0.5, 0.9), 2),
            }
        
        # スコア計算（正規化して重み付け）
        scores = {}
        for model, metrics in models_data.items():
            # レイテンシとコストは低いほど良いので逆スコア化
            normalized_metrics = {
                "精度": metrics["精度"],
                "レイテンシ": 1 - (metrics["レイテンシ"] - 50) / 450,  # 50-500msを0-1に正規化して逆転
                "コスト": 1 - (metrics["コスト"] - 0.5) / 9.5,  # 0.5-10$を0-1に正規化して逆転
                "スケーラビリティ": metrics["スケーラビリティ"],
                "説明可能性": metrics["説明可能性"]
            }
            
            # 重み付けスコア計算
            weighted_score = sum([normalized_metrics[k] * v for k, v in evaluation_criteria.items()])
            scores[model] = round(weighted_score, 2)
        
        # モデルをスコア順にソート
        sorted_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_model = sorted_models[0][0]
        
        # 結果テーブルの作成
        results_table = "| モデル | 総合スコア | 精度 | レイテンシ | コスト | スケーラビリティ | 説明可能性 |\n"
        results_table += "|-------|-----------|------|------------|-------|----------------|------------|\n"
        
        for model, score in sorted_models:
            metrics = models_data[model]
            results_table += f"| {model} | **{scores[model]}** | {metrics['精度']} | {metrics['レイテンシ']}ms | ${metrics['コスト']}/K tokens | {metrics['スケーラビリティ']} | {metrics['説明可能性']} |\n"
        
        # 最適モデルの詳細分析
        best_model_analysis = f"""
        ### {best_model}
        
        **長所:**
        - 高い精度: {models_data[best_model]['精度']}の精度でタスクを完了
        - バランスの取れたパフォーマンス: レイテンシとコストのバランスが良い
        - 堅牢性: 様々な入力タイプに対して安定した結果
        
        **短所:**
        - リソース要件: 本番環境での運用には適切なスケーリング戦略が必要
        - カスタマイズ性: 特定のドメイン向けにファインチューニングが必要になる場合がある
        
        **ユースケース適合性:**
        このモデルは要求されたタスクに非常に適しており、特に{task_description}のような用途に最適です。
        """
        
        return evaluation_template.format(
            task=task_description,
            criteria="| 評価基準 | 重み付け |\n|--------|--------|\n" + "\n".join([f"| {k} | {v} |" for k, v in evaluation_criteria.items()]),
            models_overview="評価対象としたモデルは以下の通りです：\n\n" + "\n".join([f"- **{model}**" for model in models_to_evaluate]),
            results=results_table,
            analysis=best_model_analysis + "\n\n" + f"ただし、2位の{sorted_models[1][0]}も{sorted_models[1][1]}のスコアで高いパフォーマンスを示しています。コスト効率が重視される場合の代替案として検討可能です。",
            recommendation=f"総合評価の結果、**{best_model}**の採用を推奨します。\n\nこのモデルは、設定された評価基準全体でバランスの取れたパフォーマンスを示し、特に精度とレイテンシの面で優れています。",
            implementation=f"""
            ### 導入ステップ
            1. **モデルの初期設定**
               - モデルのダウンロードとセットアップ
               - 認証・APIキー設定（必要な場合）
            
            2. **統合テスト**
               - 実際のユースケースを用いた統合テスト
               - パフォーマンス検証とボトルネック特定
            
            3. **最適化**
               - 必要に応じたモデル最適化（量子化、プルーニング等）
               - バッチ処理設定の調整
            
            4. **モニタリング設定**
               - パフォーマンス監視ダッシュボード設定
               - アラート閾値設定
            
            ### タイムライン
            - 導入準備: 1週間
            - テストと最適化: 2週間
            - 本番移行: 1週間
            """
        )


def create_ai_architect_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    AIアーキテクトエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたAIアーキテクトエージェント
    """
    logger.info("AIアーキテクトエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # AIアーキテクト固有のツールを追加
    ai_architect_specific_tools = [
        SystemArchitectureTool(),
        AIComponentDesignTool(),
        TechStackSelectorTool(),
        AIModelEvaluationTool()
    ]
    
    all_tools = tools + ai_architect_specific_tools
    
    # AIアーキテクトエージェントの作成
    ai_architect_agent = Agent(
        role="AIアーキテクト",
        goal="システム全体の技術アーキテクチャ設計、特にAI/MLコンポーネントに関する技術選定、スケーラビリティ設計、セキュリティ設計を担当します。",
        backstory="""
        あなたは、AIシステムとクラウドインフラストラクチャ両方に精通した経験豊富なAIアーキテクトです。
        大規模な機械学習システムの設計・実装経験を持ち、様々なAIモデル（NLP、コンピュータビジョン、推薦システムなど）の
        本番環境への展開に関する深い知識を有しています。
        クラウドネイティブなアーキテクチャ設計、Kubernetes上でのAIワークロード管理、MLOpsパイプラインの構築など、
        最新のベストプラクティスに精通しています。
        スケーラビリティ、耐障害性、セキュリティ、コスト効率を考慮した総合的なシステム設計が得意です。
        PLやエンジニアと緊密に連携し、技術的な意思決定をリードする役割を担います。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=True,
    )
    
    return ai_architect_agent


def design_system_architecture(agent: Agent, requirements: str, scale_requirements: str = None, security_requirements: str = None) -> Dict[str, Any]:
    """
    システムアーキテクチャを設計します。
    
    Args:
        agent: AIアーキテクトエージェント
        requirements: システム要件
        scale_requirements: スケーラビリティ要件（オプション）
        security_requirements: セキュリティ要件（オプション）
        
    Returns:
        Dict[str, Any]: アーキテクチャ設計書
    """
    logger.info("システムアーキテクチャ設計を開始します。")
    
    # アーキテクチャ設計タスクの実行
    architecture_task = Task(
        description="システム全体のアーキテクチャを設計してください。コンポーネント構成、インフラ設計、通信方式などを詳細に定義してください。スケーラビリティとセキュリティを考慮した設計を行ってください。",
        expected_output="アーキテクチャ設計書（Markdown形式）",
        agent=agent
    )
    
    context = {"requirements": requirements}
    if scale_requirements:
        context["scale_requirements"] = scale_requirements
    if security_requirements:
        context["security_requirements"] = security_requirements
    
    architecture_result = agent.execute_task(architecture_task, context=context)
    
    logger.info("システムアーキテクチャ設計が完了しました。")
    return {"architecture_design": architecture_result}


def design_ai_components(agent: Agent, requirements: str, data_description: str = None, performance_requirements: str = None) -> Dict[str, Any]:
    """
    AIコンポーネントを設計します。
    
    Args:
        agent: AIアーキテクトエージェント
        requirements: AI機能要件
        data_description: 扱うデータの説明（オプション）
        performance_requirements: パフォーマンス要件（オプション）
        
    Returns:
        Dict[str, Any]: AIコンポーネント設計書
    """
    logger.info("AIコンポーネント設計を開始します。")
    
    # AIコンポーネント設計タスクの実行
    ai_design_task = Task(
        description="AIコンポーネントの詳細設計を行ってください。モデル選定、学習・推論パイプライン、データフローなどを詳細に定義してください。",
        expected_output="AIコンポーネント設計書（Markdown形式）",
        agent=agent
    )
    
    context = {"requirements": requirements}
    if data_description:
        context["data_description"] = data_description
    if performance_requirements:
        context["performance_requirements"] = performance_requirements
    
    ai_design_result = agent.execute_task(ai_design_task, context=context)
    
    logger.info("AIコンポーネント設計が完了しました。")
    return {"ai_component_design": ai_design_result}


def select_tech_stack(agent: Agent, requirements: str, constraints: str = None, preferences: str = None) -> Dict[str, Any]:
    """
    技術スタックを選択します。
    
    Args:
        agent: AIアーキテクトエージェント
        requirements: システム要件
        constraints: 制約条件（オプション）
        preferences: 技術的な好み/方針（オプション）
        
    Returns:
        Dict[str, Any]: 技術スタック選定レポート
    """
    logger.info("技術スタック選択を開始します。")
    
    # 技術スタック選択タスクの実行
    tech_stack_task = Task(
        description="システム要件に基づいて最適な技術スタックを選択してください。バックエンド、フロントエンド、データストレージ、AI/ML技術、インフラストラクチャなどの選定を行ってください。",
        expected_output="技術スタック選定レポート（Markdown形式）",
        agent=agent
    )
    
    context = {"requirements": requirements}
    if constraints:
        context["constraints"] = constraints
    if preferences:
        context["preferences"] = preferences
    
    tech_stack_result = agent.execute_task(tech_stack_task, context=context)
    
    logger.info("技術スタック選択が完了しました。")
    return {"tech_stack_selection": tech_stack_result}


def evaluate_ai_models(agent: Agent, task_description: str, models_to_evaluate: List[str] = None, evaluation_criteria: Dict[str, float] = None) -> Dict[str, Any]:
    """
    AIモデルの評価を行います。
    
    Args:
        agent: AIアーキテクトエージェント
        task_description: AIタスクの説明
        models_to_evaluate: 評価対象のモデルリスト（オプション）
        evaluation_criteria: 評価基準と重み付け（オプション）
        
    Returns:
        Dict[str, Any]: モデル評価レポート
    """
    logger.info("AIモデル評価を開始します。")
    
    # AIモデル評価タスクの実行
    evaluation_task = Task(
        description="AIタスクに最適なモデルを評価・選定してください。各モデルの精度、レイテンシ、コスト、スケーラビリティ、説明可能性などを評価し、最適なモデルを推奨してください。",
        expected_output="モデル評価レポート（Markdown形式）",
        agent=agent
    )
    
    context = {"task_description": task_description}
    if models_to_evaluate:
        context["models_to_evaluate"] = models_to_evaluate
    if evaluation_criteria:
        context["evaluation_criteria"] = evaluation_criteria
    
    evaluation_result = agent.execute_task(evaluation_task, context=context)
    
    logger.info("AIモデル評価が完了しました。")
    return {"model_evaluation": evaluation_result} 