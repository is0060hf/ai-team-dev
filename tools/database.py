"""
データベース操作ツールモジュール。
SQLite、PostgreSQLなどのデータベースに対して、エージェントが安全にクエリ実行などの操作を行うための機能を提供します。
"""

import os
import re
import json
import sqlite3
import tempfile
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from contextlib import contextmanager
from pathlib import Path
import urllib.parse
import textwrap

from crewai.tools import BaseTool
from utils.logger import get_logger

logger = get_logger("database_tool")

# SQLインジェクション防止のための危険なパターン
DANGEROUS_SQL_PATTERNS = [
    r'--.*$',                  # SQLコメント
    r'/\*.*?\*/',              # ブロックコメント
    r';\s*\w+',                # 複数のステートメント
    r'EXEC\s+|\bXP_',          # ストアドプロシージャ実行
    r'DROP\s+|\bTRUNCATE\s+',  # テーブル削除/切り詰め
    r'ALTER\s+',               # テーブル変更
    r'SHUTDOWN\b',             # シャットダウンコマンド
    r'UNION\s+SELECT',         # UNIONベースのSQLインジェクション
    r'INTO\s+OUTFILE',         # ファイル書き込み
    r'LOAD_FILE\s*\(',         # ファイル読み込み
    r'SLEEP\s*\([^)]+\)',      # 時間ベースのSQLインジェクション
]

# 安全なSQL操作のホワイトリスト
SAFE_SQL_OPERATIONS = [
    'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE TABLE', 'ALTER TABLE',
    'CREATE INDEX', 'CREATE VIEW', 'BEGIN', 'COMMIT', 'ROLLBACK'
]

class DatabaseConnectionError(Exception):
    """データベース接続エラー"""
    pass

class SQLSanitizationError(Exception):
    """SQLサニタイズエラー"""
    pass

class DatabaseHandler:
    """データベース接続とクエリ実行を行う基底クラス"""
    
    def __init__(self, connection_string: str):
        """
        データベースハンドラーを初期化
        
        Args:
            connection_string: データベース接続文字列
        """
        self.connection_string = connection_string
        self.connection = None
        self.connected = False
    
    def connect(self) -> None:
        """データベースに接続（サブクラスで実装）"""
        raise NotImplementedError
    
    def disconnect(self) -> None:
        """データベース接続を閉じる（サブクラスで実装）"""
        raise NotImplementedError
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
        """
        クエリを実行し、結果を返す（サブクラスで実装）
        
        Args:
            query: 実行するSQLクエリ
            params: クエリパラメータ（オプション）
            
        Returns:
            Tuple[bool, Any, str]: (成功したか, 結果データ, メッセージ)
        """
        raise NotImplementedError
    
    def get_schema(self) -> Dict[str, Any]:
        """
        データベーススキーマ情報を取得（サブクラスで実装）
        
        Returns:
            Dict[str, Any]: スキーマ情報
        """
        raise NotImplementedError
    
    @contextmanager
    def connection_context(self):
        """データベース接続のコンテキストマネージャ"""
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()

