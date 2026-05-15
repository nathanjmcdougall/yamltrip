# yamltrip

[![usethis](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/usethis-python/usethis-python/main/assets/badge/v1.json)](https://github.com/usethis-python/usethis-python) [![PyPI Version](https://img.shields.io/pypi/v/yamltrip.svg)](https://pypi.python.org/pypi/yamltrip) [![PyPI License](https://img.shields.io/pypi/l/yamltrip.svg)](https://github.com/usethis-python/yamltrip?tab=MIT-1-ov-file) [![PyPI Supported Versions](https://img.shields.io/pypi/pyversions/yamltrip.svg)](https://pypi.python.org/pypi/yamltrip)

Edit YAML files from Python, while respecting format and comments during the round-trip.

Built on [tree-sitter-yaml](https://github.com/tree-sitter-grammars/tree-sitter-yaml) via the [yamlpath](https://crates.io/crates/yamlpath) and [yamlpatch](https://crates.io/crates/yamlpatch) Rust crates.

## Installation

```console
# With uv
$ uv add yamltrip

# With pip
$ pip install yamltrip
```

## Quick Start

```python
import yamltrip

# Load and read
doc = yamltrip.loads("name: Alice\nage: 30")
print(doc["name"])       # "Alice"
print("name" in doc)     # True

# Immutable mutations: each call returns a new Document
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

### Top-level function

| Function                   | Description                                    |
| -------------------------- | ---------------------------------------------- |
| `yamltrip.loads(source)` | Parse a YAML string into a `Document`        |
| `yamltrip.load(path)`    | Read a YAML file into a `Document`           |
| `yamltrip.edit(path)`    | Open a YAML file for editing (context manager) |

### Document (immutable)

Every mutation method returns a **new** `Document`. The original is never
modified.

```python
doc = yamltrip.loads("items:\n  - a\n  - b")

doc.root                      # {"items": ["a", "b"]}
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

Wraps `Document` with the same mutation methods, but applies changes in place
and writes back to disk when the context exits cleanly:

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

- **`ParseError`**: YAML input cannot be parsed.
- **`QueryError`**: path not found during lookup.
- **`PatchError`**: mutation operation failed.
  - **`KeyExistsError`**: `add()` target already exists.
  - **`KeyMissingError`**: `replace()` target does not exist.

## Limitations

- **Multi-document YAML streams** (`---` separated) are not supported.
- **YAML tags** (`!!omap`, `!!set`, `!!merge`, custom tags) are not
  interpreted.
- **Anchors and aliases** (`&anchor` / `*alias`) are detected
  (`doc.has_anchors()`) but not resolved during value extraction.
- **Large integers may lose precision.** YAML integers outside the signed
  64-bit range (i64) may become `float` during deserialization.
- **Editor write-back is not atomic.** `Editor` detects external file changes
  between enter and exit, but the check-then-write is racy. Do not use it
  with concurrent writers.

## Design Decisions

- **No custom Python class serialization.** Values convert to/from
  `str`, `int`, `float`, `bool`, `None`, `list`, and `dict` only.
- **UTF-8 only.** Other encodings raise `ParseError`.
- **Non-finite floats round-trip.** `float("inf")`, `float("-inf")`, and
  `float("nan")` map to YAML's `.inf`, `-.inf`, and `.nan`.
- **Integer keys cannot create structures.** `upsert()` with integer path
  components can update existing sequence entries but cannot create new
  intermediate mappings. Only string keys create new mappings.
- **No negative sequence indices.** Python-style negative indexing is not
  supported.
- **Line endings preserved as-is.** No CRLF/LF normalization. Mixed line
  endings pass through unchanged.

## Acknowledgements

yamltrip depends entirely on the [yamlpath](https://github.com/zizmorcore/zizmor/tree/main/crates/yamlpath) and [yamlpatch](https://github.com/zizmorcore/zizmor/tree/main/crates/yamlpatch) Rust crates for format-preserving YAML parsing and patching. These libraries use tree-sitter to query and modify YAML source text without discarding comments, whitespace, or key ordering. All of the core logic in yamltrip
passes through them. Thanks to [William Woodruff](https://github.com/woodruffw) for creating and maintaining both crates as part of [zizmor](https://github.com/zizmorcore/zizmor).

## License

MIT
