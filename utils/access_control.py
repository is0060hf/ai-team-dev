"""
アクセス制御モジュール。
ロールベースのアクセス制御（RBAC）と属性ベースのアクセス制御（ABAC）を提供します。
"""

import time
import json
import uuid
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Union, Callable
from functools import wraps
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from utils.logger import get_structured_logger
from utils.api_key_manager import validate_api_key

# ロガー設定
logger = get_structured_logger("access_control")

# OAuth2スキーム
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Permission(str, Enum):
    """アクセス制御の権限を定義する列挙型"""
    # システム管理関連
    ADMIN = "admin"                  # 管理者権限（全ての操作）
    SYSTEM_MONITOR = "system:monitor"  # システム監視
    SYSTEM_CONFIG = "system:config"    # システム設定
    
    # ユーザー管理関連
    USER_READ = "user:read"           # ユーザー情報読み取り
    USER_WRITE = "user:write"         # ユーザー情報書き込み
    USER_DELETE = "user:delete"       # ユーザー削除
    
    # APIキー管理関連
    API_KEY_READ = "apikey:read"      # APIキー情報読み取り
    API_KEY_WRITE = "apikey:write"    # APIキー作成・更新
    API_KEY_DELETE = "apikey:delete"  # APIキー削除
    
    # プロジェクト管理関連
    PROJECT_READ = "project:read"     # プロジェクト情報読み取り
    PROJECT_WRITE = "project:write"   # プロジェクト作成・更新
    PROJECT_DELETE = "project:delete" # プロジェクト削除
    
    # タスク管理関連
    TASK_READ = "task:read"           # タスク情報読み取り
    TASK_WRITE = "task:write"         # タスク作成・更新
    TASK_DELETE = "task:delete"       # タスク削除
    
    # エージェント管理関連
    AGENT_READ = "agent:read"         # エージェント情報読み取り
    AGENT_WRITE = "agent:write"       # エージェント設定
    AGENT_EXECUTE = "agent:execute"   # エージェント実行
    
    # Human-in-the-Loop関連
    HITL_READ = "hitl:read"           # HITL情報閲覧
    HITL_APPROVE = "hitl:approve"     # HITL承認
    HITL_REJECT = "hitl:reject"       # HITL拒否
    
    # モニタリング関連
    MONITORING_READ = "monitoring:read"  # モニタリング情報閲覧
    MONITORING_WRITE = "monitoring:write"  # モニタリング設定


class Role(str, Enum):
    """システムの役割を定義する列挙型"""
    ADMIN = "admin"             # 管理者
    SYSTEM_OPERATOR = "system_operator"  # システム運用者
    PROJECT_MANAGER = "project_manager"  # プロジェクトマネージャー
    DEVELOPER = "developer"     # 開発者
    PRODUCT_OWNER = "product_owner"  # プロダクトオーナー
    VIEWER = "viewer"           # 閲覧者
    API_CLIENT = "api_client"   # APIクライアント


# 役割ごとのデフォルト権限
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.ADMIN  # 管理者は全ての権限を持つ
    ],
    Role.SYSTEM_OPERATOR: [
        Permission.SYSTEM_MONITOR,
        Permission.SYSTEM_CONFIG,
        Permission.USER_READ,
        Permission.API_KEY_READ,
        Permission.API_KEY_WRITE,
        Permission.API_KEY_DELETE,
        Permission.MONITORING_READ,
        Permission.MONITORING_WRITE
    ],
    Role.PROJECT_MANAGER: [
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_DELETE,
        Permission.TASK_READ,
        Permission.TASK_WRITE,
        Permission.TASK_DELETE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.AGENT_EXECUTE,
        Permission.HITL_READ,
        Permission.HITL_APPROVE,
        Permission.HITL_REJECT,
        Permission.MONITORING_READ
    ],
    Role.DEVELOPER: [
        Permission.PROJECT_READ,
        Permission.TASK_READ,
        Permission.TASK_WRITE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.AGENT_EXECUTE,
        Permission.HITL_READ,
        Permission.MONITORING_READ
    ],
    Role.PRODUCT_OWNER: [
        Permission.PROJECT_READ,
        Permission.TASK_READ,
        Permission.HITL_READ,
        Permission.HITL_APPROVE,
        Permission.HITL_REJECT
    ],
    Role.VIEWER: [
        Permission.PROJECT_READ,
        Permission.TASK_READ,
        Permission.HITL_READ,
        Permission.MONITORING_READ
    ],
    Role.API_CLIENT: [
        # APIクライアントの権限は個別に設定
    ]
}


class AccessDeniedException(Exception):
    """アクセス拒否例外クラス"""
    
    def __init__(self, message: str = "アクセスが拒否されました", required_permission: Optional[str] = None):
        self.message = message
        self.required_permission = required_permission
        super().__init__(self.message)


