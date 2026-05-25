# Design: Deep Merge (`merge()`)

**Date:** 2026-05-22  
**Status:** Approved

## Summary

Add a `merge()` method that recursively merges a value into an existing
mapping without removing keys not present in the target. Lists replace
entirely (list identity is ambiguous); only mapping keys get additive
treatment.

## Semantics

| Current type | Target type | Behavior |
|---|---|---|
| mapping | mapping | Recurse: update matching keys, add new keys, never remove existing keys |
| list | list | Replace the list entirely |
| scalar | mapping | Replace scalar with mapping (promote) |
| mapping | scalar | Replace mapping with scalar |
| any | any (equal) | No-op |
| missing | any | Create path + set value (delegate to `upsert()`) |

Full-depth recursion always. No configurable depth parameter.

## Public API

```python
# Document (immutable, returns new Document)
doc = doc.merge(*keys, value={"debug": False, "timeout": 30})

# Editor (mutable context manager)
with edit("config.yaml") as ed:
    ed.merge("settings", value={"debug": False, "timeout": 30})
```

Signature: `merge(self, *keys: KeyPart, value: Any) -> Document`

Matches `sync()` signature exactly.

## Error behavior

- `NodeTypeError` if path traverses through a scalar/list where a mapping
  is expected
- `PatchError` on Rust-level failures (same fallback as `sync()`)
- No new error types

## Scope

- No new Rust code — reuses existing patch primitives
- No new error types
- `sync()` behavior unchanged
- Available on both `Document` and `Editor`

## Examples

```python
from yamltrip import loads

doc = loads("""
settings:
  debug: true
  log_level: info
  custom_setting: 42
""")

# Merge ensures debug+timeout exist without removing log_level/custom_setting
doc = doc.merge("settings", value={"debug": False, "timeout": 30})

# Result:
# settings:
#   debug: false
#   log_level: info
#   custom_setting: 42
#   timeout: 30
```

```python
# Lists replace entirely
doc = loads("""
plugins:
  - eslint
  - prettier
""")

doc = doc.merge("plugins", value=["stylelint"])

# Result:
# plugins:
#   - stylelint
```

```python
# Nested merge
doc = loads("""
database:
  host: localhost
  credentials:
    user: admin
    password: secret
""")

doc = doc.merge("database", value={"credentials": {"user": "deploy"}, "port": 5432})

# Result:
# database:
#   host: localhost
#   credentials:
#     user: deploy
#     password: secret
#   port: 5432
```

## Testing

- Mapping merge: keeps extra keys, updates matching, adds new
- Nested mapping merge: recurses correctly
- List replacement: lists in target replace entirely
- Scalar-to-mapping promotion: works
- Missing path creation: delegates to upsert
- No-op when values equal: returns same Document instance
- Flow sequence handling: same fallback as sync
- Editor delegation: verify Editor.merge works
