"""
FastAPIフレームワーク用ツールモジュール。
FastAPIアプリケーションのエンドポイント定義、設定、実行などを支援するツールを提供します。
"""

import os
import re
import json
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Union, Tuple
from contextlib import contextmanager
from pathlib import Path

from crewai.tools import BaseTool
from utils.logger import get_logger

logger = get_logger("fastapi_tools")

class FastAPIEndpointTool(BaseTool):
    """FastAPIエンドポイント定義サポートツール"""
    
    name: str = "FastAPIエンドポイント定義"
    description: str = "FastAPIアプリケーションのエンドポイント（API）を定義・生成します。"
    
    def _run(self, 
            path: str, 
            http_method: str = "GET",
            function_name: Optional[str] = None,
            path_params: Optional[List[Dict[str, str]]] = None,
            query_params: Optional[List[Dict[str, str]]] = None,
            request_body: Optional[Dict[str, Any]] = None,
            response_model: Optional[str] = None,
            function_body: Optional[str] = None,
            tags: Optional[List[str]] = None) -> str:
        """
        FastAPIエンドポイントの定義コードを生成
        
        Args:
            path: エンドポイントパス（例: "/users" や "/items/{item_id}"）
            http_method: HTTPメソッド（例: "GET", "POST", "PUT", "DELETE"）
            function_name: エンドポイント関数名（省略時は自動生成）
            path_params: パスパラメータのリスト[{"name": "item_id", "type": "int"}]
            query_params: クエリパラメータのリスト[{"name": "q", "type": "str", "required": False}]
            request_body: リクエストボディの定義{"model_name": "Item", "fields": [{"name": "name", "type": "str"}]}
            response_model: レスポンスモデル名（例: "Item", "List[Item]"）
            function_body: 関数の中身（省略時はシンプルなレスポンスを返す関数を生成）
            tags: APIドキュメント用のタグリスト
            
        Returns:
            str: 生成されたFastAPIエンドポイント定義コード
        """
        logger.info(f"FastAPIエンドポイント定義ツールが呼び出されました: {path}")
        
        # パスからデフォルトの関数名を生成
        if not function_name:
            # パスパラメータ部分（{param}）を除去して関数名を生成
            clean_path = re.sub(r'\{[^}]+\}', '', path).strip('/')
            method_prefix = http_method.lower()
            
            # /users/{user_id}/items -> get_users_items
            # /items -> get_items
            function_parts = [part for part in clean_path.split('/') if part]
            if not function_parts:
                function_name = f"{method_prefix}_root"
            else:
                function_name = f"{method_prefix}_{'_'.join(function_parts)}"
        
        # インポート文
        imports = ["from fastapi import FastAPI, HTTPException"]
        if query_params:
            imports.append("from fastapi import Query")
        if path_params or query_params or request_body:
            imports.append("from typing import Optional, List")
        
        # Pydanticモデルの生成
        models = []
        if request_body:
            models.append(self._generate_pydantic_model(request_body["model_name"], request_body["fields"]))
            if not "from pydantic import BaseModel" in imports:
                imports.append("from pydantic import BaseModel")
        
        # パスパラメータの型アノテーション
        path_param_types = {}
        if path_params:
            for param in path_params:
                path_param_types[param["name"]] = param["type"]
        
        # 関数シグネチャの生成
        func_params = []
        
        # パスパラメータを関数パラメータに追加
        if path_params:
            for param in path_params:
                param_name = param["name"]
                param_type = param["type"]
                func_params.append(f"{param_name}: {param_type}")
        
        # クエリパラメータを関数パラメータに追加
        if query_params:
            for param in query_params:
                param_name = param["name"]
                param_type = param["type"]
                required = param.get("required", True)
                default_value = param.get("default", "None")
                
                # デフォルト値がない場合（必須）
                if required:
                    func_params.append(f"{param_name}: {param_type} = Query(...)")
                else:
                    func_params.append(f"{param_name}: Optional[{param_type}] = Query({default_value})")
        
        # リクエストボディを関数パラメータに追加
        if request_body:
            model_name = request_body["model_name"]
            func_params.append(f"item: {model_name}")
        
        # 関数パラメータをカンマ区切りで結合
        func_param_str = ", ".join(func_params)
        
        # デコレータの生成
        decorator = f"@app.{http_method.lower()}(\"{path}\""
        if response_model:
            decorator += f", response_model={response_model}"
        if tags:
            tags_str = ", ".join([f'"{tag}"' for tag in tags])
            decorator += f", tags=[{tags_str}]"
        decorator += ")"
        
        # 関数の戻り値の型アノテーション
        return_type = response_model if response_model else "dict"
        
        # デフォルトの関数内容
        if not function_body:
            function_body = self._generate_default_function_body(http_method, path_params, request_body)
        
        # FastAPIエンドポイント定義コードを生成
        code_parts = imports + [""] + models + [""]
        
        code_parts.append(decorator)
        code_parts.append(f"async def {function_name}({func_param_str}) -> {return_type}:")
        
        # 関数本体をインデント
        indented_body = self._indent_code(function_body, 4)
        code_parts.append(indented_body)
        
        return "\n".join(code_parts)
    
    def _generate_pydantic_model(self, model_name: str, fields: List[Dict[str, str]]) -> str:
        """Pydanticモデルを生成"""
        model_lines = [f"class {model_name}(BaseModel):"]
        
        for field in fields:
            field_name = field["name"]
            field_type = field["type"]
            if field.get("optional", False):
                field_line = f"    {field_name}: Optional[{field_type}] = None"
            else:
                field_line = f"    {field_name}: {field_type}"
            model_lines.append(field_line)
        
        # 例がない場合は追加
        if not any(field.get("example") for field in fields):
            example_dict = {field["name"]: self._get_example_value(field["type"]) for field in fields}
            model_lines.append(f"    class Config:")
            model_lines.append(f"        schema_extra = {{")
            model_lines.append(f"            \"example\": {json.dumps(example_dict, ensure_ascii=False)}")
            model_lines.append(f"        }}")
        
        return "\n".join(model_lines)
    
    def _get_example_value(self, type_str: str) -> Any:
        """型に基づくサンプル値を取得"""
        if type_str == "str":
            return "サンプル文字列"
        elif type_str == "int":
            return 42
        elif type_str == "float":
            return 3.14
        elif type_str == "bool":
            return True
        elif type_str.startswith("List["):
            inner_type = type_str[5:-1]
            return [self._get_example_value(inner_type)]
        elif type_str.startswith("Dict["):
            return {"key": "value"}
        else:
            return None
    
    def _generate_default_function_body(self, 
                                      http_method: str, 
                                      path_params: Optional[List[Dict[str, str]]] = None,
                                      request_body: Optional[Dict[str, Any]] = None) -> str:
        """デフォルトの関数内容を生成"""
        method = http_method.upper()
        
        # GETメソッドの場合
        if method == "GET":
            if path_params:
                param_refs = ", ".join([f'"{p["name"]}": {p["name"]}' for p in path_params])
                return f"""# パスパラメータが指定された場合は、特定のアイテムを返す
return {{{param_refs}}}"""
            else:
                return """# サンプルのアイテムリストを返す
return [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]"""
        
        # POSTメソッドの場合
        elif method == "POST":
            if request_body:
                model_name = request_body["model_name"].lower()
                return f"""# リクエストボディからデータを作成・保存
new_id = 1  # 実際のアプリではデータベースで生成
return {{"id": new_id, **item.dict()}}"""
            else:
                return """# リクエストから新しいアイテムを作成
return {"id": 1, "message": "アイテムが作成されました"}"""
        
        # PUTメソッドの場合
        elif method == "PUT":
            if path_params and request_body:
                param_name = path_params[0]["name"]
                return f"""# 指定されたIDのアイテムを更新
# 実際のアプリではデータベースでの存在確認・更新が必要
if {param_name} != 1:
    raise HTTPException(status_code=404, detail="アイテムが見つかりません")
return {{"id": {param_name}, **item.dict()}}"""
            else:
                return """# アイテムの更新
return {"message": "アイテムが更新されました"}"""
        
        # DELETEメソッドの場合
        elif method == "DELETE":
            if path_params:
                param_name = path_params[0]["name"]
                return f"""# 指定されたIDのアイテムを削除
# 実際のアプリではデータベースでの存在確認・削除が必要
if {param_name} != 1:
    raise HTTPException(status_code=404, detail="アイテムが見つかりません")
return {{"message": f"アイテム {{{param_name}}} を削除しました"}}"""
            else:
                return """# 全アイテムの削除（危険な操作なので通常は避ける）
return {"message": "全アイテムが削除されました"}"""
        
        # その他のメソッド
        else:
            return """return {"message": "エンドポイントが呼び出されました"}"""
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """コードを指定された空白数でインデント"""
        prefix = " " * spaces
        return "\n".join(prefix + line for line in code.split("\n"))

