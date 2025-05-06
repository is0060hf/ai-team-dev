"""
プロンプト最適化のためのユーティリティモジュール。
様々なLLMに対するプロンプトを最適化するための機能を提供します。
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
import datetime

from utils.logger import get_agent_logger

logger = get_agent_logger("prompt_optimization")


class PromptType(Enum):
    """プロンプトタイプの列挙型"""
    CHAT = "chat"
    INSTRUCTION = "instruction"
    COMPLETION = "completion"
    QA = "qa"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    COT = "chain_of_thought"
    CUSTOM = "custom"


class PromptTemplate:
    """
    プロンプトテンプレートクラス。
    再利用可能なプロンプトテンプレートを定義し、変数を置換する機能を提供します。
    """
    
    def __init__(self, template: str, template_type: PromptType = PromptType.INSTRUCTION, metadata: Dict[str, Any] = None):
        """
        Args:
            template: テンプレート文字列（変数は {{variable_name}} の形式）
            template_type: テンプレートの種類
            metadata: テンプレートに関するメタデータ
        """
        self.template = template
        self.template_type = template_type
        self.metadata = metadata or {}
        self._validate_template()
    
    def _validate_template(self):
        """テンプレートの形式を検証"""
        # 変数の形式を検証（{{variable}}）
        variables = self.extract_variables()
        
        for var in variables:
            if not re.match(r'^[a-zA-Z0-9_]+$', var):
                logger.warning(f"不正な変数名: {var}")
    
    def extract_variables(self) -> List[str]:
        """テンプレートから変数名を抽出"""
        pattern = r'{{([a-zA-Z0-9_]+)}}'
        return re.findall(pattern, self.template)
    
    def format(self, **kwargs) -> str:
        """
        テンプレートの変数を置換してプロンプトを生成
        
        Args:
            **kwargs: 変数名と値のマッピング
            
        Returns:
            str: 変数が置換されたプロンプト
        """
        result = self.template
        
        # 必要な変数が提供されているか確認
        variables = self.extract_variables()
        missing_vars = [var for var in variables if var not in kwargs]
        
        if missing_vars:
            logger.warning(f"変数が不足しています: {', '.join(missing_vars)}")
        
        # 変数の置換
        for var_name, var_value in kwargs.items():
            pattern = r'{{' + var_name + r'}}'
            result = re.sub(pattern, str(var_value), result)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """テンプレートを辞書形式で取得"""
        return {
            "template": self.template,
            "type": self.template_type.value,
            "metadata": self.metadata,
            "variables": self.extract_variables()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptTemplate':
        """辞書からテンプレートを生成"""
        return cls(
            template=data["template"],
            template_type=PromptType(data["type"]),
            metadata=data.get("metadata", {})
        )


class PromptFormatter:
    """
    プロンプトフォーマッタクラス。
    異なるLLMやフォーマットに対応するプロンプト変換機能を提供します。
    """
    
    @staticmethod
    def to_openai_chat(prompt: str, system_message: str = None) -> List[Dict[str, str]]:
        """
        OpenAI Chat APIフォーマットへの変換
        
        Args:
            prompt: プロンプト文字列
            system_message: システムメッセージ（オプション）
            
        Returns:
            List[Dict[str, str]]: OpenAI Chat API用のメッセージリスト
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        return messages
    
    @staticmethod
    def to_openai_completion(prompt: str) -> str:
        """
        OpenAI Completion APIフォーマットへの変換
        
        Args:
            prompt: プロンプト文字列
            
        Returns:
            str: OpenAI Completion API用のプロンプト
        """
        return prompt
    
    @staticmethod
    def to_anthropic_format(prompt: str, system_message: str = None) -> str:
        """
        Anthropic Claude APIフォーマットへの変換
        
        Args:
            prompt: プロンプト文字列
            system_message: システムメッセージ（オプション）
            
        Returns:
            str: Anthropic Claude API用のプロンプト
        """
        formatted_prompt = ""
        
        if system_message:
            formatted_prompt = f"{system_message}\n\nHuman: {prompt}\n\nAssistant: "
        else:
            formatted_prompt = f"Human: {prompt}\n\nAssistant: "
        
        return formatted_prompt
    
    @staticmethod
    def to_gemini_format(prompt: str, system_message: str = None) -> Dict[str, Any]:
        """
        Google Gemini APIフォーマットへの変換
        
        Args:
            prompt: プロンプト文字列
            system_message: システムメッセージ（オプション）
            
        Returns:
            Dict[str, Any]: Gemini API用のリクエスト形式
        """
        content = []
        
        if system_message:
            content.append({"role": "system", "content": system_message})
        
        content.append({"role": "user", "content": prompt})
        
        return {"contents": content}


