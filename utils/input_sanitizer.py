"""
入力サニタイズモジュール。
外部からの入力データを検証し、浄化するための機能を提供します。
XSS攻撃やSQLインジェクション、パス操作などの脆弱性を防ぎます。
"""

import re
import html
import os
import json
from typing import Any, Dict, List, Union, Optional, Callable
from pathlib import Path
from urllib.parse import urlparse, urlencode, quote, unquote
import bleach
from bleach.sanitizer import ALLOWED_TAGS, ALLOWED_ATTRIBUTES

from utils.logger import get_structured_logger

# ロガー設定
logger = get_structured_logger("input_sanitizer")

# HTML許可タグ・属性の設定（デフォルトは制限的）
DEFAULT_ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 
    'ol', 'strong', 'ul', 'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 
    'h4', 'h5', 'h6', 'hr', 'pre'
]

DEFAULT_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'abbr': ['title'],
    'acronym': ['title'],
    'span': ['class'],
    'div': ['class'],
    'p': ['class'],
    'code': ['class'],
    'pre': ['class'],
}

# 危険なファイル拡張子
DANGEROUS_EXTENSIONS = [
    '.php', '.phtml', '.php3', '.php4', '.php5', '.php7', '.pht', '.phar', '.phps',
    '.cgi', '.pl', '.py', '.pyc', '.pyo', '.sh', '.bash', '.htaccess', '.htpasswd',
    '.exe', '.dll', '.com', '.bat', '.cmd', '.vbs', '.js', '.jar', '.jsp', '.jspx',
    '.asp', '.aspx', '.cs', '.cshtml', '.config', '.asa', '.asax', '.ascx', '.ashx',
    '.asmx', '.cert', '.shtml', '.swf'
]

# 危険なSQLパターン
SQL_INJECTION_PATTERNS = [
    r'(\s|^)(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)(\s|$)',
    r'(\s|^)(UNION\s+ALL|UNION)(\s|$)',
    r'--',
    r'/\*.*\*/',
    r';\s*$'
]


