"""
utils/specialist_triggers.py のユニットテスト。
専門エージェント起動判断ロジックをテストします。
"""

import re
import pytest
from unittest.mock import MagicMock, patch

from utils.agent_communication import TaskType, TaskPriority
from utils.workflow_automation import SpecialistAgents, CoreAgents
from utils.specialist_triggers import (
    SpecialistTriggerPatterns, SpecialistTriggerAnalyzer, 
    trigger_analyzer, analyze_specialist_need, 
    request_specialist_if_needed
)


class TestSpecialistTriggerPatterns:
    """SpecialistTriggerPatternsクラスのテスト"""
    
    def test_ai_architect_patterns(self):
        """AIアーキテクト向けのパターンが正しく定義されていることを確認"""
        # パターンの存在を確認
        assert hasattr(SpecialistTriggerPatterns, 'AI_ARCHITECT_PATTERNS')
        assert isinstance(SpecialistTriggerPatterns.AI_ARCHITECT_PATTERNS, list)
        assert len(SpecialistTriggerPatterns.AI_ARCHITECT_PATTERNS) > 0
        
        # 各パターンが有効な正規表現であることを確認
        for pattern in SpecialistTriggerPatterns.AI_ARCHITECT_PATTERNS:
            # 正規表現としてコンパイルできることを確認
            assert re.compile(pattern) is not None
            
        # 代表的なパターンの動作を確認
        test_cases = [
            ("システムアーキテクチャ設計をお願いします", True),
            ("クラウドインフラ構築の支援をお願いします", True),
            ("技術スタック選定をしてください", True),
            ("スケーラビリティの確保が必要です", True),
            ("プロンプト設計をお願いします", False),
            ("データクリーニングをお願いします", False)
        ]
        
        for text, expected in test_cases:
            matched = any(re.search(pattern, text) for pattern in SpecialistTriggerPatterns.AI_ARCHITECT_PATTERNS)
            assert matched == expected, f"テキスト「{text}」の判定が{expected}になることを期待したが、{matched}になりました"
    
    def test_prompt_engineer_patterns(self):
        """プロンプトエンジニア向けのパターンが正しく定義されていることを確認"""
        # パターンの存在を確認
        assert hasattr(SpecialistTriggerPatterns, 'PROMPT_ENGINEER_PATTERNS')
        assert isinstance(SpecialistTriggerPatterns.PROMPT_ENGINEER_PATTERNS, list)
        assert len(SpecialistTriggerPatterns.PROMPT_ENGINEER_PATTERNS) > 0
        
        # 各パターンが有効な正規表現であることを確認
        for pattern in SpecialistTriggerPatterns.PROMPT_ENGINEER_PATTERNS:
            # 正規表現としてコンパイルできることを確認
            assert re.compile(pattern) is not None
            
        # 代表的なパターンの動作を確認
        test_cases = [
            ("プロンプト設計をお願いします", True),
            ("LLMへの指示を最適化したい", True),
            ("GPT-4のプロンプト最適化をお願いします", True),
            ("チェーンオブソートを使った回答が欲しい", True),
            ("システム設計をお願いします", False),
            ("データパイプラインの構築が必要です", False)
        ]
        
        for text, expected in test_cases:
            matched = any(re.search(pattern, text) for pattern in SpecialistTriggerPatterns.PROMPT_ENGINEER_PATTERNS)
            assert matched == expected, f"テキスト「{text}」の判定が{expected}になることを期待したが、{matched}になりました"
    
    def test_data_engineer_patterns(self):
        """データエンジニア向けのパターンが正しく定義されていることを確認"""
        # パターンの存在を確認
        assert hasattr(SpecialistTriggerPatterns, 'DATA_ENGINEER_PATTERNS')
        assert isinstance(SpecialistTriggerPatterns.DATA_ENGINEER_PATTERNS, list)
        assert len(SpecialistTriggerPatterns.DATA_ENGINEER_PATTERNS) > 0
        
        # 各パターンが有効な正規表現であることを確認
        for pattern in SpecialistTriggerPatterns.DATA_ENGINEER_PATTERNS:
            # 正規表現としてコンパイルできることを確認
            assert re.compile(pattern) is not None
            
        # 代表的なパターンの動作を確認
        test_cases = [
            ("データ抽出をお願いします", True),
            ("ETLパイプラインの構築が必要です", True),
            ("データクリーニングをお願いします", True),
            ("データモデル設計をしてください", True),
            ("システム設計をお願いします", False),
            ("プロンプト最適化をお願いします", False)
        ]
        
        for text, expected in test_cases:
            matched = any(re.search(pattern, text) for pattern in SpecialistTriggerPatterns.DATA_ENGINEER_PATTERNS)
            assert matched == expected, f"テキスト「{text}」の判定が{expected}になることを期待したが、{matched}になりました"