class PromptOptimizer:
    """
    プロンプト最適化クラス。
    プロンプトの問題点を分析し、最適化する機能を提供します。
    """
    
    @staticmethod
    def analyze_prompt(prompt: str) -> Dict[str, Any]:
        """
        プロンプトの問題点を分析
        
        Args:
            prompt: 分析対象のプロンプト
            
        Returns:
            Dict[str, Any]: 分析結果
        """
        issues = []
        recommendations = []
        
        # プロンプトの基本構造をチェック
        if len(prompt.strip()) < 20:
            issues.append("プロンプトが短すぎる")
            recommendations.append("詳細な指示と期待する出力形式を追加する")
        
        # 指示の明確さをチェック
        if not re.search(r'指示|命令|タスク|実行|作成|行[いう]', prompt):
            issues.append("明確な指示が不足している")
            recommendations.append("明示的な指示を含める（例: 「以下の条件に基づいて分析してください」）")
        
        # 出力形式の指定をチェック
        if not re.search(r'出力|フォーマット|形式|返[すし]|応答', prompt):
            issues.append("出力形式の指定がない")
            recommendations.append("期待する出力形式を明示する（例: 「以下の形式で回答してください」）")
        
        # 変数の使用形式をチェック
        vars_single_brace = re.findall(r'{([^{}]+)}', prompt)
        vars_double_brace = re.findall(r'{{([^{}]+)}}', prompt)
        
        if vars_single_brace and not vars_double_brace:
            issues.append("変数指定に単一中括弧を使用している")
            recommendations.append("変数には二重中括弧を使用する（例: {{variable}}）")
        
        # 分析結果を整形
        return {
            "issues": issues,
            "recommendations": recommendations,
            "structure": {
                "has_clear_instruction": bool(re.search(r'指示|命令|タスク', prompt)),
                "has_output_format": bool(re.search(r'出力|フォーマット|形式', prompt)),
                "has_constraints": bool(re.search(r'制約|制限|条件', prompt)),
                "has_examples": bool(re.search(r'例|サンプル|参考', prompt))
            },
            "variables": vars_double_brace,
            "length": len(prompt),
            "sections": [line.strip() for line in prompt.split('\n\n') if line.strip()]
        }
    
    @staticmethod
    def optimize_prompt(prompt: str, analysis: Dict[str, Any] = None) -> str:
        """
        プロンプトを最適化
        
        Args:
            prompt: 最適化対象のプロンプト
            analysis: 事前の分析結果（オプション）
            
        Returns:
            str: 最適化されたプロンプト
        """
        if analysis is None:
            analysis = PromptOptimizer.analyze_prompt(prompt)
        
        optimized = prompt
        
        # 基本構造の改善
        structure = analysis["structure"]
        sections = []
        
        # 既存のセクションを取得
        current_sections = [line.strip() for line in optimized.split('\n\n') if line.strip()]
        
        # 各推奨事項に基づいて最適化
        if not structure["has_clear_instruction"]:
            sections.append("# 指示\n以下の条件に従ってタスクを実行してください。")
            sections.extend(current_sections)
        else:
            sections = current_sections
        
        if not structure["has_constraints"]:
            sections.append("# 制約\n- 指定された形式で回答してください\n- 不明な場合は推測せず、情報不足と明示してください")
        
        if not structure["has_output_format"]:
            sections.append("# 出力フォーマット\n期待する形式で回答してください。")
        
        # 変数形式の修正
        optimized = "\n\n".join(sections)
        vars_single_brace = re.findall(r'{([^{}]+)}', optimized)
        
        for var in vars_single_brace:
            if not re.match(r'[{}]', var):  # 既に中括弧を含まない変数名のみ
                optimized = optimized.replace(f"{{{var}}}", f"{{{{{var}}}}}")
        
        return optimized
    
    @staticmethod
    def evaluate_prompt(prompt: str, criteria: Dict[str, float] = None) -> Dict[str, Any]:
        """
        プロンプトを評価
        
        Args:
            prompt: 評価対象のプロンプト
            criteria: 評価基準と重み付け（オプション）
            
        Returns:
            Dict[str, Any]: 評価結果
        """
        # デフォルトの評価基準
        if criteria is None:
            criteria = {
                "明確さ": 0.25,
                "具体性": 0.25,
                "簡潔さ": 0.2,
                "構造化": 0.15,
                "一貫性": 0.15
            }
        
        # 分析結果を取得
        analysis = PromptOptimizer.analyze_prompt(prompt)
        
        # 各基準でスコア計算（簡易版）
        scores = {}
        
        # 明確さの評価
        clarity_score = 0.5  # ベーススコア
        if analysis["structure"]["has_clear_instruction"]:
            clarity_score += 0.25
        if analysis["structure"]["has_output_format"]:
            clarity_score += 0.25
        scores["明確さ"] = min(clarity_score, 1.0)
        
        # 具体性の評価
        specificity_score = 0.3  # ベーススコア
        if analysis["structure"]["has_constraints"]:
            specificity_score += 0.3
        if analysis["structure"]["has_examples"]:
            specificity_score += 0.4
        scores["具体性"] = min(specificity_score, 1.0)
        
        # 簡潔さの評価
        if analysis["length"] < 100:
            conciseness_score = 0.9
        elif analysis["length"] < 300:
            conciseness_score = 0.7
        elif analysis["length"] < 600:
            conciseness_score = 0.5
        else:
            conciseness_score = 0.3
        scores["簡潔さ"] = conciseness_score
        
        # 構造化の評価
        structure_score = 0.2  # ベーススコア
        if len(analysis["sections"]) >= 3:
            structure_score += 0.4
        if re.search(r'#|\d+\.|•|-|\*', prompt):  # 見出しや箇条書きがある
            structure_score += 0.4
        scores["構造化"] = min(structure_score, 1.0)
        
        # 一貫性の評価
        consistency_score = 0.6  # ベーススコア
        if analysis["issues"]:
            consistency_score -= 0.1 * len(analysis["issues"])
        scores["一貫性"] = max(consistency_score, 0.0)
        
        # 総合スコア計算
        weighted_score = sum([scores[criterion] * weight for criterion, weight in criteria.items()])
        
        return {
            "scores": scores,
            "weighted_score": weighted_score,
            "analysis": analysis,
            "timestamp": datetime.datetime.now().isoformat()
        }


