"""
Djangoフレームワーク用ツールモジュール。
Djangoプロジェクトの作成、アプリ追加、モデル定義などを支援するツールを提供します。
"""

import os
import re
import json
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path

from crewai.tools import BaseTool
from utils.logger import get_logger

logger = get_logger("django_tools")

class DjangoProjectGeneratorTool(BaseTool):
    """Djangoプロジェクト生成ツール"""
    
    name: str = "Djangoプロジェクト生成"
    description: str = "基本的なDjangoプロジェクトを生成します。"
    
    def _run(self, 
            project_name: str,
            apps: Optional[List[str]] = None,
            use_rest_framework: bool = False) -> str:
        """
        Djangoプロジェクトのスケルトンコードを生成
        
        Args:
            project_name: プロジェクト名
            apps: 作成するアプリ名のリスト（省略可）
            use_rest_framework: Django REST Frameworkを使用するか
            
        Returns:
            str: 生成されたDjangoプロジェクトの構造とファイル内容
        """
        if apps is None:
            apps = []
        
        logger.info(f"Djangoプロジェクト生成ツールが呼び出されました: {project_name}")
        
        # プロジェクトの基本構造
        project_structure = [
            f"{project_name}/",
            f"{project_name}/manage.py",
            f"{project_name}/{project_name}/",
            f"{project_name}/{project_name}/__init__.py",
            f"{project_name}/{project_name}/settings.py",
            f"{project_name}/{project_name}/urls.py",
            f"{project_name}/{project_name}/asgi.py",
            f"{project_name}/{project_name}/wsgi.py",
            f"{project_name}/requirements.txt",
        ]
        
        # アプリごとの構造を追加
        for app in apps:
            project_structure.extend([
                f"{project_name}/{app}/",
                f"{project_name}/{app}/__init__.py",
                f"{project_name}/{app}/admin.py",
                f"{project_name}/{app}/apps.py",
                f"{project_name}/{app}/models.py",
                f"{project_name}/{app}/tests.py",
                f"{project_name}/{app}/views.py",
                f"{project_name}/{app}/urls.py",
                f"{project_name}/{app}/migrations/",
                f"{project_name}/{app}/migrations/__init__.py",
            ])
            
            if use_rest_framework:
                project_structure.extend([
                    f"{project_name}/{app}/serializers.py",
                    f"{project_name}/{app}/viewsets.py",
                ])
        
        # テンプレートとスタティックファイル
        project_structure.extend([
            f"{project_name}/templates/",
            f"{project_name}/templates/base.html",
            f"{project_name}/static/",
            f"{project_name}/static/css/",
            f"{project_name}/static/css/style.css",
            f"{project_name}/static/js/",
            f"{project_name}/static/js/main.js",
        ])
        
        # ファイル内容を生成
        file_contents = {}
        
        # settings.py
        file_contents[f"{project_name}/{project_name}/settings.py"] = self._generate_settings(project_name, apps, use_rest_framework)
        
        # urls.py (プロジェクト)
        file_contents[f"{project_name}/{project_name}/urls.py"] = self._generate_project_urls(project_name, apps, use_rest_framework)
        
        # requirements.txt
        file_contents[f"{project_name}/requirements.txt"] = self._generate_requirements(use_rest_framework)
        
        # 各アプリのファイル
        for app in apps:
            # models.py
            file_contents[f"{project_name}/{app}/models.py"] = self._generate_models(app)
            
            # views.py
            file_contents[f"{project_name}/{app}/views.py"] = self._generate_views(app, use_rest_framework)
            
            # urls.py (アプリ)
            file_contents[f"{project_name}/{app}/urls.py"] = self._generate_app_urls(app, use_rest_framework)
            
            # admin.py
            file_contents[f"{project_name}/{app}/admin.py"] = self._generate_admin(app)
            
            if use_rest_framework:
                # serializers.py
                file_contents[f"{project_name}/{app}/serializers.py"] = self._generate_serializers(app)
                
                # viewsets.py
                file_contents[f"{project_name}/{app}/viewsets.py"] = self._generate_viewsets(app)
        
        # テンプレート
        file_contents[f"{project_name}/templates/base.html"] = self._generate_base_template()
        
        # 静的ファイル
        file_contents[f"{project_name}/static/css/style.css"] = "/* Custom CSS styles */\nbody {\n    font-family: Arial, sans-serif;\n}"
        file_contents[f"{project_name}/static/js/main.js"] = "// Custom JavaScript"
        
        # 結果をフォーマット
        result = f"## Djangoプロジェクト: {project_name}\n\n"
        result += "### ディレクトリ構造:\n```\n"
        result += "\n".join(project_structure)
        result += "\n```\n\n"
        
        result += "### 主要ファイル内容:\n\n"
        for file_path, content in file_contents.items():
            result += f"#### {file_path}\n```python\n{content}\n```\n\n"
        
        return result.strip()
    
    def _generate_settings(self, project_name: str, apps: List[str], use_rest_framework: bool) -> str:
        """settings.pyを生成"""
        installed_apps = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ]
        
        # アプリを追加
        for app in apps:
            installed_apps.append(f"'{app}'")
        
        # Django REST Frameworkを追加
        if use_rest_framework:
            installed_apps.append("'rest_framework'")
        
        installed_apps_str = ",\n    ".join([f"'{app}'" if not app.startswith("'") else app for app in installed_apps])
        
        return f"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-replace-this-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    {installed_apps_str}
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{project_name}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{project_name}.wsgi.application'