class InputSanitizer:
    """入力サニタイズ処理を提供するクラス"""
    
    def __init__(
        self, 
        allowed_tags: List[str] = None,
        allowed_attributes: Dict[str, List[str]] = None
    ):
        """
        Args:
            allowed_tags: 許可するHTMLタグのリスト
            allowed_attributes: 許可するHTML属性の辞書
        """
        self.allowed_tags = allowed_tags or DEFAULT_ALLOWED_TAGS
        self.allowed_attributes = allowed_attributes or DEFAULT_ALLOWED_ATTRIBUTES
    
    def sanitize_html(self, input_str: str) -> str:
        """
        HTMLをサニタイズし、安全なマークアップのみを許可する
        
        Args:
            input_str: サニタイズする入力文字列
            
        Returns:
            str: サニタイズされた文字列
        """
        if not input_str:
            return ""
        
        try:
            # Bleachを使用してHTMLをサニタイズ
            sanitized = bleach.clean(
                input_str,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                strip=True
            )
            return sanitized
        except Exception as e:
            logger.error(f"HTMLサニタイズに失敗しました: {str(e)}")
            # 失敗した場合は全てのHTMLタグをエスケープ
            return html.escape(input_str)
    
    def strip_all_tags(self, input_str: str) -> str:
        """
        全てのHTMLタグを削除し、プレーンテキストのみを残す
        
        Args:
            input_str: サニタイズする入力文字列
            
        Returns:
            str: サニタイズされた文字列
        """
        if not input_str:
            return ""
        
        try:
            # Bleachを使用して全てのタグを削除
            sanitized = bleach.clean(input_str, tags=[], strip=True)
            return sanitized
        except Exception as e:
            logger.error(f"HTMLタグ削除に失敗しました: {str(e)}")
            # 失敗した場合は全てのHTMLタグをエスケープ
            return html.escape(input_str)
    
    def sanitize_filename(self, filename: str) -> str:
        """
        ファイル名をサニタイズし、安全なファイル名のみを許可する
        
        Args:
            filename: サニタイズするファイル名
            
        Returns:
            str: サニタイズされたファイル名
        """
        if not filename:
            return ""
        
        try:
            # 基本的なパス操作対策
            sanitized = os.path.basename(filename)
            
            # 危険な文字を削除
            sanitized = re.sub(r'[\\/?%*:|"<>]', '_', sanitized)
            
            # 隠しファイル対策
            sanitized = sanitized.lstrip('.')
            
            # 拡張子チェック
            _, ext = os.path.splitext(sanitized.lower())
            if ext in DANGEROUS_EXTENSIONS:
                sanitized = sanitized + ".txt"
            
            return sanitized
        except Exception as e:
            logger.error(f"ファイル名サニタイズに失敗しました: {str(e)}")
            # 失敗した場合は安全な文字列に置換
            return "sanitized_file.txt"
    
    def sanitize_filepath(self, filepath: str, allowed_dirs: List[str] = None) -> str:
        """
        ファイルパスをサニタイズし、許可されたディレクトリのみにアクセス可能にする
        
        Args:
            filepath: サニタイズするファイルパス
            allowed_dirs: 許可するディレクトリのリスト
            
        Returns:
            str: サニタイズされたファイルパス
        """
        if not filepath:
            return ""
        
        try:
            # パスの正規化
            normalized = os.path.normpath(filepath)
            
            # 絶対パスの場合
            if os.path.isabs(normalized):
                # 許可されたディレクトリに含まれているか確認
                if allowed_dirs:
                    for allowed_dir in allowed_dirs:
                        # 正規化して比較
                        allowed_dir = os.path.normpath(allowed_dir)
                        
                        # パスが許可されたディレクトリ内にあるか確認
                        if normalized.startswith(allowed_dir + os.sep):
                            return normalized
                    
                    # どの許可ディレクトリにも含まれない場合
                    logger.warning(f"許可されていないディレクトリへのアクセス試行: {filepath}")
                    return ""
                else:
                    # 許可ディレクトリが指定されていない場合は、相対パスに変換
                    return os.path.basename(normalized)
            
            # 相対パスの場合
            # パス操作（../）の除去
            parts = normalized.split(os.sep)
            clean_parts = []
            
            for part in parts:
                if part in ('', '.'):
                    continue
                elif part == '..':
                    # 親ディレクトリの参照を削除
                    if clean_parts:
                        clean_parts.pop()
                else:
                    clean_parts.append(part)
            
            # ファイル名の危険な文字を削除
            filename = clean_parts[-1] if clean_parts else ''
            clean_parts[-1] = self.sanitize_filename(filename) if clean_parts else ''
            
            return os.path.join(*clean_parts) if clean_parts else ""
        except Exception as e:
            logger.error(f"ファイルパスサニタイズに失敗しました: {str(e)}")
            return ""
    
    def check_sql_injection(self, input_str: str) -> bool:
        """
        SQLインジェクション攻撃のパターンをチェック
        
        Args:
            input_str: チェックする入力文字列
            
        Returns:
            bool: SQLインジェクションパターンが検出されればTrue
        """
        if not input_str:
            return False
        
        try:
            # 大文字小文字を区別せずにチェック
            input_upper = input_str.upper()
            
            for pattern in SQL_INJECTION_PATTERNS:
                if re.search(pattern, input_upper, re.IGNORECASE):
                    logger.warning(f"SQLインジェクションパターンを検出: {input_str}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"SQLインジェクションチェックに失敗しました: {str(e)}")
            # 失敗した場合は安全側に倒して真を返す
            return True
    
    def sanitize_url(self, url: str, allowed_schemes: List[str] = None) -> str:
        """
        URLをサニタイズし、安全なURLのみを許可する
        
        Args:
            url: サニタイズするURL
            allowed_schemes: 許可するスキーム（http, https等）
            
        Returns:
            str: サニタイズされたURL、不正な場合は空文字
        """
        if not url:
            return ""
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            # URLをパース
            parsed = urlparse(url)
            
            # スキームをチェック
            if parsed.scheme not in allowed_schemes:
                logger.warning(f"許可されていないURLスキーム: {url}")
                return ""
            
            # 最低限のURLコンポーネントがあるか確認
            if not parsed.netloc:
                logger.warning(f"不正なURLフォーマット: {url}")
                return ""
            
            # 特殊文字をエンコード
            path = quote(parsed.path)
            query = urlencode(dict(item.split('=') for item in parsed.query.split('&') if '=' in item)) if parsed.query else ''
            fragment = quote(parsed.fragment)
            
            # URLを再構築
            sanitized = f"{parsed.scheme}://{parsed.netloc}{path}"
            if query:
                sanitized += f"?{query}"
            if fragment:
                sanitized += f"#{fragment}"
            
            return sanitized
        except Exception as e:
            logger.error(f"URLサニタイズに失敗しました: {str(e)}")
            return ""
    
    def sanitize_json(self, json_data: str) -> Dict[str, Any]:
        """
        JSON文字列をサニタイズして安全にロード
        
        Args:
            json_data: サニタイズするJSON文字列
            
        Returns:
            Dict[str, Any]: パースされたJSONデータ、エラー時は空辞書
        """
        if not json_data:
            return {}
        
        try:
            # JSONパース
            parsed = json.loads(json_data)
            return parsed
        except Exception as e:
            logger.error(f"JSONパースに失敗しました: {str(e)}")
            return {}
    
    def sanitize_int(self, input_str: str, min_value: int = None, max_value: int = None) -> Optional[int]:
        """
        入力を整数としてサニタイズし、範囲チェックを行う
        
        Args:
            input_str: サニタイズする入力文字列
            min_value: 最小値
            max_value: 最大値
            
        Returns:
            Optional[int]: サニタイズされた整数、変換できない場合はNone
        """
        if not input_str:
            return None
        
        try:
            # 整数に変換
            value = int(input_str)
            
            # 範囲チェック
            if min_value is not None and value < min_value:
                logger.warning(f"入力値が最小値より小さい: {value} < {min_value}")
                return min_value
            
            if max_value is not None and value > max_value:
                logger.warning(f"入力値が最大値より大きい: {value} > {max_value}")
                return max_value
            
            return value
        except Exception as e:
            logger.error(f"整数変換に失敗しました: {str(e)}")
            return None
    
    def sanitize_float(self, input_str: str, min_value: float = None, max_value: float = None) -> Optional[float]:
        """
        入力を浮動小数点数としてサニタイズし、範囲チェックを行う
        
        Args:
            input_str: サニタイズする入力文字列
            min_value: 最小値
            max_value: 最大値
            
        Returns:
            Optional[float]: サニタイズされた浮動小数点数、変換できない場合はNone
        """
        if not input_str:
            return None
        
        try:
            # 浮動小数点数に変換
            value = float(input_str)
            
            # 範囲チェック
            if min_value is not None and value < min_value:
                logger.warning(f"入力値が最小値より小さい: {value} < {min_value}")
                return min_value
            
            if max_value is not None and value > max_value:
                logger.warning(f"入力値が最大値より大きい: {value} > {max_value}")
                return max_value
            
            return value
        except Exception as e:
            logger.error(f"浮動小数点数変換に失敗しました: {str(e)}")
            return None
    
    def sanitize_string(self, input_str: str, max_length: int = None, pattern: str = None) -> str:
        """
        文字列をサニタイズし、長さと内容のチェックを行う
        
        Args:
            input_str: サニタイズする文字列
            max_length: 最大長
            pattern: 許可するパターン（正規表現）
            
        Returns:
            str: サニタイズされた文字列
        """
        if not input_str:
            return ""
        
        try:
            # 文字列に変換
            value = str(input_str)
            
            # 長さチェック
            if max_length is not None and len(value) > max_length:
                logger.warning(f"文字列が最大長を超えています: {len(value)} > {max_length}")
                value = value[:max_length]
            
            # パターンチェック
            if pattern is not None and not re.match(pattern, value):
                logger.warning(f"文字列がパターンに一致しません: {value} !~ {pattern}")
                return ""
            
            return value
        except Exception as e:
            logger.error(f"文字列サニタイズに失敗しました: {str(e)}")
            return ""
    
    def sanitize_email(self, email: str) -> str:
        """
        メールアドレスをサニタイズし、有効なメールアドレスのみを許可する
        
        Args:
            email: サニタイズするメールアドレス
            
        Returns:
            str: サニタイズされたメールアドレス、無効な場合は空文字
        """
        if not email:
            return ""
        
        try:
            # 基本的なメールアドレスパターン
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(pattern, email):
                return email
            else:
                logger.warning(f"無効なメールアドレス: {email}")
                return ""
        except Exception as e:
            logger.error(f"メールアドレスサニタイズに失敗しました: {str(e)}")
            return ""
    
    def sanitize_dict(
        self,
        input_dict: Dict[str, Any],
        schema: Dict[str, Dict[str, Any]] = None,
        sanitize_unknown: bool = True
    ) -> Dict[str, Any]:
        """
        辞書データをサニタイズし、スキーマに従って検証する
        
        Args:
            input_dict: サニタイズする辞書
            schema: フィールド名とサニタイズ方法のスキーマ
                形式: {'field_name': {'type': 'string', 'max_length': 100, 'required': True}}
            sanitize_unknown: スキーマに含まれないフィールドをサニタイズするか
            
        Returns:
            Dict[str, Any]: サニタイズされた辞書
        """
        if not input_dict:
            return {}
        
        if not schema:
            # スキーマがない場合は単純な文字列サニタイズのみ
            return {k: self.sanitize_string(v) if isinstance(v, str) else v for k, v in input_dict.items()}
        
        result = {}
        
        # スキーマの各フィールドに対して処理
        for field_name, field_schema in schema.items():
            field_type = field_schema.get('type', 'string')
            required = field_schema.get('required', False)
            
            # フィールドが存在するかチェック
            if field_name not in input_dict:
                if required:
                    logger.warning(f"必須フィールドがありません: {field_name}")
                continue
            
            value = input_dict[field_name]
            
            # 型に基づいてサニタイズ
            if field_type == 'string':
                max_length = field_schema.get('max_length')
                pattern = field_schema.get('pattern')
                result[field_name] = self.sanitize_string(value, max_length, pattern)
            
            elif field_type == 'html':
                result[field_name] = self.sanitize_html(value)
            
            elif field_type == 'int':
                min_value = field_schema.get('min')
                max_value = field_schema.get('max')
                sanitized = self.sanitize_int(value, min_value, max_value)
                if sanitized is not None:
                    result[field_name] = sanitized
            
            elif field_type == 'float':
                min_value = field_schema.get('min')
                max_value = field_schema.get('max')
                sanitized = self.sanitize_float(value, min_value, max_value)
                if sanitized is not None:
                    result[field_name] = sanitized
            
            elif field_type == 'email':
                result[field_name] = self.sanitize_email(value)
            
            elif field_type == 'url':
                allowed_schemes = field_schema.get('allowed_schemes')
                result[field_name] = self.sanitize_url(value, allowed_schemes)
            
            elif field_type == 'filename':
                result[field_name] = self.sanitize_filename(value)
            
            elif field_type == 'filepath':
                allowed_dirs = field_schema.get('allowed_dirs')
                result[field_name] = self.sanitize_filepath(value, allowed_dirs)
            
            else:
                # 未知の型はそのまま
                result[field_name] = value
        
        # スキーマに含まれないフィールドの処理
        if sanitize_unknown:
            for field_name, value in input_dict.items():
                if field_name not in schema:
                    if isinstance(value, str):
                        result[field_name] = self.sanitize_string(value)
                    else:
                        result[field_name] = value
        
        return result


# シングルトンインスタンス
input_sanitizer = InputSanitizer()


# ヘルパー関数
def sanitize_html(input_str: str) -> str:
    """HTMLをサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_html(input_str)


def strip_all_tags(input_str: str) -> str:
    """全てのHTMLタグを削除するヘルパー関数"""
    return input_sanitizer.strip_all_tags(input_str)


def sanitize_filename(filename: str) -> str:
    """ファイル名をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_filename(filename)


def sanitize_filepath(filepath: str, allowed_dirs: List[str] = None) -> str:
    """ファイルパスをサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_filepath(filepath, allowed_dirs)


def check_sql_injection(input_str: str) -> bool:
    """SQLインジェクションをチェックするヘルパー関数"""
    return input_sanitizer.check_sql_injection(input_str)


def sanitize_url(url: str, allowed_schemes: List[str] = None) -> str:
    """URLをサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_url(url, allowed_schemes)


def sanitize_json(json_str: str) -> Dict[str, Any]:
    """JSON文字列をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_json(json_str)


def sanitize_int(input_str: str, min_value: int = None, max_value: int = None) -> Optional[int]:
    """整数をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_int(input_str, min_value, max_value)


def sanitize_float(input_str: str, min_value: float = None, max_value: float = None) -> Optional[float]:
    """浮動小数点数をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_float(input_str, min_value, max_value)


def sanitize_string(input_str: str, max_length: int = None, pattern: str = None) -> str:
    """文字列をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_string(input_str, max_length, pattern)


def sanitize_email(email: str) -> str:
    """メールアドレスをサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_email(email)


def sanitize_dict(
    input_dict: Dict[str, Any],
    schema: Dict[str, Dict[str, Any]] = None,
    sanitize_unknown: bool = True
) -> Dict[str, Any]:
    """辞書をサニタイズするヘルパー関数"""
    return input_sanitizer.sanitize_dict(input_dict, schema, sanitize_unknown) 