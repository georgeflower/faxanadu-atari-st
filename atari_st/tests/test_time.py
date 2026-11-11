"""The HUD's time (T:) in the ROM, recorded in jsnes by `tools/refnes/timeprobe.mjs`.

T: is the Wing Boots' seconds (UI_DrawTimeValue at $2058; nothing else in the ROM writes it). It is drawn when the boots are put on, at each second they lose
(the global InterruptCounter's low six bits 0) and, as 0, by every screen set-up (Screen_SetupNew -> UI_DrawHUD: doors, buildings, areas, the respawn);
nothing draws it when they run out, so the last 00 stays. The port's side is `items_tick`, `hud_set_time` and `enter_screen` (`tests/test_viewer.py`
`test_a_door_shows_the_time_as_00_until_the_next_second_of_the_wing_boots`)."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFNES = ROOT / "tools" / "refnes"
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
DIGIT0 = 0x30


@unittest.skipUnless(ROM.is_file() and shutil.which("node") and (REFNES / "node_modules" / "jsnes").is_dir() and (ROOT / "build" / "refnes" / "ram_labels.json").is_file(),
                     "needs the ROM, node, the jsnes harness and the RAM labels")
class TimeInTheRomTests(unittest.TestCase):
    def test_the_time_counts_the_wing_boots_and_a_door_draws_00(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "time.json"
            subprocess.run(["node", "timeprobe.mjs", str(out)], cwd=REFNES, check=True, capture_output=True)
            rec = json.loads(out.read_text())
        shown = lambda r: (r["t"][0] - DIGIT0) * 10 + r["t"][1] - DIGIT0 if r["t"][0] >= DIGIT0 else None
        for i in range(1, len(rec)):
            a, b = rec[i - 1], rec[i]
            if b["wb"] != a["wb"] and b["tag"] != "count2" and a["wb"] != 255:
                self.assertEqual(b["ic"] & 0x3F, 0, "a second is counted when the interrupt counter's six low bits are 0")
                self.assertEqual(shown(rec[i + 1]), b["wb"], "and drawn (the PPU has it a frame later)")
        door = [r for r in rec if r["tag"] == "after"]
        first = next(r for r in door if shown(r) is not None and r["screen"] == 1 and r["t"] != rec[-1 - len(door)]["t"])
        self.assertEqual(shown(first), 0, "the new screen's HUD shows 00")
        self.assertGreater(first["wb"], 0, "while the boots are on")
        redrawn = next(r for r in door if shown(r) not in (None, 0))
        self.assertEqual(shown(redrawn), redrawn["wb"], "the next second draws the seconds left again")


if __name__ == "__main__":
    unittest.main()
