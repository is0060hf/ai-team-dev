# MCP互換性対応

このドキュメントはModel Context Protocol (MCP)互換性対応の実装に関する情報を提供します。

## 概要

Model Context Protocol (MCP)は、AIモデルとツール・リソース間の標準的なインターフェイスを提供するプロトコルです。このプロジェクトでは、内部エージェント通信プロトコルとMCPとの互換性を確保することで、外部システムとの連携やツールの再利用性を高めます。

公式仕様: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

## 実装コンポーネント

### 1. MCP Bridge (`utils/mcp_bridge.py`)

内部エージェント通信プロトコルとMCPプロトコルの間の変換レイヤーを提供します。

- `MCPBridge` - 単一エージェントとMCPシステム間の橋渡しを行うクラス
- `MCPGateway` - 複数エージェントとMCPシステム間の中継を行うゲートウェイクラス

主な機能:
- 内部メッセージ → MCPメッセージの変換
- MCPメッセージ → 内部メッセージの変換
- MCPサーバーへの接続管理
- プロトコル互換ツールの登録

### 2. MCP Mapper (`utils/mcp_mapper.py`)

内部エージェント役割とMCPの標準ロール間のマッピングを提供します。

- `MCPRole` - MCPプロトコルで定義される標準的なエージェント役割
- `MCPMapper` - 役割マッピングと推論を行うクラス

主な機能:
- 内部エージェント役割 → MCPロールの変換
- タスク種別からの役割推論
- カスタム役割マッピングの管理

### 3. MCP Conversation (`utils/mcp_conversation.py`)

MCP準拠の会話状態とメッセージの管理機能を提供します。

- `MCPMessage` - MCP形式のメッセージを表すデータクラス
- `MCPConversation` - MCP準拠の会話を表すデータクラス
- `MCPConversationManager` - 複数の会話を管理するクラス

主な機能:
- 会話とメッセージの管理
- 会話履歴の保存と読み込み
- 内部/外部ロール形式の変換

### 4. MCP互換性テスト (`tests/test_mcp_compatibility.py`)

MCPプロトコルの各機能が正しく動作するかを検証するテストスイート。

- `MCPCompatibilityTest` - 基本的な互換性機能のテスト
- `MCPVersionCompatibilityTest` - バージョン互換性のテスト

## 利用方法

### エージェントからMCPシステムへのメッセージ送信

```python
from utils.mcp_bridge import MCPBridge
from utils.agent_communication import TaskRequest, TaskType, TaskPriority

# MCPブリッジの作成
bridge = MCPBridge("my_agent")

# MCPサーバーに接続
await bridge.connect_to_mcp_server(["path/to/mcp_server"])

# タスク依頼の作成
task_request = TaskRequest(
    sender="PdM",
    recipient="external_agent",
    task_type=TaskType.ARCHITECTURE_DESIGN,
    description="アーキテクチャを設計してください",
    priority=TaskPriority.HIGH
)

# MCPサーバーを通じてメッセージを送信
success = await bridge.send_message(task_request)
```

### 会話管理の利用

```python
from utils.mcp_conversation import get_conversation_manager

# 会話マネージャーを取得
manager = get_conversation_manager()

# 新しい会話を作成
conversation = manager.create_conversation({"topic": "アーキテクチャ設計"})

# 会話にメッセージを追加
manager.add_message_to_conversation(
    conversation.id,
    role="user",
    content="AI搭載Webアプリのアーキテクチャを設計してください"
)

# 会話履歴を取得
history = manager.get_conversation_history(conversation.id)

# 会話を保存
manager.save_conversation(conversation.id, "conversations/design_discussion.json")
```

## バージョン互換性

このMCP実装は標準仕様バージョン1.0に準拠しています。バージョン互換性については以下のルールに従います：

- メジャーバージョンが同じ場合は互換性あり
- マイナーバージョンの違いは上位互換性あり
- メジャーバージョンが異なる場合は基本的に互換性なし（フォールバック機構で対応）

互換性がない場合は、フォールバック機構を使用して複数のバージョンでの接続を試みます。

## 今後の拡張予定

1. **MCPブリッジの拡張** - より多くのメッセージタイプとツールをサポート
2. **分散システム対応** - 複数のゲートウェイ間の連携
3. **セキュリティ強化** - 認証・認可機能の実装
4. **パフォーマンス最適化** - 大量メッセージ処理時の最適化

## 関連ドキュメント

- [MCPプロトコル公式仕様](https://modelcontextprotocol.io/)
- [システムアーキテクチャ設計書](../document/仕様書.md)
- [テストガイド](../tests/README.md) 