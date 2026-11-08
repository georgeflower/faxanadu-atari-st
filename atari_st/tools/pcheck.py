#!/usr/bin/env python3
"""Runs the unit tests in parallel: `make pcheck` (JOBS=n, default the number of cores).

Every test builds the program into build/ and runs Hatari, so tests cannot share one tree. Each worker gets a copy of atari_st/ of its own (without
build/, but with the label cache) next to links to everything else in the repository, and takes the tests one at a time from a common queue, the
slow ones (the Hatari scenes) first. A failed test's output is printed at the end; the exit code is 1 when any failed.

    tools/pcheck.py [-j N] [-k PATTERN ...]      only the tests whose id contains a pattern
"""
from __future__ import annotations

import argparse
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SLOW_FIRST = ("test_viewer", "test_enemy", "test_menu", "test_items")


def test_ids(patterns: list[str]) -> list[str]:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    ids: list[str] = []

    def walk(s) -> None:
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                ids.append(t.id())

    walk(suite)
    if patterns:
        ids = [i for i in ids if any(p in i for p in patterns)]
    return sorted(ids, key=lambda i: (0 if any(s in i for s in SLOW_FIRST) else 1, i))


def make_tree(base: Path, n: int) -> Path:
    """repo-like tree number n: links to everything but atari_st, which is a copy (tests write into it)."""
    top = base / f"w{n}"
    top.mkdir()
    for entry in REPO.iterdir():
        if entry.name in ("atari_st", ".git"):
            continue
        (top / entry.name).symlink_to(entry)
    work = top / "atari_st"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("build", "__pycache__", ".git"))
    (work / "build").mkdir()
    if (ROOT / "build" / "refnes").is_dir():
        shutil.copytree(ROOT / "build" / "refnes", work / "build" / "refnes")
    return work


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", type=int, default=int(os.environ.get("JOBS") or os.cpu_count() or 2))
    ap.add_argument("-k", action="append", default=[])
    args = ap.parse_args()
    ids = test_ids(args.k)
    work = queue.Queue()
    for i in ids:
        work.put(i)
    results: dict[str, tuple[bool, float, str]] = {}
    lock = threading.Lock()
    base = Path(tempfile.mkdtemp(prefix="pcheck"))
    trees = [make_tree(base, n) for n in range(args.j)]
    started = time.time()

    def worker(tree: Path) -> None:
        while True:
            try:
                tid = work.get_nowait()
            except queue.Empty:
                return
            t0 = time.time()
            p = subprocess.run([sys.executable, "-m", "unittest", tid], cwd=tree / "tests", capture_output=True, text=True)
            with lock:
                results[tid] = (p.returncode == 0, time.time() - t0, p.stdout + p.stderr)
                done = len(results)
                print(f"[{done}/{len(ids)}] {'ok  ' if p.returncode == 0 else 'FAIL'} {tid} ({time.time() - t0:.0f}s)", flush=True)

    threads = [threading.Thread(target=worker, args=(t,)) for t in trees]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    failed = [i for i in ids if not results[i][0]]
    for i in failed:
        print("=" * 70, f"\n{i}\n{results[i][2]}")
    print(f"{len(ids) - len(failed)} of {len(ids)} passed, {len(failed)} failed, {time.time() - started:.0f}s with {args.j} workers")
    shutil.rmtree(base, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
