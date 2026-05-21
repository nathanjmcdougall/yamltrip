# Support Mutations on Empty Documents

**Date:** 2026-05-22
**Issue:** #34

## Problem

Mutation methods that create structure (`upsert`, `add`, `sync`) raise `PatchError` when called on a document with no root data node:

```python
doc = yamltrip.loads("")
doc.upsert("x", value=1)
# PatchError: YAML query error: syntax node 'stream' is missing named child 'document'
```

The underlying yamlpatch `Add` operation requires an existing mapping node at the target route. This forces callers to use a sentinel workaround.

## Scope

"Empty document" means any document with no root data node:
- Zero-length source (`""`)
- Whitespace-only source (`"  \n"`)
- Comment-only source (`"# header\n"`)

Integer keys on empty documents still error — consistent with existing behaviour. Only string keys can bootstrap a root mapping.

## Design decisions

### Detection

Check whether the root route resolves to a data node. If it doesn't, the document is "empty" for our purposes. This covers all three cases above uniformly.

### New Rust capability: `_core.serialize_value()`

Expose a function that takes a Python value and returns YAML text via `serde_yaml`. This gives the Python layer a direct serialization path without constructing throwaway documents. Uses the existing `py_to_yaml_value` conversion.

### Bootstrap strategy

When a mutation targets an empty document and needs to create structure:
1. Build the nested Python dict representing the full key path + value
2. Serialize it to YAML text via `serialize_value`
3. Concatenate with existing source content (preserving comments) 
4. Re-parse into a new Document

This is the same cost as any other mutation (every patch application ends with a re-parse).

### Comment preservation

When the document is comment-only, the existing source is preserved as a prefix above the new content.

### Per-method behaviour on empty documents

| Method | Behaviour on empty doc |
|--------|----------------------|
| `upsert` | Creates root mapping (bootstrap) |
| `sync` | Delegates to `upsert` (existing path) |
| `add` | Creates root mapping (bootstrap) |
| `replace` | `KeyMissingError` (correct — nothing to replace) |
| `append` / `insert` / `extend_list` | `PatchError` (correct — no sequence) |
| `remove` | `PatchError` (correct — nothing to remove) |

## Expected behaviour

```python
# Basic
Document("").upsert("x", value=1)["x"] == 1

# Nested keys
Document("").upsert("a", "b", value="hello")["a", "b"] == "hello"

# Comment preservation
doc = Document("# header\n").upsert("x", value=1)
doc.source.startswith("# header\n")  # True

# add() works too
Document("").add(key="name", value="foo")["name"] == "foo"

# Integer keys still error
Document("").upsert(0, value="x")  # raises PatchError

# Complex values
Document("").upsert("items", value=["a", "b", "c"])["items"] == ["a", "b", "c"]
```

## Non-goals

- Creating root sequences via integer keys
- Modifying yamlpatch to handle empty documents internally
- Changing the Rust `apply_patches_impl` flow
