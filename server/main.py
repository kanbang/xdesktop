from shutil import copyfileobj
from fastapi import FastAPI, HTTPException, status, Request, Body, Depends, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, StreamingResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pathvalidate import is_valid_filename
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
from fs.osfs import OSFS
from fs import path as fspath, errors, copy, walk
from fs.zipfs import ZipFS
from fs.base import FS

import io
import mimetypes
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile

from vuefinder import Adapter, to_vuefinder_resource

# 数据库设置
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 秘钥和算法
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 用户数据库模型
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# Pydantic 用户模型
class UserInDB(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    hashed_password: str

# 验证用户
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 获取当前用户
async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if token is None or not token.startswith("Bearer "):
        return "public_user"
    
    token = token.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return "public_user"
    except JWTError:
        return "public_user"
    
    return username

# FastAPI 应用
app = FastAPI()

# 登录并获取令牌
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(SessionLocal)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 示例受保护的路由
@app.get("/users/me")
async def read_users_me(request: Request):
    username = await get_current_user(request)
    return {"username": username}

# 全局字典存储用户适配器
user_adapters = {}

def get_user_adapters(username: str):
    if username not in user_adapters:
        user_adapters[username] =  {
            "document": OSFS(f"./cloud/{username}/document", create=True),
            "resource": OSFS(f"./cloud/{username}/resource", create=True),
            "release": OSFS(f"./cloud/{username}/release", create=True)
        }

          # 使用 OSFS 适配器
    return user_adapters[username]


# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

async def get_adapter(request: Request) -> Adapter:
    username = await get_current_user(request)
    # 获取用户特定的适配器
    key = request.query_params.get("adapter", "")
    user_adapters = get_user_adapters(username)
    if key not in user_adapters:
        key, value = next(iter(user_adapters.items()))
        return Adapter(key, value)
    
    return Adapter(key, user_adapters[key])

    
async def get_adapter_keys(request: Request) -> List[str]:
    username = await get_current_user(request)
    # 获取用户特定的适配器
    user_adapters = get_user_adapters(username)
    return list(user_adapters.keys())

async def get_full_path(request: Request, adapter: Adapter) -> str:
    return request.query_params.get("path", adapter.key + "://")

def fs_path(path: str) -> str:
    if ":/" in path:
        return fspath.abspath(path.split(":/")[1])
    return fspath.abspath(path)

async def index(request: Request, filter: str = None):
    adapter = await get_adapter(request)
    full_path = await get_full_path(request, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    infos = list(fs.scandir(path, namespaces=["basic", "details"]))

    if filter:
        infos = [info for info in infos if filter in info.name]

    infos.sort(key=lambda i: ("0_" if i.is_dir else "1_") + i.name.lower())

    return JSONResponse(
        {
            "adapter": adapter.key,
            "storages": await get_adapter_keys(request),
            "dirname": await get_full_path(request, adapter),
            "files": [
                to_vuefinder_resource(adapter.key, path, info) for info in infos
            ],
        }
    )

async def download(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    info = fs.getinfo(path, ["basic", "details"])

    headers = {
        "Content-Disposition": f'attachment; filename="{info.name}"',
    }
    if info.size is not None:
        headers["Content-Length"] = str(info.size)

    return StreamingResponse(
        fs.open(path, "rb"),
        media_type="application/octet-stream",
        headers=headers,
    )

async def preview(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    info = fs.getinfo(path, ["basic", "details"])

    headers = {
        "Content-Disposition": f'inline; filename="{info.name}"',
    }
    if info.size is not None:
        headers["Content-Length"] = str(info.size)

    return StreamingResponse(
        fs.open(path, "rb"),
        media_type=mimetypes.guess_type(info.name)[0] or "application/octet-stream",
        headers=headers,
    )

async def subfolders(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    infos = fs.scandir(path, namespaces=["basic", "details"])
    return JSONResponse(
        {
            "folders": [
                to_vuefinder_resource(adapter.key, path, info)
                for info in infos
                if info.is_dir
            ]
        }
    )

async def search(request: Request, filter: str = None):
    return await index(request, filter)

async def newfolder(request: Request):
    adapter = await get_adapter(request)
    full_path = await get_full_path(request, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    
    data = await request.json()
    name = data.get("name", "")
    
    fs.makedir(fspath.join(path, name))
    return await index(request)

async def newfile(request: Request):
    adapter = await get_adapter(request)
    full_path = await get_full_path(request, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    data = await request.json()
    name = data.get("name", "")

    fs.writetext(fspath.join(path, name), "")
    return await index(request)

async def rename(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    src = fs_path(data.get("item", ""))
    dst = fspath.join(path, data.get("name", ""))
    if fs.isdir(src):
        fs.movedir(src, dst, create=True)
    else:
        fs.move(src, dst)
    return await index(request)

async def move(request: Request, items: List[Dict] = Body(...), item: str = Body(...)):
    adapter = await get_adapter(request)
    fs, _ = adapter.fs, fs_path(await get_full_path(request, adapter))
    dst_dir = item
    for item in items:
        src = item["path"]
        src_path = fs_path(src)
        dst_path = fspath.combine(dst_dir, fspath.basename(src))
        if fs.isdir(src_path):
            fs.movedir(src_path, dst_path, create=True)
        else:
            fs.move(src_path, dst_path)
    return await index(request)

async def delete(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    for item in data.get("items", []):
        item_path = fs_path(item["path"])
        if fs.isdir(item_path):
            fs.removetree(item_path)
        else:
            fs.remove(item_path)
    return await index(request)

async def upload(request: Request):
    adapter = await get_adapter(request)
    full_path = await get_full_path(request, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    
    # 使用 await request.form() 获取表单数据
    form = await request.form()
    
    for key, fsrc in form.items():
        if isinstance(fsrc, UploadFile):
            file_path = fspath.join(path, fsrc.filename)
            with fs.open(file_path, "wb") as fdst:
                # 读取文件内容并写入目标文件
                content = await fsrc.read()
                fdst.write(content)

    return JSONResponse("ok")

# def _archive(self, request: Request) -> Response:
#         payload = request.get_json()
#         name = self._get_filename(payload, ext=".zip")

#         fs, path = self.delegate(request)
#         items: list[dict] = payload.get("items", [])
#         paths = [self._fs_path(item["path"]) for item in items if "path" in item]
#         archive_path = fspath.join(path, name)

#         if fs.exists(archive_path):
#             raise HTTPException(status_code=400, detail=f"Archive {archive_path} already exists")

#         with fs.openbin(archive_path, mode="w") as f:
#             with ZipFS(f, write=True) as zip:
#                 self._write_zip(zip, fs, paths, path)

#         return self._index(request)

def _write_zip(zip: FS, fs: FS, paths: list[str], base="/"):
    while len(paths) > 0:
        path = paths.pop()
        dst_path = fspath.relativefrom(base, path)
        if fs.isdir(path):
            zip.makedir(dst_path)
            paths = [fspath.join(path, name) for name in fs.listdir(path)] + paths
        else:
            with fs.openbin(path) as f:
                zip.writefile(dst_path, f)

def _get_filename(payload: dict, param: str = "name", ext: str = "") -> str:
    name = payload.get("name", None)
    if name is None or not is_valid_filename(name, platform="universal"):
        raise HTTPException(status_code=400, detail=f"Invalid archive name")

    if ext.startswith(".") and fspath.splitext(name)[1] != ext:
        name = name + ext

    return name

async def archive(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    name = _get_filename(data, ext=".zip")
    items: list[dict] = data.get("items", [])
    paths = [fs_path(item["path"]) for item in items if "path" in item]
    archive_path = fspath.join(path, name)

    if fs.exists(archive_path):
        raise HTTPException(status_code=400, detail=f"Archive {archive_path} already exists")

    with fs.openbin(archive_path, mode="w") as f:
        with ZipFS(f, write=True) as zip:
            _write_zip(zip, fs, paths, path)

    return await index(request)

async def download_archive(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    paths = [fs_path(p) for p in data.get("items", []) if "path" in p]

    stream = io.BytesIO()

    with ZipFS(stream, write=True) as zip:
        while len(paths) > 0:
            path = paths.pop()
            dst_path = fspath.relativefrom(path, path)
            if fs.isdir(path):
                zip.makedir(dst_path)
                paths = [fspath.join(path, name) for name in fs.listdir(path)] + paths
            else:
                with fs.openbin(path) as f:
                    zip.writefile(dst_path, f)

    return StreamingResponse(
        stream.getvalue(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Type": "application/zip",
        },
    )

async def unarchive(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    archive_path = fs_path(data.get("item", ""))

    with fs.openbin(archive_path) as zip_file:
        with ZipFS(zip_file) as zip:
            walker = walk.Walker()
            for file_path in walker.files(zip):
                dst_path = fspath.join(path, fspath.relpath(file_path))
                if fs.exists(dst_path):
                    raise HTTPException(status_code=400, detail=f"File {dst_path} would be overridden by unarchive")

            copy.copy_dir(zip, "/", fs, path)

    return await index(request)

async def save(request: Request):
    adapter = await get_adapter(request)
    fs, path = adapter.fs, fs_path(await get_full_path(request, adapter))
    data = await request.json()
    content = data.get("content", "")
    with fs.open(path, "w") as f:
        f.write(content)
    return await preview(request)

# Define a mapping of endpoint names to functions
endpoints = {
    "index": index,
    "preview": preview,
    "subfolders": subfolders,
    "download": download,
    "download_archive": download_archive,
    "search": search,
    "newfolder": newfolder,
    "newfile": newfile,
    "rename": rename,
    "move": move,
    "delete": delete,
    "upload": upload,
    "archive": archive,
    "unarchive": unarchive,
    "save": save,
}

@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def dispatch_request(request: Request):
    headers = {}
    if request.method == "OPTIONS":
        return JSONResponse(headers=headers)

    q = request.query_params.get("q")
    if not q or q not in endpoints:
        raise HTTPException(status_code=400, detail="Invalid endpoint")

    try:
        response = await endpoints[q](request)
    except errors.ResourceReadOnly as exc:
        return JSONResponse({"message": str(exc), "status": False}, status_code=400)
    except HTTPException as exc:
        return JSONResponse({"message": exc.detail, "status": False}, status_code=exc.status_code)

    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="debug")