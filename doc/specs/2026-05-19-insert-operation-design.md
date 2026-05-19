# Insert Operation for Block Sequences

**Date:** 2026-05-19
**Issue:** #24

## Problem

There is no way to insert an item at a specific position in a YAML sequence while preserving comments on existing items. The only options are `append` (end only) or `replace` on the entire list (loses internal comments).

Use case: in usethis, pre-commit hooks have a defined ordering. Adding a new hook repo at a specific position requires inserting between existing repos.

## Approach

Direct string surgery in yamltrip's Rust layer (`document.rs`), following the same pattern as `apply_complex_replace`. The operation is intercepted in `apply_patches_impl` before reaching yamlpatch, since `yamlpatch::Op` has no `InsertAt` variant and we cannot upstream to yamlpatch.

## Python API

### Document (immutable)

```python
doc = doc.insert('repos', index=1, value={'repo': 'https://...', 'hooks': [...]})
doc = doc.insert('repos', index=-1, value='before_last')  # negative index
doc = doc.insert('repos', index=0, value='prepend')        # prepend
```

**Signature:** `insert(*keys: KeyPart, index: int, value: Any) -> Document`

### Editor (mutable)

```python
with Editor('file.yaml') as ed:
    ed.insert('repos', index=1, value=new_repo)
```

**Signature:** `insert(*keys: KeyPart, index: int, value: Any) -> None`

### Index Semantics

Follows Python `list.insert()`:
- Non-negative indices insert before the item at that position.
- Negative indices count from the end: `-1` means before the last item, `-2` before the second-to-last, etc.
- Out-of-range indices clamp: `index >= len` acts like append, `index <= -len` acts like prepend.

## Rust Layer

### The Problem with `yamlpatch::Op`

`yamlpatch::Op` is an external enum we cannot extend. We need a way to represent `InsertAt` in the patch pipeline.

### Solution: Extend `PyOp` with a local variant

Introduce an internal enum in `ops.rs` that wraps both yamlpatch ops and local-only ops:

```rust
/// Operations that yamltrip handles locally (not in yamlpatch).
#[derive(Clone, Debug)]
pub enum LocalOp {
    InsertAt { index: i64, value: serde_yaml::Value },
}

/// The inner representation of a PyOp.
#[derive(Clone, Debug)]
pub enum OpInner {
    Yamlpatch(yamlpatch::Op<'static>),
    Local(LocalOp),
}
```

`PyOp` changes from holding `yamlpatch::Op<'static>` directly to holding `OpInner`. The existing `#[staticmethod]` constructors (`replace`, `add`, `remove`, `append`, etc.) wrap in `OpInner::Yamlpatch(...)`. A new `insert_at` constructor wraps in `OpInner::Local(LocalOp::InsertAt { ... })`.

### Patch Routing in `apply_patches_impl`

The existing logic batches yamlpatch ops and flushes them together. `InsertAt` (and any future local ops) flush the batch first, then execute via dedicated string surgery — identical to the complex-replace pattern:

```
for each patch:
    if patch is Local(InsertAt { index, value }):
        flush yamlpatch batch
        apply_insert_at(&current_doc, &route, index, &value)
    else:
        add to yamlpatch batch
flush remaining batch
```

### `Op.insert_at` Python-facing constructor

```python
op = Op.insert_at(index=1, value={'repo': '...'})
```

### `kind` getter

Returns `"insert_at"` for the new variant.

## Algorithm: `apply_insert_at`

Input: `yamlpath::Document`, `yamlpath::Route` (pointing to the sequence), `index: i64`, `serde_yaml::Value`.

1. **Query the sequence feature** — `document.query_exact(&route)` → verify `FeatureKind::BlockSequence`. Error if not found, or if it's a flow sequence or non-sequence.

2. **Count items** — Iterate `route + [0]`, `route + [1]`, ... until `query_exists` returns false. Let `len` = item count.

3. **Resolve index (Python semantics):**
   ```
   if index < 0:
       resolved = max(0, len + index)
   else:
       resolved = min(index, len)
   ```

4. **Delegate to append if `resolved == len`:**
   Build a `yamlpatch::Op::Append { value }` patch and apply via yamlpatch. This reuses existing append logic including its indentation handling.

5. **Locate insertion byte position:**
   - Query `route + [resolved]` with `query_exact` to get the item feature.
   - The insertion point is the byte offset of the item's `- ` dash (accounting for leading whitespace on its line).
   - Walk backward from `feature.location.byte_span.0` to the start of the line to include the leading whitespace/indentation.

6. **Determine indentation:**
   - Extract the indentation string from the target item's line (characters from line start to `- `).
   - This becomes the indentation for the new item.

7. **Serialize new value as a sequence item:**
   - Scalar: `- value\n`
   - Mapping: `- key1: val1\n  key2: val2\n...` (indented relative to the dash)
   - Sequence: `- - item1\n  - item2\n...` (nested sequence)
   - Use `serde_yaml::to_string(&value)` then reformat as a sequence item with correct indentation.

8. **String splice** — Insert the formatted item text at the computed byte position (before the target item's line start).

9. **Re-parse** — `yamlpath::Document::new(patched_source)` to validate.

### Serialization Detail

The new item text must be a complete block sequence entry. Given base indent `I` (spaces before `-`):

- For a scalar value `v`: `"{I}- {v}\n"`
- For a mapping `{k1: v1, k2: v2}`:
  ```
  {I}- k1: v1
  {I}  k2: v2
  ```
- For a sequence `[a, b]`:
  ```
  {I}- - a
  {I}  - b
  ```

Use `serde_yaml::to_string` for the value portion, then prefix the first line with `{I}- ` and subsequent lines with `{I}  ` (indent = base + 2).

## Error Cases

| Condition | Error |
|-----------|-------|
| Path doesn't exist | `PatchError("Path not found: ...")` |
| Target is not a sequence | `PatchError("Value at ... is not a sequence")` |
| Target is a flow sequence | `PatchError("insert requires a block sequence; flow sequences are not supported")` |

No `IndexError` is raised — indices always clamp (matching `list.insert()` behavior).

## Files Changed

| File | Change |
|------|--------|
| `src/ops.rs` | Add `LocalOp` enum, `OpInner` wrapper, `insert_at` constructor, update `kind`/`__repr__` |
| `src/document.rs` | Add `apply_insert_at` function, update `apply_patches_impl` routing |
| `src/yamltrip/document.py` | Add `Document.insert()` method |
| `src/yamltrip/editor.py` | Add `Editor.insert()` method |
| `src/yamltrip/_core.pyi` | Add type stub for `Op.insert_at` |
| `tests/test_core_ops.py` | Tests for `Op.insert_at` construction |
| `tests/test_document.py` | Tests for `Document.insert()` |
| `tests/test_editor.py` | Tests for `Editor.insert()` |

## Test Cases

1. Insert at beginning (`index=0`) of multi-item list
2. Insert in middle (`index=1` of 3-item list)
3. Insert at end (`index=len`) — should produce same result as append
4. Negative index (`index=-1` inserts before last)
5. Negative out-of-range (`index=-100` prepends)
6. Positive out-of-range (`index=100` appends)
7. Complex value (dict with nested structure)
8. Comment preservation — comments on items before and after insertion point are untouched
9. Empty sequence (`index=0`)
10. Single-item sequence (insert before and after)
11. Value with special YAML characters (strings needing quoting)
12. Nested sequence insertion (list within list)
13. Target is not a sequence → error
14. Target is a flow sequence → error
15. Path doesn't exist → error
