use pyo3::prelude::*;

use crate::ops::{LocalOp, OpInner, PyPatch};
use crate::types::{PyFeature, PyFeatureKind, PyLocation, PyRoute};

/// A parsed YAML document.
#[pyclass(name = "Document", module = "yamltrip._core")]
pub struct PyDocument {
    inner: yamlpath::Document,
}

#[pymethods]
impl PyDocument {
    #[new]
    fn new(source: &str) -> PyResult<Self> {
        let doc = yamlpath::Document::new(source).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to parse YAML: {e}"))
        })?;
        Ok(Self { inner: doc })
    }

    fn source(&self) -> &str {
        self.inner.source()
    }

    fn query_exists(&self, route: &PyRoute) -> bool {
        let r = route.to_yamlpath_route();
        self.inner.query_exists(&r)
    }

    fn query_exact(&self, route: &PyRoute) -> PyResult<Option<PyFeature>> {
        let r = route.to_yamlpath_route();
        match self.inner.query_exact(&r) {
            Ok(Some(feature)) => Ok(Some(convert_feature(&feature))),
            Ok(None) => Ok(None),
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Query failed: {e}"
            ))),
        }
    }

    fn query_pretty(&self, route: &PyRoute) -> PyResult<PyFeature> {
        let r = route.to_yamlpath_route();
        match self.inner.query_pretty(&r) {
            Ok(feature) => Ok(convert_feature(&feature)),
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Query failed: {e}"
            ))),
        }
    }

    fn extract(&self, feature: &PyFeature) -> PyResult<String> {
        let source = self.inner.source();
        let start = feature.location.start;
        let end = feature.location.end;
        if end > source.len() || start > end {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Feature location is out of bounds",
            ));
        }
        source
            .get(start..end)
            .map(|s| s.to_string())
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Feature location is not aligned to UTF-8 character boundaries",
                )
            })
    }

    fn has_anchors(&self) -> bool {
        self.inner.has_anchors()
    }

    /// Parse the YAML value at a route and return it as a Python object.
    fn parse_value(&self, py: Python<'_>, route: &PyRoute) -> PyResult<Py<PyAny>> {
        let source = self.inner.source();
        let r = route.to_yamlpath_route();

        if !self.inner.query_exists(&r) {
            return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Path not found",
            ));
        }

        // For root-level, parse entire document.
        // Note: tree-sitter gives us the AST structure, but not parsed scalar
        // values, so we extract the raw YAML substring and re-parse it with
        // serde_yaml. The dedenting is needed because serde_yaml expects
        // root-level indentation.
        let yaml_str = if route.components.is_empty() {
            source.to_string()
        } else {
            match self.inner.query_exact(&r) {
                Ok(Some(feature)) => {
                    let span = feature.location.byte_span;
                    // Note: span.0 <= span.1 is guaranteed by tree-sitter node
                    // ranges, so we only check bounds and UTF-8 alignment.
                    if span.1 > source.len()
                        || !source.is_char_boundary(span.0)
                        || !source.is_char_boundary(span.1)
                    {
                        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                            "Feature span is not valid in source",
                        ));
                    }
                    let raw = &source[span.0..span.1];
                    // Calculate the column offset (in bytes) of the value
                    // start relative to the beginning of its line, so we can
                    // dedent continuation lines.
                    let line_start = source[..span.0].rfind('\n').map(|nl| nl + 1).unwrap_or(0);
                    let col = span.0 - line_start;
                    if col == 0 {
                        raw.to_string()
                    } else {
                        raw.split('\n')
                            .enumerate()
                            .map(|(i, line)| {
                                if i == 0 {
                                    line.to_string()
                                } else if line.len() >= col
                                    && line.as_bytes()[..col].iter().all(|&b| b == b' ')
                                {
                                    line[col..].to_string()
                                } else {
                                    line.to_string()
                                }
                            })
                            .collect::<Vec<_>>()
                            .join("\n")
                    }
                }
                Ok(None) => return Ok(py.None()),
                Err(e) => {
                    return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                        "Query error: {e}"
                    )));
                }
            }
        };

        let value: serde_yaml::Value = serde_yaml::from_str(&yaml_str).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("YAML parse error: {e}"))
        })?;

        crate::convert::yaml_value_to_py(py, &value)
    }

    /// Apply patches to this document and return a new document.
    fn apply_patches(&self, patches: Vec<PyPatch>) -> PyResult<Self> {
        let doc = apply_patches_impl(&self.inner, &patches).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Patch failed: {e}"))
        })?;
        Ok(Self { inner: doc })
    }
}

