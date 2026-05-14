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
    /// NOTE: Similar patch-application logic exists in ops::apply_patches (returns String).
    fn apply_patches(&self, patches: Vec<PyPatch>) -> PyResult<Self> {
        let yaml_patches: Vec<yamlpatch::Patch<'_>> = patches
            .iter()
            .map(|p| yamlpatch::Patch {
                route: p.route.to_yamlpath_route(),
                operation: p.operation.inner.clone(),
            })
            .collect();

        let result = yamlpatch::apply_yaml_patches(&self.inner, &yaml_patches).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Patch failed: {e}"))
        })?;

        Ok(Self { inner: result })
    }
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
