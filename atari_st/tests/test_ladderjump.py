"""Jumping to a ladder whose bottom is above the hero's head (the author's report on Fax085: standing under such a ladder and jumping straight up
never caught it, only a diagonal jump did).

The ROM (`Player_CheckHandleJump`, `@_playerNotMoving`): in the air, when he is not moving left or right, Up or Down with a ladder at his head or
feet steps him to it at the standard speed, as on the ground, and once he is square on it `Player_CheckHandleVertMovement` lets him climb. So a
straight jump with Up held (from the press or pressed during the jump) catches a ladder from about half a block on either side of it; a diagonal
jump goes on the way it went and catches it only when it passes square on it. The model and the 68000 lacked the step in the air: only a hero
already square on the ladder caught it.

Golden runs from jsnes (`tools/refnes/ladderjump.mjs`) on five real screens, the hero at x & 15 = 0, 4, 8, 12 around the ladder: the Python
model (`tools/hero_physics.py`) frame by frame; then the 68000 in Hatari, frame by frame, with the disk's controls (JOYPAD: the stick's Up is the
jump and stays held) and with the raw NES-like mapping (Space is A, the stick is the pad). Needs node, the harness, the ROM; Hatari, the m68k
binutils and a TOS image (TOS) for the second part.
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
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (the TOS image)

HARNESS = ROM.is_file() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists()
HATARI = HARNESS and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()

# (area, region, screen, ladder column, the floor's y under it): every ladder whose bottom is one block over his head (found by scanning the maps)
# that has room to jump under it; 5/27 and 2/60 have a ceiling beside the ladder, so only a block's width there jumps at all.
SPOTS = ((1, 1, 6, 14, 160), (2, 2, 60, 12, 112), (6, 4, 3, 2, 160), (5, 3, 27, 9, 128), (1, 1, 44, 13, 144))
CASES = [["a_up", [[["A", "UP"], 1], [["UP"], 50]]],                        # A with Up held from the press (the disk's stick Up)
         ["a_then_up", [[["A"], 1], [[], 3], [["UP"], 50]]],                # Up pressed in the jump
         ["a_held_up_late", [[["A"], 6], [["UP", "A"], 50]]],
         ["a_only", [[["A"], 1], [[], 45]]],                                # no Up: no ladder
         ["right_a_up", [[["RIGHT", "A"], 1], [["RIGHT", "UP"], 50]]],      # the diagonal jumps
         ["left_a_up", [[["LEFT", "A"], 1], [["LEFT", "UP"], 50]]]]
_golden: list | None = None


def golden() -> list:
    """The jsnes runs (made once per test process, about a minute)."""
    global _golden
    if _golden is None:
        with tempfile.TemporaryDirectory() as tmp:
            spots = [dict(area=a, region=r, screen=s, y=y, xs=[c * 16 + d for d in (-12, -8, -4, 0, 4, 8, 12)], cases=CASES) for a, r, s, c, y in SPOTS]
            (Path(tmp) / "spots.json").write_text(json.dumps(spots), encoding="utf-8")
            subprocess.run(["node", "ladderjump.mjs", str(Path(tmp) / "spots.json"), str(Path(tmp) / "out.json")], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            _golden = json.loads((Path(tmp) / "out.json").read_text())
    return _golden


def grabbed(run: dict) -> int | None:
    """The first frame with the Climbing flag set."""
    return next((i for i, f in enumerate(run["frames"]) if f["flags"] & 0x10), None)


def screen_flags(area: int, screen: int) -> tuple[list[int], list[int]]:
    import faxanadu_maps as fm
    import faxanadu_rom as fr
    import hero_physics as hp

    rom = fr.Rom(ROM)
    a = fm.area(rom, area)
    props = fm.block_properties(rom, a)
    blocks = fm.decode_screen(rom, a, screen)
    return [hp.IMPASSABLE[props[b] & 15] for b in blocks], [hp.CLIMBABLE[props[b] & 15] for b in blocks][:208]


@unittest.skipUnless(HARNESS, "needs the ROM and the jsnes harness")
class RomAndModelTests(unittest.TestCase):
    def test_a_straight_jump_with_up_catches_a_ladder_over_his_head_in_the_rom(self) -> None:
        """What the ROM does, in numbers: under the ladder of Daybreak's screen 27 (column 9, no ceiling only at x 140 to 147) and Apolune's screen 44
        (column 13), A with Up catches it at x & 15 = 12, 0 (and 4, 8 on screen 44) in the second frame of the jump, Up pressed three frames into
        the jump in the fifth; he steps to x = the ladder's in the air and climbs; without Up he lands again."""
        runs = {(r["area"], r["screen"], r["x"], r["name"]): r for r in golden()}
        for area, screen, xs in ((5, 27, (140, 144)), (1, 44, (204, 208, 212))):
            for x in xs:
                with self.subTest(area=area, screen=screen, x=x):
                    up = runs[(area, screen, x, "a_up")]
                    self.assertEqual(grabbed(up), 2)
                    self.assertEqual(grabbed(runs[(area, screen, x, "a_then_up")]), 5)
                    self.assertEqual(up["frames"][-1]["x"], x & 0xF0 if x & 15 < 8 else (x & 0xF0) + 16)
                    self.assertLess(up["frames"][-1]["y"], up["frames"][0]["y"] - 32, "climbing above the jump's top")
                    self.assertIsNone(grabbed(runs[(area, screen, x, "a_only")]))
                    self.assertEqual(runs[(area, screen, x, "a_only")]["frames"][-1]["y"], up["frames"][0]["y"])

    def test_the_model_matches_every_run_frame_by_frame(self) -> None:
        import hero_physics as hp

        flags = {}
        stepped = 0
        for run in golden():
            key = (run["area"], run["screen"])
            if key not in flags:
                flags[key] = screen_flags(*key)
            impassable, ladder = flags[key]
            f0 = run["frames"][0]
            h = hp.Hero(x=f0["x"], frac=f0["frac"], y=f0["y"], acc=f0["acc"], flags=f0["flags"], tick=f0["tick"], title=f0["title"], jump=f0["jump"],
                        climb=f0["climb"], status=f0["status"], invinc=f0["invinc"])
            for n, f in enumerate(run["frames"][1:], 1):
                if f["screen"] != run["screen"]:
                    break                                           # (walked off the screen: the rest is the scroll)
                hp.step(h, f["joy"], f["changed"], impassable, ladder=ladder)
                got = (h.x, h.frac, h.y, h.acc, h.flags, h.tick, h.jump, h.climb)
                want = (f["x"], f["frac"], f["y"], f["acc"], f["flags"], f["tick"], f["jump"], f["climb"])
                self.assertEqual(got, want, f"area {run['area']} screen {run['screen']} x {run['x']} {run['name']}: frame {n}")
            g = grabbed(run)
            stepped += g is not None and run["x"] & 15 != 0 and run["name"] in ("a_up", "a_then_up")
        self.assertGreater(stepped, 20, "runs that catch the ladder from off it (the step in the air)")


