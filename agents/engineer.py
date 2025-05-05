"""
エンジニアエージェントモジュール。
PLからの指示に基づき、実装、単体テスト、デバッグを担当します。
"""

import json
import os
from typing import List, Dict, Any, Optional
from crewai import Agent, Task
from langchain.tools import Tool

from utils.logger import get_agent_logger
from utils.config import config

logger = get_agent_logger("engineer")


class CodeGeneratorTool(Tool):
    """コード生成ツール"""
    
    name = "コード生成"
    description = "実装指示書に基づいてプログラムコードを生成します。"
    
    def _run(self, implementation_guide: str, programming_language: str = "python") -> str:
        """
        プログラムコードを生成します。
        
        Args:
            implementation_guide: 実装指示書
            programming_language: プログラミング言語（デフォルト: python）
            
        Returns:
            str: 生成されたコード
        """
        logger.info("コード生成ツールが呼び出されました。")
        
        # 実際のプロジェクトではLLMを使用してより高度なコード生成を行う
        # 現段階ではサンプルコードを返す
        if programming_language.lower() == "python":
            generated_code = """
# ユーザー認証モジュール
# auth/models.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }
"""
        elif programming_language.lower() == "javascript" or programming_language.lower() == "typescript":
            generated_code = """
// ユーザープロファイルコンポーネント
// src/components/UserProfile.tsx

import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Container, Form } from 'react-bootstrap';

interface User {
  id: string;
  name: string;
  email: string;
}

const UserProfile: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const [user, setUser] = useState<User | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  useEffect(() => {
    // ユーザーデータの取得
    const fetchUser = async () => {
      try {
        const response = await fetch(`/api/users/${userId}`);
        if (!response.ok) {
          throw new Error('ユーザー情報の取得に失敗しました');
        }
        const userData = await response.json();
        setUser(userData);
        setFormData({ name: userData.name, email: userData.email });
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };
    
    fetchUser();
  }, [userId]);
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // フォームデータの送信処理
    try {
      const response = await fetch(`/api/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });
      
      if (!response.ok) {
        throw new Error('プロファイルの更新に失敗しました');
      }
      
      const updatedUser = await response.json();
      setUser(updatedUser);
      setIsEditing(false);
    } catch (err) {
      setError(err.message);
    }
  };
  
  if (loading) return <div>読み込み中...</div>;
  if (error) return <div>エラー: {error}</div>;
  if (!user) return <div>ユーザーが見つかりません</div>;
  
  return (
    <Container className="mt-4">
      <Card>
        <Card.Header as="h5">ユーザープロファイル</Card.Header>
        <Card.Body>
          {isEditing ? (
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>名前</Form.Label>
                <Form.Control
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  required
                />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>メールアドレス</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                />
              </Form.Group>
              <Button variant="primary" type="submit" className="me-2">
                保存
              </Button>
              <Button variant="secondary" onClick={() => setIsEditing(false)}>
                キャンセル
              </Button>
            </Form>
          ) : (
            <>
              <p><strong>ID:</strong> {user.id}</p>
              <p><strong>名前:</strong> {user.name}</p>
              <p><strong>メールアドレス:</strong> {user.email}</p>
              <Button variant="primary" onClick={() => setIsEditing(true)}>
                編集
              </Button>
            </>
          )}
        </Card.Body>
      </Card>
    </Container>
  );
};

export default UserProfile;
"""
        elif programming_language.lower() == "html":
            generated_code = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ログインページ</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            border-radius: 5px;
        }
        .error-message {
            color: red;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-container">
            <h2 class="text-center mb-4">ログイン</h2>
            <div id="error-container" class="error-message"></div>
            <form id="login-form">
                <div class="mb-3">
                    <label for="email" class="form-label">メールアドレス</label>
                    <input type="email" class="form-control" id="email" name="email" required>
                </div>
                <div class="mb-3">
                    <label for="password" class="form-label">パスワード</label>
                    <input type="password" class="form-control" id="password" name="password" required>
                </div>
                <div class="mb-3 form-check">
                    <input type="checkbox" class="form-check-input" id="remember-me" name="remember-me">
                    <label class="form-check-label" for="remember-me">ログイン状態を保持する</label>
                </div>
                <button type="submit" class="btn btn-primary w-100">ログイン</button>
            </form>
            <div class="mt-3 text-center">
                <a href="/register">新規登録はこちら</a> | <a href="/forgot-password">パスワードをお忘れの方</a>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const rememberMe = document.getElementById('remember-me').checked;
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password, rememberMe }),
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.message || 'ログインに失敗しました');
                }
                
                // ログイン成功
                window.location.href = '/dashboard';
            } catch (error) {
                document.getElementById('error-container').textContent = error.message;
            }
        });
    </script>
