use crossbeam_channel::{Receiver, RecvTimeoutError};
use mimalloc::MiMalloc;
use pyo3::{exceptions::PyRuntimeError, ffi, prelude::*};
use pyo3_stub_gen::{define_stub_info_gatherer, derive::*};
use std::{
    os::raw::{c_int, c_void},
    time::Duration,
};

#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

mod scanner;

#[gen_stub_pyclass]
#[pyclass]
struct FrioBuffer {
    data: Vec<u8>,
}

#[pymethods]
impl FrioBuffer {
    fn __len__(&self) -> usize {
        self.data.len()
    }

    unsafe fn __getbuffer__(
        slf: PyRefMut<'_, Self>,
        view: *mut ffi::Py_buffer,
        flags: c_int,
    ) -> PyResult<()> {
        let py_ptr = slf.as_ptr();
        let vec_data = &slf.data;

        let res = unsafe {
            ffi::PyBuffer_FillInfo(
                view,
                py_ptr,
                vec_data.as_ptr() as *mut c_void,
                vec_data.len() as ffi::Py_ssize_t,
                1,
                flags,
            )
        };

        if res == -1 {
            return Err(PyRuntimeError::new_err("Failed to fill buffer info"));
        }
        Ok(())
    }
}

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
                    let buf = FrioBuffer { data };
                    let py_buf = Bound::new(py, buf).ok()?.into_any().unbind();
                    return Some(Ok((path, py_buf)));
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
    m.add_class::<FrioBuffer>()?;
    m.add_class::<FileContentIterator>()?;
    m.add_function(wrap_pyfunction!(fetch, m)?)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
