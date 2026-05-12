mod convert;
mod types;

use pyo3::prelude::*;

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
}
