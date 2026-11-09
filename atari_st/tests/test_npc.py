"""The Python model of the town people (tools/npc_model.py) against the game in jsnes (needs node, the harness's packages and your ROM): the hero stands (or sweeps
across the screen) in a street or a building and every frame the state of the people's sprite slots and the sprites on show are compared. Two kinds the game never
places ($35, $36) are put into a street by hand. The scripts that go into the program (`iscripts.walk_file`) are the ROM's own bytes, cut out the way the enemies' are."""
import copy
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
FRAMES = 640
REGIONS = {0: 0, 1: 1, 2: 2, 3: 0, 6: 4}          # the region the game's temple table takes an area by (`tools/refnes/buildingprobe.mjs`)

# (area, screen, the hero's x) of the streets, and the ids of the buildings: every kind of person is in one of them ($35 and $36 are not placed anywhere in the game)
STREETS = ((0, 1, 64), (0, 2, 64), (0, 3, 64), (0, 6, 64), (0, 7, 64), (3, 1, 64), (3, 10, 64), (3, 2, 64), (3, 8, 64), (3, 0, 64), (1, 61, 64), (1, 63, 64))
BUILDINGS = (0, 1, 2, 3, 4, 5, 6, 7, 40, 12, 22, 49, 50, 13, 17)
INJECTED = ((0x35, 100, 144), (0x36, 150, 144))      # put into slots 6 and 5 of Eolis screen 1
FIELDS = (("ent", "Entities"), ("x", "x"), ("xf", "xf"), ("y", "y"), ("yf", "yf"), ("flags", "Flags"), ("phase", "Phases"), ("beh", "Behaviors"), ("arg1", "BehaviorArg1"),
          ("d2", "BehaviorData2"), ("d3", "BehaviorData3"), ("internal", "InternalBehaviorStates"), ("bxf", "BehaviorState_XFrac"), ("bxfull", "BehaviorState_XFull"),
          ("byf", "BehaviorState_YFrac"), ("byfull", "BehaviorState_YFull"))
PEOPLE = range(0x34, 0x46)


def sweep(lo: int = 24, hi: int = 230, still: int = 60, frames: int = FRAMES) -> list[list[int]]:
    """The hero's x written before each frame: still for a while, then a triangle wave between lo and hi, one pixel a frame (it crosses every person and the King's 64 and 72)."""
    out, x, d = [[0, lo + 8]], lo + 8, 1
    for f in range(still, frames):
        x += d
        if x >= hi or x <= lo:
            d = -d
        out.append([f, x])
    return out


def building_doors(rom) -> dict[int, list[tuple[int, int, int, int, int]]]:
    """For each building id (`Area_DestScreen`): the doors of the ROM that lead there, as (area, region, screen, x, y)."""
    import faxanadu_maps as fm

    out: dict[int, list[tuple[int, int, int, int, int]]] = {}
    for a in (0, 1, 2, 3, 6):
        area = fm.area(rom, a)
        for door in fm.doors(rom, area):
            if (a == 3 and door.destination >= 0xFE) or (a != 3 and not 0x20 <= door.destination < 0xFE):
                continue
            record = fm.door_destination(rom, area, door)
            out.setdefault(record[0], []).append((a, REGIONS[a], door.screen, (door.block & 15) * 16, (door.block >> 4) * 16))
    return out


