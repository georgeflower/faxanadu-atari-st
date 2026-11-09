#!/usr/bin/env python3
"""Have the ROM play every song and sound effect in the headless NES and record the sound chip (tools/refnes/soundrec.mjs).

    record_sounds.py [--out build/refnes/sound] [--music-frames 9000] [--jobs 4]

Writes m1.json .. m16.json (songs) and s1.json .. s28.json (sound effects); tools/build_sound.py turns them into the ST's sound data.
Needs node, `npm install` in tools/refnes, the RAM labels (tools/ram_labels.py) and the ROM. Takes a few minutes; files that exist are kept
(a sound effect recorded before the engine's priority note, `handler`, was added is recorded again).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def record(out: Path, music_frames: int = 9000, sfx_frames: int = 300, jobs: int = 4) -> None:
    """Record what is not in out yet. Raises when node, the harness or the ROM is missing."""
    if not (ROOT / "tools" / "refnes" / "node_modules" / "jsnes").is_dir():
        raise RuntimeError("npm install in tools/refnes first")
    out.mkdir(parents=True, exist_ok=True)
    work = [("music", i, music_frames, out / f"m{i}.json") for i in range(1, 17)]
    work += [("sfx", i, sfx_frames, out / f"s{i}.json") for i in range(1, 29)]

    def run(job):
        kind, i, frames, path = job
        if path.is_file() and (kind == "music" or '"handler"' in path.read_text()):
            return
        done = subprocess.run(["node", "soundrec.mjs", kind, str(i), str(frames), str(path)], cwd=ROOT / "tools" / "refnes",
                              capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "soundrec.mjs failed")
        print(path.name, flush=True)

    with ThreadPoolExecutor(jobs) as pool:
        list(pool.map(run, work))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "refnes" / "sound")
    parser.add_argument("--music-frames", type=int, default=9000, help="long enough to see every song repeat twice")
    parser.add_argument("--sfx-frames", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    record(args.out, args.music_frames, args.sfx_frames, args.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