class SQLiteHandler(DatabaseHandler):
    """SQLiteデータベースハンドラー"""
    
    def __init__(self, db_path: str):
        """
        SQLiteハンドラーを初期化
        
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        super().__init__(db_path)
        self.db_path = db_path
    
    def connect(self) -> None:
        """SQLiteデータベースに接続"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # 名前付きカラムを有効化
            self.connected = True
            logger.info(f"SQLiteデータベースに接続しました: {self.db_path}")
        except Exception as e:
            logger.error(f"SQLiteデータベース接続エラー: {str(e)}")
            raise DatabaseConnectionError(f"SQLiteデータベース接続に失敗しました: {str(e)}")
    
    def disconnect(self) -> None:
        """SQLiteデータベース接続を閉じる"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.connected = False
            logger.info(f"SQLiteデータベース接続を閉じました: {self.db_path}")
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
        """
        SQLiteデータベースでクエリを実行
        
        Args:
            query: 実行するSQLクエリ
            params: クエリパラメータ（オプション）
            
        Returns:
            Tuple[bool, Any, str]: (成功したか, 結果データ, メッセージ)
        """
        if not self.connected or not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        result_data = None
        error_msg = ""
        success = False
        
        try:
            start_time = pd.Timestamp.now()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # SELECTクエリかどうかを確認
            if query.strip().upper().startswith("SELECT"):
                # 結果を取得
                rows = cursor.fetchall()
                if rows:
                    # 列名を取得
                    columns = [desc[0] for desc in cursor.description]
                    
                    # 辞書のリストに変換
                    result_data = [dict(zip(columns, row)) for row in rows]
                else:
                    result_data = []
                
                message = f"{len(result_data)} 行が返されました。"
            else:
                # DDL/DMLの場合は影響を受けた行数を返す
                self.connection.commit()
                affected_rows = cursor.rowcount
                result_data = {"affected_rows": affected_rows}
                message = f"{affected_rows} 行が影響を受けました。"
            
            end_time = pd.Timestamp.now()
            execution_time = (end_time - start_time).total_seconds()
            message += f" 実行時間: {execution_time:.3f} 秒"
            
            success = True
            return success, result_data, message
        
        except Exception as e:
            self.connection.rollback()
            error_msg = f"クエリ実行エラー: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        
        finally:
            cursor.close()
    
    def get_schema(self) -> Dict[str, Any]:
        """
        SQLiteデータベーススキーマ情報を取得
        
        Returns:
            Dict[str, Any]: スキーマ情報（テーブル、列、インデックスなど）
        """
        if not self.connected or not self.connection:
            self.connect()
        
        schema_info = {
            "tables": [],
            "views": [],
            "indexes": []
        }
        
        try:
            # テーブル一覧を取得
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 各テーブルの列情報を取得
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "is_primary_key": bool(col[5])
                    })
                
                # テーブルの外部キー情報を取得
                cursor.execute(f"PRAGMA foreign_key_list({table})")
                foreign_keys = []
                for fk in cursor.fetchall():
                    foreign_keys.append({
                        "id": fk[0],
                        "seq": fk[1],
                        "referenced_table": fk[2],
                        "from_column": fk[3],
                        "to_column": fk[4],
                        "on_update": fk[5],
                        "on_delete": fk[6],
                        "match": fk[7]
                    })
                
                schema_info["tables"].append({
                    "name": table,
                    "columns": columns,
                    "foreign_keys": foreign_keys
                })
            
            # ビュー一覧を取得
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view'")
            for row in cursor.fetchall():
                schema_info["views"].append({
                    "name": row[0],
                    "definition": row[1]
                })
            
            # インデックス一覧を取得
            cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
            for row in cursor.fetchall():
                schema_info["indexes"].append({
                    "name": row[0],
                    "table": row[1],
                    "definition": row[2]
                })
            
            return schema_info
        
        except Exception as e:
            logger.error(f"スキーマ取得エラー: {str(e)}")
            return {"error": str(e)}

class PostgreSQLHandler(DatabaseHandler):
    """PostgreSQLデータベースハンドラー"""
    
    def __init__(self, connection_string: str):
        """
        PostgreSQLハンドラーを初期化
        
        Args:
            connection_string: PostgreSQL接続文字列
        """
        super().__init__(connection_string)
        
        # psycopg2が利用可能かチェック
        self.psycopg2_available = False
        try:
            import psycopg2
            import psycopg2.extras
            self.psycopg2 = psycopg2
            self.psycopg2_available = True
        except ImportError:
            logger.warning("psycopg2がインストールされていません。PostgreSQL接続には必要です。")
    
    def connect(self) -> None:
        """PostgreSQLデータベースに接続"""
        if not self.psycopg2_available:
            raise DatabaseConnectionError("psycopg2がインストールされていないため、PostgreSQLに接続できません。")
        
        try:
            self.connection = self.psycopg2.connect(self.connection_string)
            self.connected = True
            logger.info("PostgreSQLデータベースに接続しました")
        except Exception as e:
            logger.error(f"PostgreSQL接続エラー: {str(e)}")
            raise DatabaseConnectionError(f"PostgreSQL接続に失敗しました: {str(e)}")
    
    def disconnect(self) -> None:
        """PostgreSQL接続を閉じる"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.connected = False
            logger.info("PostgreSQL接続を閉じました")
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
        """
        PostgreSQLデータベースでクエリを実行
        
        Args:
            query: 実行するSQLクエリ
            params: クエリパラメータ（オプション）
            
        Returns:
            Tuple[bool, Any, str]: (成功したか, 結果データ, メッセージ)
        """
        if not self.connected or not self.connection:
            self.connect()
        
        cursor = self.connection.cursor(cursor_factory=self.psycopg2.extras.DictCursor)
        result_data = None
        error_msg = ""
        success = False
        
        try:
            start_time = pd.Timestamp.now()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # SELECTクエリかどうかを確認
            if query.strip().upper().startswith("SELECT"):
                # 結果を取得
                rows = cursor.fetchall()
                if rows:
                    # 辞書のリストに変換
                    result_data = [dict(row) for row in rows]
                else:
                    result_data = []
                
                message = f"{len(result_data)} 行が返されました。"
            else:
                # DDL/DMLの場合は影響を受けた行数を返す
                self.connection.commit()
                affected_rows = cursor.rowcount
                result_data = {"affected_rows": affected_rows}
                message = f"{affected_rows} 行が影響を受けました。"
            
            end_time = pd.Timestamp.now()
            execution_time = (end_time - start_time).total_seconds()
            message += f" 実行時間: {execution_time:.3f} 秒"
            
            success = True
            return success, result_data, message
        
        except Exception as e:
            self.connection.rollback()
            error_msg = f"クエリ実行エラー: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        
        finally:
            cursor.close()
    
    def get_schema(self) -> Dict[str, Any]:
        """
        PostgreSQLデータベーススキーマ情報を取得
        
        Returns:
            Dict[str, Any]: スキーマ情報（テーブル、列、インデックスなど）
        """
        if not self.connected or not self.connection:
            self.connect()
        
        schema_info = {
            "tables": [],
            "views": [],
            "indexes": [],
            "schemas": []
        }
        
        try:
            cursor = self.connection.cursor(cursor_factory=self.psycopg2.extras.DictCursor)
            
            # スキーマ一覧を取得
            cursor.execute("""
                SELECT schema_name, schema_owner
                FROM information_schema.schemata
                WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema'
            """)
            schemas = cursor.fetchall()
            schema_info["schemas"] = [dict(schema) for schema in schemas]
            
            # テーブル一覧を取得
            cursor.execute("""
                SELECT 
                    table_schema, 
                    table_name, 
                    table_type
                FROM 
                    information_schema.tables
                WHERE 
                    table_schema NOT LIKE 'pg_%' 
                    AND table_schema != 'information_schema'
                ORDER BY 
                    table_schema, table_name
            """)
            tables_and_views = cursor.fetchall()
            
            # テーブルと列情報を取得
            for item in tables_and_views:
                schema_name = item["table_schema"]
                table_name = item["table_name"]
                table_type = item["table_type"]
                
                # 列情報を取得
                cursor.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        is_nullable, 
                        column_default,
                        character_maximum_length
                    FROM 
                        information_schema.columns
                    WHERE 
                        table_schema = %s AND table_name = %s
                    ORDER BY 
                        ordinal_position
                """, (schema_name, table_name))
                
                columns = []
                for col in cursor.fetchall():
                    column_info = {
                        "name": col["column_name"],
                        "type": col["data_type"],
                        "not_null": col["is_nullable"] == "NO",
                        "default_value": col["column_default"]
                    }
                    
                    if col["character_maximum_length"]:
                        column_info["max_length"] = col["character_maximum_length"]
                    
                    columns.append(column_info)
                
                # 主キー情報を取得
                cursor.execute("""
                    SELECT 
                        kcu.column_name
                    FROM 
                        information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu 
                            ON tc.constraint_name = kcu.constraint_name 
                            AND tc.table_schema = kcu.table_schema
                    WHERE 
                        tc.constraint_type = 'PRIMARY KEY' 
                        AND tc.table_schema = %s 
                        AND tc.table_name = %s
                """, (schema_name, table_name))
                
                primary_keys = [row["column_name"] for row in cursor.fetchall()]
                
                # 外部キー情報を取得
                cursor.execute("""
                    SELECT
                        kcu.column_name,
                        ccu.table_schema AS foreign_schema,
                        ccu.table_name AS foreign_table,
                        ccu.column_name AS foreign_column
                    FROM
                        information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                            AND ccu.table_schema = tc.table_schema
                    WHERE
                        tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = %s
                        AND tc.table_name = %s
                """, (schema_name, table_name))
                
                foreign_keys = []
                for fk in cursor.fetchall():
                    foreign_keys.append({
                        "column": fk["column_name"],
                        "references": {
                            "schema": fk["foreign_schema"],
                            "table": fk["foreign_table"],
                            "column": fk["foreign_column"]
                        }
                    })
                
                # テーブルまたはビュー情報を追加
                item_info = {
                    "schema": schema_name,
                    "name": table_name,
                    "columns": columns,
                    "primary_keys": primary_keys,
                    "foreign_keys": foreign_keys
                }
                
                if table_type == "BASE TABLE":
                    schema_info["tables"].append(item_info)
                elif table_type == "VIEW":
                    # ビューの定義を取得
                    cursor.execute("""
                        SELECT 
                            view_definition
                        FROM 
                            information_schema.views
                        WHERE 
                            table_schema = %s AND table_name = %s
                    """, (schema_name, table_name))
                    
                    view_def = cursor.fetchone()
                    if view_def and view_def["view_definition"]:
                        item_info["definition"] = view_def["view_definition"]
                    
                    schema_info["views"].append(item_info)
            
            # インデックス情報を取得
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM
                    pg_indexes
                WHERE
                    schemaname NOT LIKE 'pg_%'
                    AND schemaname != 'information_schema'
                ORDER BY
                    schemaname, tablename, indexname
            """)
            
            for idx in cursor.fetchall():
                schema_info["indexes"].append({
                    "schema": idx["schemaname"],
                    "table": idx["tablename"],
                    "name": idx["indexname"],
                    "definition": idx["indexdef"]
                })
            
            return schema_info
        
        except Exception as e:
            logger.error(f"スキーマ取得エラー: {str(e)}")
            return {"error": str(e)}
        
        finally:
            if cursor:
                cursor.close()

