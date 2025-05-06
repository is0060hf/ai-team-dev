"""
Flaskフレームワーク用ツールモジュール。
Flaskアプリケーションのルート定義、設定、実行などを支援するツールを提供します。
"""

import os
import re
import json
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Union, Tuple
from contextlib import contextmanager
from pathlib import Path

from crewai.tools import BaseTool
from utils.logger import get_logger

logger = get_logger("flask_tools")

class FlaskRouteTool(BaseTool):
    """Flaskルート定義サポートツール"""
    
    name: str = "Flaskルート定義"
    description: str = "Flaskアプリケーションのルート（エンドポイント）を定義・生成します。"
    
    def _run(self, 
            route_path: str, 
            http_methods: str = "GET",
            function_name: Optional[str] = None,
            function_body: Optional[str] = None) -> str:
        """
        Flaskルートの定義コードを生成
        
        Args:
            route_path: ルートパス（例: "/users" や "/api/items/<item_id>"）
            http_methods: サポートするHTTPメソッド（例: "GET" や "GET,POST"）
            function_name: ルートハンドラ関数名（省略時は自動生成）
            function_body: ルートハンドラ関数の中身（省略時はシンプルなレスポンスを返す関数を生成）
            
        Returns:
            str: 生成されたFlaskルート定義コード
        """
        logger.info(f"Flaskルート定義ツールが呼び出されました: {route_path}")
        
        # ルートパスからデフォルトの関数名を生成
        if not function_name:
            # 先頭の/を削除し、その他の/と<>をアンダースコアに置換して関数名生成
            clean_path = route_path.strip("/").replace("/", "_").replace("<", "").replace(">", "")
            function_name = clean_path or "index"
        
        # HTTPメソッドのリスト化
        http_methods_list = [method.strip().upper() for method in http_methods.split(",")]
        http_methods_str = ", ".join([f'"{method}"' for method in http_methods_list])
        
        # デフォルトの関数内容
        if not function_body:
            function_body = self._generate_default_function_body(route_path, http_methods_list)
        
        # Flaskルート定義コードを生成
        code = f'''
@app.route("{route_path}", methods=[{http_methods_str}])
def {function_name}():
{self._indent_code(function_body, 4)}
'''
        
        return code.strip()
    
    def _generate_default_function_body(self, route_path: str, http_methods: List[str]) -> str:
        """デフォルトの関数内容を生成"""
        
        # パスパラメータ（<param>形式）を抽出
        params = re.findall(r'<([^>]+)>', route_path)
        
        # GETメソッドの場合
        if "GET" in http_methods:
            if params:
                param_dict = ", ".join([f'"{p}": {p}' for p in params])
                return f'return jsonify({{{param_dict}}})'
            else:
                return 'return jsonify({"message": "Success"})'
        
        # POSTメソッドの場合
        elif "POST" in http_methods:
            return '''data = request.get_json()
if not data:
    return jsonify({"error": "Invalid request"}), 400
return jsonify({"message": "Created", "data": data}), 201'''
        
        # PUTメソッドの場合
        elif "PUT" in http_methods and params:
            return '''data = request.get_json()
if not data:
    return jsonify({"error": "Invalid request"}), 400
return jsonify({"message": "Updated", "data": data})'''
        
        # DELETEメソッドの場合
        elif "DELETE" in http_methods and params:
            return f'return jsonify({"message": "Deleted"}), 200'
        
        # その他のメソッド
        else:
            return 'return jsonify({"message": "Endpoint called"})'
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """コードを指定された空白数でインデント"""
        prefix = " " * spaces
        return "\n".join(prefix + line for line in code.split("\n"))

