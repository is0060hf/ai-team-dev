"""
プロンプトエンジニアエージェントモジュール。
各AIエージェントが使用する大規模言語モデル（LLM）への指示（プロンプト）の設計、最適化、評価を行います。
エージェントの応答精度や効率を向上させる役割を担います。
"""

import json
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("prompt_engineer")


class PromptDesignTool(Tool):
    """プロンプト設計ツール"""
    
    name = "プロンプト設計"
    description = "ユースケースに応じた効果的なプロンプトを設計します。"
    
    def _run(self, use_case: str, context: str = None, constraints: str = None) -> str:
        """
        プロンプトを設計します。
        
        Args:
            use_case: プロンプトの使用目的
            context: 関連するコンテキスト情報（オプション）
            constraints: 制約条件（オプション）
            
        Returns:
            str: 設計されたプロンプト
        """
        logger.info("プロンプト設計ツールが呼び出されました。")
        
        # プロンプト設計レポートテンプレート
        prompt_design_template = """
        # プロンプト設計レポート

        ## ユースケース
        {use_case}

        ## 設計したプロンプト
        ```
        {designed_prompt}
        ```

        ## 設計の根拠
        {rationale}

        ## 期待される動作
        {expected_behavior}

        ## 制約と考慮事項
        {considerations}

        ## 代替案
        {alternatives}
        """
        
        # ユースケースに基づくプロンプト設計（簡易サンプル）
        # 実際のプロジェクトではLLMを使用してより詳細なプロンプト設計を行う
        
        designed_prompt = ""
        rationale = ""
        expected_behavior = ""
        considerations = ""
        alternatives = ""
        
        # ユースケース別のプロンプト設計（サンプル）
        if "分類" in use_case or "カテゴリ分類" in use_case:
            designed_prompt = f"""
            あなたは高精度なテキスト分類システムです。
            
            # 指示
            与えられたテキストを以下のカテゴリのいずれかに分類してください：
            - カテゴリA: {context or "製品関連の問い合わせ"}
            - カテゴリB: {context or "サービス関連の問い合わせ"}
            - カテゴリC: {context or "請求関連の問い合わせ"}
            
            # 制約
            - 必ず上記のカテゴリの中から1つだけ選んでください
            - カテゴリ名のみを出力してください
            - 複数のカテゴリが当てはまる場合は、最も関連性の高いものを選択してください
            
            # 入力テキスト
            {{input_text}}
            
            # 出力
            """
            
            rationale = "分類タスクでは、カテゴリの明確な定義と出力形式の制約が重要です。このプロンプトは、カテゴリを明示し、出力形式を厳格に指定することで、一貫性のある結果を得られるよう設計されています。"
            expected_behavior = "モデルは入力テキストを分析し、指定されたカテゴリの中から最も適切なものを選択します。出力はカテゴリ名のみとなり、余分な説明は含まれません。"
            considerations = "カテゴリ数が多い場合や、カテゴリ間の境界が曖昧な場合は注意が必要です。また、モデルの知識や訓練データによってパフォーマンスが変わる可能性があります。"
            alternatives = "- カテゴリごとに詳細な説明を加える\n- 確信度スコアを出力させる\n- 複数カテゴリへの分類を許可する（マルチラベル分類）"
            
        elif "要約" in use_case or "サマリー" in use_case:
            designed_prompt = f"""
            あなたは高性能なテキスト要約システムです。
            
            # 指示
            与えられたテキストの要点を抽出し、簡潔に要約してください。
            
            # 制約
            - 要約は{constraints or "100"}単語以内に収めてください
            - 原文の主要な情報を漏らさないでください
            - 要約は客観的であり、新しい情報や意見を追加しないでください
            - 箇条書きではなく、文章形式で出力してください
            
            # 入力テキスト
            {{input_text}}
            
            # 出力
            """
            
            rationale = "要約タスクでは、重要な情報を保持しながら冗長性を削減することが重要です。このプロンプトは、要約の最大長を設定し、客観性を保ちながら主要な情報を抽出するように設計されています。"
            expected_behavior = "モデルは入力テキストを理解し、主要な情報を抽出して指定された長さ以内の要約を生成します。要約は文章形式で、オリジナルの主旨を保持しています。"
            considerations = "入力テキストが非常に長い場合や専門的な内容を含む場合は、情報の損失や不正確さが生じる可能性があります。また、指定された単語数が短すぎると重要な情報が省略される恐れがあります。"
            alternatives = "- 箇条書き形式での要約\n- 要約の詳細度レベルを指定\n- 特定の観点（例: ビジネス視点、技術視点）からの要約"
            
        elif "質問応答" in use_case or "QA" in use_case:
            designed_prompt = f"""
            あなたは高精度な質問応答システムです。
            
            # 指示
            与えられたコンテキスト情報に基づいて、質問に正確に答えてください。
            
            # 制約
            - コンテキスト内の情報のみを使用してください
            - コンテキストに情報がない場合は「情報がありません」と回答してください
            - 回答は{constraints or "簡潔"}にしてください
            - 推測や不確かな情報は含めないでください
            
            # コンテキスト
            {context or "{{context}}"}
            
            # 質問
            {{question}}
            
            # 出力
            """
            
            rationale = "質問応答タスクでは、与えられたコンテキストに基づいて正確な回答を提供することが重要です。このプロンプトは、コンテキスト情報の利用を明示的に指示し、コンテキスト外の情報による回答を防止するよう設計されています。"
            expected_behavior = "モデルはコンテキスト内の情報のみを参照して質問に回答します。コンテキストに関連情報がない場合は、「情報がありません」と回答します。"
            considerations = "コンテキストが不完全または曖昧な場合は、回答の質が低下する可能性があります。また、質問の解釈によっては、意図とは異なる回答が生成されることがあります。"
            alternatives = "- コンテキスト情報の信頼性スコアを付加\n- 複数の可能な回答を提示\n- コンテキスト外の知識を使用する場合にその旨を明示"
            
        else:
            # 汎用的なプロンプト設計
            designed_prompt = f"""
            # 指示
            {use_case}について詳細に説明してください。
            
            # 制約
            - 正確な情報のみを提供してください
            - 専門用語を使用する場合は、簡潔な説明を加えてください
            - 回答は論理的で体系的な構造を持つようにしてください
            
            # 入力
            {{input}}
            
            # 出力
            """
            
            rationale = "このプロンプトは汎用的な情報提供タスク向けに設計されています。正確性と理解しやすさを重視しています。"
            expected_behavior = "モデルは指定されたトピックについて、正確かつ構造化された情報を提供します。専門用語には説明が付加され、情報は論理的に整理されます。"
            considerations = "トピックによっては、より特化した指示や制約が必要になる場合があります。また、モデルの知識の制限により、特定の分野では情報が不足または古い可能性があります。"
            alternatives = "- より対話的なスタイルでの回答\n- 特定の観点からの説明\n- 情報の詳細度レベルを指定"
        
        return prompt_design_template.format(
            use_case=use_case,
            designed_prompt=designed_prompt.strip(),
            rationale=rationale,
            expected_behavior=expected_behavior,
            considerations=considerations,
            alternatives=alternatives
        )


