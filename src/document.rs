use pyo3::prelude::*;

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
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Failed to parse YAML: {e}"
            ))
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
        Ok(source[start..end].to_string())
    }

    fn has_anchors(&self) -> bool {
        self.inner.has_anchors()
    }

    /// Parse the YAML value at a route and return it as a Python object.
    fn parse_value(&self, py: Python<'_>, route: &PyRoute) -> PyResult<PyObject> {
        let source = self.inner.source();
        let r = route.to_yamlpath_route();

        if !self.inner.query_exists(&r) {
            return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Path not found",
            ));
        }

        // For root-level, parse entire document
        let yaml_str = if route.components.is_empty() {
            source.to_string()
        } else {
            match self.inner.query_exact(&r) {
                Ok(Some(feature)) => {
                    let span = feature.location.byte_span;
                    let raw = &source[span.0..span.1];
                    // Calculate column offset of the value start to dedent
                    // subsequent lines that carry the original indentation.
                    let col = source[..span.0]
                        .rfind('\n')
                        .map(|nl| span.0 - nl - 1)
                        .unwrap_or(span.0);
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
                    )))
                }
            }
        };

        let value: serde_yaml::Value = serde_yaml::from_str(&yaml_str).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("YAML parse error: {e}"))
        })?;

        crate::convert::yaml_value_to_py(py, &value)
    }
}

/// Parse the YAML value at a route and return it as a Python object.
///
/// Standalone wrapper that parses the source first.  Prefer
/// `Document.parse_value` when you already hold a `Document`.
#[pyfunction]
pub fn parse_value(py: Python<'_>, source: &str, route: &PyRoute) -> PyResult<PyObject> {
    let doc = PyDocument::new(source)?;
    doc.parse_value(py, route)
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
