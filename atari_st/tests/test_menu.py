"""The player menu: the Python model (`enemy_model.Engine.menu_choose`) against the ROM in jsnes (`tools/refnes/menuprobe.mjs`: Select, the cursor to a
category, A, the cursor to an entry, A; what the game changed is read from its RAM)."""
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
         ("MagicInventory", "NumberOfMagicSpells", "magics"), ("ItemInventory", "NumberOfItems", "items"))
SELECTED = ("SelectedWeapon", "SelectedArmor", "SelectedShield", "SelectedMagic", "SelectedItem")
# what he owns (the lists hold what is not worn) and what he wears
PRESETS = {
    "some": {"NumberOfWeapons": 2, "WeaponInventory": [1, 2, 0, 0], "SelectedWeapon": 0, "NumberOfArmors": 2, "ArmorInventory": [1, 2, 0, 0], "SelectedArmor": 0,
             "NumberOfShields": 1, "ShieldInventory": [1, 0, 0, 0], "SelectedShield": 0, "NumberOfMagicSpells": 3, "MagicInventory": [1, 3, 4, 0], "SelectedMagic": 0,
             "NumberOfItems": 3, "ItemInventory": [9, 4, 0x0F, 0, 0, 0, 0, 0], "SelectedItem": 0x10},
    "nothing worn": {"NumberOfMagicSpells": 2, "MagicInventory": [0, 2, 0, 0], "SelectedMagic": 255, "NumberOfItems": 2, "ItemInventory": [9, 4, 0, 0, 0, 0, 0, 0], "SelectedItem": 255,
                     "NumberOfShields": 2, "ShieldInventory": [0, 2, 0, 0], "SelectedShield": 255},
    # the Dragon Slayer, the Battle Suit and the Battle Helmet owned (worn: the plain ones) : choosing any of them puts all three on
    "slayer owned": {"NumberOfWeapons": 2, "WeaponInventory": [1, 3, 0, 0], "SelectedWeapon": 0, "NumberOfArmors": 2, "ArmorInventory": [3, 1, 0, 0], "SelectedArmor": 2,
                     "NumberOfShields": 2, "ShieldInventory": [3, 1, 0, 0], "SelectedShield": 0},
    "slayer without suit": {"NumberOfWeapons": 2, "WeaponInventory": [1, 3, 0, 0], "SelectedWeapon": 0, "NumberOfArmors": 2, "ArmorInventory": [3, 1, 0, 0], "SelectedArmor": 2,
                            "NumberOfShields": 1, "ShieldInventory": [1, 0, 0, 0], "SelectedShield": 0},
    "all three worn": {"NumberOfWeapons": 1, "WeaponInventory": [1, 0, 0, 0], "SelectedWeapon": 3, "NumberOfArmors": 1, "ArmorInventory": [1, 0, 0, 0], "SelectedArmor": 3,
                       "NumberOfShields": 1, "ShieldInventory": [1, 0, 0, 0], "SelectedShield": 3},
    "full pack": {"NumberOfItems": 8, "ItemInventory": [9, 4, 0x0F, 0x10, 0x0D, 5, 6, 7], "SelectedItem": 0x0A},
}
# (preset, category, entry): the cursor goes down `category` places, A, down `entry` places, A
SCENES = [("some", 0, 0), ("some", 0, 1), ("some", 1, 1), ("some", 2, 0), ("some", 3, 2), ("some", 4, 1), ("some", 4, 2),
          ("nothing worn", 3, 1), ("nothing worn", 4, 0), ("nothing worn", 2, 1),
          ("slayer owned", 0, 1), ("slayer owned", 1, 0), ("slayer owned", 2, 0), ("slayer owned", 1, 1),
          ("slayer without suit", 0, 1), ("slayer without suit", 1, 0),
          ("all three worn", 0, 0), ("all three worn", 1, 0), ("all three worn", 2, 0),
          ("full pack", 4, 7), ("full pack", 4, 0)]


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_probe(self, preset: str, category: int, entry: int) -> dict:
        out = Path(self.tmp.name) / f"{preset.replace(' ', '_')}_{category}_{entry}.json"
        keys = ",".join(["SELECT"] + ["DOWN"] * category + ["A", "WAIT"] + ["DOWN"] * entry + ["A"])
        subprocess.run(["node", "menuprobe.mjs", "1", "24", keys, str(out), json.dumps(PRESETS[preset])], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, env=os.environ)
        return json.loads(out.read_text())

    def test_choosing_an_entry_does_to_the_hero_what_the_rom_does(self) -> None:
        import enemy_model as em

        for preset, category, entry in SCENES:
            with self.subTest(preset=preset, category=category, entry=entry):
                run = self.run_probe(preset, category, entry)
                before, after = run["before"], run["after"]
                eng = em.Engine(b"", b"", bytes(256), b"")
                h = eng.hero
                for label, count, mine in LISTS:
                    setattr(h, mine, list(before[label][:before[count]]))
                h.weapon, h.armour, h.shield, h.magic, h.item = (before[n] for n in SELECTED)
                h.special = before["SpecialItems"]
                eng.menu_choose(category, entry)
                for label, count, mine in LISTS:
                    self.assertEqual(getattr(h, mine), after[label][:after[count]], label)
                self.assertEqual((h.weapon, h.armour, h.shield, h.magic, h.item, h.special), tuple(after[n] for n in SELECTED) + (after["SpecialItems"],))
                self.assertEqual(h.events, [s for _, s in run["sounds"] if s in (8, 13)])


if __name__ == "__main__":
    unittest.main()