# Database
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}
}}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {{
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    }},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
"""
    
    def _generate_project_urls(self, project_name: str, apps: List[str], use_rest_framework: bool) -> str:
        """プロジェクトのurls.pyを生成"""
        code = """from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
"""
        
        # アプリのURLを追加
        for app in apps:
            code += f"    path('{app}/', include('{app}.urls')),\n"
        
        # Django REST Framework APIブラウザのURLを追加
        if use_rest_framework:
            code += """    # API認証のためのURL
    path('api-auth/', include('rest_framework.urls')),
"""
        
        code += "]\n"
        return code
    
    def _generate_requirements(self, use_rest_framework: bool) -> str:
        """requirements.txtを生成"""
        requirements = [
            "Django==4.2.4",
            "python-dotenv==1.0.0",
        ]
        
        if use_rest_framework:
            requirements.append("djangorestframework==3.14.0")
        
        return "\n".join(requirements)
    
    def _generate_models(self, app: str) -> str:
        """models.pyを生成"""
        model_name = app.title().rstrip('s')  # 複数形の場合、単数形に変換（単純な処理）
        
        return f"""from django.db import models

class {model_name}(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = '{model_name}s'
"""
    
    def _generate_views(self, app: str, use_rest_framework: bool) -> str:
        """views.pyを生成"""
        model_name = app.title().rstrip('s')
        
        if use_rest_framework:
            # REST Frameworkを使用する場合は、シンプルなビューのみ
            return f"""from django.shortcuts import render
from .models import {model_name}

def index(request):
    {app} = {model_name}.objects.all()
    return render(request, '{app}/index.html', {{{app}: {app}}})

def detail(request, pk):
    item = {model_name}.objects.get(pk=pk)
    return render(request, '{app}/detail.html', {{'item': item}})
"""
        else:
            # 標準的なDjangoビュー
            return f"""from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import {model_name}
from django.contrib import messages

class {model_name}ListView(ListView):
    model = {model_name}
    template_name = '{app}/index.html'
    context_object_name = '{app}'
    
class {model_name}DetailView(DetailView):
    model = {model_name}
    template_name = '{app}/detail.html'
    context_object_name = 'item'
    
class {model_name}CreateView(CreateView):
    model = {model_name}
    template_name = '{app}/form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('{app}:index')
    
    def form_valid(self, form):
        messages.success(self.request, '{model_name} created successfully.')
        return super().form_valid(form)
    
class {model_name}UpdateView(UpdateView):
    model = {model_name}
    template_name = '{app}/form.html'
    fields = ['name', 'description']
    context_object_name = 'item'
    success_url = reverse_lazy('{app}:index')
    
    def form_valid(self, form):
        messages.success(self.request, '{model_name} updated successfully.')
        return super().form_valid(form)
    
class {model_name}DeleteView(DeleteView):
    model = {model_name}
    template_name = '{app}/confirm_delete.html'
    context_object_name = 'item'
    success_url = reverse_lazy('{app}:index')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, '{model_name} deleted successfully.')
        return super().delete(request, *args, **kwargs)