class FastAPIAppGeneratorTool(BaseTool):
    """FastAPIアプリ生成ツール"""
    
    name: str = "FastAPIアプリ生成"
    description: str = "基本的なFastAPIアプリケーションのスケルトンコードを生成します。"
    
    def _run(self, 
            app_name: str = "fastapi_app",
            use_sqlalchemy: bool = False,
            include_authentication: bool = False) -> str:
        """
        FastAPIアプリケーションのスケルトンコードを生成
        
        Args:
            app_name: アプリケーション名
            use_sqlalchemy: SQLAlchemyを使用するか
            include_authentication: 認証機能を含めるか
            
        Returns:
            str: 生成されたFastAPIアプリケーションの構造とファイル内容
        """
        logger.info(f"FastAPIアプリ生成ツールが呼び出されました: {app_name}")
        
        # アプリケーションの基本構造を定義
        app_structure = [
            f"{app_name}/",
            f"{app_name}/main.py",
            f"{app_name}/requirements.txt",
            f"{app_name}/app/",
            f"{app_name}/app/__init__.py",
            f"{app_name}/app/api/",
            f"{app_name}/app/api/__init__.py",
            f"{app_name}/app/api/endpoints/",
            f"{app_name}/app/api/endpoints/__init__.py",
            f"{app_name}/app/api/endpoints/items.py",
            f"{app_name}/app/schemas/",
            f"{app_name}/app/schemas/__init__.py",
            f"{app_name}/app/schemas/item.py",
            f"{app_name}/app/core/",
            f"{app_name}/app/core/__init__.py",
            f"{app_name}/app/core/config.py",
        ]
        
        if use_sqlalchemy:
            app_structure.extend([
                f"{app_name}/app/db/",
                f"{app_name}/app/db/__init__.py",
                f"{app_name}/app/db/base.py",
                f"{app_name}/app/db/session.py",
                f"{app_name}/app/models/",
                f"{app_name}/app/models/__init__.py",
                f"{app_name}/app/models/item.py",
                f"{app_name}/app/crud/",
                f"{app_name}/app/crud/__init__.py",
                f"{app_name}/app/crud/crud_item.py",
            ])
        
        if include_authentication:
            app_structure.extend([
                f"{app_name}/app/api/endpoints/auth.py",
                f"{app_name}/app/core/security.py",
                f"{app_name}/app/schemas/user.py",
                f"{app_name}/app/schemas/token.py",
            ])
            
            if use_sqlalchemy:
                app_structure.extend([
                    f"{app_name}/app/models/user.py",
                    f"{app_name}/app/crud/crud_user.py",
                ])
        
        # ファイル内容を生成
        file_contents = {}
        
        # main.py
        file_contents[f"{app_name}/main.py"] = self._generate_main_py(use_sqlalchemy, include_authentication)
        
        # requirements.txt
        file_contents[f"{app_name}/requirements.txt"] = self._generate_requirements_txt(use_sqlalchemy, include_authentication)
        
        # config.py
        file_contents[f"{app_name}/app/core/config.py"] = self._generate_config_py(include_authentication)
        
        # items.py (endpoints)
        file_contents[f"{app_name}/app/api/endpoints/items.py"] = self._generate_items_endpoint(use_sqlalchemy)
        
        # item.py (schemas)
        file_contents[f"{app_name}/app/schemas/item.py"] = self._generate_item_schema()
        
        if use_sqlalchemy:
            # session.py
            file_contents[f"{app_name}/app/db/session.py"] = self._generate_db_session()
            
            # base.py
            file_contents[f"{app_name}/app/db/base.py"] = self._generate_db_base(include_authentication)
            
            # item.py (models)
            file_contents[f"{app_name}/app/models/item.py"] = self._generate_item_model()
            
            # crud_item.py
            file_contents[f"{app_name}/app/crud/crud_item.py"] = self._generate_crud_item()
        
        if include_authentication:
            # security.py
            file_contents[f"{app_name}/app/core/security.py"] = self._generate_security()
            
            # auth.py (endpoints)
            file_contents[f"{app_name}/app/api/endpoints/auth.py"] = self._generate_auth_endpoint(use_sqlalchemy)
            
            # user.py (schemas)
            file_contents[f"{app_name}/app/schemas/user.py"] = self._generate_user_schema()
            
            # token.py (schemas)
            file_contents[f"{app_name}/app/schemas/token.py"] = self._generate_token_schema()
            
            if use_sqlalchemy:
                # user.py (models)
                file_contents[f"{app_name}/app/models/user.py"] = self._generate_user_model()
                
                # crud_user.py
                file_contents[f"{app_name}/app/crud/crud_user.py"] = self._generate_crud_user()
        
        # 結果をフォーマット
        result = f"## FastAPIアプリケーション: {app_name}\n\n"
        result += "### ディレクトリ構造:\n```\n"
        result += "\n".join(app_structure)
        result += "\n```\n\n"
        
        result += "### 主要ファイル内容:\n\n"
        for file_path, content in file_contents.items():
            result += f"#### {file_path}\n```python\n{content}\n```\n\n"
        
        return result.strip()
    
    def _generate_main_py(self, use_sqlalchemy: bool, include_authentication: bool) -> str:
        """main.pyファイルを生成"""
        code = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import items"""
        
        if include_authentication:
            code += "\nfrom app.api.endpoints import auth"
        
        if use_sqlalchemy:
            code += "\nfrom app.db.session import engine"
            code += "\nfrom app.db.base import Base"
        
        code += "\n\nfrom app.core.config import settings\n\n"
        
        if use_sqlalchemy:
            code += """# データベーステーブルの作成
