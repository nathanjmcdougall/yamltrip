# yamltrip Design Spec

**Date:** 2026-05-13
**Status:** Draft

## Overview

yamltrip is a round-tripping YAML library for Python, backed by Rust. It wraps
the `yamlpath` and `yamlpatch` crates (from the zizmor project) via PyO3 to
provide comment-, quote-, and indentation-preserving YAML editing.

### Goals

- General-purpose YAML library for Python with first-class round-trip support.
- Replace ruamel.yaml for config-editing use cases with better preservation
  guarantees and a simpler API.
- Rust-powered performance with a Pythonic interface.

### Non-goals (v0.1)

- Multi-document YAML streams (`---` delimiters).
- Full YAML data model (tagged types, `!!omap`, `!!set`, `!!merge`).
- Custom Python class serialization/deserialization.
- YAML emitter controls (flow style, colon alignment, etc.) — not needed since
  the original formatting is preserved.

## Architecture

Two layers:

### Layer 1: `yamltrip._core` (Rust / PyO3)

Direct wrappings of yamlpath + yamlpatch types:

| Rust Type | Python `_core` Class | Purpose |
|---|---|---|
| `yamlpath::Document` | `_core.Document` | Parse YAML, hold tree-sitter state |
| `yamlpath::Route` | `_core.Route` | Path into a YAML document |
| `yamlpath::Component` | `_core.Component` | Single route segment (Key or Index) |
| `yamlpath::Feature` | `_core.Feature` | Query result with location/span info |
| `yamlpath::Location` | `_core.Location` | Byte offset span (start, end) |
| `yamlpath::FeatureKind` | `_core.FeatureKind` | Enum: BlockMapping, FlowMapping, BlockSequence, FlowSequence, Scalar |
| `yamlpatch::Patch` | `_core.Patch` | Route + Op pair |
| `yamlpatch::Op` | `_core.Op` | Enum with static constructors |
| `yamlpatch::apply_yaml_patches` | `_core.apply_patches()` | Apply patches to YAML string |

### Layer 2: `yamltrip` (pure Python)

High-level Pythonic API built on `_core`:

- `Document` — immutable YAML document value object.
- `Editor` — mutable context manager for file editing.
- `loads()` / `load()` / `edit()` — module-level constructors.
- `Feature`, `Location`, `FeatureKind` — re-exported from `_core`.
- Error types.

## API

### Construction

```python
import yamltrip

doc = yamltrip.loads("name: foo\nitems:\n  - a\n  - b")
doc = yamltrip.load("config.yml")
```

### Document (immutable)

Each mutation method returns a new `Document`. The original is never modified.

```python
class Document:
    source: str   # current YAML text
```

#### Querying

Returns Python primitives (str, int, float, bool, None, list, dict).

```python
doc["name"]            # → "foo"
doc["items", 0]        # → "a"
("name",) in doc       # → True
("missing",) in doc    # → False
```

`__getitem__` accepts a single key or a tuple of keys. Each key is `str` (mapping
key) or `int` (sequence index). Raises `QueryError` if the path doesn't exist.
Python's `__getitem__` naturally handles both: `doc["name"]` receives `"name"`,
`doc["a", "b"]` receives `("a", "b")`. The implementation normalizes single keys
to 1-tuples.

`__contains__` accepts a tuple of keys. Returns `False` for missing paths (never
raises).

#### Patch Operations

All return a new `Document`.

| Method | Behavior |
|---|---|
| `replace(*keys, value=...)` | Replace value at existing path. Raises `KeyMissingError` if path doesn't exist. |
| `add(*keys, key=..., value=...)` | Add a new key-value pair to the mapping at path. Raises `KeyExistsError` if key already exists. |
| `upsert(*keys, value=...)` | Replace if path exists, create (including intermediate mappings) if not. Never raises for missing/existing keys. |
| `remove(*keys, prune=False)` | Remove key or index at path. If `prune=True`, also removes parent mappings/sequences that become empty, bottom-up. |
| `prune_remove(*keys)` | Convenience for `remove(*keys, prune=True)`. |
| `append(*keys, value=...)` | Append a single item to the sequence at path. |
| `extend_list(*keys, values=[...])` | Append multiple items to the sequence at path. |
| `remove_from_list(*keys, values=[...])` | Remove all occurrences of the given values from the sequence at path. |

