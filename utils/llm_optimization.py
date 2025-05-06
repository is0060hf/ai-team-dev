"""
LLM (大規模言語モデル) 呼び出しの最適化モジュール。
トークン削減、バッチ処理、プロンプト最適化などの機能を提供します。
"""

import time
import hashlib
import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import concurrent.futures
from datetime import datetime, timedelta

import tiktoken
import openai
from openai import OpenAI

from utils.logger import get_structured_logger
from utils.tracing import trace, trace_span
from utils.config import config
from utils.performance import time_operation

# ロガーの設定
logger = get_structured_logger("llm_optimization")

# OpenAIクライアントの初期化
client = OpenAI(api_key=config.OPENAI_API_KEY)

# 各モデルの最大トークン数
MODEL_MAX_TOKENS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
}

# エンコーダーのキャッシュ
_encoder_cache = {}


def get_encoder_for_model(model_name: str):
    """
    指定されたモデル用のエンコーダーを取得
    
    Args:
        model_name: モデル名
        
    Returns:
        tiktoken.Encoding: エンコーダー
    """
    if model_name in _encoder_cache:
        return _encoder_cache[model_name]
    
    try:
        # 適切なエンコーディングを使用
        if "gpt-4" in model_name:
            encoder = tiktoken.encoding_for_model("gpt-4")
        elif "gpt-3.5" in model_name:
            encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
        else:
            encoder = tiktoken.get_encoding("cl100k_base")  # デフォルトエンコーディング
        
        _encoder_cache[model_name] = encoder
        return encoder
    except Exception as e:
        logger.error(f"エンコーダーの取得に失敗しました: {str(e)}")
        # 失敗した場合はデフォルトエンコーディングを使用
        default_encoder = tiktoken.get_encoding("cl100k_base")
        _encoder_cache[model_name] = default_encoder
        return default_encoder


@trace("count_tokens")
def count_tokens(text: str, model_name: str = "gpt-4o") -> int:
    """
    テキストのトークン数をカウント
    
    Args:
        text: テキスト
        model_name: モデル名
        
    Returns:
        int: トークン数
    """
    encoder = get_encoder_for_model(model_name)
    tokens = encoder.encode(text)
    return len(tokens)


@trace("count_message_tokens")
def count_message_tokens(messages: List[Dict[str, str]], model_name: str = "gpt-4o") -> int:
    """
    メッセージのトークン数をカウント
    
    Args:
        messages: メッセージリスト（role, contentを含む辞書のリスト）
        model_name: モデル名
        
    Returns:
        int: トークン数
    """
    encoder = get_encoder_for_model(model_name)
    total_tokens = 0
    
    # メッセージごとにトークン数をカウント
    for message in messages:
        # roleとcontentのトークン数
        total_tokens += 4  # 各メッセージのオーバーヘッド
        
        for key, value in message.items():
            total_tokens += len(encoder.encode(str(value)))
    
    # 最終的なオーバーヘッド
    total_tokens += 2  # チャット補完のためのオーバーヘッド
    
    return total_tokens


@trace("truncate_text")
def truncate_text(text: str, max_tokens: int, model_name: str = "gpt-4o") -> str:
    """
    テキストを指定したトークン数に切り詰める
    
    Args:
        text: テキスト
        max_tokens: 最大トークン数
        model_name: モデル名
        
    Returns:
        str: 切り詰められたテキスト
    """
    encoder = get_encoder_for_model(model_name)
    tokens = encoder.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
    
    truncated_tokens = tokens[:max_tokens]
    truncated_text = encoder.decode(truncated_tokens)
    
    logger.info(f"テキストを {len(tokens)} トークンから {max_tokens} トークンに切り詰めました")
    
    return truncated_text