class Port:
    """One build of the viewer on a screen and one Hatari run a start x: the hero's record (`hero_x`, 26 bytes) dumped at every VBL."""

    def __init__(self, area: int, screen: int, x0: int, y: int, joypad: bool):
        import hatari_shot as hs

        self.hs = hs
        defs = "--defsym NO_ENEMIES=1" + (" --defsym JOYPAD=1" if joypad else "")
        subprocess.run(["make", "-C", str(ROOT), "viewer", "ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={x0},{y},0,255,0,0,1", "HUD=16,0,0,0,0",
                        f"VIEWER_DEFS={defs}"], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        self.sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        self.work = ROOT / "build" / f"shots_ladderjump{area}_{screen}_{int(joypad)}"
        self.work.mkdir(parents=True, exist_ok=True)
        self.prg = ROOT / "build" / "VIEWER.PRG"
        self.hatari = shutil.which("hatari")
        (self.work / "c0.ini").write_text(f"savebin {self.work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(self.hatari, tv.TOS, self.prg, self.work, 500, "0", f"b VBL > 499 :once :file {self.work / 'c0.ini'}\n", None)
        self.base = (self.work / "ram0.bin").read_bytes().find(image[self.sym["start"]:self.sym["start"] + 48]) - self.sym["start"]
        assert self.base > 0

    def run(self, x: int, pokes: list[tuple[int, str, int]]) -> list[dict]:
        """He is put at x (standing) at VBL 590, then the pokes ("joy": the stick byte, "key": scan code << 8 | 1 down or 0 up); the record of
        every VBL from 595 to 660."""
        hero = self.base + self.sym["hero_x"]
        script = ""
        for i, (vbl, what, value) in enumerate([(590, "x", x)] + pokes):
            if what == "x":
                text = f"memwrite ${hero:x} 0x{x >> 8:02x} 0x{x & 255:02x}\n"
            elif what == "joy":
                text = f"memwrite ${self.base + self.sym['input_state'] + 259:x} 0x{value:02x}\n"
            else:
                text = f"memwrite ${self.base + self.sym['input_state'] + 264 + (value >> 8):x} 0x{value & 255:02x}\n"
            (self.work / f"poke{i}.ini").write_text(text + "cont\n", encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {self.work / f'poke{i}.ini'}\n"
        (self.work / "dump.ini").write_text(f"m ${hero:x}-${hero + 26:x}\ncont\n", encoding="utf-8")
        script += f"b VBL ! VBL && VBL > 594 && VBL < 661 :file {self.work / 'dump.ini'}\n"
        log = self.hs.run_hatari(self.hatari, tv.TOS, self.prg, self.work, 670, "0", script, None)
        data: list[bytearray] = []
        for line in log.splitlines():
            m = re.match(r"^([0-9A-Fa-f]{8}): ((?:[0-9a-f]{2} ){1,16})", line)
            if not m:
                continue
            if int(m.group(1), 16) == hero:
                data.append(bytearray())
            if data:
                data[-1] += bytes(int(b, 16) for b in m.group(2).split())
        word = lambda d, o: int.from_bytes(d[o:o + 2], "big")
        return [dict(x=word(d, 0), y=word(d, 2), right=word(d, 4), frac=word(d, 10), moving=word(d, 14), jump=word(d, 16), flags=word(d, 18) & 0xFF,
                     climb=word(d, 20)) for d in data]


@unittest.skipUnless(HATARI, "needs the ROM, the jsnes harness, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class PortTests(unittest.TestCase):
    """The 68000 against the ROM, frame by frame from the first frame of the jump for 40 frames: x, its fraction, y, the jump's index, the
    climbing fraction and the flags (the ROM's Moving bit is the port's moving word, its facing bit the port's facing word)."""

    FRAMES = 40

    def compare(self, port: list[dict], rom: dict, what: str) -> None:
        start = next((i for i, p in enumerate(port) if p["flags"] & 1), None)
        self.assertIsNotNone(start, f"{what}: the port never jumped")
        for n in range(self.FRAMES):
            f, p = rom["frames"][1 + n], port[start + n]
            want = (f["x"], f["frac"], f["y"], f["jump"], f["climb"], f["flags"] & 0x9F, bool(f["flags"] & 0x20))
            got = (p["x"], p["frac"], p["y"], p["jump"], p["climb"], p["flags"] & 0x9F, bool(p["moving"]))
            self.assertEqual(got, want, f"{what}: frame {n + 1} of the jump")
        self.assertEqual(grabbed(rom) is not None, any(p["flags"] & 0x10 for p in port[start:start + self.FRAMES]), what)

    def runs(self, area: int, screen: int) -> dict:
        return {(r["x"], r["name"]): r for r in golden() if (r["area"], r["screen"]) == (area, screen)}

    def check(self, joypad: bool, cases: dict) -> None:
        """cases: the ROM's case name -> the pokes that do it with this mapping (the press at VBL 602, polled in the frame after it)."""
        caught = 0
        for area, _, screen, column, y in SPOTS[3:]:
            rom = self.runs(area, screen)
            xs = sorted({x for x, _ in rom if x & 15 in (0, 4, 8, 12)})
            port = Port(area, screen, xs[0], y, joypad)
            for x in xs:
                for name, pokes in cases.items():
                    with self.subTest(area=area, screen=screen, x=x, case=name):
                        r = rom[(x, name)]
                        if not r["frames"][1]["flags"] & 1:
                            continue                                # a ceiling over him: no jump in the ROM either (the model test has these)
                        self.compare(port.run(x, pokes), r, f"area {area} screen {screen} x {x} {name}")
                        caught += grabbed(r) is not None and x & 15 != 0
        self.assertGreater(caught, 3, "runs that catch the ladder from off it")

    def test_the_disks_stick_up_under_a_ladder_jumps_and_catches_it_as_the_roms_a_and_up(self) -> None:
        """JOYPAD: the stick's Up is the jump (its press) and stays held: the ROM's A with Up held; Up and Right is the diagonal jump."""
        self.check(True, {"a_up": [(602, "joy", 1), (655, "joy", 0)], "right_a_up": [(602, "joy", 1 | 8), (655, "joy", 0)],
                          "left_a_up": [(602, "joy", 1 | 4), (655, "joy", 0)]})

    def test_the_raw_mapping_space_and_up_catches_it_as_the_rom_does(self) -> None:
        """Without JOYPAD: Space is A, the stick is the pad: A with Up, and Up pressed three frames into the jump."""
        space = lambda down: 0x39 << 8 | down
        self.check(False, {"a_up": [(602, "joy", 1), (602, "key", space(1)), (603, "key", space(0)), (655, "joy", 0)],
                           "a_then_up": [(602, "key", space(1)), (603, "key", space(0)), (606, "joy", 1), (655, "joy", 0)]})


if __name__ == "__main__":
    unittest.main()
