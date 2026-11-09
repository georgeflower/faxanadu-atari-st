"""Sprites behind the background: the NES draws a sprite's 8-pixel column with the "behind the background" bit when the block under it has the property 4, 9 or 13
(`Player_CalculateVisibility`, `CurrentSprite_CalculateVisibility`); on the ST `behind_set` and `behind_image` (src/enemy.s) do the same with the package part `behind`
(`tools/behind.py`). Eolis screen 4 has a pillar (blocks 92 and 93, x 176 to 207, rows 4 to 10) that the hero and the Zozuras walk behind.

The ROM is checked in jsnes (`tools/refnes/behindprobe.mjs`: the attribute bit 5 of every hero and Zozura sprite against the rule), the ST in Hatari."""
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
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class BehindInTheRomTests(unittest.TestCase):
    def test_the_attribute_bit_of_every_hero_and_enemy_column_follows_the_rule(self) -> None:
        """Walking left through the pillar and back (130 frames each way): for every frame the hero's two body columns and each Zozura's two columns have the bit
        exactly when the block under x + 4 (left) or x + 12 (right) in the row of the sprite's y has property 4, 9 or 13, whichever way he faces; the walk covers all four
        combinations for the hero and the three that fit the pillar for the enemies."""
        import behind
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "behind.json"
            subprocess.run(["node", "behindprobe.mjs", "4", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            rec = json.loads(out.read_text())
        hero_seen, enemy_seen = set(), set()
        for r in rec:
            y = r["y"]
            body = [o for o in r["oam"] if o[1] < 0x20 and y + 32 <= o[0] < y + 64 and abs(o[3] - r["x"]) < 20]        # [line above, tile, attribute, x]
            if body:
                x = min(o[3] for o in body)                                  # (the game draws before it moves him: the sprites say where he was drawn)
                v = behind.halves(rom, a, 4, x, y)
                for o in body:
                    column = (o[3] - x) // 8
                    self.assertEqual(bool(o[2] & 0x20), bool(v & (1 << column)), f"hero at {x},{y}: sprite {o}")
                    hero_seen.add((v, column))
            for s in r["slots"]:
                if s["e"] == 255:
                    continue
                sprites = [o for o in r["oam"] if o[1] >= 0x80 and s["y"] + 32 <= o[0] < s["y"] + 64 and 0 <= o[3] - s["x"] < 16]
                if not sprites:
                    continue
                x = min(o[3] for o in sprites)
                v = behind.halves(rom, a, 4, x, s["y"])
                for o in sprites:
                    column = (o[3] - x) // 8
                    self.assertEqual(bool(o[2] & 0x20), bool(v & (1 << column)), f"enemy {s} drawn at {x}: sprite {o}")
                    enemy_seen.add((v, column))
        self.assertEqual(len({v for v, _ in hero_seen}), 4, sorted(hero_seen))
        self.assertGreaterEqual(len({v for v, _ in enemy_seen}), 3, sorted(enemy_seen))
        self.assertIn((3, 1), hero_seen)


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class BehindOnTheStTests(unittest.TestCase):
    """Eolis screen 4. The hero stands at x1 (no weapon: the sword's own visibility, which the ROM works out at the weapon's place, is not done) and the first Zozura is
    put at x2 (the Hour Glass holds it still), the other taken away. The picture is the background, then the hero's and the Zozura's pictures with the pixels dropped
    that `behind.drop_behind` says (the blocks of the package part only: the neighbours of the pillar are in front on the NES as well, a few pixels at the edge)."""

    def scene(self, hero_x: int, enemy_x: int) -> None:
        import behind
        import enemy_data as ed
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import faxanadu_sprites as fs
        import hatari_shot as hs
        import st_convert as sc
        from test_viewer import ViewerTests

        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        run_scenario = ViewerTests.run_scenario.__get__(self)
        pal = a.palette_index
        plan = sc.plan_for_set(rom, pal)
        palettes = sc.sprite_palettes(rom, pal)
        pokes = [(100, "w:hero_invinc", 30000), (250, "w:hourglass", 60), (255, "mem:enemies+180", 255), (257, f"mem:enemies+212", enemy_x), (258, "hp", 99)]
        ram, word, log = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", f"HERO={hero_x},144,0,255,255,0,0", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 330, "shots_behind")
        raw = word.raw("enemies", 8 * 30)
        slot = raw[7 * 30:8 * 30]
        self.assertEqual((slot[0], slot[2], slot[4]), (0x47, enemy_x, 160), "the Zozura stands where it was put")
        hud = word.raw("hud_state", 10)
        rows = hs.decode_screen(ram, hs.video_base(log))
        camera = word("camera")
        opaque = behind.opaque_screen(rom, a, 4, True)
        expected = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]))
        hero = sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 255, word("hero_frame"), bool(word("hero_flip")))
        self.assertEqual(word("hero_x"), hero_x)
        pictures = [(hero.x, hero.y, fs.sprite_layer(hero.sprites(rom), fs.pattern_tiles(rom, 0, 255, 255), palettes))]
        counter = word("en_counter")
        app = fs.appearance(rom, ed.entity(rom, 0x47)["appearance"] + ((counter >> 4) & 1), "TILEINFO_ENTITY_ADDRS")
        pictures.append((enemy_x, 160, fs.sprite_layer(fs.place(app, enemy_x, 160, 0x40 if slot[1] & 1 else 0), fs.entity_tiles(rom, 0x47), palettes)))
        want_halves = []
        for x, y, layer in pictures:
            v = behind.halves(rom, a, 4, x, y)
            want_halves.append(v)
            for (px, line), c in behind.drop_behind(layer, x, v, opaque).items():
                yy = line - camera
                if sc.ST_TOP <= yy < 200 and sc.ST_LEFT <= px + sc.ST_LEFT < sc.ST_LEFT + 256:
                    expected[yy][px + sc.ST_LEFT] = plan.slot[c & 0x3F]
        bad = [(x, y) for y in range(200) for x in range(320) if rows[y][x] != expected[y][x]]
        self.assertEqual(bad[:6], [], f"hero {hero_x}, enemy {enemy_x}: {len(bad)} pixels differ (the halves behind: {want_halves})")
        # (and the test is not vacuous: without the rule the pictures differ)
        plain = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]))
        for x, y, layer in pictures:
            for (px, line), c in layer.items():
                yy = line - camera
                if sc.ST_TOP <= yy < 200 and sc.ST_LEFT <= px + sc.ST_LEFT < sc.ST_LEFT + 256:
                    plain[yy][px + sc.ST_LEFT] = plan.slot[c & 0x3F]
        self.assertGreater(sum(rows[y][x] != plain[y][x] for y in range(200) for x in range(320)), 100, "the pictures would be the same without the rule")
        return want_halves

    def test_both_halves_of_the_hero_and_the_left_half_of_a_zozura_are_behind_the_pillar(self) -> None:
        self.assertEqual(self.scene(184, 200), [3, 1])

    def test_the_left_half_of_the_hero_and_both_halves_of_a_zozura_are_behind_the_pillar(self) -> None:
        self.assertEqual(self.scene(200, 180), [1, 3])
