"""
認証・認可関連のAPIルーター。
ユーザー認証、トークン発行などの機能を提供します。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from api.auth import (
    Token, User, authenticate_user, create_access_token,
    fake_users_db, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user, has_role, Roles
)

# ルーターの作成
router = APIRouter(
    prefix="/auth",
    tags=["認証"],
    responses={401: {"description": "認証エラー"}},
)


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    ユーザー認証を行い、アクセストークンを発行します。
    """
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # トークンの有効期限を設定
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # トークンにユーザー情報とロールを含める
    token_data = {
        "sub": user.username,
        "roles": user.roles
    }
    
    # トークンを生成
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    現在のユーザー情報を取得します。
    """
    return current_user


@router.get("/users/me/roles")
async def read_own_roles(current_user: User = Depends(get_current_active_user)):
    """
    現在のユーザーのロールを取得します。
    """
    return {"roles": current_user.roles}


@router.get("/admin", dependencies=[Depends(has_role([Roles.ADMIN]))])
async def admin_only():
    """
    管理者専用のエンドポイント。
    """
    return {"message": "あなたは管理者権限を持っています"}


@router.get("/manager", dependencies=[Depends(has_role([Roles.MANAGER, Roles.PM]))])
async def manager_only():
    """
    マネージャー専用のエンドポイント。
    """
    return {"message": "あなたはマネージャー権限を持っています"} 