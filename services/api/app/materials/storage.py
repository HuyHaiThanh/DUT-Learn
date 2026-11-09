import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from app.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root if root is not None else get_settings().data_dir).resolve()

    def _path(self, key: str) -> Path:
        parts = PurePosixPath(key)
        if not key or parts.is_absolute() or "\\" in key or ":" in key:
            raise ValueError("Invalid storage key")
        if any(part in {".", ".."} for part in key.split("/")):
            raise ValueError("Invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Storage key escapes root")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = stream.name
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
