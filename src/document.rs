use pyo3::prelude::*;

use crate::ops::PyPatch;
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
        let is_complex_replace = matches!(
            &patch.operation.inner,
            yamlpatch::Op::Replace(v) if matches!(v, serde_yaml::Value::Mapping(_) | serde_yaml::Value::Sequence(_))
        );

        if is_complex_replace {
            // Flush any pending yamlpatch batch first
            if !batch.is_empty() {
                let yaml_patches: Vec<yamlpatch::Patch<'_>> = batch
                    .iter()
                    .map(|&i| yamlpatch::Patch {
                        route: patches[i].route.to_yamlpath_route(),
                        operation: patches[i].operation.inner.clone(),
                    })
                    .collect();
                current_doc = yamlpatch::apply_yaml_patches(&current_doc, &yaml_patches)
                    .map_err(|e| e.to_string())?;
                batch.clear();
            }

            // Apply the complex replace directly
            let route = patch.route.to_yamlpath_route();
            let value = match &patch.operation.inner {
                yamlpatch::Op::Replace(v) => v,
                _ => unreachable!(),
            };
            current_doc = apply_complex_replace(&current_doc, &route, value)?;
        } else {
            batch.push(idx);
        }
    }

    // Flush remaining batch
    if !batch.is_empty() {
        let yaml_patches: Vec<yamlpatch::Patch<'_>> = batch
            .iter()
            .map(|&i| yamlpatch::Patch {
                route: patches[i].route.to_yamlpath_route(),
                operation: patches[i].operation.inner.clone(),
            })
            .collect();
        current_doc = yamlpatch::apply_yaml_patches(&current_doc, &yaml_patches)
            .map_err(|e| e.to_string())?;
    }

    Ok(current_doc)
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

    let content_with_ws = doc.extract_with_leading_whitespace(&feature);
    let content = doc.extract(&feature);

    // Calculate the start byte including leading whitespace.
    // Safety: ws_len <= byte_span.0 because extract_with_leading_whitespace only
    // extends backward to the last newline (or start of document), never beyond byte_span.0.
    let ws_len = content_with_ws.len() - content.len();
    let start_byte = feature.location.byte_span.0 - ws_len;
    let end_byte = feature.location.byte_span.1;

    // Find the colon separating key from value
    let colon_pos = find_key_colon(content_with_ws);

    let (key_part, value_first_line) = match colon_pos {
        Some(pos) => {
            let key = &content_with_ws[..pos + 1]; // through the colon
            let rest = &content_with_ws[pos + 1..];
            (key.to_string(), rest.to_string())
        }
        None => {
            // No colon found — bare value (e.g. sequence item)
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
    };

    // Detect inline comment on the first line of the value part
    let first_line = value_first_line.lines().next().unwrap_or("");
    let comment = extract_inline_comment(first_line);

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

    // Assemble: key: [# comment]\n  indented_value
    let replacement = match comment {
        Some(c) => format!("{} {}\n{}", key_part, c, indented_value),
        None => format!("{}\n{}", key_part, indented_value),
    };

    // Replace in source
    let mut result = source.to_string();
    result.replace_range(start_byte..end_byte, &replacement);

    if !result.ends_with('\n') {
        result.push('\n');
    }

    yamlpath::Document::new(result).map_err(|e| format!("Failed to re-parse YAML: {e}"))
}

/// Find the first structural colon (key-value separator) in a YAML fragment,
/// skipping colons inside single- or double-quoted strings.
///
/// Precondition: `content` must be valid YAML text extracted from a yamlpath
/// feature. Unterminated quotes cannot occur in practice because yamlpath
/// only produces features from successfully parsed documents.
fn find_key_colon(content: &str) -> Option<usize> {
    let bytes = content.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'\'' => {
                i += 1;
                while i < bytes.len() && bytes[i] != b'\'' {
                    i += 1;
                }
                if i < bytes.len() {
                    i += 1;
                }
            }
            b'"' => {
                i += 1;
                while i < bytes.len() {
                    if bytes[i] == b'\\' {
                        i = (i + 2).min(bytes.len());
                    } else if bytes[i] == b'"' {
                        break;
                    } else {
                        i += 1;
                    }
                }
                if i < bytes.len() {
                    i += 1;
                }
            }
            b':' => {
                let next = bytes.get(i + 1);
                if matches!(next, Some(b' ') | Some(b'\n') | Some(b'\r') | None) {
                    return Some(i);
                }
                i += 1;
            }
            _ => {
                i += 1;
            }
        }
    }
    None
}

fn extract_inline_comment(line: &str) -> Option<&str> {
    let bytes = line.as_bytes();
    let mut i = 0;
    let mut in_single_quote = false;
    let mut in_double_quote = false;

    while i < bytes.len() {
        match bytes[i] {
            b'\'' if !in_double_quote => {
                in_single_quote = !in_single_quote;
            }
            b'"' if !in_single_quote => {
                in_double_quote = !in_double_quote;
            }
            b'\\' if in_double_quote => {
                i += 1;
            }
            b'#' if !in_single_quote
                && !in_double_quote
                && i > 0
                && (bytes[i - 1] == b' ' || bytes[i - 1] == b'\t') =>
            {
                return Some(&line[i..]);
            }
            _ => {}
        }
        i += 1;
    }
    None
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