def people_only(eng) -> None:
    """The model runs the people of a screen only (a screen of Trunk has items too): every other slot is empty."""
    for s in eng.sprites:
        if s.ent not in PEOPLE:
            s.ent = 255


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class NpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import enemy_data as ed
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)
        cls.tmp = tempfile.TemporaryDirectory()
        doors = building_doors(cls.rom)
        cls.runs = {}                                  # (area, screen) -> the records; the buildings are area 4 and their id
        for area, screen, x in STREETS:
            cls.runs[(area, screen)] = cls.record(dict(area=area, region=REGIONS[area], screen=screen, x=x, door=None), f"{area}_{screen}")
        inject = [dict(slot=6 - i, entity=e, x=x, y=y, hbox=ed.entity(cls.rom, e)["hitbox"], script=cls.rom.word("SPRITE_BSCRIPTS", e)) for i, (e, x, y) in enumerate(INJECTED)]
        cls.runs[(0, 1000)] = cls.record(dict(area=0, region=0, screen=1, x=64, door=None, inject=inject), "injected")
        for ident in BUILDINGS:
            for a, region, screen, x, y in doors[ident]:                    # (a door the hero cannot be put in front of is skipped for the next of its building)
                try:
                    cls.runs[(4, ident)] = cls.record(dict(area=a, region=region, screen=screen, x=0, door=dict(x=x, y=y)), f"4_{ident}")
                    break
                except subprocess.CalledProcessError:
                    continue
            else:
                raise AssertionError(f"no door leads into building {ident}")

    @classmethod
    def record(cls, scene: dict, name: str) -> list:
        """The game's run for a scene. Each takes several seconds and every test of the class needs all of them, so they are kept in a folder (`NPC_CACHE`, else the system's temporary
        folder) under a name that has a hash of the spec, the probe, the harness and the ROM in it."""
        import hashlib

        spec = dict(scene, frames=FRAMES, hero=sweep())
        refnes = ROOT / "tools" / "refnes"
        digest = hashlib.sha1(json.dumps(spec, sort_keys=True).encode() + (refnes / "npcprobe.mjs").read_bytes() + (refnes / "faxanadu.mjs").read_bytes() + ROM.read_bytes()).hexdigest()[:16]
        cached = Path(os.environ.get("NPC_CACHE") or Path(tempfile.gettempdir()) / "faxanadu_npc_cache") / f"{name}.{digest}.json"
        if cached.exists():
            return json.loads(cached.read_text())
        spec_file, out = Path(cls.tmp.name) / f"{name}.spec.json", Path(cls.tmp.name) / f"{name}.json"
        spec_file.write_text(json.dumps(spec))
        subprocess.run(["node", "npcprobe.mjs", str(spec_file), str(out)], cwd=refnes, check=True, capture_output=True, env=os.environ)
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, cached.with_suffix(f".{os.getpid()}.tmp"))
        os.replace(cached.with_suffix(f".{os.getpid()}.tmp"), cached)
        return json.loads(out.read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def engine(self, key, rec):
        """The model with the people of the screen the hero is on, started as the game loads them, the hero at his x before the recording began."""
        import npc_model as nm

        return nm.engine(self.rom, rec[0]["area"], rec[0]["screen"], bytes(rec[0]["blocks"]), rec[0]["start_x"], rec[0]["py"])

    def replay(self, key, rec, start: int = 0):
        """The model started from the state of record `start`, then every record after it (the hero where the game has him; the game stops its sprites while a screen scrolls)."""
        eng = self.engine(key, rec)
        eng.counter = rec[start]["counter"]
        for i, s in enumerate(rec[start]["slots"]):
            sp = eng.sprites[i]
            for mine, theirs in FIELDS:
                setattr(sp, mine, s[theirs])
            sp.hbox = s["HitBoxTypes"]
            sp.script = s["BehaviorAddrs_L"] | s["BehaviorAddrs_U"] << 8
        people_only(eng)
        for n in range(start + 1, len(rec)):
            eng.hero_x, eng.hero_y = rec[n]["px"], rec[n]["py"]
            if rec[n]["counter"] != rec[n - 1]["counter"]:
                eng.update_all()
            yield n, eng

    def test_a_person_slot_is_the_enemies_slot_and_the_fields_after_it(self) -> None:
        """src/town.s NPC_REC is a number (the assembler does not take a forward name in `.space`): it is the enemies' slot (enemy.s E_BYTES) and ten bytes of the person's own,
        which lie after the enemies' fields and inside the record."""
        import re

        src = Path(__file__).resolve().parents[1] / "src"
        enemy = {m.group(1): int(m.group(2)) for m in re.finditer(r"\.equ (E_[A-Z0-9_]+),\s*(\d+)", (src / "enemy.s").read_text())}
        town = (src / "town.s").read_text()
        rec = int(re.search(r"\.equ NPC_REC,\s*(\d+)", town).group(1))
        self.assertEqual(rec, enemy["E_BYTES"] + 10)
        own = {m.group(1): int(m.group(2)) for m in re.finditer(r"\.equ (N_[A-Z]+),\s*NPC_REC-(\d+)", town)}
        self.assertEqual(sorted(own), ["N_POSE", "N_RAM", "N_SCRIPT"])
        spans = sorted((rec - back, rec - back + (4 if name == "N_RAM" else 1), name) for name, back in own.items())
        self.assertGreaterEqual(spans[0][0], enemy["E_BYTES"])
        self.assertLessEqual(spans[-1][1], rec)
        for (a, b, _), (c, d, _) in zip(spans, spans[1:]):
            self.assertLessEqual(b, c, "the fields do not overlap")
        self.assertEqual(rec % 2, 0)

    def test_the_model_runs_the_people_as_the_game_does(self) -> None:
        checked, kinds = 0, set()
        for key, rec in sorted(self.runs.items()):
            with self.subTest(area=key[0], screen=key[1]):
                if key[0] == 4:
                    self.assertEqual((rec[0]["area"], rec[0]["screen"]), key, "the hero is in the building the scene says")
                slots = [i for i, s in enumerate(rec[0]["slots"]) if s["Entities"] in PEOPLE]
                self.assertTrue(slots, "someone is there")
                kinds |= {rec[0]["slots"][i]["Entities"] for i in slots}
                for n, eng in self.replay(key, rec):
                    self.assertEqual((rec[n]["area"], rec[n]["screen"]), (rec[0]["area"], rec[0]["screen"]), f"{key} frame {n}: the screen changed under the hero")
                    for i in slots:
                        got = tuple(getattr(eng.sprites[i], mine) for mine, _ in FIELDS)
                        want = tuple(rec[n]["slots"][i][theirs] for _, theirs in FIELDS)
                        self.assertEqual(got, want, f"{key} frame {n} slot {i}")
                    checked += 1
        self.assertEqual(kinds, set(PEOPLE), "every kind of person was run")
        self.assertGreater(checked, 5000)

    def test_a_person_loaded_as_the_model_loads_him_is_where_the_game_has_him(self) -> None:
        """The state the game gives a person when the screen is loaded (behaviour ready, phase 0, the script's start) is, after some number of updates (none if the recording began at once;
        the recording began up to 400 frames after the load), the state of the first record: where he is, which way he faces, his phase, his behaviour and its count. (The game leaves the
        walk speed, the last flag bit and the like in the slot as the sprite of the screen before had them; nothing reads them before the script sets them.)"""
        keep = [i for i, (mine, _) in enumerate(FIELDS) if mine in ("ent", "x", "y", "phase", "beh", "arg1")]

        def state(sp):
            return tuple(getattr(sp, FIELDS[i][0]) for i in keep) + (sp.flags & 0x40,)

        for key, rec in sorted(self.runs.items()):
            if key == (0, 1000):
                continue
            with self.subTest(area=key[0], screen=key[1]):
                eng = self.engine(key, rec)
                want = {i: tuple(s[FIELDS[j][1]] for j in keep) + (s["Flags"] & 0x40,) for i, s in enumerate(rec[0]["slots"]) if s["Entities"] in PEOPLE}
                self.assertTrue(want)
                found = None
                for k in range(0, 401):
                    trial = copy.deepcopy(eng)
                    trial.hero_y = rec[0]["py"]
                    trial.counter = (rec[0]["counter"] - k) & 255            # (it is one more at every update)
                    for j in range(k):
                        trial.hero_x = rec[0]["start_x"] + (rec[0]["px"] - rec[0]["start_x"]) * j // k      # (the hero walked from where he began to where the recording found him)
                        trial.update_all()
                    trial.hero_x = rec[0]["px"]
                    if all(state(trial.sprites[i]) == w for i, w in want.items()):
                        found = k
                        break
                self.assertIsNotNone(found, f"{key}: no number of updates leads to the first record")

    def test_the_sprites_on_show_are_the_pictures_the_model_picks(self) -> None:
        import faxanadu_sprites as fs
        import npc_model as nm

        checked = 0
        for key, rec in sorted(self.runs.items()):
            if key == (0, 1000) or key[0] == 1:                       # (the tiles of a kind that is not placed are not loaded; a screen of Trunk has items on show too)
                continue
            with self.subTest(area=key[0], screen=key[1]):
                for n in range(1, len(rec) - 1):
                    if rec[n]["counter"] == rec[n - 1]["counter"] or rec[n + 1]["counter"] == rec[n]["counter"]:
                        continue
                    want = []
                    for s in rec[n]["slots"]:
                        if s["Entities"] not in PEOPLE:
                            continue
                        frame, mirrored = nm.appearance(s["Entities"], s["Phases"], s["Flags"], rec[n]["counter"])
                        app = fs.appearance(self.rom, self.rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", s["Entities"]) + frame, "TILEINFO_ENTITY_ADDRS")
                        want += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(app, s["x"], s["y"], 0x40 if mirrored else 0, s["PPUOffsets"]) if sp.y < 240]
                    got = [(y, t, a & ~0x20, x) for y, t, a, x in rec[n + 1]["oam"]]
                    self.assertEqual(sorted(want), sorted(got), f"{key} frame {n}")
                    checked += 1
        self.assertGreater(checked, 3000)


if __name__ == "__main__":
    unittest.main()
