"""Immutable YAML Document class."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from yamltrip import _core
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    ParseError,
    PatchError,
    QueryError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

KeyPart = str | int


def _normalize_keys(keys: Any) -> tuple[KeyPart, ...]:
    """Normalize __getitem__ input to a tuple of keys."""
    if isinstance(keys, (str, int)):
        return (keys,)
    if isinstance(keys, tuple):
        return keys
    msg = f"Keys must be str, int, or tuple, got {type(keys).__name__}"
    raise TypeError(msg)


def _make_route(keys: Sequence[KeyPart]) -> _core.Route:
    """Build a _core.Route from a sequence of keys."""
    return _core.Route(list(keys))


def _check_no_int_keys_for_creation(keys: Sequence[KeyPart]) -> None:
    """Raise PatchError if any key is an int (cannot create sequences via upsert)."""
    for k in keys:
        if isinstance(k, int):
            msg = (
                f"Cannot create intermediate structure with integer key {k}; "
                "only string keys can create new mappings"
            )
            raise PatchError(msg)


class Document:
    """An immutable YAML document.

    Each mutation method returns a new Document — the original is never modified.

    Equality and hashing are based on the raw source text, not semantic content.
    Two documents with equivalent YAML but different formatting (e.g. extra
    whitespace) are considered unequal. This is intentional for a round-tripping
    library where formatting is significant.
    """

    def __init__(self, source: str) -> None:
        """Parse a YAML string into an immutable document."""
        try:
            self._core_doc = _core.Document(source)
        except (ValueError, RuntimeError) as e:
            raise ParseError(str(e)) from None
        self._source = source

    @classmethod
    def _from_core(cls, core_doc: _core.Document) -> Document:
        """Construct a Document from an already-parsed _core.Document."""
        obj = object.__new__(cls)
        obj._core_doc = core_doc
        obj._source = core_doc.source()
        return obj

    def _apply_patches(self, patches: list[_core.Patch]) -> Document:
        """Apply patches to this document and return a new Document."""
        try:
            core_doc = self._core_doc.apply_patches(patches)
        except RuntimeError as e:
            raise PatchError(str(e)) from None
        return Document._from_core(core_doc)

    @property
    def source(self) -> str:
        """The current YAML source text."""
        return self._source

    def __eq__(self, other: object) -> bool:
        """Compare documents by their source text."""
        if not isinstance(other, Document):
            return NotImplemented
        return self._source == other._source

    def __hash__(self) -> int:
        """Hash based on source text."""
        return hash(self._source)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"Document(<{len(self._source)} bytes>)"

    def __getitem__(self, keys: Any) -> Any:
        """Retrieve the parsed value at the given path."""
        normalized = _normalize_keys(keys)
        route = _make_route(normalized)
        try:
            return self._core_doc.parse_value(route)
        except (ValueError, KeyError) as e:
            raise QueryError(str(e)) from None

    def __contains__(self, keys: Any) -> bool:
        """Check whether a path exists in the document."""
        normalized = _normalize_keys(keys)
        route = _make_route(normalized)
        return self._core_doc.query_exists(route)

    def query(self, *keys: KeyPart) -> _core.Feature:
        """Return the Feature at the given path."""
        route = _make_route(keys)
        try:
            feature = self._core_doc.query_exact(route)
        except KeyError as e:
            raise QueryError(str(e)) from None
        if feature is None:
            msg = f"Path has no value: {keys}"
            raise QueryError(msg)
        return feature

    def query_pretty(self, *keys: KeyPart) -> _core.Feature:
        """Return a Feature with context (surrounding structure) at the path."""
        route = _make_route(keys)
        try:
            return self._core_doc.query_pretty(route)
        except KeyError as e:
            raise QueryError(str(e)) from None

    def has_anchors(self) -> bool:
        """Check whether the document contains YAML anchors (&anchor/*alias)."""
        return self._core_doc.has_anchors()

    def extract(self, feature: _core.Feature) -> str:
        """Extract the raw YAML text for a feature."""
        return self._core_doc.extract(feature)

    def dumps(self) -> str:
        """Return the YAML source text."""
        return self._source

    def dump(self, path: str | Path) -> None:
        """Write the YAML source text to a file."""
        Path(path).write_text(self._source, encoding="utf-8")

    def replace(self, *keys: KeyPart, value: Any) -> Document:
        """Replace value at an existing path. Raises KeyMissingError if missing."""
        route = _make_route(keys)
        if not self._core_doc.query_exists(route):
            msg = f"Path not found: {keys}"
            raise KeyMissingError(msg)

        op = _core.Op.replace(value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def add(self, *keys: KeyPart, key: str, value: Any) -> Document:
        """Add a new key to the mapping at path. Raises KeyExistsError if exists."""
        full_path = (*keys, key)
        check_route = _make_route(full_path)
        if self._core_doc.query_exists(check_route):
            msg = f"Key already exists: {full_path}"
            raise KeyExistsError(msg)

        route = _make_route(keys)
        op = _core.Op.add(key, value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def upsert(self, *keys: KeyPart, value: Any) -> Document:
        """Replace if exists, create (with intermediate mappings) if not."""
        if not keys:
            route = _make_route(())
            op = _core.Op.replace(value)
            patch = _core.Patch(route=route, operation=op)
            return self._apply_patches([patch])

        full_route = _make_route(keys)
        if self._core_doc.query_exists(full_route):
            return self.replace(*keys, value=value)

        # Find deepest existing ancestor
        for depth in range(len(keys) - 1, 0, -1):
            ancestor_keys = keys[:depth]
            ancestor_route = _make_route(ancestor_keys)
            if self._core_doc.query_exists(ancestor_route):
                remaining_keys = keys[depth:]
                _check_no_int_keys_for_creation(remaining_keys)
                merge_key = remaining_keys[0]
                if not isinstance(merge_key, str):
                    msg = f"Expected string key, got {type(merge_key).__name__}"
                    raise TypeError(msg)
                nested_value = value
                for k in reversed(remaining_keys[1:]):
                    nested_value = {k: nested_value}
                route = _make_route(ancestor_keys)
                if isinstance(nested_value, dict):
                    op = _core.Op.merge_into(merge_key, nested_value)
                else:
                    op = _core.Op.add(merge_key, nested_value)
                patch = _core.Patch(route=route, operation=op)
                return self._apply_patches([patch])

        # No path exists — add at root
        _check_no_int_keys_for_creation(keys)
        root_key = keys[0]
        if not isinstance(root_key, str):
            msg = f"Expected string key, got {type(root_key).__name__}"
            raise TypeError(msg)
        nested_value = value
        for k in reversed(keys[1:]):
            nested_value = {k: nested_value}
        route = _make_route(())
        op = _core.Op.add(root_key, nested_value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def remove(self, *keys: KeyPart, prune: bool = False) -> Document:
        """Remove the key/index at path."""
        route = _make_route(keys)
        op = _core.Op.remove()
        patch = _core.Patch(route=route, operation=op)
        doc = self._apply_patches([patch])

        if prune and len(keys) > 1:
            for depth in range(len(keys) - 1, 0, -1):
                parent_keys = keys[:depth]
                if parent_keys in doc:
                    parent_val = doc[parent_keys]
                    if parent_val is None or parent_val in ({}, []):
                        doc = doc.remove(*parent_keys)
                    else:
                        break
                else:
                    break
        return doc

    def prune_remove(self, *keys: KeyPart) -> Document:
        """Remove key and prune empty parents."""
        return self.remove(*keys, prune=True)

    def append(self, *keys: KeyPart, value: Any) -> Document:
        """Append a single item to the sequence at path."""
        route = _make_route(keys)
        op = _core.Op.append(value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Append multiple items to the sequence at path."""
        if not values:
            return self
        route = _make_route(keys)
        patches = [
            _core.Patch(route=route, operation=_core.Op.append(v)) for v in values
        ]
        return self._apply_patches(patches)

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Remove all occurrences of given values from the sequence at path."""
        current_list = self[keys]
        if not isinstance(current_list, list):
            msg = f"Value at {keys} is not a list"
            raise PatchError(msg)

        values_list = list(values)
        indices_to_remove = sorted(
            (i for i, item in enumerate(current_list) if item in values_list),
            reverse=True,
        )

        if not indices_to_remove:
            return self
        patches = [
            _core.Patch(
                route=_make_route((*keys, idx)),
                operation=_core.Op.remove(),
            )
            for idx in indices_to_remove
        ]
        return self._apply_patches(patches)
