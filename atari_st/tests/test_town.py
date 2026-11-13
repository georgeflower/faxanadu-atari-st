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
    text_box = tv.ViewerTests.text_box

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
        """Script $1C with no rank earned: message $22, the choice of Save to disk or Show mantra (B shows it), then the mantra (16 characters a line) until A; the rank is as
        it was, the temple is set."""
        import password_model as pm

        plan = pages(raw_message(self.rom, 0x22))
        mantra = pm.password(pm.State(1, 0, 0, 0, 0, 0, pm.UNSET, pm.UNSET, pm.UNSET))
        wait = START + plan[-1]["press"] + 60
        show = [(START + plan[-1]["press"] + 20, "b", 1), (START + plan[-1]["press"] + 22, "b", 0)]
        ram, word, log = self.scene(0x1C, [], presses(plan) + show, wait, "shots_guru_mantra")
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
    UPDATES_BEHIND = 187                                  # the people of the street have had (the frame - this) updates: the program makes its images first (en_counter)

    @staticmethod
    def box_hit(bounds: dict, state: list, hero_x: int, hero_y: int) -> bool:
        """Player_CheckHandlePressUpOnNPC's box test of the hero against the people of `state` (person_key tuples)."""
        for s in state:
            left, top, width, height = bounds[s[0]]
            left = left - 256 if left > 127 else left
            if (hero_x + 11 - (s[1] + left)) & 0xFFFF < width + 11 and (hero_y + 27 - (s[3] + top)) & 0xFFFF < height + 27:
                return True
        return False

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

    SLOT = 40                                                          # npc_slots: a record of the enemies' layout (30 bytes) and the person's own fields (src/town.s NPC_REC)

    @staticmethod
    def person_key(s) -> tuple:
        return (s.ent, s.x, s.xf, s.y, s.yf, s.flags, s.phase, s.beh, s.arg1, s.d3, s.d2, s.internal, s.bxf, s.bxfull, s.byf, s.byfull)

    def people_raw(self, word, count: int) -> list[tuple]:
        """The people's slots as the program has them (the same fields in the same order as `person_key`; enemy.s E_xxx)."""
        raw = word.raw("npc_slots", self.SLOT * count)
        return [(r[0], r[2], r[3], r[4], r[5], r[1], r[6], r[7], r[8], r[10], r[11], r[9], r[13], r[12], r[29], r[28]) for r in (raw[i * self.SLOT:(i + 1) * self.SLOT] for i in range(count))]

    def people_states(self, area: int, screen: int, layout: int, hero_x: int, hero_y: int, updates: int, extra: tuple[int, int, int] | None = None) -> list[list[tuple]]:
        """What `tools/npc_model.py` (checked against the game in tests/test_npc.py) has for the people of a screen (a building: its id, and `layout` is the screen of area 4 whose picture it
        has) after 0, 1, ... `updates` updates with the hero standing still: a list of the people's states for each count (the first person of the screen is the model's slot 7)."""
        import copy

        import enemy_model as em
        import faxanadu_maps as fm
        import npc_model as nm

        props = fm.block_properties(self.rom, fm.area(self.rom, area))
        free = next(b for b in range(256) if em.IMPASSABLE[props[b] & 15] == 0 and props[b] & 15 != em.LADDER)
        blocks = bytes(fm.decode_screen(self.rom, fm.area(self.rom, area), layout)[:208]) + bytes([free]) * 48
        eng = nm.engine(self.rom, area, screen, blocks, hero_x, hero_y)
        count = len(nm.people(self.rom, area, screen))
        if extra:                                                      # a kind the game never places, put in the next slot as the loader would (NPC_EXTRA)
            ent, x, y = extra
            s = eng.sprites[7 - count]
            s.ent, s.x, s.y, s.beh, s.hbox, s.script = ent, x, y, 0xFF, eng.kinds[ent]["hitbox"], eng.kinds[ent]["script"]
            count += 1
        out = []
        for _ in range(updates + 1):
            out.append([self.person_key(eng.sprites[7 - i]) for i in range(count)])
            eng.update_all()
        return out

    def assert_people_as_model(self, word, states: list[list[tuple]], what: str) -> int:
        """Every person is where the model puts him after some number n of updates (not before 60: they have walked), or where he was after n - 1 (a capture can fall between the updates of two
        people: the first of the screen goes first); returns the n."""
        count = len(states[0])
        got = self.people_raw(word, count)
        for n in range(len(states) - 1, 59, -1):
            if all(got[i] in (states[n][i], states[n - 1][i]) for i in range(count)):
                return n
        self.fail(f"{what}: the people are {got}, the model's states run from {states[60]} to {states[-1]}")

    def people_info(self, word, count: int = 2) -> list[dict]:
        """The people's slots: entity ($FF: empty), script (the record's), x, y, flags, phase."""
        raw = word.raw("npc_slots", self.SLOT * count)
        out = []
        for i in range(count):
            r = raw[i * self.SLOT:(i + 1) * self.SLOT]
            out.append(dict(ent=r[0], script=r[self.SLOT - 4], x=r[2], y=r[4], flags=r[1], phase=r[6]))
        return out

    def draw_people(self, rows, npc: dict, state: list[tuple], counter: int, palette_set: int, camera: int) -> None:
        """The people of `state` (person_key tuples) drawn as the program draws them: the pose the kind's rule gives for the counter, mirrored as the kind says."""
        import npc_model as nm

        for s in state:
            frame, _ = nm.appearance(s[0], s[6], s[5], counter)
            self.npc_layer(rows, npc, s[0], s[1], s[3], palette_set, camera, frame, faces_right=bool(s[5] & 1))

    def assert_people_shown(self, word, got, states: list[list[tuple]], make_expected, npc: dict, palette_set: int) -> None:
        """The picture is `make_expected()` (the screen without the people) with the people drawn from the model's state: the one the program has, or the one before (a capture can
        fall between a frame's update and its show), with the counter of that frame."""
        count = len(states[0])
        have = self.people_raw(word, count)
        counter = word("en_counter")
        tries, best = [], None
        for n in range(1, len(states)):
            if all(have[i] in (states[n][i], states[n - 1][i]) for i in range(count)):
                tries += [(states[n] if have == states[n] else have, counter), (states[n - 1], counter - 1)]
        self.assertTrue(tries, "the people are where the model has them")
        seen = []
        for state, ctr in tries:
            if (state, ctr) in seen:
                continue
            seen.append((state, ctr))
            expected = make_expected()
            self.draw_people(expected, npc, state, ctr, palette_set, word("camera"))
            bad = sum(1 for y in range(200) for x in range(320) if got[y][x] != expected[y][x])
            best = bad if best is None else min(best, bad)
            if not bad:
                return
        self.fail(f"pixels that differ from the picture with the people of the program's state or the one before: {best}")

    def test_a_walker_in_the_street_walks_and_stops_as_the_game_does(self) -> None:
        """Eolis screen 1: the walker $34 (script 1: walk 60 frames at 0.75 pixel, stand 30, face the hero) and on screen 6 the nurse-like $44 (script 5: move 80, stand 10, flip, face the
        hero), the hero standing still: after n updates every slot is where the model says."""
        for screen, hero in ((1, 144), (6, 16)):
            with self.subTest(screen=screen):
                ram, word, log = self.run_scenario(self.street_args(screen, f"{hero},144"), [], 700, "shots_npc_walk")
                states = self.people_states(0, screen, screen, word("hero_x"), word("hero_y"), 800)
                n = self.assert_people_as_model(word, states, f"screen {screen}")
                self.assertGreater(len({st[0][1] for st in states[:n]}), 8, "he has moved")

    def walkers_on_a_street(self, area: int, screen: int, hero_x: int, entity: int, extra: tuple[int, int, int] | None, name: str) -> None:
        """A street of Eolis (`area` 0) or of the towns (3) with the hero standing at `hero_x`: the kind `entity` is in the slot the program has (`extra` = (entity, x, y) is put there by the
        test build, NPC_EXTRA, for a kind the game never places) and at two moments, 500 and 700 updates after the screen came, every person is where the model (checked against the game
        in tests/test_npc.py) has him, the picture is the screen with the people drawn from the model's state in the kind's pose, and the person has walked."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        defs = f" --defsym NPC_EXTRA={extra[0]} --defsym NPC_EXTRA_X={extra[1]} --defsym NPC_EXTRA_Y={extra[2]}" if extra else ""
        args = ["ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={hero_x},144,0,255,255,0,1", "WORLD=1", "HUD=16,0,0,0,0", f"VIEWER_DEFS={self.NPC_DEFS} --defsym NO_ENEMIES=1{defs}"]
        seen = set()
        for capture in (700, 900):
            with self.subTest(entity=hex(entity), capture=capture):
                ram, word, log = self.run_scenario(args, [], capture, name)
                self.assertEqual((word("cur_area"), word("cur_screen")), (area, screen))
                states = self.people_states(area, screen, screen, hero_x, 144, 1100, extra)
                self.assert_people_as_model(word, states, f"{hex(entity)} at {capture}")
                got = hs.decode_screen(ram, hs.video_base(log))
                pal = word("cur_pal")
                self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, area, screen, word("camera"), palette_index=pal,
                                                                                      hero=sc.Hero(hero_x, 144, 0, 255, 255, 0, True)), npc, pal)
                mine = [r for r in self.people_raw(word, len(states[0])) if r[0] == entity]
                self.assertTrue(mine, f"the kind {hex(entity)} is in a slot")
                seen.add(mine[0][1])
        self.assertGreater(len(seen), 1, f"{hex(entity)} has moved between the two captures")

    def test_the_blue_lady_who_the_game_never_places_walks_80_flips_walks_20_flips_and_walks_80(self) -> None:
        """$35 (script: walk 80 frames at half a pixel, flip, walk 20, flip, walk 80, flip) put into Eolis screen 1 beside the street's walker: the model (and in tests/test_npc.py the game)."""
        self.walkers_on_a_street(0, 1, 144, 0x35, (0x35, 100, 144), "shots_npc_blue_lady")

    def test_the_child_who_the_game_never_places_walks_hops_twice_and_turns(self) -> None:
        """$36 (script: walk 60 at 0.75 pixel, two hops, walk 10, stand 5, flip) put into Eolis screen 1."""
        self.walkers_on_a_street(0, 1, 144, 0x36, (0x36, 150, 144), "shots_npc_child")

    def test_the_lady_of_the_forepaw_street_moves_192_frames_stands_moves_40_and_turns(self) -> None:
        """$41 (script 16: move 192 frames at half a pixel, stand 5, move 40, flip) on screen 10 of the towns, where the game has her."""
        self.walkers_on_a_street(3, 10, 16, 0x41, None, "shots_npc_lady")

    def test_the_guard_of_the_kings_street_patrols_80_frames_and_turns(self) -> None:
        """$42 (script 7: move 80 frames at 0.75 pixel, stand 5, flip) in front of the King's door, Eolis screen 7, where the game has him."""
        self.walkers_on_a_street(0, 7, 16, 0x42, None, "shots_npc_guard")

    def test_the_people_walk_on_while_the_hour_glass_runs_with_the_pictures_standing_still(self) -> None:
        """Eolis screen 1: at VBL 650 the Hour Glass is put in force (`hourglass`, seconds) and the program's counter (en_counter, SpriteUpdateCounter) is set to a number of its own; 110 frames
        later the counter has not moved (the game adds to it only without the Hour Glass) and the walker has gone on walking by the model's updates, all of them (the ROM runs the behaviour
        of every sprite that is not of category 0: tests/test_npc.py, jsnes), and is drawn in the pose that counter gives (frozen, so the same step of his walk)."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        pokes = [(650, "w:hourglass", 15), (650, "w:en_counter", 0x0123)]
        ram, word, log = self.run_scenario(self.street_args(1, "144,144"), pokes, 760, "shots_npc_hourglass")
        self.assertEqual((word("hourglass") >= 0, word("en_counter")), (True, 0x0123), "the Hour Glass is in force and the counter stands still")
        got = hs.decode_screen(ram, hs.video_base(log))
        states = self.people_states(0, 1, 1, 144, 144, 800)
        n = self.assert_people_as_model(word, states, "the walker in the Hour Glass")
        self.assertGreaterEqual(n, 760 - self.UPDATES_BEHIND - 3, "he did not stop: every frame since the program began was an update")
        at_the_poke = {states[k][0][1] for k in range(650 - self.UPDATES_BEHIND - 3, 650 - self.UPDATES_BEHIND + 4)}
        self.assertNotIn(self.people_raw(word, 1)[0][1], at_the_poke, "and he is not where he stood when the Hour Glass began")
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 255, 0, True)), npc, 0)

    def test_the_priest_and_the_doctor_stand_where_op_6_puts_them(self) -> None:
        """Eolis screen 2, the door at x 80: building 2, the priest ($39, placed at x 32) stands at x 36 (his script adds 4 to his x: the box of Up and the picture are there); area 3 screen
        0, the door at x 208: building 10, the doctor ($43, placed at x 112) stands at x 120 (adds 8) and the smoking man ($3D, at x 16) flips as his script says."""
        for area, screen, door, ident, layout, want in ((0, 2, 80, 2, 1, {0: 36}), (3, 0, 208, 10, 3, {1: 120})):
            with self.subTest(building=ident):
                ram, word, log = self.run_scenario(self.building_args(screen, door, area=area), self.ENTER, 799, "shots_npc_op6")
                self.assertEqual((word("cur_area"), word("building_id")), (4, ident))
                states = self.people_states(4, ident, layout, word("hero_x"), word("hero_y"), 300)
                self.assert_people_as_model(word, states, f"building {ident}")
                got = self.people_raw(word, len(states[0]))
                for i, x in want.items():
                    self.assertEqual(got[i][1], x, f"building {ident}: person {i}'s x")

    def test_the_king_steps_forward_when_the_hero_is_near_and_back_when_he_is_not(self) -> None:
        """The King's room with the hero poked to x 48 (near: the script adds 8 to the King's x, 40, in the near picture) and to x 200 (far: he is back at 32): the model's state."""
        got = {}
        for hero in (48, 200):
            with self.subTest(hero=hero):
                ram, word, log = self.run_scenario(self.building_args(7, 128), self.RING + self.ENTER + [(720, "x", hero)], 799, "shots_npc_king_near")
                self.assertEqual((word("cur_area"), word("building_id"), word("hero_x")), (4, 7, hero))
                states = self.people_states(4, 7, 0, hero, word("hero_y"), 300)
                self.assert_people_as_model(word, states, f"hero at {hero}")
                got[hero] = self.people_info(word, 1)[0]["x"]
        self.assertEqual(got, {48: 40, 200: 32})

    def test_the_people_who_face_the_hero_turn_to_him(self) -> None:
        """Eolis screen 6, the door at x 192 (building 5, the Ring opens it): the magic teacher ($3B, x 16) turns every frame to the hero, who is poked to x 220 (he faces right: bit 0
        of the flags, which the mirror rule reads) and then to x 4 (left): the model's state."""
        faces = {}
        for hero in (220, 4):
            with self.subTest(hero=hero):
                ram, word, log = self.run_scenario(self.building_args(6, 192), self.RING + self.ENTER + [(720, "x", hero)], 799, "shots_npc_turn")
                self.assertEqual((word("cur_area"), word("building_id"), word("hero_x")), (4, 5, hero))
                states = self.people_states(4, 5, 9, hero, word("hero_y"), 300)
                self.assert_people_as_model(word, states, f"hero at {hero}")
                faces[hero] = self.people_info(word, 1)[0]["flags"] & 1
        self.assertEqual(faces, {220: 1, 4: 0}, "he turns to the hero")

    def test_up_at_a_person_who_has_walked_uses_where_he_is_now(self) -> None:
        """In the King's room the King steps to x 40 when the hero is near: his box (left 0, width 48) is hit by a hero at x 87 ((87 + 11 - 40) < 48 + 11) and not by one at x 88; at the
        place he is built at, x 32, 87 would be out (87 + 11 - 32 = 66)."""
        plan = pages(raw_message(self.rom, 0x35))
        start = 720 + 20 + 2
        for hero, typed in ((87, True), (88, False)):
            with self.subTest(hero=hero):
                pokes = self.RING + self.talk_pokes(hero, hero_y=112)
                ram, word, log = self.run_scenario(self.building_args(7, 128), pokes, start + plan[0]["frame"] + 10, "shots_npc_up_walked")
                self.assertEqual(word("hero_x"), hero)
                self.assertEqual((word("tb_vars+10"), word("tb_vars+12")) == (1, 0), typed, "the first page is typed and waits for A" if typed else "no script runs")

    def test_the_king_stands_in_his_room(self) -> None:
        """Eolis screen 7, the door at x 128 (id 7, type 0: the Ring of Elf opens it): the King (entity $3A, script 8) in his room: his script moved him to x 40 when the hero is near (it adds
        8 to the x), at y 112 in the pose of either of his frames, facing right (mirrored: his rule 1), in the slots of palette set 17 (npc.bin); the rest of the room is the
        building's picture."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 4, 7, 0x3A)
        ram, word, log = self.run_scenario(self.building_args(7, 128), self.RING + self.ENTER, 799, "shots_npc_king")
        self.assertEqual((word("cur_area"), word("cur_pal"), word("building_id")), (4, 17, 7))
        slots = self.people_info(word, 2)
        self.assertEqual((slots[0]["ent"], slots[0]["script"], slots[0]["y"]), (0x3A, script, y))
        self.assertIn(slots[0]["x"], (x, x + 8))
        self.assertEqual(slots[1]["ent"], 0xFF, "no second person in this room")
        states = self.people_states(4, 7, 0, word("hero_x"), word("hero_y"), 300)
        self.assert_people_as_model(word, states, "the King")
        got = hs.decode_screen(ram, hs.video_base(log))
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 4, 0, word("camera"), palette_index=17, tiles_index=6,
                                                                              hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0)), npc, 17)

    def talk_pokes(self, hero_x: int, at: int = 720, hero_y: int | None = None):
        """He stands at `hero_x` (and `hero_y`) in the building at frame `at`, and Up is pressed (the script starts in the next frame). The King sits on a step: to
        reach him he stands on it, at y 112 (the floor is 144; the ROM's box test says the same, no talk from the floor)."""
        return self.ENTER + [(at, "x", hero_x)] + ([(at, "y", hero_y)] if hero_y is not None else []) + [(at + 20, "joy", 1), (at + 23, "joy", 0)]

    def test_a_door_in_another_town_puts_the_roms_people_in_the_building(self) -> None:
        """Area 3, the towns after Eolis: screen 0's door at block $94 leads to the building with the id 8 (its type, 4, is the number of another room whose person has the script
        $0D; the ROM's id gives the armour salesman, entity $37 at x 48 with script $19); screen 1's door at block $95 has the id 11 (type 1: the people of room 1 would stand
        there): the priest, entity $39 at x 32 with script $1C, who stands at x 36 (his script adds 4). The ids are the first bytes of the ROM's door records (tests/test_disk.py checks
        every door)."""
        for screen, x, ident, want in ((0, 64, 8, [(0x37, 0x19, 48)]), (1, 80, 11, [(0x39, 0x1C, 36)])):
            ram, word, log = self.run_scenario(self.building_args(screen, x, area=3), self.ENTER, 760, f"shots_npc_town_{ident}")
            self.assertEqual((word("cur_area"), word("building_id")), (4, ident), f"the door of screen {screen}")
            got = sorted((i["ent"], i["script"], i["x"]) for i in self.people_info(word, 2) if i["ent"] != 0xFF)
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
        slot = got[112][80]                                                   # the frame's colour: the text colour (not black)
        self.assertNotEqual(slot, 0, "the frame's top edge is not drawn")
        self.assertEqual(hs.read_palette(log)[slot] & 0x777, 0x777, "the text and the frames are white (the palette on the hardware while the portrait is up)")
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
        self.assertEqual(hs.read_palette(log)[slot] & 0x777, 0x777, "the shop's text and box are white")
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
        """Eolis screen 2, the door at x 224 (id 1, type 6, the house): a person of kind $3F (script 9, stands) at x 64 and one of kind $45 (script 10, walks) from x 144, each in the pose
        the model has for the program's counter, in the slots of the building's palette set (npc.bin); the room is the building's picture."""
        import faxanadu_maps as fm
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        info = fm.building(self.rom, 6)
        ram, word, log = self.run_scenario(self.building_args(2, 224), self.ENTER, 799, "shots_npc_room")
        self.assertEqual((word("cur_area"), word("building_id"), word("cur_pal")), (4, 1, info["palette"]))
        slots = self.people_info(word, 2)
        self.assertEqual((slots[0]["ent"], slots[1]["ent"], slots[0]["x"]), (0x3F, 0x45, 64))
        states = self.people_states(4, 1, 6, word("hero_x"), word("hero_y"), 300)
        self.assert_people_as_model(word, states, "the room")
        got = hs.decode_screen(ram, hs.video_base(log))
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 4, 6, word("camera"), palette_index=info["palette"], tiles_index=info["tiles"],
                                                                              hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0)), npc, info["palette"])

    def street_args(self, screen: int, hero: str, gold: int = 0):
        return ["ALL=1", "AREA=0", f"SCREEN={screen}", f"HERO={hero},0,255,255,0,1", "WORLD=1", f"HUD=16,0,0,{gold},0", f"VIEWER_DEFS={self.NPC_DEFS} --defsym NO_ENEMIES=1"]

    def test_a_person_walks_in_the_street_in_the_outside_colours(self) -> None:
        """Eolis screen 1: the walker $34 (script 1) is where the model has him after the program's updates, in the pose and the mirror the model picks, in the slots of palette set 0;
        the rest is the screen's picture with the hero."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        ram, word, log = self.run_scenario(self.street_args(1, "144,144"), [], 700, "shots_npc_street")
        got = hs.decode_screen(ram, hs.video_base(log))
        states = self.people_states(0, 1, 1, 144, 144, 800)
        self.assert_people_as_model(word, states, "the street")
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(144, 144, 0, 255, 255, 0, True)), npc, 0)

    def test_up_at_a_person_in_the_street_starts_his_script(self) -> None:
        """The hero stands at x 144 while the walker $34 (the box: left -8, width 32) walks by: Up alone, newly pressed, when the model has his box over the hero's for a while
        (`box_hit`): script 1 (no gold): message $27 is typed on the box at the top of the window (the hero stands at y 144: no portrait). Up with Left held, a few frames before,
        does nothing."""
        npc, _ = self.town_files()
        bounds = {k["entity"]: k["bounds"] for k in npc["kinds"]}
        states = self.people_states(0, 1, 1, 144, 144, 800)
        hit = [n for n in range(800) if self.box_hit(bounds, states[n], 144, 144)]
        first = next(f for f in range(660, 780) if all(f - self.UPDATES_BEHIND + d in hit for d in range(-14, 6)))          # (a window of updates around the frame: where the frame falls is not exact)
        plan = pages(raw_message(self.rom, 0x27))
        pokes = [(first - 20, "joy", 1 | 4), (first - 17, "joy", 0), (first, "joy", 1), (first + 3, "joy", 0)]
        start = first + 2
        ram, word, log = self.run_scenario(self.street_args(1, "144,144"), pokes, start + plan[0]["frame"] + 10, "shots_npc_up")
        self.assertEqual((word("tb_vars+10"), word("tb_vars+12")), (1, 0), "the first page is typed and waits for A")
        rows = word.raw("tb_rows", 64).decode("latin-1")
        self.assertEqual([rows[i:i + 16] for i in range(0, 64, 16)], plan[0]["rows"])
        self.assertEqual(word("portrait_k"), -1, "a person in the street has no portrait")

    def test_a_walker_in_front_of_a_door_does_not_keep_the_hero_out(self) -> None:
        """Eolis screen 1, the hero at the door at x 48 while the walker $34 walks by (the model has his box over the hero's for a while): Up opens the door (building 0) and does
        not start the walker's script: in the game the door comes first (Player_CheckHandleEnterDoor is in the player's update, the sprites' collision handlers after it; jsnes: Up
        at a door with a person over the hero enters it)."""
        npc, _ = self.town_files()
        bounds = {k["entity"]: k["bounds"] for k in npc["kinds"]}
        states = self.people_states(0, 1, 1, 48, 144, 800)
        hit = [n for n in range(800) if self.box_hit(bounds, states[n], 48, 144)]
        first = next(f for f in range(599, 780) if all(f - self.UPDATES_BEHIND + d in hit for d in range(-14, 6)))
        ram, word, log = self.run_scenario(self.building_args(1, 48), [(first, "joy", 1), (first + 3, "joy", 0)], first + 130, "shots_npc_door")
        self.assertEqual((word("cur_area"), word("building_id")), (4, 0), "the door opened")
        self.assertEqual(word("tb_vars+10"), 0, "no message was typed")

    def test_up_at_a_locked_door_with_a_person_over_him_shows_the_hint_and_not_the_persons_script(self) -> None:
        """Eolis screen 7, the King's door (key requirement 6, the Ring of Elf: he has none), the hero at the door's x and the guard ($42) patrolling over it; Up while his box is over the hero's.
        The ROM (tests/test_npc.py, jsnes: `Player_CheckHandleEnterDoor` is in the player's update, the sprites' Up handler (CMP #$08) after it) runs the door's script ($7F: message $A9) and
        never the person's, not even after the message is dismissed. The port: the hint's box (in the middle of the window) is up in the first capture, in the second, after A, the picture
        is the street again with the guard and no script has started."""
        import faxanadu_text as ft
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        bounds = {k["entity"]: k["bounds"] for k in npc["kinds"]}
        states = {x: self.people_states(0, 7, 7, x, 144, 800) for x in (128, 112)}
        hit = {x: [n for n in range(800) if self.box_hit(bounds, states[x][n], x, 144)] for x in states}
        first = next(f for f in range(599, 780) if all(f - self.UPDATES_BEHIND + d in hit[x] for x in hit for d in range(-14, 6)))     # (a time when his box is over both places)
        up = [(first, "joy", 1), (first + 3, "joy", 0)]
        ram, word, log = self.run_scenario(self.street_args(7, "112,144"), up, first + 40, "shots_npc_locked_control")
        self.assertEqual((word("cur_screen"), word("tb_vars")), (7, 7), "the control, one block from the door: the same Up, with the guard's box over him, starts the guard's script (7)")
        ram, word, log = self.run_scenario(self.street_args(7, "128,144"), up, first + 40, "shots_npc_locked")
        self.assertEqual((word("cur_area"), word("cur_screen"), word("tb_vars")), (0, 7, 0), "still in the street, no script has started (tb_vars holds the number of the script that ran last)")
        got = hs.decode_screen(ram, hs.video_base(log))
        expected = sc.expected_screen(self.rom, 0, 7, word("camera"), hero=sc.Hero(128, 144, 0, 255, 255, 0, True))
        self.text_box(expected, self.rom, 0, ft.message(self.rom, 0xA9))
        text = ft.message(self.rom, 0xA9)
        height = 10 * len(text.split("\n")) + 8
        y0 = 32 + (168 - height) // 2
        bad = [(x, y) for y in range(y0, y0 + height) for x in range(80, 240) if got[y][x] != expected[y][x]]
        self.assertEqual(bad[:5], [], "the door's hint is on a box over the window")
        self.assertGreater(first, 0)
        pokes = up + [(first + 60, "joy", 0x80), (first + 64, "joy", 0)]
        ram, word, log = self.run_scenario(self.street_args(7, "128,144"), pokes, first + 200, "shots_npc_locked_after")
        self.assertEqual((word("cur_area"), word("cur_screen"), word("tb_vars"), word("tb_vars+12")), (0, 7, 0, 0), "the hint is gone and no script (the guard's, 7) started after it")
        got = hs.decode_screen(ram, hs.video_base(log))
        states = self.people_states(0, 7, 7, 128, 144, 1000)
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 0, 7, word("camera"), hero=sc.Hero(128, 144, 0, 255, 255, 0, True)), npc, 0)

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
        """He walks off the left edge of Eolis screen 1: the walker of screen 1 is gone, screen 2's person (kind $45, script 3, from x 112) is there once the scroll is done, where
        the model has her, drawn over the new screen's picture."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 0, 2, 0x45)
        args = ["ALL=1", "AREA=0", "SCREEN=1", "HERO=16,144,0,255,255,0,1", "WORLD=1", f"VIEWER_DEFS={self.NPC_DEFS} --defsym NO_ENEMIES=1"]
        ram, word, log = self.run_scenario(args, [(599, "joy", 4), (660, "joy", 0)], 799, "shots_npc_scroll")
        self.assertEqual(word("cur_screen"), 2)
        slots = self.people_info(word, 2)
        self.assertEqual((slots[0]["ent"], slots[0]["script"], slots[0]["y"], slots[1]["ent"]), (0x45, script, y, 0xFF))
        states = self.people_states(0, 2, 2, word("hero_x"), word("hero_y"), 300)
        self.assert_people_as_model(word, states, "the next screen")
        got = hs.decode_screen(ram, hs.video_base(log))
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 0, 2, word("camera"), hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0)), npc, 0)

    def test_walking_out_of_a_building_brings_the_street_back_with_its_people(self) -> None:
        """In the building of Eolis screen 1's door (x 48), off its right side: screen 1 again, the walker $34 where the model has him (the hero stands at the door), in the outside
        colours (the room's palette with its people's colours is gone), the people of the room are not drawn."""
        import hatari_shot as hs
        import st_convert as sc

        npc, _ = self.town_files()
        script, x, y = self.person(npc, 0, 1, 0x34)
        pokes = self.ENTER + [(699, "x", 240), (700, "joy", 8), (703, "joy", 0)]
        ram, word, log = self.run_scenario(self.building_args(1, 48), pokes, 899, "shots_npc_out")
        self.assertEqual((word("cur_area"), word("cur_screen")), (0, 1))
        slots = self.people_info(word, 2)
        self.assertEqual((slots[0]["ent"], slots[0]["script"], slots[1]["ent"]), (0x34, script, 0xFF))
        states = self.people_states(0, 1, 1, word("hero_x"), word("hero_y"), 300)
        self.assert_people_as_model(word, states, "the street again")
        got = hs.decode_screen(ram, hs.video_base(log))
        self.assert_people_shown(word, got, states, lambda: sc.expected_screen(self.rom, 0, 1, word("camera"), hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, 0, word("hero_flip") != 0)), npc, 0)


if __name__ == "__main__":
    unittest.main()
