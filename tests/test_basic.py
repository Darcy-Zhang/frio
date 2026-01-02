from pathlib import Path
from frio import fetch


import pytest
import shutil


@pytest.fixture
def temp_test_dir():
    base_dir = Path("test_playground")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()

    (base_dir / "file1.txt").write_text("Hello World")
    (base_dir / "file2.py").write_text("print('hello')")
    (base_dir / "file3.rs").write_text("fn main() {}")
    (base_dir / "image.jpg").write_bytes(b"\xff\xd8\xff")

    nested = base_dir / "nested"
    nested.mkdir()
    (nested / "file4.txt").write_text("Nested Content")
    (nested / "script.py").write_text("import os")

    ignored = base_dir / "ignored_dir"
    ignored.mkdir()
    (ignored / "file5.txt").write_text("Should not see me")

    hidden = base_dir / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("git config")

    yield base_dir

    if base_dir.exists():
        shutil.rmtree(base_dir)


def test_fast_readfiles(temp_test_dir):
    """测试并发读取文件内容"""
    f1 = temp_test_dir / "file1.txt"
    f2 = temp_test_dir / "file2.py"

    file_list = [str(f1), str(f2)]

    content_iter = fast_scan.fast_readfiles(file_list, 0)

    results = {}
    for path, data in content_iter:
        results[path] = data

    assert str(f1) in results
    assert results[str(f1)] == b"Hello World"
    assert results[str(f2)] == b"print('hello')"


def test_readfiles_chunked(temp_test_dir):
    """测试分块读取（截断）"""
    f1 = temp_test_dir / "file1.txt"

    content_iter = fast_scan.fast_readfiles([str(f1)], 5)

    for _, data in content_iter:
        assert data == b"Hello"
        assert len(data) == 5
