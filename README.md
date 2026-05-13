# yamltrip

A round-tripping YAML library for Python. Edit YAML files while preserving
comments, formatting, and key ordering.

Built on [tree-sitter-yaml](https://github.com/tree-sitter-grammars/tree-sitter-yaml)
via the [yamlpath](https://crates.io/crates/yamlpath) and
[yamlpatch](https://crates.io/crates/yamlpatch) Rust crates, with Python
bindings through [PyO3](https://pyo3.rs).

## Installation

```
pip install yamltrip
```

Requires Python 3.10+. Distributed as pre-built wheels (no Rust toolchain
needed at install time).

## Quick Start

```python
import yamltrip

# Load and read
doc = yamltrip.loads("name: Alice\nage: 30")
print(doc["name"])       # "Alice"
print("name" in doc)     # True

# Immutable mutations — each returns a new Document
doc2 = doc.replace("age", value=31)
doc3 = doc2.add(key="city", value="Portland")
print(doc3.dumps())

# File-based editing with a context manager
with yamltrip.edit("config.yml") as editor:
    editor.replace("version", value="2.0")
    editor.upsert("settings", "debug", value=True)
    # writes back on successful exit; discards on exception
```

## API Overview

### Top-level functions

| Function | Description |
|---|---|
| `yamltrip.loads(source)` | Parse a YAML string into a `Document` |
| `yamltrip.load(path)` | Read a YAML file into a `Document` |
| `yamltrip.edit(path)` | Open a YAML file for editing (context manager) |

### Document (immutable)

Each mutation method returns a **new** `Document` — the original is never
modified.

```python
doc = yamltrip.loads("items:\n  - a\n  - b")

doc["items"]                  # ["a", "b"]
doc["items", 0]               # "a"
("items", 0) in doc           # True

doc.replace("items", 0, value="x")
doc.add("items", key="c", value=3)
doc.upsert("new", "nested", value=True)
doc.remove("items", 0)
doc.prune_remove("a", "b", "c")  # remove + prune empty parents
doc.append("items", value="c")
doc.extend_list("items", values=["d", "e"])
doc.remove_from_list("items", values=["a"])

doc.query("items")            # Feature with location info
doc.query_pretty("items")    # Feature with surrounding context
doc.extract(feature)          # raw YAML text for a Feature
doc.has_anchors()             # True if anchors/aliases present
doc.dumps()                   # full YAML source
doc.dump("output.yml")        # write to file
```

### Editor (mutable context manager)

Wraps `Document` with the same methods, but mutates in place and writes back
to disk on successful context exit:

```python
with yamltrip.edit("config.yml") as ed:
    ed.replace("version", value="2.0")
    ed.upsert("new_key", value="new_value")
    ed.remove("old_key")
    print(ed["version"])        # "2.0"
    print(ed.original["version"])  # original value before edits
```

### Error Hierarchy

All yamltrip errors inherit from `YAMLTripError`:

- **`ParseError`** — YAML input cannot be parsed
- **`QueryError`** — path not found during lookup
- **`PatchError`** — mutation operation failed
  - **`KeyExistsError`** — `add()` target already exists
  - **`KeyMissingError`** — `replace()` target doesn't exist

## Limitations

- **Multi-document YAML streams** (`---` separated) are not supported —
  behavior is undefined.
- **YAML tags** (`!!omap`, `!!set`, `!!merge`, custom tags) are not
  interpreted.
- **Anchors and aliases** (`&anchor` / `*alias`) are detected
  (`doc.has_anchors()`) but not resolved during value extraction.
- **No custom Python class serialization** — values are converted to/from
  basic Python types (`str`, `int`, `float`, `bool`, `None`, `list`, `dict`).

## Development

```bash
# Install dev dependencies
uv sync

# Build and test
uv run pytest

# Lint
uv run ruff check
uv run ruff format --check
```

## License

MIT