def sanitize_sql(sql: str) -> Tuple[bool, str]:
    """
    SQLインジェクションを防ぐためのSQLサニタイズ
    
    Args:
        sql: サニタイズするSQL文
        
    Returns:
        Tuple[bool, str]: (安全かどうか, エラーメッセージ)
    """
    # 危険なパターンをチェック
    for pattern in DANGEROUS_SQL_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE | re.MULTILINE):
            return False, f"危険なSQLパターンが検出されました: {pattern}"
    
    # トリムして最初の単語を取得（コマンドタイプ）
    command = sql.strip().split()[0].upper() if sql.strip() else ""
    
    # 安全なコマンドのホワイトリストチェック
    safe_command = False
    for safe_op in SAFE_SQL_OPERATIONS:
        if command == safe_op.split()[0] or sql.strip().upper().startswith(safe_op):
            safe_command = True
            break
    
    if not safe_command:
        return False, f"許可されていないSQLコマンドです: {command}"
    
    return True, ""

class DatabaseQueryTool(BaseTool):
    """データベースクエリ実行ツール"""
    
    name: str = "データベースクエリ実行"
    description: str = "SQLデータベース（SQLite、PostgreSQL）に対してクエリを実行し、結果を返します。"
    
    def __init__(self, db_type: str = "sqlite", connection_string: str = ":memory:"):
        """
        データベースクエリ実行ツールを初期化
        
        Args:
            db_type: データベースタイプ（'sqlite' または 'postgresql'）
            connection_string: データベース接続文字列
        """
        super().__init__()
        self.db_type = db_type.lower()
        self.connection_string = connection_string
        
        # 適切なハンドラーを選択
        if self.db_type == "sqlite":
            self.db_handler = SQLiteHandler(connection_string)
        elif self.db_type == "postgresql":
            self.db_handler = PostgreSQLHandler(connection_string)
        else:
            raise ValueError(f"サポートされていないデータベースタイプです: {db_type}")
    
    def _run(self, query: str, sanitize: bool = True) -> str:
        """
        SQLクエリを実行して結果を返す
        
        Args:
            query: 実行するSQLクエリ
            sanitize: SQLインジェクション防止のためのサニタイズを行うかどうか
            
        Returns:
            str: クエリ実行結果またはエラーメッセージ
        """
        logger.info(f"データベースクエリを実行: {query[:100]}...")
        
        # SQLサニタイズ
        if sanitize:
            is_safe, error_msg = sanitize_sql(query)
            if not is_safe:
                return f"SQLセキュリティエラー: {error_msg}"
        
        # クエリ実行
        with self.db_handler.connection_context():
            success, result, message = self.db_handler.execute_query(query)
            
            if not success:
                return f"クエリ実行エラー: {message}"
            
            # 結果を整形して返す
            if isinstance(result, list):
                if result:
                    # DataFrameに変換して表示
                    df = pd.DataFrame(result)
                    table_str = df.to_string(index=False)
                    return f"クエリ成功: {message}\n\n{table_str}"
                else:
                    return f"クエリ成功: {message}\n結果セットが空です。"
            else:
                return f"クエリ成功: {message}"

