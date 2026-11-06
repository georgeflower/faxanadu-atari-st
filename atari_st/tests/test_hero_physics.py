"""The Python walking model against a golden run recorded from the ROM in jsnes (needs node, the harness's packages and your ROM)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class WalkingTests(unittest.TestCase):
    def test_walking_matches_the_rom_frame_by_frame(self) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import hero_physics as hp

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "walk.json"
            subprocess.run(["node", "walkgolden.mjs", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            frames = json.loads(out.read_text())
        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        blocks = fm.decode_screen(rom, a, 1)
        props = fm.block_properties(rom, a)
        impassable = [hp.IMPASSABLE[props[b] & 15] for b in blocks]
        first = frames[0]
        h = hp.Hero(x=first["x"], frac=first["frac"], y=first["y"], acc=first["acc"] | first["accU"] << 8, flags=first["flags"], tick=first["tick"],
                    title=first["title"], jump=first["jump"], status=first["status"])
        jumps = 0
        patched = False
        ladder = [0] * 208
        for n, f in enumerate(frames[1:], 1):
            joy = f["joy"]
            if f.get("set"):                                # the harness has put the hero somewhere; from the first time on the screen is changed too
                if not patched:
                    patched = True
                    ground, air = impassable[11 * 16], impassable[0]
                    for index in [8 * 16 + 3, 8 * 16 + 4, 7 * 16 + 6, 7 * 16 + 7] + [12 * 16 + c for c in range(8, 12)]:
                        impassable[index] = 1
                    for c in range(8, 12):
                        impassable[11 * 16 + c] = 0
                if f.get("ladder"):
                    for r in range(6, 11):
                        ladder[r * 16 + 13] = 1
                        impassable[r * 16 + 13] = 0
                h = hp.Hero(x=f["x"], frac=f["frac"], y=f["y"], acc=0, flags=f["flags"], tick=f["tick"], title=f["title"], jump=f["jump"], climb=f["climb"], status=f["status"])
                continue
            jumps += bool(f["flags"] & 1)
            hp.step(h, joy, f["changed"], impassable, ladder=ladder)
            got = (h.x, h.frac, h.y, h.acc, h.flags, h.tick, h.jump, h.climb, h.status, h.attack_timer, h.attack_frame)
            want = (f["x"], f["frac"], f["y"], f["acc"] | f["accU"] << 8, f["flags"], f["tick"], f["jump"], f["climb"], f["status"], f["atkTimer"], f["atkFrame"])
            self.assertEqual(got, want, f"frame {n}, joy {joy}")
        self.assertGreater(jumps, 60)                       # both jumps were really checked


if __name__ == "__main__":
    unittest.main()
