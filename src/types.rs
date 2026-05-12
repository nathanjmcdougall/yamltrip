use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use pyo3::prelude::*;

/// Byte offset span in the YAML source.
#[pyclass(name = "Location", module = "yamltrip._core")]
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

    fn __eq__(&self, other: &Self) -> bool {
        self.start == other.start && self.end == other.end
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.start.hash(&mut hasher);
        self.end.hash(&mut hasher);
        hasher.finish()
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
#[pyclass(name = "Component", module = "yamltrip._core")]
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

    fn __eq__(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Key { name: a }, Self::Key { name: b }) => a == b,
            (Self::Index { index: a }, Self::Index { index: b }) => a == b,
            _ => false,
        }
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.hash(&mut hasher);
        hasher.finish()
    }
}

/// A path into a YAML document.
#[pyclass(name = "Route", module = "yamltrip._core")]
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

    fn __eq__(&self, other: &Self) -> bool {
        self.components == other.components
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.components.hash(&mut hasher);
        hasher.finish()
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
#[pyclass(name = "Feature", module = "yamltrip._core")]
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

    fn __eq__(&self, other: &Self) -> bool {
        self == other
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.hash(&mut hasher);
        hasher.finish()
    }
}