</body>
</html>
"""
        else:
            generated_code = f"# {programming_language}用のサンプルコードはまだ実装されていません。"
        
        return generated_code


class CodeDebugTool(Tool):
    """コードデバッグツール"""
    
    name = "コードデバッグ"
    description = "コードの問題を分析し、デバッグ情報と修正案を提供します。"
    
    def _run(self, code: str, error_message: str = None) -> str:
        """
        コードをデバッグし、修正案を提供します。
        
        Args:
            code: デバッグ対象のコード
            error_message: エラーメッセージ（オプション）
            
        Returns:
            str: デバッグ結果と修正案
        """
        logger.info("コードデバッグツールが呼び出されました。")
        
        # デバッグレポートテンプレート
        debug_template = """
        # デバッグレポート

        ## 問題の特定
        {issue}

        ## 原因分析
        {cause}

        ## 修正案
        ```{language}
        {fixed_code}
        ```

        ## 説明
        {explanation}

        ## 予防策
        {prevention}
        """
        
        # 実際のプロジェクトではLLMとコード解析ツールを使用してより高度なデバッグを行う
        # 現段階ではサンプルデバッグレポートを返す
        
        # コードの言語を簡易的に判定
        language = "python"  # デフォルト
        if "function" in code and "{" in code:
            language = "javascript"
        elif "<!DOCTYPE html>" in code or "<html" in code:
            language = "html"
        
        # エラーメッセージの有無で異なるサンプルレポートを返す
        if error_message:
            return debug_template.format(
                issue=f"コードで次のエラーが発生しています：\n```\n{error_message}\n```",
                cause="変数 `user` が定義される前に参照されています。API呼び出しが非同期であるため、データが取得される前にアクセスが行われています。",
                language=language,
                fixed_code=code.replace("console.log(user.name);", "if (user) {\n  console.log(user.name);\n}"),
                explanation="非同期処理では、データが取得される前にコードが実行される可能性があります。そのため、変数が確実に存在することを確認してから参照する必要があります。",
                prevention="非同期処理を扱う際は常に次のプラクティスに従いましょう：\n1. データの存在チェックを行う\n2. ローディング状態を管理する\n3. エラーハンドリングを実装する"
            )
        else:
            return debug_template.format(
                issue="コードには明示的なエラーはありませんが、以下の潜在的な問題が見られます：\n1. エラーハンドリングが不十分\n2. パフォーマンスの最適化余地あり",
                cause="try-catch ブロックがありますが、特定のエラーに対する処理が不足しています。また、不必要なデータ処理や再レンダリングが発生する可能性があります。",
                language=language,
                fixed_code=code.replace("catch (err) {", "catch (err) {\n  console.error('詳細なエラー情報:', err);\n"),
                explanation="エラーハンドリングを強化し、デバッグ情報を充実させました。また、パフォーマンス向上のためにメモ化を検討すべきです。",
                prevention="1. 詳細なエラーログを記録する\n2. React.memoやuseCallbackを使用して不要な再レンダリングを防ぐ\n3. エラーバウンダリを実装して予期しないエラーに対処する"
            )


class CodeRunnerTool(Tool):
    """コード実行ツール"""
    
    name = "コード実行"
    description = "生成されたコードを安全な環境で実行し、結果を返します。"
    
    def _run(self, code: str, input_data: str = None) -> str:
        """
        コードを実行し、結果を返します。
        
        Args:
            code: 実行するコード
            input_data: 入力データ（オプション）
            
        Returns:
            str: 実行結果
        """
        logger.info("コード実行ツールが呼び出されました。")
        
        # 実際のプロジェクトでは安全なサンドボックス環境でコードを実行する
        # 現段階ではシミュレートした実行結果を返す
        
        # 簡易的な言語検出
        if "import " in code and "def " in code:
            # Pythonコードと判断
            return """
実行結果:
---
データベース接続成功
ユーザーテーブルが作成されました
テストユーザーが追加されました
ID: 550e8400-e29b-41d4-a716-446655440000
名前: テストユーザー
Eメール: test@example.com
---
実行完了 (所要時間: 0.45秒)
"""
        elif "function" in code or "const " in code or "let " in code:
            # JavaScript/TypeScriptコードと判断
            return """
実行結果:
---
React コンポーネントをレンダリング中...
コンポーネントがマウントされました
ユーザーデータを取得しています...
ユーザーデータ取得完了
---
実行完了 (所要時間: 0.32秒)
"""
        elif "<!DOCTYPE html>" in code or "<html" in code:
            # HTMLコードと判断
            return """
実行結果:
---
HTML文書の解析に成功しました
ドキュメントがDOMに読み込まれました
フォームイベントリスナーが設定されました
---
レンダリングプレビュー:
| ログインページ         |
| -------------------- |
| [メールアドレス     ]  |
| [パスワード        ]  |
| [x] ログイン状態を保持   |
| [   ログイン       ]  |
| 新規登録はこちら | パスワードをお忘れの方 |
---
実行完了 (所要時間: 0.18秒)
"""
        else:
            # その他の言語またはテキスト
            return """
