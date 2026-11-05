"""The hero decoder (tools/faxanadu_sprites.py) against jsnes running the game.

For several equipments: the pattern tiles equal the PPU's, the sprites equal the game's sprite list frame by frame while the hero walks,
crouches, attacks and jumps, and the picture of the hero equals jsnes' picture pixel for pixel.
Skipped without the ROM, cc65, node and jsnes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from test_data import have_harness, have_rom  # noqa: E402

REFNES = ROOT / "tools" / "refnes"
EQUIPMENT = [(0, 255, 0), (0, 0, 1), (1, 1, 2), (2, 2, 3), (3, 255, 0), (3, 3, 3), (2, 1, 3)]   # armour, shield, weapon


@unittest.skipUnless(have_rom() and have_harness(), "needs the ROM, cc65, node and jsnes (npm install in tools/refnes)")
class HeroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr
        import faxanadu_sprites as sp
        import nes_palette
        import render_screen as rs

        cls.fr, cls.sp, cls.rs, cls.rgb = fr, sp, rs, nes_palette.NES_RGB
        cls.rom = fr.Rom(ROOT.parent / "ext" / "Faxanadu_Europe.nes")

    def shot(self, equipment: tuple[int, int, int], hero_x: int = 64) -> tuple[dict, bytes, list]:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "h")
            subprocess.run(["node", "heroshot.mjs", *map(str, equipment), prefix], cwd=REFNES, check=True, capture_output=True,
                           env=dict(os.environ, HERO_X=str(hero_x)))
            state = json.loads(Path(prefix + ".state.json").read_text())
            return state, Path(prefix + ".chr.bin").read_bytes(), self.rs.read_ppm(Path(prefix + ".ppm"))

    def test_the_pattern_tiles_and_the_picture_equal_jsnes(self) -> None:
        for equipment in EQUIPMENT:
            with self.subTest(equipment=equipment):
                state, chr_, ppm = self.shot(equipment)
                tiles = self.sp.pattern_tiles(self.rom, *equipment)
                self.assertEqual([n for n, b in tiles.items() if chr_[n * 16:n * 16 + 16] != b], [])
                sprites = self.sp.hero_sprites(self.rom, state["x"], state["y"], *equipment, 0, bool(state["flags"] & 0x40))
                palettes = [state["sprPal"][i * 4:i * 4 + 4] for i in range(4)]
                self.assertEqual(palettes[:2], [list(self.rom.prg(11)[0x1C0 + 4 * i:0x1C0 + 4 * i + 4]) for i in range(2)])
                layer = self.sp.sprite_layer(sprites, tiles, palettes)
                bad = [(x, y) for (x, y), c in layer.items() if tuple(ppm[y][x]) != tuple(self.rgb[c & 0x3F])]
                self.assertEqual(bad[:5], [])
                self.assertGreater(len(layer), 100)

    def test_every_frame_of_a_walk_attack_and_jump_equals_the_games_sprites(self) -> None:
        for equipment in [(0, 255, 0), (1, 1, 2), (3, 3, 3)]:
            with self.subTest(equipment=equipment):
                with tempfile.TemporaryDirectory() as tmp:
                    out = os.path.join(tmp, "w.json")
                    subprocess.run(["node", "herowalk.mjs", *map(str, equipment), out], cwd=REFNES, check=True, capture_output=True)
                    frames = json.loads(Path(out).read_text())
                bad = 0
                for before, now in zip(frames, frames[1:]):
                    # the game draws before it moves: the state of the frame before is what the sprites were made from
                    frame, extra = self.sp.body_frame(before["flags"], before["tick"], before["attack"], before["status"], before["joy"])
                    mine = sorted((s.x, s.y, s.tile, s.attr) for s in self.sp.hero_sprites(
                        self.rom, before["x"], before["y"], *equipment, frame, bool(before["flags"] & 0x40), extra, before["scrollX"],
                        before["attack"] if before["flags"] & 0x80 else -1))
                    game = sorted((e[3], e[0], e[1], e[2]) for e in now["oam"] if e[1] < 0x80)
                    bad += mine != game
                self.assertEqual(bad, 0)
                self.assertGreater(len(frames), 250)


if __name__ == "__main__":
    unittest.main()
