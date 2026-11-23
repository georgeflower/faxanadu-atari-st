"""The up-and-down ways out of a screen: Trunk screens 12 and 22.

The ROM (`Player_CheckSwitchScreen`): when the block at his x and the one at x + 15 (in the row of his y) are both of property 9, 10, 12 or 13 and
the second is 9 or 10, the area's list in `AREA_SCREEN_COMPARATORS` is searched for the screen. Only Trunk has one: screen 12 (the top of the
ladder in column 13, property 10 in row 0) leads to screen 22 with him at x 48, y 176 (on the ladder in column 3), and screen 22 (the bottom
of that ladder, row 12) back to screen 12 at x 208, y 32 (under the ladder, so he falls to the floor at y 64). Both are palette set 6, Trunk's.
It goes through `Game_SetupEnterScreen` as a door does, but without `Screen_FadeToBlack` and without a change of song: the picture is black at
once (rendering off) for 24 frames from screen 12 and 20 from 22, and of the hero only x and y change (his flags, the climbing bits too, his
facing and his ticks stay). The other screens with blocks of property 10 (ladders in Trunk 19, 51, 56, 58 and Dartmoor 11, 22) have no record:
nothing happens there.

The ROM's runs (`tools/refnes/knockedge.mjs` with "walk": "up"/"down") are compared with the port in Hatari, VBL by VBL. Needs the ROM, node and
the harness, Hatari, the m68k binutils and a TOS image (TOS).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_viewer as tv  # noqa: E402

HARNESS = tv.ROM.is_file() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists()
HATARI = HARNESS and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and tv.TOS.is_file()

# (the ROM's case, the stick byte for the port: 1 up, 2 down)
CASES = [({"screen": 12, "x": 208, "y": 16, "walk": "up", "hold": 200, "frames": 120}, 1),
         ({"screen": 22, "x": 48, "y": 176, "walk": "down", "hold": 200, "frames": 120}, 2)]
PRESS, LAST = 600, 720          # the port: the stick is pushed at VBL PRESS; the record of every VBL up to LAST


def black(f: dict) -> bool:
    return f["lit"] == 0


@unittest.skipUnless(HARNESS, "needs the ROM, node and the harness")
class RomTests(unittest.TestCase):
    rom: list = []

    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec, out = Path(tmp) / "cases.json", Path(tmp) / "out.json"
            spec.write_text(json.dumps([dict(area=1, region=1, **c) for c, _ in CASES]))
            subprocess.run(["node", "knockedge.mjs", str(spec), str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            cls.rom = json.loads(out.read_text())

    def arrival(self, i: int) -> tuple[int, dict, int]:
        """(the frame of the last picture before the black, the first frame with the new picture, the frames of black)."""
        frames = self.rom[i]["frames"]
        first = next(n for n, f in enumerate(frames) if black(f))
        back = next(n for n in range(first, len(frames)) if not black(frames[n]))
        return first - 1, frames[back], back - first

    def test_the_rom(self) -> None:
        up, down = self.arrival(0), self.arrival(1)
        self.assertEqual((up[1]["screen"], up[1]["x"], up[1]["y"]), (22, 48, 176))
        self.assertEqual((down[1]["screen"], down[1]["x"], down[1]["y"]), (12, 208, 32))
        self.assertEqual((up[2], down[2]), (24, 20), "black for 24 and 20 frames")
        for i in range(2):
            frames = self.rom[i]["frames"]
            self.assertEqual({(f["area"], f["palette"], f["music"], tuple(f["ppal"])) for f in frames}, {(1, 6, frames[0]["music"], tuple(frames[0]["ppal"]))},
                             "no fade, no other palette set, the same song")
        self.assertEqual(up[1]["flags"], 0x58, "the flags stay: facing right, can climb, climbing")
        self.assertEqual(down[1]["flags"], 0x58)
        self.assertEqual(self.rom[1]["frames"][-1]["y"], 64, "under the ladder of screen 12: he falls to the floor")


class Port:
    """One build of the viewer on a screen, one Hatari run: the hero's record (`hero_x`, 32 bytes), `cur_screen` and the first colours of the
    palette at every VBL from PRESS - 4 to LAST."""

    def __init__(self, screen: int, x: int, y: int, joy: int):
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", "AREA=1", f"SCREEN={screen}", f"HERO={x},{y},0,255,0,0,1", "HUD=16,0,0,0,0",
                        "VIEWER_DEFS=--defsym NO_ENEMIES=1"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / f"shots_vertway{screen}"
        work.mkdir(parents=True, exist_ok=True)
        prg, hatari = ROOT / "build" / "VIEWER.PRG", shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, tv.TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        assert base > 0
        hero, scr = base + sym["hero_x"], base + sym["cur_screen"]
        (work / "poke.ini").write_text(f"memwrite ${base + sym['input_state'] + 259:x} 0x{joy:02x}\ncont\n", encoding="utf-8")
        (work / "dump.ini").write_text(f"m ${hero:x}-${hero + 32:x}\nm ${scr:x}-${scr + 2:x}\nm $ff8240-$ff8248\ncont\n", encoding="utf-8")
        script = f"b VBL > {PRESS} :once :file {work / 'poke.ini'}\n"
        script += f"b VBL ! VBL && VBL > {PRESS - 5} && VBL < {LAST + 1} :file {work / 'dump.ini'}\n"
        log = hs.run_hatari(hatari, tv.TOS, prg, work, LAST + 10, "0", script, None)
        rows: list[dict] = []
        cur: dict[int, bytearray] = {}
        for line in log.splitlines():
            m = re.match(r"^([0-9A-Fa-f]{8}): ((?:[0-9a-f]{2} ){1,16})", line)
            if not m:
                continue
            a, data = int(m.group(1), 16), bytes(int(b, 16) for b in m.group(2).split())
            if a == hero:
                cur = {hero: bytearray(data)}
            elif a == hero + 16 and hero in cur:
                cur[hero] += data
            elif a == scr or a == 0xFF8240:
                cur[a] = bytearray(data)
                if a == 0xFF8240 and hero in cur and scr in cur:
                    d, w = cur[hero], lambda b, o: int.from_bytes(b[o:o + 2], "big")
                    rows.append(dict(x=w(d, 0), y=w(d, 2), right=w(d, 4), flags=w(d, 18) & 0xFF, screen=w(cur[scr], 0),
                                     black=all(w(data, o) & 0x777 == 0 for o in range(0, 8, 2))))
        self.rows = rows


@unittest.skipUnless(HATARI, "needs the ROM, node and the harness, hatari, the m68k binutils and a TOS image")
class PortTests(RomTests):
    def test_the_port_does_what_the_rom_does(self) -> None:
        for i, (case, joy) in enumerate(CASES):
            with self.subTest(case["screen"]):
                last, back, dark = self.arrival(i)
                rows = Port(case["screen"], case["x"], case["y"], joy).rows
                self.assertGreater(len(rows), 100)
                self.assertFalse(any(r["black"] for r in rows[:4]))
                first = next(n for n, r in enumerate(rows) if r["black"])
                ret = next(n for n in range(first, len(rows)) if not rows[n]["black"])
                self.assertEqual(rows[first - 1]["screen"], case["screen"], "the old screen up to the black")
                # the ROM still shows the picture of the frame that takes the way (y 15, 192), the port is black in it: one frame earlier
                self.assertEqual(rows[first - 1]["y"], self.rom[i]["frames"][last - 1]["y"], "the way is taken at the ROM's y")
                self.assertLessEqual(abs((ret - first) - dark), 2, f"black for {ret - first} VBLs, the ROM {dark}")
                r = rows[ret]
                self.assertEqual((r["screen"], r["x"], r["y"]), (back["screen"], back["x"], back["y"]), "where he arrives")
                self.assertEqual(r["flags"] & 0x18, back["flags"] & 0x18, "can climb and climbing stay")
                self.assertEqual((rows[0]["right"], r["right"]), (1, 1), "he faces right as before (as in the ROM's runs)")
                rom_after = [f["y"] for f in self.rom[i]["frames"][self.rom[i]["frames"].index(back):][:20]]
                self.assertEqual([q["y"] for q in rows[ret:ret + 20]], rom_after, "the frames after the arrival")


if __name__ == "__main__":
    unittest.main()
