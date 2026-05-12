mod convert;
mod document;
mod ops;
mod types;

use pyo3::prelude::*;

use document::PyDocument;
use ops::{PyOp, PyPatch};
use types::{PyComponent, PyFeature, PyFeatureKind, PyLocation, PyRoute};

#[pymodule]
mod _core {
    use super::*;

    #[pymodule_export]
    use super::PyLocation;
    #[pymodule_export]
    use super::PyFeatureKind;
    #[pymodule_export]
    use super::PyComponent;
    #[pymodule_export]
    use super::PyRoute;
    #[pymodule_export]
    use super::PyFeature;
    #[pymodule_export]
    use super::PyDocument;
    #[pymodule_export]
    use super::PyOp;
    #[pymodule_export]
    use super::PyPatch;

    #[pyfunction]
    fn apply_patches(source: &str, patches: Vec<PyPatch>) -> PyResult<String> {
        ops::apply_patches(source, patches)
    }

    #[pyfunction]
    fn parse_value(py: Python<'_>, source: &str, route: &PyRoute) -> PyResult<PyObject> {
        document::parse_value(py, source, route)
    }
}