"""
    
    def _generate_app_urls(self, app: str, use_rest_framework: bool) -> str:
        """アプリのurls.pyを生成"""
        model_name = app.title().rstrip('s')
        
        if use_rest_framework:
            # REST Frameworkを使用する場合
            return f"""from django.urls import path, include
from . import views
from . import viewsets
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'{app}', viewsets.{model_name}ViewSet)

app_name = '{app}'

urlpatterns = [
    # 通常のビュー
    path('', views.index, name='index'),
    path('<int:pk>/', views.detail, name='detail'),
    
    # APIエンドポイント
    path('api/', include(router.urls)),
]
"""
        else:
            # 標準的なDjangoのURL設定
            return f"""from django.urls import path
from . import views

app_name = '{app}'

urlpatterns = [
    path('', views.{model_name}ListView.as_view(), name='index'),
    path('<int:pk>/', views.{model_name}DetailView.as_view(), name='detail'),
    path('new/', views.{model_name}CreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.{model_name}UpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.{model_name}DeleteView.as_view(), name='delete'),
]
"""
    
    def _generate_admin(self, app: str) -> str:
        """admin.pyを生成"""
        model_name = app.title().rstrip('s')
        
        return f"""from django.contrib import admin
from .models import {model_name}

@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    list_filter = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
"""
    
    def _generate_serializers(self, app: str) -> str:
        """serializers.pyを生成 (REST Framework用)"""
        model_name = app.title().rstrip('s')
        
        return f"""from rest_framework import serializers
from .models import {model_name}

class {model_name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {model_name}
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
"""
    
    def _generate_viewsets(self, app: str) -> str:
        """viewsets.pyを生成 (REST Framework用)"""
        model_name = app.title().rstrip('s')
        
        return f"""from rest_framework import viewsets, permissions
from .models import {model_name}
from .serializers import {model_name}Serializer

class {model_name}ViewSet(viewsets.ModelViewSet):
    queryset = {model_name}.objects.all()
    serializer_class = {model_name}Serializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
"""
    
    def _generate_base_template(self) -> str:
        """ベーステンプレートを生成"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Django Project{% endblock %}</title>
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <header>
        <h1>Django Application</h1>
        <nav>
            <ul>
                <li><a href="/">Home</a></li>
                <!-- Add more navigation links as needed -->
            </ul>
        </nav>
    </header>
    
    {% if messages %}
    <div class="messages">
        {% for message in messages %}
        <div class="message {% if message.tags %}{{ message.tags }}{% endif %}">
            {{ message }}
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>&copy; {% now "Y" %} Django Project</p>
    </footer>
    
    <script src="{% static 'js/main.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
"""

class DjangoModelGeneratorTool(BaseTool):
    """Djangoモデル生成ツール"""
    
    name: str = "Djangoモデル生成"
    description: str = "Djangoアプリケーションのモデルを生成します。"
    
    def _run(self, 
            model_name: str,
            fields: List[Dict[str, str]],
            meta_options: Optional[Dict[str, Any]] = None) -> str:
        """
        Djangoモデルを生成
        
        Args:
            model_name: モデル名
            fields: フィールド定義のリスト[{'name': 'title', 'type': 'CharField', 'options': {'max_length': 100}}]
            meta_options: Metaクラスのオプション（省略可）
            
