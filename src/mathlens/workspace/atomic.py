"""Atomic file write utility — write to tmp, rename to target."""

from __future__ import annotations

from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write *content* to *path* atomically via a temporary file.

    If the process crashes mid-write, the original file is preserved.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    tmp.write_text(content, encoding=encoding)
    tmp.rename(path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write *content* bytes to *path* atomically."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    tmp.write_bytes(content)
    tmp.rename(path)
