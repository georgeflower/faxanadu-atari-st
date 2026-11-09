"""The game's flow (src/flow.s) in Hatari: a new game from the title, the temple a death leads to, boss rooms, the ending.

The ROM's tables and rules are in the code's comments; the numbers here are from the Europe ROM and the disassembly (the temple table, the ending's frame counts,
EndGame_MovePlayerTowardKing). Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS), like tests/test_viewer.py.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (the TOS image, the boxes of text)

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()
UP, DOWN, LEFT, RIGHT, FIRE = 1, 2, 4, 8, 0x80


class Shot:
    def __init__(self, run: "Run", ram: bytes, rows, video: int, palette: list[int]):
        self.run, self.ram, self.rows, self.video, self.palette = run, ram, rows, video, palette

    def at(self, name: str, offset: int = 0, size: int = 2, signed: bool = True) -> int:
        a = self.run.base + self.run.sym[name] + offset
        return int.from_bytes(self.ram[a:a + size], "big", signed=signed)

    def raw(self, name: str, n: int) -> bytes:
        a = self.run.base + self.run.sym[name]
        return self.ram[a:a + n]


class Run:
    """One build and one Hatari run. Pokes: (vbl, what, value) with what "joy" (the stick byte), "key" (a scan code << 8 | 1 or 0), "w:label[+offset]" (a word) or "b:label[+offset]" (a byte); captures are VBLs."""

    def __init__(self, make_args: list[str], pokes: list[tuple[int, str, int]], captures: list[int], name: str):
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer", *make_args], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        self.sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / name
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, tv.TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        self.base = (work / "ram0.bin").read_bytes().find(image[self.sym["start"]:self.sym["start"] + 48]) - self.sym["start"]
        assert self.base > 0
        script = ""
        for i, (vbl, what, value) in enumerate(pokes):
            if what == "joy":
                text = f"memwrite ${self.base + self.sym['input_state'] + 259:x} 0x{value:02x}\ncont\n"
            elif what == "key":                                        # any key by scan code: value = scan code << 8 | 1 (down) or 0 (up)
                text = f"memwrite ${self.base + self.sym['input_state'] + 264 + (value >> 8):x} 0x{value & 255:02x}\ncont\n"
            else:
                symbol, _, offset = what[2:].partition("+")
                at = self.base + self.sym[symbol] + int(offset or 0)
                text = (f"memwrite ${at:x} 0x{(value >> 8) & 255:02x} 0x{value & 255:02x}\ncont\n" if what[0] == "w" else f"memwrite ${at:x} 0x{value & 255:02x}\ncont\n")
            (work / f"poke{i}.ini").write_text(text, encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'poke{i}.ini'}\n"
        for i, vbl in enumerate(captures):
            (work / f"cap{i}.ini").write_text(f"savebin {work / f'ram_{i}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'cap{i}.ini'}\n"
        log = hs.run_hatari(hatari, tv.TOS, prg, work, max(captures) + 1, "0", script, None)
        chunks = re.split(r"(?m)^(?=00FF8200:)", log)[1:]
        assert len(chunks) == len(captures), "every capture's dump of the video registers is in the log"
        self.shots = []
        for i, chunk in enumerate(chunks):
            ram = (work / f"ram_{i}.bin").read_bytes()
            base = hs.video_base(chunk)
            self.shots.append(Shot(self, ram, hs.decode_screen(ram, base), base, hs.read_palette(chunk)))


def diag(shot: Shot) -> dict:
    return {n: shot.at(n) for n in ("cur_area", "cur_screen", "hero_x", "hero_y", "hero_dead", "cur_music", "flow_event", "end_state", "hourglass")} | {"hp": shot.raw("hud_state", 2).hex()}


def mismatch(rows, expected) -> list:
    return [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]][:5]


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class FlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    # ------------------------------------------------------------------------------------------------------ a new game
    def test_start_on_the_title_begins_the_roms_new_game(self) -> None:
        """NEWGAME=1 (the disk build): START plays the intro and then Eolis screen 0 is there, the hero at x 16, y 144 facing right, power 16, magic 0, no experience or
        gold, rank 0, leather armour and nothing else, the first spawn point, Eolis's song, no timers (Game_Start, Game_LoadFirstLevel, Player_SetStartGameState)."""
        import st_convert as sc

        run = Run(["ALL=1", "AREA=0", "SCREEN=1", "VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1"],
                  [(480, "joy", FIRE), (484, "joy", 0)], [2300], "shots_flow_new_game")
        (shot,) = run.shots
        self.assertEqual((shot.at("cur_area"), shot.at("cur_pal"), shot.at("cur_screen")), (0, 0, 0))
        self.assertEqual((shot.at("hero_x"), shot.at("hero_y"), shot.at("hero_flip")), (16, 144, 1))
        self.assertEqual(shot.raw("hud_state", 10), bytes([16, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        self.assertEqual((shot.at("hero_title"), shot.at("hero_next"), shot.at("hero_spawn")), (0, 0, 0))
        self.assertEqual((shot.at("hero_weapon"), shot.at("hero_magic")), (255, -1))
        inv = shot.raw("inv", 38)
        self.assertEqual(list(inv[:31]), [0] * 31, "no lists, no special items, no quests")
        self.assertEqual((inv[31], inv[32], inv[34], inv[35], inv[36]), (255, 255, 0, 255, 255), "no glove or ointment in force, leather armour, no shield, no item")
        self.assertEqual((shot.at("hourglass"), shot.at("hero_wings"), shot.at("cur_music")), (-1, -1, 7))
        expected = sc.expected_screen(self.rom, 0, 0, shot.at("camera"), hero=sc.Hero(16, 144, 0, 255, 255, 0, True))
        self.assertEqual(mismatch(shot.rows, expected), [], "Eolis screen 0 with the new hero and the HUD of a new game")


    def test_the_disk_build_has_no_test_keys(self) -> None:
        """NEWGAME=1 (the disk build) leaves out the test keys: H and G (hurt), M (the next spell), P (the mantra in a box), F1 and the digit keys (songs and sounds)
        do nothing in play; the same keys held for the same time do work in the build the other tests use (the control: H takes power)."""
        keys = [(0x23, "H"), (0x22, "G"), (0x32, "M"), (0x19, "P"), (0x3B, "F1"), (0x02, "1")]
        pokes = [(480, "joy", FIRE), (484, "joy", 0)] + [(2320, "key", k << 8 | 1) for k, _ in keys]
        defs = "--defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1 --defsym NO_ENEMIES=1"
        run = Run(["ALL=1", "AREA=0", "SCREEN=1", f"VIEWER_DEFS=--defsym NEWGAME=1 {defs}"], pokes, [2300, 2400], "shots_flow_no_keys")
        before, after = run.shots
        self.assertEqual((before.at("cur_screen"), before.raw("hud_state", 1), after.raw("hud_state", 1)), (0, bytes([16]), bytes([16])), "in play, power 16")
        self.assertEqual((after.at("hero_invinc"), after.at("hero_magic"), after.at("hero_dead")), (0, -1, 0), "H, G and M did nothing")
        self.assertEqual((after.raw("pw_text", 1), after.raw("snd_state", 48)[46:]), (b"\0", before.raw("snd_state", 48)[46:]), "no mantra box, no sound started by a key")
        run = Run(["ALL=1", "AREA=0", "SCREEN=1", "HUD=80,80,0,0,0", f"VIEWER_DEFS=--defsym FLOW=1 {defs.replace('--defsym MENU=1 ', '')}"], [(2320, "key", 0x2301)], [2400], "shots_flow_keys")
        (after,) = run.shots
        self.assertLess(after.raw("hud_state", 1)[0], 80, "the control: without NEWGAME the H key hurts")

    # ------------------------------------------------------------------------------------------------------ CONTINUE
    def test_continue_with_a_mantra_starts_the_game_in_the_temple_of_its_spawn_point(self) -> None:
        """The disk build: Down and Start on the title take CONTINUE, a mantra for spawn point 3 (rank 2, the Hand Dagger and leather armour, the Deluge spell)
        is typed on the entry grid and END takes it. The game begins as after a death: inside the temple of the third town (area 4, building 30's people, palette set
        18, x 224, y 144, facing left, song 14), power and magic 80, the experience and gold of rank 2, the spell and the equipment of the mantra, the spawn point
        kept; walking out of the room leads to Mist screen 6 at x 144, y 128 with the area's song."""
        import password_model as pm
        import st_convert as sc

        mantra = pm.password(pm.State(3, 2, 0, 0, 0, 0, pm.UNSET, 0, pm.UNSET, weapons=[0], armors=[0], spells=[0]))
        cont = [(480, "joy", DOWN), (484, "joy", 0), (490, "joy", FIRE), (494, "joy", 0)]
        pokes, end = tv.ViewerTests.typing(mantra, 560)
        out = [(end + 400, "w:hero_x", 240), (end + 401, "joy", RIGHT), (end + 404, "joy", 0)]
        run = Run(["ALL=1", "AREA=0", "SCREEN=1", "WORLD=2", "VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1 --defsym NO_ENEMIES=1"],
                  cont + pokes + out, [end + 300, end + 700], "shots_flow_continue")
        inside, outside = run.shots
        self.assertEqual((inside.at("hero_title"), inside.at("hero_next"), inside.at("hero_spawn"), inside.at("hero_magic"), inside.at("hero_weapon")), (2, 2, 3, 0, 0))
        self.assertEqual((inside.at("cur_area"), inside.at("cur_pal"), inside.at("cur_screen")), (4, 18, 0), "the building of the temple")
        self.assertEqual((inside.at("building_id"), inside.at("hero_x"), inside.at("hero_y"), inside.at("hero_flip")), (30, 224, 144, 0), diag(inside))
        self.assertEqual((inside.at("cur_music"), inside.at("hero_dead")), (14, 0))
        self.assertEqual(inside.raw("hud_state", 2), bytes([80, 80]), "power and magic 80")
        self.assertEqual((inside.at("hud_state", 2), inside.at("hud_state", 6)), (2200, 800), "the experience and gold of rank 2")
        self.assertEqual((inside.at("saved_area"), inside.at("saved_pal"), inside.at("saved_screen"), inside.at("saved_pos")), (2, 10, 6, 0x80 | 9))
        state = dict(hp=80, mp=80, experience=2200, gold=800, seconds=0)
        expected = sc.expected_screen(self.rom, 4, 1, inside.at("camera"), palette_index=18, tiles_index=6, state=state, hero=sc.Hero(224, 144, 0, 255, 255, 0, False))
        bad = [(x, y) for y in range(200) for x in range(320) if inside.rows[y][x] != expected[y][x]]
        self.assertTrue(bad and all(66 <= x < 114 and 118 <= y < 156 for x, y in bad), f"only the Guru differs from the plain room: {bad[:5]}")
        self.assertEqual((outside.at("cur_area"), outside.at("cur_pal"), outside.at("cur_screen")), (2, 10, 6), diag(outside))
        self.assertEqual((outside.at("hero_x"), outside.at("hero_y"), outside.at("hero_flip"), outside.at("cur_music")), (144, 128, 1, 5))

    # ------------------------------------------------------------------------------------------------------ death
    TEMPLE = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=128,144,0,255,0,0,1", "HUD=80,80,0,0,0",
              "VIEWER_DEFS=--defsym DAMAGE=80 --defsym TITLE=2 --defsym FLOW=1 --defsym NO_ENEMIES=1"]
    H_KEY = 0x23

    def die(self, spawn: int, world: str, extra: list, captures: list[int], name: str) -> Run:
        """He is hit for 80 at VBL 600 (the H key), the death takes 256 passes, the message waits for a button (A at 1000)."""
        pokes = [(300, "w:hero_spawn", spawn), (599, "key", self.H_KEY << 8 | 1), (600, "key", self.H_KEY << 8), (1000, "joy", FIRE), (1010, "joy", 0)] + extra
        return Run([*self.TEMPLE, f"WORLD={world}"], pokes, captures, name)

    def check_temple(self, shot: Shot, spawn: int) -> None:
        import st_convert as sc

        area, screen, x, y = {0: (0, 2, 80, 144), 1: (3, 1, 80, 144), 2: (3, 3, 48, 144), 3: (2, 6, 144, 128)}[spawn]
        self.assertEqual((shot.at("cur_area"), shot.at("cur_pal"), shot.at("cur_screen")), (4, 18, 0), "the building of the temple")
        self.assertEqual((shot.at("hero_x"), shot.at("hero_y"), shot.at("hero_flip")), (224, 144, 0), "inside: x 224, y 144, facing left")
        self.assertEqual(shot.at("cur_music"), 14)
        self.assertEqual(shot.raw("hud_state", 10)[:2], bytes([80, 80]), "power and magic 80")
        self.assertEqual((shot.at("hud_state", 2), shot.at("hud_state", 6)), (2200, 800), "the experience and gold of rank 2")
        self.assertEqual((shot.at("saved_area"), shot.at("saved_screen"), shot.at("saved_pos")), (area, screen, (y & 0xF0) | (x >> 4)))
        self.assertEqual((shot.at("hourglass"), shot.at("hero_wings")), (-1, -1))
        state = dict(hp=80, mp=80, experience=2200, gold=800, seconds=0)
        expected = sc.expected_screen(self.rom, 4, 1, shot.at("camera"), palette_index=18, tiles_index=6, state=state, hero=sc.Hero(224, 144, 0, 255, 255, 0, False))
        self.assertEqual(mismatch(shot.rows, expected), [], "the temple with the hero in it")

    def test_a_death_leads_to_the_temple_of_spawn_point_0_and_its_door_to_eolis(self) -> None:
        """Spawn point 0 (Eolis): he is in the building of the temple (area 4, building 1: palette set 18, x 224, y 144, facing left, song 14), power and magic 80, the
        experience and gold of rank 2; the way out is Eolis screen 2 at x 80, y 144 (the ROM's temple table); walking off the side of the room leads there, facing right,
        with Eolis's song."""
        import st_convert as sc

        x_off = [(1200, "w:hero_x", 240), (1201, "joy", RIGHT), (1204, "joy", 0)]
        run = self.die(0, "1", x_off, [1150, 1400], "shots_flow_temple0")
        inside, outside = run.shots
        self.check_temple(inside, 0)
        self.assertEqual((outside.at("cur_area"), outside.at("cur_pal"), outside.at("cur_screen")), (0, 0, 2))
        self.assertEqual((outside.at("hero_x"), outside.at("hero_y"), outside.at("hero_flip"), outside.at("cur_music")), (80, 144, 1, 7))
        state = dict(hp=80, mp=80, experience=2200, gold=800, seconds=0)
        expected = sc.expected_screen(self.rom, 0, 2, outside.at("camera"), state=state, hero=sc.Hero(80, 144, 0, 255, 0, 0, True))
        self.assertEqual(mismatch(outside.rows, expected), [], "Eolis screen 2 again")

    def test_the_respawn_fades_the_picture_out_in_four_steps_before_the_temple(self) -> None:
        """Player_Spawn's Screen_FadeToBlack: after the death message the picture goes to black in four steps (a quarter darker every 5th frame), then the temple is drawn;
        the ROM has no fade in."""
        run = self.die(0, "1", [], [990] + list(range(1011, 1060, 3)) + [1250], "shots_flow_respawn_fade")
        full = run.shots[0].palette

        def step(n: int) -> list[int]:
            def dim(c: int) -> int:
                return c * (4 - n) // 4
            return [(dim(c >> 8 & 15) << 8) | (dim(c >> 4 & 15) << 4) | dim(c & 15) for c in full]

        seen = {tuple(sh.palette) for sh in run.shots[1:-1]}
        for n in (1, 2, 3, 4):
            self.assertIn(tuple(step(n)), seen, f"fade step {n} was on the screen")
        self.assertEqual((run.shots[-1].at("cur_area"), run.shots[-1].at("cur_music")), (4, 14), "and then the temple")

    def test_spawn_point_3_is_the_temple_of_fog_and_leads_to_mist_screen_6_with_the_areas_song(self) -> None:
        """Spawn point 3 (the third town): the way out is area 2 screen 6 at x 144, y 128 in palette set 10, and the song after it is AREA_TO_MUSIC_TABLE[2] = 5."""
        x_off = [(1200, "w:hero_x", 240), (1201, "joy", RIGHT), (1204, "joy", 0)]
        run = self.die(3, "2", x_off, [1150, 1700], "shots_flow_temple3")
        inside, outside = run.shots
        self.check_temple(inside, 3)
        self.assertEqual((inside.at("saved_pal"), inside.at("flow_exit")), (10, 5))
        self.assertEqual((outside.at("cur_area"), outside.at("cur_pal"), outside.at("cur_screen")), (2, 10, 6))
        self.assertEqual((outside.at("hero_x"), outside.at("hero_y"), outside.at("hero_flip")), (144, 128, 1))
        self.assertEqual((outside.at("cur_music"), outside.at("flow_exit")), (5, 0))

    # ------------------------------------------------------------------------------------------------------ doors
    def test_a_door_fades_the_picture_to_black_in_four_steps_before_the_next_screen(self) -> None:
        """Screen_FadeToBlack: the palette a quarter darker every 5th frame (the counter adds $32 a frame, a step at 5.12), black after four; then the new screen."""
        run = Run(["ALL=1", "SCREEN=0", "HERO=192,144,0,255,0,0,1", "VIEWER_DEFS=--defsym FLOW=1 --defsym NO_ENEMIES=1"],
                  [(599, "joy", UP), (602, "joy", 0)], [590] + list(range(603, 660, 4)) + [800], "shots_flow_door")
        full = run.shots[0].palette

        def step(n: int) -> list[int]:
            def dim(c: int) -> int:
                return c * (4 - n) // 4
            return [(dim(c >> 8 & 15) << 8) | (dim(c >> 4 & 15) << 4) | dim(c & 15) for c in full]

        seen = {tuple(s.palette) for s in run.shots[1:-1]}
        for n in (1, 2, 3, 4):
            self.assertIn(tuple(step(n)), seen, f"fade step {n} was on the screen")
        last = run.shots[-1]
        self.assertEqual((last.at("cur_screen"), last.at("hero_x"), last.at("hero_y")), (1, 144, 144))
        self.assertEqual(last.palette, full)

    # ------------------------------------------------------------------------------------------------------ boss rooms
    BOSS = ["ALL=1", "AREA=1", "SCREEN=21", "HERO=16,144,0,255,0,0,1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym FLOW=1"]

    def test_a_boss_room_plays_the_boss_song_cuts_the_ointment_and_the_hour_glass_and_the_song_comes_back_when_the_boss_is_gone(self) -> None:
        """Area 1 screen 21 (Trunk, the area's song 3) has the special event 1: on its first tick the song is 10 (ScreenEvents_HandleBoss) and the Ointment and the Hour
        Glass are set to 0 (LimitItemDurations; here the first tick is run again with both in force, the time counter set so that none of them ticks meanwhile); when no
        boss is on the screen the area's song comes back and the event is over."""
        pokes = [(740, "b:inv+32", 20), (740, "w:hourglass", 10), (740, "w:item_ticks", 1), (740, "w:flow_event", 1)]
        pokes += [(775, f"b:enemies+{i * 30}", 255) for i in range(8)]
        run = Run(self.BOSS, pokes, [600, 735, 770, 795], "shots_flow_boss")
        start, before, capped, gone = run.shots
        self.assertEqual((start.at("cur_music"), start.at("flow_event")), (10, 0x81), "the boss song from the first tick; the event's first tick is done")
        self.assertEqual((before.raw("inv", 33)[32], before.at("hourglass")), (255, -1), "nothing in force before")
        self.assertEqual((capped.raw("inv", 33)[32], capped.at("hourglass"), capped.at("cur_music")), (0, 0, 10), "the Ointment and the Hour Glass cut to 0")
        self.assertEqual((gone.at("cur_screen"), gone.at("cur_music"), gone.at("flow_event")), (21, 3, 0xFF), f"the boss is gone: the area's song {diag(gone)}")

    def test_scrolling_out_of_a_boss_room_brings_the_areas_song_back(self) -> None:
        pokes = [(330, "joy", LEFT), (400, "joy", 0)]
        run = Run([a if not a.startswith("HERO=") else "HERO=32,48,0,255,0,0,1" for a in self.BOSS], pokes, [320, 700], "shots_flow_boss_out")
        inside, outside = run.shots
        self.assertEqual((inside.at("cur_screen"), inside.at("cur_music")), (21, 10))
        self.assertEqual((outside.at("cur_screen"), outside.at("cur_music"), outside.at("flow_event")), (20, 3, 0xFF), diag(outside))

    # ------------------------------------------------------------------------------------------------------ the ending
    def test_the_ending_begins_when_the_last_sprite_of_the_final_boss_screen_is_gone(self) -> None:
        """With Shadow Eura on the screen nothing happens; when the slots are empty (the boss and its bolts and what it dropped) the ending begins."""
        pokes = [(300, f"b:enemies+{i * 30}", 255) for i in range(8)]
        run = Run(["ALL=1", "AREA=7", "SCREEN=0", "HERO=100,144,0,255,0,0,1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym FLOW=1 --defsym SPLASH=1 --defsym NO_TITLE=1"],
                  pokes, [290, 330], "shots_flow_final_boss")
        before, after = run.shots
        slots = [before.raw("enemies", 240)[i * 30] for i in range(8)]
        self.assertEqual((before.at("end_state"), any(k != 255 for k in slots)), (0, True), f"the boss is there {slots} {diag(before)}")
        self.assertEqual((after.at("end_state"), after.at("cur_music")), (1, 7))

    FINAL = ["ALL=1", "AREA=7", "SCREEN=0", "HERO=100,144,0,255,0,0,1", "HUD=80,80,0,0,0"]

    def test_esc_in_the_black_frames_of_the_ending_leaves_at_once(self) -> None:
        """The 120 black frames before the King's room used to read no key: Esc (IN_QUIT, the byte the keyboard code sets) now ends the wait and the program leaves (its memory is
        TOS's again at the second capture, after the wait would have ended); without it the King's room would be loaded and the hero walking."""
        pokes = [(300, f"b:enemies+{i * 30}", 255) for i in range(8)] + [(480, "b:input_state+262", 255)]
        run = Run([*self.FINAL, "VIEWER_DEFS=--defsym FLOW=1 --defsym SPLASH=1 --defsym NO_TITLE=1"], pokes, [470, 600], "shots_flow_ending_esc")
        black, after = run.shots
        self.assertEqual((black.at("end_state"), black.at("cur_area")), (1, 7), "in the black frames")
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        at = run.sym["start"]
        n = 8000           # (the desktop does not necessarily reuse the program's first bytes: look further in; without Esc the same 8,000 bytes are unchanged at the capture)
        self.assertNotEqual(after.raw("start", n), image[at:at + n], "the program has left (TOS has used its memory again)")
        self.assertEqual(black.raw("start", 48), image[at:at + 48], "and it was there before")

    def test_a_walk_to_the_king_that_takes_too_long_goes_on_with_his_message(self) -> None:
        """The walk has a time limit: end_count runs out (set to 1 here, the hero is still far from the King) and the King's script is started from where he stands;
        A through it, then the outro. Without a person in the room (slots emptied) the outro starts at once."""
        pokes = [(v, "key", 0x3901) for v in range(620, 3000, 40)] + [(v + 6, "key", 0x3900) for v in range(620, 3000, 40)]
        base = ["ALL=1", "AREA=7", "SCREEN=0", "HERO=100,144,0,255,0,0,1", "HUD=80,80,0,0,0",
                "VIEWER_DEFS=--defsym NEWGAME=1 --defsym NPCS=1 --defsym MENU=1 --defsym NO_TITLE=1 --defsym NO_ENEMIES=1"]
        run = Run(base, pokes + [(560, "w:end_count", 1)], [555, 600, 700, 2500], "shots_flow_walk_timeout")
        room, started, message, outro = run.shots
        self.assertEqual((room.at("end_state"), room.at("cur_area"), room.at("end_stage")), (2, 4, 0), f"the King's room, walking {diag(room)}")
        self.assertEqual((started.at("end_state"), started.at("end_stage")), (2, 1), "the time ran out: the message")
        self.assertGreater(message.at("hero_x"), 0x60, "he never walked to the King")
        self.assertEqual((outro.at("end_state"), outro.at("sp_phase")), (0, 3), "FINISH_GAME: the outro plays")
        empty = [(556, "b:npc_slots", 255), (556, "b:npc_slots+16", 255), (560, "w:end_count", 1)]
        run = Run(base, empty, [555, 600, 800], "shots_flow_walk_timeout2")
        room, waiting, outro = run.shots
        self.assertEqual((room.at("end_state"), room.at("end_stage")), (2, 0))
        self.assertEqual((waiting.at("end_state"), waiting.at("end_stage")), (0, 1), f"no King: nothing to start, the outro follows at once {diag(waiting)}")
        self.assertEqual((outro.at("end_state"), outro.at("sp_phase")), (0, 3), "and plays")

    def test_the_final_boss_leads_to_the_ending_the_kings_room_the_message_the_outro_and_the_title(self) -> None:
        """Evil Fortress screen 0 (special event 2): when no sprite is left the song is Eolis's, the game stands 120 frames, the screen fades (4 steps) and stays black for
        120 frames, then the King's room (area 4, building 0: palette set 17, song 13, hero at x 208, y 144 facing left, people placed by id $44) and the hero walks left
        by himself (EndGame_MovePlayerTowardKing) until x < $44, where Up starts the King's script: message $A4 and FINISH_GAME, which plays the outro and shows the title."""
        pokes = [(v, "key", 0x3901) for v in range(1100, 4000, 40)] + [(v + 6, "key", 0x3900) for v in range(1100, 4000, 40)]       # (Space is the A button)
        caps = [230, 260, 400, 560, 1000, 2500, 5400]
        run = Run(["ALL=1", "AREA=7", "SCREEN=0", "HERO=100,144,0,255,0,0,1", "HUD=80,80,0,0,0",
                   "VIEWER_DEFS=--defsym NEWGAME=1 --defsym NPCS=1 --defsym MENU=1 --defsym NO_TITLE=1 --defsym NO_ENEMIES=1"],
                  pokes, caps, "shots_flow_ending")
        early, later, black, king, message, outro, title = run.shots
        self.assertEqual((early.at("end_state"), early.at("cur_music")), (1, 7), "no sprite left: Eolis's song, the game stands")
        self.assertEqual((later.at("end_state"), later.at("end_count")), (1, early.at("end_count") - 30), "120 frozen frames count down (30 VBLs between the two shots)")
        self.assertEqual((early.at("hero_x"), early.at("hero_y")), (later.at("hero_x"), later.at("hero_y")), "he stands")
        self.assertEqual((black.at("end_state"), black.at("cur_area")), (1, 7), "the fade and the black frames: still Evil Fortress")
        t0, t1 = king.at("end_times", 0, 4, False), king.at("end_times", 4, 4, False)
        self.assertEqual((king.at("end_state"), king.at("cur_area"), king.at("cur_screen"), king.at("cur_pal"), king.at("building_id"), king.at("cur_music")), (2, 4, 0, 17, 0x44, 13),
                         "the King's room: building 0, palette set 17, song 13, the people of id $44")
        self.assertTrue(120 + 20 + 120 <= t1 - t0 <= 120 + 20 + 120 + 60, f"120 frozen frames, 4 fade steps of 5, 120 black frames (the ROM: the room is there at 261), then the load: {t1 - t0}")
        self.assertLess(king.at("hero_x"), 208, "he walks left by himself")
        self.assertEqual((message.at("end_state"), message.at("hero_y"), message.at("hero_flip")), (2, 112, 0), "on the King's step, facing left")
        self.assertLess(message.at("hero_x"), 0x44, "Up at x < $44 engaged the King")
        self.assertEqual((outro.at("end_state"), outro.at("sp_phase")), (0, 3), "the script's FINISH_GAME: the outro plays")
        self.assertEqual(title.at("sp_phase"), 1, "and the title again")

if __name__ == "__main__":
    unittest.main()