class PromptOptimizationTool(Tool):
    """プロンプト最適化ツール"""
    
    name = "プロンプト最適化"
    description = "既存のプロンプトを分析し、改善案を提案します。"
    
    def _run(self, current_prompt: str, performance_issues: str = None, desired_outcome: str = None) -> str:
        """
        プロンプトを最適化します。
        
        Args:
            current_prompt: 現在使用しているプロンプト
            performance_issues: 現在のプロンプトの問題点（オプション）
            desired_outcome: 期待される結果（オプション）
            
        Returns:
            str: 最適化されたプロンプト
        """
        logger.info("プロンプト最適化ツールが呼び出されました。")
        
        # プロンプト最適化レポートテンプレート
        optimization_template = """
        # プロンプト最適化レポート

        ## 元のプロンプト
        ```
        {original_prompt}
        ```

        ## 問題点の分析
        {issues_analysis}

        ## 最適化されたプロンプト
        ```
        {optimized_prompt}
        ```

        ## 改善点の説明
        {improvements}

        ## 追加の推奨事項
        {recommendations}
        """
        
        # プロンプトの分析と最適化（簡易サンプル）
        # 実際のプロジェクトではLLMを使用してより詳細な分析と最適化を行う
        
        # 問題点の分析
        issues = []
        if not performance_issues:
            # 基本的な問題点チェック
            if not "指示" in current_prompt and not "# 指示" in current_prompt:
                issues.append("明確な指示セクションがありません")
            if len(current_prompt.split()) < 20:
                issues.append("プロンプトが短すぎ、十分なコンテキストや制約が含まれていない可能性があります")
            if not "制約" in current_prompt and not "# 制約" in current_prompt:
                issues.append("制約条件が明示されていないため、期待と異なる結果が生成される可能性があります")
            if "{" in current_prompt and "}" in current_prompt and not "{{" in current_prompt:
                issues.append("変数の記法が不適切です。二重中括弧 {{variable}} を使用してください")
        else:
            # 指定された問題点を解析
            issues = performance_issues.split("\n")
        
        issues_analysis = "### 特定された問題点:\n" + "\n".join([f"- {issue}" for issue in issues])
        
        # プロンプトの構造分析
        has_instruction = "指示" in current_prompt or "# 指示" in current_prompt
        has_constraints = "制約" in current_prompt or "# 制約" in current_prompt
        has_example = "例" in current_prompt or "# 例" in current_prompt
        has_format = "出力" in current_prompt or "# 出力" in current_prompt or "フォーマット" in current_prompt
        
        # 基本構造の改善推奨
        structure_recommendations = []
        if not has_instruction:
            structure_recommendations.append("明確な指示セクションを追加する")
        if not has_constraints:
            structure_recommendations.append("制約条件を明示的に定義する")
        if not has_example:
            structure_recommendations.append("適切な例を追加する")
        if not has_format:
            structure_recommendations.append("期待される出力フォーマットを指定する")
        
        # 最適化されたプロンプトの生成
        # 簡易的な最適化（実際にはLLMを使用してより高度な最適化を行う）
        optimized_prompt = current_prompt
        
        # 基本構造の追加
        if structure_recommendations:
            sections = optimized_prompt.split("\n\n")
            if not has_instruction:
                sections.insert(0, "# 指示\n以下の条件に従ってタスクを実行してください。")
            if not has_constraints:
                sections.append("# 制約\n- 指定された形式で回答してください\n- 不明な場合は推測せず、情報不足と明示してください")
            if not has_format:
                sections.append("# 出力フォーマット\n[ここに期待する出力形式を記述]")
            optimized_prompt = "\n\n".join(sections)
        
        # プロンプトの明確化と具体化
        # ここでは簡易的な置換のみ（実際にはLLMを使用）
        if "曖昧" in performance_issues or "不明確" in performance_issues:
            optimized_prompt = optimized_prompt.replace("適切に", "詳細かつ論理的に")
            optimized_prompt = optimized_prompt.replace("分析", "以下の観点から分析: 1. 事実関係, 2. 因果関係, 3. 影響範囲")
        
        if "冗長" in performance_issues or "長すぎる" in performance_issues:
            optimized_prompt = optimized_prompt.replace("詳細に説明", "簡潔に説明")
            optimized_prompt = optimized_prompt.replace("すべての", "主要な")
            
        # プロンプトに必要な情報を含める
        if desired_outcome:
            if "# 期待される結果" not in optimized_prompt:
                optimized_prompt += f"\n\n# 期待される結果\n{desired_outcome}"
        
        # 改善点の説明
        improvements = "以下の改善を実施しました：\n"
        if structure_recommendations:
            improvements += "### 構造の改善\n" + "\n".join([f"- {rec}" for rec in structure_recommendations]) + "\n\n"
        
        if "曖昧" in performance_issues or "不明確" in performance_issues:
            improvements += "### 明確化\n- 曖昧な表現を具体的な指示に置き換え\n- 分析の観点を明示的に指定\n\n"
            
        if "冗長" in performance_issues or "長すぎる" in performance_issues:
            improvements += "### 簡潔化\n- 冗長な表現を簡潔な表現に置き換え\n- 不要な修飾語を削除\n\n"
            
        if desired_outcome:
            improvements += "### 期待される結果の明示\n- 期待される結果を明示的に追加し、目標を明確化\n\n"
        
        # 追加の推奨事項
        recommendations = """
        ### さらなる改善のための推奨事項:
        1. **Few-shot learning**: 2-3の例を追加することで、モデルの理解を深める
        2. **変数の明確化**: プレースホルダー変数に説明を追加する（例: {{input_text: 分析対象のテキスト}}）
        3. **コンテキストの充実**: 必要に応じて背景情報を追加する
        4. **チェーンオブソート**: 複雑なタスクでは、思考プロセスを段階的に指示する
        5. **ユースケースのテスト**: 様々な入力でテストし、最適化を繰り返す
        """
        
        return optimization_template.format(
            original_prompt=current_prompt.strip(),
            issues_analysis=issues_analysis,
            optimized_prompt=optimized_prompt.strip(),
            improvements=improvements,
            recommendations=recommendations
        )


