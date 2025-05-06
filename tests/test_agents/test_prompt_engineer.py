"""
プロンプトエンジニアエージェントモジュールのユニットテスト。
プロンプト設計、最適化、評価、思考連鎖設計の機能をテストします。
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

# テスト対象のモジュールをインポート
from agents.prompt_engineer import (
    PromptDesignTool, PromptOptimizationTool, PromptEvaluationTool, ChainOfThoughtDesignTool,
    create_prompt_engineer_agent, design_prompt, optimize_prompt, evaluate_prompts, design_cot_prompt
)


class TestPromptDesignTool:
    """プロンプト設計ツールのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        self.tool = PromptDesignTool()
    
    def test_design_for_classification(self):
        """分類タスク向けプロンプト設計のテスト"""
        # 分類タスク用のプロンプト設計
        result = self.tool._run("テキストのカテゴリ分類", "製品、サービス、請求の3カテゴリ")
        
        # 結果の検証
        assert "プロンプト設計レポート" in result
        assert "カテゴリ" in result
        assert "分類" in result
        assert "設計の根拠" in result
        assert "期待される動作" in result
    
    def test_design_for_summarization(self):
        """要約タスク向けプロンプト設計のテスト"""
        # 要約タスク用のプロンプト設計
        result = self.tool._run("テキストの要約", constraints="200単語以内")
        
        # 結果の検証
        assert "プロンプト設計レポート" in result
        assert "要約" in result
        assert "200単語以内" in result
        assert "設計の根拠" in result
        assert "期待される動作" in result
    
    def test_design_for_qa(self):
        """質問応答タスク向けプロンプト設計のテスト"""
        # 質問応答タスク用のプロンプト設計
        context = "AIと機械学習に関する情報"
        result = self.tool._run("質問応答システム", context=context)
        
        # 結果の検証
        assert "プロンプト設計レポート" in result
        assert "質問応答" in result
        assert context in result
        assert "設計の根拠" in result
        assert "期待される動作" in result
    
    def test_design_for_generic(self):
        """汎用的なタスク向けプロンプト設計のテスト"""
        # 汎用タスク用のプロンプト設計
        result = self.tool._run("AIの倫理的問題について")
        
        # 結果の検証
        assert "プロンプト設計レポート" in result
        assert "AIの倫理的問題" in result
        assert "設計の根拠" in result
        assert "期待される動作" in result


