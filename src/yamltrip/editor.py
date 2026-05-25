"""Mutable YAML Editor context manager."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from .document import Document, normalize_keys

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType

    from ._core import Feature
    from ._types import KeyPart


class Editor:
    """A mutable context manager for editing YAML files.

    On successful exit, writes the modified document back to the file.
    On exception, the file is left unchanged.
    """

    def __init__(self, path: str | Path) -> None:
        """Create an editor for the given YAML file path."""
        self._path: Path = Path(path)
        self._original: Document | None = None
        self._document: Document | None = None
        self._original_source: str | None = None

    @override
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
        self._document = doc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Write changes on success, discard on exception.

        The external-modification check is best-effort: it detects changes
        made between ``__enter__`` and ``__exit__`` but is not atomic and
        cannot guard against concurrent writes during the write itself.
        """
        del exc_val, exc_tb
        if exc_type is None and self._document is not None:
            current_source = self._path.read_text(encoding="utf-8")
            if current_source != self._original_source:
                msg = f"File was modified externally: {self._path}"
                raise RuntimeError(msg)
            _ = self._path.write_text(self._document.dumps(), encoding="utf-8")
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
    def root(self) -> Any:
        """The entire document parsed as a Python object."""
        return self.document.root

    def get(self, *keys: KeyPart, default: Any = None) -> Any:
        """Return the parsed value at path, or default if missing."""
        return self.document.get(*keys, default=default)

    def __getitem__(self, keys: object) -> Any:
        """Retrieve the parsed value at the given path."""
        return self.document[keys]

    def __contains__(self, keys: object) -> bool:
        """Check whether a path exists in the document."""
        return keys in self.document

    def __setitem__(self, keys: object, value: Any) -> None:
        """Upsert a value at the given path."""
        normalized = normalize_keys(keys)
        self._document = self.document.upsert(*normalized, value=value)

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

    def insert(self, *keys: KeyPart, index: int, value: Any) -> None:
        """Insert an item at a specific position in the sequence at path."""
        self._document = self.document.insert(*keys, index=index, value=value)

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        """Append multiple items to the sequence at path."""
        self._document = self.document.extend_list(*keys, values=values)

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> None:
        """Remove all occurrences of given values from the sequence at path."""
        self._document = self.document.remove_from_list(*keys, values=values)

    def ensure_in_list(
        self, *keys: KeyPart, value: Any, where: dict[str, Any] | None = None
    ) -> None:
        """Ensure a value is present in the sequence at path."""
        self._document = self.document.ensure_in_list(*keys, value=value, where=where)

    def sync(self, *keys: KeyPart, value: Any) -> None:
        """Sync the value at path to match the desired value."""
        self._document = self.document.sync(*keys, value=value)

    def merge(self, *keys: KeyPart, value: Any) -> None:
        """Merge or replace the value at path, depending on node type."""
        self._document = self.document.merge(*keys, value=value)

    def find_index(self, *keys: KeyPart, where: dict[str, Any]) -> int | None:
        """Return the index of the first list item matching all key/value pairs."""
        return self.document.find_index(*keys, where=where)

    def query(self, *keys: KeyPart) -> Feature:
        """Return the Feature at the given path."""
        return self.document.query(*keys)

    def extract(self, feature: Feature) -> str:
        """Extract the raw YAML text for a feature."""
        return self.document.extract(feature)

    @property
    def document(self) -> Document:
        """The current in-progress document."""
        if self._document is None:
            msg = "Editor must be used as a context manager"
            raise RuntimeError(msg)
        return self._document
