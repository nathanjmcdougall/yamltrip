# Document.get() — Non-Raising Value Access

**Date:** 2026-05-19
**Issue:** #23

## Problem

Accessing `doc.root` or `doc[()]` on a document with no YAML value (empty string, comment-only, or `---` only) raises `QueryError`. This forces callers to wrap every access in try/except even though an empty document is a normal state.

The request proposes making `.root` return `None`, but that conflates "document has no value" with "document explicitly contains null" — two semantically different states. A `.get()` pattern keeps the distinction clear and gives callers control over the fallback.

## Design

Add a `get(*keys, default=None)` method to `Document` and `Editor` that returns the parsed Python value at the given path, or `default` if the path doesn't exist.

### Signature

```python
def get(self, *keys: KeyPart, default: Any = None) -> Any:
```

### Semantics

| Expression | Result |
|------------|--------|
| `doc.get()` | Root value, or `None` if empty doc |
| `doc.get('tool', 'ruff')` | Value at path, or `None` if missing |
| `doc.get('missing', default={})` | `{}` |
| `doc.get('existing_null_key')` | `None` (the actual YAML null) |
| `doc.root` | Unchanged — still raises `QueryError` on empty docs |

### Null Ambiguity

`doc.get('key')` returns `None` both for "key missing" and "key has YAML null value". Callers who need to distinguish use `'key' in doc` first. This is the same trade-off as `dict.get()`.

## Implementation

### Document.get()

```python
def get(self, *keys: KeyPart, default: Any = None) -> Any:
    """Return the parsed value at path, or default if the path doesn't exist."""
    normalized = _normalize_keys(keys) if keys else ()
    route = _make_route(normalized)
    if not self._core_doc.query_exists(route):
        return default
    return self._core_doc.parse_value(route)
```

Uses `query_exists` (the same mechanism as `__contains__`) to check existence before accessing. No exception handling in the happy path.

### Editor.get()

Delegates to the underlying document:

```python
def get(self, *keys: KeyPart, default: Any = None) -> Any:
    """Return the parsed value at path, or default if missing."""
    return self._document.get(*keys, default=default)
```

## Change Locations

- `src/yamltrip/document.py` — add `get()` method to `Document`
- `src/yamltrip/editor.py` — add `get()` method to `Editor`
- No Rust changes required

## Testing

New tests:

- `doc.get()` on empty document → `None`
- `doc.get()` on comment-only document → `None`
- `doc.get()` on `---\n` document → `None`
- `doc.get()` on document with root value → returns the value
- `doc.get('key')` on existing key → returns value
- `doc.get('key')` on missing key → `None`
- `doc.get('key', default={})` on missing key → `{}`
- `doc.get('nested', 'path')` on existing nested path → value
- `doc.get('nested', 'missing')` on partial path → `None`
- `doc.get('null_key')` where value is YAML null → `None`
- `doc.root` still raises on empty docs (no regression)
- `Editor.get()` mirrors Document behavior

## Scope Boundaries

**In scope:**
- `Document.get()` method
- `Editor.get()` method

**Out of scope:**
- Changing `.root` behavior
- Adding `.get()` to the stub file (`_core.pyi`) — this is Python-only
- Sentinel-based missing detection (use `in` operator for that)