class FlaskAppGeneratorTool(BaseTool):
    """Flaskアプリ生成ツール"""
    
    name: str = "Flaskアプリ生成"
    description: str = "基本的なFlaskアプリケーションのスケルトンコードを生成します。"
    
    def _run(self, 
            app_name: str = "flask_app",
            include_templates: bool = True,
            include_static: bool = True,
            use_blueprints: bool = False,
            api_mode: bool = False) -> str:
        """
        Flaskアプリケーションのスケルトンコードを生成
        
        Args:
            app_name: アプリケーション名
            include_templates: テンプレートディレクトリを含めるか
            include_static: 静的ファイルディレクトリを含めるか
            use_blueprints: Blueprintを使用するか
            api_mode: APIモードで生成するか（API用のコードを生成）
            
        Returns:
            str: 生成されたFlaskアプリケーションの構造とファイル内容
        """
        logger.info(f"Flaskアプリ生成ツールが呼び出されました: {app_name}")
        
        # アプリケーションの基本構造を定義
        app_structure = [
            f"{app_name}/",
            f"{app_name}/__init__.py",
            f"{app_name}/app.py",
            f"{app_name}/config.py",
            f"{app_name}/requirements.txt"
        ]
        
        if include_templates:
            app_structure.extend([
                f"{app_name}/templates/",
                f"{app_name}/templates/base.html",
                f"{app_name}/templates/index.html"
            ])
        
        if include_static:
            app_structure.extend([
                f"{app_name}/static/",
                f"{app_name}/static/css/",
                f"{app_name}/static/css/style.css",
                f"{app_name}/static/js/",
                f"{app_name}/static/js/main.js"
            ])
        
        if use_blueprints:
            app_structure.extend([
                f"{app_name}/blueprints/",
                f"{app_name}/blueprints/__init__.py",
                f"{app_name}/blueprints/main/__init__.py",
                f"{app_name}/blueprints/main/routes.py"
            ])
            
            if api_mode:
                app_structure.extend([
                    f"{app_name}/blueprints/api/__init__.py",
                    f"{app_name}/blueprints/api/routes.py"
                ])
        
        # ファイル内容を生成
        file_contents = {}
        
        # __init__.py
        file_contents[f"{app_name}/__init__.py"] = '# Flask application package'
        
        # app.py
        if use_blueprints:
            app_py_content = self._generate_blueprint_app_py(app_name, include_templates, api_mode)
        else:
            app_py_content = self._generate_simple_app_py(app_name, include_templates, api_mode)
        file_contents[f"{app_name}/app.py"] = app_py_content
        
        # config.py
        file_contents[f"{app_name}/config.py"] = self._generate_config_py(app_name)
        
        # requirements.txt
        file_contents[f"{app_name}/requirements.txt"] = self._generate_requirements_txt(api_mode)
        
        # HTML テンプレート
        if include_templates:
            file_contents[f"{app_name}/templates/base.html"] = self._generate_base_template()
            file_contents[f"{app_name}/templates/index.html"] = self._generate_index_template()
        
        # 静的ファイル
        if include_static:
            file_contents[f"{app_name}/static/css/style.css"] = "/* Custom CSS styles */\nbody {\n    font-family: Arial, sans-serif;\n}"
            file_contents[f"{app_name}/static/js/main.js"] = "// Custom JavaScript"
        
        # Blueprint関連ファイル
        if use_blueprints:
            file_contents[f"{app_name}/blueprints/__init__.py"] = "# Blueprints package"
            file_contents[f"{app_name}/blueprints/main/__init__.py"] = self._generate_blueprint_init("main")
            file_contents[f"{app_name}/blueprints/main/routes.py"] = self._generate_main_blueprint_routes(include_templates)
            
            if api_mode:
                file_contents[f"{app_name}/blueprints/api/__init__.py"] = self._generate_blueprint_init("api")
                file_contents[f"{app_name}/blueprints/api/routes.py"] = self._generate_api_blueprint_routes()
        
        # 結果をフォーマット
        result = f"## Flaskアプリケーション: {app_name}\n\n"
        result += "### ディレクトリ構造:\n```\n"
        result += "\n".join(app_structure)
        result += "\n```\n\n"
        
        result += "### ファイル内容:\n\n"
        for file_path, content in file_contents.items():
            result += f"#### {file_path}\n```python\n{content}\n```\n\n"
        
        return result.strip()
    
    def _generate_simple_app_py(self, app_name: str, include_templates: bool, api_mode: bool) -> str:
        """シンプルなapp.pyを生成"""
        code = f'''from flask import Flask, jsonify, request{", render_template" if include_templates else ""}
import os
from config import config

app = Flask(__name__)

# 環境設定を読み込む
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

@app.route('/')
def index():
'''
        
        if include_templates and not api_mode:
            code += '''    return render_template('index.html')
'''
        else:
            code += '''    return jsonify({"message": "Welcome to the API"})
'''
        
        if api_mode:
            code += '''
@app.route('/api/items', methods=['GET'])
def get_items():
    # サンプルデータ
    items = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ]
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Invalid request"}), 400
    # 実際のアプリケーションではデータベースに保存する
    return jsonify({"id": 3, "name": data['name']}), 201

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    # 実際のアプリケーションではデータベースからitem_idに基づいて取得する
    item = {"id": item_id, "name": f"Item {item_id}"}
    return jsonify(item)
'''
        
        code += '''
if __name__ == '__main__':
    app.run(debug=True)
'''
        
        return code
    
    def _generate_blueprint_app_py(self, app_name: str, include_templates: bool, api_mode: bool) -> str:
        """Blueprint使用時のapp.pyを生成"""
        code = f'''from flask import Flask
import os
from config import config

def create_app(config_name=None):
    """アプリケーションファクトリ関数"""
    app = Flask(__name__)
    
    # 環境設定を読み込む
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Blueprintを登録
    from blueprints.main import main_bp
    app.register_blueprint(main_bp)
    
'''
        
        if api_mode:
            code += '''    # API Blueprintを登録
    from blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
'''
        
        code += '''    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
'''
        
        return code
    
    def _generate_config_py(self, app_name: str) -> str:
        """設定ファイルを生成"""
        return f'''import os
import secrets

class Config:
    """基本設定クラス"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    # データベース設定などの共通設定をここに追加

class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    # 開発環境固有の設定をここに追加

class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    # テスト環境固有の設定をここに追加

class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    # 本番環境固有の設定をここに追加

# 環境設定マッピング
config = {{
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}}
'''
    
    def _generate_requirements_txt(self, api_mode: bool) -> str:
        """requirements.txtを生成"""
        requirements = [
            "Flask==2.3.3",
            "python-dotenv==1.0.0",
            "Werkzeug==2.3.7"
        ]
        
        if api_mode:
            requirements.extend([
                "Flask-Cors==4.0.0",
                "marshmallow==3.20.1"
            ])
        
        return "\n".join(requirements)
    
    def _generate_base_template(self) -> str:
        """ベーステンプレートを生成"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Flask App{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <header>
        <h1>Flask Application</h1>
        <nav>
            <ul>
                <li><a href="{{ url_for('index') }}">Home</a></li>
                <!-- Add more navigation links as needed -->
            </ul>
        </nav>
    </header>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>&copy; {{ now.year }} Flask App</p>
    </footer>
    
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
'''
    
    def _generate_index_template(self) -> str:
        """インデックステンプレートを生成"""
        return '''{% extends "base.html" %}

{% block title %}Home{% endblock %}

{% block content %}
<section>
    <h2>Welcome to Flask App</h2>
    <p>This is a simple Flask application.</p>
</section>
{% endblock %}
'''
    
    def _generate_blueprint_init(self, blueprint_name: str) -> str:
        """Blueprint初期化ファイルを生成"""
        return f'''from flask import Blueprint

{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__)

from . import routes
'''
    
    def _generate_main_blueprint_routes(self, include_templates: bool) -> str:
        """メインBlueprintのルートファイルを生成"""
        if include_templates:
            return '''from flask import render_template
from . import main_bp

@main_bp.route('/')
def index():
    return render_template('index.html')
'''
        else:
            return '''from flask import jsonify
from . import main_bp

@main_bp.route('/')
def index():
    return jsonify({"message": "Welcome to the API"})
'''
    
    def _generate_api_blueprint_routes(self) -> str:
        """API Blueprintのルートファイルを生成"""
        return '''from flask import jsonify, request
from . import api_bp

# アイテム一覧を取得
@api_bp.route('/items', methods=['GET'])
def get_items():
    # サンプルデータ
    items = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ]
    return jsonify(items)

# 新しいアイテムを作成
@api_bp.route('/items', methods=['POST'])
def create_item():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Invalid request"}), 400
    # 実際のアプリケーションではデータベースに保存する
    return jsonify({"id": 3, "name": data['name']}), 201

# 特定のアイテムを取得
@api_bp.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    # 実際のアプリケーションではデータベースからitem_idに基づいて取得する
    item = {"id": item_id, "name": f"Item {item_id}"}
    return jsonify(item)

# アイテムを更新
@api_bp.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Invalid request"}), 400
    # 実際のアプリケーションではデータベースの item_id を持つアイテムを更新する
    return jsonify({"id": item_id, "name": data['name']})

# アイテムを削除
@api_bp.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    # 実際のアプリケーションではデータベースの item_id を持つアイテムを削除する
    return jsonify({"message": f"Item {item_id} deleted"}), 200
'''

class FlaskRunnerTool(BaseTool):
    """Flask実行ツール"""
    
    name: str = "Flask実行"
    description: str = "Flaskアプリケーションの実行を支援します。"
    
    def _run(self, 
            app_file_path: str,
            host: str = "127.0.0.1",
            port: int = 5000,
            debug: bool = True,
            wait_time: int = 5) -> str:
        """
        Flaskアプリケーションを実行
        
        Args:
            app_file_path: Flaskアプリケーションのエントリポイントファイルパス
            host: ホストアドレス
            port: ポート番号
            debug: デバッグモードを有効にするか
            wait_time: 開始後に待機する秒数（負の値の場合は待機しない）
            
        Returns:
            str: 実行結果またはエラーメッセージ
        """
        logger.info(f"Flask実行ツールが呼び出されました: {app_file_path}")
        
        # ファイルの存在確認
        if not os.path.exists(app_file_path):
            return f"エラー: ファイルが見つかりません: {app_file_path}"
        
        # Flaskコマンドの実行
        try:
            env = os.environ.copy()
            env["FLASK_APP"] = app_file_path
            env["FLASK_DEBUG"] = "1" if debug else "0"
            
            # 非同期で実行するためのコマンド
            command = [
                "flask", "run",
                "--host", host,
                "--port", str(port)
            ]
            
            # アプリケーションを起動（バックグラウンドで）
            process = subprocess.Popen(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 指定時間待機
            if wait_time > 0:
                try:
                    stdout, stderr = process.communicate(timeout=wait_time)
                    if process.returncode != 0:
                        return f"エラー: Flaskアプリケーションの起動に失敗しました:\n{stderr}"
                except subprocess.TimeoutExpired:
                    # タイムアウトは正常（アプリが動作中）
                    return f"Flaskアプリケーションが起動しました:\nURL: http://{host}:{port}/\n\n(バックグラウンドで実行中。プロセスを停止するには Ctrl+C を使用してください)"
            
            return f"Flaskアプリケーションの起動を開始しました:\nURL: http://{host}:{port}/\n\n(バックグラウンドで実行中。プロセスを停止するには Ctrl+C を使用してください)"
        
        except Exception as e:
            return f"エラー: Flaskアプリケーションの実行中に例外が発生しました: {str(e)}" 