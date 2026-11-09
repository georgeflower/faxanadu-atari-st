"""The Mattock (src/items.s `use_mattock`) in Hatari. The ROM's rules are in the spec the code quotes: one block in front of the top of the hero, matched
against USE_MATTOCK_BLOCK_TRANSITIONS, message $AB, four steps of four frames, nothing kept when the screen is left."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (borrowed: the scene runner and the picture helpers; the class itself is not imported)

TRUNK = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym NO_ENEMIES=1"]
WALL = {10 * 16 + 3: 0x63, 11 * 16 + 3: 0x63}


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class MattockTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario
    assert_picture = tv.ViewerTests.assert_picture
    use_pokes = staticmethod(tv.ViewerTests.use_pokes)

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def picture(self, ram, log, word, patch, hero=(40, 160)):
        import hatari_shot as hs
        import faxanadu_maps as fm
        import st_convert as sc

        rows = hs.decode_screen(ram, hs.video_base(log))
        want = sc.expected_screen(self.rom, 1, 12, word("camera"), hero=sc.Hero(hero[0], hero[1], 0, 255, 0, 0, True), state=dict(hp=80, mp=80, experience=0, gold=0, seconds=0),
                                  patch=patch)
        self.assert_picture(rows, want)

    def run_multi(self, make_args, pokes, captures, name):
        """`tv.ViewerTests.run_scenario` with one Hatari run for many captures (one a VBL): returns [(rows, word)] in the order of `captures`; the screen is the one on show at that VBL."""
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(tv.ROOT), "viewer", *make_args], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(tv.ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (tv.ROOT / "build" / "viewer.bin").read_bytes()
        work = tv.ROOT / "build" / name
        work.mkdir(parents=True, exist_ok=True)
        prg = tv.ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(hatari, tv.TOS, prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        base = (work / "ram0.bin").read_bytes().find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        script = ""
        for i, (vbl, what, value) in enumerate(pokes):
            vbl += tv.START_DELAY
            if what == "joy":
                text = f"memwrite ${base + sym['input_state'] + 259:x} 0x{value:02x}\ncont\n"
            elif what == "b":
                text = f"memwrite ${base + sym['input_state'] + 264 + 0x38:x} 0x{value:02x}\ncont\n"
            elif what == "inv":
                text = f"memwrite ${base + sym['inv'] + (value >> 8):x} 0x{value & 255:02x}\ncont\n"
            elif what.startswith("w:"):
                text = f"memwrite ${base + sym[what[2:]]:x} 0x{(value >> 8) & 255:02x} 0x{value & 255:02x}\ncont\n"
            elif what.startswith("mem:"):
                symbol, _, offset = what[4:].partition("+")
                text = f"memwrite ${base + sym[symbol] + int(offset or 0):x} 0x{value & 255:02x}\ncont\n"
            else:
                raise ValueError(what)
            (work / f"poke{i}.ini").write_text(text, encoding="utf-8")
            script += f"b VBL > {vbl} :once :file {work / f'poke{i}.ini'}\n"
        for i, vbl in enumerate(captures):
            (work / f"cap{i}.ini").write_text(f"savebin {work / f'ram{i + 1}.bin'} 0 $80000\nm $ff8200-$ff8260\ncont\n", encoding="utf-8")
            script += f"b VBL > {vbl + tv.START_DELAY} :once :file {work / f'cap{i}.ini'}\n"
        log = hs.run_hatari(hatari, tv.TOS, prg, work, captures[-1] + tv.START_DELAY + 1, "0", script, None)
        bases = [(int(m.group(2), 16) << 16) | (int(m.group(4), 16) << 8) for m in re.finditer(r"^00FF8200: ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2}) ([0-9a-fA-F]{2})", log, re.M)]
        self.last_log = log
        self.assertEqual(len(bases), len(captures), "every capture was made")
        out = []
        for i in range(len(captures)):
            ram = (work / f"ram{i + 1}.bin").read_bytes()

            def word(name: str, ram=ram) -> int:
                symbol, _, offset = name.partition("+")
                at = base + sym[symbol] + int(offset or 0)
                return int.from_bytes(ram[at:at + 2], "big", signed=True)
            word.raw = lambda name, n, ram=ram: ram[base + sym[name]:base + sym[name] + n]
            out.append((hs.decode_screen(ram, bases[i]), word))
        return out

    STATE = dict(hp=80, mp=80, experience=0, gold=0, seconds=0)
    STAGES = [{}, {i: 0x85 for i in WALL}, {i: 0x86 for i in WALL}, {i: 0x42 for i in WALL}]

    def crumble(self, args, pokes, before_vbl, first, last, name, hero_at=(40, 160), keep=True, later=None, mp=80, patches=None):
        """The whole crumble, a capture at every VBL from `first` to `last` (and one at `before_vbl`, a plain frame before the item is used, whose sprite pixels are the oracle for what
        enemies and people look like: whatever differs from the converter's plain screen outside the hero; `later` is one more capture, long after). What is on the screen at each VBL is the
        message box, or one of the stages of the wall (`patches`: $63, $85, $86, $42) with those sprite pixels over it (not with `keep` False: the spell) and the hero; the HUD is not looked at.
        Returns (the sprite pixels, the stage of each capture: "box", 0 to 3 or None for neither, the captures, the late capture)."""
        import faxanadu_maps as fm
        import st_convert as sc

        patches = patches or self.STAGES
        shots = self.run_multi(args, pokes, [before_vbl] + list(range(first, last + 1)) + ([later] if later else []), name)
        (before, word0), shots = shots[0], shots[1:]
        late = shots.pop() if later else None
        self.word_before = word0
        camera = word0("camera")
        pal = fm.area(self.rom, 1).palette_index
        plan = sc.plan_for_set(self.rom, pal)
        state = dict(self.STATE, mp=mp)
        plain = sc.expected_screen(self.rom, 1, 12, camera, state=state)
        hero_before = sc.hero_layer(self.rom, sc.Hero(*hero_at, 0, 255, 255, word0("hero_frame"), True), pal, plan)
        sprites = {(x, y): before[y][x] for y in range(sc.ST_TOP, 200) for x in range(32, 288)
                   if before[y][x] != plain[y][x] and (x, y + camera) not in hero_before}
        stage_plain = [sc.expected_screen(self.rom, 1, 12, camera, state=state, patch=patch) for patch in patches]
        cache: dict = {}

        def wanted(n: int, frame: int):
            if (n, frame) not in cache:
                want = [row[:] for row in stage_plain[n]]
                for (x, y), c in (sprites.items() if keep else ()):
                    want[y][x] = c
                for (x, line), slot in sc.hero_layer(self.rom, sc.Hero(*hero_at, 0, 255, 255, frame, True), pal, plan).items():
                    want[line - camera][x] = slot
                cache[(n, frame)] = want
            return cache[(n, frame)]

        xs = [x for x, _ in sprites]
        ys = [y for _, y in sprites]
        box = (min(xs), max(xs), min(ys), max(ys)) if sprites else (0, -1, 0, -1)
        first_rows = shots[0][0]
        boxed = [(x, y) for y in range(sc.ST_TOP, 200) for x in range(100, 288) if first_rows[y][x] != wanted(0, shots[0][1]("hero_frame"))[y][x]]
        self.assertGreater(len(boxed), 200, "the message box is on the screen at the first capture")
        boxed = boxed[::max(1, len(boxed) // 400)]
        stages = []
        for rows, word in shots:
            frame = word("hero_frame")
            found = None
            for n in range(len(patches)):
                want = wanted(n, frame)
                if rows[sc.ST_TOP:] == want[sc.ST_TOP:]:               # (the playfield: the HUD's item box is emptied after the box has gone, tests/test_items.py)
                    found = n
                    break
                # a sprite pixel whose colour was that of the old wall is not in `sprites`: where the sprite lies over the cells that change, the old picture's pixel is allowed too
                if all(rows[y][x] == want[y][x] or (n and box[0] <= x <= box[1] and box[2] <= y <= box[3] and 80 <= x < 96 and rows[y][x] == before[y][x]) for y in range(sc.ST_TOP, 200) for x in range(320)):
                    found = n
                    break
            if found is None and all(rows[y][x] == first_rows[y][x] for x, y in boxed):
                found = "box"
            stages.append(found)
        self.last_stages = stages
        return sprites, stages, shots, late

    def assert_sequence(self, stages: list, first: int, count: int = 4) -> None:
        """`stages` as `crumble` returns it (a capture is "box", a stage 0 to count - 1 or None), up to the first capture of the last stage when there are several (the game goes on after that:
        his sword, the walkers, the spell move again): the box first, then at every capture one of the stages with the sprites, only forward, and all seen: no capture in between with the box
        gone and a sprite not on the screen."""
        if count > 1 and count - 1 in stages:
            stages = stages[:stages.index(count - 1) + 1]
        seen = [n for n in stages if isinstance(n, int)]
        self.assertTrue(seen, f"the crumble is on the screen at some capture: {stages}")
        start = stages.index(seen[0])
        self.assertGreater(start, 0, "the box is up at the first capture")
        self.assertEqual([n for n in stages[:start]], ["box"] * start, f"the box, then the wall: {stages}")
        gaps = [first + i for i, n in enumerate(stages) if i > start and not isinstance(n, int)]
        self.assertEqual(gaps, [], f"captures (VBLs) after the box went at which the picture is not the wall with its sprites and the hero: {gaps} (stages {stages})")
        self.assertEqual(seen, sorted(seen), f"the wall's stages only go forward: {stages}")
        self.assertEqual(set(seen), set(range(count)), f"all the stages are seen: {stages}")

    def test_the_tables_are_the_roms(self) -> None:
        import itempics
        import faxanadu_maps as fm

        table = itempics.mattock_table(self.rom)
        self.assertEqual(table.hex(), "00000000" "63858642" + "00000000" * 6)
        self.assertEqual(bytes(self.rom.at("USE_MATTOCK_BLOCK_DISTANCES", 2)), b"\xff\x10")
        a = fm.area(self.rom, 1)
        blocks = fm.decode_screen(self.rom, a, 12)
        self.assertEqual({i: blocks[i] for i in WALL}, WALL)

    def test_the_wall_crumbles_in_four_steps_and_he_can_walk_through(self) -> None:
        """Trunk screen 12, hero at x 40 facing the wall (rows 10 and 11, column 3): Down and B, the message ($AB), then the Mattock is gone, the wall
        goes in steps ($63, $85, $86, $42 in both cells) and he walks on through the gap. Without the Mattock nothing happens and the wall stops him."""
        item = [(380, "inv", 36 << 8 | 9)]
        ram, word, log = self.run_scenario(TRUNK, item + self.use_pokes(599) + [(700, "joy", 8)], 600, "shots_mattock")
        self.assertEqual(word.raw("inv", 37)[36], 9, "the message is up, the Mattock still there")
        ram, word, log = self.run_scenario(TRUNK, item + self.use_pokes(599), 720, "shots_mattock")       # (the B press is a sword swing too: wait for it to end)
        self.assertEqual(word.raw("inv", 37)[36], 255, "used up")
        self.picture(ram, log, word, {i: 0x42 for i in WALL})
        pokes = item + self.use_pokes(599) + [(660, "joy", 8)]
        ram, word, log = self.run_scenario(TRUNK, pokes, 760, "shots_mattock")
        self.assertGreater(word("hero_x"), 70, "through the gap")
        ram, word, log = self.run_scenario(TRUNK, [(660, "joy", 8)], 760, "shots_mattock")
        self.assertLess(word("hero_x"), 48, "the wall stops him")

    def test_the_enemies_stay_on_the_screen_while_the_wall_crumbles(self) -> None:
        """The game stands still during the crumble and the ROM's sprites stay on the screen (the OAM is not touched). A Trunk Hornet is put on the wall (x 56, y 168: over the
        two cells that change, half of it outside them) and the Hour Glass holds it still. The picture of the screen before the Mattock is used gives the sprite's pixels (the
        Hornet's: whatever differs from the converter's plain screen); then every VBL from the message's dismissal to the end of the crumble is captured and is the plain screen with
        the wall at one of its four stages and those pixels over it, from the first VBL after the box went: the enemies are on the screen at every one (the box's screens used to be
        made with the hero and the people only, and the Hornet was off the screen for about three frames)."""
        args = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0"]
        pokes = [(380, "inv", 36 << 8 | 9), (560, "w:hourglass", 3000), (560, "mem:enemies+182", 56), (560, "mem:enemies+184", 168)] + self.use_pokes(599)
        sprites, stages, _, _ = self.crumble(args, pokes, 596, 612, 650, "shots_mattock_enemy")
        self.assertGreater(sum(1 for (x, y) in sprites if x < 96), 20, "the Hornet's pixels over the cells that change")
        self.assert_sequence(stages, 612)

    def test_a_person_stays_on_the_screen_while_the_wall_crumbles(self) -> None:
        """The people are drawn again at every step too (`npc_erase_boxes`, `npc_draw`). Trunk has no people, and none of the screens with a wall the Mattock works on has one (the walls
        of the other areas are the ROM's id 0, air: the blocks in front of him become air, which is no change on a screen with an empty background), so the test build puts one in
        (NPC_EXTRA: $37, a man who stands, at x 56, y 160, over the two cells that change). As the enemy's: every VBL from the box's going to the end is a stage with his pixels."""
        defs = "VIEWER_DEFS=--defsym NPCS=1 --defsym NO_ENEMIES=1 --defsym NPC_EXTRA=0x37 --defsym NPC_EXTRA_X=56 --defsym NPC_EXTRA_Y=160"
        args = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0", defs]
        pokes = [(380, "inv", 36 << 8 | 9)] + self.use_pokes(599)
        sprites, stages, _, _ = self.crumble(args, pokes, 596, 612, 650, "shots_mattock_person")
        self.assertGreater(sum(1 for (x, y) in sprites if x < 96), 20, "his pixels over the cells that change")
        self.assertGreater(len(sprites), 60, "he is drawn")
        self.assert_sequence(stages, 612)

    def test_a_spell_in_flight_waits_and_is_not_on_the_screen_while_the_wall_crumbles(self) -> None:
        """Up and fire cast Death, then Down and fire use the Mattock while the spell flies (the ROM does not look at the spell: checked with jsnes, `tools/refnes/mattockspell.mjs`; the hero
        stands against the wall, the spell is at x 40 when the item is used). The ROM's spell stands still, takes no part in the box and the crumble (its sprites are off the screen from
        the message on: the OAM of the crumble is the same with and without a spell) and goes on flying when the game does (from x 44, a frame later, through the gap). So here: the spell
        is on the screen just before, its state does not move from the message to the end of the crumble, every VBL of the crumble is the wall's stage with the hero only, and later it has flown on."""
        args = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=32,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym NO_ENEMIES=1 --defsym MAGIC=3"]
        pokes = [(380, "inv", 36 << 8 | 9), (560, "joy", 0x81), (562, "joy", 0)] + self.use_pokes(564)
        sprites, stages, shots, late = self.crumble(args, pokes, 563, 576, 603, "shots_mattock_spell", hero_at=(32, 160), keep=False, later=640, mp=70)
        self.assertGreater(len(sprites), 8, "the spell is on the screen before the item is used")
        self.assertEqual((self.word_before("spell_state"), self.word_before("spell_state+4")), (3, 38), "Death at x 38, flying")
        self.assert_sequence(stages, 576)
        frozen = {tuple(word.raw("spell_state", 18)) for _, word in shots[:stages.index(3) + 1]}
        self.assertEqual(len(frozen), 1, f"from the message to the end of the crumble the spell stands still: {frozen}")
        self.assertEqual(shots[0][1]("spell_state"), 3)
        self.assertGreater(late[1]("spell_state+4"), 44, "and it flies on afterwards")

    def test_the_enemies_stay_on_the_screen_when_the_box_of_an_item_goes(self) -> None:
        """The same box path, `use_spent`, is every item's: the Wing Boots (item 15) used with a Hornet on the screen (the Hour Glass holds it still): from the first VBL after the box went the
        picture is the plain screen with the Hornet's pixels (from a capture before) and the hero, at every VBL (it was off the screen for about three frames)."""
        args = ["ALL=1", "AREA=1", "SCREEN=12", "HERO=40,160,0,255,255,0,1", "WORLD=1", "HUD=80,80,0,0,0"]
        pokes = [(380, "inv", 36 << 8 | 15), (560, "w:hourglass", 3000), (560, "mem:enemies+182", 120), (560, "mem:enemies+184", 168)] + self.use_pokes(599)
        sprites, stages, _, _ = self.crumble(args, pokes, 596, 612, 627, "shots_mattock_boots", patches=[{}])
        self.assertGreater(len(sprites), 60, "the Hornet is drawn")
        self.assert_sequence(stages, 612, 1)

    def test_nothing_happens_when_the_block_in_front_is_not_the_one(self) -> None:
        """Hero at x 100: the block in front of his head is not $63: no message, the Mattock stays in hand."""
        ram, word, log = self.run_scenario([a.replace("HERO=40", "HERO=100") for a in TRUNK], [(380, "inv", 36 << 8 | 9)] + self.use_pokes(599), 640, "shots_mattock_miss")
        self.assertEqual(word.raw("inv", 37)[36], 9)

    def test_the_screen_is_whole_again_when_he_comes_back(self) -> None:
        """Nothing is kept (the ROM makes the screen from its data each time): after the wall is broken he walks off the left edge and back, and the wall stands."""
        pokes = [(380, "inv", 36 << 8 | 9)] + self.use_pokes(599) + [(650, "joy", 4), (740, "joy", 0), (1000, "joy", 8), (1100, "joy", 0)]
        ram, word, log = self.run_scenario(TRUNK, pokes, 1300, "shots_mattock_back")
        self.assertEqual(word("cur_screen"), 12)
        self.picture(ram, log, word, {}, hero=(word("hero_x"), word("hero_y")))


if __name__ == "__main__":
    unittest.main()
