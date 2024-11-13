from fastapi import Request, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.datastructures import UploadFile
from fs.osfs import OSFS
from fs import path as fspath, errors, copy, walk
from fs.zipfs import ZipFS
from fs.base import FS
import io
import mimetypes
from typing import List, Dict
from pathvalidate import is_valid_filename
from utils.auth import get_current_user
from utils.vuefinder import Adapter, to_vuefinder_resource
from pydantic import BaseModel
from urllib.parse import quote
from PIL import Image

# 全局字典存储用户适配器
user_adapters = {}

def get_user_adapters(username: str):
    if username not in user_adapters:
        user_adapters[username] =  {
            "document": OSFS(f"./cloud/{username}/document", create=True),
            "resource": OSFS(f"./cloud/{username}/resource", create=True),
            "release": OSFS(f"./cloud/{username}/release", create=True)
        }
    return user_adapters[username]


def _fs_path(path: str) -> str:
    if ":/" in path:
        return fspath.abspath(path.split(":/")[1])
    return fspath.abspath(path)

def __move(fs, src, dst):
    src = _fs_path(src)
    dst = _fs_path(dst)
    if fs.isdir(src):
        fs.movedir(src, dst, create=True)
    else:
        fs.move(src, dst)
# Define RequestContext data class
class RequestContext:
    def __init__(self, request, username):
        self.request = request
        self.username = username
    
    async def get_storages(self) -> List[str]:
        user_adapters = get_user_adapters(self.username)
        return list(user_adapters.keys())
    
    async def get_adapter(self) -> Adapter:
        key = self.request.query_params.get("adapter", "")
        user_adapters = get_user_adapters(self.username)
        if key not in user_adapters:
            key, value = next(iter(user_adapters.items()))
            return Adapter(key, value)
        return Adapter(key, user_adapters[key])

    async def get_full_path(self, adapter: Adapter) -> str:
        return self.request.query_params.get("path", adapter.key + "://")
    
    async def delegate(self) -> tuple[FS, str]:
        adapter = await self.get_adapter()
        full_path = await self.get_full_path(adapter)
        fs, path = adapter.fs, _fs_path(full_path)
        return fs, path 



async def index(context: RequestContext, filter: str = None):
    fs, path = await context.delegate()
    infos = list(fs.scandir(path, namespaces=["basic", "details"]))

    if filter:
        infos = [info for info in infos if filter in info.name]

    infos.sort(key=lambda i: ("0_" if i.is_dir else "1_") + i.name.lower())

    adapter = await context.get_adapter()
    return JSONResponse(
        {
            "adapter": adapter.key,
            "storages": await context.get_storages(),
            "dirname": await context.get_full_path(adapter),
            "files": [
                to_vuefinder_resource(adapter.key, path, info) for info in infos
            ],
        }
    )

async def download(context: RequestContext):
    fs, path = await context.delegate()
    info = fs.getinfo(path, ["basic", "details"])

    headers = {
        "Content-Disposition": f'attachment; filename="{quote(info.name)}"',
    }
    if info.size is not None:
        headers["Content-Length"] = str(info.size)

    return StreamingResponse(
        fs.open(path, "rb"),
        media_type="application/octet-stream",
        headers=headers,
    )

async def preview(context: RequestContext):
    fs, path = await context.delegate()
    info = fs.getinfo(path, ["basic", "details"])

    headers = {
        "Content-Disposition": f'inline; filename="{quote(info.name)}"',
    }

    # if info.size is not None:
    #     headers["Content-Length"] = str(info.size)

    # def iterfile():
    #     with fs.open(path, "rb") as file_like:
    #         yield from file_like

    # return StreamingResponse(
    #     iterfile(),
    #     media_type=mimetypes.guess_type(info.name)[0] or "application/octet-stream",
    #     headers=headers,
    # )

     # 打开图像并生成缩略图
    with fs.open(path, "rb") as file_like:
        image = Image.open(file_like)
        image.thumbnail((128, 128))  # 生成 128x128 的缩略图

        # 将图像保存到字节流中
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)

    # 使用字节流的大小设置 Content-Length
    headers["Content-Length"] = str(len(img_byte_arr.getvalue()))

    return StreamingResponse(
        img_byte_arr,
        media_type="image/png",
        headers=headers,
    )
    

