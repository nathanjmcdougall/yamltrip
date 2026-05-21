# Design: `ensure_in_list` — Idempotent List Addition

**Date:** 2026-05-22  
**Status:** Approved

## Problem

"Add this value to the list if it's not already there" requires manual
check-then-append boilerplate:

```python
items = doc["items"]
if "new_hook" not in items:
    doc = doc.append("items", value="new_hook")
```

This is the most common pattern when managing hook lists, dependency arrays,
and plugin registrations.

## API

### Document (immutable, returns new Document)

```python
def ensure_in_list(
    self,
    *keys: KeyPart,
    value: Any,
    where: dict[str, Any] | None = None,
) -> Document:
```

### Editor (mutable, returns None)

```python
def ensure_in_list(
    self,
    *keys: KeyPart,
    value: Any,
    where: dict[str, Any] | None = None,
) -> None:
```

## Semantics

### Scalar matching (`where=None`)

Check if `value` is already in the list via Python `==`. No-op if present,
append if not.

```python
doc = doc.ensure_in_list("hooks", value="pre-commit")
# If "pre-commit" already in doc["hooks"], returns self unchanged.
# Otherwise appends it.
```

### Dict matching (`where={...}`)

Check if any item in the list has all key/value pairs in `where` (AND
semantics, equality via Python `==`). No-op if a match exists, append `value`
if not.

The matched item is NOT updated — `ensure_in_list` guarantees presence, not
correctness. Users who need update-in-place should use `find_index` + `replace`
or `sync`.

```python
doc = doc.ensure_in_list(
    "repos",
    where={"repo": "https://github.com/pre-commit/mirrors-prettier"},
    value={
        "repo": "https://github.com/pre-commit/mirrors-prettier",
        "rev": "v3.0.0",
        "hooks": [{"id": "prettier"}],
    },
)
```

### Path missing — create the list

If the path does not exist, create intermediate mappings (like `upsert`) and
set the value to `[value]`.

```python
doc = doc.ensure_in_list("new_list", value="first_item")
# Result: new_list:\n-  first_item
```

### Path exists but is not a list

Raise `NodeTypeError`.

### Flow sequence fallback

Same pattern as `append`: catch the flow-sequence error from yamlpatch and fall
back to reading the current list, checking membership in Python, and replacing
with the new list if needed.

### Idempotence

Calling `ensure_in_list` twice with the same arguments always produces the same
result. This is guaranteed by the no-op-if-present semantics.

## What this does NOT include

- **No `values` plural parameter.** Caller loops for multiple items. This
  avoids ambiguity about `where` + `values` interaction.
- **No update-in-place.** If `where` matches an existing item, returns self
  unchanged regardless of whether `value` differs from the matched item.
- **No `upsert_in_list`.** Deferred until demand appears.

## Error conditions

| Condition | Behavior |
|-----------|----------|
| Path missing | Create list with `[value]` |
| Path is not a list | Raise `NodeTypeError` |
| `where` is empty dict | Raise `ValueError` (matches `find_index`) |
| `where` provided but list items aren't dicts | No match found → append |

## Implementation approach

Pure Python in `document.py`. No Rust changes needed — this composes existing
primitives (`__contains__`, `__getitem__`, `append`, `upsert`).

Rough logic:

```python
def ensure_in_list(self, *keys, value, where=None):
    if where is not None:
        if not where:
            raise ValueError("where must be a non-empty dict")

    # Check if path exists
    route = _make_route(keys)
    if not self._core_doc.query_exists(route):
        # Path missing: create with [value]
        return self.upsert(*keys, value=[value])

    current = self[keys]
    if not isinstance(current, list):
        msg = f"Value at {keys} is not a list"
        raise NodeTypeError(msg)

    # Check membership
    if where is None:
        if value in current:
            return self
    else:
        for item in current:
            if isinstance(item, dict) and all(
                k in item and item[k] == v for k, v in where.items()
            ):
                return self

    # Not present: append
    return self.append(*keys, value=value)
```

## Documentation

Add an example to README.md showing both the scalar and `where`-based usage.

## Testing

- Scalar value already present → no-op (same source)
- Scalar value missing → appended
- Dict matching via `where` already present → no-op
- Dict matching via `where` missing → appended
- Path does not exist → list created
- Path is a scalar → `NodeTypeError`
- Path is a mapping → `NodeTypeError`
- Empty `where` dict → `ValueError`
- Flow sequence handling (inline `[a, b]` style)
- Idempotence: calling twice gives same result
- Editor wrapper delegates correctly
