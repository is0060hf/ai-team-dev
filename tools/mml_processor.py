"""
MML（Multimodal Markup Language）処理モジュール。
テキスト、画像、表、グラフなどの複数のメディアタイプを統合的に扱うためのマークアップ言語を処理します。
"""

import re
import json
import base64
import os
from enum import Enum
from typing import Dict, List, Any, Union, Optional, Tuple
from pathlib import Path
import mimetypes
import markdown
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
import io
import uuid
import html

from utils.logger import get_logger

logger = get_logger("mml_processor")

class MediaType(Enum):
    """MMLでサポートされるメディアタイプ"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TABLE = "table"
    CHART = "chart"
    CODE = "code"
    MATH = "math"
    LINK = "link"

class MMLElement:
    """MML要素の基底クラス"""
    
    def __init__(self, media_type: MediaType, content: Any, attributes: Dict[str, str] = None):
        self.media_type = media_type
        self.content = content
        self.attributes = attributes or {}
        self.id = self.attributes.get('id', str(uuid.uuid4()))
    
    def to_mml(self) -> str:
        """MMLフォーマットの文字列に変換"""
        attrs = ' '.join([f'{k}="{v}"' for k, v in self.attributes.items()])
        attrs_str = f" {attrs}" if attrs else ""
        
        if self.media_type == MediaType.TEXT:
            return self.content
        
        content_str = self._format_content()
        return f"<{self.media_type.value}{attrs_str}>{content_str}</{self.media_type.value}>"
    
    def _format_content(self) -> str:
        """メディアタイプに応じてコンテンツをフォーマット"""
        if self.media_type == MediaType.TEXT:
            return html.escape(self.content)
        elif self.media_type == MediaType.CODE:
            lang = self.attributes.get('language', '')
            return f"```{lang}\n{self.content}\n```"
        elif self.media_type == MediaType.MATH:
            return f"$${self.content}$$"
        elif self.media_type == MediaType.LINK:
            href = self.attributes.get('href', '#')
            return f"[{self.content}]({href})"
        elif self.media_type == MediaType.TABLE:
            if isinstance(self.content, pd.DataFrame):
                return self.content.to_html(index=False)
            return str(self.content)
        elif self.media_type in [MediaType.IMAGE, MediaType.AUDIO, MediaType.VIDEO]:
            if isinstance(self.content, str) and (os.path.exists(self.content) or self.content.startswith('http')):
                # パスやURLの場合はそのまま返す
                return self.content
            else:
                # バイナリデータの場合はBase64エンコード
                if isinstance(self.content, bytes):
                    binary_data = self.content
                else:
                    binary_data = self._get_binary_data()
                
                if not binary_data:
                    return "[バイナリデータの変換に失敗しました]"
                
                mime_type = self.attributes.get('mime_type')
                if not mime_type:
                    # 拡張子やバイナリシグネチャからMIMEタイプを推測
                    if isinstance(self.content, str) and os.path.exists(self.content):
                        mime_type, _ = mimetypes.guess_type(self.content)
                    else:
                        # デフォルトのMIMEタイプ
                        mime_type = {
                            MediaType.IMAGE: 'image/png',
                            MediaType.AUDIO: 'audio/mp3',
                            MediaType.VIDEO: 'video/mp4'
                        }.get(self.media_type, 'application/octet-stream')
                
                base64_data = base64.b64encode(binary_data).decode('utf-8')
                return f"data:{mime_type};base64,{base64_data}"
        
        return str(self.content)
    
    def _get_binary_data(self) -> Optional[bytes]:
        """コンテンツのバイナリデータを取得"""
        if isinstance(self.content, bytes):
            return self.content
        
        if isinstance(self.content, str):
            if os.path.exists(self.content):
                # ファイルパスの場合
                with open(self.content, 'rb') as f:
                    return f.read()
            elif self.content.startswith('data:'):
                # data URLの場合
                try:
                    header, data = self.content.split(',', 1)
                    return base64.b64decode(data)
                except:
                    logger.error(f"Failed to decode data URL: {self.content[:50]}...")
        
        if isinstance(self.content, Image.Image):
            # PILイメージの場合
            buffer = io.BytesIO()
            format = self.attributes.get('format', 'PNG')
            self.content.save(buffer, format=format)
            return buffer.getvalue()
        
        if self.media_type == MediaType.CHART and isinstance(self.content, (plt.Figure, plt.Axes)):
            # matplotlibのFigureまたはAxesの場合
            buffer = io.BytesIO()
            if isinstance(self.content, plt.Axes):
                fig = self.content.figure
            else:
                fig = self.content
            fig.savefig(buffer, format='png')
            plt.close(fig)  # メモリリーク防止
            return buffer.getvalue()
        
        return None
    
    def to_html(self) -> str:
        """HTML形式に変換"""
        if self.media_type == MediaType.TEXT:
            return markdown.markdown(self.content)
        
        elif self.media_type == MediaType.IMAGE:
            src = self._format_content()
            alt = self.attributes.get('alt', 'Image')
            return f'<img src="{src}" alt="{alt}" />'
        
        elif self.media_type == MediaType.AUDIO:
            src = self._format_content()
            return f'<audio controls><source src="{src}">お使いのブラウザはオーディオ要素をサポートしていません。</audio>'
        
        elif self.media_type == MediaType.VIDEO:
            src = self._format_content()
            return f'<video controls><source src="{src}">お使いのブラウザはビデオ要素をサポートしていません。</video>'
        
        elif self.media_type == MediaType.TABLE:
            if isinstance(self.content, pd.DataFrame):
                return self.content.to_html(index=False)
            return f'<pre>{html.escape(str(self.content))}</pre>'
        
        elif self.media_type == MediaType.CHART:
            src = self._format_content()
            return f'<img src="{src}" alt="Chart" />'
        
        elif self.media_type == MediaType.CODE:
            lang = self.attributes.get('language', '')
            code = html.escape(str(self.content))
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        
        elif self.media_type == MediaType.MATH:
            # 数式はMathJaxなどで表示される想定
            return f'<div class="math">${html.escape(str(self.content))}$</div>'
        
        elif self.media_type == MediaType.LINK:
            href = self.attributes.get('href', '#')
            return f'<a href="{href}">{html.escape(str(self.content))}</a>'
        
        return html.escape(str(self.content))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MMLElement':
        """辞書からMML要素を生成"""
        try:
            media_type = MediaType(data.get('type', 'text'))
        except ValueError:
            logger.warning(f"Unknown media type: {data.get('type')}, falling back to text")
            media_type = MediaType.TEXT
        
        content = data.get('content', '')
        attributes = data.get('attributes', {})
        
        return cls(media_type, content, attributes)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'type': self.media_type.value,
            'content': self.content,
            'attributes': self.attributes
        }

class MMLDocument:
    """MMLドキュメント"""
    
    def __init__(self, elements: List[MMLElement] = None):
        self.elements = elements or []
    
    def add_element(self, element: MMLElement) -> None:
        """要素を追加"""
        self.elements.append(element)
    
    def add_text(self, text: str, attributes: Dict[str, str] = None) -> None:
        """テキスト要素を追加"""
        self.add_element(MMLElement(MediaType.TEXT, text, attributes))
    
    def add_image(self, image_data: Union[str, bytes, Image.Image], 
                 attributes: Dict[str, str] = None) -> None:
        """画像要素を追加"""
        self.add_element(MMLElement(MediaType.IMAGE, image_data, attributes))
    
    def add_audio(self, audio_data: Union[str, bytes], 
                 attributes: Dict[str, str] = None) -> None:
        """音声要素を追加"""
        self.add_element(MMLElement(MediaType.AUDIO, audio_data, attributes))
    
    def add_video(self, video_data: Union[str, bytes], 
                 attributes: Dict[str, str] = None) -> None:
        """動画要素を追加"""
        self.add_element(MMLElement(MediaType.VIDEO, video_data, attributes))
    
    def add_table(self, table_data: Union[str, pd.DataFrame, List[List[Any]]], 
                 attributes: Dict[str, str] = None) -> None:
        """表要素を追加"""
        # リストの場合はDataFrameに変換
        if isinstance(table_data, list) and table_data and isinstance(table_data[0], list):
            # 最初の行をヘッダーとみなす
            headers = [f"Column{i+1}" for i in range(len(table_data[0]))]
            table_data = pd.DataFrame(table_data, columns=headers)
        
        self.add_element(MMLElement(MediaType.TABLE, table_data, attributes))
    
    def add_chart(self, chart_data: Union[plt.Figure, plt.Axes, Dict[str, Any]],
                 attributes: Dict[str, str] = None) -> None:
        """チャート要素を追加"""
        # 辞書の場合は簡易チャート生成
        if isinstance(chart_data, dict):
            fig, ax = plt.subplots()
            
            chart_type = chart_data.get('type', 'bar')
            data = chart_data.get('data', {})
            title = chart_data.get('title', '')
            
            if chart_type == 'bar':
                ax.bar(data.keys(), data.values())
            elif chart_type == 'line':
                ax.plot(list(data.keys()), list(data.values()))
            elif chart_type == 'pie':
                ax.pie(list(data.values()), labels=list(data.keys()), autopct='%1.1f%%')
            
            ax.set_title(title)
            plt.tight_layout()
            chart_data = fig
        
        self.add_element(MMLElement(MediaType.CHART, chart_data, attributes))
    
    def add_code(self, code: str, language: str = "", 
                attributes: Dict[str, str] = None) -> None:
        """コードブロック要素を追加"""
        attrs = attributes or {}
        if language:
            attrs['language'] = language
        self.add_element(MMLElement(MediaType.CODE, code, attrs))
    
    def add_math(self, math_expr: str, attributes: Dict[str, str] = None) -> None:
        """数式要素を追加"""
        self.add_element(MMLElement(MediaType.MATH, math_expr, attributes))
    
    def add_link(self, text: str, href: str, attributes: Dict[str, str] = None) -> None:
        """リンク要素を追加"""
        attrs = attributes or {}
        attrs['href'] = href
        self.add_element(MMLElement(MediaType.LINK, text, attrs))
    
    def to_mml(self) -> str:
        """MML形式の文字列に変換"""
        return '\n'.join([element.to_mml() for element in self.elements])
    
    def to_html(self) -> str:
        """HTML形式に変換"""
        html_elements = [element.to_html() for element in self.elements]
        return '\n'.join(html_elements)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'elements': [element.to_dict() for element in self.elements]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MMLDocument':
        """辞書からMMLドキュメントを生成"""
        elements = []
        for elem_data in data.get('elements', []):
            elements.append(MMLElement.from_dict(elem_data))
        return cls(elements)
    
    def save(self, file_path: str, format: str = 'mml') -> None:
        """ドキュメントをファイルに保存"""
        if format == 'mml':
            content = self.to_mml()
        elif format == 'html':
            content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MML Document</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        img {{ max-width: 100%; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; }}
        th {{ background-color: #f2f2f2; }}
        code {{ background-color: #f5f5f5; padding: 2px 4px; border-radius: 4px; }}
        pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
{self.to_html()}
</body>
</html>"""
        elif format == 'json':
            content = json.dumps(self.to_dict(), indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Saved MML document to {file_path}")

class MMLParser:
    """MMLパーサー"""
    
    @staticmethod
    def parse(text: str) -> MMLDocument:
        """MMLテキストをパースしてMMLドキュメントを生成"""
        document = MMLDocument()
        
        # タグパターン
        tag_pattern = r'<(\w+)(.*?)>(.*?)</\1>'
        
        # 属性パターン
        attr_pattern = r'(\w+)="([^"]*)"'
        
        # 現在位置
        pos = 0
        
        # タグマッチング
        for match in re.finditer(tag_pattern, text, re.DOTALL):
            # タグ前のテキスト
            if pos < match.start():
                text_before = text[pos:match.start()]
                if text_before.strip():
                    document.add_text(text_before)
            
            # タグの解析
            tag_name = match.group(1)
            try:
                media_type = MediaType(tag_name)
            except ValueError:
                logger.warning(f"Unknown tag: {tag_name}, treating as text")
                document.add_text(match.group(0))
                pos = match.end()
                continue
            
            # 属性の解析
            attrs_text = match.group(2)
            attributes = {}
            
            for attr_match in re.finditer(attr_pattern, attrs_text):
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(2)
                attributes[attr_name] = attr_value
            
            # コンテンツ
            content = match.group(3)
            
            # 特定タイプの処理
            if media_type == MediaType.TABLE:
                try:
                    # HTMLテーブルをDataFrameとしてパース
                    dfs = pd.read_html(f"<table>{content}</table>")
                    if dfs:
                        content = dfs[0]
                except:
                    pass
            
            # 要素の追加
            document.add_element(MMLElement(media_type, content, attributes))
            
            # 位置更新
            pos = match.end()
        
        # 最後のテキスト
        if pos < len(text):
            final_text = text[pos:]
            if final_text.strip():
                document.add_text(final_text)
        
        return document
    
    @staticmethod
    def parse_json(json_text: str) -> MMLDocument:
        """JSON形式のMMLをパース"""
        try:
            data = json.loads(json_text)
            return MMLDocument.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            raise

class MMLConverter:
    """MML形式変換ユーティリティ"""
    
    @staticmethod
    def mml_to_html(mml_text: str) -> str:
        """MMLテキストをHTMLに変換"""
        document = MMLParser.parse(mml_text)
        return document.to_html()
    
    @staticmethod
    def mml_to_json(mml_text: str) -> str:
        """MMLテキストをJSONに変換"""
        document = MMLParser.parse(mml_text)
        return json.dumps(document.to_dict())
    
    @staticmethod
    def json_to_mml(json_text: str) -> str:
        """JSON形式のMMLをMMLテキストに変換"""
        document = MMLParser.parse_json(json_text)
        return document.to_mml()
    
    @staticmethod
    def extract_media(mml_text: str, target_dir: str = '.', 
                     media_types: List[MediaType] = None) -> Dict[str, str]:
        """MMLからメディアファイルを抽出"""
        document = MMLParser.parse(mml_text)
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if media_types is None:
            media_types = [MediaType.IMAGE, MediaType.AUDIO, MediaType.VIDEO, MediaType.CHART]
        
        extracted_files = {}
        
        for i, element in enumerate(document.elements):
            if element.media_type in media_types:
                binary_data = element._get_binary_data()
                if binary_data:
                    # ファイル名の生成
                    extension = {
                        MediaType.IMAGE: 'png',
                        MediaType.AUDIO: 'mp3',
                        MediaType.VIDEO: 'mp4',
                        MediaType.CHART: 'png'
                    }.get(element.media_type, 'bin')
                    
                    filename = element.attributes.get('id', f"{element.media_type.value}_{i}.{extension}")
                    if not filename.endswith(f".{extension}"):
                        filename = f"{filename}.{extension}"
                    
                    file_path = target_dir / filename
                    
                    # ファイル保存
                    with open(file_path, 'wb') as f:
                        f.write(binary_data)
                    
                    extracted_files[element.id] = str(file_path)
        
        return extracted_files

# ユーティリティ関数
def create_mml_document_from_chat(messages: List[Dict[str, Any]]) -> MMLDocument:
    """チャットメッセージからMMLドキュメントを生成"""
    document = MMLDocument()
    
    for message in messages:
        role = message.get('role', 'user')
        content = message.get('content', '')
        
        # ロールの表示
        document.add_text(f"**{role.capitalize()}**:", {'role': role})
        
        # コンテンツの処理（文字列または構造化データ）
        if isinstance(content, str):
            document.add_text(content)
        elif isinstance(content, list):
            # マルチモーダルコンテンツ
            for item in content:
                item_type = item.get('type', 'text')
                item_content = item.get('text', item.get('content', ''))
                
                if item_type == 'text':
                    document.add_text(item_content)
                elif item_type == 'image_url':
                    url = item.get('image_url', {}).get('url', '')
                    if url:
                        document.add_image(url, {'alt': 'Image'})
                else:
                    document.add_text(f"Unsupported content type: {item_type}")
        
        # メッセージ間の区切り
        document.add_text("\n---\n")
    
    return document

def markdown_to_mml(markdown_text: str) -> str:
    """Markdownテキストを簡易的にMMLに変換"""
    # コードブロックの変換
    code_block_pattern = r'```(\w*)\n(.*?)```'
    
    def code_replacement(match):
        lang = match.group(1)
        code = match.group(2)
        return f'<code language="{lang}">{code}</code>'
    
    text = re.sub(code_block_pattern, code_replacement, markdown_text, flags=re.DOTALL)
    
    # 画像の変換
    img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    def img_replacement(match):
        alt = match.group(1)
        src = match.group(2)
        return f'<image alt="{alt}">{src}</image>'
    
    text = re.sub(img_pattern, img_replacement, text)
    
    # リンクの変換
    link_pattern = r'\[(.*?)\]\((.*?)\)'
    
    def link_replacement(match):
        text = match.group(1)
        href = match.group(2)
        return f'<link href="{href}">{text}</link>'
    
    text = re.sub(link_pattern, link_replacement, text)
    
    return text 