Base.metadata.create_all(bind=engine)

"""
        
        code += """# FastAPIアプリケーションの作成
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルーターの設定
app.include_router(items.router, prefix=settings.API_V1_STR)"""

        if include_authentication:
            code += """
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["auth"])"""
        
        code += """

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI application"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
"""
        return code
    
    def _generate_requirements_txt(self, use_sqlalchemy: bool, include_authentication: bool) -> str:
        """requirements.txtを生成"""
        requirements = [
            "fastapi==0.103.1",
            "uvicorn==0.23.2",
            "pydantic==2.3.0",
        ]
        
        if use_sqlalchemy:
            requirements.extend([
                "sqlalchemy==2.0.20",
                "alembic==1.12.0",
                "psycopg2-binary==2.9.7",  # PostgreSQL用ドライバ
            ])
        
        if include_authentication:
            requirements.extend([
                "python-jose==3.3.0",
                "passlib==1.7.4",
                "python-multipart==0.0.6",
                "bcrypt==4.0.1",
            ])
        
        return "\n".join(requirements)
    
    def _generate_config_py(self, include_authentication: bool) -> str:
        """config.pyを生成"""
        code = """from typing import List, Union
import secrets
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FastAPI Application"
    PROJECT_DESCRIPTION: str = "FastAPI Application with automatic API documentation"
    PROJECT_VERSION: str = "0.1.0"
    
    # CORSの設定
    CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # データベースURL
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"
    
