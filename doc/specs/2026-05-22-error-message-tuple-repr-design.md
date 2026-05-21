# Design: Human-Readable Path Formatting in NodeTypeError Messages

**Date:** 2026-05-22
**Status:** Approved

## Problem

`NodeTypeError` messages interpolate raw Python tuples into error strings:

```python
msg = f"Value at {keys} is not a list"
# Produces: "Value at ('repos',) is not a list"
```

The tuple syntax (`('repos',)`) is implementation noise that leaks internal representation to users.

## Solution

Introduce a `format_path` helper in a new `_display.py` module that converts key tuples to a human-readable path string using ` > ` as separator.

### Output Examples

| Input | Output |
|-------|--------|
| `('repos',)` | `repos` |
| `('repos', 0, 'steps')` | `repos > 0 > steps` |
| `()` | `<root>` |

### Separator Choice: ` > ` (ASCII arrow)

- Unambiguous: no YAML key naturally contains ` > `
- Works in all terminals and log viewers (no UTF-8 issues)
- Easy to grep and type
- Reads naturally as "drill into"

## New Module: `src/yamltrip/_display.py`

Single function:

```python
def format_path(keys: tuple[str | int, ...]) -> str:
    if not keys:
        return "<root>"
    return " > ".join(str(k) for k in keys)
```

## Affected Call Sites (3)

All in `src/yamltrip/document.py`, all with the same pattern:

1. `remove_from_list` — type-checks retrieved value is a list
2. `ensure_in_list` — type-checks retrieved value is a list
3. `find_index` — type-checks retrieved value is a list

Each changes from:
```python
msg = f"Value at {keys} is not a list"
```
To:
```python
msg = f"Value at {format_path(keys)} is not a list"
```

## Out of Scope

- Rust-originating error messages (lines that use `msg = str(e)`) — these come from the Rust layer and don't contain tuple repr.
- Reformatting other exception types.

## Testing

- Unit test for `format_path` covering: single key, multi-key, integer indices, empty tuple.
- Update any existing tests that assert on `NodeTypeError` message content.