class TestSpecialistTriggerAnalyzer:
    """SpecialistTriggerAnalyzerクラスのテスト"""
    
    def test_analyzer_initialization(self):
        """アナライザーが正しく初期化されることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # パターンがコンパイルされていることを確認
        assert hasattr(analyzer, 'ai_architect_patterns')
        assert all(isinstance(pattern, re.Pattern) for pattern in analyzer.ai_architect_patterns)
        
        assert hasattr(analyzer, 'prompt_engineer_patterns')
        assert all(isinstance(pattern, re.Pattern) for pattern in analyzer.prompt_engineer_patterns)
        
        assert hasattr(analyzer, 'data_engineer_patterns')
        assert all(isinstance(pattern, re.Pattern) for pattern in analyzer.data_engineer_patterns)
        
        # しきい値が設定されていることを確認
        assert 0 <= analyzer.ai_architect_threshold <= 1
        assert 0 <= analyzer.prompt_engineer_threshold <= 1
        assert 0 <= analyzer.data_engineer_threshold <= 1
    
    def test_analyze_request_ai_architect(self):
        """AIアーキテクト関連の要求を正しく識別できることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # AIアーキテクト関連テキスト
        text = "システムアーキテクチャの設計を手伝ってください。スケーラビリティを考慮した設計が必要です。"
        
        needed, specialist, confidence = analyzer.analyze_request(text)
        
        # 結果を確認
        assert needed is True
        assert specialist == SpecialistAgents.AI_ARCHITECT
        assert confidence >= analyzer.ai_architect_threshold
    
    def test_analyze_request_prompt_engineer(self):
        """プロンプトエンジニア関連の要求を正しく識別できることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # プロンプトエンジニア関連テキスト
        text = "GPT-4のプロンプト最適化を支援してください。レスポンスの精度を上げたいです。"
        
        needed, specialist, confidence = analyzer.analyze_request(text)
        
        # 結果を確認
        assert needed is True
        assert specialist == SpecialistAgents.PROMPT_ENGINEER
        assert confidence >= analyzer.prompt_engineer_threshold
    
    def test_analyze_request_data_engineer(self):
        """データエンジニア関連の要求を正しく識別できることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # データエンジニア関連テキスト
        text = "データ抽出とクリーニングのパイプラインを作りたいです。CSVからPostgreSQLへのETLが必要です。"
        
        needed, specialist, confidence = analyzer.analyze_request(text)
        
        # 結果を確認
        assert needed is True
        assert specialist == SpecialistAgents.DATA_ENGINEER
        assert confidence >= analyzer.data_engineer_threshold
    
    def test_analyze_request_no_match(self):
        """専門エージェントが不要な要求を正しく識別できることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # 専門エージェント不要なテキスト
        text = "プロジェクトの進捗状況を教えてください。"
        
        needed, specialist, confidence = analyzer.analyze_request(text)
        
        # 結果を確認
        assert needed is False
        assert specialist is None
        assert confidence < max(
            analyzer.ai_architect_threshold,
            analyzer.prompt_engineer_threshold,
            analyzer.data_engineer_threshold
        )
    
    def test_analyze_request_with_context(self):
        """コンテキスト情報による判断調整が正しく行われることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # 通常はデータエンジニア不要なテキスト
        text = "このデータの取り扱いについてアドバイスください。"
        
        # コンテキストなしの場合（専門エージェント不要と判断される可能性が高い）
        needed_without_context, specialist_without_context, _ = analyzer.analyze_request(text)
        
        # データエンジニア指定のコンテキスト
        context = {"specialist_type": "data_engineer"}
        needed_with_context, specialist_with_context, _ = analyzer.analyze_request(text, context)
        
        # 結果を確認（コンテキストありの場合は専門エージェントが必要と判断される）
        assert needed_with_context is True
        assert specialist_with_context == SpecialistAgents.DATA_ENGINEER
    
    def test_calculate_confidence(self):
        """信頼度スコアの計算が正しく行われることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # スコア計算用のテストケース
        test_cases = [
            # (テキスト, パターンセット, 期待される結果範囲)
            ("システムアーキテクチャ設計をお願いします", analyzer.ai_architect_patterns, (0.4, 0.7)),  # 1つのパターンマッチで0.4
            ("", analyzer.ai_architect_patterns, (0.0, 0.0)),  # 空文字列
            ("アーキテクチャ設計とインフラ構築とスケーラビリティ確保", analyzer.ai_architect_patterns, (0.7, 1.0))  # 3つのパターンマッチで0.4+2*0.3=1.0
        ]
        
        for text, patterns, expected_range in test_cases:
            # プライベートメソッドをテスト
            score = analyzer._calculate_confidence(text, patterns)
            
            # 期待される範囲内であることを確認
            min_expected, max_expected = expected_range
            assert min_expected <= score <= max_expected, f"スコア {score} が範囲 {expected_range} 内であることを期待"
    
    def test_adjust_score_by_context(self):
        """コンテキストによるスコア調整が正しく行われることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # 基本スコア
        base_score = 0.5
        
        # 明示的な指定ありのコンテキスト
        explicit_context = {"specialist_type": "ai_architect"}
        adjusted_score1 = analyzer._adjust_score_by_context(base_score, explicit_context, "ai_architect")
        assert adjusted_score1 >= 0.8  # 0.8以上に引き上げられる
        
        # 優先度指定ありのコンテキスト
        priority_context = {"architecture_priority": 1.0}  # 最大優先度
        adjusted_score2 = analyzer._adjust_score_by_context(base_score, priority_context, "ai_architect")
        assert adjusted_score2 > base_score  # 元のスコアより大きくなる
        
        # 関連なしのコンテキスト
        unrelated_context = {"prompt_priority": 1.0}  # プロンプトエンジニア向け優先度
        adjusted_score3 = analyzer._adjust_score_by_context(base_score, unrelated_context, "ai_architect")
        assert adjusted_score3 == base_score  # 変化なし
    
    def test_get_probable_task_type(self):
        """要求テキストからタスク種別を推定できることを確認"""
        analyzer = SpecialistTriggerAnalyzer()
        
        # AIアーキテクト向けタスク種別
        ai_arch_text = "システムアーキテクチャの設計をお願いします。"
        ai_arch_task_type = analyzer.get_probable_task_type(SpecialistAgents.AI_ARCHITECT, ai_arch_text)
        assert ai_arch_task_type == TaskType.ARCHITECTURE_DESIGN
        
        # プロンプトエンジニア向けタスク種別
        prompt_text = "プロンプトの最適化をお願いします。"
        prompt_task_type = analyzer.get_probable_task_type(SpecialistAgents.PROMPT_ENGINEER, prompt_text)
        assert prompt_task_type == TaskType.PROMPT_OPTIMIZATION
        
        # データエンジニア向けタスク種別
        data_text = "データ抽出をお願いします。"
        data_task_type = analyzer.get_probable_task_type(SpecialistAgents.DATA_ENGINEER, data_text)
        assert data_task_type == TaskType.DATA_EXTRACTION


