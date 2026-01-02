from tqdm import tqdm
from pathlib import Path
from frio import fetch
from concurrent import futures
from random import shuffle

import fnmatch
import os
import re


def _make_validator(patterns):
    if not patterns:
        return None
    regex = "|".join(fnmatch.translate(p) for p in patterns)
    return re.compile(regex).match


def fast_scan(root, whitelist=None, blacklist=None):
    root = os.path.abspath(root)

    _black_match = _make_validator(blacklist)
    _white_match = _make_validator(whitelist)

    is_ignored = _black_match if _black_match else (lambda x: False)
    is_allowed = _white_match if _white_match else (lambda x: True)

    stack = [root]
    results = []

    pbar = tqdm(desc=f"Scanning", unit="files", mininterval=0.5)

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
                        pbar.update(1)

            if dirs:
                dirs.sort(key=lambda e: e.inode())
                stack.extend(d.path for d in reversed(dirs))

    results.sort(key=lambda x: x[1])
    # shuffle(results)
    return [x[0] for x in results]


def _read_worker(args):
    """
    工作线程执行的函数
    """
    path, chunk_size = args
    try:
        # 打开并读取
        with open(path, "rb") as f:
            if chunk_size > 0:
                # 只读头部
                data = f.read(chunk_size)
            else:
                # 读全文
                data = f.read()
        return (path, data)
    except Exception:
        # 忽略错误
        return None


def fast_readfiles_python_threaded(files, chunk_size, max_workers=8):
    """
    Python 原生多线程读取
    max_workers: 建议设置为 CPU 核心数 * 2，或者 8-16
    """
    # 构造参数列表
    tasks = [(f, chunk_size) for f in files]

    # 使用 ThreadPoolExecutor 管理线程池
    # 相比 ProcessPoolExecutor，线程池启动更快，且数据共享开销小
    with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # map 会按顺序提交任务，并返回迭代器
        # chunksize 参数可以稍微调大，减少队列交互开销
        future_iter = executor.map(_read_worker, tasks)

        # 这里的 tqdm 显示的是处理进度
        # 注意：executor.map 是惰性的，只要有结果就会 yield 出来
        for res in tqdm(
            future_iter,
            total=len(files),
            desc=f"PyThread[W={max_workers}]",
            unit="file",
        ):
            pass

    # return


# dicom_path = Path("/storage/data1/zhangzeao/数据导出")
dicom_path = Path("/home/zhangzeao/Darcy/bone-kit/raw_images")

all_files = fast_scan(dicom_path, blacklist=["*.png"])
# all_files = fast_scan(dicom_path)

# python的文件读取
# for path in tqdm(all_files, desc="Reading files", unit="files"):
#     with open(path, "rb") as f:
#         _ = f.read()

# rust的文件读取
# for path, content in tqdm(
#     fast_readfiles(all_files, threads=1),
#     desc="Reading files",
#     unit="files",
#     total=len(all_files),
# ):
#     pass

# python多线程的文件读取
fast_readfiles_python_threaded(all_files, chunk_size=0, max_workers=1)
