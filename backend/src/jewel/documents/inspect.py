"""Byte checks that run before an upload is stored.

The extension decides which parser would run. These checks refuse a file whose bytes are
a different kind of file, or an Office package that declares a path outside itself or an
expansion big enough to exhaust memory when it is opened.
"""

import io
import zipfile
from pathlib import PurePosixPath

_OFFICE = {".docx", ".pptx", ".xlsx"}
_TEXT = {".txt", ".md", ".html", ".htm"}
# Declared uncompressed size, summed across members. The upload itself is already capped
# at 20 MB; this stops a small zip whose headers claim a huge expansion.
_MAX_OFFICE_MEMBERS = 512
_MAX_OFFICE_UNCOMPRESSED = 40 * 1024 * 1024


class UnsafeUpload(Exception):
    """The bytes are not a safe file of the claimed type. Nothing is stored."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def check_bytes(extension: str, data: bytes) -> None:
    """Raise ``UnsafeUpload`` when the bytes do not match ``extension``."""
    if extension == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise UnsafeUpload("This PDF does not start with a PDF header.")
        return
    if extension in _OFFICE:
        _check_office(data)
        return
    if extension in _TEXT:
        _check_text(data)


def _check_text(data: bytes) -> None:
    if b"\x00" in data:
        raise UnsafeUpload("Text and HTML files cannot contain null bytes.")
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsafeUpload("Text and HTML files must be UTF-8.") from exc


def _check_office(data: bytes) -> None:
    if not data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        raise UnsafeUpload("This Office file is not a valid package.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise UnsafeUpload("This Office file is not a valid package.") from exc
    if len(members) > _MAX_OFFICE_MEMBERS:
        raise UnsafeUpload("This Office file has too many parts.")
    total = 0
    for info in members:
        name = info.filename.replace("\\", "/")
        parts = PurePosixPath(name).parts
        if not name or name.startswith("/") or ".." in parts:
            raise UnsafeUpload("This Office file contains an unsafe path.")
        if info.file_size < 0 or info.file_size > _MAX_OFFICE_UNCOMPRESSED:
            raise UnsafeUpload("This Office file expands too far.")
        total += info.file_size
        if total > _MAX_OFFICE_UNCOMPRESSED:
            raise UnsafeUpload("This Office file expands too far.")
    names = {info.filename.replace("\\", "/") for info in members}
    if "[Content_Types].xml" not in names:
        raise UnsafeUpload("This Office file is not a valid package.")
