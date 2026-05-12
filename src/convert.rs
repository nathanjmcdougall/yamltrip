use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyNone, PyString, PyTuple};
use serde_yaml::Value;

/// Convert a Python object to a serde_yaml::Value.
///
/// Supported types: None, bool, int, float, str, list, dict.
/// Raises TypeError for unsupported types.
pub fn py_to_yaml_value(obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if obj.is_instance_of::<PyNone>() {
        Ok(Value::Null)
    } else if obj.is_instance_of::<PyBool>() {
        // Must check bool before int, since bool is a subclass of int in Python
        Ok(Value::Bool(obj.extract::<bool>()?))
    } else if obj.is_instance_of::<PyInt>() {
        let i: i64 = obj.extract()?;
        Ok(Value::Number(i.into()))
    } else if obj.is_instance_of::<PyFloat>() {
        let f: f64 = obj.extract()?;
        if f.is_finite() {
            Ok(Value::Number(serde_yaml::Number::from(f)))
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Cannot convert float value {f} to YAML number"),
            ))
        }
    } else if obj.is_instance_of::<PyString>() {
        Ok(Value::String(obj.extract::<String>()?))
    } else if obj.is_instance_of::<PyList>() {
        let list = obj.downcast::<PyList>()?;
        let items: PyResult<Vec<Value>> = list.iter().map(|item| py_to_yaml_value(&item)).collect();
        Ok(Value::Sequence(items?))
    } else if obj.is_instance_of::<PyTuple>() {
        let tuple = obj.downcast::<PyTuple>()?;
        let items: PyResult<Vec<Value>> = tuple.iter().map(|item| py_to_yaml_value(&item)).collect();
        Ok(Value::Sequence(items?))
    } else if obj.is_instance_of::<PyDict>() {
        let dict = obj.downcast::<PyDict>()?;
        let mut mapping = serde_yaml::Mapping::new();
        for (k, v) in dict.iter() {
            let key = py_to_yaml_value(&k)?;
            let val = py_to_yaml_value(&v)?;
            mapping.insert(key, val);
        }
        Ok(Value::Mapping(mapping))
    } else {
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(format!(
            "Cannot convert {} to YAML value",
            obj.get_type().name()?
        )))
    }
}

/// Convert a serde_yaml::Value to a Python object.
pub fn yaml_value_to_py(py: Python<'_>, value: &Value) -> PyResult<PyObject> {
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(b) => Ok(b.into_pyobject(py)?.as_any().to_owned().unbind()),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any().unbind())
            } else if let Some(u) = n.as_u64() {
                Ok(u.into_pyobject(py)?.into_any().unbind())
            } else if let Some(f) = n.as_f64() {
                Ok(f.into_pyobject(py)?.into_any().unbind())
            } else {
                Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Cannot convert YAML number to Python",
                ))
            }
        }
        Value::String(s) => Ok(s.into_pyobject(py)?.into_any().unbind()),
        Value::Sequence(seq) => {
            let list = pyo3::types::PyList::empty(py);
            for item in seq {
                list.append(yaml_value_to_py(py, item)?)?;
            }
            Ok(list.into_any().unbind())
        }
        Value::Mapping(map) => {
            let dict = pyo3::types::PyDict::new(py);
            for (k, v) in map {
                dict.set_item(yaml_value_to_py(py, k)?, yaml_value_to_py(py, v)?)?;
            }
            Ok(dict.into_any().unbind())
        }
        Value::Tagged(tagged) => {
            // For tagged values, just convert the inner value
            yaml_value_to_py(py, &tagged.value)
        }
    }
}