"""
        
        if include_authentication:
            code += """    # JWT設定
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60分
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
"""
        
        code += """    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
"""
        return code
    
    def _generate_items_endpoint(self, use_sqlalchemy: bool) -> str:
        """items.pyエンドポイントを生成"""
        if use_sqlalchemy:
            return """from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import crud_item
from app.db.session import get_db
from app.schemas.item import Item, ItemCreate, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_model=List[Item])
def read_items(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    items = crud_item.get_items(db=db, skip=skip, limit=limit)
    return items

@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(
    item: ItemCreate, 
    db: Session = Depends(get_db)
):
    return crud_item.create_item(db=db, item=item)

@router.get("/{item_id}", response_model=Item)
def read_item(
    item_id: int, 
    db: Session = Depends(get_db)
):
    item = crud_item.get_item(db=db, item_id=item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    return item

@router.put("/{item_id}", response_model=Item)
def update_item(
    item_id: int, 
    item: ItemUpdate, 
    db: Session = Depends(get_db)
):
    db_item = crud_item.get_item(db=db, item_id=item_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    return crud_item.update_item(db=db, db_item=db_item, item=item)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int, 
    db: Session = Depends(get_db)
):
    db_item = crud_item.get_item(db=db, item_id=item_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    crud_item.delete_item(db=db, item_id=item_id)
    return None
"""
        else:
            return """from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status

from app.schemas.item import Item, ItemCreate, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])

# 仮想的なデータストア（実際のアプリケーションではデータベースを使用）
fake_items_db = {
    1: {"id": 1, "name": "Item 1", "description": "This is item 1", "price": 50.2},
    2: {"id": 2, "name": "Item 2", "description": "This is item 2", "price": 30.0},
}

@router.get("/", response_model=List[Item])
def read_items(skip: int = 0, limit: int = 100):
    return list(fake_items_db.values())[skip : skip + limit]

@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate):
    item_id = max(fake_items_db.keys(), default=0) + 1
    item_dict = item.dict()
    item_dict.update({"id": item_id})
    fake_items_db[item_id] = item_dict
    return item_dict