        Returns:
            str: 生成されたDjangoモデルコード
        """
        logger.info(f"Djangoモデル生成ツールが呼び出されました: {model_name}")
        
        imports = set(['from django.db import models'])
        
        # フィールド定義を生成
        field_lines = []
        for field in fields:
            field_name = field['name']
            field_type = field['type']
            field_options = field.get('options', {})
            
            # 特別なインポートが必要なフィールドタイプがあれば追加
            if field_type == 'ForeignKey' or field_type == 'OneToOneField' or field_type == 'ManyToManyField':
                if 'to' in field_options:
                    # 参照先モデル名によってインポート文を変える
                    related_model = field_options['to']
                    if '.' in related_model:
                        app_label, related_model_name = related_model.split('.')
                        imports.add(f'from {app_label}.models import {related_model_name}')
            
            # オプションの文字列化
            options_str = ', '.join([f"{k}={repr(v)}" for k, v in field_options.items()])
            
            # フィールド行を生成
            field_lines.append(f"    {field_name} = models.{field_type}({options_str})")
        
        # __str__メソッドを生成
        str_method = "    def __str__(self):\n"
        # title, name, または最初のCharFieldを__str__メソッドで使用
        str_field = next((field['name'] for field in fields if field['name'] in ['title', 'name']), None)
        if not str_field:
            str_field = next((field['name'] for field in fields if field['type'] == 'CharField'), None)
        
        if str_field:
            str_method += f"        return self.{str_field}"
        else:
            str_method += f"        return f'{model_name} {{self.id}}'"
        
        # Metaクラスを生成
        meta_class = "    class Meta:\n"
        if meta_options:
            for key, value in meta_options.items():
                meta_class += f"        {key} = {repr(value)}\n"
        else:
            meta_class += f"        verbose_name_plural = '{model_name}s'\n"
        
        # モデルコードを生成
        imports_str = '\n'.join(imports)
        model_code = f"""{imports_str}

class {model_name}(models.Model):
{chr(10).join(field_lines)}

{str_method}

{meta_class}
"""
        
        return model_code

class DjangoRunnerTool(BaseTool):
    """Django実行ツール"""
    
    name: str = "Django実行"
    description: str = "Djangoアプリケーションの実行を支援します。"
    
    def _run(self, 
            command_type: str,
            manage_py_path: str,
            args: Optional[List[str]] = None) -> str:
        """
        Djangoコマンドを実行
        
        Args:
            command_type: 実行するコマンドタイプ（runserver, makemigrations, migrate, createsuperuser, shell, test）
            manage_py_path: manage.pyファイルのパス
            args: コマンドに渡す追加の引数（省略可）
            
        Returns:
            str: 実行結果またはエラーメッセージ
        """
        if args is None:
            args = []
            
        logger.info(f"Django実行ツールが呼び出されました: {command_type}")
        
        # ファイルの存在確認
        if not os.path.exists(manage_py_path):
            return f"エラー: manage.pyが見つかりません: {manage_py_path}"
        
        # コマンドを準備
        cmd = [sys.executable, manage_py_path, command_type] + args
        
        # 実行
        try:
            if command_type == "runserver":
                # runserverの場合は非同期で実行
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # 少し待って初期メッセージを取得
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    if process.returncode is not None and process.returncode != 0:
                        return f"エラー: Djangoサーバーの起動に失敗しました:\n{stderr}"
                except subprocess.TimeoutExpired:
                    # タイムアウトは正常（サーバーが起動中）
                    return "Djangoサーバーが起動しました。プロセスを停止するには Ctrl+C を使用してください。"
            else:
                # その他のコマンドは通常実行
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    return f"コマンド `{' '.join(cmd)}` が正常に実行されました。\n\n結果:\n{result.stdout}"
                else:
                    return f"コマンド `{' '.join(cmd)}` の実行中にエラーが発生しました。\n\nエラー:\n{result.stderr}\n\n出力:\n{result.stdout}"
        
        except Exception as e:
            return f"エラー: Djangoコマンドの実行中に例外が発生しました: {str(e)}" 