@trace("optimize_prompt")
def optimize_prompt(prompt: str, model_name: str = "gpt-4o") -> str:
    """
    プロンプトを最適化してトークン数を削減
    
    Args:
        prompt: 最適化するプロンプト
        model_name: モデル名
        
    Returns:
        str: 最適化されたプロンプト
    """
    # 冗長な表現を削除
    optimizations = [
        (r"お願いします。", "。"),
        (r"ありがとうございます。", "。"),
        (r"(\w+)をしてください", r"\1せよ"),
        (r"(\w+)してください", r"\1せよ"),
        (r"以下の(\w+)について", r"次の\1:"),
        (r"次に示す(\w+)は", r"次の\1:"),
        (r"(\w+)を提供してください", r"\1を示せ"),
        (r"(\w+)を説明してください", r"\1とは"),
        (r"詳細に(\w+)してください", r"\1せよ"),
        (r"できるだけ詳しく", ""),
        (r"可能な限り", ""),
        (r"(\w+)する必要があります", r"\1せよ"),
        (r"私は(\w+)を知りたいです", r"\1は?"),
    ]
    
    original_prompt = prompt
    for pattern, replacement in optimizations:
        prompt = re.sub(pattern, replacement, prompt)
    
    # 空白行を削除
    prompt = re.sub(r'\n\s*\n', '\n', prompt)
    
    # 過剰な空白を削除
    prompt = re.sub(r' +', ' ', prompt)
    prompt = prompt.strip()
    
    # 効果を測定
    original_tokens = count_tokens(original_prompt, model_name)
    optimized_tokens = count_tokens(prompt, model_name)
    savings = original_tokens - optimized_tokens
    
    logger.info(f"プロンプト最適化: {savings} トークン削減 ({original_tokens} → {optimized_tokens})")
    
    return prompt