@router.get("/{item_id}", response_model=Item)
def read_item(item_id: int):
    if item_id not in fake_items_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    return fake_items_db[item_id]

@router.put("/{item_id}", response_model=Item)
def update_item(item_id: int, item: ItemUpdate):
    if item_id not in fake_items_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    
    item_dict = fake_items_db[item_id]
    update_data = item.dict(exclude_unset=True)
    updated_item = {**item_dict, **update_data}
    fake_items_db[item_id] = updated_item
    return updated_item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if item_id not in fake_items_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="アイテムが見つかりません"
        )
    
    del fake_items_db[item_id]
    return None
"""
    
    def _generate_item_schema(self) -> str:
        """item.pyスキーマを生成"""
        return """from typing import Optional
from pydantic import BaseModel

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float

class ItemCreate(ItemBase):
    pass

class ItemUpdate(ItemBase):
    name: Optional[str] = None
    price: Optional[float] = None

class Item(ItemBase):
    id: int

    class Config:
        orm_mode = True
        from_attributes = True
"""
    
    def _generate_db_session(self) -> str:
        """db/session.pyを生成"""
        return """from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# データベースエンジンの作成
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

# セッションを作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# モデルの基底クラス
Base = declarative_base()

# データベースセッションの依存関係
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""
    
    def _generate_db_base(self, include_authentication: bool) -> str:
        """db/base.pyを生成"""
        code = """# データベースモデルのインポート
from app.db.session import Base
from app.models.item import Item
"""
        if include_authentication:
            code += "from app.models.user import User\n"
        return code
    
    def _generate_item_model(self) -> str:
        """models/item.pyを生成"""
        return """from sqlalchemy import Column, Integer, String, Float
from app.db.session import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    price = Column(Float)
"""
    
    def _generate_crud_item(self) -> str:
        """crud/crud_item.pyを生成"""
        return """from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate

def get_item(db: Session, item_id: int) -> Optional[Item]:
    return db.query(Item).filter(Item.id == item_id).first()

def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[Item]:
    return db.query(Item).offset(skip).limit(limit).all()

def create_item(db: Session, item: ItemCreate) -> Item:
    db_item = Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, db_item: Item, item: ItemUpdate) -> Item:
    update_data = item.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: int) -> None:
    item = db.query(Item).filter(Item.id == item_id).first()
    db.delete(item)
    db.commit()
"""
    
    def _generate_security(self) -> str:
        """security.pyを生成"""
        return """from datetime import datetime, timedelta
from typing import Any, Union, Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
"""
    
    def _generate_auth_endpoint(self, use_sqlalchemy: bool) -> str:
        """auth.pyエンドポイントを生成"""
        if use_sqlalchemy:
            return """from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.token import Token
from app.crud import crud_user

router = APIRouter()

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 互換トークンログイン, トークンを取得
    """
    user = crud_user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
