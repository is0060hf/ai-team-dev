"""
Webフレームワーク用ツールモジュール。
Flaskフレームワーク、Djangoフレームワーク、FastAPIフレームワークなどのツールを提供します。
"""

import os
import sys
import re
import json
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path

from crewai.tools import BaseTool
from utils.logger import get_logger

# 各フレームワーク固有のツールをインポート
try:
    from tools.flask_tools import FlaskRouteTool, FlaskAppGeneratorTool, FlaskRunnerTool
except ImportError:
    # Flask用ツールが見つからない場合はNone
    FlaskRouteTool = None
    FlaskAppGeneratorTool = None
    FlaskRunnerTool = None

try:
    from tools.django_tools import DjangoProjectGeneratorTool, DjangoModelGeneratorTool, DjangoRunnerTool
except ImportError:
    # Django用ツールが見つからない場合はNone
    DjangoProjectGeneratorTool = None
    DjangoModelGeneratorTool = None
    DjangoRunnerTool = None

try:
    from tools.fastapi_tools import FastAPIEndpointTool, FastAPIAppGeneratorTool, FastAPIRunnerTool
except ImportError:
    # FastAPI用ツールが見つからない場合はNone
    FastAPIEndpointTool = None
    FastAPIAppGeneratorTool = None
    FastAPIRunnerTool = None

logger = get_logger("web_frameworks")

class WebFrameworkSelectorTool(BaseTool):
    """Webフレームワーク選択ツール"""
    
    name: str = "Webフレームワーク選択"
    description: str = "プロジェクトの要件に基づいて最適なWebフレームワークを選択します。"
    
    def _run(self, 
            requirements: Dict[str, Any] = None, 
            prefer_lightweight: bool = False,
            need_admin: bool = False,
            need_rest_api: bool = False,
            team_experience: Optional[str] = None) -> str:
        """
        要件に基づいて最適なWebフレームワークを選択
        
        Args:
            requirements: 要件の辞書 {"db_complexity": 1-5, "scale": 1-5, "time_constraint": 1-5, ...}
            prefer_lightweight: 軽量フレームワークを優先するか
            need_admin: 管理画面が必要か
            need_rest_api: REST APIが必要か
            team_experience: チームの経験 ("Django", "Flask", "FastAPI", "None" など)
            
        Returns:
            str: 推奨されるフレームワークと理由の説明
        """
        logger.info("Webフレームワーク選択ツールが呼び出されました")
        
        # デフォルト要件
        if not requirements:
            requirements = {
                "db_complexity": 3,  # 1-5 (低-高)
                "scale": 3,          # 1-5 (小-大)
                "time_constraint": 3, # 1-5 (緩-厳)
                "customization": 3,   # 1-5 (低-高)
            }
        
        # スコア初期化
        scores = {
            "Django": 0,
            "Flask": 0,
            "FastAPI": 0
        }
        
        # データベース複雑性
        if requirements.get("db_complexity", 3) >= 4:
            scores["Django"] += 2
            scores["Flask"] += 0
            scores["FastAPI"] += 1
        else:
            scores["Django"] += 1
            scores["Flask"] += 2
            scores["FastAPI"] += 2
        
        # プロジェクト規模
        if requirements.get("scale", 3) >= 4:
            scores["Django"] += 2
            scores["Flask"] += 0
            scores["FastAPI"] += 1
        else:
            scores["Django"] += 0
            scores["Flask"] += 2
            scores["FastAPI"] += 2
        
        # 時間制約
        if requirements.get("time_constraint", 3) >= 4:
            scores["Django"] += 1
            scores["Flask"] += 1
            scores["FastAPI"] += 2
        else:
            scores["Django"] += 2
            scores["Flask"] += 1
            scores["FastAPI"] += 1
        
        # カスタマイズ性
        if requirements.get("customization", 3) >= 4:
            scores["Django"] += 0
            scores["Flask"] += 2
            scores["FastAPI"] += 2
        else:
            scores["Django"] += 2
            scores["Flask"] += 1
            scores["FastAPI"] += 1
        
        # 軽量性
        if prefer_lightweight:
            scores["Django"] -= 2
            scores["Flask"] += 2
            scores["FastAPI"] += 2
        
        # 管理画面
        if need_admin:
            scores["Django"] += 3
            scores["Flask"] -= 1
            scores["FastAPI"] -= 1
        
        # REST API
        if need_rest_api:
            scores["Django"] += 1
            scores["Flask"] += 1
            scores["FastAPI"] += 3
        
        # チーム経験
        if team_experience:
            if team_experience.lower() == "django":
                scores["Django"] += 2
            elif team_experience.lower() == "flask":
                scores["Flask"] += 2
            elif team_experience.lower() == "fastapi":
                scores["FastAPI"] += 2
        
        # 結果
        best_framework = max(scores, key=scores.get)
        
        # フレームワーク別の説明文
        explanations = {
            "Django": """
Djangoをお勧めします。Djangoは「バッテリー込み」のフルスタックフレームワークで、以下の特徴があります：

- 強力なORM、管理画面、フォーム処理、認証など多くの機能が組み込まれている
- 大規模で複雑なデータベース駆動アプリケーションに適している
- プロジェクト構造が規定されており、チーム開発で一貫性を保ちやすい
- セキュリティ機能が充実
- 豊富なドキュメントとコミュニティサポート

ただし、軽量アプリケーションの場合、オーバーヘッドが大きいことに注意が必要です。
            """,
            
            "Flask": """
Flaskをお勧めします。Flaskは軽量でカスタマイズ性の高いマイクロフレームワークです：

- 最小限の機能から始めて、必要な拡張機能を追加していくアプローチ
- 小〜中規模のプロジェクトに適している
- 自由度が高く、特殊な要件にも対応しやすい
- 学習曲線が緩やか
- プロジェクト構造を柔軟に設計可能

ただし、大規模プロジェクトでは、多くの機能を自分で実装または統合する必要があります。
            """,
            
            "FastAPI": """
FastAPIをお勧めします。FastAPIは最新のPython非同期フレームワークです：

- 高速なパフォーマンス（Starletteベース、非同期処理）
- 自動APIドキュメント生成（OpenAPI）
- 型ヒントによる優れたIDEサポートとバリデーション（Pydanticベース）
- RESTful APIの構築に最適
- WebSocketsサポート
- 最新のPython機能（Python 3.6+）活用

APIバックエンドの開発に特に適していますが、フロントエンド統合には追加作業が必要です。
            """
        }
        
        result = f"## 推奨フレームワーク: {best_framework}\n\n"
        result += explanations[best_framework]
        
        # スコア表示（デバッグ用）
        result += "\n\n### フレームワーク評価スコア:\n"
        for fw, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            result += f"- {fw}: {score}点\n"
        
        # 利用可能なツール情報
        available_tools = {
            "Django": DjangoProjectGeneratorTool is not None,
            "Flask": FlaskAppGeneratorTool is not None,
            "FastAPI": FastAPIAppGeneratorTool is not None
        }
        
        result += "\n### 利用可能なツール:\n"
        for fw, available in available_tools.items():
            status = "✅ 利用可能" if available else "❌ 利用不可"
            result += f"- {fw}: {status}\n"
        
        return result

