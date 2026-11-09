"""The Python model of the ROM's script interpreter (tools/iscript_model.py) against the ROM itself, run in jsnes (tools/refnes/iscriptprobe.mjs): the same script on the same
player state, and what the buttons do; the actions the ROM ran (their addresses in bank 12) and the state it left must be the model's. The model is what the 68000
interpreter is checked against (tests/test_iscript_batch.py), so this ties that test to the ROM. A run of all 151 scripts on five states and three button rules (755 jobs,
about 15 minutes) found no difference; the test takes a few of them. Without node, jsnes and the ROM only the model's own checks run."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFNES = ROOT / "tools" / "refnes"
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

# the scripts of every kind: a shop, a seller of items, a doctor, quest scripts, the marks, a guru, the Battle Suit branch, Fraternal, the last temple
SAMPLE = (0x0C, 0x1A, 0x0B, 0x2A, 0x25, 0x26, 0x27, 0x24, 0x02, 0x7B, 0x1C, 0x55, 0x74, 0x78, 0x43, 0x4B, 0x03)
PLAN = (("fresh", "A"), ("mid", "A"), ("full", "A"), ("rich", "BA"), ("elixir", "A"))


def labels(s) -> dict:
    """A model state as the ROM's variables."""
    d = {"Gold": s.gold & 255, "Gold_M": s.gold >> 8 & 255, "Gold_U": s.gold >> 16 & 255, "Player_HP_U": s.power, "Temp_AddedHPValue": s.power, "Player_MP": s.magic,
         "PlayerTitle": s.title, "NextPlayerTitle": s.next_title, "TempleSpawnPoint": s.spawn, "SpecialItems": s.special, "Quests": s.quests}
    for c, (name, n, sel) in enumerate((("WeaponInventory", "NumberOfWeapons", "SelectedWeapon"), ("ArmorInventory", "NumberOfArmors", "SelectedArmor"),
                                        ("ShieldInventory", "NumberOfShields", "SelectedShield"), ("MagicInventory", "NumberOfMagicSpells", "SelectedMagic"),
                                        ("ItemInventory", "NumberOfItems", "SelectedItem"))):
        d[name] = list(s.lists[c]) + [0] * ((8 if c == 4 else 4) - len(s.lists[c]))
        d[n] = len(s.lists[c])
        d[sel] = s.selected[c]
    return d


def state_of(after: dict) -> dict:
    """The ROM's variables after a script as a model state's key."""
    lists = [after[name][:after[n]] for name, n in (("WeaponInventory", "NumberOfWeapons"), ("ArmorInventory", "NumberOfArmors"), ("ShieldInventory", "NumberOfShields"),
                                                    ("MagicInventory", "NumberOfMagicSpells"), ("ItemInventory", "NumberOfItems"))]
    return {"gold": after["Gold"] | after["Gold_M"] << 8 | after["Gold_U"] << 16, "power": after["Player_HP_U"], "magic": after["Player_MP"], "title": after["PlayerTitle"],
            "next_title": after["NextPlayerTitle"], "spawn": after["TempleSpawnPoint"], "special": after["SpecialItems"], "quests": after["Quests"], "lists": lists,
            "selected": [after[k] for k in ("SelectedWeapon", "SelectedArmor", "SelectedShield", "SelectedMagic", "SelectedItem")]}


def ready() -> bool:
    return bool(shutil.which("node") and shutil.which("ca65") and shutil.which("ld65") and ROM.is_file() and (REFNES / "node_modules" / "jsnes").is_dir())


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr
        import iscript_model as im

        cls.im = im
        cls.script = im.Script(fr.Rom(ROM))

    def test_every_script_ends_on_every_state_and_the_whole_language_is_used(self) -> None:
        seen = set()
        for ident in range(152):
            if ident == 0x79:                                                       # (the password script: it waits for a typed password)
                continue
            for state in self.im.PRESETS.values():
                for buttons in ("A", "BA"):
                    actions, _messages, _after = self.im.run(self.script, ident, state, buttons)
                    seen |= {self.script.byte(a) for a in actions}
        self.assertTrue(seen <= set(range(0x18)) - {0x16}, "an action outside the language")
        self.assertNotIn(0x11, seen, "the model has no rule for choosing Sell yet")
        self.assertTrue({0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x12, 0x13, 0x17} <= seen, f"unused {sorted(seen)}")

    # the item scripts $80-$97 are not talked to: the pickup, use and expiry code of the ROM runs them (Player_PickUp*, Player_Use*, Game_Dec*Duration), each a message and END
    PICKUP = {0x48: 0x92, 0x49: 0x8E, 0x4A: 0x8F, 0x4B: 0x87, 0x4C: 0x91, 0x4D: 0x86, 0x4E: 0x94, 0x50: 0x88, 0x55: 0x89, 0x56: 0x8A, 0x57: 0x90, 0x58: 0x8B, 0x59: 0x8C, 0x5A: 0x8D,
              0x5B: 0x88, 0x5C: 0x89, 0x5D: 0x87, 0x5E: 0x91, 0x5F: 0x92, 0x60: 0x94}                    # the item's entity: the script its Player_PickUp routine runs
    USED = {0x80: 0xAA, 0x81: 0xAB, 0x82: 0xAC, 0x83: 0xAD, 0x84: 0xAE, 0x85: 0xAF, 0x93: 0xBD, 0x95: 0xBF, 0x96: 0xC0, 0x97: 0xC1}   # script: its message, as build_assets.py has it

    def test_the_item_scripts_say_what_the_port_says_when_an_item_is_picked_up_used_or_runs_out(self) -> None:
        import enemy_model as em

        for ident in range(0x80, 0x98):
            actions, messages, _after = self.im.run(self.script, ident, self.im.State(), "A")
            self.assertEqual([self.script.byte(a) for a in actions], [1, 0], f"script {ident:#x}: one unskippable message, then END")
            self.assertEqual(self.script.byte(self.script.pointers[ident]), 0x00, "no portrait")
        for entity, ident in self.PICKUP.items():
            _a, messages, _s = self.im.run(self.script, ident, self.im.State(), "A")
            self.assertEqual(em.Engine.ITEM_MESSAGES[entity], messages[0], f"entity {entity:#x}: the port says message {em.Engine.ITEM_MESSAGES[entity]:#x}, the ROM's script {ident:#x} {messages[0]:#x}")
        self.assertEqual(sorted(self.PICKUP), sorted(em.Engine.ITEM_MESSAGES), "every item the port says something for, and no other")
        for ident, message in self.USED.items():
            self.assertEqual(self.im.run(self.script, ident, self.im.State(), "A")[1], [message], f"script {ident:#x}")

    def test_a_shop_sells_a_potion_again_but_not_a_second_sword_or_ring(self) -> None:
        """Shop_GetPlayerHasSelectedItem: only equipment and special items count as owned."""
        im = self.im
        base = im.PRESETS["mid"].copy()
        self.assertFalse(im.owns_for_shop(base, 0x87), "a potion he carries is sold again")
        self.assertTrue(im.owns_for_shop(base, 0x80), "the Ring of Elf he has")
        base.lists[0] = [1]
        self.assertTrue(im.owns_for_shop(base, 0x01), "a weapon in the list")


