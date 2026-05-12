"""Immutable YAML Document class."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

from yamltrip import _core
from yamltrip.errors import ParseError, QueryError

if TYPE_CHECKING:
    from collections.abc import Sequence

KeyPart = Union[str, int]


def _normalize_keys(keys: Any) -> tuple[KeyPart, ...]:
    """Normalize __getitem__ input to a tuple of keys."""
    if isinstance(keys, (str, int)):
        return (keys,)
    if isinstance(keys, tuple):
        return keys
    raise TypeError(f"Keys must be str, int, or tuple, got {type(keys).__name__}")


def _make_route(keys: Sequence[KeyPart]) -> _core.Route:
    """Build a _core.Route from a sequence of keys."""
    return _core.Route(list(keys))


class Document:
    """An immutable YAML document.

    Each mutation method returns a new Document — the original is never modified.
    """

    def __init__(self, source: str) -> None:
        try:
            self._core_doc = _core.Document(source)
        except Exception as e:
            raise ParseError(str(e)) from None
        self._source = source

    @property
    def source(self) -> str:
        """The current YAML source text."""
        return self._source

    def __getitem__(self, keys: Any) -> Any:
        normalized = _normalize_keys(keys)
        route = _make_route(normalized)

        if not self._core_doc.query_exists(route):
            raise QueryError(f"Path not found: {normalized}")

        route = _make_route(normalized)
        return _core.parse_value(self._source, route)

    def __contains__(self, keys: Any) -> bool:
        try:
            normalized = _normalize_keys(keys)
        except TypeError:
            return False
        route = _make_route(normalized)
        return self._core_doc.query_exists(route)

    def query(self, *keys: KeyPart) -> _core.Feature:
        route = _make_route(keys)
        if not self._core_doc.query_exists(route):
            raise QueryError(f"Path not found: {keys}")
        route = _make_route(keys)
        feature = self._core_doc.query_exact(route)
        if feature is None:
            raise QueryError(f"Path has no value: {keys}")
        return feature

    def extract(self, feature: _core.Feature) -> str:
        return self._core_doc.extract(feature)

    def dumps(self) -> str:
        return self._source

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(self._source, encoding="utf-8")
