"""
プロンプト最適化モジュールのユニットテスト。
PromptTemplate、PromptFormatter、PromptOptimizerクラスのテストを行います。
"""

import pytest
from typing import Dict, List, Any
import re

from utils.prompt_optimization import (
    PromptType, PromptTemplate, PromptFormatter, PromptOptimizer,
    get_template, create_prompt_from_template, optimize_existing_prompt,
    compare_prompts, optimize_prompt, PRESET_TEMPLATES
)


class TestPromptTemplate:
    """プロンプトテンプレートクラスのテスト"""
    
    def test_template_initialization(self):
        """テンプレートの初期化と基本的な機能のテスト"""
        template = PromptTemplate(
            template="{{greeting}}、{{name}}さん！",
            template_type=PromptType.CUSTOM,
            metadata={"description": "挨拶用テンプレート"}
        )
        
        # 初期化されたプロパティの確認
        assert template.template == "{{greeting}}、{{name}}さん！"
        assert template.template_type == PromptType.CUSTOM
        assert template.metadata == {"description": "挨拶用テンプレート"}
    
    def test_extract_variables(self):
        """変数の抽出機能のテスト"""
        template = PromptTemplate("{{greeting}}、{{name}}さん！今日は{{date}}です。")
        variables = template.extract_variables()
        
        # 変数が正しく抽出されることを確認
        assert len(variables) == 3
        assert "greeting" in variables
        assert "name" in variables
        assert "date" in variables
    
    def test_format(self):
        """変数置換機能のテスト"""
        template = PromptTemplate("{{greeting}}、{{name}}さん！今日は{{date}}です。")
        
        # 変数を置換してプロンプトを生成
        result = template.format(greeting="こんにちは", name="田中", date="2023年4月1日")
        
        # 正しく置換されることを確認
        assert result == "こんにちは、田中さん！今日は2023年4月1日です。"
    
    def test_format_with_missing_variables(self):
        """不足している変数がある場合のフォーマットテスト"""
        template = PromptTemplate("{{greeting}}、{{name}}さん！今日は{{date}}です。")
        
        # 一部の変数のみを指定
        result = template.format(greeting="こんにちは", name="田中")
        
        # 不足している変数は置換されないことを確認
        assert result == "こんにちは、田中さん！今日は{{date}}です。"
    
    def test_to_and_from_dict(self):
        """辞書への変換と復元のテスト"""
        original = PromptTemplate(
            template="{{greeting}}、{{name}}さん！",
            template_type=PromptType.CUSTOM,
            metadata={"description": "挨拶用テンプレート"}
        )
        
        # 辞書へ変換
        data = original.to_dict()
        
        # 辞書から復元
        restored = PromptTemplate.from_dict(data)
        
        # 復元されたテンプレートが元のテンプレートと同じであることを確認
        assert restored.template == original.template
        assert restored.template_type == original.template_type
        assert restored.metadata == original.metadata


class TestPromptFormatter:
    """プロンプトフォーマッタクラスのテスト"""
    
    def test_to_openai_chat(self):
        """OpenAI Chat APIフォーマットへの変換テスト"""
        prompt = "これはテストプロンプトです。"
        system_message = "あなたは優秀なAIアシスタントです。"
        
        # OpenAI Chat API形式に変換
        result = PromptFormatter.to_openai_chat(prompt, system_message)
        
        # 形式が正しいことを確認
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == system_message
        assert result[1]["role"] == "user"
        assert result[1]["content"] == prompt
    
    def test_to_openai_chat_without_system(self):
        """システムメッセージなしのOpenAI Chat APIフォーマットテスト"""
        prompt = "これはテストプロンプトです。"
        
        # OpenAI Chat API形式に変換（システムメッセージなし）
        result = PromptFormatter.to_openai_chat(prompt)
        
        # 形式が正しいことを確認
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == prompt
    
    def test_to_anthropic_format(self):
        """Anthropic Claude APIフォーマットへの変換テスト"""
        prompt = "これはテストプロンプトです。"
        system_message = "あなたは優秀なAIアシスタントです。"
        
        # Anthropic形式に変換
        result = PromptFormatter.to_anthropic_format(prompt, system_message)
        
        # 形式が正しいことを確認
        assert isinstance(result, str)
        assert system_message in result
        assert prompt in result
        assert result.startswith(system_message)
        assert "Human:" in result
        assert "Assistant:" in result
    
    def test_to_gemini_format(self):
        """Google Gemini APIフォーマットへの変換テスト"""
        prompt = "これはテストプロンプトです。"
        system_message = "あなたは優秀なAIアシスタントです。"
        
        # Gemini形式に変換
        result = PromptFormatter.to_gemini_format(prompt, system_message)
        
        # 形式が正しいことを確認
        assert isinstance(result, dict)
        assert "contents" in result
        assert len(result["contents"]) == 2
        assert result["contents"][0]["role"] == "system"
        assert result["contents"][0]["content"] == system_message
        assert result["contents"][1]["role"] == "user"
        assert result["contents"][1]["content"] == prompt


