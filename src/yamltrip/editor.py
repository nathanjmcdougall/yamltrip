"""Mutable YAML Editor context manager."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from yamltrip.document import Document

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType

    from yamltrip._core import Feature
    from yamltrip.document import KeyPart


class Editor:
    """A mutable context manager for editing YAML files.

    On successful exit, writes the modified document back to the file.
    On exception, the file is left unchanged.
    """

    def __init__(self, path: str | Path) -> None:
        """Create an editor for the given YAML file path."""
        self._path = Path(path)
        self._original: Document | None = None
        self._document: Document | None = None
        self._original_source: str | None = None

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"Editor('{self._path}')"

    def __enter__(self) -> Editor:
        """Read the file and enter the editing context."""
        if not self._path.exists():
            msg = f"File not found: {self._path}"
            raise FileNotFoundError(msg)
        source = self._path.read_text(encoding="utf-8")
        doc = Document(source)
        self._original_source = source
        self._original = doc
        self._document = Document(source)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Write changes on success, discard on exception."""
        if exc_type is None and self._document is not None:
            current_source = self._path.read_text(encoding="utf-8")
            if current_source != self._original_source:
                msg = f"File was modified externally: {self._path}"
                raise RuntimeError(msg)
            self._path.write_text(self._document.dumps(), encoding="utf-8")
        self._original = None
        self._document = None
        self._original_source = None

    @property
    def original(self) -> Document:
        """The document as it was when the editor was entered."""
        if self._original is None:
            msg = "Editor must be used as a context manager"
            raise RuntimeError(msg)
        return self._original

    @property
    def document(self) -> Document:
        """The current in-progress document."""
        if self._document is None:
            msg = "Editor must be used as a context manager"
            raise RuntimeError(msg)
        return self._document

    def __getitem__(self, keys: Any) -> Any:
        """Retrieve the parsed value at the given path."""
        return self.document[keys]

    def __contains__(self, keys: Any) -> bool:
        """Check whether a path exists in the document."""
        return keys in self.document

    def __setitem__(self, keys: Any, value: Any) -> None:
        """Upsert a value at the given path."""
        if isinstance(keys, (str, int)):
            keys = (keys,)
        elif not isinstance(keys, tuple):
            msg = f"Keys must be str, int, or tuple, got {type(keys).__name__}"
            raise TypeError(msg)
        self._document = self.document.upsert(*keys, value=value)

    def replace(self, *keys: KeyPart, value: Any) -> None:
        """Replace the value at an existing path."""
        self._document = self.document.replace(*keys, value=value)

    def add(self, *keys: KeyPart, key: str, value: Any) -> None:
        """Add a new key to the mapping at path."""
        self._document = self.document.add(*keys, key=key, value=value)

    def upsert(self, *keys: KeyPart, value: Any) -> None:
        """Replace if exists, create if not."""
        self._document = self.document.upsert(*keys, value=value)

    def remove(self, *keys: KeyPart, prune: bool = False) -> None:
        """Remove the key or index at path."""
        self._document = self.document.remove(*keys, prune=prune)

    def prune_remove(self, *keys: KeyPart) -> None:
        """Remove key and prune empty parents."""
        self._document = self.document.prune_remove(*keys)

    def append(self, *keys: KeyPart, value: Any) -> None:
        """Append an item to the sequence at path."""
        self._document = self.document.append(*keys, value=value)

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        """Append multiple items to the sequence at path."""
        self._document = self.document.extend_list(*keys, values=values)

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        """Remove all occurrences of given values from the sequence at path."""
        self._document = self.document.remove_from_list(*keys, values=values)

    def query(self, *keys: KeyPart) -> Feature:
        """Return the Feature at the given path."""
        return self.document.query(*keys)

    def extract(self, feature: Feature) -> str:
        """Extract the raw YAML text for a feature."""
        return self.document.extract(feature)