# プリセットプロンプトテンプレート集
PRESET_TEMPLATES = {
    "classification": PromptTemplate(
        template="""
# 指示
以下のテキストを次のカテゴリに分類してください:
{{categories}}

# 制約
- 必ず上記のカテゴリの中から1つだけ選んでください
- カテゴリ名のみを出力してください
- 複数のカテゴリが当てはまる場合は、最も関連性の高いものを選択してください

# 入力テキスト
{{input_text}}

# 出力
""",
        template_type=PromptType.CLASSIFICATION,
        metadata={"description": "テキスト分類用のテンプレート"}
    ),
    
    "summarization": PromptTemplate(
        template="""
# 指示
以下のテキストの要点を抽出し、簡潔に要約してください。

# 制約
- 要約は{{max_length}}以内に収めてください
- 原文の主要な情報を漏らさないでください
- 要約は客観的であり、新しい情報や意見を追加しないでください
- {{format_instruction}}

# 入力テキスト
{{input_text}}

# 出力
""",
        template_type=PromptType.SUMMARIZATION,
        metadata={"description": "テキスト要約用のテンプレート"}
    ),
    
    "qa": PromptTemplate(
        template="""
# 指示
与えられたコンテキスト情報に基づいて、質問に正確に答えてください。

# 制約
- コンテキスト内の情報のみを使用してください
- コンテキストに情報がない場合は「情報がありません」と回答してください
- 回答は{{response_style}}にしてください
- 推測や不確かな情報は含めないでください

# コンテキスト
{{context}}

# 質問
{{question}}

# 出力
""",
        template_type=PromptType.QA,
        metadata={"description": "質問応答用のテンプレート"}
    ),
    
    "chain_of_thought": PromptTemplate(
        template="""
# 指示
以下の問題を解いてください。段階的に考えを進めて、最終的な答えに到達してください。

# 例題
{{example_problem}}

# 思考のステップ
{{example_steps}}

# 問題
{{problem}}

# 回答（段階的に考え方を示してください）
""",
        template_type=PromptType.COT,
        metadata={"description": "Chain of Thought用のテンプレート"}
    )
}