class TestPromptOptimizationTool:
    """プロンプト最適化ツールのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        self.tool = PromptOptimizationTool()
    
    def test_optimize_basic_prompt(self):
        """基本的なプロンプト最適化のテスト"""
        # 最適化対象の簡易プロンプト
        current_prompt = "AIについて説明してください。"
        
        # プロンプト最適化実行
        result = self.tool._run(current_prompt)
        
        # 結果の検証
        assert "プロンプト最適化レポート" in result
        assert "元のプロンプト" in result
        assert current_prompt in result
        assert "最適化されたプロンプト" in result
        assert "問題点の分析" in result
        assert "改善点の説明" in result
        assert "推奨事項" in result
    
    def test_optimize_with_performance_issues(self):
        """パフォーマンス問題を指定したプロンプト最適化のテスト"""
        # 最適化対象のプロンプト
        current_prompt = "データ分析を行ってください。"
        performance_issues = "曖昧な指示\n具体的な分析方法が指定されていない"
        
        # プロンプト最適化実行
        result = self.tool._run(current_prompt, performance_issues=performance_issues)
        
        # 結果の検証
        assert "プロンプト最適化レポート" in result
        assert "元のプロンプト" in result
        assert "問題点の分析" in result
        assert "曖昧な指示" in result
        assert "最適化されたプロンプト" in result
        assert "改善点の説明" in result
    
    def test_optimize_with_desired_outcome(self):
        """期待される結果を指定したプロンプト最適化のテスト"""
        # 最適化対象のプロンプト
        current_prompt = "製品レビューを分析してください。"
        desired_outcome = "ポジティブとネガティブの感情スコアと主要なフィードバックポイントのリスト"
        
        # プロンプト最適化実行
        result = self.tool._run(current_prompt, desired_outcome=desired_outcome)
        
        # 結果の検証
        assert "プロンプト最適化レポート" in result
        assert "元のプロンプト" in result
        assert "最適化されたプロンプト" in result
        assert desired_outcome in result
        assert "改善点の説明" in result
        assert "期待される結果の明示" in result


class TestPromptEvaluationTool:
    """プロンプト評価ツールのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        self.tool = PromptEvaluationTool()
    
    def test_evaluate_prompt_versions(self):
        """複数のプロンプトバージョン評価のテスト"""
        # 評価対象のプロンプトバージョン
        prompt_versions = [
            "データを分析して傾向を見つけてください。",
            "以下のデータセットの傾向分析を行ってください。主要な統計指標と異常値を特定してください。",
            "# 指示\nデータ分析を行い、以下の情報を提供してください：\n- 基本統計量（平均、中央値、標準偏差）\n- 主要な傾向\n- 異常値とその影響\n\n# 出力フォーマット\n分析結果を箇条書きでまとめてください。"
        ]
        
        # プロンプト評価実行
        result = self.tool._run(prompt_versions)
        
        # 結果の検証
        assert "プロンプト評価レポート" in result
        assert "評価基準と重み付け" in result
        assert "各プロンプトバージョンの評価" in result
        for i, _ in enumerate(prompt_versions):
            assert f"バージョン {i+1}" in result
        assert "テストケース結果" in result
        assert "推奨プロンプト" in result
        assert "最終評価コメント" in result
    
    def test_evaluate_with_custom_criteria(self):
        """カスタム評価基準を使用したプロンプト評価のテスト"""
        # 評価対象のプロンプトバージョン
        prompt_versions = [
            "顧客データを分析してください。",
            "顧客セグメンテーション分析を行い、主要な顧客グループを特定してください。"
        ]
        
        # カスタム評価基準
        evaluation_criteria = {
            "業務適合性": 0.4,
            "実用性": 0.3,
            "効率性": 0.2,
            "汎用性": 0.1
        }
        
        # プロンプト評価実行
        result = self.tool._run(prompt_versions, evaluation_criteria=evaluation_criteria)
        
        # 結果の検証
        assert "プロンプト評価レポート" in result
        assert "評価基準と重み付け" in result
        for criterion in evaluation_criteria:
            assert criterion in result
        assert "各プロンプトバージョンの評価" in result
        assert "テストケース結果" in result
        assert "推奨プロンプト" in result


class TestChainOfThoughtDesignTool:
    """思考連鎖設計ツールのテスト"""
    
    def setup_method(self):
        """各テスト前の準備"""
        self.tool = ChainOfThoughtDesignTool()
    
    def test_design_cot_prompt(self):
        """思考連鎖プロンプト設計のテスト"""
        # タスク説明
        task_description = "複雑な数学的問題を解く"
        
        # 思考連鎖プロンプト設計実行
        result = self.tool._run(task_description)
        
        # 結果の検証
        assert "思考連鎖（Chain of Thought）プロンプト設計" in result
        assert task_description in result
        assert "設計したプロンプト" in result
        assert "プロンプトの説明" in result
    
    def test_design_cot_with_custom_example(self):
        """カスタム例題を使用した思考連鎖プロンプト設計のテスト"""
        # タスク説明
        task_description = "論理パズルを解く"
        
        # カスタム例題と解決手順
        example_problem = "AとBとCの3人がいます。Aは嘘つき、Bは正直者、Cは時々嘘をつきます。Aは「Bは嘘つきだ」と言い、Bは「Cは正直者だ」と言い、Cは「Aは正直者だ」と言いました。誰が正直者ですか？"
        solution_steps = [
            "Aが正直者と仮定すると、「Bは嘘つき」という発言は真実になります。",
            "Bが嘘つきなら、「Cは正直者」という発言は嘘になります。つまりCは嘘つきです。",
            "Cが嘘つきなら、「Aは正直者」という発言は嘘になります。つまりAは嘘つきです。",
            "これは「Aは正直者」という仮定と矛盾するため、Aは嘘つきです。",
            "Aが嘘つきなら、「Bは嘘つき」という発言は嘘になります。つまりBは正直者です。",
            "Bが正直者なら、「Cは正直者」という発言は真実です。つまりCは正直者です。",
            "しかしこれは「Aは正直者」というCの発言と矛盾します（Aは嘘つきと判明）。",
            "したがって、Bは正直者、AとCは嘘つきです。"
        ]
        
        # 思考連鎖プロンプト設計実行
        result = self.tool._run(task_description, example_problem=example_problem, solution_steps=solution_steps)
        
        # 結果の検証
        assert "思考連鎖（Chain of Thought）プロンプト設計" in result
        assert task_description in result
        assert "設計したプロンプト" in result
        assert example_problem in result
        assert "プロンプトの説明" in result
        # 各ステップが含まれていることを確認
        for step in solution_steps:
            assert step in result