/// Shared patch-application logic used by both PyDocument::apply_patches and ops::apply_patches.
///
/// Patches are applied in order. Complex replaces (Mapping/Sequence values) are handled via
/// direct string surgery; all other operations are batched and passed to yamlpatch.
///
/// Routes are symbolic paths (key names / sequence indices), not byte offsets, so they remain
/// valid across complex replaces that restructure sibling values. This is the same sequential
/// semantics yamlpatch uses internally when applying multiple patches.
pub(crate) fn apply_patches_impl(
    doc: &yamlpath::Document,
    patches: &[PyPatch],
) -> Result<yamlpath::Document, String> {
    let mut current_doc = doc.clone();
    let mut batch: Vec<usize> = Vec::new();

    for (idx, patch) in patches.iter().enumerate() {
        let needs_direct_handling = match &patch.operation.inner {
            OpInner::Yamlpatch(yamlpatch::Op::Replace(v)) => {
                matches!(
                    v,
                    serde_yaml::Value::Mapping(_) | serde_yaml::Value::Sequence(_)
                )
            }
            OpInner::Local(_) => true,
            _ => false,
        };

        if needs_direct_handling {
            // Flush any pending yamlpatch batch first
            if !batch.is_empty() {
                let yaml_patches: Vec<yamlpatch::Patch<'_>> = batch
                    .iter()
                    .filter_map(|&i| {
                        patches[i]
                            .operation
                            .as_yamlpatch_op()
                            .map(|op| yamlpatch::Patch {
                                route: patches[i].route.to_yamlpath_route(),
                                operation: op.clone(),
                            })
                    })
                    .collect();
                current_doc = yamlpatch::apply_yaml_patches(&current_doc, &yaml_patches)
                    .map_err(|e| e.to_string())?;
                batch.clear();
            }

            let route = patch.route.to_yamlpath_route();
            match &patch.operation.inner {
                OpInner::Yamlpatch(yamlpatch::Op::Replace(value)) => {
                    current_doc = apply_complex_replace(&current_doc, &route, value)?;
                }
                OpInner::Local(LocalOp::InsertAt { index, value }) => {
                    current_doc = apply_insert_at(&current_doc, &route, *index, value)?;
                }
                _ => unreachable!(),
            }
        } else {
            batch.push(idx);
        }
    }

    // Flush remaining batch
    if !batch.is_empty() {
        let yaml_patches: Vec<yamlpatch::Patch<'_>> = batch
            .iter()
            .filter_map(|&i| {
                patches[i]
                    .operation
                    .as_yamlpatch_op()
                    .map(|op| yamlpatch::Patch {
                        route: patches[i].route.to_yamlpath_route(),
                        operation: op.clone(),
                    })
            })
            .collect();
        current_doc = yamlpatch::apply_yaml_patches(&current_doc, &yaml_patches)
            .map_err(|e| e.to_string())?;
    }

    Ok(current_doc)
}

