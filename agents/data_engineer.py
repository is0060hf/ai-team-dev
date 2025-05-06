"""
データエンジニアエージェントモジュール。
AIモデルの学習やシステム開発に必要なデータの収集、クレンジング、前処理、管理を行います。
データパイプラインを構築・運用します。
"""

import json
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("data_engineer")


class DataExtractionTool(Tool):
    """データ抽出ツール"""
    
    name = "データ抽出"
    description = "様々なソースからデータを抽出します。"
    
    def _run(self, source_type: str, source_path: str, query: str = None) -> str:
        """
        データを抽出します。
        
        Args:
            source_type: データソースの種類（例: "csv", "json", "database", "api"）
            source_path: データソースのパスまたはURL
            query: 抽出条件やクエリ（オプション）
            
        Returns:
            str: 抽出されたデータの概要
        """
        logger.info(f"データ抽出ツールが呼び出されました: {source_type} - {source_path}")
        
        # 実際のプロジェクトでは、実際のデータ抽出処理を実装
        # 現段階では処理のシミュレーション結果を返す
        
        result = {
            "source_type": source_type,
            "source_path": source_path,
            "query": query,
            "status": "成功",
            "records_count": 1000,  # サンプル
            "columns": ["id", "name", "value", "timestamp"],  # サンプル
            "sample_data": [
                {"id": 1, "name": "サンプル1", "value": 100, "timestamp": "2023-01-01T12:00:00"},
                {"id": 2, "name": "サンプル2", "value": 200, "timestamp": "2023-01-02T12:00:00"},
            ]
        }
        
        return f"""
        # データ抽出結果

        ## ソース情報
        - タイプ: {source_type}
        - パス: {source_path}
        - クエリ: {query if query else "なし"}

        ## 抽出結果概要
        - ステータス: {result['status']}
        - レコード数: {result['records_count']} 件
        - カラム: {', '.join(result['columns'])}

        ## サンプルデータ
        ```json
        {json.dumps(result['sample_data'], indent=2, ensure_ascii=False)}
        ```
        """


class DataCleaningTool(Tool):
    """データクリーニングツール"""
    
    name = "データクリーニング"
    description = "データのクリーニングと前処理を行います。"
    
    def _run(self, data_description: str, cleaning_operations: List[str]) -> str:
        """
        データのクリーニングと前処理を行います。
        
        Args:
            data_description: データの説明
            cleaning_operations: 実行するクリーニング操作のリスト
            
        Returns:
            str: クリーニング結果の概要
        """
        logger.info("データクリーニングツールが呼び出されました。")
        
        # 実際のプロジェクトでは、実際のデータクリーニング処理を実装
        # 現段階では処理のシミュレーション結果を返す
        
        # 各クリーニング操作の結果を生成
        operation_results = []
        for operation in cleaning_operations:
            if "欠損値" in operation:
                result = {
                    "operation": operation,
                    "affected_rows": 120,
                    "details": "欠損値を列の平均値で補完しました。"
                }
            elif "重複" in operation:
                result = {
                    "operation": operation,
                    "affected_rows": 45,
                    "details": "重複レコードを削除しました。"
                }
            elif "外れ値" in operation:
                result = {
                    "operation": operation,
                    "affected_rows": 23,
                    "details": "IQRに基づく外れ値検出を実施し、検出された外れ値を上下限値で置換しました。"
                }
            elif "正規化" in operation:
                result = {
                    "operation": operation,
                    "affected_columns": ["value1", "value2"],
                    "details": "指定された数値列に対してMin-Max正規化を適用しました。"
                }
            elif "型変換" in operation:
                result = {
                    "operation": operation,
                    "affected_columns": ["date_column"],
                    "details": "文字列の日付をdatetime型に変換しました。"
                }
            else:
                result = {
                    "operation": operation,
                    "status": "実行済み",
                    "details": "指定された操作を実行しました。"
                }
            operation_results.append(result)
        
        # クリーニング前後のデータ統計の生成（サンプル）
        before_stats = {
            "total_rows": 1000,
            "missing_values": 150,
            "duplicate_rows": 45,
            "outliers": 30
        }
        
        after_stats = {
            "total_rows": 955,  # 重複削除後
            "missing_values": 30,  # 一部未処理の欠損値
            "duplicate_rows": 0,
            "outliers": 7  # 一部未処理の外れ値
        }
        
        # 結果レポートの生成
        return f"""
        # データクリーニング結果

        ## 処理対象データ
        {data_description}

        ## クリーニング操作の結果
        {self._format_operation_results(operation_results)}

        ## データ統計（クリーニング前後）
        
        | 項目 | クリーニング前 | クリーニング後 |
        |------|--------------|--------------|
        | レコード総数 | {before_stats['total_rows']} | {after_stats['total_rows']} |
        | 欠損値 | {before_stats['missing_values']} | {after_stats['missing_values']} |
        | 重複レコード | {before_stats['duplicate_rows']} | {after_stats['duplicate_rows']} |
        | 外れ値 | {before_stats['outliers']} | {after_stats['outliers']} |

        ## 注意事項
        - クリーニング後もデータに一部欠損値や外れ値が残っています。
        - これらは適切なビジネスルールがなく、自動処理が難しい部分です。
        - 必要に応じて、個別に対応を検討してください。
        """
    
    def _format_operation_results(self, results: List[Dict[str, Any]]) -> str:
        """操作結果をフォーマットします。"""
        formatted = ""
        for i, result in enumerate(results, 1):
            formatted += f"### 操作 {i}: {result['operation']}\n"
            if "affected_rows" in result:
                formatted += f"- 影響を受けた行数: {result['affected_rows']}\n"
            if "affected_columns" in result:
                formatted += f"- 影響を受けた列: {', '.join(result['affected_columns'])}\n"
            formatted += f"- 詳細: {result['details']}\n\n"
        return formatted