@patch("agents.prompt_engineer.Agent")
class TestAgentFunctions:
    """エージェント関連の関数のテスト"""
    
    def test_create_prompt_engineer_agent(self, mock_agent_class):
        """プロンプトエンジニアエージェント作成のテスト"""
        # モックの設定
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        
        # エージェント作成
        agent = create_prompt_engineer_agent()
        
        # 結果の検証
        assert agent == mock_agent_instance
        mock_agent_class.assert_called_once()
        
        # エージェントにツールが設定されていることを確認
        args, kwargs = mock_agent_class.call_args
        assert "role" in kwargs
        assert "goal" in kwargs
        assert "backstory" in kwargs
        assert "tools" in kwargs
        
        # 必要なツールがあることを確認
        tools = kwargs["tools"]
        tool_names = [tool.name for tool in tools]
        assert "プロンプト設計" in tool_names
        assert "プロンプト最適化" in tool_names
        assert "プロンプト評価" in tool_names
        assert "思考連鎖設計" in tool_names
    
    def test_design_prompt(self, mock_agent_class):
        """design_prompt関数のテスト"""
        # モックの設定
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_task.return_value = "設計されたプロンプト"
        
        # 関数実行
        result = design_prompt(mock_agent_instance, "テキスト分類", "カテゴリ情報", "200単語以内")
        
        # 結果の検証
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == "設計されたプロンプト"
        
        # エージェントのexecute_taskが呼ばれたことを確認
        mock_agent_instance.execute_task.assert_called_once()
    
    def test_optimize_prompt(self, mock_agent_class):
        """optimize_prompt関数のテスト"""
        # モックの設定
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_task.return_value = "最適化されたプロンプト"
        
        # 関数実行
        current_prompt = "テストプロンプト"
        performance_issues = "曖昧さがある"
        desired_outcome = "より明確な指示"
        result = optimize_prompt(
            mock_agent_instance, 
            current_prompt, 
            performance_issues=performance_issues, 
            desired_outcome=desired_outcome
        )
        
        # 結果の検証
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == "最適化されたプロンプト"
        
        # エージェントのexecute_taskが呼ばれたことを確認
        mock_agent_instance.execute_task.assert_called_once()
    
    def test_evaluate_prompts(self, mock_agent_class):
        """evaluate_prompts関数のテスト"""
        # モックの設定
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_task.return_value = "プロンプト評価結果"
        
        # 関数実行
        prompt_versions = ["バージョン1", "バージョン2"]
        criteria = {"明確さ": 0.5, "簡潔さ": 0.5}
        test_cases = ["ケース1", "ケース2"]
        result = evaluate_prompts(
            mock_agent_instance, 
            prompt_versions, 
            evaluation_criteria=criteria, 
            test_cases=test_cases
        )
        
        # 結果の検証
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == "プロンプト評価結果"
        
        # エージェントのexecute_taskが呼ばれたことを確認
        mock_agent_instance.execute_task.assert_called_once()
    
    def test_design_cot_prompt(self, mock_agent_class):
        """design_cot_prompt関数のテスト"""
        # モックの設定
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_task.return_value = "設計された思考連鎖プロンプト"
        
        # 関数実行
        task_description = "数学問題を解く"
        example_problem = "問題例"
        solution_steps = ["ステップ1", "ステップ2"]
        result = design_cot_prompt(
            mock_agent_instance, 
            task_description, 
            example_problem=example_problem, 
            solution_steps=solution_steps
        )
        
        # 結果の検証
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == "設計された思考連鎖プロンプト"
        
        # エージェントのexecute_taskが呼ばれたことを確認
        mock_agent_instance.execute_task.assert_called_once() 