"""Local-volume file storage under ``JEWEL_UPLOAD_DIR``.

Files are written at opaque, server-generated names (32 hex characters, no extension);
clients never supply a path. Anything that does not match that shape is refused.
"""

import re
import uuid
from pathlib import Path

_STORED_NAME = re.compile(r"^[0-9a-f]{32}$")


class FileStore:
    def __init__(self, upload_dir: str | Path) -> None:
        self.root = Path(upload_dir)

    def _path(self, stored_path: str) -> Path:
        if not _STORED_NAME.fullmatch(stored_path):
            raise ValueError("invalid stored path")
        return self.root / stored_path

    def save(self, data: bytes) -> str:
        """Write bytes and return the opaque stored path."""
        self.root.mkdir(parents=True, exist_ok=True)
        stored_path = uuid.uuid4().hex
        self._path(stored_path).write_bytes(data)
        return stored_path

    def read(self, stored_path: str) -> bytes:
        return self._path(stored_path).read_bytes()

    def delete(self, stored_path: str) -> None:
        self._path(stored_path).unlink(missing_ok=True)
