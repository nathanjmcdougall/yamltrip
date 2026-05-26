# Design: `RoutingError` Typed Exception

**Date:** 2026-05-26  
**Status:** Approved  
**Related todo:** `doc/todo/error-routing-typed-exception.md`

---

## Problem

When `upsert`, `add`, or `merge` tries to write through a key path and an
intermediate node is not a mapping (it is a scalar or a list), yamlpatch
raises a `PatchError` whose message contains one of three Rust-layer
substrings:

| Rust substring | Triggering scenario |
|---|---|
| `"non-mapping route"` | `Op.add` with a scalar or list as the parent |
| `"expected mapping containing key"` | `Op.merge_into` with a list as the parent |
| `"unexpected node"` | `Op.merge_into` with a scalar as the parent |

There is currently no typed exception for this condition. Callers who need
to distinguish a routing failure from other `PatchError`s must match raw
strings — fragile and not part of the public API contract.

`merge()` already works around this by catching `_PatchErrorKind.UNEXPECTED_NODE`
and re-raising as `NodeTypeError`. That is an approximation: routing errors
and target-type errors are distinct failure modes and should have distinct
exception types.

---

## Goals

- Introduce `RoutingError` so callers can `except yamltrip.RoutingError`
  without any string matching.
- Confine all three routing-related Rust substrings to the existing
  `_PatchErrorKind` / `_classify_patch_error` / `_is_routing_error` layer.
- Produce human-readable messages (`"Route passes through a non-mapping node
  at a > b"`) rather than leaking Rust internals.
- Fix `merge()` to raise `RoutingError` instead of `NodeTypeError` for
  routing failures (breaking change; `NodeTypeError` was an approximation).

---

## Exception Hierarchy

```python
# errors.py — added after KeyMissingError, before NodeTypeError
class RoutingError(PatchError):
    """Raised when a key path passes through a non-mapping node."""
```

`RoutingError` is a direct subclass of `PatchError`. It is **not** a subclass
of `NodeTypeError`: routing errors and target-type errors are semantically
distinct, and `NodeTypeError` carries a `TypeError` mixin that is not
appropriate here.

`RoutingError` is exported in `__init__.py` alongside the other `PatchError`
subclasses.

---

## Detection Layer (`_PatchErrorKind`, `_classify_patch_error`, `_is_routing_error`)

Two new members are added to `_PatchErrorKind` (after `BLOCK_SEQUENCE_EXPECTED`,
before `UNEXPECTED_NODE`):

```python
NON_MAPPING_ROUTE = "non-mapping route"
EXPECTED_MAPPING  = "expected mapping containing key"
```

`UNEXPECTED_NODE = "unexpected node"` already exists and is also a routing
error in all contexts where yamlpatch emits it.

`_classify_patch_error` gains two new branches (inserted before the
`UNEXPECTED_NODE` check):

```python
if _PatchErrorKind.NON_MAPPING_ROUTE.value in msg:
    return _PatchErrorKind.NON_MAPPING_ROUTE
if _PatchErrorKind.EXPECTED_MAPPING.value in msg:
    return _PatchErrorKind.EXPECTED_MAPPING
```

A new module-level helper (placed after `_classify_patch_error`) unifies the
three routing kinds:

```python
def _is_routing_error(kind: _PatchErrorKind) -> bool:
    """Return True if kind represents a routing failure."""
    return kind in (
        _PatchErrorKind.NON_MAPPING_ROUTE,
        _PatchErrorKind.EXPECTED_MAPPING,
        _PatchErrorKind.UNEXPECTED_NODE,
    )
```

`_is_routing_error` is the single place in the codebase that knows which Rust
error substrings constitute a routing failure.

---

## Raise Sites (Option A: catch in private helpers)

### `_create_at(parent_keys, child_keys, value)`

`_create_at` is the common creation path for both `upsert` and `add` (when the
document is empty). Each `_apply_patches` call that uses `parent_keys` as the
route is wrapped:

```python
try:
    return self._apply_patches([patch])          # or [add_patch, replace_patch]
except PatchError as e:
    if _is_routing_error(_classify_patch_error(e)):
        msg = f"Route passes through a non-mapping node at {format_path(parent_keys)}"
        raise RoutingError(msg) from None
    raise
```

The bootstrap branch (`not parent_keys and self._is_empty_document()`) creates
a `Document` from scratch and never calls `_apply_patches`, so no catch is
needed there.

### `add(*keys, key, value)`

The non-empty-document path calls `_apply_patches` directly (not via
`_create_at`). That call is wrapped identically, using `keys` as the path:

```python
try:
    return self._apply_patches([patch])
except PatchError as e:
    if _is_routing_error(_classify_patch_error(e)):
        msg = f"Route passes through a non-mapping node at {format_path(keys)}"
        raise RoutingError(msg) from None
    raise
```

### `merge()`

The existing `_classify_patch_error(e) == _PatchErrorKind.UNEXPECTED_NODE`
block is removed entirely. `upsert` (via `_create_at`) now raises `RoutingError`
directly with a good message; `merge()` just lets it propagate.

The ancestor-finding loop in `merge()` (previously used to construct the
`NodeTypeError` message) is no longer needed.

### Methods that get `RoutingError` for free

`upsert`, `sync`, and any future method that calls `_create_at` raise
`RoutingError` without any further changes.

---

## Public API

### `errors.py`

```python
class RoutingError(PatchError):
    """Raised when a key path passes through a non-mapping node."""
```

### `__init__.py`

`RoutingError` added to the import from `.errors` and to `__all__`, placed
adjacent to the other `PatchError` subclasses.

### `editor.py`

No changes required. `RoutingError` propagates through `Editor`'s delegation
layer automatically.

---

## Tests

### `TestPatchErrorStringPins` additions (in `test_edge_cases.py`)

Two new substring pin tests with their `test_classify_*` counterparts:

- `test_non_mapping_route_substring` — triggers `Op.add` on a scalar parent,
  asserts `_PatchErrorKind.NON_MAPPING_ROUTE.value in msg`
- `test_expected_mapping_substring` — triggers `Op.merge_into` on a list parent,
  asserts `_PatchErrorKind.EXPECTED_MAPPING.value in msg`
- `test_classify_non_mapping_route` — verifies classifier round-trips to `NON_MAPPING_ROUTE`
- `test_classify_expected_mapping` — verifies classifier round-trips to `EXPECTED_MAPPING`

### New `TestRoutingError` class (in `test_errors.py` or `test_edge_cases.py`)

Behaviour tests that verify the public exception type and message:

- `upsert("a", "b", value=...)` on `a: scalar` raises `RoutingError` with `"at a"` in message
- `add("a", key="b", value=...)` on `a: scalar` raises `RoutingError`
- `merge("a", "b", value=...)` on `a: scalar` raises `RoutingError` (not `NodeTypeError`)
- `isinstance(err, PatchError)` — confirms `RoutingError` IS-A `PatchError`
- `upsert("a", "b", value=...)` on `items: [x, y]` raises `RoutingError`
  (covers the `EXPECTED_MAPPING` path)

### Existing tests

`NodeTypeError` tests for `append`, `insert`, `extend_list` on wrong-type
targets are unaffected. Any existing test that asserts `NodeTypeError` from
`merge()` for routing failures must be updated to expect `RoutingError`.

### Public API / stubs

`test_public_api.py` or `test_stubs.py` must be updated to include `RoutingError`
in the expected exports.

---

## Breaking Changes

| Method | Old exception | New exception |
|---|---|---|
| `merge()` routing through non-mapping | `NodeTypeError` | `RoutingError` |

All other methods (`upsert`, `add`, `sync`) previously raised raw `PatchError`
for routing failures; they now raise the more specific `RoutingError`, which is
a `PatchError` subclass — `except PatchError` continues to work.