async def subfolders(context: RequestContext):
    fs, path = await context.delegate()
    infos = fs.scandir(path, namespaces=["basic", "details"])
    adapter = await context.get_adapter()
    return JSONResponse(
        {
            "folders": [
                to_vuefinder_resource(adapter.key, path, info)
                for info in infos
                if info.is_dir
            ]
        }
    )

async def search(context: RequestContext):
    filter = context.request.query_params.get("filter", None)
    return await index(context, filter)

async def newfolder(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    name = data.get("name", "")
    
    fs.makedir(fspath.join(path, name))
    return await index(context)

async def newfile(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    name = data.get("name", "")

    fs.writetext(fspath.join(path, name), "")
    return await index(context)


async def rename(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    src = data.get("item", "")
    dst = fspath.join(path, data.get("name", ""))
    __move(fs, src, dst)
    return await index(context)

async def move(context: RequestContext):
    fs, _ = await context.delegate()
    data = await context.request.json()
    dst_dir = data.get("item", "")
    for item in data.get("items", []):
        src = item["path"]
        __move(fs, src, fspath.combine(dst_dir, fspath.basename(src)))
    return await index(context)

async def delete(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    for item in data.get("items", []):
        item_path = _fs_path(item["path"])
        if fs.isdir(item_path):
            fs.removetree(item_path)
        else:
            fs.remove(item_path)
    return await index(context)

async def upload(context: RequestContext):
    fs, path = await context.delegate()
    form = await context.request.form()
    
    for key, fsrc in form.items():
        if isinstance(fsrc, UploadFile):
            file_path = fspath.join(path, fsrc.filename)
            with fs.open(file_path, "wb") as fdst:
                content = await fsrc.read()
                fdst.write(content)

    return JSONResponse("ok")

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

async def archive(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    name = _get_filename(data, ext=".zip")
    items: list[dict] = data.get("items", [])
    paths = [_fs_path(item["path"]) for item in items if "path" in item]
    archive_path = fspath.join(path, name)

    if fs.exists(archive_path):
        raise HTTPException(status_code=400, detail=f"Archive {archive_path} already exists")

    with fs.openbin(archive_path, mode="w") as f:
        with ZipFS(f, write=True) as zip:
            _write_zip(zip, fs, paths, path)

    return await index(context)

async def download_archive(context: RequestContext):
    name = _get_filename(await context.request.json(), ext=".zip")  
    fs, path = await context.delegate()
    data = await context.request.json()
    paths = [_fs_path(p) for p in data.get("items", []) if "path" in p]

    stream = io.BytesIO()

    with ZipFS(stream, write=True) as zip:
        _write_zip(zip, fs, paths, path)

    return StreamingResponse(
        stream.getvalue(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{urllib.parse.quote(name)}"',
            "Content-Type": "application/zip",
        },
    )

async def unarchive(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    archive_path = _fs_path(data.get("item", ""))

    with fs.openbin(archive_path) as zip_file:
        with ZipFS(zip_file) as zip:
            walker = walk.Walker()
            for file_path in walker.files(zip):
                dst_path = fspath.join(path, fspath.relpath(file_path))
                if fs.exists(dst_path):
                    raise HTTPException(status_code=400, detail=f"File {dst_path} would be overridden by unarchive")

            copy.copy_dir(zip, "/", fs, path)

    return await index(context)

async def save(context: RequestContext):
    fs, path = await context.delegate()
    data = await context.request.json()
    content = data.get("content", "")
    with fs.open(path, "w") as f:
        f.write(content)
    return await preview(context)

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