class DataTransformationTool(Tool):
    """データ変換ツール"""
    
    name = "データ変換"
    description = "機械学習や分析のためのデータ変換を行います。"
    
    def _run(self, data_description: str, transformation_type: str, transformation_params: Dict[str, Any] = None) -> str:
        """
        データの変換を行います。
        
        Args:
            data_description: データの説明
            transformation_type: 変換の種類（例: "特徴量エンジニアリング", "次元削減", "エンコーディング"）
            transformation_params: 変換のパラメータ（オプション）
            
        Returns:
            str: 変換結果の概要
        """
        logger.info(f"データ変換ツールが呼び出されました: {transformation_type}")
        
        # パラメータのデフォルト値設定
        if transformation_params is None:
            transformation_params = {}
        
        # 変換の種類に応じた処理（サンプル）
        if transformation_type == "特徴量エンジニアリング":
            return self._feature_engineering(data_description, transformation_params)
        elif transformation_type == "次元削減":
            return self._dimension_reduction(data_description, transformation_params)
        elif transformation_type == "エンコーディング":
            return self._encoding(data_description, transformation_params)
        else:
            return f"""
            # データ変換結果
            
            ## 変換情報
            - 対象データ: {data_description}
            - 変換タイプ: {transformation_type}
            - パラメータ: {json.dumps(transformation_params, ensure_ascii=False)}
            
            ## 注意
            指定された変換タイプ「{transformation_type}」は標準サポートされていません。
            カスタム変換として処理しました。
            
            ## 結果概要
            - 変換前の特徴数: 10
            - 変換後の特徴数: 12
            - 変換にかかった時間: 1.2秒
            """
    
    def _feature_engineering(self, data_description: str, params: Dict[str, Any]) -> str:
        """特徴量エンジニアリングを行います。"""
        operations = params.get("operations", ["統計量計算", "多項式特徴量", "時間特徴量"])
        
        # 特徴量エンジニアリングの結果（サンプル）
        new_features = []
        if "統計量計算" in operations:
            new_features.extend(["値_平均", "値_標準偏差", "値_最大", "値_最小"])
        if "多項式特徴量" in operations:
            new_features.extend(["値1_二乗", "値1*値2", "値2_二乗"])
        if "時間特徴量" in operations:
            new_features.extend(["日付_年", "日付_月", "日付_日", "日付_曜日", "日付_時間"])
        
        return f"""
        # 特徴量エンジニアリング結果
        
        ## 処理対象データ
        {data_description}
        
        ## 実行された操作
        {', '.join(operations)}
        
        ## 生成された特徴量
        - 元の特徴数: {params.get('original_features_count', 8)}
        - 生成された新しい特徴:
          {', '.join(new_features)}
        - 最終的な特徴数: {params.get('original_features_count', 8) + len(new_features)}
        
        ## 注意事項
        - 特徴量間の相関を確認し、必要に応じて高相関の特徴を除外することを検討してください。
        - 特徴量の重要度分析を行い、モデルのパフォーマンスへの影響を評価することをお勧めします。
        """
    
    def _dimension_reduction(self, data_description: str, params: Dict[str, Any]) -> str:
        """次元削減を行います。"""
        method = params.get("method", "PCA")
        components = params.get("components", 3)
        
        # 次元削減の結果（サンプル）
        variance_explained = [0.45, 0.25, 0.15]  # サンプル値
        total_variance = sum(variance_explained)
        
        return f"""
        # 次元削減結果
        
        ## 処理対象データ
        {data_description}
        
        ## 次元削減の詳細
        - 手法: {method}
        - 元の次元数: {params.get('original_dimensions', 10)}
        - 削減後の次元数: {components}
        
        ## 結果分析
        - 説明された分散: {total_variance:.2f} ({total_variance*100:.1f}%)
        - 各成分の寄与率:
          - 成分1: {variance_explained[0]:.2f} ({variance_explained[0]*100:.1f}%)
          - 成分2: {variance_explained[1]:.2f} ({variance_explained[1]*100:.1f}%)
          - 成分3: {variance_explained[2]:.2f} ({variance_explained[2]*100:.1f}%)
        
        ## 推奨事項
        - {'次元数の選択は適切です。' if total_variance >= 0.8 else '説明された分散が低いため、次元数を増やすことを検討してください。'}
        - 次元削減後のデータを可視化して、クラスタリングパターンを確認することをお勧めします。
        """
    
    def _encoding(self, data_description: str, params: Dict[str, Any]) -> str:
        """カテゴリ変数のエンコーディングを行います。"""
        method = params.get("method", "one-hot")
        target_columns = params.get("target_columns", ["カテゴリ1", "カテゴリ2", "カテゴリ3"])
        
        # エンコーディングの結果（サンプル）
        if method == "one-hot":
            increase_in_columns = sum([params.get(f"{col}_unique_values", 5) for col in target_columns])
            encoding_detail = "- 各カテゴリ値ごとに新しい二値特徴量（0/1）を作成"
        elif method == "label":
            increase_in_columns = 0
            encoding_detail = "- 各カテゴリに整数値を割り当て（順序なし）"
        elif method == "target":
            increase_in_columns = 0
            encoding_detail = "- 各カテゴリ値をターゲット変数の平均値で置換"
        else:
            increase_in_columns = len(target_columns)
            encoding_detail = "- カスタムエンコーディング手法を適用"
        
        return f"""
        # エンコーディング結果
        
        ## 処理対象データ
        {data_description}
        
        ## エンコーディングの詳細
        - 手法: {method}エンコーディング
        - 対象カラム: {', '.join(target_columns)}
        - エンコーディング方法: {encoding_detail}
        
        ## 結果概要
        - 元のカラム数: {params.get('original_columns_count', 15)}
        - エンコーディング後の追加カラム数: {increase_in_columns}
        - 最終的なカラム数: {params.get('original_columns_count', 15) + increase_in_columns}
        
        ## 注意事項
        - エンコーディング後のデータを使用する前に、特徴のスケーリングを検討してください。
        - 高次元データになる場合は、次元削減の適用を検討してください。
        """


