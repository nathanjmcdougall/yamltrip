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


def _apply(source: str, patches: list[_core.Patch]) -> str:
    """Apply patches, converting Rust errors to PatchError."""
    try:
        return _core.apply_patches(source, patches)
    except RuntimeError as e:
        raise PatchError(str(e)) from e


class Document:
    """An immutable YAML document.

    Each mutation method returns a new Document — the original is never modified.
    """

    def __init__(self, source: str) -> None:
        """Parse a YAML string into an immutable document."""
        try:
            self._core_doc = _core.Document(source)
        except (ValueError, RuntimeError) as e:
            raise ParseError(str(e)) from None
        self._source = source

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
        new_source = _apply(self._source, [patch])
        return Document(new_source)

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
        new_source = _apply(self._source, [patch])
        return Document(new_source)

    def upsert(self, *keys: KeyPart, value: Any) -> Document:
        """Replace if exists, create (with intermediate mappings) if not."""
        if not keys:
            route = _make_route(())
            op = _core.Op.replace(value)
            patch = _core.Patch(route=route, operation=op)
            new_source = _apply(self._source, [patch])
            return Document(new_source)

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
                nested_value = value
                for k in reversed(remaining_keys[1:]):
                    nested_value = {k: nested_value}
                merge_key = remaining_keys[0]
                route = _make_route(ancestor_keys)
                if isinstance(nested_value, dict):
                    op = _core.Op.merge_into(merge_key, nested_value)
                else:
                    op = _core.Op.add(merge_key, nested_value)
                patch = _core.Patch(route=route, operation=op)
                new_source = _apply(self._source, [patch])
                return Document(new_source)

        # No path exists — add at root
        _check_no_int_keys_for_creation(keys)
        nested_value = value
        for k in reversed(keys[1:]):
            nested_value = {k: nested_value}
        root_key = keys[0]
        route = _make_route(())
        op = _core.Op.add(root_key, nested_value)
        patch = _core.Patch(route=route, operation=op)
        new_source = _apply(self._source, [patch])
        return Document(new_source)

    def remove(self, *keys: KeyPart, prune: bool = False) -> Document:
        """Remove the key/index at path."""
        route = _make_route(keys)
        op = _core.Op.remove()
        patch = _core.Patch(route=route, operation=op)
        new_source = _apply(self._source, [patch])
        doc = Document(new_source)

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
        new_source = _apply(self._source, [patch])
        return Document(new_source)

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Append multiple items to the sequence at path."""
        if not values:
            return self
        route = _make_route(keys)
        patches = [
            _core.Patch(route=route, operation=_core.Op.append(v)) for v in values
        ]
        new_source = _apply(self._source, patches)
        return Document(new_source)

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Remove all occurrences of given values from the sequence at path."""
        current_list = self[keys]
        if not isinstance(current_list, list):
            msg = f"Value at {keys} is not a list"
            raise PatchError(msg)

        values_set: set[Any] = set()
        values_unhashable: list[Any] = []
        for v in values:
            try:
                values_set.add(v)
            except TypeError:
                values_unhashable.append(v)

        indices_to_remove = sorted(
            [
                i
                for i, item in enumerate(current_list)
                if item in values_set or item in values_unhashable
            ],
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
        new_source = _apply(self._source, patches)
        return Document(new_source)