fn apply_insert_at(
    doc: &yamlpath::Document,
    route: &yamlpath::Route<'_>,
    index: i64,
    value: &serde_yaml::Value,
) -> Result<yamlpath::Document, String> {
    let source = doc.source();

    // 1. Query the sequence feature and verify it's a block sequence
    let feature = doc
        .query_exact(route)
        .map_err(|e| format!("Query failed: {e}"))?
        .ok_or_else(|| "insert_at: sequence not found at route".to_string())?;

    if feature.kind() != yamlpath::FeatureKind::BlockSequence {
        return Err(format!(
            "insert_at: expected BlockSequence, got {:?}",
            feature.kind()
        ));
    }

    // 2. Count items in the sequence
    let mut len: i64 = 0;
    loop {
        let item_route = route.with_key(yamlpath::Component::Index(len as usize));
        if !doc.query_exists(&item_route) {
            break;
        }
        len += 1;
    }

    // 3. Resolve index with Python list.insert semantics
    let resolved = if index < 0 {
        0i64.max(len + index)
    } else {
        index.min(len)
    } as usize;

    // 4. Delegate to append if inserting at the end
    if resolved as i64 == len {
        let patch = yamlpatch::Patch {
            route: route.clone(),
            operation: yamlpatch::Op::Append {
                value: value.clone(),
            },
        };
        return yamlpatch::apply_yaml_patches(doc, &[patch]).map_err(|e| e.to_string());
    }

    // 5. Locate insertion byte position
    let item_route = route.with_key(yamlpath::Component::Index(resolved));
    let item_feature = doc
        .query_exact(&item_route)
        .map_err(|e| format!("Query failed: {e}"))?
        .ok_or_else(|| format!("insert_at: item at index {resolved} not found"))?;

    let item_start = item_feature.location.byte_span.0;
    // Note: no reversed-span check needed; tree-sitter nodes guarantee start <= end.
    if item_start > source.len() || !source.is_char_boundary(item_start) {
        return Err("Feature span is not valid in source".to_string());
    }
    let line_start = source[..item_start]
        .rfind('\n')
        .map(|nl| nl + 1)
        .unwrap_or(0);

    // 6. Determine indentation from the existing item's line prefix
    let prefix = &source[line_start..item_start];
    let dash_pos = prefix.find('-').unwrap_or(prefix.len());
    let base_indent = &prefix[..dash_pos];

    // 7. Serialize new value as a sequence item
    let serialized =
        serde_yaml::to_string(value).map_err(|e| format!("Failed to serialize YAML: {e}"))?;
    let trimmed = serialized.trim_end_matches('\n');

    let mut item_text = String::new();
    for (i, line) in trimmed.lines().enumerate() {
        if i == 0 {
            item_text.push_str(base_indent);
            item_text.push_str("- ");
            item_text.push_str(line);
        } else {
            item_text.push('\n');
            item_text.push_str(base_indent);
            item_text.push_str("  ");
            item_text.push_str(line);
        }
    }
    item_text.push('\n');

    // 8. String splice — insert before the target item's line
    let mut result = source.to_string();
    result.insert_str(line_start, &item_text);

    // 9. Re-parse to validate
    yamlpath::Document::new(result).map_err(|e| format!("Failed to re-parse YAML: {e}"))
}