class DataPipelineTool(Tool):
    """データパイプライン設計ツール"""
    
    name = "データパイプライン設計"
    description = "データの収集から処理、保存までのパイプラインを設計します。"
    
    def _run(self, requirements: str, data_sources: List[str] = None, processing_steps: List[str] = None) -> str:
        """
        データパイプラインを設計します。
        
        Args:
            requirements: パイプラインの要件
            data_sources: データソースのリスト（オプション）
            processing_steps: 処理ステップのリスト（オプション）
            
        Returns:
            str: パイプライン設計書
        """
        logger.info("データパイプライン設計ツールが呼び出されました。")
        
        # デフォルト値の設定
        if data_sources is None:
            data_sources = ["APIデータ", "データベース", "ファイルストレージ"]
        
        if processing_steps is None:
            processing_steps = ["データ抽出", "データクリーニング", "データ変換", "データ保存"]
        
        # パイプライン設計書テンプレート
        pipeline_template = """
        # データパイプライン設計書

        ## 概要
        {summary}

        ## 要件
        {requirements}

        ## データソース
        {data_sources_section}

        ## 処理ステップ
        {processing_steps_section}

        ## データフロー図
        {data_flow}

        ## 技術スタック
        {tech_stack}

        ## スケジュールと実行
        {scheduling}

        ## モニタリングと障害対応
        {monitoring}

        ## セキュリティとデータガバナンス
        {governance}
        """
        
        # 各セクションの内容生成
        summary = "このデータパイプラインは、複数のソースからデータを収集し、クリーニング、変換、保存までの一連の処理を自動化します。"
        
        # データソースセクション
        data_sources_section = ""
        for i, source in enumerate(data_sources, 1):
            if source == "APIデータ":
                data_sources_section += f"### {i}. {source}\n- REST APIからJSONデータを定期的に取得\n- APIキー認証を使用した安全なアクセス\n- レート制限を考慮した取得間隔の調整\n\n"
            elif source == "データベース":
                data_sources_section += f"### {i}. {source}\n- 運用データベースからの増分データ抽出\n- 低負荷時間帯のバッチ抽出\n- 接続プール管理による効率的なリソース利用\n\n"
            elif source == "ファイルストレージ":
                data_sources_section += f"### {i}. {source}\n- クラウドストレージからのCSV/Excelファイル取得\n- ファイル命名規則に基づく自動分類\n- 取得済みファイルの追跡管理\n\n"
            else:
                data_sources_section += f"### {i}. {source}\n- カスタムデータソースからのデータ取得\n- ソース固有の最適抽出方法の適用\n\n"
        
        # 処理ステップセクション
        processing_steps_section = ""
        for i, step in enumerate(processing_steps, 1):
            if step == "データ抽出":
                processing_steps_section += f"### {i}. {step}\n- 各データソースに対する専用コネクタの活用\n- 増分抽出とメタデータ管理\n- 抽出履歴と統計情報の記録\n\n"
            elif step == "データクリーニング":
                processing_steps_section += f"### {i}. {step}\n- 欠損値の検出と処理（補完/除外）\n- 重複レコードの特定と排除\n- 外れ値の検出と処理\n- データ型の検証と変換\n\n"
            elif step == "データ変換":
                processing_steps_section += f"### {i}. {step}\n- スキーマの正規化と統一\n- 特徴量エンジニアリング（派生変数の作成）\n- 次元削減と特徴選択\n- カテゴリ変数のエンコーディング\n\n"
            elif step == "データ保存":
                processing_steps_section += f"### {i}. {step}\n- データウェアハウスへの書き込み\n- パーティショニングとインデックス最適化\n- メタデータ保存とバージョン管理\n- アーカイブポリシーの適用\n\n"
            else:
                processing_steps_section += f"### {i}. {step}\n- カスタム処理ステップの実行\n- 処理結果の検証と品質チェック\n\n"
        
        # その他のセクション
        data_flow = """
        ```
        [データソース] --> [抽出] --> [ステージングエリア]
                                        |
                                        v
        [データウェアハウス] <-- [保存] <-- [変換] <-- [クリーニング]
                |
                v
        [分析/ML] --> [モニタリング]
        ```
        """
        
        tech_stack = """
        ### データ収集
        - Apache Airflow: ワークフロー管理とスケジューリング
        - カスタムコネクタ: APIデータ、DBデータの抽出
        
        ### データ処理
        - Apache Spark: 大規模データ処理
        - Pandas: 中小規模データの処理
        - Scikit-learn: 特徴量エンジニアリングと変換
        
        ### データストレージ
        - Amazon S3: 生データとステージングデータ
        - Amazon Redshift: データウェアハウス
        - PostgreSQL: メタデータと結果データ
        
        ### モニタリング
        - Prometheus/Grafana: パイプライン監視
        - Great Expectations: データ品質テスト
        """
        
        scheduling = """
        ### スケジュール
        - APIデータ取得: 1時間ごと
        - データベース抽出: 日次（深夜1時）
        - ファイル取得: 日次（朝6時）
        - フルパイプライン実行: 日次（朝7時）
        
        ### 依存関係
        - 各ソースからの抽出が完了次第、クリーニングと変換を実行
        - すべての変換が完了後、データウェアハウスへの保存を実行
        
        ### リトライ戦略
        - 最大3回のリトライ（指数バックオフ）
        - リトライ失敗後は管理者通知と手動介入
        """
        
        monitoring = """
        ### モニタリング指標
        - パイプライン実行状態と所要時間
        - 処理レコード数とエラー率
        - リソース使用率（CPU、メモリ、ディスク）
        
        ### アラート
        - パイプライン失敗時の即時通知
        - データ品質問題の検出時の警告
        - リソース使用率の閾値超過通知
        
        ### 障害復旧
        - 自動リトライによる一時的エラーの回復
        - チェックポイントからの再開機能
        - バックアップデータからの復元手順
        """
        
        governance = """
        ### セキュリティ
        - 保存データと転送データの暗号化
        - 最小権限アクセスコントロール
        - 認証情報の安全な管理（シークレットマネージャ）
        
        ### データガバナンス
        - データカタログによるメタデータ管理
        - データ系統（lineage）の追跡
        - コンプライアンス要件に基づくデータ保持ポリシー
        
        ### プライバシー
        - 機密データの識別と保護
        - データマスキングと匿名化
        - アクセスログと監査証跡
        """
        
        return pipeline_template.format(
            summary=summary,
            requirements=requirements,
            data_sources_section=data_sources_section,
            processing_steps_section=processing_steps_section,
            data_flow=data_flow,
            tech_stack=tech_stack,
            scheduling=scheduling,
            monitoring=monitoring,
            governance=governance
        )


