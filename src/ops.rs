use pyo3::prelude::*;

use crate::convert::py_to_yaml_value;
use crate::types::PyRoute;

/// A YAML patch operation.
#[pyclass(name = "Op", module = "yamltrip._core")]
#[derive(Clone, Debug)]
pub struct PyOp {
    pub inner: yamlpatch::Op<'static>,
}

#[pymethods]
impl PyOp {
    #[staticmethod]
    fn replace(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let val = py_to_yaml_value(value)?;
        Ok(Self {
            inner: yamlpatch::Op::Replace(val),
        })
    }

    #[staticmethod]
    fn add(key: &str, value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let val = py_to_yaml_value(value)?;
        Ok(Self {
            inner: yamlpatch::Op::Add {
                key: key.to_string(),
                value: val,
            },
        })
    }

    #[staticmethod]
    fn remove() -> Self {
        Self {
            inner: yamlpatch::Op::Remove,
        }
    }

    #[staticmethod]
    fn append(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let val = py_to_yaml_value(value)?;
        Ok(Self {
            inner: yamlpatch::Op::Append { value: val },
        })
    }

    /// Merge key-value pairs into an existing mapping.
    #[staticmethod]
    fn merge_into(key: &str, updates: &Bound<'_, PyAny>) -> PyResult<Self> {
        let dict = updates.downcast::<pyo3::types::PyDict>().map_err(|_| {
            let type_name = updates.get_type().name().map_or_else(
                |_| "<unknown>".to_string(),
                |n| n.to_string(),
            );
            PyErr::new::<pyo3::exceptions::PyTypeError, _>(format!(
                "updates must be a dict, got {type_name}"
            ))
        })?;
        let mut map = indexmap::IndexMap::new();
        for (k, v) in dict.iter() {
            let key_str: String = k.extract()?;
            let val = py_to_yaml_value(&v)?;
            map.insert(key_str, val);
        }
        Ok(Self {
            inner: yamlpatch::Op::MergeInto {
                key: key.to_string(),
                updates: map,
            },
        })
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            yamlpatch::Op::Replace(val) => {
                format!("Op.replace({})", yaml_value_repr(val))
            }
            yamlpatch::Op::Add { key, value } => {
                format!("Op.add({}, {})", yaml_value_repr(&serde_yaml::Value::String(key.clone())), yaml_value_repr(value))
            }
            yamlpatch::Op::Remove => "Op.remove()".to_string(),
            yamlpatch::Op::Append { value } => {
                format!("Op.append({})", yaml_value_repr(value))
            }
            yamlpatch::Op::MergeInto { key, .. } => {
                format!("Op.merge_into({}, ...)", yaml_value_repr(&serde_yaml::Value::String(key.clone())))
            }
            _ => format!("Op({:?})", self.inner),
        }
    }
}

/// Format a serde_yaml::Value as a Python-style repr.
fn yaml_value_repr(val: &serde_yaml::Value) -> String {
    match val {
        serde_yaml::Value::Null => "None".to_string(),
        serde_yaml::Value::Bool(b) => if *b { "True" } else { "False" }.to_string(),
        serde_yaml::Value::Number(n) => format!("{n}"),
        serde_yaml::Value::String(s) => format!("'{s}'"),
        serde_yaml::Value::Sequence(_) => "[...]".to_string(),
        serde_yaml::Value::Mapping(_) => "{...}".to_string(),
        serde_yaml::Value::Tagged(t) => yaml_value_repr(&t.value),
    }
}

/// A patch: a route + an operation.
#[pyclass(name = "Patch", module = "yamltrip._core")]
#[derive(Clone, Debug)]
pub struct PyPatch {
    #[pyo3(get)]
    pub route: PyRoute,
    #[pyo3(get)]
    pub operation: PyOp,
}

#[pymethods]
impl PyPatch {
    #[new]
    fn new(route: PyRoute, operation: PyOp) -> Self {
        Self { route, operation }
    }
}

/// Apply a list of patches to a YAML source string.
#[pyfunction]
pub fn apply_patches(source: &str, patches: Vec<PyPatch>) -> PyResult<String> {
    let document = yamlpath::Document::new(source).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid YAML: {e}"))
    })?;

    let yaml_patches: Vec<yamlpatch::Patch<'_>> = patches
        .iter()
        .map(|p| yamlpatch::Patch {
            route: p.route.to_yamlpath_route(),
            operation: p.operation.inner.clone(),
        })
        .collect();

    let result = yamlpatch::apply_yaml_patches(&document, &yaml_patches).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Patch failed: {e}"))
    })?;

    Ok(result.source().to_string())
}
