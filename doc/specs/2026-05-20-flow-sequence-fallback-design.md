# Flow Sequence Fallback

**Date:** 2026-05-20
**Issue:** #31

## Problem

`insert()`, `append()`, `extend_list()`, and `sync()` raise `PatchError` when the target sequence uses flow syntax (e.g. `repos: [a, b, c]` or `repos: []`). The Rust `apply_insert_at` implementation requires a `BlockSequence` tree-sitter node — flow sequences have different grammar structure and are not supported.

This forces callers to defensively wrap calls in try/except:

```python
try:
    doc = doc.sync("repos", value=repos_list)
except yamltrip.PatchError:
    doc = doc.upsert("repos", value=repos_list)
```

The error is surprising because callers expressed high-level intent ("append to this list", "sync this list") and don't expect to care about YAML syntax details.

## Design

When a list-mutating operation hits a flow sequence, fall back to a get→mutate→replace strategy in Python. This eliminates the `PatchError` for flow sequences at the cost of losing inline formatting (flow → block conversion), which is acceptable because:

1. An empty flow sequence (`[]`) has no formatting to preserve.
2. A non-empty single-line flow sequence cannot contain comments; multi-line flow sequences could in theory, but are vanishingly rare in practice.
3. The alternative is crashing.

### Affected Methods

| Method | Current Behavior | New Behavior |
|--------|-----------------|--------------|
| `sync()` | `PatchError` when diff produces `insert_at` on flow seq | Catch error, fall back to full `replace` with computed new value |
| `insert()` | `PatchError` always on flow seq | Get current list, insert in Python, `replace` full list |
| `append()` | `PatchError` always on flow seq | Get current list, append in Python, `replace` full list |
| `extend_list()` | `PatchError` always on flow seq | Get current list, extend in Python, `replace` full list |

### Detection Strategy

Catch `PatchError` from `_apply_patches` and inspect the message for the flow sequence signature (`"expected BlockSequence"`). If matched, execute the fallback. If not, re-raise.

This is preferable to pre-checking the node type because:
- It keeps the happy path (block sequences) zero-cost.
- It avoids duplicating Rust-side type checking in Python.
- It naturally handles mixed patches where only some operations hit flow sequences.

### Implementation: `sync()`

```python
def sync(self, *keys: KeyPart, value: Any) -> Document:
    ...
    patches = _compute_patches(old_value, value, normalized)
    if not patches:
        return self
    try:
        return self._apply_patches(patches)
    except PatchError as e:
        if "expected BlockSequence" not in str(e):
            raise
        # Flow sequence — fall back to replacing the entire value
        route = _make_route(normalized)
        op = _core.Op.replace(value)
        return self._apply_patches([_core.Patch(route=route, operation=op)])
```

### Implementation: `insert()`

```python
def insert(self, *keys: KeyPart, index: int, value: Any) -> Document:
    route = _make_route(keys)
    op = _core.Op.insert_at(index=index, value=value)
    patch = _core.Patch(route=route, operation=op)
    try:
        return self._apply_patches([patch])
    except PatchError as e:
        if "expected BlockSequence" not in str(e):
            raise
        current = self[keys]
        # Use Python list.insert semantics
        new_list = list(current)
        new_list.insert(index, value)
        replace_op = _core.Op.replace(new_list)
        return self._apply_patches([_core.Patch(route=route, operation=replace_op)])
```

### Implementation: `append()`

```python
def append(self, *keys: KeyPart, value: Any) -> Document:
    route = _make_route(keys)
    op = _core.Op.append(value)
    patch = _core.Patch(route=route, operation=op)
    try:
        return self._apply_patches([patch])
    except PatchError as e:
        if "expected BlockSequence" not in str(e):
            raise
        current = self[keys]
        new_list = list(current) + [value]
        replace_op = _core.Op.replace(new_list)
        return self._apply_patches([_core.Patch(route=route, operation=replace_op)])
```

### Implementation: `extend_list()`

```python
def extend_list(self, *keys: KeyPart, values: Sequence[Any]) -> Document:
    if not values:
        return self
    route = _make_route(keys)
    patches = [
        _core.Patch(route=route, operation=_core.Op.append(v)) for v in values
    ]
    try:
        return self._apply_patches(patches)
    except PatchError as e:
        if "expected BlockSequence" not in str(e):
            raise
        current = self[keys]
        new_list = list(current) + list(values)
        replace_op = _core.Op.replace(new_list)
        return self._apply_patches([_core.Patch(route=route, operation=replace_op)])
```

## Behavioral Notes

- The fallback always produces block sequence output. `repos: []` becomes:
  ```yaml
  repos:
    - item1
    - item2
  ```
- If the entire value is being replaced (e.g. `sync` from `[a]` to `[b]`), no fallback is needed — `Op.replace` works on any node type.
- Comment preservation: flow sequences cannot contain comments, so no comments are lost.
- The fallback does NOT apply to `remove()` or `remove_from_list()` — those already work on flow sequences via index paths.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `sync("key", value=[])` on flow seq `key: [a, b]` | No fallback needed — `_diff_lists` emits a single `replace([])` |
| `sync("key", value=[a, b])` on `key: []` (flow) | Fallback: replace with `[a, b]` as block |
| `insert("key", index=0, value="x")` on `key: [a]` (flow) | Fallback: replace with `["x", "a"]` |
| `append("key", value="x")` on `key: []` (flow) | Fallback: replace with `["x"]` |
| Nested flow inside block: `- [a, b]` | Fallback applies to inner flow sequence if targeted directly |

## Not In Scope

- Teaching Rust to natively insert into flow sequences (potential future optimization).
- Converting block sequences to flow sequences.
- Handling flow mappings (`{a: 1, b: 2}`) — not affected since `sync` on mappings uses `add`/`replace`/`remove`, not `insert_at`.