def create_data_engineer_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    データエンジニアエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたデータエンジニアエージェント
    """
    logger.info("データエンジニアエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # データエンジニア固有のツールを追加
    data_engineer_specific_tools = [
        DataExtractionTool(),
        DataCleaningTool(),
        DataTransformationTool(),
        DataPipelineTool()
    ]
    
    all_tools = tools + data_engineer_specific_tools
    
    # データエンジニアエージェントの作成
    data_engineer_agent = Agent(
        role="データエンジニア",
        goal="AIモデルの学習やシステム開発に必要なデータの収集、クレンジング、前処理、管理を行い、効率的なデータパイプラインを構築・運用します。",
        backstory="""
        あなたは、データエンジニアリングの専門家です。
        データベース、API、ストレージなど様々なソースからデータを抽出し、変換、クレンジングする豊富な経験を持っています。
        効率的かつスケーラブルなデータパイプラインを設計・実装する能力に長けており、
        大規模データの処理においても適切なツールと手法を選択できます。

        データの品質と整合性を確保するためのベストプラクティスに精通しており、
        機械学習モデルのためのデータ準備や特徴量エンジニアリングも得意としています。
        AIエンジニアやデータサイエンティストと緊密に連携し、彼らが効果的に業務を遂行できるよう、
        必要なデータを適切な形で提供するのがあなたの役割です。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=False,
    )
    
    return data_engineer_agent