def get_template(template_name: str) -> Optional[PromptTemplate]:
    """
    プリセットテンプレートを取得
    
    Args:
        template_name: テンプレート名
        
    Returns:
        Optional[PromptTemplate]: テンプレートオブジェクト（存在しない場合はNone）
    """
    return PRESET_TEMPLATES.get(template_name)


def create_prompt_from_template(template_name: str, **kwargs) -> str:
    """
    テンプレートを使用してプロンプトを生成
    
    Args:
        template_name: テンプレート名
        **kwargs: テンプレート変数の値
        
    Returns:
        str: 生成されたプロンプト
    """
    template = get_template(template_name)
    if not template:
        logger.error(f"テンプレート '{template_name}' が見つかりません")
        return ""
    
    return template.format(**kwargs)


def optimize_existing_prompt(prompt: str, task_type: str = None, performance_issues: List[str] = None) -> Dict[str, Any]:
    """
    既存のプロンプトを分析・最適化
    
    Args:
        prompt: 最適化対象のプロンプト
        task_type: タスクタイプ（分類、要約など）
        performance_issues: 既知のパフォーマンス問題リスト
        
    Returns:
        Dict[str, Any]: 最適化結果（元のプロンプト、最適化されたプロンプト、分析、評価）
    """
    # プロンプト分析
    analysis = PromptOptimizer.analyze_prompt(prompt)
    
    # 既知の問題点を追加
    if performance_issues:
        analysis["issues"].extend(performance_issues)
        analysis["issues"] = list(set(analysis["issues"]))  # 重複除去
    
    # プロンプト最適化
    optimized_prompt = PromptOptimizer.optimize_prompt(prompt, analysis)
    
    # タスクタイプに基づく追加最適化
    if task_type and task_type in PRESET_TEMPLATES:
        template = PRESET_TEMPLATES[task_type]
        template_structure = [section.strip() for section in template.template.split('\n\n') if section.strip()]
        
        # テンプレートの構造を参考に、最適化プロンプトの構造を改善
        if len(template_structure) > 0:
            # タスク特有のセクションや制約がある場合は参考にする
            for section in template_structure:
                if section.startswith("# 制約") and "# 制約" not in optimized_prompt:
                    optimized_prompt += f"\n\n{section}"
                elif section.startswith("# 出力") and "# 出力" not in optimized_prompt:
                    optimized_prompt += f"\n\n{section}"
    
    # 最適化されたプロンプトを評価
    evaluation = PromptOptimizer.evaluate_prompt(optimized_prompt)
    
    return {
        "original_prompt": prompt,
        "optimized_prompt": optimized_prompt,
        "analysis": analysis,
        "evaluation": evaluation,
        "improvement": evaluation["weighted_score"] - PromptOptimizer.evaluate_prompt(prompt)["weighted_score"]
    }


