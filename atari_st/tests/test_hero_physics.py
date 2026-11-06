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
        h = hp.Hero(x=first["x"], frac=first["frac"], y=first["y"], acc=first["acc"] | first["accU"] << 8, flags=first["flags"], tick=first["tick"], title=first["title"])
        for n, f in enumerate(frames[1:], 1):
            joy = f["joy"]
            hp.walk_step(h, joy, impassable)
            got = (h.x, h.frac, h.acc, h.flags, h.tick)
            want = (f["x"], f["frac"], f["acc"] | f["accU"] << 8, f["flags"], f["tick"])
            self.assertEqual(got, want, f"frame {n}, joy {joy}")


if __name__ == "__main__":
    unittest.main()
