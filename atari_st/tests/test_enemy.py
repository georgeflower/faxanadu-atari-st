"""The Python enemy model against golden runs recorded from the ROM in jsnes (needs node, the harness's packages and your ROM): the hero stands
still on a screen of Eolis and every frame the 8 sprite slots' state is compared."""
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
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
SCENES = ((0, 4, "left", 400), (0, 5, "left", 400), (0, 8, "right", 400), (1, 16, "right", 400), (1, 6, "right", 400), (1, 19, "right", 400), (1, 22, "right", 400), (1, 23, "right", 400), (1, 29, "right", 400), (1, 45, "right", 400), (1, 25, "right", 400),
          (2, 23, "right", 400), (2, 39, "right", 400), (2, 60, "right", 400), (5, 25, "right", 400), (5, 2, "right", 400), (5, 31, "right", 400),
          (2, 4, "right", 400), (2, 14, "right", 400), (2, 19, "right", 400), (5, 21, "right", 400), (5, 35, "right", 400), (5, 36, "right", 400),
          (2, 1, "right", 400), (2, 3, "right", 400), (2, 25, "right", 400), (2, 29, "right", 400), (2, 32, "right", 400), (2, 37, "right", 400),
          (2, 45, "right", 400),
          (2, 33, "right", 400), (2, 38, "right", 400), (2, 30, "right", 400), (2, 31, "right", 400), (2, 42, "right", 400), (5, 5, "right", 400), (5, 32, "right", 400), (5, 34, "right", 400), (5, 3, "right", 400), (6, 13, "right", 400), (6, 10, "right", 400), (6, 11, "right", 400), (7, 15, "right", 400), (7, 16, "right", 400), (2, 80, "right", 400), (2, 81, "right", 400), (2, 82, "right", 400),
          (6, 30, "right", 400), (2, 59, "right", 400), (6, 23, "right", 400), (6, 25, "right", 400),
          (1, 58, "right", 400), (6, 26, "right", 400), (7, 17, "right", 400),
          (2, 51, "right", 400), (2, 63, "right", 400), (7, 4, "right", 400), (6, 22, "right", 400))
