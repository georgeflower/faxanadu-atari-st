"""The save file (src/save.s): the mantra in a file, as an alternative to the mantra shown by a Guru and typed on the title.

The model tests (no emulator) check that the text of the file round-trips through tools/password_model.py and the rules by which a file is read. The Hatari tests run the
program with a host directory as its drive (the harness copies the .DAT files there; `drive` adds SAVE.SAV or write protects it): a Guru's script $1C (Save to disk writes
SAVE.SAV, whose text must be the mantra of the state; Show mantra and B show it as before; a write protected drive gives "Could not save." and then the mantra) and CONTINUE on
the title (a file loads, a damaged one is refused with the ROM's message, no file goes straight to the entry). Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS).
"""
from __future__ import annotations

import contextlib
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_town as tt  # noqa: E402  (the message model: when a message's last page is complete)
import test_viewer as tv  # noqa: E402  (the scene runner and the picture helpers)

import password_model as pm  # noqa: E402

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()

# the state the Guru scenes poke into the game: every kind of entry the mantra holds
POKED = pm.State(spawn=1, title=4, special_items=0x45, quests=0x03, weapon=1, armor=0, shield=1, magic=3, item=5,
                 weapons=[1, 3], armors=[0], shields=[1], spells=[1, 3], items=[5, 8])
# a state for the files the title scenes read
FILE_STATE = pm.State(spawn=3, title=5, special_items=0x81, quests=0x04, weapon=2, armor=1, shield=0, magic=1, item=7,
                      weapons=[0, 2], armors=[0, 1], shields=[0], spells=[1], items=[7, 9, 3])


class SaveModelTests(unittest.TestCase):
    STATES = (pm.State(armor=0), POKED, FILE_STATE,
              pm.State(spawn=7, title=15, special_items=255, quests=255, weapon=3, armor=3, shield=3, magic=4, item=20,
                       weapons=[0, 1, 2, 3], armors=[0, 1, 2, 3], shields=[0, 1, 2, 3], spells=[0, 1, 2, 3], items=[0, 1, 2, 3, 4, 5, 6, 7]))

    def test_the_text_of_the_file_is_the_mantra_and_a_line_end_and_gives_the_state_back(self) -> None:
        for state in self.STATES:
            data = pm.save_file(state)
            self.assertEqual(data, pm.password(state).encode() + b"\r\n")
            self.assertLessEqual(len(data), pm.SAVE_READ, "all of it is read")
            self.assertEqual(pm.read_save(data), state)

    def test_a_file_edited_on_another_machine_is_read_the_same(self) -> None:
        state = POKED
        text = pm.password(state).encode()
        for data in (text, text + b"\n", text + b"\r\n\x1a", text + b" \r\n", text + b"\n\nanything after the line end"):
            self.assertEqual(pm.read_save(data), state, data)

    def test_a_file_that_is_not_a_mantra_is_refused(self) -> None:
        text = pm.password(POKED)
        flipped = text[:3] + ("B" if text[3] != "B" else "C") + text[4:]
        for data in (b"", b"\r\n", b" " + text.encode(), b"\n" + text.encode(), text.lower().encode(), flipped.encode() + b"\r\n", text.encode()[:-1] + b"\r\n",
                     (text + "A").encode() + b"\r\n", b"A" * 40, bytes(35), text.encode() + b"=\r\n", b"\xc3\x84" + text.encode()[2:]):
            self.assertIsNone(pm.read_save(data), data)

    def test_a_file_is_read_to_35_bytes(self) -> None:
        """More than the 32 characters (and the line end) of a mantra is a mantra that is too long, as typing a 33rd character would be, wherever the line end is."""
        self.assertIsNone(pm.read_save(b"A" * 33 + b"\r\n"))
        text = pm.password(FILE_STATE).encode()
        self.assertEqual(pm.read_save(text + b"\r\n" + b"x" * 100), FILE_STATE)


@contextlib.contextmanager
def drive(files: dict[str, bytes] | None = None, extra: list[str] | None = None):
    """The harness' drive gets more files and Hatari more options while a scene runs (tools/hatari_shot.py `run_hatari`)."""
    import hatari_shot as hs

    original = hs.run_hatari
    hs.run_hatari = lambda *a, **k: original(*a, **k, files=files, extra=extra)
    try:
        yield
    finally:
        hs.run_hatari = original


