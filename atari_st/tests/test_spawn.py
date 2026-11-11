"""Where the hero comes back after a death or a mantra (Game_SpawnInTemple, Player_Spawn): the ROM in jsnes for all eight temple spawn points
(`tools/refnes/spawnprobe.mjs`) against the port's tables in src/flow.s (`temple_enter`, tt_*), and the rule of the script action that sets the spawn point.
The port's whole path (death, the message, the temple, the door out) is run in Hatari by tests/test_flow.py for spawn points 0 and 3."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
FLOW = ROOT / "src" / "flow.s"


def flow_table(name: str) -> list[int]:
    text = FLOW.read_text(encoding="utf-8")
    m = re.search(rf"^{name}:.*\n\s*\.byte ([^|\n]+)", text, re.M)
    return [int(v.strip(), 0) for v in m.group(1).split(",")]


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class SpawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        out = subprocess.run(["node", "spawnprobe.mjs"], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, text=True).stdout
        cls.runs = json.loads(out)

    def test_every_spawn_point_leads_where_the_rom_takes_him(self) -> None:
        area, screen, x, y = flow_table("tt_area"), flow_table("tt_screen"), flow_table("tt_x"), flow_table("tt_y")
        dest, palette, music = flow_table("tt_dest"), flow_table("tt_palette"), flow_table("tt_music")
        self.assertEqual(len(self.runs), 8)
        for run in self.runs:
            k, temple, outside = run["k"], run["temple"], run["outside"]
            with self.subTest(spawn=k):
                self.assertEqual((temple["area"], temple["x"], temple["y"], temple["flags"] & 0x40), (4, 224, 144, 0))     # the temple, at $9E, facing left
                self.assertEqual(temple["dest"], dest[k])                                       # the temple's people (building_id)
                self.assertEqual((temple["hp"], temple["mp"]), (80, 80))
                self.assertEqual(temple["quests"], 0x07)                                        # Player_Spawn: the Mattock's quest bit (4) goes
                self.assertEqual((outside["area"], outside["screen"], outside["x"], outside["y"]), (area[k], screen[k], x[k], y[k]))
                self.assertEqual(outside["palette"], palette[outside["area"]])
                self.assertEqual(outside["music"] & 0x7F, music[outside["area"]])

    def test_the_port_sets_the_spawn_point_as_the_rom_does(self) -> None:
        """IScriptAction_SetSpawnPoint keeps the later temple (CMP, BCC: a lower number is not taken); the port's op_set_spawn does the same, and the start position
        in the temple is $9E as Game_SpawnInTemple's."""
        town = (ROOT / "src" / "town.s").read_text(encoding="utf-8")
        body = town[town.index("op_set_spawn:"):town.index("op_if_quest:")]
        self.assertIn("cmp.w hero_spawn(%pc), %d0", body)
        self.assertIn("bcs.s 1f", body)
        flow = FLOW.read_text(encoding="utf-8")
        self.assertIn("move.w #0x9E, %d1", flow[flow.index("temple_enter:"):flow.index("flow_exit_music:")])
        items = (ROOT / "src" / "items.s").read_text(encoding="utf-8")
        self.assertIn("andi.b #0xEF, INV_QUESTS(%a0)", items[items.index("timers_clear:"):items.index("use_elixir:")])


if __name__ == "__main__":
    unittest.main()
