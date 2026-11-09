"""Sprites behind the background: the NES draws a sprite's 8-pixel column with the "behind the background" bit when the block under it has the property 4, 9 or 13
(`Player_CalculateVisibility`, `CurrentSprite_CalculateVisibility`); on the ST `behind_set` and `behind_tile` (src/enemy.s, src/blit.s) do the same with the package part `behind`
(`tools/behind.py`). Eolis screen 4 has a pillar (blocks 92 and 93, x 176 to 207, rows 4 to 10) that the hero and the Zozuras walk behind.

The ROM is checked in jsnes (`tools/refnes/behindprobe.mjs`: the attribute bit 5 of every hero and Zozura sprite against the rule; `behindspots.mjs`: the same for the hero's
arm piece, weapon and shield, each at its own place), the ST in Hatari."""
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

    def test_the_attribute_bit_of_every_spell_column_follows_the_rule(self) -> None:
        """Every spell cast through the pillar from six places (`magicbehind.mjs`, both ways): its sprites have the bit exactly when the block under x + 4 (left column) or
        x + 12 (right) of the spell's place has property 4, 9 or 13, counted from the picture's left edge, which is the spell's x, whichever way it flies (the game swaps the
        two bits for one way, but then it draws the tiles in the other order; the physical columns keep their bits). `CastMagic_CalculateVisibility` counts only property 4 on
        the right (it compares with 4 before it looks at 13 and 9), which the pillar cannot show. The recorded place is that of the pass after the one the sprites are from."""
        import behind
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "magic.json"
            subprocess.run(["node", "magicbehind.mjs", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            rec = json.loads(out.read_text())
        seen = set()
        for before, r in zip(rec, rec[1:]):
            if (before["spell"], before["hx"], before["type"]) != (r["spell"], r["hx"], r["type"]):
                continue
            x, y = before["x"], before["y"]
            sprites = [o for o in r["oam"] if o[1] >= 0x50 and abs(o[0] - 32 - y) <= 16 and abs(o[3] - x) <= 40]          # [line above, tile, attribute, x]
            if not sprites:
                continue
            self.assertEqual(min(o[3] for o in sprites), x, "the picture's left edge is the spell's x")
            v = behind.halves(rom, a, 4, x, y)
            for o in sprites:
                column = ((o[3] - x) // 8) & 1
                self.assertEqual(bool(o[2] & 0x20), bool(v & (1 << column)), f"spell {r['spell']} at {x},{y} ({r['cflags']:#x}): sprite {o}")
                seen.add((v, column))
        self.assertEqual(seen, {(v, c) for v in range(4) for c in range(2)}, sorted(seen))

    def test_the_arm_piece_the_weapon_and_the_shield_are_behind_by_their_own_place(self) -> None:
        """The hero strikes at every x from 160 to 215 facing either way (`behindspots.mjs`: dagger with the small shield, long sword with the large one): the sprites of the shield
        (tiles $30 to $37), of the weapon (from $38) and of the arm piece (the body's tiles at x - 8 or x + 16) have the bit exactly when the block under x + 4 or x + 12 of the
        part's own place has property 4, 9 or 13, where the part's place is the hero's x and y for the body, x - 8 / x + 16 and y for the arm piece, (`PlayerPosXPlus10`,
        `Maybe_Something_WeaponPosY`: the picture's own corner, see `weapon_offset`) for the weapon and x + SHIELD_SPRITE_OFFSETS_X, y + 8 for the shield; the picture's left edge is that x for every part."""
        import behind
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        a = fm.area(rom, 0)
        seen: set = set()
        for equip in ("1,0,1", "2,1,2"):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "spots.json"
                subprocess.run(["node", "behindspots.mjs", "160", "215", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, env={**os.environ, "EQUIP": equip})
                rec = json.loads(out.read_text())
            for r in rec:
                if r["flags"] & 0x20:
                    continue                                                 # (walking: not set up by the harness)
                x, y, left = r["x"], r["y"], r["flags"] & 0x40 != 0
                parts: dict[str, list] = {"shield": [], "weapon": [], "arm": []}
                for o in r["oam"]:                                           # [line above, tile, attribute, x]
                    if 0x30 <= o[1] < 0x38:
                        parts["shield"].append(o)
                    elif o[1] >= 0x38:
                        parts["weapon"].append(o)
                    elif o[3] == x + (16 if left else -8):
                        parts["arm"].append(o)
                for part, sprites in parts.items():
                    if not sprites:
                        continue
                    ox, oy = {"shield": (min(o[3] for o in sprites), y + 8), "weapon": (min(o[3] for o in sprites), min(o[0] for o in sprites) - 32), "arm": (x + (16 if left else -8), y)}[part]
                    self.assertEqual(min(o[3] for o in sprites), ox, f"{part}: the picture's left edge is the part's x")
                    if part != "arm":
                        self.assertEqual(min(o[0] for o in sprites) - 32, oy, f"{part}: the picture's top is the part's y")
                    v = behind.halves(rom, a, 4, ox, oy)
                    for o in sprites:
                        column = ((o[3] - ox) // 8) & 1
                        self.assertEqual(bool(o[2] & 0x20), bool(v & (1 << column)), f"{part} of the hero at {x},{y} (left {left}) at {ox},{oy}: sprite {o}")
                        seen.add((part, v, column))
        for part in ("shield", "weapon", "arm"):
            self.assertGreaterEqual(len({v for p, v, _ in seen if p == part}), 2, (part, sorted(seen)))


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class BehindOnTheStTests(unittest.TestCase):
    """Eolis screen 4. The hero stands at x1 and the first Zozura is put at x2 (the Hour Glass holds it still), the other taken away. The picture is the background, then
    the hero's parts (his body; with a weapon in the attack frames the arm piece and the weapon; with a shield the shield) and the Zozura's picture, each with the pixels
    dropped that `behind.drop_behind` says for its own place (the blocks of the package part only: the neighbours of the pillar are in front on the NES as well, a few pixels
    at the edge)."""

    @staticmethod
    def hero_parts_at(rom, hero_x: int, hero_y: int, shield: int, weapon: int, frame: int, flip: int, palettes) -> list:
        """[(x, y, layer)] for the parts of the hero that are drawn (armour 0), each with the place the ROM works its visibility at: the body at the hero's, the arm piece at
        x - 8 (x + 16 facing the way the flip bit says) and y, the weapon at `weapon_offset` from him, the shield at SHIELD_SPRITE_OFFSETS_X and 8 lower."""
        import faxanadu_sprites as fs

        left = bool(flip)
        parts = fs.hero_parts(rom, hero_x, hero_y, 0, shield, weapon, frame, left, attacking_frame=2 if frame == 6 else -1)
        tiles = fs.pattern_tiles(rom, 0, shield, weapon)
        origins = [(hero_x, hero_y), (hero_x + (16 if left else -8), hero_y)]
        if weapon != fs.NO_ITEM:
            dx, dy = fs.weapon_offset(rom, 0, shield, weapon, frame, left)
            origins.append(((hero_x + dx) & 0xFF, (hero_y + dy) & 0xFF))
        else:
            origins.append((0, 0))
        origins.append(((hero_x + rom.byte("SHIELD_SPRITE_OFFSETS_X", 2 * frame + (1 if left else 0))) & 0xFF, hero_y + 8))
        return [(x, y, fs.sprite_layer(part, tiles, palettes)) for part, (x, y) in zip(parts, origins) if part]

    def scene(self, hero_x: int, enemy_x: int | None, shield: int = 255, weapon: int = 255, frame: int = 0, flip: int = 0, capture: int = 330, least: int = 100) -> list[int]:
        """Returns the halves behind of each picture: the hero's body, the arm piece, the weapon and the shield when he has them (each at its own place, see
        `hero_parts_at`), then the Zozura's."""
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
        pokes = [(165, "w:hero_invinc", 30000), (170, "w:hero_invinc", 30000), (250, "w:hourglass", 60), (255, "mem:enemies+180", 255), (257, f"mem:enemies+212", enemy_x), (258, "hp", 99)]
        if enemy_x is None:                                                  # no Zozuras (both taken away), and he strikes (B) when the weapon is out
            pokes = [(165, "w:hero_invinc", 30000), (170, "w:hero_invinc", 30000), (195, "mem:enemies+180", 255), (195, "mem:enemies+210", 255)] + ([(200, "b", 1), (203, "b", 0)] if weapon != 255 else [])
        ram, word, log = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", f"HERO={hero_x},144,0,{shield},{weapon},{frame},{flip}", "WORLD=1", "HUD=80,80,0,0,0"], pokes, capture, "shots_behind")
        raw = word.raw("enemies", 8 * 30)
        slot = raw[7 * 30:8 * 30]
        if enemy_x is not None:
            self.assertEqual((slot[0], slot[2], slot[4]), (0x47, enemy_x, 160), "the Zozura stands where it was put")
        hud = word.raw("hud_state", 10)
        rows = hs.decode_screen(ram, hs.video_base(log))
        camera = word("camera")
        opaque = behind.opaque_screen(rom, a, 4, True)
        expected = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]))
        self.assertEqual((word("hero_x"), word("hero_frame"), word("hero_flip")), (hero_x, frame, flip))
        pictures = self.hero_parts_at(rom, hero_x, word("hero_y"), shield, weapon, frame, flip, palettes)
        if enemy_x is not None:
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
        self.assertGreater(sum(rows[y][x] != plain[y][x] for y in range(200) for x in range(320)), least, "the pictures would be the same without the rule")
        return want_halves

    def test_both_halves_of_the_hero_and_the_left_half_of_a_zozura_are_behind_the_pillar(self) -> None:
        self.assertEqual(self.scene(184, 200), [3, 1])

    def test_the_left_half_of_the_hero_and_both_halves_of_a_zozura_are_behind_the_pillar(self) -> None:
        self.assertEqual(self.scene(200, 180), [1, 3])

    def test_the_arm_piece_the_weapon_and_the_shield_are_each_behind_by_what_is_under_their_own_place(self) -> None:
        """(hero x, he faces the way the flip bit says, the body frame 5 or 6 of an attack, shield, weapon, the VBL of the capture, B pressed at 200): in each the parts have halves of their own (the ROM works them out at
        the part's place, see the jsnes test above) and the picture is the model's."""
        seen: dict[int, set] = {}
        for args in ((150, 1, 6, 0, 1, 214), (168, 0, 6, 1, 2, 214), (192, 0, 6, 0, 1, 214), (184, 1, 6, 0, 1, 214), (160, 1, 5, 0, 0, 209)):
            hero_x, flip, frame, shield, weapon, vbl = args
            halves = self.scene(hero_x, None, shield, weapon, frame, flip, vbl, 10)
            for part, v in enumerate(halves):
                seen.setdefault(part, set()).add(v)
            self.assertGreater(len(set(halves)), 1, f"{args}: the parts are not all behind alike: {halves}")
        self.assertTrue(all(len(v) >= 3 for v in seen.values()), seen)

    def test_a_spell_is_behind_the_pillar_by_what_is_under_its_own_place(self) -> None:
        """Deluge cast through the pillar from either side (CastMagic_CalculateVisibility, worked out at the spell's place; its picture's left edge is the spell's x, see
        `test_the_attribute_bit_of_every_spell_column_follows_the_rule`): at some captures all of it is in front, at others one or both columns are behind; the picture is the model's
        (the spell's state is read from the program; a capture can fall between a pass's update and its show, so the state of the pass before is allowed as well)."""
        import behind
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
        tiles = fs.common_tiles(rom)
        opaque = behind.opaque_screen(rom, a, 4, True)
        seen, differ = set(), 0
        for hero_x, flip, vbl in ((80, 1, 206), (150, 1, 206), (150, 1, 210), (150, 1, 213), (150, 1, 216), (150, 1, 219), (230, 0, 207), (230, 0, 210), (230, 0, 213), (230, 0, 216), (230, 0, 220)):
            pokes = [(165, "w:hero_invinc", 30000), (170, "w:hero_invinc", 30000), (195, "mem:enemies+180", 255), (195, "mem:enemies+210", 255), (200, "joy", 0x81), (202, "joy", 0)]
            ram, word, log = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", f"HERO={hero_x},144,0,255,255,0,{flip}", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym MAGIC=0"], pokes, vbl, "shots_behind")
            self.assertEqual(word("spell_state"), 0, f"hero {hero_x}, VBL {vbl}: Deluge flies")
            flags, sx, sy, ic = word("spell_state+2"), word("spell_state+4"), word("spell_state+8"), word("spell_state+16")
            self.assertEqual(bool(flags & 0x40), bool(flip))
            hud = word.raw("hud_state", 10)
            rows = hs.decode_screen(ram, hs.video_base(log))
            camera = word("camera")
            for k in (0, 1, 2, 3):                                           # (this pass's state, or the ones before)
                x, counter = sx - k * (3 if flags & 0x40 else -3), ic - k
                expected = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]))
                plain = [row[:] for row in expected]
                app = fs.appearance(rom, 0x95 + ((counter >> 2) & 3), "TILEINFO_ENTITY_ADDRS")
                layers = [(hx, hy, layer) for hx, hy, layer in self.hero_parts_at(rom, hero_x, word("hero_y"), 255, 255, word("hero_frame"), flip, palettes)]
                layers.append((x, sy, fs.sprite_layer(fs.place(app, x, sy, 0x40 if flags & 0x40 else 0), tiles, palettes)))
                v = behind.halves(rom, a, 4, x, sy)
                for i, (lx, ly, layer) in enumerate(layers):
                    for target, picture in ((expected, behind.drop_behind(layer, lx, behind.halves(rom, a, 4, lx, ly), opaque)), (plain, layer)):
                        for (px, line), c in picture.items():
                            yy = line - camera
                            if sc.ST_TOP <= yy < 200 and sc.ST_LEFT <= px + sc.ST_LEFT < sc.ST_LEFT + 256:
                                target[yy][px + sc.ST_LEFT] = plan.slot[c & 0x3F]
                hx, hy = hero_x + sc.ST_LEFT, word("hero_y") + 32 - camera                # (his own picture is tested elsewhere: the box round him is left out)
                bad = [(px, py) for py in range(200) for px in range(320) if rows[py][px] != expected[py][px] and not (hx - 8 <= px < hx + 24 and hy - 8 <= py < hy + 40)]
                if not bad:
                    break
            else:
                self.fail(f"hero {hero_x}, VBL {vbl}: spell at {sx},{sy} ({flags:#x}, counter {ic}), halves {v}: {len(bad)} pixels differ, e.g. {[(px, py, rows[py][px], expected[py][px]) for px, py in bad[:5]]}")
            seen.add(v)
            differ += sum(expected[y][x] != plain[y][x] for y in range(200) for x in range(320)) > 0
        self.assertGreaterEqual(len(seen), 3, sorted(seen))
        self.assertGreaterEqual(differ, 4, "the spell is hidden by the pillar in some captures")
