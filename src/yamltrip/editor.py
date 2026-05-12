"""Mutable YAML Editor context manager."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yamltrip.document import Document, KeyPart, _normalize_keys

if __import__("typing").TYPE_CHECKING:
    from yamltrip._core import Feature


class Editor:
    """A mutable context manager for editing YAML files.

    On successful exit, writes the modified document back to the file.
    On exception, the file is left unchanged.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._original: Document | None = None
        self._document: Document | None = None

    def __enter__(self) -> Editor:
        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")
        source = self._path.read_text(encoding="utf-8")
        self._original = Document(source)
        self._document = Document(source)
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        if exc_type is None and self._document is not None:
            self._path.write_text(self._document.dumps(), encoding="utf-8")
        self._original = None
        self._document = None
        return None

    @property
    def original(self) -> Document:
        assert self._original is not None, "Editor not entered"
        return self._original

    @property
    def document(self) -> Document:
        assert self._document is not None, "Editor not entered"
        return self._document

    def __getitem__(self, keys: Any) -> Any:
        return self.document[keys]

    def __contains__(self, keys: Any) -> bool:
        return keys in self.document

    def __setitem__(self, keys: Any, value: Any) -> None:
        normalized = _normalize_keys(keys)
        self._document = self.document.upsert(*normalized, value=value)

    def replace(self, *keys: KeyPart, value: Any) -> None:
        self._document = self.document.replace(*keys, value=value)

    def add(self, *keys: KeyPart, key: str, value: Any) -> None:
        self._document = self.document.add(*keys, key=key, value=value)

    def upsert(self, *keys: KeyPart, value: Any) -> None:
        self._document = self.document.upsert(*keys, value=value)

    def remove(self, *keys: KeyPart, prune: bool = False) -> None:
        self._document = self.document.remove(*keys, prune=prune)

    def prune_remove(self, *keys: KeyPart) -> None:
        self._document = self.document.prune_remove(*keys)

    def append(self, *keys: KeyPart, value: Any) -> None:
        self._document = self.document.append(*keys, value=value)

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        self._document = self.document.extend_list(*keys, values=values)

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        self._document = self.document.remove_from_list(*keys, values=values)

    def query(self, *keys: KeyPart) -> Feature:
        return self.document.query(*keys)

    def extract(self, feature: Feature) -> str:
        return self.document.extract(feature)