FIGHT_HEROX = {(2, 51): 16, (6, 22): 16}      # where the hero starts a fight when 208 is a pit or a wall
HEROX = {(1, 23): 80, (1, 29): 16, (2, 23): 144, (2, 39): 80, (2, 60): 144, (5, 25): 144, (5, 2): 144, (5, 31): 144, (5, 21): 144, (5, 35): 144, (5, 36): 144, (2, 1): 16, (2, 3): 144, (2, 25): 144, (2, 33): 144, (2, 38): 16, (2, 30): 144, (2, 31): 144, (2, 42): 144, (5, 5): 240, (5, 32): 16, (5, 34): 16, (5, 3): 144, (6, 13): 144, (6, 10): 144, (6, 11): 144, (7, 15): 208, (7, 16): 112, (2, 80): 16, (2, 81): 16, (2, 82): 16, (6, 30): 144, (2, 59): 144, (6, 23): 16, (6, 25): 240, (1, 58): 16, (6, 26): 16, (7, 17): 208, (2, 51): 16, (2, 63): 16, (7, 4): 16, (6, 22): 16}       # where the hero stands when the default (64) has him fall off the screen or walk into a wall
FIELDS = (("ent", "Entities"), ("x", "x"), ("xf", "xf"), ("y", "y"), ("yf", "yf"), ("flags", "Flags"), ("phase", "Phases"), ("beh", "Behaviors"), ("arg1", "BehaviorArg1"),
          ("d2", "BehaviorData2"), ("d3", "BehaviorData3"), ("internal", "InternalBehaviorStates"), ("bxf", "BehaviorState_XFrac"), ("bxfull", "BehaviorState_XFull"))


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class EnemyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)
        cls.props_by_area = {a: fm.block_properties(cls.rom, fm.area(cls.rom, a)) for a in (0, 1, 2, 5, 6, 7)}
        cls.bank14 = cls.rom.prg(14)
        o = cls.rom.label("Sprites_UpdateAll").offset - fr.HEADER - 14 * fr.BANK
        cls.random_table = cls.bank14[o:o + 256]
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = {}
        # (area, screen, direction): Eolis' screens are reached walking from its gate, those of the other areas through a temple (`AREA`)
        for area, screen, direction, frames in SCENES:
            out = Path(cls.tmp.name) / f"{area}_{screen}.json"
            subprocess.run(["node", "enemyprobe.mjs", str(screen), str(frames), str(out), direction], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True,
                           env={**os.environ, "AREA": str(area), "HEROX": str(HEROX.get((area, screen), 64))})
            cls.runs[(area, screen)] = json.loads(out.read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def packed(self, entities) -> tuple[bytes, dict]:
        """The scripts of these entities as a package holds them (`enemy_data.script_chunk`), the chunks put at $8000 and up so that the model can
        run them as they are: (the bytes, entity -> {the old address of an op: its new one})."""
        import enemy_data as ed

        blob, where = bytearray(), {}
        entities = set(entities)
        for e in sorted(entities | {ed.SPAWNED[e] for e in entities if e in ed.SPAWNED}):
            chunk, _, mapping = ed.script_chunk(self.rom, self.rom.word("SPRITE_BSCRIPTS", e), 0x8000 + len(blob))
            where[e] = {old: 0x8000 + len(blob) + new for old, new in mapping.items()}
            blob += chunk
        return bytes(blob), where

    def replay(self, rec: list, packed: bool = False, area: int = 0):
        import enemy_data as ed
        import enemy_model as em

        blob, where = self.packed(s["Entities"] for s in rec[0]["slots"] if s["Entities"] != 255) if packed else (self.bank14, {})
        eng = em.Engine(blob, self.random_table, bytes(rec[0]["blocks"]), self.props_by_area[area])
        # (a screen the hero has just entered may stand still for a few records, the counter already running: start at the first record that has moved)
        start = next((n for n in range(1, 12) if rec[n]["slots"] != rec[0]["slots"]), 0)
        eng.rnd, eng.counter = rec[start]["rnd"], rec[start]["counter"]
        for ent in ed.EXTRAS + ed.ENEMIES + tuple(ed.SPAWNED.values()):
            eng.kinds[ent] = dict(ed.kind_info(self.rom, ent))
            if packed and ent in where:
                eng.kinds[ent]["script"] = where[ent][eng.kinds[ent]["script"]]
        for i, s in enumerate(rec[start]["slots"]):
            sp = eng.sprites[i]
            for mine, theirs in FIELDS:
                setattr(sp, mine, s[theirs])
            sp.hbox = s["HitBoxTypes"]
            sp.script = s["BehaviorAddrs_L"] | s["BehaviorAddrs_U"] << 8
            if packed and sp.ent != 255:
                sp.script = where[sp.ent][sp.script]
        for n in range(start + 1, len(rec)):
            eng.hero_x, eng.hero_y, eng.mask = rec[n]["px"], rec[n]["py"], rec[n]["mask"]
            eng.hero.flags = rec[n]["pf"]
            if rec[n]["counter"] != rec[n - 1]["counter"]:         # the game stops the sprites while the screen scrolls
                eng.update_all()
            yield n, eng

    def check(self, screen: int, packed: bool = False, area: int = 0) -> None:
        rec = self.runs[(area, screen)]
        placed = lambda slots: [s["Entities"] if s["Entities"] not in (0x51, 0x54, 0x0A) else 255 for s in slots]       # (a fireball or a bolt comes and goes)
        first = placed(rec[0]["slots"])
        for n, eng in self.replay(rec, packed, area):
            if placed(rec[n]["slots"]) != first or abs(rec[n]["py"] - rec[n - 1]["py"]) > 100:     # the hero went on (the screen scrolled, the sprites were loaded anew)
                self.assertGreater(n, 100, f"screen {screen}: the run ended early")
                return
            for i, s in enumerate(rec[n]["slots"]):
                if eng.sprites[i].ent == 0x0A and s["Entities"] == 255:      # (a bolt is gone when it has hurt the hero; this replay has no touch)
                    eng.sprites[i].ent = 255
                got = tuple(getattr(eng.sprites[i], mine) for mine, _ in FIELDS)
                want = tuple(s[theirs] for _, theirs in FIELDS)
                self.assertEqual(got, want, f"screen {screen} frame {n} slot {i}")
            self.assertEqual(eng.rnd, rec[n]["rnd"], f"screen {screen} frame {n}: random offset")

    def fight(self, screen: int, weapon: int, armour: int, area: int = 0, boss: bool = False):
        """The golden fight (`combatprobe.mjs`: the hero walks up to the enemies and cuts them down, picks up what they drop) replayed in the model: the
        hero is what the ROM had when it entered `Sprites_UpdateAll`; the model runs the sprites and its hero and the slots are compared with the ROM's after."""
        import enemy_data as ed
        import enemy_model as em

        out = Path(self.tmp.name) / f"fight{area}_{screen}_{int(boss)}.json"
        if not out.exists():
            subprocess.run(["node", "combatprobe.mjs", str(screen), "700", str(out), str(weapon), str(armour)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True,
                           env={**os.environ, "AREA": str(area), "HEROX": str(FIGHT_HEROX.get((area, screen), 208)), **({"HEAL": "1", "JUMP": "1", "REACH": "24"} if boss else {})})    # (on screen 16 of area 1 a wall cuts off the left half)
        run = json.loads(out.read_text())
        frames = run["frames"]
        eng = em.Engine(self.bank14, self.random_table, bytes(run["start"]["blocks"]), self.props_by_area[area])
        for ent in ed.EXTRAS + ed.ENEMIES + tuple(ed.SPAWNED.values()):
            eng.kinds[ent] = ed.kind_info(self.rom, ent)
        eng.combat = ed.tables(self.rom)
        first = next(n for n, f in enumerate(frames) if f["preSlots"])          # (a screen the hero has just entered may stand still for a few frames)
        for i, s in enumerate(frames[first]["preSlots"]):
            sp = eng.sprites[i]
            for mine, theirs in FIELDS:
                setattr(sp, mine, s[theirs])
            sp.hbox, sp.hit, sp.hp, sp.value = s["HitBoxTypes"], s["HitCounter"], s["HP"], s["Values"]
            sp.script = s["BehaviorAddrs_L"] | s["BehaviorAddrs_U"] << 8
        names = {"x": "x", "y": "y", "flags": "flags", "atk": "atk", "wx": "wx", "wy": "wy", "rx": "rx", "ry": "ry", "inv": "inv", "status": "status",
                 "hp_u": "hpU", "hp_l": "hpL", "weapon": "weapon"}
        kills = pickups = 0
        for n, rec in enumerate(frames):
            if rec["scroll"] != 255:
                self.assertGreater(n, 300, f"screen {screen}: the fight ended early")
                break
            if n < first or (n and rec["counter"] == frames[n - 1]["counter"] and n > first):        # (the game did not run the sprites in this frame)
                continue
            h = eng.hero
            for mine, theirs in names.items():
                setattr(h, mine, rec["pre"][theirs])
            h.armour, h.exp, h.gold = run["start"]["armour"], frames[n - 1]["exp"] if n else 0, frames[n - 1]["gold"] if n else 0
            h.special, h.glove, h.ointment = run["start"]["special"], run["start"]["glove"], run["start"]["ointment"]
            h.events = []
            eng.rnd, eng.mask = rec["rnd"] if False else eng.rnd, rec["mask"]
            if n == first:
                eng.rnd, eng.counter = rec["rnd"], (rec["counter"] - 1) & 255
            eng.update_frame()
            m = n
            while m + 1 < len(frames) and frames[m + 1]["counter"] == rec["counter"] and frames[m + 1]["scroll"] == 255:        # (a long update runs into the next frame: its end is the last record with this count)
                m += 1
            rec = {**rec, **{k: frames[m][k] for k in ("slots", "hero", "exp", "gold")}}
            for i, s in enumerate(rec["slots"]):
                sp = eng.sprites[i]
                got = tuple(getattr(sp, mine) for mine, _ in FIELDS) + (sp.hit, sp.hp, sp.value)
                want = tuple(s[theirs] for _, theirs in FIELDS) + (s["HitCounter"], s["HP"], s["Values"])
                if sp.ent == 255 and s["Entities"] == 255:
                    got, want = got[:1], want[:1]                  # an empty slot keeps stale values nobody looks at
                self.assertEqual(got, want, f"screen {screen} frame {n} slot {i}")
            end = rec["hero"]
            self.assertEqual((h.hp_u, h.hp_l, h.inv, h.exp, h.gold), (end["hpU"], end["hpL"], end["inv"], rec["exp"], rec["gold"]), f"screen {screen} frame {n}: the hero")
            kills += 3 in h.events
            pickups += (9 in h.events) + (0x1B in h.events)
        return kills, pickups

    def test_the_sword_kills_and_the_drops_are_picked_up_as_in_the_rom(self) -> None:
        for area, screen, weapon, armour in ((0, 4, 1, 0), (0, 8, 2, 1), (0, 5, 3, 2), (1, 16, 2, 1), (1, 7, 2, 1), (1, 31, 2, 1), (1, 22, 2, 1), (1, 25, 2, 1), (1, 28, 2, 1), (2, 39, 2, 1), (5, 31, 2, 1), (2, 19, 2, 1), (5, 35, 2, 1), (2, 45, 2, 1),
                                              (2, 33, 2, 1), (2, 30, 2, 1), (6, 13, 2, 1), (6, 11, 2, 1), (6, 10, 2, 1)):
            with self.subTest(area=area, screen=screen):
                kills, pickups = self.fight(screen, weapon, armour, area)
                self.assertGreaterEqual(kills, 1)

    def test_rokusutahn_is_cut_down_and_dies_as_a_boss_in_the_rom(self) -> None:
        for area, screen in ((6, 30), (2, 59)):          # (hit from the air, the hero cured now and then: the slots, his power, experience and gold are the ROM's)
            with self.subTest(area=area, screen=screen):
                kills, pickups = self.fight(screen, 3, 2, area, boss=True)
                self.assertGreaterEqual(kills, 1)

    def test_ripasheiku_and_king_grieve_fly_and_shoot_as_in_the_rom_in_a_fight(self) -> None:
        for area, screen in ((2, 51), (6, 22)):          # (the bolts hurt the hero, who is cured now and then: the slots, his power, experience and gold are the ROM's)
            with self.subTest(area=area, screen=screen):
                self.fight(screen, 3, 2, area, boss=True)

    def test_nash_tamazutsu_and_ishiisu_are_as_in_the_rom_when_the_sword_cuts_at_nothing(self) -> None:
        for area, screen in ((2, 42), (5, 3), (2, 80), (2, 81)):           # (they hide and show; the hero cuts at nothing, the slots and his power are the ROM's)
            with self.subTest(area=area, screen=screen):
                self.fight(screen, 2, 1, area)

    def test_zozura_walks_as_in_the_rom(self) -> None:
        self.check(4)
        self.check(5)

    def test_monodron_hops_as_in_the_rom(self) -> None:
        self.check(8)

    def test_the_snowman_walks_and_hops_as_in_the_rom(self) -> None:
        self.check(16, area=1)

    def test_the_zombie_walks_toward_the_hero_as_in_the_rom(self) -> None:
        self.check(6, area=1)

    def test_ikeda_moves_as_in_the_rom(self) -> None:
        self.check(19, area=1)

    def test_the_myconid_moves_as_in_the_rom(self) -> None:
        self.check(22, area=1)

    def test_charron_walks_and_casts_fireballs_as_in_the_rom(self) -> None:
        self.check(25, area=1)

    def test_the_yuinaru_waves_as_in_the_rom(self) -> None:
        self.check(23, area=1)
        self.check(29, area=1)

    def test_the_hornet_buzzes_as_in_the_rom(self) -> None:
        self.check(45, area=1)

    def test_the_kinds_of_the_other_areas_move_as_in_the_rom(self) -> None:
        for area, screen in ((2, 23), (2, 39), (2, 60), (5, 25), (5, 2), (5, 31), (2, 4), (2, 14), (2, 19), (5, 21), (5, 35), (5, 36),
                             (2, 1), (2, 3), (2, 25), (2, 29), (2, 32), (2, 37), (2, 45),
                             (2, 33), (2, 38), (2, 30), (2, 31), (2, 42), (5, 5), (5, 32), (5, 34), (5, 3), (6, 13), (6, 10), (6, 11), (7, 15), (7, 16), (2, 80), (2, 81), (2, 82), (6, 30), (2, 59), (6, 23), (6, 25), (1, 58), (6, 26), (7, 17)):
            with self.subTest(area=area, screen=screen):
                self.check(screen, area=area)

    def test_the_pictures_are_the_roms_sprites_one_frame_later(self) -> None:
        import enemy_data as ed
        import enemy_model as em
        import faxanadu_sprites as fs

        checked = 0
        for screen in self.runs:
            rec = self.runs[screen]
            first = [s["Entities"] for s in rec[0]["slots"]]
            for n in range(1, len(rec) - 1):
                if [s["Entities"] for s in rec[n]["slots"]] != first or rec[n]["counter"] == rec[n - 1]["counter"] or rec[n + 1]["counter"] == rec[n]["counter"]:
                    break
                want = []
                masks = em.flip_masks([(s["Entities"], s["Flags"], s["HitCounter"]) for s in rec[n]["slots"]], rec[n]["counter"], rec[n - 1]["pf"])      # (the hero is drawn before the sprites update, with the flags of the frame before)
                for i, s in enumerate(rec[n]["slots"]):
                    if s["Entities"] == 255 or not em.is_drawn(s["Entities"], s["Phases"], rec[n]["counter"], s["BehaviorData2"]):
                        continue
                    app = fs.appearance(self.rom, ed.entity(self.rom, s["Entities"])["appearance"] + em.appearance_offset(s["Entities"], s["Phases"], rec[n]["counter"], s["BehaviorData2"]),
                                        "TILEINFO_ENTITY_ADDRS")
                    want += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(app, s["x"], s["y"], masks[i], s["PPUOffsets"]) if sp.y < 240]    # (the NES hides a tile from line 240)
                got = [(y, t, a & ~0x20, x) for y, t, a, x in rec[n + 1]["oam"]]       # (a sprite goes behind blocks of some kinds: not modelled yet)
                self.assertEqual(sorted(want), sorted(got), f"screen {screen} frame {n}")
                checked += 1
        self.assertGreater(checked, 150)

    def test_the_enemy_tiles_are_the_ones_the_game_loads(self) -> None:
        import enemy_data as ed
        import faxanadu_sprites as fs

        for screen in self.runs:
            first = self.runs[screen][10]               # (the tiles are in the PPU a few frames after the screen is)
            for s in first["slots"]:
                if s["Entities"] != 255:
                    ent = s["Entities"]
                    used = None                                    # (the tiles a kind's pictures use; the ROM does not load the whole count of some)
                    if ent in ed.KINDS:
                        used = {sp.tile for f in range(ed.KINDS[ent]) for sp in fs.place(fs.appearance(self.rom, ed.entity(self.rom, ent)["appearance"] + f, "TILEINFO_ENTITY_ADDRS"), 0, 0, 0)}
                    for n, tile in fs.entity_tiles(self.rom, ent).items():
                        if used is not None and n not in used:
                            continue
                        at = (s["PPUOffsets"] - 0x90 + n) * 16
                        self.assertEqual(tile, bytes(first["chr"][at:at + 16]), f"screen {screen} entity {s['Entities']} tile {n}")

    def test_the_scripts_cut_out_for_a_package_run_the_same(self) -> None:
        for area, screen, _, _ in SCENES:
            self.check(screen, packed=True, area=area)


if __name__ == "__main__":
    unittest.main()
