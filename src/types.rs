use pyo3::prelude::*;

/// Byte offset span in the YAML source.
#[pyclass(name = "Location", module = "yamltrip._core", frozen, eq, hash)]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct PyLocation {
    #[pyo3(get)]
    pub start: usize,
    #[pyo3(get)]
    pub end: usize,
}

#[pymethods]
impl PyLocation {
    #[new]
    fn new(start: usize, end: usize) -> PyResult<Self> {
        if start > end {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Location start ({start}) must not exceed end ({end})"),
            ));
        }
        Ok(Self { start, end })
    }

    fn __repr__(&self) -> String {
        format!("Location(start={}, end={})", self.start, self.end)
    }
}

impl From<yamlpath::Location> for PyLocation {
    fn from(loc: yamlpath::Location) -> Self {
        Self {
            start: loc.byte_span.0,
            end: loc.byte_span.1,
        }
    }
}

/// The kind of a YAML feature.
#[pyclass(name = "FeatureKind", module = "yamltrip._core", frozen, eq, eq_int, hash)]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum PyFeatureKind {
    Scalar,
    BlockMapping,
    FlowMapping,
    BlockSequence,
    FlowSequence,
}

impl From<yamlpath::FeatureKind> for PyFeatureKind {
    fn from(kind: yamlpath::FeatureKind) -> Self {
        match kind {
            yamlpath::FeatureKind::Scalar => Self::Scalar,
            yamlpath::FeatureKind::BlockMapping => Self::BlockMapping,
            yamlpath::FeatureKind::FlowMapping => Self::FlowMapping,
            yamlpath::FeatureKind::BlockSequence => Self::BlockSequence,
            yamlpath::FeatureKind::FlowSequence => Self::FlowSequence,
        }
    }
}

/// A single route component — either a mapping key or a sequence index.
#[pyclass(name = "Component", module = "yamltrip._core", frozen, eq, hash)]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum PyComponent {
    Key { name: String },
    Index { index: usize },
}

#[pymethods]
impl PyComponent {
    #[staticmethod]
    fn key(name: &str) -> Self {
        Self::Key {
            name: name.to_string(),
        }
    }

    #[staticmethod]
    fn index(index: usize) -> Self {
        Self::Index { index }
    }

    fn __repr__(&self) -> String {
        match self {
            Self::Key { name } => format!("Component.key('{name}')"),
            Self::Index { index } => format!("Component.index({index})"),
        }
    }
}

/// A path into a YAML document.
#[pyclass(name = "Route", module = "yamltrip._core", frozen, eq, hash)]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct PyRoute {
    pub components: Vec<PyComponent>,
}

#[pymethods]
impl PyRoute {
    #[new]
    fn new(parts: Vec<Bound<'_, PyAny>>) -> PyResult<Self> {
        let mut components = Vec::new();
        for part in parts {
            if let Ok(s) = part.extract::<String>() {
                components.push(PyComponent::Key { name: s });
            } else if let Ok(i) = part.extract::<usize>() {
                components.push(PyComponent::Index { index: i });
            } else if part.extract::<i64>().is_ok() {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Route indices must be non-negative integers",
                ));
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(format!(
                    "Route components must be str or int, got {}",
                    part.get_type().name()?
                )));
            }
        }
        Ok(Self { components })
    }

    fn __len__(&self) -> usize {
        self.components.len()
    }

    fn __repr__(&self) -> String {
        let parts: Vec<String> = self.components.iter().map(|c| c.__repr__()).collect();
        format!("Route([{}])", parts.join(", "))
    }
}

impl PyRoute {
    /// Convert to a yamlpath::Route.
    pub fn to_yamlpath_route(&self) -> yamlpath::Route<'_> {
        let components: Vec<yamlpath::Component<'_>> = self
            .components
            .iter()
            .map(|c| match c {
                PyComponent::Key { name } => yamlpath::Component::Key(name.as_str().into()),
                PyComponent::Index { index } => yamlpath::Component::Index(*index),
            })
            .collect();
        yamlpath::Route::from(components)
    }
}

/// The result of a YAML path query.
#[pyclass(name = "Feature", module = "yamltrip._core", frozen, eq, hash)]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct PyFeature {
    #[pyo3(get)]
    pub location: PyLocation,
    #[pyo3(get)]
    pub context: Option<PyLocation>,
    #[pyo3(get)]
    pub kind: PyFeatureKind,
    #[pyo3(get)]
    pub is_multiline: bool,
}

#[pymethods]
impl PyFeature {
    fn __repr__(&self) -> String {
        format!(
            "Feature(location={}, kind={:?})",
            self.location.__repr__(),
            self.kind
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_location_equality() {
        let a = PyLocation { start: 0, end: 5 };
        let b = PyLocation { start: 0, end: 5 };
        let c = PyLocation { start: 0, end: 6 };
        assert_eq!(a, b);
        assert_ne!(a, c);
    }

    #[test]
    fn test_location_from_yamlpath() {
        let loc = yamlpath::Location {
            byte_span: (10, 20),
            point_span: ((0, 10), (0, 20)),
        };
        let py_loc = PyLocation::from(loc);
        assert_eq!(py_loc.start, 10);
        assert_eq!(py_loc.end, 20);
    }

    #[test]
    fn test_feature_kind_from_yamlpath() {
        assert_eq!(
            PyFeatureKind::from(yamlpath::FeatureKind::Scalar),
            PyFeatureKind::Scalar
        );
        assert_eq!(
            PyFeatureKind::from(yamlpath::FeatureKind::BlockMapping),
            PyFeatureKind::BlockMapping
        );
        assert_eq!(
            PyFeatureKind::from(yamlpath::FeatureKind::FlowMapping),
            PyFeatureKind::FlowMapping
        );
        assert_eq!(
            PyFeatureKind::from(yamlpath::FeatureKind::BlockSequence),
            PyFeatureKind::BlockSequence
        );
        assert_eq!(
            PyFeatureKind::from(yamlpath::FeatureKind::FlowSequence),
            PyFeatureKind::FlowSequence
        );
    }

    #[test]
    fn test_component_equality() {
        assert_eq!(
            PyComponent::Key {
                name: "a".to_string()
            },
            PyComponent::Key {
                name: "a".to_string()
            }
        );
        assert_ne!(
            PyComponent::Key {
                name: "a".to_string()
            },
            PyComponent::Index { index: 0 }
        );
    }

    #[test]
    fn test_route_to_yamlpath_conversion() {
        let route = PyRoute {
            components: vec![
                PyComponent::Key {
                    name: "a".to_string(),
                },
                PyComponent::Index { index: 0 },
                PyComponent::Key {
                    name: "b".to_string(),
                },
            ],
        };
        // Just verify it doesn't panic
        let _yamlpath_route = route.to_yamlpath_route();
    }

    #[test]
    fn test_empty_route_conversion() {
        let route = PyRoute {
            components: vec![],
        };
        let _yamlpath_route = route.to_yamlpath_route();
    }

    #[test]
    fn test_route_negative_int_error_message() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let neg = (-1i64).into_pyobject(py).unwrap().into_any();
            let parts = vec![neg];
            let list = pyo3::types::PyList::new(py, &parts).unwrap();
            let bound_list: Vec<Bound<'_, PyAny>> = list.iter().collect();
            let result = PyRoute::new(bound_list);
            let err = result.unwrap_err();
            let msg = err.to_string();
            assert!(
                !msg.contains("must be str or int"),
                "Error should not say 'must be str or int' for a negative int, got: {msg}"
            );
        });
    }
}
