use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyNone, PyString, PyTuple};
use serde_yaml::Value;

/// Convert a Python object to a serde_yaml::Value.
///
/// Supported types: None, bool, int, float, str, list, dict.
/// Raises TypeError for unsupported types.
///
/// # Recursion depth
/// This function recurses into nested lists/dicts without a depth limit.
/// In practice, Python's own recursion limit (~1000 by default) prevents
/// callers from constructing structures deep enough to overflow the Rust
/// stack. A dedicated depth guard is not warranted unless Python's limit
/// is bypassed (e.g. via `sys.setrecursionlimit`).
pub fn py_to_yaml_value(obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if obj.is_instance_of::<PyNone>() {
        Ok(Value::Null)
    } else if obj.is_instance_of::<PyBool>() {
        // Must check bool before int, since bool is a subclass of int in Python
        Ok(Value::Bool(obj.extract::<bool>()?))
    } else if obj.is_instance_of::<PyInt>() {
        if let Ok(i) = obj.extract::<i64>() {
            Ok(Value::Number(i.into()))
        } else if let Ok(u) = obj.extract::<u64>() {
            Ok(Value::Number(u.into()))
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                "Integer too large for YAML number (must fit in i64 or u64)",
            ))
        }
    } else if obj.is_instance_of::<PyFloat>() {
        let f: f64 = obj.extract()?;
        Ok(Value::Number(serde_yaml::Number::from(f)))
    } else if obj.is_instance_of::<PyString>() {
        Ok(Value::String(obj.extract::<String>()?))
    } else if obj.is_instance_of::<PyList>() {
        let list = obj.cast::<PyList>()?;
        let items: PyResult<Vec<Value>> = list.iter().map(|item| py_to_yaml_value(&item)).collect();
        Ok(Value::Sequence(items?))
    } else if obj.is_instance_of::<PyTuple>() {
        let tuple = obj.cast::<PyTuple>()?;
        let items: PyResult<Vec<Value>> =
            tuple.iter().map(|item| py_to_yaml_value(&item)).collect();
        Ok(Value::Sequence(items?))
    } else if obj.is_instance_of::<PyDict>() {
        let dict = obj.cast::<PyDict>()?;
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
///
/// # Recursion depth
/// This function recurses without a depth limit. The input comes from
/// `serde_yaml::from_str`, which enforces its own recursion limit (128
/// by default), so the nesting depth is bounded in practice.
pub fn yaml_value_to_py(py: Python<'_>, value: &Value) -> PyResult<Py<PyAny>> {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_py_to_yaml_none() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let none = py.None().into_bound(py);
            let val = py_to_yaml_value(&none).unwrap();
            assert_eq!(val, Value::Null);
        });
    }

    #[test]
    fn test_py_to_yaml_bool() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let t = true.into_pyobject(py).unwrap();
            assert_eq!(py_to_yaml_value(t.as_any()).unwrap(), Value::Bool(true));
            let f = false.into_pyobject(py).unwrap();
            assert_eq!(py_to_yaml_value(f.as_any()).unwrap(), Value::Bool(false));
        });
    }

    #[test]
    fn test_py_to_yaml_int() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let i = 42i64.into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&i).unwrap();
            assert_eq!(val, Value::Number(42.into()));
        });
    }

    #[test]
    fn test_py_to_yaml_large_unsigned_int() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            // i64::MAX + 1 is a valid u64 but overflows i64
            let large = (i64::MAX as u64 + 1).into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&large).unwrap();
            assert_eq!(
                val,
                Value::Number(serde_yaml::Number::from(i64::MAX as u64 + 1))
            );
        });
    }

    #[test]
    fn test_py_to_yaml_float_finite() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let f = 3.15f64.into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&f).unwrap();
            match val {
                Value::Number(n) => assert_eq!(n.as_f64().unwrap(), 3.15),
                _ => panic!("expected Number"),
            }
        });
    }

    #[test]
    fn test_py_to_yaml_float_nan() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let nan = f64::NAN.into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&nan).unwrap();
            match val {
                Value::Number(n) => assert!(n.is_nan()),
                _ => panic!("expected Number"),
            }
        });
    }

    #[test]
    fn test_py_to_yaml_float_inf() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let inf = f64::INFINITY.into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&inf).unwrap();
            match val {
                Value::Number(n) => assert!(n.is_infinite()),
                _ => panic!("expected Number"),
            }
        });
    }

    #[test]
    fn test_py_to_yaml_float_neg_inf() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let neg_inf = f64::NEG_INFINITY.into_pyobject(py).unwrap().into_any();
            let val = py_to_yaml_value(&neg_inf).unwrap();
            match val {
                Value::Number(n) => {
                    assert!(n.is_infinite());
                    assert_eq!(n.as_f64().unwrap(), f64::NEG_INFINITY);
                }
                _ => panic!("expected Number"),
            }
        });
    }

    #[test]
    fn test_py_to_yaml_string() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let s = "hello".into_pyobject(py).unwrap().into_any();
            assert_eq!(py_to_yaml_value(&s).unwrap(), Value::String("hello".into()));
        });
    }

    #[test]
    fn test_py_to_yaml_list() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let list = PyList::new(py, [1i64, 2, 3]).unwrap();
            let val = py_to_yaml_value(list.as_any()).unwrap();
            assert_eq!(
                val,
                Value::Sequence(vec![
                    Value::Number(1.into()),
                    Value::Number(2.into()),
                    Value::Number(3.into()),
                ])
            );
        });
    }

    #[test]
    fn test_py_to_yaml_dict() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let dict = PyDict::new(py);
            dict.set_item("key", "value").unwrap();
            let val = py_to_yaml_value(dict.as_any()).unwrap();
            let mut expected = serde_yaml::Mapping::new();
            expected.insert(Value::String("key".into()), Value::String("value".into()));
            assert_eq!(val, Value::Mapping(expected));
        });
    }

    #[test]
    fn test_py_to_yaml_unsupported_type_rejected() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let set = py.eval(pyo3::ffi::c_str!("set()"), None, None).unwrap();
            assert!(py_to_yaml_value(&set).is_err());
        });
    }

    #[test]
    fn test_yaml_to_py_null() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let obj = yaml_value_to_py(py, &Value::Null).unwrap();
            assert!(obj.bind(py).is_none());
        });
    }

    #[test]
    fn test_yaml_to_py_bool() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let obj = yaml_value_to_py(py, &Value::Bool(true)).unwrap();
            assert!(obj.extract::<bool>(py).unwrap());
        });
    }

    #[test]
    fn test_yaml_to_py_number_i64() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let obj = yaml_value_to_py(py, &Value::Number(42.into())).unwrap();
            assert_eq!(obj.extract::<i64>(py).unwrap(), 42);
        });
    }

    #[test]
    fn test_yaml_to_py_string() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let obj = yaml_value_to_py(py, &Value::String("hello".into())).unwrap();
            assert_eq!(obj.extract::<String>(py).unwrap(), "hello");
        });
    }

    #[test]
    fn test_yaml_to_py_sequence() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let seq = Value::Sequence(vec![Value::Number(1.into()), Value::Number(2.into())]);
            let obj = yaml_value_to_py(py, &seq).unwrap();
            let list = obj.extract::<Vec<i64>>(py).unwrap();
            assert_eq!(list, vec![1, 2]);
        });
    }

    #[test]
    fn test_yaml_to_py_tagged_strips_tag() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let tagged = Value::Tagged(Box::new(serde_yaml::value::TaggedValue {
                tag: serde_yaml::value::Tag::new("!custom"),
                value: Value::String("inner".into()),
            }));
            let obj = yaml_value_to_py(py, &tagged).unwrap();
            assert_eq!(obj.extract::<String>(py).unwrap(), "inner");
        });
    }
}