# 使用可能なすべてのフレームワークツールを取得
def get_available_framework_tools() -> Dict[str, List[BaseTool]]:
    """
    使用可能なすべてのWebフレームワークツールを取得する
    
    Returns:
        Dict[str, List[BaseTool]]: フレームワーク名をキーとするツールリストの辞書
    """
    tools = {}
    
    # Flaskツール
    flask_tools = []
    if FlaskRouteTool:
        flask_tools.append(FlaskRouteTool())
    if FlaskAppGeneratorTool:
        flask_tools.append(FlaskAppGeneratorTool())
    if FlaskRunnerTool:
        flask_tools.append(FlaskRunnerTool())
    
    if flask_tools:
        tools["Flask"] = flask_tools
    
    # Djangoツール
    django_tools = []
    if DjangoProjectGeneratorTool:
        django_tools.append(DjangoProjectGeneratorTool())
    if DjangoModelGeneratorTool:
        django_tools.append(DjangoModelGeneratorTool())
    if DjangoRunnerTool:
        django_tools.append(DjangoRunnerTool())
    
    if django_tools:
        tools["Django"] = django_tools
    
    # FastAPIツール
    fastapi_tools = []
    if FastAPIEndpointTool:
        fastapi_tools.append(FastAPIEndpointTool())
    if FastAPIAppGeneratorTool:
        fastapi_tools.append(FastAPIAppGeneratorTool())
    if FastAPIRunnerTool:
        fastapi_tools.append(FastAPIRunnerTool())
    
    if fastapi_tools:
        tools["FastAPI"] = fastapi_tools
    
    # フレームワーク選択ツールも追加
    tools["selector"] = [WebFrameworkSelectorTool()]
    
    return tools

# 使用可能なフレームワークツールのエクスポート
available_framework_tools = get_available_framework_tools()

# ツールのエクスポート
__all__ = [
    'WebFrameworkSelectorTool',
    'FlaskRouteTool',
    'FlaskAppGeneratorTool', 
    'FlaskRunnerTool',
    'DjangoProjectGeneratorTool',
    'DjangoModelGeneratorTool',
    'DjangoRunnerTool',
    'FastAPIEndpointTool',
    'FastAPIAppGeneratorTool',
    'FastAPIRunnerTool'
] 