"""
        else:
            return """from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.schemas.token import Token

router = APIRouter()

# 仮想的なユーザーデータベース（実際のアプリケーションではデータベースを使用）
fake_users_db = {
    "user@example.com": {
        "id": 1,
        "email": "user@example.com",
        "hashed_password": "$2b$12$zXMTWudZ3xRQYNSvu1L7UOb6K4A7tqOb8o0UbPXOxokDaAU8KT5o.",  # "password"
        "is_active": True,
    }
}

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 互換トークンログイン, トークンを取得
    """
    user = fake_users_db.get(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )
    
    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user["id"], expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
"""
    
    def _generate_user_schema(self) -> str:
        """user.pyスキーマを生成"""
        return """from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    email: EmailStr
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: int

    class Config:
        orm_mode = True
        from_attributes = True
"""
    
    def _generate_token_schema(self) -> str:
        """token.pyスキーマを生成"""
        return """from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
"""
    
    def _generate_user_model(self) -> str:
        """models/user.pyを生成"""
        return """from sqlalchemy import Boolean, Column, Integer, String
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
"""
    
    def _generate_crud_user(self) -> str:
        """crud/crud_user.pyを生成"""
        return """from typing import Optional
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate) -> User:
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user: UserUpdate) -> User:
    update_data = user.dict(exclude_unset=True)
    
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
        
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate(db: Session, *, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
"""

class FastAPIRunnerTool(BaseTool):
    """FastAPI実行ツール"""
    
    name: str = "FastAPI実行"
    description: str = "FastAPIアプリケーションの実行を支援します。"
    
    def _run(self, 
            app_file_path: str,
            host: str = "127.0.0.1",
            port: int = 8000,
            reload: bool = True,
            workers: int = 1,
            wait_time: int = 5) -> str:
        """
        FastAPIアプリケーションを実行
        
        Args:
            app_file_path: FastAPIアプリケーションのエントリポイントファイルパス
            host: ホストアドレス
            port: ポート番号
            reload: ホットリロードを有効にするか
            workers: ワーカープロセス数
            wait_time: 開始後に待機する秒数（負の値の場合は待機しない）
            
        Returns:
            str: 実行結果またはエラーメッセージ
        """
        logger.info(f"FastAPI実行ツールが呼び出されました: {app_file_path}")
        
        # ファイルの存在確認
        if not os.path.exists(app_file_path):
            return f"エラー: ファイルが見つかりません: {app_file_path}"
        
        # モジュールパスとアプリオブジェクト名の取得
        file_path = Path(app_file_path)
        module_path = str(file_path.stem)  # 例: "main"
        
        # main.pyのような場合は"main:app"になる
        app_reference = f"{module_path}:app"
        
        # uvicornコマンドの実行
        try:
            # コマンドの構築
            command = [
                "uvicorn",
                app_reference,
                "--host", host,
                "--port", str(port),
                "--workers", str(workers)
            ]
            
            if reload:
                command.append("--reload")
            
            # 環境変数を設定
            env = os.environ.copy()
            
            # アプリケーションを起動（バックグラウンドで）
            process = subprocess.Popen(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(file_path.parent.absolute())  # 実行ディレクトリを設定
            )
            
            # 指定時間待機
            if wait_time > 0:
                try:
                    stdout, stderr = process.communicate(timeout=wait_time)
                    if process.returncode != 0:
                        return f"エラー: FastAPIアプリケーションの起動に失敗しました:\n{stderr}"
                except subprocess.TimeoutExpired:
                    # タイムアウトは正常（アプリが動作中）
                    return f"FastAPIアプリケーションが起動しました:\nURL: http://{host}:{port}/\nAPI Docs: http://{host}:{port}/docs\n\n(バックグラウンドで実行中。プロセスを停止するには Ctrl+C を使用してください)"
            
            return f"FastAPIアプリケーションの起動を開始しました:\nURL: http://{host}:{port}/\nAPI Docs: http://{host}:{port}/docs\n\n(バックグラウンドで実行中。プロセスを停止するには Ctrl+C を使用してください)"
        
        except Exception as e:
            return f"エラー: FastAPIアプリケーションの実行中に例外が発生しました: {str(e)}" 