# Changelog

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