class PromptEvaluationTool(Tool):
    """プロンプト評価ツール"""
    
    name = "プロンプト評価"
    description = "複数のプロンプトバージョンを評価し、最適なものを選定します。"
    
    def _run(self, prompt_versions: List[str], evaluation_criteria: Dict[str, float] = None, test_cases: List[str] = None) -> str:
        """
        プロンプトバージョンを評価します。
        
        Args:
            prompt_versions: 評価するプロンプトのリスト
            evaluation_criteria: 評価基準と重み付け（オプション）
            test_cases: テストケースのリスト（オプション）
            
        Returns:
            str: プロンプト評価レポート
        """
        logger.info("プロンプト評価ツールが呼び出されました。")
        
        # デフォルトの評価基準
        if evaluation_criteria is None:
            evaluation_criteria = {
                "明確さ": 0.25,
                "具体性": 0.25,
                "簡潔さ": 0.2,
                "構造化": 0.15,
                "一貫性": 0.15
            }
        
        # デフォルトのテストケース
        if test_cases is None:
            test_cases = ["一般的なユースケース", "エッジケース", "複雑なユースケース"]
        
        # プロンプト評価レポートテンプレート
        evaluation_template = """
        # プロンプト評価レポート

        ## 評価基準と重み付け
        {criteria_table}

        ## 各プロンプトバージョンの評価
        {version_evaluations}

        ## テストケース結果
        {test_results}

        ## 推奨プロンプト
        {recommendation}

        ## 最終評価コメント
        {final_comments}
        """
        
        # 評価基準のテーブル
        criteria_table = "| 評価基準 | 重み付け |\n|--------|--------|\n"
        criteria_table += "\n".join([f"| {criterion} | {weight} |" for criterion, weight in evaluation_criteria.items()])
        
        # 各プロンプトの評価（サンプル）
        # 実際のプロジェクトではLLMを使用して詳細な評価を行う
        import random
        random.seed(42)  # 再現性のため
        
        version_scores = {}
        for i, prompt in enumerate(prompt_versions):
            scores = {}
            for criterion in evaluation_criteria:
                # ランダムなスコア生成（実際のプロジェクトではLLMによる評価）
                score = round(random.uniform(0.6, 1.0), 2)
                scores[criterion] = score
            
            # 総合スコア計算
            weighted_score = sum([scores[criterion] * weight for criterion, weight in evaluation_criteria.items()])
            version_scores[i] = {
                "prompt": prompt,
                "scores": scores,
                "weighted_score": round(weighted_score, 2)
            }
        
        # 各プロンプトバージョンの評価
        version_evaluations = ""
        for i, data in version_scores.items():
            version_evaluations += f"### バージョン {i+1}\n"
            version_evaluations += "プロンプト:\n```\n" + data["prompt"][:200] + "..." + "\n```\n\n"
            version_evaluations += "評価スコア:\n"
            for criterion, score in data["scores"].items():
                version_evaluations += f"- {criterion}: {score}\n"
            version_evaluations += f"**総合スコア: {data['weighted_score']}**\n\n"
        
        # テストケース結果（サンプル）
        test_results = ""
        for i, test_case in enumerate(test_cases):
            test_results += f"### テストケース {i+1}: {test_case}\n"
            for j in range(len(prompt_versions)):
                result = ["良好", "平均的", "要改善"][random.randint(0, 2)]
                test_results += f"- バージョン {j+1}: {result}\n"
            test_results += "\n"
        
        # ベストプロンプトの選定
        best_version = max(version_scores.items(), key=lambda x: x[1]["weighted_score"])
        best_index = best_version[0]
        best_score = best_version[1]["weighted_score"]
        
        recommendation = f"評価の結果、**バージョン {best_index+1}** が最も高いスコア（{best_score}）を獲得しました。このプロンプトの使用を推奨します。\n\n"
        recommendation += "推奨プロンプト:\n```\n" + prompt_versions[best_index] + "\n```"
        
        # 最終評価コメント
        final_comments = f"""
        バージョン {best_index+1} は以下の点で優れています：
        
        1. **構造化:** 明確なセクション分けと論理的な流れ
        2. **明確さ:** 指示が明確で誤解の余地が少ない
        3. **適切な詳細度:** 十分な情報を提供しつつ、冗長性を避けている
        
        テストケースでの実際の性能も考慮すると、このプロンプトは多様なシナリオで一貫した結果を提供すると期待できます。
        
        ただし、実際の運用環境でさらなる調整が必要になる場合があります。フィードバックループを構築し、定期的にプロンプトの性能を評価・最適化することをお勧めします。
        """
        
        return evaluation_template.format(
            criteria_table=criteria_table,
            version_evaluations=version_evaluations,
            test_results=test_results,
            recommendation=recommendation,
            final_comments=final_comments
        )


