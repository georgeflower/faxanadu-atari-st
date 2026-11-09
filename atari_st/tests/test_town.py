"""The script interpreter (src/town.s) in Hatari: the King, a shop, the Gurus. Each scene starts one script of the ROM's bank 12 by its number at the start of
the game (the test hook `--defsym SCRIPT=n`), presses A where a message waits for it and then reads the program's variables and the screen. The last tests
(NPCS=1) go into the buildings of Eolis through their doors, look at the people there, talk to them with Up, and use the portraits and the shops.

The expected text comes from a model of the message printer in this file (`pages`): the raw message bytes, 16 columns by 4 lines, a line that fills ends,
a pause or the end waits, a fifth line scrolls. The model also gives the frame in which each page is complete, which is when the test presses A."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (borrowed: the scene runner and the picture helpers; the class itself is not imported, so its tests do not run here)

START = 204         # the VBL (counted from the start of the harness run, TOS's boot included) in which the first message's timer is 0: the script starts in the loop's 20th pass
MARGIN = 16         # A is pressed this many frames after the page is complete
BOX_X, BOX_GROUPS, BOX_Y, BOX_H = 112, 10, 144, 48        # group 7 of 16 pixels, 160 wide, at the bottom of the window (every script of these tests has a portrait)
TEXT_X, PITCH = 128, 10
ARROW_X = 256                                              # the cell right of the text where the arrow blinks (blank or the arrow)


def pages(msg: bytes, rank: str = "", margin: int = MARGIN) -> list[dict]:
    """The message printer's behaviour as a list of pages: {rows: the four lines of the text area, kind: 'pause' or 'end', frame: when it is complete, press: when
    A is pressed}. One byte of the message every fourth frame, counted from the message's first frame."""
    data = bytearray()
    for b in msg:
        if b == 0xFB:
            data += rank.encode()                          # (one character a step, as every other)
        else:
            data.append(b)
    rows = [[" "] * 16 for _ in range(4)]
    line = col = i = frame = 0
    out: list[dict] = []

    def next_line() -> None:
        nonlocal line, col
        col = 0
        line += 1
        if line >= 4:                                      # the fifth line: the text goes up one line
            rows.pop(0)
            rows.append([" "] * 16)
            line = 3

    while True:
        frame = (frame // 4 + 1) * 4
        kind = None
        while True:                                        # one step
            b = data[i]
            i += 1
            if b == 0xFF:
                kind = "end"
            elif b == 0xFE:
                if col == 0:
                    continue                               # a new line at the start of a line is nothing
                next_line()
            elif b == 0xFC:
                kind = "end" if data[i] == 0xFF else "pause"
            else:
                rows[line][col] = " " if b == 0xFD else chr(b)
                col += 1
                if col == 16:
                    if data[i] == 0xFF:
                        kind = "end"
                    elif data[i] != 0xFC:
                        next_line()
            break
        if kind is None:
            continue
        page = dict(rows=["".join(r) for r in rows], kind=kind, frame=frame, press=frame + margin)
        out.append(page)
        if kind == "end":
            return out
        frame += margin                                    # A: the text goes on in the line below
        if col:
            next_line()


def raw_message(rom, number: int) -> bytes:
    import iscripts as isc

    block, offsets = isc.messages(rom)
    return block[offsets[number - 1]:block.index(0xFF, offsets[number - 1]) + 1]


def presses(plan: list[dict], first: int = 0, start: int = START) -> list[tuple[int, str, int]]:
    """The pokes that press A (two frames down) after each page of the plan from page `first` on."""
    out: list[tuple[int, str, int]] = []
    for page in plan[first:]:
        out += [(start + page["press"], "space", 1), (start + page["press"] + 2, "space", 0)]
    return out


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class TownTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture
    text_layer = staticmethod(tv.ViewerTests.text_layer)
    box_layer = staticmethod(tv.ViewerTests.box_layer)
    bright_slot = staticmethod(tv.ViewerTests.bright_slot)

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def scene(self, script: int, extra: list[str], pokes: list[tuple[int, str, int]], capture: int, name: str, defs: str = ""):
        args = [f"VIEWER_DEFS=--defsym SCRIPT={script} {defs}".strip()] + extra
        return self.run_scenario(args, pokes, capture, name)

    @staticmethod
    def hud(word) -> dict:
        raw = word.raw("hud_state", 10)
        return dict(hp=raw[0], mp=raw[1], experience=int.from_bytes(raw[2:4], "big"), gold=int.from_bytes(raw[4:8], "big"), seconds=raw[8])

    ARROWS = {"down": (0x18, 0x18, 0x18, 0x18, 0xDB, 0x7E, 0x3C, 0x18), "up": (0x18, 0x3C, 0x7E, 0xDB, 0x18, 0x18, 0x18, 0x18)}

    def box_picture(self, ram, word, log, rows, state: dict, arrow: str | None = None):
        """The screen the game shows, and the expected one: the plain screen with the HUD of `state`, the message box at the bottom with `rows` of text."""
        import hatari_shot as hs
        import st_convert as sc

        got = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(self.rom, 0, 1, word("camera"), state=state, hero=sc.Hero(144, 144, 0, 255, 0, 0, True))
        slot, font = self.bright_slot(self.rom, 0), __import__("faxanadu_text").font(self.rom)
        self.box_layer(expected, slot, BOX_X // 16, BOX_Y, BOX_GROUPS, BOX_H)
        self.text_layer(expected, font, slot, [(TEXT_X + 8 * c, BOX_Y + 4 + PITCH * n, ch, False) for n, row in enumerate(rows) for c, ch in enumerate(row)])
        top = BOX_Y + 4 + 3 * PITCH                                              # the arrow blinks: its cell is blank or the arrow, nothing else
        cell = [[got[y][x] for x in range(ARROW_X, ARROW_X + 8)] for y in range(top, top + 8)]
        shape = [[slot if bits >> (7 - x) & 1 else 0 for x in range(8)] for bits in self.ARROWS[arrow or "down"]]
        self.assertIn(cell, ([[0] * 8] * 8, shape if arrow else [[0] * 8] * 8), f"the arrow cell shows neither blank nor the {arrow} arrow")
        for y in range(8):
            for x in range(8):
                expected[top + y][ARROW_X + x] = got[top + y][ARROW_X + x]
        return got, expected

    def plain_picture(self, ram, word, log, state: dict):
        import hatari_shot as hs
        import st_convert as sc

        got = hs.decode_screen(ram, hs.video_base(log))
        return got, sc.expected_screen(self.rom, 0, 1, word("camera"), state=state, hero=sc.Hero(144, 144, 0, 255, 0, 0, True))

    # ------------------------------------------------------------------------------------------------------------------ the model
    def test_the_message_model_wraps_scrolls_and_waits_as_the_rom_does(self) -> None:
        plan = pages(raw_message(self.rom, 0x36))
        self.assertEqual([p["kind"] for p in plan], ["pause", "end"])
        self.assertEqual(plan[0]["rows"], ["There is nothing", "more I can do to", "help you.       ", " " * 16])
        self.assertEqual(plan[1]["rows"], ["more I can do to", "help you.       ", "Looking forward ", "to good news.   "])
        rank = pages(raw_message(self.rom, 0x23), "Aspirant")
        self.assertEqual([r.rstrip() for r in rank[0]["rows"]], ["I shall give you", "a title.", "'Aspirant'", ""])
        king = pages(raw_message(self.rom, 0x35))
        self.assertEqual([p["kind"] for p in king], ["pause"] * 7 + ["end"])

    # ------------------------------------------------------------------------------------------------------------------ the King
    def test_the_king_gives_1500_gold_once(self) -> None:
        """Script $08 with no gold: message $35 (pauses and the end wait for A), then 1500 gold, ten a frame; the screens are the game's again with the gold on the HUD."""
        plan = pages(raw_message(self.rom, 0x35))
        last = plan[-1]["press"] + START
        ram, word, log = self.scene(0x08, [], presses(plan), last + 150 + 60 + 40, "shots_king")
        self.assertEqual(self.hud(word)["gold"], 1500)
        self.assertEqual((word("tb_vars+12"), word("hero_title"), word("hero_spawn")), (1, 0, 0), "the message ended; the king changes neither the rank nor the temple")
        got, expected = self.plain_picture(ram, word, log, dict(hp=16, mp=0, experience=0, gold=1500, seconds=0))
        self.assert_picture(got, expected)

    def test_the_king_with_gold_says_there_is_nothing_more_to_do(self) -> None:
        """Script $08 with 1 gold: message $36 on a box at the bottom of the window, 16 columns by 4 lines; after the pause the second page scrolls the text up a line."""
        plan = pages(raw_message(self.rom, 0x36))
        ram, word, log = self.scene(0x08, ["HUD=16,0,0,1,0"], presses(plan, 0)[:2], plan[1]["frame"] + START + MARGIN + 2 + 30, "shots_king_gold")
        self.assertEqual(self.hud(word)["gold"], 1, "no gold is given")
        self.assertEqual((word("tb_vars+10"), word("tb_vars+12")), (0, 1), "not paused, ended")
        got, expected = self.box_picture(ram, word, log, plan[1]["rows"], dict(hp=16, mp=0, experience=0, gold=1, seconds=0), "up")
        self.assert_picture(got, expected)

    # ------------------------------------------------------------------------------------------------------------------ a shop
    def test_the_meat_shop_takes_50_gold_and_gives_30_power_and_30_magic(self) -> None:
        """Script $0B: the question (A is yes), PAY_GOLD 50, ADD_HP 30, ADD_MP 30, message $02."""
        ask = pages(raw_message(self.rom, 7))
        pokes = presses(ask)
        thanks = pages(raw_message(self.rom, 2))
        after = ask[-1]["press"] + 65 + 30 + 30 + 20                          # the payment, the power, the magic: then the next message
        pokes += [(START + after + p["press"], "space", v) for p in thanks for v in (1,)] + [(START + after + p["press"] + 2, "space", 0) for p in thanks]
        capture = START + after + thanks[-1]["press"] + 40
        ram, word, log = self.scene(0x0B, ["HUD=10,20,0,100,0"], pokes, capture, "shots_meat")
        state = self.hud(word)
        self.assertEqual((state["gold"], state["hp"], state["mp"]), (50, 40, 50))

    def test_the_meat_shop_with_too_little_gold_says_so_and_ends(self) -> None:
        """20 gold: the question is answered yes, PAY_GOLD finds it is not enough: message $03 and nothing changes."""
        ask = pages(raw_message(self.rom, 7))
        short = pages(raw_message(self.rom, 3))
        start = ask[-1]["press"] + 2
        capture = START + start + short[-1]["frame"] + 40
        ram, word, log = self.scene(0x0B, ["HUD=10,20,0,20,0"], presses(ask), capture, "shots_meat_poor")
        state = self.hud(word)
        self.assertEqual((state["gold"], state["hp"], state["mp"]), (20, 10, 20), "nothing was paid or given")
        self.assertEqual(word("tb_vars+12"), 1)
        got, expected = self.box_picture(ram, word, log, short[-1]["rows"], dict(hp=10, mp=20, experience=0, gold=20, seconds=0), "up")
        self.assert_picture(got, expected)

    # ------------------------------------------------------------------------------------------------------------------ the Gurus
    def test_a_guru_gives_the_rank_the_experience_has_earned(self) -> None:
        """Script $1C with the rank Aspirant earned (NEXT_TITLE=1): the temple is set, the rank is his, message $23 has its name in it."""
        plan = pages(raw_message(self.rom, 0x23), "Aspirant")
        ram, word, log = self.scene(0x1C, [], [], START + plan[0]["frame"] + 30, "shots_guru_rank", "--defsym NEXT_TITLE=1")
        self.assertEqual((word("hero_title"), word("hero_spawn"), word("tb_vars+10")), (1, 1, 1), "the rank, the temple, waiting at the pause")
        got, expected = self.box_picture(ram, word, log, plan[0]["rows"], dict(hp=16, mp=0, experience=0, gold=0, seconds=0), "down")
        self.assert_picture(got, expected)

    def test_a_guru_without_a_new_rank_says_peace_and_shows_the_mantra(self) -> None:
        """Script $1C with no rank earned: message $22, then the mantra (16 characters a line) until A; the rank is as it was, the temple is set."""
        import password_model as pm

        plan = pages(raw_message(self.rom, 0x22))
        mantra = pm.password(pm.State(1, 0, 0, 0, 0, 0, pm.UNSET, pm.UNSET, pm.UNSET))
        wait = START + plan[-1]["press"] + 60
        ram, word, log = self.scene(0x1C, [], presses(plan), wait, "shots_guru_mantra")
        self.assertEqual((word("hero_title"), word("hero_spawn")), (0, 1))
        self.assertEqual(word.raw("pw_text", len(mantra) + 1), mantra.encode() + b"\0")
        rows = [mantra[i:i + 16].ljust(16) for i in range(0, 64, 16)]
        got, expected = self.box_picture(ram, word, log, rows, dict(hp=16, mp=0, experience=0, gold=0, seconds=0), "up")
        self.assert_picture(got, expected)

    def test_the_ring_guru_gives_the_ring_to_a_hero_who_has_none(self) -> None:
        """Script $04: IF_HAS_ITEM does not jump, message $2C, ADD_ITEM sets the Ring of Elf's bit among the special items (its name on show until A)."""
        plan = pages(raw_message(self.rom, 0x2C))
        pokes = presses(plan)
        after = plan[-1]["press"] + 12
        pokes += [(START + after + MARGIN + 20, "space", 1), (START + after + MARGIN + 22, "space", 0)]
        ram, word, log = self.scene(0x04, [], pokes, START + after + MARGIN + 80, "shots_guru_ring")
        inv = word.raw("inv", 38)
        self.assertEqual((inv[29], inv[28]), (0x80, 0), "the Ring of Elf is a special item (bit 7 of INV_SPECIAL), it takes no place in the list")

    def test_the_ring_guru_says_visit_the_gurus_to_a_hero_who_has_the_ring(self) -> None:
        """The same script with the Ring (INV_SPECIAL bit 7 poked in): IF_HAS_ITEM jumps to message $2D and nothing is added."""
        plan = pages(raw_message(self.rom, 0x2D))
        pokes = [(START - 6, "inv", 29 << 8 | 0x80)] + presses(plan)
        ram, word, log = self.scene(0x04, [], pokes, START + plan[-1]["press"] + 60, "shots_guru_ring_owned")
        inv = word.raw("inv", 38)
        self.assertEqual((inv[29], inv[28]), (0x80, 0), "nothing was added")
        self.assertEqual(word("tb_vars+12"), 1)

    # ------------------------------------------------------------------------------------------------------------------ the people, the portraits, the shops
    NPC_DEFS = "--defsym NPCS=1"
    FIRST_PASS = 20           # the loop's pass in which SCRIPT=n starts (not used here: the people are talked to)

    @classmethod
    def town_files(cls):
        import iscripts as isc

        npc = isc.parse_npc_file(isc.npc_file(cls.rom))
        por = isc.parse_portrait_file(isc.portrait_file(cls.rom))
        return npc, por

    def building_args(self, door_screen: int, door_x: int, gold: int = 0, extra: str = "", area: int = 0):
        """Screen `door_screen` of the area (Eolis unless `area` says another) with the hero at the door (block row 9, x `door_x`) with no weapon (the shops would say he has the
        Hand Dagger already), the viewer with the people (NPCS=1) and every screen of the area."""
        return ["ALL=1", f"AREA={area}", f"SCREEN={door_screen}", f"HERO={door_x},144,0,255,255,0,1", "WORLD=1", f"HUD=16,0,0,{gold},0",
                f"VIEWER_DEFS={self.NPC_DEFS} {extra}".strip()]

    ENTER = [(599, "joy", 1), (602, "joy", 0)]          # Up at the door: the building (the picture is steady well before frame 720)

    def npc_layer(self, rows, npc: dict, entity: int, x: int, y: int, palette_set: int, camera: int, frame: int, faces_right: bool = False) -> None:
        """The person drawn into `rows` (slot numbers) from npc.bin's tiles and the slot map of the palette set: what the game's blitter makes of the pose."""
        kind = next(k for k in npc["kinds"] if k["entity"] == entity)
        mirrored = kind["mirror"] == 1 or (kind["mirror"] == 2 and faces_right)
        pose = kind["poses"][2 * frame + (1 if mirrored else 0)]
        slots = npc["slots"][palette_set]
        for dx, dy, tile, attr in pose:
            data = kind["tiles"][tile]
            left = 32 <= x + dx < 288
            for row in range(8):
                for col in range(8):
                    bit = col if attr & 0x40 else 7 - col
                    value = (data[row] >> bit & 1) | (data[8 + row] >> bit & 1) << 1
                    px, py = x + dx + col, y - camera + dy + row
                    if value and left and 32 <= py < 200 and px < 288:
                        rows[py][px] = slots[(attr & 3) * 4 + value]

    def person(self, npc: dict, area: int, screen: int, entity: int) -> tuple[int, int, int]:
        place = next(p for p in npc["places"] if p[:3] == (area, screen, entity))
        return place[3], place[4], place[5]                              # the script, x, y

    RING = [(300, "inv", 29 << 8 | 0x80)]               # the Ring of Elf in hand: it opens the doors of key 6 (the magician, the martial artist, the King)

    def test_the_king_stands_in_his_room(self) -> None:
        """Eolis screen 7, the door at x 128 (id 7, type 0: the Ring of Elf opens it): the King (entity $3A, script 8) stands at x 32, y 112 in the pose of either of his
        two frames, facing right (mirrored: his rule 1), in the slots of palette set 17 (npc.bin); the rest of the room is the building's picture."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 4, 7, 0x3A)
        ram, word, log = self.run_scenario(self.building_args(7, 128), self.RING + self.ENTER, 799, "shots_npc_king")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("building_id")), (4, 17, 7))
        slot = word.raw("npc_slots", 16)
        self.assertEqual((slot[0], slot[1], int.from_bytes(slot[2:4], "big"), int.from_bytes(slot[4:6], "big")), (0x3A, script, x, y))
        self.assertEqual(word.raw("npc_slots", 32)[16], 0xFF, "no second person in this room")
        got = hs.decode_screen(ram, hs.video_base(log))
        poses = []
        for frame in (0, 1):
            expected = sc.expected_screen(self.rom, 4, 0, word("camera"), palette_index=17, tiles_index=6, hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0))
            self.npc_layer(expected, npc, 0x3A, x, y, 17, word("camera"), frame)
            poses.append(sum(1 for yy in range(200) for xx in range(320) if got[yy][xx] != expected[yy][xx]))
        self.assertEqual(min(poses), 0, f"pixels that differ from the King's pose 0 / pose 1: {poses}")

    def talk_pokes(self, hero_x: int, at: int = 720, hero_y: int | None = None):
        """He stands at `hero_x` (and `hero_y`) in the building at frame `at`, and Up is pressed (the script starts in the next frame). The King sits on a step: to
        reach him he stands on it, at y 112 (the floor is 144; the ROM's box test says the same, no talk from the floor)."""
        return self.ENTER + [(at, "x", hero_x)] + ([(at, "y", hero_y)] if hero_y is not None else []) + [(at + 20, "joy", 1), (at + 23, "joy", 0)]

    def test_a_door_in_another_town_puts_the_roms_people_in_the_building(self) -> None:
        """Area 3, the towns after Eolis: screen 0's door at block $94 leads to the building with the id 8 (its type, 4, is the number of another room whose person has the script
        $0D; the ROM's id gives the armour salesman, entity $37 at x 48 with script $19); screen 1's door at block $95 has the id 11 (type 1: the people of room 1 would stand
        there): the priest, entity $39 at x 32 with script $1C. The ids are the first bytes of the ROM's door records (tests/test_disk.py checks every door)."""
        for screen, x, ident, want in ((0, 64, 8, [(0x37, 0x19, 48)]), (1, 80, 11, [(0x39, 0x1C, 32)])):
            ram, word, log = self.run_scenario(self.building_args(screen, x, area=3), self.ENTER, 760, f"shots_npc_town_{ident}")
            self.assertEqual((word("cur_area"), word("building_id")), (4, ident), f"the door of screen {screen}")
            raw = word.raw("npc_slots", 32)
            got = sorted((raw[16 * i], raw[16 * i + 1], int.from_bytes(raw[16 * i + 2:16 * i + 4], "big")) for i in range(2) if raw[16 * i] != 0xFF)
            self.assertEqual(got, sorted(want), f"the people of building {ident}")

    def test_up_at_the_king_gives_the_message_and_1500_gold(self) -> None:
        """Up with his box over the King's: script 8 (no gold yet): message $35, then 1500 gold; the gold is on the HUD and the script has ended."""
        plan = pages(raw_message(self.rom, 0x35))
        start = 720 + 20 + 2                                              # the frame in which the message's timer is 0 (within a frame or two)
        pokes = self.RING + self.talk_pokes(48, hero_y=112) + presses(plan, start=start)
        last = start + plan[-1]["press"]
        ram, word, log = self.run_scenario(self.building_args(7, 128), pokes, last + 150 + 60 + 40, "shots_npc_king_talk")
        self.assertEqual(self.hud(word)["gold"], 1500)
        self.assertEqual(word("tb_vars+12"), 1, "the message has ended")

    def test_the_kings_portrait_is_drawn_and_blinks(self) -> None:
        """While the King's message types, his 48 by 64 portrait is in its frame left of the text box (group 3, y 112): the base picture and the eyes and mouth of the
        frame f the game says it drew (portrait_f), in the colours portraits.bin gives set 0 (the King's room); the frame is two pixels thick."""
        import hatari_shot as hs

        npc, por = self.town_files()
        plan = pages(raw_message(self.rom, 0x35))
        start = 720 + 20 + 2
        ram, word, log = self.run_scenario(self.building_args(7, 128), self.RING + self.talk_pokes(48, hero_y=112) + presses(plan, start=start)[:2], start + plan[0]["frame"] + 20, "shots_portrait_king")
        self.assertEqual(word("portrait_k"), 0, "portrait 0 is the King's")
        self.assert_portrait(ram, word, log, por, 0, 0)

    def assert_portrait(self, ram, word, log, por: dict, k: int, building_type: int) -> None:
        """The portrait frame region of the screen on show against the model: the box, the base picture and the eyes and the mouth of frame f = portrait_f."""
        import hatari_shot as hs

        got = hs.decode_screen(ram, hs.video_base(log))
        slot = got[112][80]                                                   # the frame's colour: the brightest of the palette (not black)
        self.assertNotEqual(slot, 0, "the frame's top edge is not drawn")
        expected = [[0] * 320 for _ in range(200)]
        self.box_layer(expected, slot, 3, 112, 4, 80)
        portrait = por["portraits"][k]
        slots = por["slots"][building_type]
        f = word("portrait_f")
        self.assertIn(f, (0, 1, 2, 3))
        for frame in (0, 1 + (f & 1), 3 + (f >> 1 & 1)):
            cols, rows, ox, oy, cells = portrait["frames"][frame]
            for n, cell in enumerate(cells):
                if cell is None:
                    continue
                tile, attr = cell
                data = portrait["tiles"][tile]
                for row in range(8):
                    for col in range(8):
                        bit = col if attr & 0x40 else 7 - col
                        value = (data[row] >> bit & 1) | (data[8 + row] >> bit & 1) << 1
                        expected[120 + oy + 8 * (n // cols) + row][56 + ox + 8 * (n % cols) + col] = slots[(attr & 3) * 4 + value] if value else 0
        bad = [(x, y) for y in range(112, 192) for x in range(48, 112) if got[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels of the portrait differ")

    def shop_pokes(self, hero_x: int, plan_start: int, greeting: int, buy: bool):
        """Walk up to the person at `hero_x`, Up, the greeting (message `greeting`, A at its end); returns the pokes and the frame after the greeting."""
        plan = pages(raw_message(self.rom, greeting))
        start = 720 + 20 + 2
        pokes = self.talk_pokes(hero_x) + presses(plan, start=start)
        return pokes, start + plan[-1]["press"] + 2

    def test_the_tool_shop_sells_a_hand_dagger_once(self) -> None:
        """Eolis screen 3, the door at x 160 (building 4, the tools): Up at the salesman (script 13): the greeting, Buy, the shop box (Hand Dagger 400), A: gold 1500 ->
        1100, the dagger is the first of his weapons; thank you. Talking again and buying again: he has it already: "You can't carry any more." (message $06), nothing
        changes."""
        pokes, t = self.shop_pokes(64, 720, 0x0F, True)
        thanks = pages(raw_message(self.rom, 2))
        pokes += [(t + 12, "space", 1), (t + 14, "space", 0)]                      # Buy (the arrow is on it)
        shop = pages(raw_message(self.rom, 0x14))
        t2 = t + 14 + shop[-1]["frame"] + 20                                         # "What would you like?" has been typed: the shop box is up
        pokes += [(t2, "space", 1), (t2 + 2, "space", 0)]                          # A on the Hand Dagger
        t3 = t2 + 2 + 40 + 60 + 20                                                  # the payment: 400 gold ten a frame, then 60 frames; "Thank you." types
        pokes += [(t3 + thanks[-1]["press"], "space", 1), (t3 + thanks[-1]["press"] + 2, "space", 0)]
        t4 = t3 + thanks[-1]["press"] + 30                                           # the script has ended: Up again
        again = pages(raw_message(self.rom, 0x0F))
        pokes += [(t4, "joy", 1), (t4 + 3, "joy", 0)]
        start = t4 + 2
        pokes += presses(again, start=start)
        t5 = start + again[-1]["press"] + 2
        pokes += [(t5 + 12, "space", 1), (t5 + 14, "space", 0)]                    # Buy
        t6 = t5 + 14 + shop[-1]["frame"] + 20
        pokes += [(t6, "space", 1), (t6 + 2, "space", 0)]                          # the Hand Dagger again
        full = pages(raw_message(self.rom, 6))
        capture = t6 + 2 + full[-1]["frame"] + 40
        ram, word, log = self.run_scenario(self.building_args(3, 160, 1500), pokes, capture, "shots_shop_tools")
        self.assertEqual(self.hud(word)["gold"], 1100)
        inv = word.raw("inv", 38)
        self.assertEqual((inv[0], inv[24]), (0, 1), "the Hand Dagger (weapon 0) is the only weapon in his list")
        rows = word.raw("tb_rows", 64).decode("latin-1")
        self.assertEqual([rows[i:i + 16] for i in range(0, 64, 16)], full[-1]["rows"], "message $06")
        self.assertEqual(word("tb_vars+12"), 1)

    # the shop box
    def tools_pokes(self, extra: list[tuple[int, str, int]] | None = None):
        """Walk to the tools salesman (building 4), the greeting, Buy: returns the pokes and the frame in which "What would you like?" has been typed."""
        pokes, t = self.shop_pokes(64, 720, 0x0F, True)
        shop = pages(raw_message(self.rom, 0x14))
        pokes += [(t + 12, "space", 1), (t + 14, "space", 0)]
        return pokes, t, t + 14 + shop[-1]["frame"] + 20

    def tile_rows(self, rows, tile: bytes, x: int, y: int) -> None:
        for dy in range(8):
            for dx in range(8):
                rows[y + dy][x + dx] = sum(((tile[4 * dy + p] >> (7 - dx)) & 1) << p for p in range(4))

    def test_the_shop_box_shows_pictures_names_prices_and_the_cursor(self) -> None:
        """The tools salesman's list (Hand Dagger 400, Potion 160, Elixir 320, a spell 400): the box (group 7, y 40, 16 lines an entry and 16 more) with each
        entry's 16 by 16 picture, name and five-digit price, and the arrow before the picture the cursor is on (Down moves it one entry, wrapping at the end)."""
        import faxanadu_text as ft
        import hatari_shot as hs
        import iscripts as isc
        import itempics

        pokes, t, up = self.tools_pokes()
        pokes += [(up - 6, "joy", 2), (up - 3, "joy", 0)]
        ram, word, log = self.run_scenario(self.building_args(3, 160, 1500), pokes, up, "shots_shop_box")
        self.assertEqual((word("shop_count"), word("shop_cursor")), (4, 1), "four entries, the cursor moved down once")
        font = bytearray(ft.font(self.rom))
        font[8 * (ord(">") - 32):8 * (ord(">") - 32) + 8] = bytes([0x00, 0x10, 0x18, 0xFC, 0xFC, 0x18, 0x10, 0x00])
        names = ft.menu_strings(self.rom)["names"]
        got = hs.decode_screen(ram, hs.video_base(log))
        slot = got[40][140]
        self.assertNotEqual(slot, 0)
        expected = [[0] * 320 for _ in range(200)]
        self.box_layer(expected, slot, 7, 40, 10, 4 * 16 + 16)
        entries = [(0x00, 400), (0x90, 160), (0x92, 320), (0x60, 400)]
        for i, (item, price) in enumerate(entries):
            index = itempics.picture_index(item)
            for n, tile in enumerate(itempics.st_tiles(self.rom, index, word("cur_pal"))):
                self.tile_rows(expected, tile, 128 + 8 * (n & 1), 48 + 16 * i + 8 * (n >> 1))
            glyphs = [(152 + 8 * c, 48 + 16 * i, ch, False) for c, ch in enumerate(names[index])]
            glyphs += [(216 + 8 * c, 56 + 16 * i, ch, False) for c, ch in enumerate(f"{price:5d}")]
            if i == 1:
                glyphs.append((120, 52 + 16 * i, ">", False))
            self.text_layer(expected, bytes(font), slot, glyphs)
        bad = [(x, y) for y in range(40, 120) for x in range(112, 272) if got[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], f"{len(bad)} pixels of the shop box differ")

    def test_the_tool_shop_buys_a_potion_for_half_price_and_ends_with_nothing_to_sell(self) -> None:
        """BUY_SELL_MENU: Down and A is Sell; SELL_MENU lists the items in his pack that the shop names, at half price (a Potion, 80); A: it is gone and the 80 gold is his,
        ten a frame; thank you."""
        pokes, t = self.shop_pokes(64, 720, 0x0F, False)
        pokes += [(300, "inv", 16 << 8 | 16), (301, "inv", 28 << 8 | 1)]               # a Potion (item 16) is in his pack
        pokes += [(t + 6, "joy", 2), (t + 9, "joy", 0), (t + 20, "space", 1), (t + 22, "space", 0)]
        sell = pages(raw_message(self.rom, 0x13))
        t2 = t + 22 + sell[-1]["frame"] + 20
        pokes += [(t2, "space", 1), (t2 + 2, "space", 0)]
        thanks = pages(raw_message(self.rom, 2))
        t3 = t2 + 2 + 8 + 60 + 20
        pokes += [(t3 + thanks[-1]["press"], "space", 1), (t3 + thanks[-1]["press"] + 2, "space", 0)]
        ram, word, log = self.run_scenario(self.building_args(3, 160, 0), pokes, t3 + thanks[-1]["press"] + 40, "shots_shop_sell")
        self.assertEqual(self.hud(word)["gold"], 80)
        inv = word.raw("inv", 38)
        self.assertEqual(inv[28], 0, "the Potion is gone from his pack")
        self.assertEqual(word("tb_vars+12"), 1)

    def test_the_key_shop_sells_key_j_for_100(self) -> None:
        """Script 12 (the key salesman, started by the test hook): the greeting, Buy, the shop (Key J 100): A: 150 gold becomes 50 and Key J (item 7) is in his pack."""
        greeting = pages(raw_message(self.rom, 0x0E))
        pokes = presses(greeting)
        t = START + greeting[-1]["press"] + 2
        pokes += [(t + 12, "space", 1), (t + 14, "space", 0)]
        shop = pages(raw_message(self.rom, 0x14))
        t2 = t + 14 + shop[-1]["frame"] + 20
        pokes += [(t2, "space", 1), (t2 + 2, "space", 0)]
        thanks = pages(raw_message(self.rom, 2))
        t3 = t2 + 2 + 10 + 60 + 20
        pokes += [(t3 + thanks[-1]["press"], "space", 1), (t3 + thanks[-1]["press"] + 2, "space", 0)]
        ram, word, log = self.scene(12, ["HUD=16,0,0,150,0"], pokes, t3 + thanks[-1]["press"] + 40, "shots_shop_key")
        self.assertEqual(self.hud(word)["gold"], 50)
        inv = word.raw("inv", 38)
        self.assertEqual((inv[16], inv[28]), (7, 1), "Key J is the first item of his pack")

    def test_the_meat_salesman_has_his_portrait_while_he_asks(self) -> None:
        """Eolis screen 1, the door at x 48 (id 0, type 7): the meat salesman (entity $40, script 11) at x 64: Up, and while the question types
        and waits his portrait (7: MeatSalesman, 8th of the 11) is in its frame in the colours of building type 7."""
        npc, por = self.town_files()
        plan = pages(raw_message(self.rom, 7))
        start = 720 + 20 + 2
        pokes = self.talk_pokes(64)
        ram, word, log = self.run_scenario(self.building_args(1, 48, 100), pokes, start + plan[-1]["frame"] + 20, "shots_portrait_meat")
        self.assertEqual((word("cur_area"), word("building_id"), word("portrait_k")), (4, 0, 8))
        self.assert_portrait(ram, word, log, por, 8, 7)

    def test_a_room_with_two_people_draws_both_in_their_own_colours(self) -> None:
        """Eolis screen 2, the door at x 224 (id 1, type 6, the house): a person of kind $3F (script 9) at x 64 and one of kind $45 (script 10) at x 144, each in the pose of either of its
        frames (they turn by the counter, a pose for each), in the slots of the building's palette set (npc.bin); the room is the building's picture."""
        import faxanadu_maps as fm
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        info = fm.building(self.rom, 6)
        ram, word, log = self.run_scenario(self.building_args(2, 224), self.ENTER, 799, "shots_npc_room")
        self.assertEqual((word("cur_area"), word("building_id"), word("cur_pal")), (4, 1, info["palette"]))
        slots = word.raw("npc_slots", 32)
        self.assertEqual((slots[0], slots[16]), (0x3F, 0x45))
        got = hs.decode_screen(ram, hs.video_base(log))
        best = None
        for first in (0, 1):
            for second in (0, 1):
                expected = sc.expected_screen(self.rom, 4, 6, word("camera"), palette_index=info["palette"], tiles_index=info["tiles"],
                                              hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0))
                for entity, x, y, frame in ((0x3F, 64, 128, first), (0x45, 144, 128, second)):
                    self.npc_layer(expected, npc, entity, x, y, info["palette"], word("camera"), frame)
                bad = sum(1 for yy in range(200) for xx in range(320) if got[yy][xx] != expected[yy][xx])
                best = bad if best is None else min(best, bad)
        self.assertEqual(best, 0, "pixels that differ from the best of the four pose pairs")

    def street_args(self, screen: int, hero: str, gold: int = 0):
        return ["ALL=1", "AREA=0", f"SCREEN={screen}", f"HERO={hero},0,255,255,0,1", "WORLD=1", f"HUD=16,0,0,{gold},0", f"VIEWER_DEFS={self.NPC_DEFS} --defsym NO_ENEMIES=1"]

    def test_a_person_stands_in_the_street_in_the_outside_colours(self) -> None:
        """Eolis screen 1: the walker $34 (script 1) at x 192, y 144 stands still (his walk is not done), in frame 0 and not mirrored (he faces left), in the slots of
        palette set 0; the rest is the screen's picture with the hero."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 0, 1, 0x34)
        ram, word, log = self.run_scenario(self.street_args(1, "144,144"), [], 700, "shots_npc_street")
        got = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 255, 0, True))
        self.npc_layer(expected, npc, 0x34, x, y, 0, word("camera"), 0)
        self.assert_picture(got, expected)

    def test_up_at_a_person_in_the_street_starts_his_script(self) -> None:
        """He walks to x 192 (the walker's box: left -8, width 32) and presses Up alone: script 1 (no gold): message $27 is typed on the box at the top of the window
        (the hero stands at y 144: no portrait); Up with Left held does nothing."""
        plan = pages(raw_message(self.rom, 0x27))
        pokes = [(620, "x", 192), (640, "joy", 1 | 4), (643, "joy", 0), (660, "joy", 1), (663, "joy", 0)]
        start = 660 + 2
        ram, word, log = self.run_scenario(self.street_args(1, "144,144"), pokes, start + plan[0]["frame"] + 10, "shots_npc_up")
        self.assertEqual((word("tb_vars+10"), word("tb_vars+12")), (1, 0), "the first page is typed and waits for A")
        rows = word.raw("tb_rows", 64).decode("latin-1")
        self.assertEqual([rows[i:i + 16] for i in range(0, 64, 16)], plan[0]["rows"])
        self.assertEqual(word("portrait_k"), -1, "a person in the street has no portrait")

    def test_touching_the_intro_trigger_in_eolis_starts_the_intro_once(self) -> None:
        """Eolis screen 0: the touch trigger (entity $4F, script 0) at x 64 runs the intro message $26 when the hero stands in it (the game starts there); when the message
        ends the trigger is spent (once in a game): nothing runs again while he stands there."""
        import hatari_shot as hs
        import st_convert as sc

        plan = pages(raw_message(self.rom, 0x26))
        first = 186                                                       # the loop's first pass (SCRIPT hooks pass 20, frame 204)
        ram, word, log = self.run_scenario(self.street_args(0, "64,144"), presses(plan, start=first), first + plan[-1]["press"] + 80, "shots_npc_trigger")
        self.assertEqual((word("npc_intro_done"), word("tb_vars+12")), (1, 1), "the script ran, and has ended")
        self.assertEqual(word.raw("npc_slots", 1)[0], 0xFF, "the trigger is gone")
        got = hs.decode_screen(ram, hs.video_base(log))
        self.assert_picture(got, sc.expected_screen(self.rom, 0, 0, word("camera"), hero=sc.Hero(64, 144, 0, 255, 255, 0, True)))

    def test_the_people_go_with_a_scroll_and_come_with_the_next_screen(self) -> None:
        """He walks off the left edge of Eolis screen 1: the walker of screen 1 is gone, screen 2's person (kind $45, script 3, x 112) is there once the scroll is done, drawn
        in either of its two poses over the new screen's picture."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 0, 2, 0x45)
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=16,144,0,255,255,0,1", "WORLD=1", f"VIEWER_DEFS={self.NPC_DEFS} --defsym NO_ENEMIES=1"]
        ram, word, log = self.run_scenario(args, [(599, "joy", 4), (660, "joy", 0)], 799, "shots_npc_scroll")
        self.assertEqual(word("cur_screen"), 2)
        slot = word.raw("npc_slots", 32)
        self.assertEqual((slot[0], slot[1], int.from_bytes(slot[2:4], "big"), int.from_bytes(slot[4:6], "big"), slot[16]), (0x45, script, x, y, 0xFF))
        got = hs.decode_screen(ram, hs.video_base(log))
        poses = []
        for frame in (0, 1):
            expected = sc.expected_screen(self.rom, 0, 2, word("camera"), hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0))
            self.npc_layer(expected, npc, 0x45, x, y, 0, word("camera"), frame)
            poses.append(sum(1 for yy in range(200) for xx in range(320) if got[yy][xx] != expected[yy][xx]))
        self.assertEqual(min(poses), 0, f"pixels that differ from the pose 0 / pose 1: {poses}")

    def test_walking_out_of_a_building_brings_the_street_back_with_its_people(self) -> None:
        """In the King's room, off its right side: Eolis screen 1 again, the walker $34 at x 192 in the pose of frame 0 in the outside colours (the room's palette with its
        people's colours is gone), the people of the room are not drawn."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 0, 1, 0x34)
        pokes = self.ENTER + [(699, "x", 240), (700, "joy", 8), (703, "joy", 0)]
        ram, word, log = self.run_scenario(self.building_args(1, 48), pokes, 899, "shots_npc_out")
        self.assertEqual((word("cur_area"), word("cur_screen")), (0, 1))
        slot = word.raw("npc_slots", 32)
        self.assertEqual((slot[0], slot[1], slot[16]), (0x34, script, 0xFF))
        got = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0))
        self.npc_layer(expected, npc, 0x34, x, y, 0, word("camera"), 0)
        self.assert_picture(got, expected)


if __name__ == "__main__":
    unittest.main()