@trace("optimize_messages")
def optimize_messages(messages: List[Dict[str, str]], model_name: str = "gpt-4o", max_tokens: Optional[int] = None) -> List[Dict[str, str]]:
    """
    メッセージリストを最適化
    
    Args:
        messages: メッセージリスト
        model_name: モデル名
        max_tokens: 最大トークン数（指定しない場合はモデルの最大値の80%）
        
    Returns:
        List[Dict[str, str]]: 最適化されたメッセージリスト
    """
    if not messages:
        return []
    
    # 最大トークン数を設定
    if max_tokens is None:
        model_max = MODEL_MAX_TOKENS.get(model_name, 4096)
        max_tokens = int(model_max * 0.8)  # 80%に設定
    
    original_messages = messages.copy()
    original_token_count = count_message_tokens(original_messages, model_name)
    
    # トークン数が既に制限内ならそのまま返す
    if original_token_count <= max_tokens:
        return original_messages
    
    # システムメッセージは保持
    system_messages = [m for m in messages if m.get("role") == "system"]
    system_tokens = count_message_tokens(system_messages, model_name)
    
    # 最新のユーザーメッセージとアシスタントメッセージを保持
    recent_messages = []
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") in ["user", "assistant"] and len(recent_messages) < 4:
            recent_messages.insert(0, messages[i])
    
    recent_tokens = count_message_tokens(recent_messages, model_name)
    
    # システムと最新メッセージが収まらない場合は内容を切り詰め
    if system_tokens + recent_tokens > max_tokens:
        # システムメッセージの内容を切り詰め
        remaining_tokens = max_tokens - recent_tokens
        
        # 各システムメッセージを均等に切り詰める
        if system_messages and remaining_tokens > 0:
            tokens_per_system = max(1, remaining_tokens // len(system_messages))
            for i, msg in enumerate(system_messages):
                content = msg.get("content", "")
                system_messages[i]["content"] = truncate_text(content, tokens_per_system, model_name)
        
        # システムメッセージを優先させ、最新のメッセージを切り詰める
        final_messages = system_messages + recent_messages
        return final_messages
    
    # 中間のメッセージを可能な限り保持
    middle_messages = [m for m in messages if m.get("role") not in ["system"] and m not in recent_messages]
    
    # 古いものから順にスキップ
    remaining_tokens = max_tokens - system_tokens - recent_tokens
    preserved_middle = []
    
    for msg in reversed(middle_messages):  # 新しいものから処理
        msg_tokens = count_message_tokens([msg], model_name)
        if remaining_tokens - msg_tokens >= 0:
            preserved_middle.insert(0, msg)  # 順序を維持
            remaining_tokens -= msg_tokens
        else:
            break
    
    # 最終的なメッセージを構築
    final_messages = system_messages + preserved_middle + recent_messages
    
    # 最終確認
    final_token_count = count_message_tokens(final_messages, model_name)
    if final_token_count > max_tokens:
        logger.warning(f"最適化後もトークン数が最大値を超えています: {final_token_count} > {max_tokens}")
    
    logger.info(f"メッセージを {original_token_count} トークンから {final_token_count} トークンに最適化しました")
    
    return final_messages


# プロンプトキャッシュのためのクラス
class PromptCache:
    """プロンプトとレスポンスをキャッシュするクラス"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Args:
            max_size: キャッシュの最大サイズ
            ttl_seconds: キャッシュエントリの有効期間（秒）
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def _generate_key(self, messages: List[Dict[str, str]], model: str, temperature: float) -> str:
        """キャッシュキーを生成"""
        cache_obj = {
            "messages": messages,
            "model": model,
            "temperature": temperature
        }
        serialized = json.dumps(cache_obj, sort_keys=True)
        return hashlib.md5(serialized.encode()).hexdigest()
    
    def get(self, messages: List[Dict[str, str]], model: str, temperature: float) -> Optional[Dict[str, Any]]:
        """
        キャッシュからレスポンスを取得
        
        Args:
            messages: メッセージリスト
            model: モデル名
            temperature: 温度パラメータ
            
        Returns:
            Optional[Dict[str, Any]]: キャッシュされたレスポンス（ない場合はNone）
        """
        cache_key = self._generate_key(messages, model, temperature)
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            # TTLチェック
            if datetime.now() < entry["expires_at"]:
                logger.info(f"キャッシュヒット: {cache_key[:8]}...")
                return entry["response"]
            else:
                # 期限切れエントリを削除
                logger.debug(f"キャッシュ期限切れ: {cache_key[:8]}...")
                del self.cache[cache_key]
        
        return None
    
    def set(self, messages: List[Dict[str, str]], model: str, temperature: float, response: Dict[str, Any]):
        """
        レスポンスをキャッシュに保存
        
        Args:
            messages: メッセージリスト
            model: モデル名
            temperature: 温度パラメータ
            response: キャッシュするレスポンス
        """
        cache_key = self._generate_key(messages, model, temperature)
        
        # キャッシュが最大サイズに達したら、最も古いエントリを削除
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["created_at"])
            del self.cache[oldest_key]
        
        expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)
        
        self.cache[cache_key] = {
            "response": response,
            "created_at": datetime.now(),
            "expires_at": expires_at
        }
        
        logger.info(f"キャッシュに保存: {cache_key[:8]}...")
    
    def clear(self):
        """キャッシュをクリア"""
        self.cache.clear()
        logger.info("キャッシュをクリアしました")
    
    def clear_expired(self):
        """期限切れのキャッシュエントリをクリア"""
        now = datetime.now()
        expired_keys = [k for k, v in self.cache.items() if now >= v["expires_at"]]
        
        for key in expired_keys:
            del self.cache[key]
        
        logger.info(f"{len(expired_keys)} 件の期限切れキャッシュエントリをクリアしました")


# シングルトンインスタンス
prompt_cache = PromptCache()


@trace("chat_completion_with_cache")
def chat_completion_with_cache(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    use_cache: bool = True,
    optimize: bool = True
) -> Dict[str, Any]:
    """
    キャッシュを利用したチャット補完
    
    Args:
        messages: メッセージリスト
        model: モデル名
        temperature: 温度パラメータ
        max_tokens: 最大トークン数
        use_cache: キャッシュを使用するかどうか
        optimize: メッセージを最適化するかどうか
        
    Returns:
        Dict[str, Any]: レスポンス
    """
    # メッセージの最適化
    if optimize:
        messages = optimize_messages(messages, model, max_tokens)
    
    # キャッシュチェック（temperature = 0の場合のみ）
    if use_cache and temperature == 0:
        cached_response = prompt_cache.get(messages, model, temperature)
        if cached_response:
            return cached_response
    
    # OpenAI APIを呼び出し
    with time_operation("openai_api_call"):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # レスポンスを辞書に変換
            response_dict = {
                "id": response.id,
                "object": response.object,
                "created": response.created,
                "model": response.model,
                "choices": [
                    {
                        "index": choice.index,
                        "message": {
                            "role": choice.message.role,
                            "content": choice.message.content
                        },
                        "finish_reason": choice.finish_reason
                    }
                    for choice in response.choices
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            # キャッシュに保存（temperature = 0の場合のみ）
            if use_cache and temperature == 0:
                prompt_cache.set(messages, model, temperature, response_dict)
            
            return response_dict
        except Exception as e:
            logger.error(f"OpenAI API呼び出しエラー: {str(e)}")
            raise


@trace("batch_completions")
def batch_completions(
    batch_messages: List[List[Dict[str, str]]],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    max_workers: int = 5
) -> List[Dict[str, Any]]:
    """
    複数のチャット補完リクエストを並列実行
    
    Args:
        batch_messages: メッセージリストのバッチ
        model: モデル名
        temperature: 温度パラメータ
        max_tokens: 最大トークン数
        max_workers: 最大並列数
        
    Returns:
        List[Dict[str, Any]]: レスポンスのリスト
    """
    responses = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                chat_completion_with_cache,
                messages,
                model,
                temperature,
                max_tokens
            )
            for messages in batch_messages
        ]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                responses.append(future.result())
            except Exception as e:
                logger.error(f"バッチ処理エラー: {str(e)}")
                responses.append({"error": str(e)})
    
    return responses


@trace("extract_key_information")
def extract_key_information(text: str, max_tokens: int = 1000, model_name: str = "gpt-4o") -> str:
    """
    テキストから重要な情報を抽出して要約
    
    Args:
        text: 元のテキスト
        max_tokens: 最大トークン数
        model_name: モデル名
        
    Returns:
        str: 重要情報を抽出した要約
    """
    current_tokens = count_tokens(text, model_name)
    
    # 既に制限内ならそのまま返す
    if current_tokens <= max_tokens:
        return text
    
    # 長いテキストから重要情報を抽出するためのプロンプト
    messages = [
        {"role": "system", "content": "あなたは長いテキストから最も重要な情報を抽出して要約するエキスパートです。オリジナルの意味を保ちながら、必要最小限の文章にしてください。"},
        {"role": "user", "content": f"以下のテキストから重要な情報のみを抽出し、{max_tokens}トークン以内に要約してください。\n\n{text}"}
    ]
    
    try:
        response = chat_completion_with_cache(
            messages=messages,
            model=model_name,
            temperature=0.3,
            max_tokens=max_tokens,
            optimize=False
        )
        
        summary = response["choices"][0]["message"]["content"]
        
        # 要約が目標トークン数を超えていないか確認
        summary_tokens = count_tokens(summary, model_name)
        if summary_tokens > max_tokens:
            # それでも長い場合は単純に切り詰める
            summary = truncate_text(summary, max_tokens, model_name)
        
        logger.info(f"テキストを {current_tokens} トークンから {count_tokens(summary, model_name)} トークンに要約しました")
        return summary
    
    except Exception as e:
        logger.error(f"テキスト要約エラー: {str(e)}")
        # エラーが発生した場合は単純に切り詰める
        return truncate_text(text, max_tokens, model_name)


@trace("optimize_function_calls")
def optimize_function_calls(functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    関数定義を最適化してトークン数を削減
    
    Args:
        functions: 関数定義のリスト
        
    Returns:
        List[Dict[str, Any]]: 最適化された関数定義
    """
    optimized_functions = []
    
    for func in functions:
        # 関数の説明を最適化
        if "description" in func:
            func["description"] = func["description"].strip()
        
        # パラメータの説明を最適化
        if "parameters" in func and "properties" in func["parameters"]:
            for param_name, param in func["parameters"]["properties"].items():
                if "description" in param:
                    param["description"] = param["description"].strip()
        
        optimized_functions.append(func)
    
    return optimized_functions


@trace("function_calling_with_retry")
def function_calling_with_retry(
    messages: List[Dict[str, str]],
    functions: List[Dict[str, Any]],
    model: str = "gpt-4o",
    max_retries: int = 3,
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    関数呼び出し機能を使用したChat APIリクエスト（リトライ機能付き）
    
    Args:
        messages: メッセージリスト
        functions: 関数定義のリスト
        model: モデル名
        max_retries: 最大リトライ回数
        temperature: 温度パラメータ
        
    Returns:
        Dict[str, Any]: レスポンス
    """
    # 関数定義の最適化
    optimized_functions = optimize_function_calls(functions)
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                functions=optimized_functions,
                function_call="auto",
                temperature=temperature
            )
            
            # レスポンスを辞書に変換
            response_dict = {
                "id": response.id,
                "object": response.object,
                "created": response.created,
                "model": response.model,
                "choices": [
                    {
                        "index": choice.index,
                        "message": {
                            "role": choice.message.role,
                            "content": choice.message.content,
                            "function_call": {
                                "name": choice.message.function_call.name,
                                "arguments": choice.message.function_call.arguments
                            } if choice.message.function_call else None
                        },
                        "finish_reason": choice.finish_reason
                    }
                    for choice in response.choices
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            return response_dict
        
        except Exception as e:
            retry_count += 1
            last_error = e
            wait_time = 2 ** retry_count  # 指数バックオフ
            
            logger.warning(f"関数呼び出しエラー (リトライ {retry_count}/{max_retries}): {str(e)}")
            time.sleep(wait_time)
    
    # すべてのリトライが失敗した場合
    logger.error(f"関数呼び出しが {max_retries} 回リトライ後も失敗しました: {str(last_error)}")
    raise last_error


# 定期的にキャッシュの期限切れエントリをクリアするスレッド
class CacheCleanupThread(threading.Thread):
    """キャッシュクリーンアップスレッド"""
    
    def __init__(self, interval: int = 3600):
        """
        Args:
            interval: 実行間隔（秒）
        """
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_event = threading.Event()
    
    def run(self):
        """スレッドの実行"""
        logger.info(f"キャッシュクリーンアップスレッドを開始しました（間隔: {self.interval}秒）")
        
        while not self.stop_event.is_set():
            try:
                prompt_cache.clear_expired()
            except Exception as e:
                logger.error(f"キャッシュクリーンアップ中にエラーが発生しました: {str(e)}")
            
            # 次の実行まで待機
            self.stop_event.wait(self.interval)
        
        logger.info("キャッシュクリーンアップスレッドを停止しました")
    
    def stop(self):
        """スレッドの停止"""
        self.stop_event.set()


# キャッシュクリーンアップスレッドのインスタンス
_cache_cleanup_thread = None


def start_cache_cleanup(interval: int = 3600):
    """
    キャッシュクリーンアップスレッドを開始
    
    Args:
        interval: 実行間隔（秒）
    """
    global _cache_cleanup_thread
    
    if _cache_cleanup_thread is not None and _cache_cleanup_thread.is_alive():
        logger.warning("キャッシュクリーンアップスレッドは既に実行中です")
        return
    
    _cache_cleanup_thread = CacheCleanupThread(interval)
    _cache_cleanup_thread.start()


def stop_cache_cleanup():
    """キャッシュクリーンアップスレッドを停止"""
    global _cache_cleanup_thread
    
    if _cache_cleanup_thread is None or not _cache_cleanup_thread.is_alive():
        logger.warning("キャッシュクリーンアップスレッドは実行されていません")
        return
    
    _cache_cleanup_thread.stop()
    _cache_cleanup_thread.join(timeout=5)
    _cache_cleanup_thread = None


# デフォルトでキャッシュクリーンアップスレッドを開始
start_cache_cleanup() 