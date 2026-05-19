# Sync Operation

**Date:** 2026-05-20
**Issue:** #25

## Problem

A common pattern when editing YAML config files is: parse into a Python dict, mutate the dict, write it back preserving comments and formatting. With yamltrip today, step 3 requires manually orchestrating individual `upsert`, `replace`, `append`, `remove`, and `remove_from_list` calls for each change. This is verbose and error-prone.

## Design

Add a `sync` method that takes a desired Python value, diffs it against the current document content at a given path, and applies the minimal set of patches.

### Signature

```python
# Document (immutable — returns new Document)
def sync(self, *keys: KeyPart, value: Any) -> Document:

# Editor (mutable — updates in place)
def sync(self, *keys: KeyPart, value: Any) -> None:
```

### Examples

```python
# Sync a mapping — adds missing keys, removes extra keys, updates changed values
doc2 = doc.sync('ci', value={'autofix_prs': False, 'skip': ['codespell']})

# Sync a list — uses SequenceMatcher for minimal edits
doc2 = doc.sync('repos', value=new_repos)

# Sync at root
doc2 = doc.sync(value={'ci': {...}, 'repos': [...]})

# No-op — returns self when value already matches
doc2 = doc.sync('ci', value=doc['ci'])
assert doc2 is doc
```

### Diff Algorithm

The diff is recursive. At each level, the type of old and new values determines the strategy:

**Mapping diff** (both old and new are dicts):
1. Keys in new that exist in old → recurse into value pair
2. Keys in new that don't exist in old → `upsert` the new key+value
3. Keys in old that don't exist in new → `remove` the key
4. Key ordering: existing key order is preserved; new keys are appended at the end

**List diff** (both old and new are lists):
Uses `difflib.SequenceMatcher` to compute an optimal edit script. Items are compared by deep equality (`==`). Since `SequenceMatcher` requires hashable elements, items are mapped to integers via equality comparison (same approach as usethis's `_shared_id_sequences`).

Opcode translation:
- `equal` → no patch
- `replace` → if both items are dicts, recurse; otherwise `replace` at index
- `insert` → `insert(index=...)` for each new item
- `delete` → `remove` at index (processed in reverse to preserve indices)

**Scalar diff** (values differ or types differ):
- Single `replace` at the path

**Type mismatch** (e.g. old is mapping, new is scalar):
- Single `replace` at the path (no error)

### Patch Application Order

Patches are applied sequentially — each patch operates on the result of the previous one. For list diffs, opcodes are processed left-to-right with a running position offset that accounts for how prior inserts/deletes have shifted indices. This mirrors how usethis's `lcs_list_update` maintains an `original_idx` cursor.

For mapping diffs and scalar replacements, order doesn't matter (no index shifting).

### Edge Cases

| Scenario | Behavior |
|---|---|
| Path doesn't exist in document | `upsert` the whole value (creates path) |
| Type mismatch at path | `replace` the whole node |
| `value` is `{}` | Remove all keys from mapping at path |
| `value` is `[]` | Remove all items from sequence at path |
| `value` is `None` | Replace with YAML null |
| Value already matches | Return `self` (no patches, identity preserved) |
| Root-level sync (empty keys) | Diffs the entire document root |

### No-op Optimization

When the diff produces zero patches, `sync` returns `self` unchanged. This allows callers to detect "no changes needed" via `doc.sync(...) is doc`.

## Module Structure

New file: `src/yamltrip/sync.py`

Contains the pure diff logic:

```python
def _compute_patches(
    old_value: Any,
    new_value: Any,
    path: tuple[KeyPart, ...],
) -> list[_core.Patch]:
```

This function is called by `Document.sync()` which:
1. Checks if the path exists — if not, delegates to `upsert`
2. Gets current value via `self[keys]`
3. Calls `_compute_patches(old, new, keys)`
4. If no patches, returns `self`
5. Otherwise, applies patches via `self._apply_patches(patches)`

## Change Locations

- `src/yamltrip/sync.py` — new module with `_compute_patches` and helpers
- `src/yamltrip/document.py` — add `sync()` method to `Document`
- `src/yamltrip/editor.py` — add `sync()` method to `Editor`
- No Rust changes required

## Testing

### Mapping sync tests
- Add a new key to a mapping
- Remove a key from a mapping
- Change a scalar value in a mapping
- Nested mapping: change a deep value
- Nested mapping: add a deep key
- Sync preserves comments on unchanged keys
- Sync preserves comments on keys with changed values
- Empty dict `{}` removes all mapping keys

### List sync tests
- Append items to a list
- Remove items from a list
- Replace an item in a list (scalar)
- Insert an item in the middle
- Reorder items (delete + insert)
- List of dicts: changed dict is recursed into (comments preserved)
- Empty list `[]` removes all items
- Preserves comments on unchanged list items

### Type mismatch tests
- Old is mapping, new is scalar → replaces
- Old is scalar, new is mapping → replaces
- Old is list, new is scalar → replaces

### Path handling tests
- Path doesn't exist → creates via upsert
- Root-level sync (empty keys)
- Nested path with intermediate keys

### No-op tests
- Value matches exactly → returns `self`
- Editor: no-op sync doesn't modify file

### Integration tests
- Pre-commit-style config: add a repo, modify a hook, remove a repo
- Multi-level nested change in one sync call

## Scope Boundaries

**In scope:**
- `Document.sync()` method
- `Editor.sync()` method
- New `sync.py` module with diff logic
- Tests for all the above

**Out of scope:**
- `key` parameter for identity-based list matching (future PR)
- Key reordering within mappings
- Stub file changes — this is pure Python
- Performance optimization for large documents
