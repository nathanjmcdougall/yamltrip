# Complex Value Support for Replace and Upsert

**Date:** 2026-05-15
**Issue:** #18

## Problem

`Document.replace()` and `Document.upsert()` only accept scalar values. Passing a dict or list raises `PatchError: Patch failed: input is not valid YAML` because yamlpatch's `apply_value_replacement` serializes the value inline after the key colon, producing invalid YAML when the serialized value is multi-line.

`Op.add` and `Op.append` already handle complex values correctly. Only `Op.replace` is broken.

## Approach

Intercept `Replace` operations with complex values (Mapping or Sequence) in yamltrip's Rust layer before they reach yamlpatch. Perform direct string surgery on the document source. Scalar `Replace` and all other operation types pass through to yamlpatch unchanged.

## Change Location

All Rust changes are in `src/document.rs`. No Python API changes. No yamlpatch changes. No new files.

A new function `apply_complex_replace` handles the complex case, called from `PyDocument::apply_patches`.

## Algorithm: `apply_complex_replace`

Input: a `yamlpath::Document`, a `yamlpath::Route`, and a `serde_yaml::Value` (Mapping or Sequence).

1. **Locate the feature** — `document.query_pretty(&route)` to get the byte span with surrounding key context.

2. **Extract content** — `extract_with_leading_whitespace(feature)` to get the full `key: value` text. Split at the first `: ` (colon-space) or `:\n` (colon-newline) into `key_part` (through the colon) and `value_part` (after the colon).

3. **Detect inline comment** — Scan the first line of `value_part` for a trailing `# comment`. Heuristic: after the value content on the first line, find `\s+#`. Save the comment text if found.

4. **Compute indentation** — Derive base indent from the number of leading spaces on the feature's line. Value content indentation = base indent + 2 spaces.

5. **Serialize the new value** — `serde_yaml::to_string(&value)`, strip trailing newline, re-indent each line to the computed value indentation.

6. **Assemble replacement text**:
   - With comment: `key: # comment\n  indented_value`
   - Without comment: `key:\n  indented_value`

7. **String surgery** — Replace the byte range from the feature's span (adjusted for leading whitespace) in the document source.

8. **Re-parse** — `yamlpath::Document::new(patched_source)` to validate.

### Root-level replace

If the route is empty, skip key extraction. Replace the entire document content with the serialized value. This matches yamlpatch's existing root-replace behavior.

## Patch Routing in `apply_patches`

In `PyDocument::apply_patches`, before building the `Vec<yamlpatch::Patch>`:

```
for each patch:
  if patch.operation is Replace(value) AND value is Mapping or Sequence:
    apply_complex_replace(document, route, value)
    re-parse document for subsequent patches
  else:
    collect into yamlpatch batch
```

Patches are applied sequentially. If a complex replace is encountered mid-batch, the preceding yamlpatch batch is flushed first, then the complex replace is applied, then the next batch starts from the updated document.

## How Upsert Benefits

`Document.upsert()` delegates to `replace()` when the path exists, and to `_create_at()` (which uses `Op.add`/`Op.merge_into`) when it doesn't. Since `Op.add` and `Op.merge_into` already handle complex values, the only broken path is the `replace` delegation — fixed by this change. No changes to `document.py`.

## Comment Relocation

When replacing a scalar that has an inline comment (e.g. `repos: [] # managed by tool`) with a multi-line block value:

- The comment is preserved on the key line: `repos: # managed by tool`
- The block value starts on the next line, indented

Detection heuristic: after stripping the YAML value from the first line of `value_part`, look for `\s+#` at the end.

**Limitation:** Comments inside quoted strings that happen to contain `#` could be misdetected. This is unlikely for the scalar values being replaced and is documented as a known limitation.

## Serialization Style

No changes to `Op.add` behavior. Complex values in `Replace` use `serde_yaml::to_string()` which produces block style by default (block mappings, block sequences). This matches the pre-commit config use case where block style is expected.

## Testing

New tests in `tests/test_document.py`:

- `replace()` with a dict value
- `replace()` with a list value
- `replace()` with nested dict-in-list-in-dict
- `upsert()` with a dict value (path exists → goes through replace)
- `upsert()` with a dict value (path doesn't exist → goes through add, already works)
- Comment preservation when replacing scalar with complex value
- Replacing a complex value with another complex value
- Root-level replace with complex value
- Indentation correctness at various nesting depths (0, 2, 4 spaces)

## Scope Boundaries

**In scope:**
- `Replace` with Mapping/Sequence values
- Inline comment relocation
- Indentation handling

**Out of scope:**
- Changing `Add`/`Append` serialization style
- Multi-document YAML support
- Tagged values
- Flow-style output preference (uses serde_yaml default block style)