実行結果:
---
コードの言語を識別できないか、実行できない形式です。
サポートされている言語: Python, JavaScript, HTML
---
"""


def create_engineer_agent(tools: Optional[List[Tool]] = None, agent_id: int = 1) -> Agent:
    """
    エンジニアエージェントを作成します。
    
    Args:
        tools: エージェントが使用するツールのリスト
        agent_id: エージェントの識別子（複数のエンジニアエージェントを区別するため）
        
    Returns:
        Agent: 設定されたエンジニアエージェント
    """
    logger.info(f"エンジニアエージェント {agent_id} を作成します。")
    
    # ツールがNoneの場合は空リストを設定
    if tools is None:
        tools = []
    
    # エンジニア固有のツールを追加
    engineer_specific_tools = [
        CodeGeneratorTool(),
        CodeDebugTool(),
        CodeRunnerTool(),
    ]
    
    all_tools = tools + engineer_specific_tools
    
    # エンジニアエージェントの作成
    engineer_agent = Agent(
        role=f"ソフトウェアエンジニア {agent_id}",
        goal="PLからの指示に基づき、担当機能のコーディング、単体テスト、デバッグを行う。技術的な課題解決に取り組む。",
        backstory=f"""
        あなたは、幅広い開発経験を持つソフトウェアエンジニア {agent_id} です。
        複数のプログラミング言語とフレームワークに精通し、フロントエンドからバックエンド、データベース、
        インフラまで、フルスタックな開発スキルを持っています。コードの品質と保守性を重視し、単体テストを
        徹底して実施することで堅牢なシステムを構築します。技術的な課題に対して創造的な解決策を提案し、
        実装することができます。チームでの協業経験が豊富で、PLやデザイナーと緊密に連携しながら効率的に
        開発を進める能力を持っています。継続的に新しい技術を学び、実践に活かしています。
        """,
        verbose=True,
        llm=config.get_llm_config(),
        tools=all_tools,
        allow_delegation=False,  # エンジニアは基本的に下位エージェントに委任しない
    )
    
    return engineer_agent


def generate_code(agent: Agent, implementation_guide: str, programming_language: str = "python") -> Dict[str, Any]:
    """
    コードを生成します。
    
    Args:
        agent: エンジニアエージェント
        implementation_guide: 実装指示書
        programming_language: プログラミング言語
        
    Returns:
        Dict[str, Any]: 生成されたコード
    """
    logger.info(f"コード生成を開始します。言語: {programming_language}")
    
    # コード生成タスクの実行
    code_task = Task(
        description=f"実装指示書に基づいて{programming_language}コードを生成してください。コードは読みやすく、保守性を考慮し、ベストプラクティスに従って実装してください。",
        expected_output=f"{programming_language}コード",
        agent=agent
    )
    
    code_result = agent.execute_task(code_task, context={
        "implementation_guide": implementation_guide,
        "programming_language": programming_language
    })
    
    logger.info("コード生成が完了しました。")
    return {"code": code_result}


def debug_code(agent: Agent, code: str, error_message: str = None) -> Dict[str, Any]:
    """
    コードをデバッグします。
    
    Args:
        agent: エンジニアエージェント
        code: デバッグ対象のコード
        error_message: エラーメッセージ（オプション）
        
    Returns:
        Dict[str, Any]: デバッグ結果
    """
    logger.info("コードデバッグを開始します。")
    
    # デバッグタスクの実行
    debug_task = Task(
        description="提供されたコードの問題を分析し、デバッグして修正してください。エラーの原因と解決策を説明してください。",
        expected_output="デバッグレポートと修正済みコード",
        agent=agent
    )
    
    context = {"code": code}
    if error_message:
        context["error_message"] = error_message
    
    debug_result = agent.execute_task(debug_task, context=context)
    
    logger.info("コードデバッグが完了しました。")
    return {"debug_report": debug_result}


def run_code(agent: Agent, code: str, input_data: str = None) -> Dict[str, Any]:
    """
    コードを実行します。
    
    Args:
        agent: エンジニアエージェント
        code: 実行するコード
        input_data: 入力データ（オプション）
        
    Returns:
        Dict[str, Any]: 実行結果
    """
    logger.info("コード実行を開始します。")
    
    # コード実行タスクの実行
    run_task = Task(
        description="提供されたコードを実行し、結果を返してください。",
        expected_output="実行結果",
        agent=agent
    )
    
    context = {"code": code}
    if input_data:
        context["input_data"] = input_data
    
    run_result = agent.execute_task(run_task, context=context)
    
    logger.info("コード実行が完了しました。")
    return {"execution_result": run_result} 