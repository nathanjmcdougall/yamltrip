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