fn apply_complex_replace(
    doc: &yamlpath::Document,
    route: &yamlpath::Route<'_>,
    value: &serde_yaml::Value,
) -> Result<yamlpath::Document, String> {
    let source = doc.source();

    // Root-level replace: just serialize the entire value
    if route.is_empty() {
        let serialized =
            serde_yaml::to_string(value).map_err(|e| format!("Failed to serialize YAML: {e}"))?;
        return yamlpath::Document::new(serialized)
            .map_err(|e| format!("Failed to re-parse YAML: {e}"));
    }

    // Locate the feature (with key context)
    let feature = doc
        .query_pretty(route)
        .map_err(|e| format!("Query failed: {e}"))?;

    let span = feature.location.byte_span;
    // Note: span.0 <= span.1 is guaranteed by tree-sitter node ranges,
    // so we only check bounds and UTF-8 alignment.
    if span.1 > source.len() || !source.is_char_boundary(span.0) || !source.is_char_boundary(span.1)
    {
        return Err("Feature span is not valid in source".to_string());
    }

    let content_with_ws = doc.extract_with_leading_whitespace(&feature);
    let content = doc.extract(&feature);

    // Calculate the start byte including leading whitespace.
    // Safety: ws_len <= byte_span.0 because extract_with_leading_whitespace only
    // extends backward to the last newline (or start of document), never beyond byte_span.0.
    let ws_len = content_with_ws.len() - content.len();
    let start_byte = feature.location.byte_span.0 - ws_len;
    let end_byte = feature.location.byte_span.1;

    // Use query_exact to locate the value's byte span independently.
    // This avoids string-searching for the colon separator, which breaks
    // on quoted keys containing colons (e.g. "http://example.com": 8080).
    let value_feature = doc
        .query_exact(route)
        .map_err(|e| format!("Query failed: {e}"))?;

    let key_part = match value_feature {
        Some(vf) => {
            let vf_start = vf.location.byte_span.0;
            // Note: no reversed-span check needed; tree-sitter nodes guarantee start <= end.
            if vf_start > source.len() || !source.is_char_boundary(vf_start) {
                return Err("Value feature span is not valid in source".to_string());
            }
            let prefix = source[start_byte..vf_start].trim_end();
            if prefix.is_empty() {
                // Bare value (e.g. sequence item) — no key prefix
                let serialized = serde_yaml::to_string(value)
                    .map_err(|e| format!("Failed to serialize YAML: {e}"))?;
                let trimmed = serialized.trim_end_matches('\n');

                let line_start = source[..feature.location.byte_span.0]
                    .rfind('\n')
                    .map(|nl| nl + 1)
                    .unwrap_or(0);
                let base_indent = feature.location.byte_span.0 - line_start;
                let indent_str = " ".repeat(base_indent);

                let indented = indent_block(trimmed, &indent_str);

                let mut result = source.to_string();
                result.replace_range(
                    feature.location.byte_span.0..feature.location.byte_span.1,
                    &indented,
                );
                if !result.ends_with('\n') {
                    result.push('\n');
                }
                return yamlpath::Document::new(result)
                    .map_err(|e| format!("Failed to re-parse YAML: {e}"));
            }
            prefix.to_string()
        }
        None => {
            // Absent value (e.g. `key:\n`) — content is just key+colon
            content_with_ws.trim_end().to_string()
        }
    };

    // Compute base indentation from the feature's actual position
    let feat_start = feature.location.byte_span.0;
    let line_start = source[..feat_start]
        .rfind('\n')
        .map(|nl| nl + 1)
        .unwrap_or(0);
    let base_indent = feat_start - line_start;
    // NOTE: The +2 assumes 2-space indentation. This is consistent with yamlpatch,
    // which also hardcodes 2-space indent in Add, Append, MergeInto, and Replace ops.
    let value_indent = " ".repeat(base_indent + 2);

    // Serialize the new value in block style
    let serialized =
        serde_yaml::to_string(value).map_err(|e| format!("Failed to serialize YAML: {e}"))?;
    let trimmed = serialized.trim_end_matches('\n');

    // Re-indent each line of the serialized value
    let indented_value = indent_block(trimmed, &value_indent);

    // Assemble: key:\n  indented_value
    // NOTE: Inline comments on the value line are not preserved, consistent
    // with yamlpatch's own Replace behavior for scalar values.
    let replacement = format!("{}\n{}", key_part, indented_value);

    // Replace in source
    let mut result = source.to_string();
    result.replace_range(start_byte..end_byte, &replacement);

    if !result.ends_with('\n') {
        result.push('\n');
    }

    yamlpath::Document::new(result).map_err(|e| format!("Failed to re-parse YAML: {e}"))
}

fn indent_block(content: &str, indent: &str) -> String {
    let mut result = String::new();
    for (i, line) in content.lines().enumerate() {
        if i > 0 {
            result.push('\n');
        }
        // Blank lines are preserved (the \n above) but not indented,
        // avoiding trailing whitespace. In practice serde_yaml::to_string()
        // never emits blank lines for Mapping/Sequence values.
        if !line.trim().is_empty() {
            result.push_str(indent);
            result.push_str(line);
        }
    }
    result
}

fn convert_feature(feature: &yamlpath::Feature<'_>) -> PyFeature {
    PyFeature {
        location: PyLocation {
            start: feature.location.byte_span.0,
            end: feature.location.byte_span.1,
        },
        context: feature.context.as_ref().map(|c| PyLocation {
            start: c.byte_span.0,
            end: c.byte_span.1,
        }),
        kind: PyFeatureKind::from(feature.kind()),
        is_multiline: feature.is_multiline(),
    }
}
