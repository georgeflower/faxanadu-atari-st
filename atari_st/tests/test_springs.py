"""The springs of Trunk ($61 to $63), the fountain ($52) and the way to Mascon (Trunk's screen 40): the ROM in jsnes (`tools/refnes/springprobe.mjs`) against the
Python model (`enemy_model`: the behaviours 57 to 60 and the pictures) and against the timings `src/water.s` uses; the port in Hatari (pictures, quest bits, the
stone, the ladder, the restore when the screen is drawn again)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
HARNESS = shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists()
WATER = (0x52, 0x61, 0x62, 0x63)

# (name, spec): the hero comes out of a temple onto the screen with the quests and special items given
SPECS = {
    "trunk_flows": {"screen": 61, "x": 96, "y": 144, "quests": 0, "frames": 80, "pokes": [[20, "Quests", 1]]},
    "trunk_right": {"screen": 61, "x": 216, "y": 144, "right": 1, "quests": 1, "frames": 60},
    "sky": {"screen": 37, "x": 64, "y": 144, "quests": 2, "frames": 60},
    "joker_dry": {"screen": 63, "x": 64, "y": 144, "quests": 3, "frames": 70, "pokes": [[40, "Quests", 7]]},
    "fountain_dry": {"screen": 40, "x": 32, "y": 144, "quests": 3, "frames": 40, "pokes": [[20, "Quests", 7]]},
    "fountain": {"screen": 40, "x": 32, "y": 144, "quests": 7, "frames": 40},
    "push": {"screen": 40, "x": 80, "y": 80, "right": 1, "quests": 7, "special": 0x40, "frames": 200, "hold": [[5, 190, "RIGHT"]]},
    "push_left": {"screen": 40, "x": 112, "y": 80, "right": 0, "quests": 7, "special": 0x40, "frames": 200, "hold": [[5, 190, "LEFT"]]},
    "push_no_ring": {"screen": 40, "x": 80, "y": 80, "right": 1, "quests": 7, "special": 0, "frames": 130, "hold": [[5, 125, "RIGHT"]]},
    "push_let_go": {"screen": 40, "x": 80, "y": 80, "right": 1, "quests": 7, "special": 0x40, "frames": 260, "hold": [[5, 60, "RIGHT"], [62, 250, "RIGHT"]]},
    "open_again": {"screen": 40, "x": 32, "y": 144, "quests": 0x27, "special": 0x40, "frames": 60},
}


def timeline(rec: list) -> dict:
    """What the ROM's run shows of the way to Mascon, in frames from the push that opened it (or from the screen's first tick): when the push counter reached 63
    (sound $0F), the frame the stone moved (0), when it was gone, the frames of the ladder's blocks (sound $17 each) and when the game went on."""
    stone = lambda r: r["blocks"][8:14]
    out = {}
    first = next((n for n, r in enumerate(rec) if r["opening"]), None)
    if first is None:
        return out
    out["push63"] = next((n - first for n, r in enumerate(rec) if r["push"] == 63), None)
    gone = next(n for n in range(first, len(rec)) if 0x88 not in stone(rec[n]))
    out["gone"] = gone - first
    out["ladder"] = [n - first for n in range(first + 1, len(rec)) if rec[n]["blocks"][:8] != rec[n - 1]["blocks"][:8] or (rec[n]["sfx"] == 0x17 and rec[n - 1]["sfx"] != 0x17)]
    out["resume"] = next(n for n in range(first + 1, len(rec)) if rec[n]["counter"] != rec[first]["counter"]) - first
    out["moved_to"] = [i for i, b in enumerate(stone(rec[first])) if b == 0x88]
    return out