@unittest.skipUnless(ready(), "needs node, npm install in tools/refnes, cc65 and the ROM")
class RomTests(unittest.TestCase):
    def test_the_model_runs_scripts_as_the_rom_does(self) -> None:
        import faxanadu_rom as fr
        import iscript_model as im

        script = im.Script(fr.Rom(ROM))
        jobs = [{"id": ident, "state": labels(im.PRESETS[name]), "policy": buttons, "preset": name} for ident in SAMPLE for name, buttons in PLAN]
        with tempfile.TemporaryDirectory() as tmp:
            path, out = Path(tmp) / "jobs.json", Path(tmp) / "out.json"
            path.write_text(json.dumps(jobs), encoding="utf-8")
            subprocess.run(["node", "iscriptprobe.mjs", str(path), str(out)], cwd=REFNES, check=True, capture_output=True, timeout=900)
            results = json.loads(out.read_text(encoding="utf-8"))
        bad = []
        for job, got in zip(jobs, results):
            actions, _messages, after = im.run(script, job["id"], im.PRESETS[job["preset"]], job["policy"])
            seen = [t for t in got["trace"] if t != -1]
            if not got["done"] or seen != actions or state_of(got["after"]) != after.key():
                bad.append(f"script {job['id']:#x} {job['preset']} {job['policy']}: done={got['done']} rom {[hex(t) for t in seen]} model {[hex(t) for t in actions]}")
        self.assertEqual(bad, [])

    def test_the_walking_man_of_eolis_walks_60_frames_waits_30_and_faces_the_hero(self) -> None:
        """BSCRIPT of entity $34 (bank 14): SWITCH_BEHAVIOR walk (60 frames, 0.75 pixel a frame the way it faces), SWITCH_BEHAVIOR wait (30 frames), RUN_ACTION 0 (face the
        player), GOTO. What the ROM does is recorded here; the port's people stand still (docs: AGENTS.md)."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "walk.json"
            subprocess.run(["node", "walkerprobe.mjs", str(out), "520"], cwd=REFNES, check=True, capture_output=True, timeout=300)
            rows = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual({r["entity"] for r in rows}, {0x34})
        at = lambda r: r["x"] + r["frac"] / 256                                # noqa: E731
        runs, start = [], 0
        for i in range(1, len(rows) + 1):
            if i == len(rows) or (rows[i]["beh"] & 0x7F) != (rows[start]["beh"] & 0x7F):
                runs.append((rows[start]["beh"] & 0x7F, i - start, start, i - 1))
                start = i
        walks = [r for r in runs[1:-1] if r[0] == 4]
        waits = [r for r in runs[1:-1] if r[0] == 0x15]
        self.assertTrue(len(walks) >= 3 and len(waits) >= 3)
        for beh, length, first, last in walks:
            self.assertEqual(length, 60, "a walk lasts 60 frames")
            step = (at(rows[last]) - at(rows[first])) / (length - 1)
            self.assertAlmostEqual(abs(step), 0.75, places=2)
            self.assertEqual(step > 0, bool(rows[first]["flags"] & 1), "he walks the way he faces (flags bit 0: right)")
        for beh, length, first, last in waits:
            self.assertEqual(length, 30, "a wait lasts 30 frames")
            self.assertEqual(at(rows[first]), at(rows[last]))
        for (_b, _l, _f, last), (_b2, _l2, first, _l3) in zip(waits, walks[1:]):          # after each wait he faces the hero
            self.assertEqual(bool(rows[first]["flags"] & 1), rows[first]["hero"] > rows[first]["x"], "RUN_ACTION 0: face the player")


if __name__ == "__main__":
    unittest.main()
