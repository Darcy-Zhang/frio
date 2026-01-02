# frio 🚀

**frio** (Fast Rust I/O) is a high-performance **batch file reading library** for Python, engineered for extreme throughput and minimal CPU overhead. 

It bridges the gap between Python's high-level logic and Linux's cutting-edge **io_uring** interface, providing a truly asynchronous, zero-copy data pipeline.

---

## ✨ Key Features

* **io_uring Integration**: Powered by `monoio`, utilizing the latest Linux asynchronous I/O primitives for maximum hardware saturation.
* **True Zero-Copy**: Implements the **Python Buffer Protocol**. File data is DMA-transferred from disk to Rust memory and shared with Python via memory views—zero redundant copies.
* **GIL-Free Fetching**: Background worker threads handle all I/O, releasing the GIL to ensure your Python application stays responsive.

---

## 🛠 Installation

`frio` utilizes `uv` to handle building and installation automatically. No manual compilation required.

### Prerequisites
* **Linux Kernel 5.6+** (Required for `io_uring` support)
* **Rust Toolchain** (Must be installed on the system)

### Quick Add
```bash
# Add to your project
uv add git+[https://github.com/Darcy-Zhang/frio.git](https://github.com/Darcy-Zhang/frio.git)
```

### Manual Sync
Add the following to your `pyproject.toml`:
```toml
[project]
dependencies = [
    "frio @ git+[https://github.com/Darcy-Zhang/frio.git](https://github.com/Darcy-Zhang/frio.git)"
]
```
Then run:
```bash
uv sync
```


## 🚀 Usage

`frio` provides a simple, Pythonic iterator-based API.

```python
import frio
import numpy as np

# Batch fetch files
files = ["data1.bin", "data2.bin", "large_image.jpg"]

# fetch(files, chunk_size=0, threads=1)
# threads=0 will auto-calculate based on core count
for path, buf in frio.fetch(files, threads=4):
    # 'buf' is a FrioBuffer object supporting the Buffer Protocol
    # Create a zero-copy memoryview or numpy array
    mv = memoryview(buf)
    data = np.frombuffer(buf, dtype=np.uint8)
    
    print(f"Read {path}: {len(data)} bytes")
    print(f"Memory Address: {hex(data.__array_interface__['data'][0])}")
```

---

## 🏗 Dependencies

`frio` stands on the shoulders of these amazing projects:
* [PyO3](https://pyo3.rs/) - Rust bindings for Python.
* [monoio](https://github.com/bytedance/monoio) - A thread-per-core Rust runtime based on io_uring.
* [crossbeam-channel](https://github.com/crossbeam-rs/crossbeam) - Multi-producer multi-consumer channels.
* [core_affinity](https://github.com/Elar7/core_affinity-rs) - For CPU pinning and performance stability.

---

## ⚠️ Status & Disclaimer

**This is a TOY project for experimental purposes.**

* **Stability**: The API is highly unstable and subject to change without notice.
* **Platform Support**: Optimized strictly for **Linux**. It **WILL NOT** work on Windows or macOS due to the `io_uring` dependency.
* **Production**: This library is NOT battle-tested. **Use at your own risk.** The author is not responsible for any data loss or system instability.