def compare_prompts(prompts: List[str], test_cases: List[str] = None) -> Dict[str, Any]:
    """
    複数のプロンプトを比較評価
    
    Args:
        prompts: 比較するプロンプトのリスト
        test_cases: テストケースのリスト（オプション）
        
    Returns:
        Dict[str, Any]: 比較結果
    """
    results = []
    best_score = 0
    best_index = 0
    
    for i, prompt in enumerate(prompts):
        # プロンプト評価
        evaluation = PromptOptimizer.evaluate_prompt(prompt)
        
        # 最高スコアの更新
        if evaluation["weighted_score"] > best_score:
            best_score = evaluation["weighted_score"]
            best_index = i
        
        results.append({
            "prompt": prompt,
            "evaluation": evaluation
        })
    
    return {
        "results": results,
        "best_prompt_index": best_index,
        "best_score": best_score,
        "best_prompt": prompts[best_index]
    }


# メインの最適化関数
def optimize_prompt(prompt: str = None, 
                    template_name: str = None, 
                    template_vars: Dict[str, Any] = None,
                    task_type: str = None,
                    performance_issues: List[str] = None,
                    target_model: str = "openai",
                    system_message: str = None) -> Dict[str, Any]:
    """
    プロンプト最適化のメイン関数
    
    Args:
        prompt: 最適化対象のプロンプト（直接指定する場合）
        template_name: テンプレート名（テンプレートから生成する場合）
        template_vars: テンプレート変数（テンプレートから生成する場合）
        task_type: タスクタイプ
        performance_issues: 既知のパフォーマンス問題
        target_model: ターゲットモデル（openai, anthropic, gemini）
        system_message: システムメッセージ（オプション）
        
    Returns:
        Dict[str, Any]: 最適化結果
    """
    final_prompt = prompt
    
    # テンプレートからプロンプトを生成
    if template_name and template_name in PRESET_TEMPLATES:
        if template_vars is None:
            template_vars = {}
        
        template = PRESET_TEMPLATES[template_name]
        final_prompt = template.format(**template_vars)
        task_type = template.template_type.value
    
    # プロンプトが指定されていない場合はエラー
    if not final_prompt:
        logger.error("プロンプトまたはテンプレートが指定されていません")
        return {"error": "プロンプトまたはテンプレートが指定されていません"}
    
    # プロンプト最適化
    optimization_result = optimize_existing_prompt(final_prompt, task_type, performance_issues)
    optimized_prompt = optimization_result["optimized_prompt"]
    
    # ターゲットモデルに合わせてフォーマット
    formatted_prompt = None
    if target_model == "openai":
        formatted_prompt = PromptFormatter.to_openai_chat(optimized_prompt, system_message)
    elif target_model == "anthropic":
        formatted_prompt = PromptFormatter.to_anthropic_format(optimized_prompt, system_message)
    elif target_model == "gemini":
        formatted_prompt = PromptFormatter.to_gemini_format(optimized_prompt, system_message)
    else:
        formatted_prompt = optimized_prompt
    
    # 結果を返す
    return {
        "original_prompt": final_prompt,
        "optimized_prompt": optimized_prompt,
        "formatted_prompt": formatted_prompt,
        "target_model": target_model,
        "analysis": optimization_result["analysis"],
        "evaluation": optimization_result["evaluation"],
        "improvement": optimization_result["improvement"]
    } 