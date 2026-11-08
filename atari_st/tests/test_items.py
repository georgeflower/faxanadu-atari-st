"""Picking up the things that lie on the screens: the Python model against the ROM in jsnes (`tools/refnes/pickprobe.mjs`: the hero stands on the item,
the message is dismissed, and what the game changed is read from its RAM)."""
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
LISTS = (("WeaponInventory", "NumberOfWeapons", "weapons"), ("ArmorInventory", "NumberOfArmors", "armours"), ("ShieldInventory", "NumberOfShields", "shields"),
         ("ItemInventory", "NumberOfItems", "items"))
# a new game owns nothing; the others are states in which the game's habits show (a full pack, the lists the suit and the slayer mix up)
PRESETS = {
    "new": {},
    "full": {"NumberOfItems": 8, "ItemInventory": [1, 2, 3, 4, 5, 6, 7, 8]},
    "mixed": {"NumberOfWeapons": 2, "WeaponInventory": [0, 1, 0, 0], "NumberOfArmors": 3, "ArmorInventory": [0, 1, 2, 0], "NumberOfShields": 4, "ShieldInventory": [0, 1, 2, 0]},
    "many": {"NumberOfWeapons": 4, "WeaponInventory": [0, 1, 2, 0], "NumberOfArmors": 4, "ArmorInventory": [0, 1, 2, 0], "NumberOfShields": 1, "ShieldInventory": [0, 0, 0, 0]},
    "hurt": {"Player_HP_U": 10},
    "owns": {"SpecialItems": 0x0B, "Quests": 0x18, "DurationGlove": 5, "DurationOintment": 7},
}


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class PickUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import enemy_data as ed
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ed = ed

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_probe(self, ent: int, preset: str) -> dict:
        out = Path(self.tmp.name) / f"{ent}_{preset}.json"
        subprocess.run(["node", "pickprobe.mjs", "1", "24", "16", "64", str(out), json.dumps(PRESETS[preset])], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True,
                       env={**os.environ, "INJECT": str(ent)})
        return json.loads(out.read_text())

    def model_after(self, before: dict, ent: int):
        import enemy_model as em

        eng = em.Engine(b"", b"", bytes(256), b"")
        h = eng.hero
        for label, count, mine in LISTS:
            setattr(h, mine, list(before[label][:before[count]]))
        h.special, h.quests, h.glove, h.ointment = before["SpecialItems"], before["Quests"], before["DurationGlove"], before["DurationOintment"]
        h.exp, h.hp_u, h.hp_l, h.inv = before["Experience"] | before["Experience_U"] << 8, before["Player_HP_U"], before["Player_HP_L"], before["Player_InvincibilityPhase"]
        eng.pickup(ent)
        return eng

    def test_every_item_does_to_the_hero_what_the_rom_does(self) -> None:
        for ent in self.ed.ITEMS:
            for preset in PRESETS:
                if preset in ("many", "mixed") and ent not in (0x58, 0x59, 0x5A):
                    continue
                if preset in ("full", "hurt", "owns") and ent in (0x58, 0x59, 0x5A):
                    continue
                with self.subTest(item=hex(ent), preset=preset):
                    run = self.run_probe(ent, preset)
                    self.assertGreaterEqual(run["picked"], 0, "the game did not take it")
                    before, after = run["before"], run["after"]
                    eng = self.model_after(before, ent)
                    h = eng.hero
                    for label, count, mine in LISTS:
                        self.assertEqual(getattr(h, mine), after[label][:after[count]], f"{label}: {before[label]} {before[count]}")
                    self.assertEqual((h.special, h.quests, h.glove, h.ointment), (after["SpecialItems"], after["Quests"], after["DurationGlove"], after["DurationOintment"]))
                    self.assertEqual((h.exp, h.hp_u, h.hp_l), (after["Experience"] | after["Experience_U"] << 8, after["Player_HP_U"], after["Player_HP_L"]))
                    if not h.dead:                                      # (the death routine puts the phase right again)
                        self.assertEqual(h.inv, after["Player_InvincibilityPhase"])
                    self.assertEqual(h.events[-1] if h.events else None, run["sounds"][-1][1])


if __name__ == "__main__":
    unittest.main()
