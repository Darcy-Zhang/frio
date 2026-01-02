use crossbeam_channel::{Receiver, RecvTimeoutError};
use pyo3::{exceptions::PyRuntimeError, prelude::*, types::PyBytes};
use pyo3_stub_gen::{define_stub_info_gatherer, derive::*};
use std::time::Duration;

mod scanner;

#[gen_stub_pyclass]
#[pyclass]
struct FileContentIterator {
    receiver: Receiver<anyhow::Result<scanner::ReadResult>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl FileContentIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(slf: PyRefMut<'_, Self>, py: Python<'_>) -> Option<PyResult<(String, Py<PyAny>)>> {
        let rx = &slf.receiver;

        loop {
            let result = py.detach(|| rx.recv_timeout(Duration::from_millis(50)));

            match result {
                Ok(Ok((path, data))) => {
                    let py_bytes = PyBytes::new(py, &data).unbind().into_any();
                    return Some(Ok((path, py_bytes)));
                }
                Ok(Err(e)) => return Some(Err(PyRuntimeError::new_err(e.to_string()))),
                Err(RecvTimeoutError::Disconnected) => return None,
                Err(RecvTimeoutError::Timeout) => {
                    if let Err(e) = py.check_signals() {
                        return Some(Err(e));
                    }
                    continue;
                }
            }
        }
    }
}

#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (files, chunk_size=0, threads=1))]
fn fetch(
    _py: Python,
    files: Vec<String>,
    chunk_size: usize,
    threads: usize,
) -> PyResult<FileContentIterator> {
    let receiver = scanner::fast_readfiles(files, chunk_size, threads);
    Ok(FileContentIterator { receiver })
}

#[pymodule]
fn frio(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FileContentIterator>()?;
    m.add_function(wrap_pyfunction!(fetch, m)?)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
