"""The overscan test program opens the bottom border in Hatari's cycle-exact mode on a PAL (50 Hz) machine.

Needs Hatari and a 50 Hz TOS image: set TOS_PAL to the German EmuTOS (etos512de.img). Skipped otherwise; no TOS image is in the repository.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOS = Path(os.environ.get("TOS_PAL", ""))


@unittest.skipUnless(shutil.which("hatari") and TOS.is_file() and shutil.which("m68k-linux-gnu-as"),
                     "needs hatari, the m68k binutils and TOS_PAL (a German EmuTOS image)")
class OverscanTests(unittest.TestCase):
    def test_the_bottom_border_is_removed_every_frame(self) -> None:
        subprocess.run(["make", "-C", str(ROOT), "overscan"], check=True, capture_output=True)
        subprocess.run([sys.executable, str(ROOT / "tools" / "hatari_shot.py"), "--tos", str(TOS), "--prg",
                        str(ROOT / "build" / "OVERSCAN.PRG"), "--out", str(ROOT / "build" / "overscan.png"), "--lines", "240",
                        "--trace", "video_border_v", "--vbls", "450"], check=True, capture_output=True, timeout=600)
        log = (ROOT / "build" / "shots" / "hatari.log").read_text(errors="replace")
        removed = len(re.findall(r"^detect remove bottom$", log, re.M))
        self.assertGreater(removed, 300, f"the border was removed {removed} times (once a frame once the program runs)")


if __name__ == "__main__":
    unittest.main()