def extract_data(agent: Agent, source_type: str, source_path: str, query: str = None) -> Dict[str, Any]:
    """
    データを抽出します。
    
    Args:
        agent: データエンジニアエージェント
        source_type: データソースの種類
        source_path: データソースのパスまたはURL
        query: 抽出条件やクエリ（オプション）
        
    Returns:
        Dict[str, Any]: 抽出結果
    """
    logger.info(f"データ抽出を開始します: {source_type} - {source_path}")
    
    # データ抽出タスクの実行
    extraction_task = Task(
        description=f"以下のソースからデータを抽出してください: {source_type} - {source_path}",
        expected_output="抽出されたデータの概要",
        agent=agent
    )
    
    context = {
        "source_type": source_type,
        "source_path": source_path
    }
    if query:
        context["query"] = query
    
    extraction_result = agent.execute_task(extraction_task, context=context)
    
    logger.info("データ抽出が完了しました。")
    return {"extraction_result": extraction_result}


def clean_data(agent: Agent, data_description: str, cleaning_operations: List[str]) -> Dict[str, Any]:
    """
    データのクリーニングと前処理を行います。
    
    Args:
        agent: データエンジニアエージェント
        data_description: データの説明
        cleaning_operations: 実行するクリーニング操作のリスト
        
    Returns:
        Dict[str, Any]: クリーニング結果
    """
    logger.info("データクリーニングを開始します。")
    
    # データクリーニングタスクの実行
    cleaning_task = Task(
        description=f"以下のデータのクリーニングと前処理を行ってください: {data_description}",
        expected_output="クリーニング結果の概要",
        agent=agent
    )
    
    cleaning_result = agent.execute_task(cleaning_task, context={
        "data_description": data_description,
        "cleaning_operations": cleaning_operations
    })
    
    logger.info("データクリーニングが完了しました。")
    return {"cleaning_result": cleaning_result}