class TestPromptOptimizer:
    """プロンプト最適化クラスのテスト"""
    
    def test_analyze_prompt(self):
        """プロンプト分析機能のテスト"""
        # 分析対象のプロンプト
        prompt = "データを分析してください。"
        
        # プロンプト分析を実行
        analysis = PromptOptimizer.analyze_prompt(prompt)
        
        # 分析結果の形式が正しいことを確認
        assert isinstance(analysis, dict)
        assert "issues" in analysis
        assert "recommendations" in analysis
        assert "structure" in analysis
        assert "length" in analysis
        
        # 短すぎるプロンプトには問題点がある
        assert len(analysis["issues"]) > 0
        assert "プロンプトが短すぎる" in analysis["issues"]
    
    def test_analyze_prompt_with_good_structure(self):
        """構造が良いプロンプトの分析テスト"""
        # 分析対象のプロンプト（良い構造）
        prompt = """
# 指示
以下のデータセットを分析し、主要な傾向を特定してください。
        
# 制約
- 分析は定量的かつ客観的に行ってください
- グラフや表の使用は最小限にしてください
- 専門用語の使用は避けてください
        
# 入力データ
{{data}}
        
# 出力フォーマット
分析結果を箇条書きで提示し、各ポイントに簡潔な説明を加えてください。
        """
        
        # プロンプト分析を実行
        analysis = PromptOptimizer.analyze_prompt(prompt)
        
        # 構造が良いことを確認
        assert analysis["structure"]["has_clear_instruction"] is True
        assert analysis["structure"]["has_constraints"] is True
        assert analysis["structure"]["has_output_format"] is True
        assert "data" in analysis["variables"]
        assert len(analysis["issues"]) == 0  # 問題点がない
    
    def test_optimize_prompt(self):
        """プロンプト最適化機能のテスト"""
        # 最適化対象のプロンプト
        prompt = "データ分析を行い、結果を教えてください。"
        
        # プロンプト最適化を実行
        optimized = PromptOptimizer.optimize_prompt(prompt)
        
        # 最適化されたことを確認
        assert len(optimized) > len(prompt)
        assert "# 指示" in optimized
        assert "# 制約" in optimized
        assert "# 出力" in optimized
    
    def test_evaluate_prompt(self):
        """プロンプト評価機能のテスト"""
        # 評価対象のプロンプト
        prompt = """
# 指示
以下のテキストを要約してください。

# 制約
- 要約は3文以内にまとめてください
- 主要なポイントを漏らさないでください

# 入力テキスト
{{text}}

# 出力
        """
        
        # プロンプト評価を実行
        evaluation = PromptOptimizer.evaluate_prompt(prompt)
        
        # 評価結果の形式が正しいことを確認
        assert isinstance(evaluation, dict)
        assert "scores" in evaluation
        assert "weighted_score" in evaluation
        assert "analysis" in evaluation
        
        # スコアの範囲が正しいことを確認
        for criterion, score in evaluation["scores"].items():
            assert 0 <= score <= 1.0
        
        assert 0 <= evaluation["weighted_score"] <= 1.0


class TestPresetTemplates:
    """プリセットテンプレートのテスト"""
    
    def test_get_template(self):
        """テンプレート取得機能のテスト"""
        # 存在するテンプレートの取得
        template = get_template("classification")
        
        # テンプレートが正しく取得できることを確認
        assert template is not None
        assert isinstance(template, PromptTemplate)
        assert template.template_type == PromptType.CLASSIFICATION
        
        # 存在しないテンプレートの取得
        template = get_template("nonexistent")
        
        # 存在しないテンプレートはNoneが返ることを確認
        assert template is None
    
    def test_create_prompt_from_template(self):
        """テンプレートからのプロンプト生成テスト"""
        # 分類テンプレートを使用してプロンプトを生成
        prompt = create_prompt_from_template(
            "classification",
            categories="カテゴリA、カテゴリB、カテゴリC",
            input_text="これはテスト用のテキストです。"
        )
        
        # プロンプトが正しく生成されることを確認
        assert "カテゴリA、カテゴリB、カテゴリC" in prompt
        assert "これはテスト用のテキストです。" in prompt
        assert "# 指示" in prompt
        assert "# 制約" in prompt
        assert "# 出力" in prompt
    
    def test_create_prompt_from_nonexistent_template(self):
        """存在しないテンプレートからのプロンプト生成テスト"""
        # 存在しないテンプレートを使用してプロンプトを生成
        prompt = create_prompt_from_template(
            "nonexistent",
            var1="値1",
            var2="値2"
        )
        
        # 空の文字列が返ることを確認
        assert prompt == ""