class AccessControl:
    """アクセス制御を管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/access_control"):
        """
        Args:
            storage_path: アクセス制御データを保存するディレクトリのパス
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # ユーザーごとのロールマッピング
        self.user_roles: Dict[str, List[Role]] = {}
        
        # ユーザーごとの追加権限
        self.user_permissions: Dict[str, Set[Permission]] = {}
        
        # プロジェクトごとのユーザーロールマッピング
        self.project_roles: Dict[str, Dict[str, List[Role]]] = {}
        
        # カスタムポリシー
        self.custom_policies: Dict[str, Callable] = {}
        
        # データをロード
        self.load_data()
    
    def load_data(self):
        """保存されているアクセス制御データをロード"""
        try:
            # ユーザーロールデータ
            user_roles_path = self.storage_path / "user_roles.json"
            if user_roles_path.exists():
                with open(user_roles_path, "r") as f:
                    data = json.load(f)
                    self.user_roles = {
                        user_id: [Role(role) for role in roles]
                        for user_id, roles in data.items()
                    }
            
            # ユーザー権限データ
            user_permissions_path = self.storage_path / "user_permissions.json"
            if user_permissions_path.exists():
                with open(user_permissions_path, "r") as f:
                    data = json.load(f)
                    self.user_permissions = {
                        user_id: {Permission(perm) for perm in perms}
                        for user_id, perms in data.items()
                    }
            
            # プロジェクトロールデータ
            project_roles_path = self.storage_path / "project_roles.json"
            if project_roles_path.exists():
                with open(project_roles_path, "r") as f:
                    data = json.load(f)
                    self.project_roles = {
                        project_id: {
                            user_id: [Role(role) for role in roles]
                            for user_id, roles in user_roles.items()
                        }
                        for project_id, user_roles in data.items()
                    }
            
            logger.info("アクセス制御データを読み込みました")
        except Exception as e:
            logger.error(f"アクセス制御データの読み込みに失敗しました: {str(e)}")
    
    def save_data(self):
        """アクセス制御データを保存"""
        try:
            # ユーザーロールデータ
            user_roles_path = self.storage_path / "user_roles.json"
            with open(user_roles_path, "w") as f:
                json.dump(
                    {user_id: [role.value for role in roles] for user_id, roles in self.user_roles.items()},
                    f, indent=2
                )
            
            # ユーザー権限データ
            user_permissions_path = self.storage_path / "user_permissions.json"
            with open(user_permissions_path, "w") as f:
                json.dump(
                    {user_id: [perm.value for perm in perms] for user_id, perms in self.user_permissions.items()},
                    f, indent=2
                )
            
            # プロジェクトロールデータ
            project_roles_path = self.storage_path / "project_roles.json"
            with open(project_roles_path, "w") as f:
                json.dump(
                    {
                        project_id: {
                            user_id: [role.value for role in roles]
                            for user_id, roles in user_roles.items()
                        }
                        for project_id, user_roles in self.project_roles.items()
                    },
                    f, indent=2
                )
            
            logger.info("アクセス制御データを保存しました")
        except Exception as e:
            logger.error(f"アクセス制御データの保存に失敗しました: {str(e)}")
    
    def assign_role(self, user_id: str, role: Role):
        """
        ユーザーに役割を割り当てる
        
        Args:
            user_id: ユーザーID
            role: 割り当てる役割
        """
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        
        if role not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role)
            logger.info(f"ユーザー {user_id} に役割 {role.value} を割り当てました")
            self.save_data()
    
    def remove_role(self, user_id: str, role: Role) -> bool:
        """
        ユーザーから役割を削除する
        
        Args:
            user_id: ユーザーID
            role: 削除する役割
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        if user_id not in self.user_roles:
            return False
        
        if role not in self.user_roles[user_id]:
            return False
        
        self.user_roles[user_id].remove(role)
        logger.info(f"ユーザー {user_id} から役割 {role.value} を削除しました")
        self.save_data()
        return True
    
    def assign_project_role(self, project_id: str, user_id: str, role: Role):
        """
        プロジェクト内でユーザーに役割を割り当てる
        
        Args:
            project_id: プロジェクトID
            user_id: ユーザーID
            role: 割り当てる役割
        """
        if project_id not in self.project_roles:
            self.project_roles[project_id] = {}
        
        if user_id not in self.project_roles[project_id]:
            self.project_roles[project_id][user_id] = []
        
        if role not in self.project_roles[project_id][user_id]:
            self.project_roles[project_id][user_id].append(role)
            logger.info(f"プロジェクト {project_id} のユーザー {user_id} に役割 {role.value} を割り当てました")
            self.save_data()
    
    def remove_project_role(self, project_id: str, user_id: str, role: Role) -> bool:
        """
        プロジェクト内でユーザーから役割を削除する
        
        Args:
            project_id: プロジェクトID
            user_id: ユーザーID
            role: 削除する役割
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        if project_id not in self.project_roles:
            return False
        
        if user_id not in self.project_roles[project_id]:
            return False
        
        if role not in self.project_roles[project_id][user_id]:
            return False
        
        self.project_roles[project_id][user_id].remove(role)
        logger.info(f"プロジェクト {project_id} のユーザー {user_id} から役割 {role.value} を削除しました")
        self.save_data()
        return True
    
    def assign_permission(self, user_id: str, permission: Permission):
        """
        ユーザーに追加の権限を割り当てる
        
        Args:
            user_id: ユーザーID
            permission: 割り当てる権限
        """
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = set()
        
        if permission not in self.user_permissions[user_id]:
            self.user_permissions[user_id].add(permission)
            logger.info(f"ユーザー {user_id} に権限 {permission.value} を割り当てました")
            self.save_data()
    
    def remove_permission(self, user_id: str, permission: Permission) -> bool:
        """
        ユーザーから追加の権限を削除する
        
        Args:
            user_id: ユーザーID
            permission: 削除する権限
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        if user_id not in self.user_permissions:
            return False
        
        if permission not in self.user_permissions[user_id]:
            return False
        
        self.user_permissions[user_id].remove(permission)
        logger.info(f"ユーザー {user_id} から権限 {permission.value} を削除しました")
        self.save_data()
        return True
    
    def register_custom_policy(self, policy_name: str, policy_func: Callable):
        """
        カスタムポリシーを登録する
        
        Args:
            policy_name: ポリシー名
            policy_func: ポリシー関数（Trueを返すと許可、Falseで拒否）
        """
        self.custom_policies[policy_name] = policy_func
        logger.info(f"カスタムポリシー {policy_name} を登録しました")
    
    def unregister_custom_policy(self, policy_name: str) -> bool:
        """
        カスタムポリシーを削除する
        
        Args:
            policy_name: ポリシー名
            
        Returns:
            bool: 削除に成功した場合はTrue
        """
        if policy_name not in self.custom_policies:
            return False
        
        del self.custom_policies[policy_name]
        logger.info(f"カスタムポリシー {policy_name} を削除しました")
        return True
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        ユーザーの役割を取得する
        
        Args:
            user_id: ユーザーID
            
        Returns:
            List[Role]: ユーザーの役割リスト
        """
        return self.user_roles.get(user_id, [])
    
    def get_project_roles(self, project_id: str, user_id: str) -> List[Role]:
        """
        プロジェクト内でのユーザーの役割を取得する
        
        Args:
            project_id: プロジェクトID
            user_id: ユーザーID
            
        Returns:
            List[Role]: ユーザーの役割リスト
        """
        if project_id not in self.project_roles:
            return []
        
        return self.project_roles[project_id].get(user_id, [])
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        ユーザーの追加権限を取得する
        
        Args:
            user_id: ユーザーID
            
        Returns:
            Set[Permission]: ユーザーの追加権限セット
        """
        return self.user_permissions.get(user_id, set())
    
    def has_permission(
        self, 
        user_id: str, 
        required_permission: Permission,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        ユーザーが指定された権限を持っているかを確認する
        
        Args:
            user_id: ユーザーID
            required_permission: 要求される権限
            project_id: プロジェクトID（プロジェクト固有の権限チェック用）
            context: コンテキスト情報（属性ベースのアクセス制御用）
            
        Returns:
            bool: 権限がある場合はTrue
        """
        # ADMINは全ての権限を持つ
        if Role.ADMIN in self.get_user_roles(user_id):
            return True
        
        # 追加の権限をチェック
        if required_permission in self.get_user_permissions(user_id):
            return True
        
        # ロールベースの権限チェック
        user_roles = self.get_user_roles(user_id)
        for role in user_roles:
            permissions = DEFAULT_ROLE_PERMISSIONS.get(role, [])
            if Permission.ADMIN in permissions or required_permission in permissions:
                return True
        
        # プロジェクト固有のロールベース権限チェック
        if project_id:
            project_roles = self.get_project_roles(project_id, user_id)
            for role in project_roles:
                permissions = DEFAULT_ROLE_PERMISSIONS.get(role, [])
                if Permission.ADMIN in permissions or required_permission in permissions:
                    return True
        
        # カスタムポリシーのチェック
        if context is None:
            context = {}
        
        context["user_id"] = user_id
        context["required_permission"] = required_permission
        context["project_id"] = project_id
        
        for policy_name, policy_func in self.custom_policies.items():
            try:
                if policy_func(context):
                    logger.info(f"カスタムポリシー {policy_name} により権限が許可されました: {user_id} -> {required_permission.value}")
                    return True
            except Exception as e:
                logger.error(f"カスタムポリシー {policy_name} の実行中にエラーが発生しました: {str(e)}")
        
        return False
    
    def require_permission(
        self, 
        user_id: str, 
        required_permission: Permission,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        ユーザーが指定された権限を持っていることを要求し、持っていない場合は例外を発生させる
        
        Args:
            user_id: ユーザーID
            required_permission: 要求される権限
            project_id: プロジェクトID（プロジェクト固有の権限チェック用）
            context: コンテキスト情報（属性ベースのアクセス制御用）
            
        Raises:
            AccessDeniedException: 権限がない場合
        """
        if not self.has_permission(user_id, required_permission, project_id, context):
            message = f"アクセスが拒否されました: {user_id} には権限 {required_permission.value} がありません"
            if project_id:
                message += f" (プロジェクト: {project_id})"
            
            logger.warning(message)
            raise AccessDeniedException(message, required_permission.value)


# シングルトンインスタンス
access_control = AccessControl()


# FastAPI用の依存関係関数
async def verify_token(token: str = Depends(oauth2_scheme)):
    """
    JWTトークンを検証する依存関係関数
    
    Args:
        token: JWTトークン
        
    Returns:
        Dict: ユーザー情報
        
    Raises:
        HTTPException: トークンが無効な場合
    """
    from api.auth import verify_access_token
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ログインしてください",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # JWTトークンの検証
        payload = verify_access_token(token)
        if payload is None:
            raise credentials_exception
        
        return payload
    except Exception:
        raise credentials_exception


async def get_current_user(token_data: Dict = Depends(verify_token)):
    """
    現在のユーザーを取得する依存関係関数
    
    Args:
        token_data: トークンデータ
        
    Returns:
        Dict: ユーザー情報
    """
    return token_data


async def verify_api_key(request: Request) -> Dict[str, Any]:
    """
    APIキーを検証する依存関係関数
    
    Args:
        request: リクエストオブジェクト
        
    Returns:
        Dict: APIキー情報
        
    Raises:
        HTTPException: APIキーが無効な場合
    """
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="APIキーが必要です",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    valid, key_obj = validate_api_key(api_key)
    if not valid or not key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なAPIキーです",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return {
        "user_id": key_obj.owner,
        "permissions": key_obj.permissions,
        "api_key_id": key_obj.key_id,
        "metadata": key_obj.metadata
    }


def has_permission(permission: Permission, project_id: Optional[str] = None):
    """
    指定された権限を持っているかをチェックするデコレータ
    
    Args:
        permission: 要求される権限
        project_id: プロジェクトID（固定値の場合）
        
    Returns:
        Callable: デコレータ関数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # ユーザー情報の取得
            user = None
            request = None
            
            # FastAPI依存性注入からrequestパラメータを探す
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request is None and "request" in kwargs:
                request = kwargs["request"]
            
            # FastAPI依存性注入からcurrent_userパラメータを探す
            if "current_user" in kwargs:
                user = kwargs["current_user"]
            
            if not user and not request:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="認証情報がありません",
                )
            
            # リクエストからAPIキーを確認
            if not user and request:
                api_key = request.headers.get("x-api-key")
                if api_key:
                    valid, key_obj = validate_api_key(api_key)
                    if valid and key_obj:
                        # APIキーから権限チェック
                        if permission.value in key_obj.permissions or "*" in key_obj.permissions:
                            return await func(*args, **kwargs)
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"操作に必要な権限がありません: {permission.value}",
                            )
            
            # JWTからユーザーIDを取得
            user_id = user.get("sub") if user else None
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="ログインしてください",
                )
            
            # 動的プロジェクトIDの取得
            proj_id = project_id
            if not proj_id and "project_id" in kwargs:
                proj_id = kwargs["project_id"]
            
            # コンテキスト情報の構築
            context = {
                "request": request,
                "args": args,
                "kwargs": kwargs
            }
            
            # 権限チェック
            try:
                access_control.require_permission(user_id, permission, proj_id, context)
                return await func(*args, **kwargs)
            except AccessDeniedException as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"操作に必要な権限がありません: {e.required_permission}",
                )
        
        return wrapper
    
    return decorator


def initialize_default_roles():
    """デフォルトの役割と権限を初期化する"""
    # admin ユーザーにADMIN役割を割り当て
    access_control.assign_role("admin", Role.ADMIN)
    
    # system_operator ユーザーにSYSTEM_OPERATOR役割を割り当て
    access_control.assign_role("system_operator", Role.SYSTEM_OPERATOR)


# システム起動時にデフォルトの役割と権限を初期化
initialize_default_roles() 