def transform_data(agent: Agent, data_description: str, transformation_type: str, transformation_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    データの変換を行います。
    
    Args:
        agent: データエンジニアエージェント
        data_description: データの説明
        transformation_type: 変換の種類
        transformation_params: 変換のパラメータ（オプション）
        
    Returns:
        Dict[str, Any]: 変換結果
    """
    logger.info(f"データ変換を開始します: {transformation_type}")
    
    # データ変換タスクの実行
    transformation_task = Task(
        description=f"以下のデータに対して変換を行ってください: {data_description} - 変換タイプ: {transformation_type}",
        expected_output="変換結果の概要",
        agent=agent
    )
    
    context = {
        "data_description": data_description,
        "transformation_type": transformation_type
    }
    if transformation_params:
        context["transformation_params"] = transformation_params
    
    transformation_result = agent.execute_task(transformation_task, context=context)
    
    logger.info("データ変換が完了しました。")
    return {"transformation_result": transformation_result}


def design_data_pipeline(agent: Agent, requirements: str, data_sources: List[str] = None, processing_steps: List[str] = None) -> Dict[str, Any]:
    """
    データパイプラインを設計します。
    
    Args:
        agent: データエンジニアエージェント
        requirements: パイプラインの要件
        data_sources: データソースのリスト（オプション）
        processing_steps: 処理ステップのリスト（オプション）
        
    Returns:
        Dict[str, Any]: パイプライン設計書
    """
    logger.info("データパイプライン設計を開始します。")
    
    # データパイプライン設計タスクの実行
    pipeline_task = Task(
        description=f"以下の要件に基づいてデータパイプラインを設計してください: {requirements}",
        expected_output="データパイプライン設計書",
        agent=agent
    )
    
    context = {"requirements": requirements}
    if data_sources:
        context["data_sources"] = data_sources
    if processing_steps:
        context["processing_steps"] = processing_steps
    
    pipeline_result = agent.execute_task(pipeline_task, context=context)
    
    logger.info("データパイプライン設計が完了しました。")
    return {"pipeline_design": pipeline_result} 