@unittest.skipUnless(ROM.exists() and HARNESS, "needs the ROM and the jsnes harness")
class SpringsInTheRomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)
        cls.bank14 = cls.rom.prg(14)
        o = cls.rom.label("Sprites_UpdateAll").offset - fr.HEADER - 14 * fr.BANK
        cls.random_table = cls.bank14[o:o + 256]
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = {}
        cache = os.environ.get("SPRING_CACHE")
        for name, spec in SPECS.items():
            out = Path(cache or cls.tmp.name) / f"spring_{name}.json"
            if not (cache and out.exists()):
                specfile = Path(cls.tmp.name) / f"{name}.spec.json"
                specfile.write_text(json.dumps(spec))
                subprocess.run(["node", "springprobe.mjs", str(specfile), str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            cls.runs[name] = json.loads(out.read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def replay(self, name: str):
        import enemy_data as ed
        import enemy_model as em

        rec = self.runs[name]
        eng = em.Engine(self.bank14, self.random_table, bytes(256), bytes(256))
        start = next(n for n, r in enumerate(rec) if any(s["Entities"] in WATER and s["Flags"] & 0x40 for s in r["slots"]))
        for ent in WATER:
            eng.kinds[ent] = dict(ed.kind_info(self.rom, ent))
        for i, s in enumerate(rec[start]["slots"]):
            sp = eng.sprites[i]
            if s["Entities"] not in WATER:
                continue
            sp.ent, sp.x, sp.y, sp.flags, sp.phase, sp.beh, sp.d2, sp.d3, sp.arg1 = (s["Entities"], s["x"], s["y"], s["Flags"], s["Phases"], s["Behaviors"],
                                                                                    s["BehaviorData2"], s["BehaviorData3"], s["BehaviorArg1"])
            sp.script = s["BehaviorAddrs_L"] | s["BehaviorAddrs_U"] << 8
        for n in range(start + 1, len(rec)):
            if rec[n]["counter"] == rec[n - 1]["counter"]:
                continue
            eng.hero.quests = rec[n]["quests"]
            eng.counter = rec[n]["counter"]
            for sp in eng.sprites:
                if sp.ent != 255:
                    eng.update_behaviour(sp)
            yield n, eng

    def test_the_model_runs_the_springs_and_the_fountain_as_the_rom(self) -> None:
        checked = 0
        for name in SPECS:
            rec = self.runs[name]
            for n, eng in self.replay(name):
                for i, s in enumerate(rec[n]["slots"]):
                    if s["Entities"] not in WATER:
                        continue
                    sp = eng.sprites[i]
                    self.assertEqual((sp.ent, sp.x, sp.y, sp.flags, sp.phase, sp.d2, sp.d3),
                                     (s["Entities"], s["x"], s["y"], s["Flags"], s["Phases"], s["BehaviorData2"], s["BehaviorData3"]), f"{name} frame {n} slot {i}")
                    checked += 1
        self.assertGreater(checked, 300)

    def test_the_pictures_are_the_roms_one_frame_later(self) -> None:
        import enemy_data as ed
        import enemy_model as em
        import faxanadu_sprites as fs

        drawn = hidden = 0
        for name in SPECS:
            rec = self.runs[name]
            for n in range(1, len(rec) - 1):
                if rec[n]["counter"] == rec[n - 1]["counter"] or rec[n + 1]["counter"] == rec[n]["counter"]:
                    continue
                slots = rec[n]["slots"]
                masks = em.flip_masks([(s["Entities"], s["Flags"], s["HitCounter"], s["Phases"]) for s in slots], rec[n]["counter"], rec[n - 1]["pf"])
                oam = [(y, t, a & ~0x20, x) for y, t, a, x in rec[n + 1]["oam"]]
                for i, s in enumerate(slots):
                    ent = s["Entities"]
                    if ent not in WATER:
                        continue
                    ours = [o for o in oam if s["PPUOffsets"] <= o[1] < s["PPUOffsets"] + 12]
                    if not em.is_drawn(ent, s["Phases"], rec[n]["counter"], s["BehaviorData2"], s["Flags"]):
                        self.assertEqual(ours, [], f"{name} frame {n}: nothing of entity {ent:#x}")
                        hidden += 1
                        continue
                    app = fs.appearance(self.rom, ed.entity(self.rom, ent)["appearance"] + em.appearance_offset(ent, s["Phases"], rec[n]["counter"], s["BehaviorData2"]),
                                        "TILEINFO_ENTITY_ADDRS")
                    want = [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(app, s["x"], s["y"], masks[i], s["PPUOffsets"]) if sp.y < 240]
                    self.assertEqual(sorted(want), sorted(ours), f"{name} frame {n} entity {ent:#x}")
                    drawn += 1
        self.assertGreater(drawn, 100)
        self.assertGreater(hidden, 10)

    def test_the_way_to_mascon_opens_with_the_timings_water_s_uses(self) -> None:
        push = timeline(self.runs["push"])
        self.assertEqual(push["push63"], -33)                   # the sound at 63, the way at 96
        self.assertEqual(push["moved_to"], [2, 5])              # the stone went one block right (places $57 and $67)
        self.assertEqual(push["gone"], 30)
        self.assertEqual(push["ladder"], [34, 38, 42, 46, 50, 54, 58])
        self.assertEqual(push["resume"], 58)
        left = timeline(self.runs["push_left"])
        self.assertEqual(left["moved_to"], [0, 3])              # one block left ($55 and $65)
        self.assertEqual((left["gone"], left["ladder"]), (30, [34, 38, 42, 46, 50, 54, 58]))
        again = timeline(self.runs["open_again"])
        self.assertEqual(again["gone"], 0)                      # entered with the way open: no wait, the stone is gone at once
        self.assertEqual(again["ladder"], [4, 8, 12, 16, 20, 24, 28])
        self.assertEqual(self.runs["open_again"][-1]["blocks"][:7], [0x20] * 7)
        self.assertEqual(self.runs["push"][-1]["quests"], 0x27)
        self.assertTrue(all(r["opening"] == 0 and r["push"] == 0 for r in self.runs["push_no_ring"]))      # no Ruby Ring: nothing
        let_go = self.runs["push_let_go"]                       # let go for two frames: the count starts again from 0
        self.assertIn(0, [r["push"] for r in let_go[58:66]])
        opened = lambda rec: next(n for n, r in enumerate(rec) if r["opening"]) - next(n for n in range(1, len(rec)) if rec[n]["push"] == 1 and rec[n - 1]["push"] == 0 and n > 61 or rec is self.runs["push"] and rec[n]["push"] == 1)
        self.assertEqual(opened(let_go), opened(self.runs["push"]))
        self.assertEqual(opened(self.runs["push"]), 95)        # the push that makes the count 96 opens it


if __name__ == "__main__":
    unittest.main()


import test_viewer as tv  # noqa: E402
import test_mattock as tm  # noqa: E402

TRUNK = ["ALL=1", "AREA=1", "WORLD=1", "HUD=80,80,0,0,0"]
RIGHT, LEFT = 8, 4               # the stick's bits (input_state + 259)
T0 = 520                         # the scenes' VBLs count from here (TOS has started the program and its first screen is up)


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class SpringsOnTheStTests(unittest.TestCase):
    assert_picture = tv.ViewerTests.assert_picture

    def run_multi(self, make_args, pokes, captures, name):
        """`test_mattock.MattockTests.run_multi`, each `word` with `mem(address, n)`: bytes of the machine's memory at the capture."""
        shots = tm.MattockTests.run_multi(self, make_args, pokes, captures, name)
        for i, (_, word) in enumerate(shots):
            ram = (tv.ROOT / "build" / name / f"ram{i + 1}.bin").read_bytes()
            word.mem = lambda a, n, ram=ram: ram[a:a + n]
        return shots

    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    @staticmethod
    def slots(word) -> list:
        """The eight enemy slots (src/enemy.s, E_BYTES 30): (entity, flags, x, y, phase, d2, d3)."""
        raw = word.raw("enemies", 8 * 30)
        return [(raw[i * 30], raw[i * 30 + 1], raw[i * 30 + 2], raw[i * 30 + 4], raw[i * 30 + 6], raw[i * 30 + 11], raw[i * 30 + 10]) for i in range(8)]

    def picture(self, rows, word, screen: int, patch: dict, water: list, counter: int) -> list:
        """(x, y) of the pixels that differ from the background with `patch`, the hero and the water sprites `water` [(entity, flags, x, y, phase, d2)] drawn at
        `counter`, outside the hero's box."""
        import behind
        import enemy_data as ed
        import enemy_model as em
        import faxanadu_maps as fm
        import faxanadu_sprites as fs
        import st_convert as sc

        area = fm.area(self.rom, 1)
        pal = area.palette_index
        plan = sc.plan_for_set(self.rom, pal)
        palettes = sc.sprite_palettes(self.rom, pal)
        expected = sc.expected_screen(self.rom, 1, screen, word("camera"), state=dict(hp=80, mp=80, experience=0, gold=0, seconds=0),
                                      hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))), patch=patch)
        opaque = behind.opaque_screen(self.rom, area, screen)
        for ent, flags, x, y, phase, d2 in water:
            if not em.is_drawn(ent, phase, counter, d2, flags):
                continue
            mask = em.flip_mask(flags, ent) if ent != 0x52 and phase == 1 else 0
            app = fs.appearance(self.rom, ed.entity(self.rom, ent)["appearance"] + em.appearance_offset(ent, phase, counter, d2), "TILEINFO_ENTITY_ADDRS")
            layer = fs.sprite_layer(fs.place(app, x, y, mask), fs.entity_tiles(self.rom, ent), palettes)
            layer = behind.drop_behind(layer, x, behind.halves(self.rom, area, screen, x, y), opaque)
            for (px, line), c in layer.items():
                py = line - word("camera")
                if sc.ST_TOP <= py < 200 and 0 <= px < 256:
                    expected[py][px + sc.ST_LEFT] = plan.slot[c & 0x3F]
        hx, hy = word("hero_x") + sc.ST_LEFT, word("hero_y") + 32 - word("camera")
        return [(px, py) for py in range(32, 200) for px in range(320) if rows[py][px] != expected[py][px] and not (hx - 24 <= px < hx + 40 and hy - 8 <= py < hy + 40)]

    def assert_shown(self, shots, k, screen, patch, label):
        """The screen on show at capture k is the picture of the state at capture k or k - 1 (a capture falls between a frame's update and its show)."""
        bad = []
        for j in (k, k - 1):
            rows, word = shots[k][0], shots[j][1]
            water = [(e, f, x, y, p, d2) for e, f, x, y, p, d2, _ in self.slots(word) if e in WATER]
            for c in (word("en_counter"), word("en_counter") - 1):
                bad.append(self.picture(rows, shots[k][1] if j == k else word, screen, patch, water, c & 255))
        self.assertTrue(any(not b for b in bad), f"{label}: {[len(b) for b in bad]} pixels differ, e.g. {bad[0][:6]}")

    def test_a_spring_rises_when_its_quest_is_done_and_then_flows(self) -> None:
        pokes = [(T0 + 40, "mem:inv+30", 1)]          # (Quests: the Spring of Trunk; what the man's script does with the Elixir)
        caps = [T0 + c for c in (30, 41, 43, 50, 51, 70, 71, 140)]
        shots = self.run_multi(TRUNK + ["SCREEN=61", "HERO=96,144,0,255,0,0,0"], pokes, caps, "shots_spring")
        state = {c - T0: next(s for s in self.slots(w) if s[0] == 0x61) for c, (_, w) in zip(caps, shots)}
        self.assertEqual(state[30][4], 0)                       # dry: step 0, hidden
        self.assertTrue(state[30][1] & 0x10)
        self.assertEqual((state[30][2], state[30][3]), (184, 16))       # (x + 8: its script's first op)
        self.assertEqual(state[43][4], 1)                       # rising
        self.assertEqual(state[70][4], 2)                       # flowing after 16 updates
        self.assertEqual((state[70][5], state[70][6]), (4, 16))
        self.assertFalse(state[70][1] & 0x10)
        for k, c in enumerate(caps):
            if c - T0 in (30, 51, 71, 140):
                self.assert_shown(shots, k, 61, {}, f"VBL {c}")

    def test_the_fountain_shows_when_all_three_springs_flow(self) -> None:
        pokes = [(T0 + 40, "mem:inv+30", 7)]
        caps = [T0 + c for c in (30, 31, 60, 61)]
        shots = self.run_multi(TRUNK + ["SCREEN=40", "HERO=32,144,0,255,0,0,0"], pokes, caps, "shots_fountain")
        fountain = [next(s for s in self.slots(w) if s[0] == 0x52) for _, w in shots]
        self.assertTrue(fountain[0][1] & 0x10)
        self.assertFalse(fountain[2][1] & 0x10)
        for k in (1, 3):
            self.assert_shown(shots, k, 40, {}, f"capture {k}")

    def screen_ids(self, word, index: int) -> bytes:
        pkg = int.from_bytes(word.raw("pkg_ptr", 8)[4:8], "big")
        return word.mem(pkg + 208 * index, 208)

    def test_pushing_the_stone_opens_the_way_to_mascon(self) -> None:
        P = T0 + 40                                                   # right held from VBL P: the count is 96 at P + 95, the stone moves
        pokes = [(T0 + 10, "mem:inv+29", 0x40), (T0 + 10, "mem:inv+30", 7), (P, "joy", RIGHT)]
        caps = [P + 90, P + 97, P + 110, P + 125, P + 132, P + 140, P + 156, P + 175, P + 176]
        shots = self.run_multi(TRUNK + ["SCREEN=40", "HERO=80,80,0,255,0,0,1"], pokes, caps, "shots_push")
        index = shots[0][1]("cur_screen")
        ids = [self.screen_ids(w, index) for _, w in shots]
        stone = lambda b: [b[p] for p in (0x56, 0x57, 0x66, 0x67)]
        ladder = lambda b: [b[0x22 + 16 * k] for k in range(7)]
        self.assertEqual(stone(ids[0]), [0x88, 0x42, 0x88, 0x42])     # still pushing
        self.assertEqual(stone(ids[1]), [0x42, 0x88, 0x42, 0x88])     # moved one block right
        self.assertEqual(stone(ids[3]), [0x42, 0x88, 0x42, 0x88])     # 30 frames there
        self.assertEqual(stone(ids[4]), [0x42] * 4)                   # gone
        self.assertEqual(ladder(ids[4])[1:], ladder(ids[0])[1:])      # the ladder not yet
        self.assertEqual(ladder(ids[7]), [0x20] * 7)                  # the ladder is down
        quests = shots[7][1].raw("inv", 32)[30]
        self.assertEqual(quests, 0x27)
        down = {0x56: 0x42, 0x66: 0x42, 0x57: 0x42, 0x67: 0x42, **{0x22 + 16 * k: 0x20 for k in range(7)}}
        self.assert_shown(shots, 8, 40, down, "the way open")

    def test_entering_with_the_way_open_drops_the_ladder_again_and_leaving_puts_the_screen_back(self) -> None:
        # the way open: the next tick after a screen is entered (mascon_new) takes the stone away and drops the ladder; then right to screen 39 and back
        pokes = [(T0 + v, what, x) for v, what, x in ((10, "mem:inv+30", 0x27), (11, "w:mascon_new", 1), (60, "w:hero_x", 236), (61, "w:hero_y", 144), (62, "joy", RIGHT), (200, "joy", LEFT))]
        caps = [T0 + c for c in (11, 14, 40, 55, 190, 380, 420)]
        shots = self.run_multi(TRUNK + ["SCREEN=40", "HERO=32,144,0,255,0,0,1"], pokes, caps, "shots_mascon")
        index = shots[0][1]("cur_screen")
        ids = lambda k: self.screen_ids(shots[k][1], index)
        ladder = lambda b: [b[0x22 + 16 * k] for k in range(7)]
        self.assertEqual(ids(0)[0x56], 0x88)
        self.assertEqual(ids(1)[0x56], 0x42)                          # at once
        self.assertEqual(ladder(ids(3)), [0x20] * 7)
        self.assertNotEqual(shots[4][1]("cur_screen"), index)         # on screen 39
        back = [k for k in (5, 6) if shots[k][1]("cur_screen") == index]
        self.assertTrue(back, "back on screen 40")
        self.assertEqual(ladder(ids(6)), [0x20] * 7)                  # the ladder again
        self.assertEqual(shots[6][1].raw("mt_count", 2), bytes([0, 6]))       # the six changes noted: drawn again, the screen is whole first