class TestOptimizationFunctions:
    """最適化関連関数のテスト"""
    
    def test_optimize_existing_prompt(self):
        """既存プロンプト最適化関数のテスト"""
        # 最適化対象のプロンプト
        prompt = "顧客データを分析して、セグメント分けしてください。"
        
        # 既存プロンプト最適化を実行
        result = optimize_existing_prompt(
            prompt,
            task_type="classification",
            performance_issues=["出力形式が不明確"]
        )
        
        # 結果の形式が正しいことを確認
        assert isinstance(result, dict)
        assert "original_prompt" in result
        assert "optimized_prompt" in result
        assert "analysis" in result
        assert "evaluation" in result
        
        # 最適化されたプロンプトが元のプロンプトよりも詳細であることを確認
        assert len(result["optimized_prompt"]) > len(prompt)
        assert "# 指示" in result["optimized_prompt"]
        assert "セグメント" in result["optimized_prompt"]
    
    def test_compare_prompts(self):
        """プロンプト比較関数のテスト"""
        # 比較対象のプロンプト
        prompts = [
            "データを分析してください。",
            """
# 指示
以下のデータを分析し、主要な傾向と異常値を特定してください。

# 制約
- 客観的な分析を行ってください
- 専門用語の使用は最小限にしてください

# 出力
分析結果を箇条書きで提示してください。
            """,
            "顧客データの分析をお願いします。傾向があれば教えてください。"
        ]
        
        # プロンプト比較を実行
        result = compare_prompts(prompts)
        
        # 結果の形式が正しいことを確認
        assert isinstance(result, dict)
        assert "results" in result
        assert "best_prompt_index" in result
        assert "best_score" in result
        assert "best_prompt" in result
        
        # 最適なプロンプトが2番目（構造化されたプロンプト）であることを確認
        assert result["best_prompt_index"] == 1
    
    def test_optimize_prompt_main_function(self):
        """メインの最適化関数のテスト"""
        # 最適化対象のプロンプト
        prompt = "テキストを要約してください。"
        
        # メイン最適化関数を実行
        result = optimize_prompt(
            prompt=prompt,
            task_type="summarization",
            performance_issues=["長さ制限がない"],
            target_model="openai",
            system_message="あなたは優秀な要約ツールです。"
        )
        
        # 結果の形式が正しいことを確認
        assert isinstance(result, dict)
        assert "original_prompt" in result
        assert "optimized_prompt" in result
        assert "formatted_prompt" in result
        assert "target_model" in result
        assert "analysis" in result
        assert "evaluation" in result
        
        # OpenAI形式に変換されていることを確認
        assert isinstance(result["formatted_prompt"], list)
        assert result["formatted_prompt"][0]["role"] == "system"
        
        # 最適化されたプロンプトに要約関連のセクションが含まれていることを確認
        assert "要約" in result["optimized_prompt"]
        assert "# 指示" in result["optimized_prompt"]
        assert "# 制約" in result["optimized_prompt"]
    
    def test_optimize_prompt_with_template(self):
        """テンプレートを使用した最適化関数のテスト"""
        # テンプレートと変数を指定
        template_name = "qa"
        template_vars = {
            "context": "日本の首都は東京です。面積は約378平方キロメートルです。",
            "question": "日本の首都は何ですか？",
            "response_style": "簡潔"
        }
        
        # テンプレートを使用した最適化を実行
        result = optimize_prompt(
            template_name=template_name,
            template_vars=template_vars,
            target_model="anthropic"
        )
        
        # 結果の形式が正しいことを確認
        assert isinstance(result, dict)
        assert "original_prompt" in result
        assert "optimized_prompt" in result
        assert "formatted_prompt" in result
        
        # テンプレート変数が反映されていることを確認
        assert "日本の首都は東京です" in result["original_prompt"]
        assert "日本の首都は何ですか" in result["original_prompt"]
        
        # Anthropic形式に変換されていることを確認
        assert isinstance(result["formatted_prompt"], str)
        assert "Human:" in result["formatted_prompt"]
        assert "Assistant:" in result["formatted_prompt"] 