class DatabaseSchemaTool(BaseTool):
    """データベーススキーマ取得ツール"""
    
    name: str = "データベーススキーマ取得"
    description: str = "SQLデータベース（SQLite、PostgreSQL）のスキーマ情報を取得します。"
    
    def __init__(self, db_type: str = "sqlite", connection_string: str = ":memory:"):
        """
        データベーススキーマ取得ツールを初期化
        
        Args:
            db_type: データベースタイプ（'sqlite' または 'postgresql'）
            connection_string: データベース接続文字列
        """
        super().__init__()
        self.db_type = db_type.lower()
        self.connection_string = connection_string
        
        # 適切なハンドラーを選択
        if self.db_type == "sqlite":
            self.db_handler = SQLiteHandler(connection_string)
        elif self.db_type == "postgresql":
            self.db_handler = PostgreSQLHandler(connection_string)
        else:
            raise ValueError(f"サポートされていないデータベースタイプです: {db_type}")
    
    def _run(self, format: str = "text") -> str:
        """
        データベーススキーマを取得して結果を返す
        
        Args:
            format: 出力フォーマット（'text' または 'json'）
            
        Returns:
            str: スキーマ情報またはエラーメッセージ
        """
        logger.info(f"データベーススキーマを取得しています...")
        
        with self.db_handler.connection_context():
            schema_info = self.db_handler.get_schema()
            
            if "error" in schema_info:
                return f"スキーマ取得エラー: {schema_info['error']}"
            
            if format.lower() == "json":
                return json.dumps(schema_info, indent=2, ensure_ascii=False)
            else:
                # テキスト形式での整形
                text_output = []
                
                # スキーマ情報（PostgreSQLのみ）
                if "schemas" in schema_info and schema_info["schemas"]:
                    text_output.append("== スキーマ ==")
                    for schema in schema_info["schemas"]:
                        text_output.append(f"- {schema['schema_name']} (所有者: {schema['schema_owner']})")
                    text_output.append("")
                
                # テーブル情報
                if schema_info["tables"]:
                    text_output.append("== テーブル ==")
                    for table in schema_info["tables"]:
                        # PostgreSQLの場合はスキーマ情報も表示
                        table_header = table.get("schema", "") + "." if "schema" in table else ""
                        table_header += table["name"]
                        text_output.append(f"- {table_header}")
                        
                        # 列情報
                        text_output.append("  列:")
                        for col in table["columns"]:
                            nullable = "NULL" if not col.get("not_null", False) else "NOT NULL"
                            pk = "PK" if col.get("is_primary_key", False) or col["name"] in table.get("primary_keys", []) else ""
                            default = f"DEFAULT {col['default_value']}" if col.get("default_value") else ""
                            
                            col_info = f"    - {col['name']} ({col['type']}) {nullable} {default} {pk}".strip()
                            text_output.append(col_info)
                        
                        # 外部キー情報
                        if table.get("foreign_keys"):
                            text_output.append("  外部キー:")
                            for fk in table["foreign_keys"]:
                                if "references" in fk:  # PostgreSQL形式
                                    ref = fk["references"]
                                    fk_info = f"    - {fk['column']} -> {ref.get('schema', '')}.{ref['table']}.{ref['column']}"
                                else:  # SQLite形式
                                    fk_info = f"    - {fk['from_column']} -> {fk['referenced_table']}.{fk['to_column']}"
                                text_output.append(fk_info)
                        
                        text_output.append("")
                
                # ビュー情報
                if schema_info["views"]:
                    text_output.append("== ビュー ==")
                    for view in schema_info["views"]:
                        # PostgreSQLの場合はスキーマ情報も表示
                        view_header = view.get("schema", "") + "." if "schema" in view else ""
                        view_header += view["name"]
                        text_output.append(f"- {view_header}")
                        
                        # 定義があれば表示
                        if "definition" in view and view["definition"]:
                            # 定義を整形して表示
                            definition = textwrap.indent(view["definition"], "    ")
                            text_output.append("  定義:")
                            text_output.append(f"{definition}")
                        
                        text_output.append("")
                
                # インデックス情報
                if schema_info["indexes"]:
                    text_output.append("== インデックス ==")
                    for idx in schema_info["indexes"]:
                        # PostgreSQLの場合はスキーマ情報も表示
                        idx_header = idx.get("schema", "") + "." if "schema" in idx else ""
                        idx_header += f"{idx['name']} (テーブル: {idx['table']})"
                        text_output.append(f"- {idx_header}")
                        
                        # 定義があれば表示
                        if "definition" in idx and idx["definition"]:
                            text_output.append(f"  {idx['definition']}")
                        
                        text_output.append("")
                
                return "\n".join(text_output)

