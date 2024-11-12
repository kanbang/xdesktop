from fs.base import FS
from fs.info import Info
import mimetypes


def to_vuefinder_resource(storage: str, path: str, info: Info) -> dict:
    if path == "/":
        path = ""
    return {
        "type": "dir" if info.is_dir else "file",
        "path": f"{storage}:/{path}/{info.name}",
        "visibility": "public",
        "last_modified": info.modified.timestamp(),
        "mime_type": mimetypes.guess_type(info.name)[0],
        "extra_metadata": [],
        "basename": info.name,
        "extension": info.name.split(".")[-1],
        "storage": storage,
        "file_size": info.size,
    }


class Adapter(object):
    def __init__(self, key: str, fs: FS):
        self.key = key
        self.fs = fs