class TestHelperFunctions:
    """ヘルパー関数のテスト"""
    
    def test_analyze_specialist_need(self, sample_request_texts):
        """analyze_specialist_need関数が正しく動作することを確認"""
        with patch("utils.specialist_triggers.trigger_analyzer") as mock_analyzer:
            # モックの設定
            mock_analyzer.analyze_request.side_effect = lambda text, context=None: (
                (True, SpecialistAgents.AI_ARCHITECT, 0.8) if "アーキテクチャ" in text else
                (True, SpecialistAgents.PROMPT_ENGINEER, 0.7) if "プロンプト" in text else
                (True, SpecialistAgents.DATA_ENGINEER, 0.9) if "データ" in text else
                (False, None, 0.3)
            )
            
            # AIアーキテクト向けテキスト
            needed, specialist, confidence = analyze_specialist_need(sample_request_texts["ai_architect"])
            assert needed is True
            assert specialist == SpecialistAgents.AI_ARCHITECT
            
            # プロンプトエンジニア向けテキスト
            needed, specialist, confidence = analyze_specialist_need(sample_request_texts["prompt_engineer"])
            assert needed is True
            assert specialist == SpecialistAgents.PROMPT_ENGINEER
            
            # データエンジニア向けテキスト
            needed, specialist, confidence = analyze_specialist_need(sample_request_texts["data_engineer"])
            assert needed is True
            assert specialist == SpecialistAgents.DATA_ENGINEER
            
            # 一般的なテキスト
            needed, specialist, confidence = analyze_specialist_need(sample_request_texts["generic"])
            assert needed is False
            assert specialist is None
            
            # コンテキスト付きの呼び出し
            context = {"specialist_type": "ai_architect"}
            analyze_specialist_need(sample_request_texts["generic"], context)
            mock_analyzer.analyze_request.assert_called_with(sample_request_texts["generic"], context)
    
    @patch("utils.specialist_triggers.request_ai_architect_task")
    @patch("utils.specialist_triggers.request_prompt_engineer_task")
    @patch("utils.specialist_triggers.request_data_engineer_task")
    @patch("utils.specialist_triggers.analyze_specialist_need")
    def test_request_specialist_if_needed(
        self, mock_analyze, mock_data_task, mock_prompt_task, mock_arch_task, sample_request_texts
    ):
        """request_specialist_if_needed関数が正しく動作することを確認"""
        # 強制指定ありの場合
        mock_arch_task.return_value = "test_arch_task_id"
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text="テスト要求",
            force_type=SpecialistAgents.AI_ARCHITECT
        )
        assert task_id == "test_arch_task_id"
        mock_arch_task.assert_called_once()
        mock_analyze.assert_not_called()  # 分析は行われない
        
        # AIアーキテクトが必要な場合
        mock_analyze.reset_mock()
        mock_arch_task.reset_mock()
        mock_analyze.return_value = (True, SpecialistAgents.AI_ARCHITECT, 0.8)
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["ai_architect"]
        )
        assert task_id == "test_arch_task_id"
        mock_analyze.assert_called_once()
        mock_arch_task.assert_called_once()
        
        # プロンプトエンジニアが必要な場合
        mock_analyze.reset_mock()
        mock_prompt_task.reset_mock()
        mock_prompt_task.return_value = "test_prompt_task_id"
        mock_analyze.return_value = (True, SpecialistAgents.PROMPT_ENGINEER, 0.7)
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["prompt_engineer"]
        )
        assert task_id == "test_prompt_task_id"
        mock_analyze.assert_called_once()
        mock_prompt_task.assert_called_once()
        
        # データエンジニアが必要な場合
        mock_analyze.reset_mock()
        mock_data_task.reset_mock()
        mock_data_task.return_value = "test_data_task_id"
        mock_analyze.return_value = (True, SpecialistAgents.DATA_ENGINEER, 0.9)
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["data_engineer"]
        )
        assert task_id == "test_data_task_id"
        mock_analyze.assert_called_once()
        mock_data_task.assert_called_once()
        
        # 専門エージェントが不要な場合
        mock_analyze.reset_mock()
        mock_analyze.return_value = (False, None, 0.3)
        task_id = request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["generic"]
        )
        assert task_id is None
        mock_analyze.assert_called_once()
        
        # コンテキスト付きの呼び出し
        mock_analyze.reset_mock()
        mock_arch_task.reset_mock()
        mock_analyze.return_value = (True, SpecialistAgents.AI_ARCHITECT, 0.8)
        context = {"project": "test_project"}
        request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["ai_architect"],
            context=context
        )
        mock_analyze.assert_called_with(sample_request_texts["ai_architect"], context)
        # アーキテクトタスク依頼にコンテキストが渡されることを確認
        assert mock_arch_task.call_args.kwargs["context"] == context
        
        # 優先度指定ありの呼び出し
        mock_analyze.reset_mock()
        mock_arch_task.reset_mock()
        mock_analyze.return_value = (True, SpecialistAgents.AI_ARCHITECT, 0.8)
        priority = TaskPriority.HIGH
        request_specialist_if_needed(
            core_agent=CoreAgents.ENGINEER,
            request_text=sample_request_texts["ai_architect"],
            priority=priority
        )
        # アーキテクトタスク依頼に優先度が渡されることを確認
        assert mock_arch_task.call_args.kwargs["priority"] == priority 