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
        """Eolis screen 4 to 5: Game_MovePlayerOnScrollLeft takes 16 off the 0 he ran off at (the port had 241). And the enemies: the pass that scrolls
        gives the old ones one update more (Sprites_UpdateAll runs after the hero's step) and the new screen's keep the slots' fractions (AGENTS.md 5k);
        the port stopped them and cleared the fractions, and the new ones were a pixel off now and then."""
        pads, rom, port = self.play("eolis4_scroll_fight", 60)
        c = sb.compare(rom, port)
        k = next(i for i in range(1, len(rom)) if rom[i]["screen"] != rom[i - 1]["screen"])
        self.assertEqual((rom[k]["screen"], rom[k]["x"]), (5, 240))
        self.assertNotEqual(rom[k]["s7_xf"], 0, "a fraction the old enemy left")
        self.assertEqual(c["first"], {}, sb.report(rom, port, pads))

    def test_a_scroll_up_keeps_the_enemies_as_in_the_rom(self) -> None:
        """Trunk screen 3, up the ladder to screen 4: the new screen's enemies keep the old ones' x and y fractions, and a hopper falls through the cells
        under the 13 rows (row 13 of the screen buffer, en_low_bit: it gave "blocked" for any cell there, the flags of a move were read after a move.l,
        and the words of screen n were looked for at n * 2, not n * 4)."""
        pads, rom, port = self.play("trunk3_scroll_up")
        c = sb.compare(rom, port)
        self.assertEqual([rom[k]["screen"] for k in (0, -1)], [3, 4])
        self.assertTrue(any(r["s7_ent"] == 0x2A and r["s7_y"] > 192 for r in rom), "the hopper falls under the 13 rows")
        self.assertEqual(c["first"], {}, sb.report(rom, port, pads))

    def test_a_scroll_to_the_right_keeps_the_enemies_as_in_the_rom(self) -> None:
        pads, rom, port = self.play("eolis5_scroll_right")
        self.assertEqual([rom[k]["screen"] for k in (0, -1)], [5, 4])
        self.assertEqual(sb.compare(rom, port)["first"], {}, sb.report(rom, port, pads))

    def test_a_scroll_down_keeps_the_enemies_as_in_the_rom(self) -> None:
        """Mist screen 63, down a hole to screen 72. Only the enemies' fields: the hero's x, its fraction and acceleration are off from the pass that
        scrolls (a fall into a scroll down; AGENTS.md 5k, Left)."""
        pads, rom, port = self.play("mist63_scroll_down")
        self.assertEqual([rom[k]["screen"] for k in (0, -1)], [63, 72])
        enemies = {f: v for f, v in sb.compare(rom, port)["first"].items() if f.startswith("s")}
        self.assertEqual(enemies, {}, sb.report(rom, port, pads))

    def test_the_enemies_stay_on_the_picture_for_most_of_the_scrolls_wait(self) -> None:
        """The ROM draws the sprites of the pass that scrolls about 8 frames into the wait (the new screen's blocks are decoded first) and clears them
        two frames later; the hero stays (tools/refnes/botplay.mjs, UPDATES). The port: frames 1 to 11 with the enemies, 12 to 14 the hero alone, then
        the picture moves. Captured every VBL from the pass that scrolls: the enemies' part of the playfield (x 64 on) differs from the bare screen,
        then only the hero's does, for at least four VBLs before the first step."""
        import faxanadu_rom as fr
        import st_convert as sc
        seg = json.loads((ROOT / "tools" / "segments" / "eolis4_scroll_fight.json").read_text(encoding="utf-8"))
        seg["frames"] = 40
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "segment.json").write_text(json.dumps(seg), encoding="utf-8")
            pads, rom = sb.run_rom(out / "segment.json", out / "rom")
            p = sb.Port(seg, pads, out / "hatari")
            port, off = p.trace()
            k = next(i for i in range(1, len(port)) if port[i]["screen"] != port[i - 1]["screen"])
            v = port[k - 1]["vbl"] + off
            caps = p.captures([v + d for d in range(22)], "wait")
        r = fr.Rom(ROM)
        seen = []
        for ram, rows, _ in caps:
            word = lambda name: int.from_bytes(ram[p.base + p.sym[name]:p.base + p.sym[name] + 2], "big")
            if word("pending_offset"):
                break
            bare = sc.expected_screen(r, 0, 4, word("camera"))
            far = any(rows[y][x] != bare[y][x] for y in range(200) for x in range(64, 288))
            near = any(rows[y][x] != bare[y][x] for y in range(200) for x in range(32, 64))
            seen.append((far, near))
        self.assertTrue(all(near for _, near in seen), "the hero is on show all the time")
        first = seen.index((False, True))
        self.assertGreaterEqual(first, 9, seen)
        self.assertTrue(all(not far for far, _ in seen[first:]), seen)
        self.assertGreaterEqual(len(seen) - first, 4, seen)

    def test_ripasheiku_flies_shoots_and_dies_as_in_the_rom(self) -> None:
        """Mist screen 51. The port put the boss in step 1 at its placing and the first SWITCH_BEHAVIOR added one more: it fell, then stood and shot from
        the second pass, while the ROM's walks and climbs. Then the bolt: the ROM's hits the hero's shield (Player_CheckShieldHitByMagic, which the port
        did not have) and costs 28 >> 3 with the Magic Shield. The whole fight agrees and the boss dies (90 experience, its gold)."""
        pads, rom, port = self.play("boss_ripasheiku")
        c = sb.compare(rom, port)
        self.assertEqual(c["first"], {}, sb.report(rom, port, pads))
        self.assertEqual(rom[-1]["s7_ent"], 255, "the boss is gone")
        self.assertEqual(rom[-1]["exp"], 90)

    def test_king_grieves_bolts_hit_the_shield_as_in_the_rom(self) -> None:
        """Dartmoor: the one line his y was off came from the bolt that the ROM's shield stops (the knock-back moved the hero, not the boss's leap)."""
        pads, rom, port = self.play("boss_king_grieve", 700)
        c = sb.compare(rom, port)
        self.assertEqual(c["first"], {}, sb.report(rom, port, pads))


if __name__ == "__main__":
    unittest.main()