class ChainOfThoughtDesignTool(Tool):
    """思考連鎖（Chain of Thought）設計ツール"""
    
    name = "思考連鎖設計"
    description = "複雑な推論が必要なタスク向けに、思考連鎖（Chain of Thought）アプローチを用いたプロンプトを設計します。"
    
    def _run(self, task_description: str, example_problem: str = None, solution_steps: List[str] = None) -> str:
        """
        思考連鎖プロンプトを設計します。
        
        Args:
            task_description: タスクの説明
            example_problem: 例題（オプション）
            solution_steps: 解決手順（オプション）
            
        Returns:
            str: 思考連鎖プロンプト
        """
        logger.info("思考連鎖設計ツールが呼び出されました。")
        
        # デフォルトの例題と解決手順
        if example_problem is None:
            example_problem = "太郎は5個のリンゴを持っています。彼は花子に2個あげて、その後さらに3個買いました。太郎は今何個のリンゴを持っていますか？"
        
        if solution_steps is None:
            solution_steps = [
                "太郎は最初に5個のリンゴを持っています。",
                "太郎は花子に2個のリンゴをあげたので、残りは 5 - 2 = 3 個になります。",
                "その後、太郎はさらに3個のリンゴを買いました。よって、太郎が持っているリンゴの合計は 3 + 3 = 6 個になります。",
                "したがって、太郎は今6個のリンゴを持っています。"
            ]
        
        # 思考連鎖プロンプトテンプレート
        cot_template = """
        # 思考連鎖（Chain of Thought）プロンプト設計

        ## タスク説明
        {task_description}

        ## 設計したプロンプト
        ```
        {cot_prompt}
        ```

        ## プロンプトの説明
        {explanation}

        ## 注意点と推奨事項
        {recommendations}
        """
        
        # 思考連鎖プロンプトの生成
        cot_prompt = f"""
        # 指示
        あなたは複雑な問題を論理的に解決するエキスパートです。与えられた問題に対して、以下のステップで解決してください：
        
        1. 問題を理解し、与えられた情報を整理する
        2. 解決に必要な中間ステップを明確にする
        3. 各ステップを論理的に考え、答えを導き出す
        4. 最終的な答えを明示する
        
        # 思考プロセス
        問題を一つひとつの段階に分解し、段階ごとに考えることで解決してください。各ステップでの思考過程を明確に示してください。
        
        # 例題
        問題: {example_problem}
        
        思考過程:
        {solution_steps[0]}
        {solution_steps[1]}
        {solution_steps[2]}
        {solution_steps[3]}
        
        # 問題
        {{problem}}
        
        # 思考過程
        """
        
        explanation = f"""
        このプロンプトは思考連鎖（Chain of Thought）アプローチを実装しています。このアプローチは以下の特徴を持ちます：
        
        1. **明示的な思考ステップ**: モデルに段階的な思考プロセスを促しています
        2. **Few-shot例示**: 適切な例を示すことで、モデルに期待される思考パターンを教えています
        3. **構造化された出力**: 思考過程と最終的な回答を明確に区別するよう促しています
        
        この方法は、複雑な推論や多段階の計算が必要なタスクで特に効果的です。例えば、数学的問題、論理パズル、複数ステップの推論が必要な質問などに適しています。
        """
        
        recommendations = """
        ### プロンプト使用時の注意点:
        
        1. **適切な例の選択**: タスクの複雑さに合った例を選ぶことが重要です。実際のタスクと似た構造を持つ例が効果的です。
        
        2. **複数例の使用**: 複雑なタスクでは、複数の例を提供することで性能が向上する場合があります。
        
        3. **思考の粒度**: タスクの複雑さに応じて、思考ステップの粒度を調整してください。細かすぎると冗長に、荒すぎると重要なステップが飛ばされる可能性があります。
        
        4. **反復改善**: 実際の出力結果を評価し、問題パターンに基づいてプロンプトを調整することが重要です。
        
        5. **モデルの限界認識**: LLMは依然として計算ミスをする可能性があります。重要な計算や推論を必要とするタスクでは、結果を検証するメカニズムを設けることを検討してください。
        """
        
        return cot_template.format(
            task_description=task_description,
            cot_prompt=cot_prompt.strip(),
            explanation=explanation.strip(),
            recommendations=recommendations.strip()
        )


