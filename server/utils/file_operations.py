from fastapi import Request, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse
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
import urllib.parse


# Define RequestContext data class
class RequestContext:
    def __init__(self, request, username):
        self.request = request
        self.username = username

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

async def get_adapter(context: RequestContext) -> Adapter:
    key = context.request.query_params.get("adapter", "")
    user_adapters = get_user_adapters(context.username)
    if key not in user_adapters:
        key, value = next(iter(user_adapters.items()))
        return Adapter(key, value)
    return Adapter(key, user_adapters[key])

async def get_adapter_keys(context: RequestContext) -> List[str]:
    user_adapters = get_user_adapters(context.username)
    return list(user_adapters.keys())

async def get_full_path(context: RequestContext, adapter: Adapter) -> str:
    return context.request.query_params.get("path", adapter.key + "://")

def fs_path(path: str) -> str:
    if ":/" in path:
        return fspath.abspath(path.split(":/")[1])
    return fspath.abspath(path)

async def index(context: RequestContext, filter: str = None):
    adapter = await get_adapter(context)
    full_path = await get_full_path(context, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    infos = list(fs.scandir(path, namespaces=["basic", "details"]))

    if filter:
        infos = [info for info in infos if filter in info.name]

    infos.sort(key=lambda i: ("0_" if i.is_dir else "1_") + i.name.lower())

    return JSONResponse(
        {
            "adapter": adapter.key,
            "storages": await get_adapter_keys(context),
            "dirname": await get_full_path(context, adapter),
            "files": [
                to_vuefinder_resource(adapter.key, path, info) for info in infos
            ],
        }
    )

async def download(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
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

async def preview(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    info = fs.getinfo(path, ["basic", "details"])

    headers = {
        "Content-Disposition": f'inline; filename="{urllib.parse.quote(info.name)}"',
    }
    if info.size is not None:
        headers["Content-Length"] = str(info.size)

    return StreamingResponse(
        fs.open(path, "rb"),
        media_type=mimetypes.guess_type(info.name)[0] or "application/octet-stream",
        headers=headers,
    )

async def subfolders(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
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

async def search(context: RequestContext, filter: str = None):
    return await index(context, filter)

async def newfolder(context: RequestContext):
    adapter = await get_adapter(context)
    full_path = await get_full_path(context, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    
    data = await context.request.json()
    name = data.get("name", "")
    
    fs.makedir(fspath.join(path, name))
    return await index(context)

async def newfile(context: RequestContext):
    adapter = await get_adapter(context)
    full_path = await get_full_path(context, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    data = await context.request.json()
    name = data.get("name", "")

    fs.writetext(fspath.join(path, name), "")
    return await index(context)

async def rename(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    data = await context.request.json()
    src = fs_path(data.get("item", ""))
    dst = fspath.join(path, data.get("name", ""))
    
    try:
        if fs.isdir(src):
            fs.movedir(src, dst, create=True)
        else:
            fs.move(src, dst)
    except Exception as e   :
        return JSONResponse({"message": str(e), "status": False}, status_code=404)
    
    return await index(context)

async def move(context: RequestContext, items: List[Dict] = Body(...), item: str = Body(...)):
    adapter = await get_adapter(context)
    fs, _ = adapter.fs, fs_path(await get_full_path(context, adapter))
    dst_dir = item
    for item in items:
        src = item["path"]
        src_path = fs_path(src)
        dst_path = fspath.combine(dst_dir, fspath.basename(src))
        if fs.isdir(src_path):
            fs.movedir(src_path, dst_path, create=True)
        else:
            fs.move(src_path, dst_path)
    return await index(context)

async def delete(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    data = await context.request.json()
    for item in data.get("items", []):
        item_path = fs_path(item["path"])
        if fs.isdir(item_path):
            fs.removetree(item_path)
        else:
            fs.remove(item_path)
    return await index(context)

async def upload(context: RequestContext):
    adapter = await get_adapter(context)
    full_path = await get_full_path(context, adapter)
    fs, path = adapter.fs, fs_path(full_path)
    
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
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    data = await context.request.json()
    name = _get_filename(data, ext=".zip")
    items: list[dict] = data.get("items", [])
    paths = [fs_path(item["path"]) for item in items if "path" in item]
    archive_path = fspath.join(path, name)

    if fs.exists(archive_path):
        raise HTTPException(status_code=400, detail=f"Archive {archive_path} already exists")

    with fs.openbin(archive_path, mode="w") as f:
        with ZipFS(f, write=True) as zip:
            _write_zip(zip, fs, paths, path)

    return await index(context)

async def download_archive(context: RequestContext):
    name = _get_filename(await context.request.json(), ext=".zip")  
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    data = await context.request.json()
    paths = [fs_path(p) for p in data.get("items", []) if "path" in p]

    stream = io.BytesIO()

    with ZipFS(stream, write=True) as zip:
        _write_zip(zip, fs, paths, path)

    return StreamingResponse(
        stream.getvalue(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Type": "application/zip",
        },
    )

async def unarchive(context: RequestContext):
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
    data = await context.request.json()
    archive_path = fs_path(data.get("item", ""))

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
    adapter = await get_adapter(context)
    fs, path = adapter.fs, fs_path(await get_full_path(context, adapter))
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