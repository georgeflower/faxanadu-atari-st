"""The ROM and the port side by side (tools/sidebyside.py, tools/refnes/botplay.mjs, src/replay.s).

A bot plays Eolis screen 4 in the ROM (the two Monodrons killed with the long sword, the bread picked up) and the port plays the same pads, one a pass of
the game's loop; every field of src/replay.s's record agrees in all 160 passes. The comparison itself is checked without an emulator."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sidebyside as sb  # noqa: E402

ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
TOS = Path(os.environ.get("TOS", ""))


def record(**fields) -> bytes:
    r = bytearray(sb.REC)
    r[0:2] = fields.get("x", 0).to_bytes(2, "big")
    r[6] = fields.get("screen", 0)
    for i in range(8):
        r[16 + i * 4] = 255
    return bytes(r)


class CompareTests(unittest.TestCase):
    def test_a_screen_change_a_pass_later_is_resynchronised(self) -> None:
        rom = sb.decode(b"".join(record(x=k, screen=0 if k < 5 else 1) for k in range(10)))
        port = sb.decode(b"".join(record(x=k + (1 if k >= 4 else 0), screen=0 if k < 4 else 1) for k in range(10)))
        c = sb.compare(rom, port)
        self.assertEqual(c["offsets"], [(0, 0), (4, 1)])
        self.assertEqual(c["first"], {})

    def test_a_difference_is_reported_with_its_frame(self) -> None:
        rom = sb.decode(b"".join(record(x=k) for k in range(6)))
        port = sb.decode(b"".join(record(x=k if k < 3 else k + 1) for k in range(6)))
        self.assertEqual(sb.compare(rom, port)["first"]["x"], (3, 3, 3, 4))


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("node") and shutil.which("m68k-linux-gnu-as") and TOS.is_file(),
                     "needs the ROM, node (tools/refnes), hatari, the m68k binutils and a TOS image (TOS)")
class SideBySideTests(unittest.TestCase):
    def test_the_port_plays_a_fight_as_the_rom_does_pass_for_pass(self) -> None:
        seg = json.loads((ROOT / "tools" / "segments" / "eolis4_fight.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "segment.json").write_text(json.dumps(seg), encoding="utf-8")
            pads, rom = sb.run_rom(out / "segment.json", out / "rom")
            port, _ = sb.Port(seg, pads, out / "hatari").trace()
        self.assertEqual(len(rom), 160)
        self.assertEqual(len(port), 160)
        self.assertGreaterEqual(rom[-1]["exp"], 60, "the bot killed both Monodrons")
        self.assertTrue(any(r["s5_ent"] == 1 for r in rom), "and one left bread")
        c = sb.compare(rom, port)
        self.assertEqual(c["first"], {}, sb.report(rom, port, pads))

    def play(self, name: str, frames: int | None = None):
        seg = json.loads((ROOT / "tools" / "segments" / f"{name}.json").read_text(encoding="utf-8"))
        if frames:
            seg["frames"] = frames
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "segment.json").write_text(json.dumps(seg), encoding="utf-8")
            pads, rom = sb.run_rom(out / "segment.json", out / "rom")
            port, _ = sb.Port(seg, pads, out / "hatari").trace()
        return pads, rom, port

    def test_a_coin_on_the_bottom_row_of_mist_bounces_as_in_the_rom(self) -> None:
        """Mist screen 33, Thunder: a coin falls to the screen's bottom row (y 192). The ROM's block test reads row 13 of what the screen's
        decoder wrote under the 13 rows, and the coin bounces there; the port took them for air and the coin fell out of the screen (package part
        screen_low). And Thunder after its hit is the ROM's type 6 (24 updates more)."""
        pads, rom, port = self.play("mist33_thunder")
        self.assertTrue(any(r["s4_ent"] == 2 and r["s4_y"] == 192 for r in rom), "a coin lands on the bottom row")
        self.assertTrue(any(r["spell"] == 6 for r in rom), "Thunder hit")
        self.assertGreater(rom[-1]["gold"], 0, "the coin was picked up")
        self.assertEqual(sb.compare(rom, port)["first"], {}, sb.report(rom, port, pads))

    def test_after_a_scroll_to_the_left_he_stands_at_x_240(self) -> None:
        """Eolis screen 4 to 5: Game_MovePlayerOnScrollLeft takes 16 off the 0 he ran off at (the port had 241). The enemies are compared only
        before the scroll: the ROM's enemies go on moving in the frames before the picture moves and their fractions are left in the slots
        (AGENTS.md 5k)."""
        pads, rom, port = self.play("eolis4_scroll_fight", 60)
        c = sb.compare(rom, port)
        k = next(i for i in range(1, len(rom)) if rom[i]["screen"] != rom[i - 1]["screen"])
        self.assertEqual((rom[k]["screen"], rom[k]["x"]), (5, 240))
        hero = {f: v for f, v in c["first"].items() if not f.startswith("s")}
        self.assertEqual(hero, {}, sb.report(rom, port, pads))
        self.assertTrue(all(v[0] >= k for f, v in c["first"].items()), sb.report(rom, port, pads))


if __name__ == "__main__":
    unittest.main()
