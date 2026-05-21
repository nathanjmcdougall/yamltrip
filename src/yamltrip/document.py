"""Immutable YAML Document class."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yamltrip import _core
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    NodeTypeError,
    ParseError,
    PatchError,
    QueryError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from yamltrip._types import KeyPart


def _normalize_keys(keys: object) -> tuple[KeyPart, ...]:
    """Normalize __getitem__ input to a tuple of keys."""
    if isinstance(keys, (str, int)):
        return (keys,)
    if isinstance(keys, tuple):
        for k in keys:
            if not isinstance(k, (str, int)):
                msg = f"Key elements must be str or int, got {type(k).__name__}"
                raise TypeError(msg)
        return cast("tuple[KeyPart, ...]", tuple(keys))
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


def _flow_seq_replacements(
    core_doc: _core.Document,
    old_value: Any,
    new_value: Any,
    path: tuple[KeyPart, ...],
) -> list[_core.Patch]:
    """Find flow sequences that need modification and emit targeted replace patches."""
    patches: list[_core.Patch] = []

    if isinstance(old_value, list) and isinstance(new_value, list):
        if old_value != new_value:
            route = _make_route(path)
            try:
                feature = core_doc.query_exact(route)
                if feature and feature.kind == _core.FeatureKind.FlowSequence:
                    patches.append(
                        _core.Patch(route=route, operation=_core.Op.replace(new_value))
                    )
                    return patches
            except (KeyError, ValueError):
                pass
            # Recurse into shared list elements to find nested flow sequences
            for i in range(min(len(old_value), len(new_value))):
                sub_patches = _flow_seq_replacements(
                    core_doc, old_value[i], new_value[i], (*path, i)
                )
                patches.extend(sub_patches)
        return patches

    if isinstance(old_value, dict) and isinstance(new_value, dict):
        for key in new_value:
            if key in old_value:
                sub_patches = _flow_seq_replacements(
                    core_doc, old_value[key], new_value[key], (*path, key)
                )
                patches.extend(sub_patches)

    return patches


class Document:
    """An immutable YAML document.

    Each mutation method returns a new Document — the original is never modified.

    Equality and hashing are based on the raw source text, not semantic content.
    Two documents with equivalent YAML but different formatting (e.g. extra
    whitespace) are considered unequal. This is intentional for a round-tripping
    library where formatting is significant.

    Each instance holds a native tree-sitter parse tree plus a copy of the
    source text.  Memory is freed when the Python object is garbage-collected.
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

    @property
    def root(self) -> Any:
        """The entire document parsed as a Python object."""
        return self[()]

    def get(self, *keys: KeyPart, default: Any = None) -> Any:
        """Return the parsed value at path, or default if the path doesn't exist."""
        normalized = _normalize_keys(keys)
        route = _make_route(normalized)
        try:
            return self._core_doc.parse_value(route)
        except KeyError:
            return default
        except ValueError as e:
            raise QueryError(str(e)) from None

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

    def __getitem__(self, keys: object) -> Any:
        """Retrieve the parsed value at the given path.

        An empty tuple ``()`` retrieves the entire document as a Python object.
        """
        normalized = _normalize_keys(keys)
        route = _make_route(normalized)
        try:
            return self._core_doc.parse_value(route)
        except (ValueError, KeyError) as e:
            raise QueryError(str(e)) from None

    def __contains__(self, keys: object) -> bool:
        """Check whether a path exists in the document.

        An empty tuple ``()`` checks that the document has a root data node.
        Returns False for empty or comment-only documents.
        """
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

        if self._is_empty_document():
            return self._create_at((), full_path, value)

        route = _make_route(keys)
        op = _core.Op.add(key, value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def _is_empty_document(self) -> bool:
        """True if the document has no root data node."""
        return not self._core_doc.query_exists(_make_route(()))

    def _create_at(
        self,
        parent_keys: tuple[KeyPart, ...],
        child_keys: tuple[KeyPart, ...],
        value: Any,
    ) -> Document:
        """Create a nested value under parent_keys using child_keys."""
        _check_no_int_keys_for_creation(child_keys)

        # Bootstrap root mapping if document has no root data node
        if not parent_keys and self._is_empty_document():
            first_key = child_keys[0]
            if not isinstance(first_key, str):
                msg = f"Expected string key, got {type(first_key).__name__}"
                raise TypeError(msg)
            nested_value = value
            for k in reversed(child_keys[1:]):
                nested_value = {k: nested_value}
            full_dict = {first_key: nested_value}
            yaml_text = _core.serialize_value(full_dict)
            prefix = self._source
            if prefix and not prefix.endswith("\n"):
                prefix += "\n"
            return Document(prefix + yaml_text)

        first_key = child_keys[0]
        if not isinstance(first_key, str):
            msg = f"Expected string key, got {type(first_key).__name__}"
            raise TypeError(msg)
        nested_value = value
        for k in reversed(child_keys[1:]):
            nested_value = {k: nested_value}
        route = _make_route(parent_keys)
        if isinstance(nested_value, dict):
            op = _core.Op.merge_into(first_key, nested_value)
        else:
            op = _core.Op.add(first_key, nested_value)
        patch = _core.Patch(route=route, operation=op)
        return self._apply_patches([patch])

    def upsert(self, *keys: KeyPart, value: Any) -> Document:
        """Replace if exists, create (with intermediate mappings) if not."""
        if not keys:
            if self._is_empty_document():
                msg = (
                    "Cannot replace root of an empty document; provide at least one key"
                )
                raise PatchError(msg)
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
                return self._create_at(ancestor_keys, keys[depth:], value)

        # No path exists — add at root
        return self._create_at((), keys, value)

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
        try:
            return self._apply_patches([patch])
        except PatchError as e:
            msg = str(e)
            # yamlpatch raises "...flow sequence..." for append on FlowSequence nodes
            if "flow sequence" in msg:
                current = self[keys]
                new_list = [*list(current), value]
                replace_op = _core.Op.replace(new_list)
                return self._apply_patches(
                    [_core.Patch(route=route, operation=replace_op)]
                )
            if "only permitted against sequence" in msg:
                raise NodeTypeError(msg) from None
            raise

    def insert(self, *keys: KeyPart, index: int, value: Any) -> Document:
        """Insert an item at a specific position in the sequence at path.

        Uses Python list.insert() semantics for index resolution:
        negative indices count from the end, out-of-range indices clamp.
        """
        route = _make_route(keys)
        op = _core.Op.insert_at(index=index, value=value)
        patch = _core.Patch(route=route, operation=op)
        try:
            return self._apply_patches([patch])
        except PatchError as e:
            msg = str(e)
            # Rust apply_insert_at raises "expected BlockSequence, got ..." for
            # both FlowSequence and non-sequence nodes (Scalar, BlockMapping, etc.)
            if "expected BlockSequence" not in msg:
                raise
            current = self[keys]
            if not isinstance(current, list):
                raise NodeTypeError(msg) from None
            new_list = list(current)
            new_list.insert(index, value)
            replace_op = _core.Op.replace(new_list)
            return self._apply_patches([_core.Patch(route=route, operation=replace_op)])

    def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Append multiple items to the sequence at path."""
        if not values:
            return self
        route = _make_route(keys)
        patches = [
            _core.Patch(route=route, operation=_core.Op.append(v)) for v in values
        ]
        try:
            return self._apply_patches(patches)
        except PatchError as e:
            msg = str(e)
            # yamlpatch raises "...flow sequence..." for append on FlowSequence nodes
            if "flow sequence" in msg:
                current = self[keys]
                new_list = [*list(current), *values]
                replace_op = _core.Op.replace(new_list)
                return self._apply_patches(
                    [_core.Patch(route=route, operation=replace_op)]
                )
            if "only permitted against sequence" in msg:
                raise NodeTypeError(msg) from None
            raise

    def remove_from_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
        """Remove all occurrences of given values from the sequence at path."""
        current_list = self[keys]
        if not isinstance(current_list, list):
            msg = f"Value at {keys} is not a list"
            raise NodeTypeError(msg)

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

    def sync(self, *keys: KeyPart, value: Any) -> Document:
        """Sync the value at path to match the desired value.

        Diffs the current value against the desired value and applies
        the minimal set of patches. Returns self if no changes needed.
        """
        from yamltrip.sync import _compute_patches  # noqa: PLC0415

        normalized = _normalize_keys(keys) if keys else ()

        # If path doesn't exist, delegate to upsert.
        # Root (empty keys) always exists, so skip the check.
        if normalized:
            route = _make_route(normalized)
            if not self._core_doc.query_exists(route):
                return self.upsert(*normalized, value=value)

        # Get current value and diff
        try:
            old_value = self._core_doc.parse_value(_make_route(normalized))
        except (ValueError, KeyError):
            return self.upsert(*normalized, value=value)

        # Pre-convert any flow sequences that will be modified.
        # This targets only the affected leaf paths, preserving sibling formatting.
        doc: Document = self
        flow_patches = _flow_seq_replacements(
            self._core_doc, old_value, value, normalized
        )
        if flow_patches:
            doc = doc._apply_patches(flow_patches)
            # Re-read old_value from the now-converted document
            old_value = doc._core_doc.parse_value(_make_route(normalized))

        patches = _compute_patches(old_value, value, normalized)
        if not patches:
            return doc
        try:
            return doc._apply_patches(patches)
        except PatchError as e:
            if "expected BlockSequence" not in str(e):
                raise
            # Fallback: a flow sequence was missed by pre-detection (e.g. due to
            # list reordering). Replace the entire synced value.
            route = _make_route(normalized)
            op = _core.Op.replace(value)
            return self._apply_patches([_core.Patch(route=route, operation=op)])

    def find_index(self, *keys: KeyPart, where: dict[str, Any]) -> int | None:
        """Return the index of the first list item matching all key/value pairs.

        Comparison uses Python ``==``. YAML scalars are parsed to their
        native types (e.g. ``port: 8080`` is int, not str).

        Args:
            *keys: Path to the list within the document.
            where: Dict of key/value pairs that must all match (AND semantics).

        Returns:
            The integer index of the first matching item, or None if no match.

        Raises:
            QueryError: If the path doesn't exist.
            NodeTypeError: If the value at path is not a list.
            ValueError: If where is empty.
        """
        if not where:
            msg = "where must be a non-empty dict"
            raise ValueError(msg)

        value = self[keys]
        if not isinstance(value, list):
            msg = f"Value at {keys} is not a list"
            raise NodeTypeError(msg)

        for i, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            entry = cast("dict[str, Any]", item)
            if all(entry.get(k) == v for k, v in where.items()):
                return i
        return None