##### `upsert()` behavior

`upsert(*keys, value=...)` handles three cases internally:

1. **Full path exists:** delegates to `replace()`.
2. **Partial path exists:** walks down to the deepest existing key, then uses
   yamlpatch `MergeInto` for flat mapping values (scalar-only entries) or a
   two-step `Add` placeholder + `Replace` for nested values (dicts/lists inside
   the value). `MergeInto` uses uniform-indent serialization that only handles
   one nesting level; the `Replace` path routes through complex-replace which
   preserves relative indentation at arbitrary depth.
3. **No path exists:** uses yamlpatch `Add` with a nested value to create the
   entire path in a single operation.

This is implemented in the Python layer using existing yamlpatch operations.

##### `upsert()` with no keys (root-level)

`doc.upsert(value={"a": 1})` with no path keys replaces the entire root document
content. The value must be a mapping.

##### `remove_from_list()` implementation

`remove_from_list(*keys, values=[...])` is implemented in the Python layer:

1. Query the sequence at `*keys` to get its current contents.
2. Find the indices of all elements matching any value in `values`.
3. Remove those indices in reverse order (highest first) using yamlpatch
   `Op::Remove`, each with a `Route` targeting the specific index.

This ensures index stability during removal.

##### `prune_remove()` / `remove(prune=True)` behavior

After removing the targeted key:

1. Walk back up the key path from deepest to shallowest.
2. At each level, check if the parent mapping/sequence is now empty.
3. If empty, remove it too.
4. Stop at the first non-empty parent.

Implemented in the Python layer as a loop of `remove()` + `__contains__` checks.

#### Inspection

```python
feature = doc.query(*keys)     # → Feature with location info
text = doc.extract(feature)    # → raw text from source at feature's span
```

#### Output

```python
doc.dumps() -> str              # return YAML string
doc.dump("config.yml")          # write to file
```

### Editor (mutable context manager)

```python
with yamltrip.edit("config.yml") as editor:
    # Attributes
    editor.original        # → Document snapshot from file load (never changes)
    editor.document        # → current patched Document (updates after each op)

    # All Document patch methods are available directly:
    editor.replace("name", value="bar")
    editor.add("settings", key="debug", value=True)
    editor.upsert("timeout", value=30)
    editor.remove("old_key")
    editor.prune_remove("section", "subsection", "key")
    editor.remove("other", prune=True)
    editor.append("items", value="new")
    editor.extend_list("items", values=["c", "d"])
    editor.remove_from_list("items", values=["a"])

    # __getitem__ queries current patched state
    editor["name"]                       # → "bar"
    ("settings", "debug") in editor      # → True

    # __setitem__ calls upsert
    editor["name"] = "baz"
    editor["nested", "key"] = "val"

    # Can also query original
    editor.original["name"]              # → "foo" (original state)

# File is written on successful __exit__
# NOT written if an exception occurs
```

#### Editor semantics

- Each patch method mutates `editor.document` in place (internally replacing it
  with the new `Document` returned by the operation).
- `editor.original` is set once on `__enter__` and never modified.
- `__getitem__` delegates to `editor.document.__getitem__`.
- `__contains__` delegates to `editor.document.__contains__`.
- `__setitem__` delegates to `upsert()`. Python's `__setitem__` passes a single
  key or tuple; the Editor normalizes to a tuple before calling `upsert()`.
- `__exit__` writes `editor.document.dumps()` to the file path only if no
  exception occurred. The file is written as UTF-8.

### Feature / Location / FeatureKind

```python
class Feature:
    location: Location
    context: Location | None
    kind: FeatureKind
    is_multiline: bool
    def parent(self) -> Feature | None

class Location:
    start: int    # byte offset
    end: int      # byte offset

class FeatureKind(Enum):
    BLOCK_MAPPING = ...
    FLOW_MAPPING = ...
    BLOCK_SEQUENCE = ...
    FLOW_SEQUENCE = ...
    SCALAR = ...
```

