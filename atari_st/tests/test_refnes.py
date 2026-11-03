"""The ROM harness against the ROM: the RAM labels of the disassembly are right and the scroll is as read in the code.

Skipped without node, the harness' packages, cc65 and the ROM (ext/Faxanadu_Europe.nes), none of which is in the repository.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFNES = ROOT / "tools" / "refnes"
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


def ready() -> bool:
    return bool(shutil.which("node") and shutil.which("ca65") and shutil.which("ld65") and ROM.is_file()
                and (REFNES / "node_modules" / "jsnes").is_dir())


@unittest.skipUnless(ready(), "needs node, npm install in tools/refnes, cc65 and the ROM")
class HarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(["python3", str(ROOT / "tools" / "ram_labels.py")], check=True, capture_output=True)

    def probe(self, direction: str) -> str:
        return subprocess.run(["node", "scroll_probe.mjs", direction, "600"], cwd=REFNES, check=True,
                              capture_output=True, text=True, timeout=300).stdout

    def test_the_labels_find_the_hero_in_eolis(self) -> None:
        out = self.probe("RIGHT")
        self.assertIn("start: area=0 screen=1 x=144", out)

    def test_a_scroll_between_screens_is_64_frames_of_4_pixels(self) -> None:
        out = self.probe("RIGHT")
        self.assertRegex(out, r"scroll frames: \d+")
        changes = re.search(r"per frame \(change: frames\): (.*)", out).group(1)
        self.assertIn("4: 64", changes)
        self.assertNotRegex(changes, r"(^|, )(?!0:|4:)\S+:")


if __name__ == "__main__":
    unittest.main()
