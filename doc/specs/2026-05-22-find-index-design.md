# Document.find_index() — Find Item in List-of-Dicts

**Date:** 2026-05-22

## Problem

YAML configs frequently use lists of dicts keyed by a distinguishing field:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks: [...]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [...]
```

Finding an item by field value currently requires manual iteration:

```python
repos = doc["repos"]
idx = next((i for i, r in enumerate(repos) if r["repo"] == url), None)
doc = doc.replace("repos", idx, "hooks", value=new_hooks)
```

This is verbose, error-prone, and repeated across callers.

## Design

Add a `find_index` method to `Document` and `Editor` that returns the index of the first list item matching a set of key/value constraints.

### Signature

```python
def find_index(self, *keys: KeyPart, where: dict[str, Any]) -> int | None:
```

### Semantics

| Expression | Result |
|------------|--------|
| `doc.find_index("repos", where={"repo": url})` | Index of first item where `item["repo"] == url`, or `None` |
| `doc.find_index("repos", where={"repo": url, "rev": "v1"})` | First item matching *all* pairs (AND semantics) |
| `doc.find_index("repos", where={"repo": "nonexistent"})` | `None` |
| `doc.find_index("steps", where={"uses": "actions/checkout@v4"})` | Works for any list-of-dicts |

### Behavior

1. Retrieve the parsed value at `keys`
2. If value is not a list, raise `NodeTypeError`
3. If path doesn't exist, raise `QueryError`
4. Iterate items left-to-right; return index of first item where `item[k] == v` for all `(k, v)` in `where`
5. Items that are not dicts are skipped (no error)
6. Return `None` if no item matches

### Error Cases

| Condition | Raised |
|-----------|--------|
| Path doesn't exist | `QueryError` |
| Value at path is not a list | `NodeTypeError` |
| `where` is empty | `ValueError` |

### Editor Delegation

```python
class Editor:
    def find_index(self, *keys: KeyPart, where: dict[str, Any]) -> int | None:
        return self._doc.find_index(*keys, where=where)
```

## Change Locations

- `src/yamltrip/document.py` — add `find_index()` method to `Document`
- `src/yamltrip/editor.py` — add `find_index()` method to `Editor`
- `src/yamltrip/_core.pyi` — no changes (Python-only logic)
- No Rust changes required

## Testing

New tests:

- `doc.find_index("repos", where={"repo": url})` → correct index
- `doc.find_index("repos", where={"repo": "missing"})` → `None`
- Multi-key where: `where={"repo": url, "rev": "v1"}` matches only when both match
- First match wins when multiple items match
- Non-dict items in list are skipped
- Path not found → `QueryError`
- Value is a scalar → `NodeTypeError`
- Value is a dict → `NodeTypeError`
- Empty `where={}` → `ValueError`
- Nested path: `doc.find_index("ci", "steps", where={"uses": "..."})`
- Integer key in path prefix works: `doc.find_index("jobs", 0, "steps", where={...})`
- Editor.find_index mirrors Document behavior

## Scope Boundaries

**In scope:**
- `Document.find_index()` method
- `Editor.find_index()` method

**Out of scope:**
- `match=` callable predicate (future addition, additive)
- `find_value()` or `find()` returning the item itself (use `doc[*keys, idx]`)
- `find_all_indices()` returning multiple matches
- Rust-side implementation (pure Python is sufficient; values are already parsed)
