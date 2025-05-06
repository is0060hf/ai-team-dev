"""
専門エージェントAPIの認証・認可モジュール。
JWT認証とロールベースのアクセス制御を提供します。
"""

import os
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Union, Any

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# 設定
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_TO_A_REAL_SECRET_KEY_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# パスワードハッシュコンテキスト
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 設定
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ユーザーモデル
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    roles: List[str] = []


class UserInDB(User):
    hashed_password: str


# トークンモデル
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    roles: List[str] = []


# ロール定義
class Roles:
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    PM = "pm"
    PDM = "pdm"
    ENGINEER = "engineer"
    SPECIALIST = "specialist"


# サンプルユーザーデータベース（実際の実装では、データベースを使用すること）
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "管理者",
        "email": "admin@example.com",
        "hashed_password": pwd_context.hash("adminpass"),
        "disabled": False,
        "roles": [Roles.ADMIN]
    },
    "manager": {
        "username": "manager",
        "full_name": "マネージャー",
        "email": "manager@example.com",
        "hashed_password": pwd_context.hash("managerpass"),
        "disabled": False,
        "roles": [Roles.MANAGER, Roles.PM]
    },
    "user": {
        "username": "user",
        "full_name": "一般ユーザー",
        "email": "user@example.com",
        "hashed_password": pwd_context.hash("userpass"),
        "disabled": False,
        "roles": [Roles.USER, Roles.ENGINEER]
    }
}


# パスワード検証
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# パスワードハッシュ化
def get_password_hash(password):
    return pwd_context.hash(password)


# ユーザー取得
def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


# ユーザー認証
def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


# アクセストークン生成
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 現在のユーザーを取得
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, roles=payload.get("roles", []))
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


# アクティブなユーザーを取得
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="無効なユーザーです")
    return current_user


# ロールベースのアクセス制御
def has_role(required_roles: List[str]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        for role in required_roles:
            if role in current_user.roles:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このアクションを実行する権限がありません",
        )
    return role_checker


# レート制限機能
class RateLimiter:
    def __init__(self, rate_limit: int = 100, time_window: int = 60):
        """
        レート制限機能を初期化します。
        
        Args:
            rate_limit: 時間枠内の最大リクエスト数
            time_window: 時間枠（秒）
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.clients = {}  # IP -> {'count': n, 'reset_time': timestamp}
    
    async def check(self, request: Request):
        """
        リクエストがレート制限内かどうかをチェックします。
        
        Args:
            request: FastAPIリクエストオブジェクト
            
        Returns:
            bool: 制限内の場合はTrue、制限超過の場合はFalse
        """
        client_ip = request.client.host
        current_time = datetime.now(UTC).timestamp()
        
        # クライアント情報が存在しない場合は新規作成
        if client_ip not in self.clients:
            self.clients[client_ip] = {
                'count': 1,
                'reset_time': current_time + self.time_window
            }
            return True
        
        client = self.clients[client_ip]
        
        # 時間枠が過ぎていれば、カウンターをリセット
        if current_time > client['reset_time']:
            client['count'] = 1
            client['reset_time'] = current_time + self.time_window
            return True
        
        # 制限内かチェック
        if client['count'] < self.rate_limit:
            client['count'] += 1
            return True
        
        # 制限超過
        return False
    
    async def limiter_dependency(self, request: Request):
        """
        FastAPIの依存関係として使用するレート制限チェック。
        
        Args:
            request: FastAPIリクエストオブジェクト
        """
        if not await self.check(request):
            reset_time = self.clients[request.client.host]['reset_time']
            retry_after = int(reset_time - datetime.now(UTC).timestamp())
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="リクエスト回数の制限を超えました。しばらく経ってから再試行してください。",
                headers={"Retry-After": str(retry_after)}
            )


# デフォルトのレート制限インスタンスを作成
rate_limiter = RateLimiter() 