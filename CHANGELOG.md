# Changelog

## 0.2.0

### Features

- Non-finite floats (NaN, Inf, -Inf) now round-trip. Previously, reading a YAML `.nan`/`.inf`/`-.inf` value and writing it back raised `ValueError`.

### Packaging

- Added `License :: OSI Approved :: MIT` License trove classifier to pyproject.toml.

### Documentation

- Line-ending normalization (LF on output regardless of input) moved from "Limitations" to "Design Decisions" in the README.

### Internal

- Added cargo-deny license compliance checking.
- Extended cargo-deny to also check security advisories against the RustSec database.

## 0.1.0

Initial release. yamltrip is a round-tripping YAML library for Python.
