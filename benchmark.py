from concurrent import futures
from frio import fast_readfiles
from pathlib import Path
from random import shuffle
from tqdm import tqdm
from typing import Optional, List

import fnmatch
import os
import re
import time
import typer
import threading

stop_event = threading.Event()

app = typer.Typer()


def _make_validator(patterns):
    if not patterns:
        return None
    regex = "|".join(fnmatch.translate(p) for p in patterns)
    return re.compile(regex).match


def scan_dir(root, whitelist=None, blacklist=None, shuffle_files=False):
    root = os.path.abspath(root)
    _black_match = _make_validator(blacklist)
    _white_match = _make_validator(whitelist)
    is_ignored = _black_match if _black_match else (lambda x: False)
    is_allowed = _white_match if _white_match else (lambda x: True)

    stack = [root]
    results = []

    print(f"Scanning directory: {root}...", end="\r")

    while stack:
        current = stack.pop()
        with os.scandir(current) as it:
            dirs = []
            for entry in it:
                name = entry.name
                if is_ignored(name):
                    continue

                if entry.is_dir(follow_symlinks=False):
                    dirs.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    if is_allowed(name):
                        results.append((entry.path, entry.inode()))

            if dirs:
                dirs.sort(key=lambda e: e.inode())
                stack.extend(d.path for d in reversed(dirs))

    if shuffle_files:
        shuffle(results)
    else:
        results.sort(key=lambda x: x[1])

    print(f"Scanned {len(results)} files.")
    return [x[0] for x in results]


def _read_worker(args):
    if stop_event.is_set():
        return 0
    path, chunk_size = args
    with open(path, "rb") as f:
        data = f.read(chunk_size) if chunk_size > 0 else f.read()
    return len(data)


@app.command()
def run(
    root: Path = typer.Argument(..., help="Root directory to scan"),
    backend: str = typer.Option("rust", help="Backend to use: 'rust' or 'python'"),
    threads: int = typer.Option(1, help="Number of threads"),
    duration: int = typer.Option(10, help="Max duration in seconds"),
    shuffle_files: bool = typer.Option(False, help="Randomize file order"),
    chunk_size: int = typer.Option(0, help="Read size (0 for all)"),
    blacklist: Optional[List[str]] = typer.Option(None, help="Glob patterns to ignore"),
):
    stop_event.clear()
    files = scan_dir(root, blacklist=blacklist, shuffle_files=shuffle_files)
    if not files:
        print("No files found!")
        return

    total_bytes = 0
    files_count = 0
    start_time = time.time()

    if backend == "rust":
        iterator = fast_readfiles(files, chunk_size=chunk_size, threads=threads)
        for _path, content in tqdm(
            iterator, total=len(files), unit="files", desc=f"Rust[T={threads}]"
        ):
            files_count += 1
            total_bytes += len(content)

            if time.time() - start_time > duration:
                break
        elapsed = time.time() - start_time

    elif backend == "python":
        tasks = [(f, chunk_size) for f in files]
        executor = futures.ThreadPoolExecutor(max_workers=threads)
        try:
            future_iter = executor.map(_read_worker, tasks)
            for length in tqdm(
                future_iter, total=len(files), unit="files", desc=f"Py[T={threads}]"
            ):
                files_count += 1
                total_bytes += length

                if time.time() - start_time > duration:
                    stop_event.set()
                    break
        finally:
            elapsed = time.time() - start_time
            executor.shutdown(wait=False, cancel_futures=True)

    mb_per_sec = (total_bytes / 1024 / 1024) / elapsed
    files_per_sec = files_count / elapsed

    print(
        f"\nRESULT|{backend}|{threads}|{shuffle_files}|{mb_per_sec:.2f}|{files_per_sec:.2f}"
    )


if __name__ == "__main__":
    app()