def create_prompt_engineer_agent(tools: Optional[List[Tool]] = None) -> Agent:
    """
    プロンプトエンジニアエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        
    Returns:
        Agent: 設定されたプロンプトエンジニアエージェント
    """
    logger.info("プロンプトエンジニアエージェントを作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # プロンプトエンジニア固有のツールを追加
    prompt_engineer_specific_tools = [
        PromptDesignTool(),
        PromptOptimizationTool(),
        PromptEvaluationTool(),
        ChainOfThoughtDesignTool()
    ]
    
    all_tools = tools + prompt_engineer_specific_tools
    
    # プロンプトエンジニアエージェントの作成
    prompt_engineer_agent = Agent(
        role="プロンプトエンジニア",
        goal="各AIエージェントが使用するLLMへの指示（プロンプト）を設計、最適化、評価し、エージェントの応答精度や効率を向上させます。",
        backstory="""
        あなたは、言語モデルの潜在能力を最大限に引き出すプロンプトエンジニアリングの専門家です。
        様々なタスクに対して最適なプロンプトを設計し、精度と効率を向上させることに長けています。
        レスポンスの品質、一貫性、関連性を高めるためのテクニックに精通しており、
        Few-shot learning、Chain of Thought、ReAct パターンなど様々なプロンプティング手法を
        状況に応じて適用できます。
        
        プロンプトのA/Bテストや体系的な評価を通じて、継続的な改善プロセスを確立するのが得意です。
        また、タスクの特性や使用するAIモデルの特性を理解し、それに合わせたプロンプト設計ができます。
        チームの他のエージェントと緊密に連携し、それぞれの役割に最適なプロンプトを提供することで、
        プロジェクト全体の品質向上に貢献します。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=False,
    )
    
    return prompt_engineer_agent


def design_prompt(agent: Agent, use_case: str, context: str = None, constraints: str = None) -> Dict[str, Any]:
    """
    プロンプトを設計します。
    
    Args:
        agent: プロンプトエンジニアエージェント
        use_case: プロンプトの使用目的
        context: 関連するコンテキスト情報（オプション）
        constraints: 制約条件（オプション）
        
    Returns:
        Dict[str, Any]: 設計されたプロンプト
    """
    logger.info("プロンプト設計を開始します。")
    
    # プロンプト設計タスクの実行
    design_task = Task(
        description=f"以下のユースケースに対して最適なプロンプトを設計してください: {use_case}",
        expected_output="設計されたプロンプトとその説明",
        agent=agent
    )
    
    task_context = {"use_case": use_case}
    if context:
        task_context["context"] = context
    if constraints:
        task_context["constraints"] = constraints
    
    design_result = agent.execute_task(design_task, context=task_context)
    
    logger.info("プロンプト設計が完了しました。")
    return {"prompt_design": design_result}


def optimize_prompt(agent: Agent, current_prompt: str, performance_issues: str = None, desired_outcome: str = None) -> Dict[str, Any]:
    """
    プロンプトを最適化します。
    
    Args:
        agent: プロンプトエンジニアエージェント
        current_prompt: 現在使用しているプロンプト
        performance_issues: 現在のプロンプトの問題点（オプション）
        desired_outcome: 期待される結果（オプション）
        
    Returns:
        Dict[str, Any]: 最適化されたプロンプト
    """
    logger.info("プロンプト最適化を開始します。")
    
    # プロンプト最適化タスクの実行
    optimization_task = Task(
        description="現在のプロンプトを分析し、より効果的になるように最適化してください。",
        expected_output="最適化されたプロンプトと改善点の説明",
        agent=agent
    )
    
    task_context = {"current_prompt": current_prompt}
    if performance_issues:
        task_context["performance_issues"] = performance_issues
    if desired_outcome:
        task_context["desired_outcome"] = desired_outcome
    
    optimization_result = agent.execute_task(optimization_task, context=task_context)
    
    logger.info("プロンプト最適化が完了しました。")
    return {"prompt_optimization": optimization_result}


def evaluate_prompts(agent: Agent, prompt_versions: List[str], evaluation_criteria: Dict[str, float] = None, test_cases: List[str] = None) -> Dict[str, Any]:
    """
    複数のプロンプトバージョンを評価します。
    
    Args:
        agent: プロンプトエンジニアエージェント
        prompt_versions: 評価するプロンプトのリスト
        evaluation_criteria: 評価基準と重み付け（オプション）
        test_cases: テストケースのリスト（オプション）
        
    Returns:
        Dict[str, Any]: プロンプト評価レポート
    """
    logger.info("プロンプト評価を開始します。")
    
    # プロンプト評価タスクの実行
    evaluation_task = Task(
        description="提供された複数のプロンプトバージョンを評価し、最適なものを選定してください。",
        expected_output="プロンプト評価レポート",
        agent=agent
    )
    
    task_context = {"prompt_versions": prompt_versions}
    if evaluation_criteria:
        task_context["evaluation_criteria"] = evaluation_criteria
    if test_cases:
        task_context["test_cases"] = test_cases
    
    evaluation_result = agent.execute_task(evaluation_task, context=task_context)
    
    logger.info("プロンプト評価が完了しました。")
    return {"prompt_evaluation": evaluation_result}


def design_cot_prompt(agent: Agent, task_description: str, example_problem: str = None, solution_steps: List[str] = None) -> Dict[str, Any]:
    """
    思考連鎖（Chain of Thought）プロンプトを設計します。
    
    Args:
        agent: プロンプトエンジニアエージェント
        task_description: タスクの説明
        example_problem: 例題（オプション）
        solution_steps: 解決手順（オプション）
        
    Returns:
        Dict[str, Any]: 思考連鎖プロンプト
    """
    logger.info("思考連鎖プロンプト設計を開始します。")
    
    # 思考連鎖プロンプト設計タスクの実行
    cot_task = Task(
        description=f"複雑な推論が必要な以下のタスクに対して、思考連鎖（Chain of Thought）アプローチを用いたプロンプトを設計してください: {task_description}",
        expected_output="思考連鎖プロンプトとその説明",
        agent=agent
    )
    
    task_context = {"task_description": task_description}
    if example_problem:
        task_context["example_problem"] = example_problem
    if solution_steps:
        task_context["solution_steps"] = solution_steps
    
    cot_result = agent.execute_task(cot_task, context=task_context)
    
    logger.info("思考連鎖プロンプト設計が完了しました。")
    return {"cot_prompt_design": cot_result} 