### Errors

```python
class YAMLTripError(Exception): ...
class ParseError(YAMLTripError): ...         # invalid YAML input
class QueryError(YAMLTripError): ...         # path not found during query
class PatchError(YAMLTripError): ...         # patch operation failed
class KeyExistsError(PatchError): ...        # add() when key already exists
class KeyMissingError(PatchError): ...       # replace() when key doesn't exist
```

## Mapping to Upstream Crate Operations

| yamltrip method | yamlpatch `Op` | Notes |
|---|---|---|
| `replace()` | `Op::Replace(value)` | |
| `add()` | `Op::Add { key, value }` | |
| `upsert()` | `Replace`, `Add`, or `MergeInto` | Smart dispatch in Python layer |
| `remove()` | `Op::Remove` | |
| `prune_remove()` | Multiple `Op::Remove` | Python loop |
| `append()` | `Op::Append { value }` | |
| `extend_list()` | Multiple `Op::Append` | One per value |
| `remove_from_list()` | Query + multiple `Op::Remove` | Find matching indices, remove each |

## Rust `_core` Bindings Detail

### `_core.Document`

Wraps `yamlpath::Document`. Constructed from a YAML string.

```python
doc = _core.Document("name: foo")
doc.source()                    # → "name: foo"
doc.query_exact(route)          # → Feature | None
doc.query_pretty(route)         # → Feature
doc.query_key_only(route)       # → Feature
doc.query_exists(route)         # → bool
doc.extract(feature)            # → str
doc.extract_with_leading_whitespace(feature)  # → str
doc.feature_comments(feature)   # → list[Feature]
doc.has_anchors()               # → bool
doc.top_feature()               # → Feature
```

### `_core.Route`

Wraps `yamlpath::Route`. Constructed from a list of components.

```python
route = _core.Route(["name"])              # single key
route = _core.Route(["items", 0])          # key + index
route = _core.Route(["a", "b", "c"])       # nested keys
```

### `_core.Op`

Wraps `yamlpatch::Op`. Static constructors for each variant.

```python
_core.Op.replace(value)
_core.Op.add(key, value)
_core.Op.remove()
_core.Op.append(value)
_core.Op.merge_into(key, updates)
_core.Op.replace_comment(new)
_core.Op.emplace_comment(new)
_core.Op.rewrite_fragment(from_, to)
```

### `_core.apply_patches`

Wraps `yamlpatch::apply_yaml_patches`.

```python
new_source = _core.apply_patches(source_str, patches)
# patches: list[_core.Patch]
# each Patch has: route (_core.Route) + operation (_core.Op)
```

## File Handling

- All file I/O uses UTF-8 encoding (YAML spec default).
- `load(path)` raises `FileNotFoundError` if the file doesn't exist.
- `edit(path)` raises `FileNotFoundError` if the file doesn't exist. It is not
  a file-creation tool — use `loads("")` + `dump(path)` to create new files.
- `dump(path)` creates the file if it doesn't exist, overwrites if it does.

## Scope Constraints (v0.1)

- Python >= 3.10 (PyO3 abi3-py310).
- Single-document YAML only.
- File I/O included (load/dump/edit).
- MIT license (matching upstream crates).

## Dependencies

### Rust (Cargo.toml)

- `pyo3` (existing)
- `yamlpath` (crates.io)
- `yamlpatch` (crates.io)
- `serde_yaml` (for value conversion at the boundary)

### Python

- No runtime Python dependencies beyond the compiled `_core` extension.

## Testing Strategy

- Unit tests for each `_core` binding (Rust types exposed correctly).
- Unit tests for each `Document` method (Python layer).
- Unit tests for `Editor` context manager (file write semantics, error handling).
- Round-trip property tests: load YAML → apply operations → verify comments,
  quotes, indentation preserved.
- Integration tests comparing yamltrip output with expected YAML for real-world
  config files (GitHub Actions, pre-commit, pyproject.toml-adjacent YAML).
