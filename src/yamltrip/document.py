"""Immutable YAML Document class."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yamltrip import _core
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    ParseError,
    PatchError,
    QueryError,
)

KeyPart = str | int


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

    def replace(self, *keys: KeyPart, value: Any) -> Document:
        """Replace value at an existing path. Raises KeyMissingError if missing."""
        route = _make_route(keys)
        if not self._core_doc.query_exists(route):
            raise KeyMissingError(f"Path not found: {keys}")

        route = _make_route(keys)
        op = _core.Op.replace(value)
        patch = _core.Patch(route=route, operation=op)
        new_source = _core.apply_patches(self._source, [patch])
        return Document(new_source)

    def add(self, *keys: KeyPart, key: str, value: Any) -> Document:
        """Add a new key to the mapping at path. Raises KeyExistsError if exists."""
        full_path = (*keys, key)
        check_route = _make_route(full_path)
        if self._core_doc.query_exists(check_route):
            raise KeyExistsError(f"Key already exists: {full_path}")

        route = _make_route(keys)
        op = _core.Op.add(key, value)
        patch = _core.Patch(route=route, operation=op)
        new_source = _core.apply_patches(self._source, [patch])
        return Document(new_source)

    def upsert(self, *keys: KeyPart, value: Any) -> Document:
        """Replace if exists, create (with intermediate mappings) if not."""
        if not keys:
            route = _make_route(())
            op = _core.Op.replace(value)
            patch = _core.Patch(route=route, operation=op)
            new_source = _core.apply_patches(self._source, [patch])
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
                nested_value = value
                for k in reversed(remaining_keys[1:]):
                    nested_value = {k: nested_value}
                merge_key = str(remaining_keys[0])
                route = _make_route(ancestor_keys)
                if isinstance(nested_value, dict):
                    op = _core.Op.merge_into(merge_key, nested_value)
                else:
                    op = _core.Op.add(merge_key, nested_value)
                patch = _core.Patch(route=route, operation=op)
                new_source = _core.apply_patches(self._source, [patch])
                return Document(new_source)

        # No path exists — add at root
        nested_value = value
        for k in reversed(keys[1:]):
            nested_value = {str(k): nested_value}
        root_key = str(keys[0])
        route = _make_route(())
        op = _core.Op.add(root_key, nested_value)
        patch = _core.Patch(route=route, operation=op)
        new_source = _core.apply_patches(self._source, [patch])
        return Document(new_source)

    def remove(self, *keys: KeyPart, prune: bool = False) -> Document:
        """Remove the key/index at path."""
        route = _make_route(keys)
        op = _core.Op.remove()
        patch = _core.Patch(route=route, operation=op)
        new_source = _core.apply_patches(self._source, [patch])
        doc = Document(new_source)

        if prune and len(keys) > 1:
            for depth in range(len(keys) - 1, 0, -1):
                parent_keys = keys[:depth]
                if parent_keys in doc:
                    parent_val = doc[parent_keys]
                    if parent_val in (None, {}, []):
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
        new_source = _core.apply_patches(self._source, [patch])
        return Document(new_source)

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Append multiple items to the sequence at path."""
        doc = self
        for v in values:
            doc = doc.append(*keys, value=v)
        return doc

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Remove all occurrences of given values from the sequence at path."""
        current_list = self[keys]
        if not isinstance(current_list, list):
            raise PatchError(f"Value at {keys} is not a list")

        indices_to_remove = sorted(
            [i for i, item in enumerate(current_list) if item in values],
            reverse=True,
        )

        doc = self
        for idx in indices_to_remove:
            route = _make_route((*keys, idx))
            op = _core.Op.remove()
            patch = _core.Patch(route=route, operation=op)
            new_source = _core.apply_patches(doc._source, [patch])
            doc = Document(new_source)
        return doc
