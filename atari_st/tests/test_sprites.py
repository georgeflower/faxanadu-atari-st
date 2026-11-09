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

    def test_the_hero_inside_a_building_has_the_same_colours_as_outside(self) -> None:
        """A building loads the inside sprite palettes ($1D0 of bank 11, outside $1C0): they differ in palettes 2 and 3 only (the people's and the enemies'), and the hero and his spells
        draw with palettes 0 and 1, so the converter's outside palettes colour him right inside too. jsnes: the PPU's palettes outside and inside are the ROM's tables, the hero in the
        building (Eolis screen 1's door, standing, no weapon: it is put away inside) is the converter's picture pixel for pixel."""
        import nes_palette
        import st_convert as sc

        b11 = self.rom.prg(11)
        table = lambda base: [list(b11[base + 4 * i:base + 4 * i + 4]) for i in range(4)]
        self.assertEqual(table(0x1C0)[:2], table(0x1D0)[:2])
        self.assertNotEqual(table(0x1C0)[2:], table(0x1D0)[2:])
        for index in range(0x11, 0x1B):                                  # the ten building palette sets
            self.assertEqual(sc.palette_set(self.rom, index, "inside")[1][:2], sc.sprite_palettes(self.rom, index)[:2])
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "i")
            subprocess.run(["node", "insidepalette.mjs", prefix], cwd=REFNES, check=True, capture_output=True)
            state = json.loads(Path(prefix + ".json").read_text())
            chr_ = Path(prefix + "_in.chr.bin").read_bytes()
            ppm = self.rs.read_ppm(Path(prefix + "_in.ppm"))
        self.assertEqual([state["outside"]["sprite"][i * 4:i * 4 + 4] for i in range(4)], table(0x1C0), "outside: the $1C0 palettes")
        self.assertEqual([state["inside"]["sprite"][i * 4:i * 4 + 4] for i in range(4)], table(0x1D0), "inside: the $1D0 palettes")
        self.assertEqual(state["area"], 4)
        hero = state["hero"]
        equipment = (hero["armor"], hero["shield"], 255)                  # (the weapon is not drawn inside)
        tiles = self.sp.pattern_tiles(self.rom, *equipment)
        self.assertEqual([n for n, b in tiles.items() if chr_[n * 16:n * 16 + 16] != b], [])
        sprites = self.sp.hero_sprites(self.rom, hero["x"], hero["y"], *equipment, 0, bool(hero["flags"] & 0x40))
        layer = self.sp.sprite_layer(sprites, tiles, sc.sprite_palettes(self.rom, state["inside"]["index"]))
        bad = [(x, y) for (x, y), c in layer.items() if tuple(ppm[y][x]) != tuple(nes_palette.NES_RGB[c & 0x3F])]
        self.assertEqual(bad[:5], [])
        self.assertGreater(len(layer), 100)

    def test_a_hero_on_a_real_ladder_is_drawn_as_the_game_draws_him(self) -> None:
        """Mist screen 0 has a ladder (column 2): with the stick up and down he climbs it, in the climbing body frame 7 (`Player_GetBodySpriteFrameOffset`), mirrored by bit 4 of the
        movement tick alone: the game stores that over the facing, so a hero facing either way is mirrored the same, and his weapon and shield follow (the model once did an OR with the
        facing). Every frame of the climb up, the hang, the climb down and the frames before, for four equipments and both facings, the sprites jsnes holds (the same tiles, places and
        attributes; the behind-the-background bit is the screen's) equal `hero_sprites` made from the state the game drew them from."""
        flips = set()
        for equipment, facing in (((0, 255, 255), 1), ((1, 1, 2), 1), ((3, 3, 3), 0), ((2, 255, 0), 1)):
            with self.subTest(equipment=equipment, facing=facing):
                with tempfile.TemporaryDirectory() as tmp:
                    out = os.path.join(tmp, "l.json")
                    subprocess.run(["node", "ladderprobe.mjs", *map(str, equipment), str(facing), out], cwd=REFNES, check=True, capture_output=True)
                    frames = json.loads(Path(out).read_text())
                bad, checked, climbing = [], 0, 0
                for before, now in zip(frames, frames[1:]):
                    game = sorted((e[3], e[0], e[1], e[2] & ~0x20) for e in now["oam"] if e[1] < 0x80)
                    if not game:                                           # (the first frames after the warp: the hero is not drawn yet)
                        continue
                    on = self.sp.is_climbing(before["flags"], before["x"])
                    frame, extra = self.sp.body_frame(before["flags"], before["tick"], before["attack"], before["status"], before["joy"], on)
                    mine = sorted((s.x, s.y, s.tile, s.attr & ~0x20) for s in self.sp.hero_sprites(
                        self.rom, before["x"], before["y"], *equipment, frame, bool(before["flags"] & 0x40), extra, before["scrollX"], -1, on))
                    checked += 1
                    climbing += on
                    if on:
                        flips.add((facing, extra))
                    if mine != game:
                        bad.append((now["phase"], before["tick"], on))
                self.assertEqual(bad[:5], [])
                self.assertGreater(checked, 150)
                self.assertGreater(climbing, 100)
        self.assertEqual(flips, {(0, 0), (0, 0x40), (1, 0), (1, 0x40)}, "both mirrors were seen for both facings")

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