def saved(name: str) -> bytes | None:
    """The SAVE.SAV the program left on the drive of the scene `name` (the host's file name may have any case)."""
    for entry in (ROOT / "build" / name / "hd").iterdir():
        if entry.name.upper() == "SAVE.SAV":
            return entry.read_bytes()
    return None


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class SaveSceneTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture
    text_layer = staticmethod(tv.ViewerTests.text_layer)
    box_layer = staticmethod(tv.ViewerTests.box_layer)
    bright_slot = staticmethod(tv.ViewerTests.bright_slot)
    entry_box = tv.ViewerTests.entry_box

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def scene(self, make_args, pokes, capture, name, files=None, extra=None):
        with drive(files, extra):
            return self.run_scenario(make_args, pokes, capture, name)

    # ------------------------------------------------------------------------------------------------------------------ pictures of the boxes
    def region(self, ram, log, x0, y0, x1, y1):
        import hatari_shot as hs

        rows = hs.decode_screen(ram, hs.video_base(log))
        return [row[x0:x1] for row in rows[y0:y1]]

    def choice_box(self, lines, selected):
        """The two-line box (the start menu's place and size): groups 5 to 14, lines 88 to 143, the line the cursor is on light on dark turned round."""
        import faxanadu_text as ft

        rows = [[0] * 320 for _ in range(200)]
        slot, font = self.bright_slot(self.rom, 0), ft.font(self.rom)
        self.box_layer(rows, slot, 5, 88, 10, 56)
        self.text_layer(rows, font, slot, [(104 + 8 * i, 96 + 18 * n, c, selected == n) for n, line in enumerate(lines) for i, c in enumerate(line)])
        return [row[80:240] for row in rows[88:144]]

    def message_box(self, text):
        """message_box's box: 160 wide in the middle of the window, a line of text 10 lines high."""
        import faxanadu_text as ft

        lines = text.split("\n")
        height = 10 * len(lines) + 8
        y0 = 32 + (168 - height) // 2
        rows = [[0] * 320 for _ in range(200)]
        slot, font = self.bright_slot(self.rom, 0), ft.font(self.rom)
        self.box_layer(rows, slot, 5, y0, 10, height)
        self.text_layer(rows, font, slot, [(96 + 8 * i, y0 + 4 + 10 * n, c, False) for n, line in enumerate(lines) for i, c in enumerate(line)])
        return [row[80:240] for row in rows[y0:y0 + height]]

    # ------------------------------------------------------------------------------------------------------------------ the Guru
    PLAN = None

    @classmethod
    def after_peace(cls) -> int:
        """The VBL (from START) at which the Guru's message $22 is dismissed: the next thing on the screen is the choice."""
        if cls.PLAN is None:
            cls.PLAN = tt.pages(tt.raw_message(cls.rom, 0x22))
        return cls.PLAN[-1]["press"]

    def guru(self, name, extra_pokes, capture, files=None, extra=None, poke_state=True):
        """Script $1C (a Guru that gives no rank: the message, then the choice). POKED is what he has; A dismisses the message at `after_peace`."""
        plan = tt.pages(tt.raw_message(self.rom, 0x22))
        pokes = []
        if poke_state:
            s = POKED
            inv = {24: len(s.weapons), 25: len(s.armors), 26: len(s.shields), 27: len(s.spells), 28: len(s.items), 29: s.special_items, 30: s.quests, 34: s.armor, 35: s.shield, 36: s.item}
            inv.update({i: v for i, v in enumerate(s.weapons)})
            inv.update({4 + i: 0x20 | v for i, v in enumerate(s.armors)})
            inv.update({8 + i: 0x40 | v for i, v in enumerate(s.shields)})
            inv.update({12 + i: 0x60 | v for i, v in enumerate(s.spells)})
            inv.update({16 + i: 0x80 | v for i, v in enumerate(s.items)})
            pokes += [(tt.START - 6, "inv", off << 8 | v) for off, v in inv.items()]
            pokes += [(tt.START - 6, "weapon", s.weapon), (tt.START - 6, "w:hero_magic", s.magic), (tt.START - 6, "w:hero_title", s.title), (tt.START - 6, "w:hero_next", s.title)]
        pokes += tt.presses(plan) + extra_pokes
        return self.scene(["VIEWER_DEFS=--defsym SCRIPT=28"], pokes, capture, name, files, extra)

    @staticmethod
    def press(at, what="space"):
        return [(tt.START + at, what, 1), (tt.START + at + 2, what, 0)]

    def test_the_choice_box_has_two_lines_and_the_cursor_moves_with_up_and_down(self) -> None:
        t = self.after_peace()
        for name, scan in (("shots_save_choice_down", 0x50), ("shots_save_choice_up", 0x48)):
            ram, word, log = self.guru(name, [(tt.START + t + 20, "key", scan << 8 | 1), (tt.START + t + 22, "key", scan << 8)], tt.START + t + 60)
            self.assertEqual(self.region(ram, log, 80, 88, 240, 144), self.choice_box(["Save to disk", "Show mantra"], 1), "the cursor is on the second line (both ways round: two lines)")
            self.assertIsNone(saved(name), "nothing is written before a line is taken")

    def test_save_to_disk_writes_the_mantra_of_the_state_to_save_sav_and_the_script_goes_on(self) -> None:
        t = self.after_peace()
        pokes = self.press(t + 20) + self.press(t + 80)
        ram, word, log = self.guru("shots_save_ok", self.press(t + 20), tt.START + t + 60)
        got = self.region(ram, log, 80, 107, 240, 125)
        self.assertEqual(got, self.message_box("Game saved."), "the box that says so")
        self.assertEqual(saved("shots_save_ok"), pm.save_file(POKED), "SAVE.SAV is the mantra of what he has, and a line end")
        self.assertEqual(word("sv_status"), 0)
        ram, word, log = self.guru("shots_save_ok2", pokes, tt.START + t + 200)
        self.assertEqual(saved("shots_save_ok2"), pm.save_file(POKED))
        self.assertEqual(word("tb_vars+12"), 1, "the script ended (a Guru's END)")
        self.assertEqual((word("hero_title"), word("hero_spawn")), (4, 1), "saving changes nothing in the game")

    def test_show_mantra_and_b_show_it_as_before_and_write_nothing(self) -> None:
        t = self.after_peace()
        mantra = pm.password(POKED)
        for name, pokes in (("shots_save_show", [(tt.START + t + 20, "key", 0x50 << 8 | 1), (tt.START + t + 22, "key", 0x50 << 8)] + self.press(t + 40)),
                            ("shots_save_b", self.press(t + 20, "b"))):
            ram, word, log = self.guru(name, pokes, tt.START + t + 120)
            self.assertEqual(word.raw("pw_text", len(mantra) + 1), mantra.encode() + b"\0", name)
            self.assertEqual(bytes(word.raw("tb_rows", 16)), mantra[:16].encode(), "the first line of the mantra in the text area")
            self.assertIsNone(saved(name))

    def test_a_write_protected_drive_says_so_and_the_mantra_is_shown_instead(self) -> None:
        t = self.after_peace()
        mantra = pm.password(POKED)
        ram, word, log = self.guru("shots_save_protected", self.press(t + 20), tt.START + t + 60, extra=["--protect-hd", "on"])
        self.assertEqual(self.region(ram, log, 80, 107, 240, 125), self.message_box("Could not save."))
        self.assertEqual(word("sv_status"), -1)
        ram, word, log = self.guru("shots_save_protected2", self.press(t + 20) + self.press(t + 80), tt.START + t + 200, extra=["--protect-hd", "on"])
        self.assertEqual(word.raw("pw_text", len(mantra) + 1), mantra.encode() + b"\0")
        self.assertEqual(bytes(word.raw("tb_rows", 16)), mantra[:16].encode())
        self.assertIsNone(saved("shots_save_protected2"))

    def test_saving_again_replaces_the_file(self) -> None:
        t = self.after_peace()
        ram, word, log = self.guru("shots_save_again", self.press(t + 20), tt.START + t + 60, files={"SAVE.SAV": b"old file that is longer than the mantra, for sure, yes\r\n" * 3})
        self.assertEqual(saved("shots_save_again"), pm.save_file(POKED), "the old file is gone, not overwritten from its start")

    # ------------------------------------------------------------------------------------------------------------------ CONTINUE on the title
    TITLE = ["VIEWER_DEFS=--defsym SPLASH=1 --defsym MENU=1"]
    CONTINUE = [(360, "joy", 2), (364, "joy", 0), (420, "joy", 0x80), (424, "joy", 0)]    # Down, then fire: CONTINUE
    A = [(520, "space", 1), (522, "space", 0)]

    def test_continue_with_a_file_offers_load_game_and_loads_it_as_a_typed_mantra_would_start(self) -> None:
        files = {"SAVE.SAV": pm.save_file(FILE_STATE)}
        ram, word, log = self.scene(self.TITLE, self.CONTINUE, 500, "shots_save_load_box", files)
        self.assertEqual(self.region(ram, log, 80, 88, 240, 144), self.choice_box(["Load game", "Enter mantra"], 0))
        ram, word, log = self.scene(self.TITLE, self.CONTINUE + self.A, 800, "shots_save_load", files)
        s = FILE_STATE
        self.assertEqual((word("hero_title"), word("hero_next"), word("hero_spawn")), (s.title, s.title, s.spawn))
        inv = word.raw("inv", 38)
        self.assertEqual((inv[29], inv[30], inv[34], inv[35], inv[36]), (s.special_items, s.quests, s.armor, s.shield, s.item))
        self.assertEqual((word("hero_weapon"), word("hero_magic")), (s.weapon, s.magic))
        self.assertEqual((list(inv[24:29])), [len(s.weapons), len(s.armors), len(s.shields), len(s.spells), len(s.items)])
        self.assertEqual([b & 31 for b in inv[0:2]], s.weapons)
        self.assertEqual([b & 31 for b in inv[16:19]], s.items)
        self.assertEqual(word("sv_status"), 0)
        self.assertEqual(word.raw("hud_state", 2), bytes([80, 80]), "power and magic 80, as after a death")

    def test_a_loaded_game_starts_in_the_temple_of_its_spawn_point_like_a_typed_mantra(self) -> None:
        """The disk build (NEWGAME=1): the file of rank 2 and spawn point 0 puts him in the building of the temple (area 4, palette set 18, x 224, y 144) with the rank's
        experience and gold (2200 and 800) and power and magic 80, as `check_temple` of tests/test_flow.py has it after a death."""
        state = pm.State(spawn=0, title=2, armor=0, weapons=[0], armors=[0])
        defs = "VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1"
        pokes = [(480, "joy", 2), (484, "joy", 0), (540, "joy", 0x80), (544, "joy", 0), (640, "space", 1), (642, "space", 0)]
        ram, word, log = self.scene(["ALL=1", "AREA=0", "SCREEN=1", defs], pokes, 1100, "shots_save_temple", {"SAVE.SAV": pm.save_file(state)})
        self.assertEqual((word("cur_area"), word("cur_pal"), word("cur_screen")), (4, 18, 0), "the building of the temple")
        self.assertEqual((word("hero_x"), word("hero_y"), word("hero_flip")), (224, 144, 0))
        self.assertEqual((word("hero_title"), word("hero_spawn")), (2, 0))
        self.assertEqual((word("hud_state+2"), word("hud_state+6")), (2200, 800))
        self.assertEqual(word.raw("hud_state", 2), bytes([80, 80]))

    def test_a_damaged_file_is_refused_with_the_roms_message_and_the_choice_comes_back(self) -> None:
        text = pm.password(FILE_STATE)
        bad = (text[:5] + ("B" if text[5] != "B" else "C") + text[6:]).encode() + b"\r\n"
        ram, word, log = self.scene(self.TITLE, self.CONTINUE + self.A, 600, "shots_save_bad", {"SAVE.SAV": bad})
        self.assertEqual(self.region(ram, log, 80, 107 - 5, 240, 107 + 23), self.message_box("Mantra is in\nthe wrong."))
        self.assertEqual((word("hero_title"), word("hero_spawn")), (0, 0), "nothing was taken from it")
        self.assertEqual(word("sv_status"), -1)
        ram, word, log = self.scene(self.TITLE, self.CONTINUE + self.A + [(600, "space", 1), (602, "space", 0)], 700, "shots_save_bad2", {"SAVE.SAV": bad})
        self.assertEqual(self.region(ram, log, 80, 88, 240, 144), self.choice_box(["Load game", "Enter mantra"], 0), "back at the choice")

    def test_enter_mantra_is_still_there_with_a_file_and_no_file_goes_straight_to_the_entry(self) -> None:
        import hatari_shot as hs
        import st_convert as sc

        down = [(520, "joy", 2), (522, "joy", 0), (540, "space", 1), (542, "space", 0)]
        for name, files, pokes in (("shots_save_enter", {"SAVE.SAV": pm.save_file(FILE_STATE)}, self.CONTINUE + down), ("shots_save_nofile", None, self.CONTINUE)):
            ram, word, log = self.scene(self.TITLE, pokes, 700, name, files)
            expected = sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
            self.entry_box(expected, self.rom, 0, "", 0)
            got = hs.decode_screen(ram, hs.video_base(log))
            self.assertEqual([(x, y) for y in range(200) for x in range(320) if got[y][x] != expected[y][x]][:5], [], name)
            self.assertEqual(word("hero_title"), 0, "nothing was loaded")


if __name__ == "__main__":
    unittest.main()
