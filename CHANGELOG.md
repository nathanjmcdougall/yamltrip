# Changelog

## 0.5.0

### Features

- `append()`, `insert()`, `extend_list()`, and `sync()` now handle flow sequences (e.g. `[a, b, c]`), which previously raised `PatchError`. They fall back to replacing the sequence value, including recursive detection of flow sequences nested inside list elements.
- Added `NodeTypeError(PatchError, TypeError)` to the error hierarchy. Sequence-mutating operations (`append`, `insert`, `extend_list`, `remove_from_list`) now raise `NodeTypeError` instead of generic errors when the target node is not a sequence.

## 0.4.0

### Features

- Added `Document.insert()` and `Editor.insert()` for inserting an item at a specific position in a sequence. Uses Python `list.insert()` semantics (negative indices count from end, out-of-range clamps).
- Added `Document.get()` and `Editor.get()` for non-raising value access. This returns a default (defaults to `None`) when the path doesn't exist, similar to `dict.get()`.
- Added `Document.sync()` and `Editor.sync()` that diffs the current value at a path against a desired value and applies the minimal set of patches. Supports recursive mapping diffing and `SequenceMatcher`-based list diffing to preserve comments and formatting on unchanged elements.

### Internal

- Introduced `OpInner` enum in Rust to support local ops (like `insert_at`) alongside yamlpatch-delegated operations.
- Extracted `KeyPart` type alias to `_types.py`.

## 0.3.0

### Features

- `replace` and `upsert` now accept dicts and lists as values, not just scalars. Complex values are serialized to block-style YAML and spliced in via string surgery, bypassing yamlpatch's scalar-only limitation.
- Added `root` property to `Document` and `Editor` as a convenience for `doc[()]`.

### Internal

- Added cargo-fmt and clippy pre-commit hooks, aligned with CI.
- Simplified complex-replace internals to match yamlpatch behavior (removed quote-aware colon finding and inline comment preservation).

### Documentation

- Fixed usethis badge path in README.

## 0.2.0

### Features

- Non-finite floats (NaN, Inf, -Inf) now round-trip. Previously, reading a YAML `.nan`/`.inf`/`-.inf` value and writing it back raised `ValueError`.

### Packaging

- Added `License :: OSI Approved :: MIT License` trove classifier to pyproject.toml.

### Documentation

- Line-ending normalization (LF on output regardless of input) moved from "Limitations" to "Design Decisions" in the README.

### Internal

- Added cargo-deny license compliance checking.
- Extended cargo-deny to also check security advisories against the RustSec database.

## 0.1.0

Initial release. yamltrip is a round-tripping YAML library for Python.