class DatabaseManagementTool(BaseTool):
    """データベース管理ツール"""
    
    name: str = "データベース管理"
    description: str = "SQLiteデータベースの作成、削除、バックアップなどの管理操作を行います。"
    
    def _run(self, action: str, db_path: str, target_path: Optional[str] = None) -> str:
        """
        データベース管理操作を実行
        
        Args:
            action: 管理操作（'create', 'delete', 'backup', 'restore', 'info'）
            db_path: 対象データベースパス
            target_path: バックアップ/リストアの対象パス（オプション）
            
        Returns:
            str: 操作結果またはエラーメッセージ
        """
        logger.info(f"データベース管理操作: {action}, DB: {db_path}")
        
        # パスのサニタイズ（ディレクトリトラバーサル防止）
        db_path = os.path.abspath(db_path)
        if target_path:
            target_path = os.path.abspath(target_path)
        
        if action == "create":
            return self._create_database(db_path)
        elif action == "delete":
            return self._delete_database(db_path)
        elif action == "backup":
            if not target_path:
                return "バックアップには target_path パラメータが必要です。"
            return self._backup_database(db_path, target_path)
        elif action == "restore":
            if not target_path:
                return "リストアには target_path パラメータが必要です。"
            return self._restore_database(target_path, db_path)
        elif action == "info":
            return self._database_info(db_path)
        else:
            return f"サポートされていない操作です: {action}"
    
    def _create_database(self, db_path: str) -> str:
        """空のSQLiteデータベースを作成"""
        try:
            # 親ディレクトリが存在することを確認
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
            # 接続を作成して即閉じる
            conn = sqlite3.connect(db_path)
            conn.close()
            
            return f"データベースを作成しました: {db_path}"
        except Exception as e:
            return f"データベース作成エラー: {str(e)}"
    
    def _delete_database(self, db_path: str) -> str:
        """SQLiteデータベースファイルを削除"""
        try:
            if not os.path.exists(db_path):
                return f"データベースが見つかりません: {db_path}"
            
            os.remove(db_path)
            return f"データベースを削除しました: {db_path}"
        except Exception as e:
            return f"データベース削除エラー: {str(e)}"
    
    def _backup_database(self, db_path: str, backup_path: str) -> str:
        """SQLiteデータベースをバックアップ"""
        try:
            if not os.path.exists(db_path):
                return f"データベースが見つかりません: {db_path}"
            
            # 親ディレクトリが存在することを確認
            os.makedirs(os.path.dirname(os.path.abspath(backup_path)), exist_ok=True)
            
            # データベースバックアップの実行
            src_conn = sqlite3.connect(db_path)
            dst_conn = sqlite3.connect(backup_path)
            
            with dst_conn:
                src_conn.backup(dst_conn)
            
            src_conn.close()
            dst_conn.close()
            
            return f"データベースをバックアップしました: {db_path} -> {backup_path}"
        except Exception as e:
            return f"データベースバックアップエラー: {str(e)}"
    
    def _restore_database(self, backup_path: str, db_path: str) -> str:
        """SQLiteデータベースをリストア"""
        try:
            if not os.path.exists(backup_path):
                return f"バックアップが見つかりません: {backup_path}"
            
            # 親ディレクトリが存在することを確認
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
            # データベースリストアの実行（バックアップの逆）
            src_conn = sqlite3.connect(backup_path)
            dst_conn = sqlite3.connect(db_path)
            
            with dst_conn:
                src_conn.backup(dst_conn)
            
            src_conn.close()
            dst_conn.close()
            
            return f"データベースをリストアしました: {backup_path} -> {db_path}"
        except Exception as e:
            return f"データベースリストアエラー: {str(e)}"
    
    def _database_info(self, db_path: str) -> str:
        """SQLiteデータベースの基本情報を取得"""
        try:
            if not os.path.exists(db_path):
                return f"データベースが見つかりません: {db_path}"
            
            # ファイル情報
            file_size = os.path.getsize(db_path)
            modified_time = os.path.getmtime(db_path)
            modified_time_str = pd.Timestamp(modified_time, unit='s').strftime('%Y-%m-%d %H:%M:%S')
            
            # データベース内のテーブル数を取得
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # ページサイズとページ数を取得
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            conn.close()
            
            # 整形した情報
            info = f"""データベース情報: {db_path}
ファイルサイズ: {file_size} バイト ({file_size / (1024*1024):.2f} MB)
最終更新日時: {modified_time_str}
テーブル数: {table_count}
ページサイズ: {page_size} バイト
ページ数: {page_count}
DB実際サイズ: {page_size * page_count} バイト ({(page_size * page_count) / (1024*1024):.2f} MB)
"""
            return info
        except Exception as e:
            return f"データベース情報取得エラー: {str(e)}" 