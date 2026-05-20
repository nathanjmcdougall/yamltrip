# NodeTypeError for Type Mismatch Operations

**Date:** 2026-05-20
**Issue:** #31

## Problem

When a caller uses a sequence operation (`append`, `remove_from_list`, etc.) on a node that isn't a sequence, or a mapping operation on a non-mapping, the error raised is a bare `PatchError`. This conflates "the operation is structurally impossible given YAML syntax limitations" with "you called the wrong method for this node type."

The latter is a caller mistake — semantically a `TypeError` — and should be distinguishable from structural failures.

## Design

Introduce `NodeTypeError` as a subclass of both `PatchError` and `TypeError`:

```python
class NodeTypeError(PatchError, TypeError):
    """Raised when a node is not the expected type for the operation."""
```

### Why dual inheritance?

- Subclassing `PatchError` preserves backward compatibility: existing `except PatchError` handlers still catch it.
- Subclassing `TypeError` communicates the semantic meaning: the caller passed a path to the wrong kind of node.

### Error Hierarchy After Change

```
Exception
├── TypeError
│   └── NodeTypeError (also under PatchError)
└── YAMLTripError
    ├── ParseError
    ├── QueryError
    └── PatchError
        ├── KeyExistsError
        ├── KeyMissingError
        └── NodeTypeError (also under TypeError)
```

## Affected Call Sites

### Python-side checks (already explicit)

| Method | Current | New |
|--------|---------|-----|
| `remove_from_list()` | `raise PatchError("Value at {keys} is not a list")` | `raise NodeTypeError(...)` |

### Rust-side errors (detected by message pattern)

| Error message pattern | Source operation | New behavior |
|----------------------|-----------------|--------------|
| `"Value is not a mapping"` | `add()` on non-mapping | Catch `PatchError`, re-raise as `NodeTypeError` |
| `"Value is not a sequence"` | `append()` on non-sequence | Catch `PatchError`, re-raise as `NodeTypeError` |

### Detection in `_apply_patches`

Rather than adding detection logic to `_apply_patches` itself (which is generic), each public method that expects a specific node type handles the re-raise:

```python
def append(self, *keys: KeyPart, value: Any) -> Document:
    route = _make_route(keys)
    op = _core.Op.append(value)
    patch = _core.Patch(route=route, operation=op)
    try:
        return self._apply_patches([patch])
    except PatchError as e:
        if "expected BlockSequence" not in str(e):
            # Not a flow sequence issue — check if it's a type mismatch
            if "not a sequence" in str(e):
                raise NodeTypeError(str(e)) from None
            raise
        # flow sequence fallback (from the other spec)
        ...
```

## Error Messages

The messages stay descriptive of what went wrong:

```python
NodeTypeError("Value at ('config',) is not a list")
NodeTypeError("Patch failed: Value is not a sequence")
NodeTypeError("Patch failed: Value is not a mapping")
```

## Public API Changes

### New export

```python
# yamltrip/__init__.py
from yamltrip.errors import NodeTypeError

# yamltrip/errors.py
class NodeTypeError(PatchError, TypeError):
    """Raised when a node is not the expected type for the operation."""
```

### Stub update

```python
# yamltrip/_core.pyi — no change needed (error is Python-only)
```

## Backward Compatibility

Fully backward compatible:
- `except PatchError` still catches `NodeTypeError`.
- `except TypeError` now also catches it (new capability).
- `except NodeTypeError` is available for callers who want to distinguish.

## Not In Scope

- Checking node types before calling Rust (would require adding Python-side query logic that duplicates Rust). The catch-and-re-raise approach is sufficient.
- Flow mapping type errors — `sync` on mappings uses `add`/`replace`/`remove` which don't have this problem.
