"""What a kill by magic leaves (entity $14) and the Tilte explosion, against the ROM in jsnes (`tools/refnes/magickill.mjs`, `tiltehit.mjs`), and the same
pictures on the ST in Hatari.

The ROM's spell kill is `Sprite_ShowNormalEnemyDeathByMagic`: entity $14 where the sword's kill is $13. Both run the same behaviour (script op 0 with behaviour 7
or 8, `SpriteBehavior_EnemyDeath`); only the picture differs (`SpriteUpdateHandler_Effect_LightningBall20`: five pieces, see `enemy_data.death_pieces`)."""
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
EFFECT_TILES = (0x44, 0x4B, 0x4C, 0x5C)          # the common tiles the death effects use (appearances $A9 to $AC)


def run_probe(spell: int, *extra: str, env: dict | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "kill.json"
        subprocess.run(["node", "magickill.mjs", str(spell), str(out), *extra], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, env={**os.environ, **(env or {})})
        return json.loads(out.read_text())


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class DeathEffectInTheRomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def drawn(self, rec: list[dict], ent: int) -> list[tuple[int, int, int]]:
        """(frame, n, which of the two kinds of effect) for each frame of the recording whose OAM holds the effect's sprites: n (lines or pixels the pieces are
        apart) is found by trying every multiple of 4 against the sprites in OAM (all of them, and no others of the effect's tiles)."""
        import enemy_data as ed
        import faxanadu_sprites as fs

        base = self.rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", ent)
        out, last = [], None
        for r in rec:
            s = r["slot"]
            if s["ent"] not in (0x13, 0x14):
                continue
            seen = sorted((o[1], o[2], o[3] & 0xFF, o[4]) for o in r["oam"] if o[2] in EFFECT_TILES and abs(o[4] - s["x"]) < 60 and abs(o[1] - s["y"] - 32) < 60)
            if not seen or (r["counter"], seen) == last:
                continue                                        # (a frame the game did not run: the same sprites again)
            last = (r["counter"], seen)
            for n in range(0, 32, 4):
                frame = n // 4 + (8 if ent == 0x64 else 0)
                want = []
                for number, dx, dy, mirror in ed.death_pieces(ent, base, frame):
                    want += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(fs.appearance(self.rom, number, "TILEINFO_ENTITY_ADDRS"), s["x"] + dx, s["y"] + dy, mirror)]
                if sorted(want) == seen:
                    out.append((r["f"], n, s["ent"]))
                    break
            else:
                self.fail(f"frame {r['f']}: the sprites {seen} are no picture of the effect of entity {ent:#x}")
        return out

    def test_a_kill_by_magic_is_entity_14_and_looks_like_five_pieces_flying_apart(self) -> None:
        for spell in (1, 3):                                    # Thunder, Death
            rec = run_probe(spell)
            first = next(r for r in rec if r["slot"]["ent"] == 0x14)
            self.assertEqual(first["slot"]["internal"], 0x47, "it remembers what it was (for the drop)")
            frames = self.drawn(rec, 0x14)
            ns = [n for _, n, _ in frames]
            self.assertEqual(ns, [ns[0] + 8 * i for i in range(len(ns))], "the pieces move 8 further each drawn frame")
            self.assertEqual(len(frames), 4, "drawn on every other update of the effect's 8")
            self.assertIn(ns[0], (0, 4), "the first picture is made at the count 0 or 1, by the parity of the update that killed")
            ents = [r["slot"]["ent"] for r in rec]
            self.assertNotIn(0x13, ents)
            self.assertIn(1, [r["all"][5] for r in rec], "bread is left on the ninth update")

    def test_the_sword_kill_is_entity_13_with_three_pieces(self) -> None:
        rec = run_probe(1, "sword")
        self.assertIn(0x13, [r["slot"]["ent"] for r in rec])
        self.assertNotIn(0x14, [r["slot"]["ent"] for r in rec])
        import enemy_data as ed
        import faxanadu_sprites as fs

        base = self.rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", 0x13)
        got = 0
        for r in rec:
            s = r["slot"]
            seen = sorted((o[1], o[2], o[3] & 0xFF, o[4]) for o in r["oam"] if o[2] in EFFECT_TILES and abs(o[4] - s["x"]) < 60 and abs(o[1] - s["y"] - 32) < 60)
            if s["ent"] != 0x13 or not seen:
                continue
            ok = False
            for n in range(0, 32, 4):
                want = []
                for number, dx, dy, mirror in ed.death_pieces(0x13, base, n // 4):
                    want += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(fs.appearance(self.rom, number, "TILEINFO_ENTITY_ADDRS"), s["x"] + dx, s["y"] + dy, mirror)]
                ok = ok or sorted(want) == seen
            self.assertTrue(ok, f"frame {r['f']}")
            got += 1
        self.assertGreater(got, 3)

    def test_a_boss_death_in_its_steps_2_and_7_draws_the_same_five_pieces(self) -> None:
        """The probe turns the effect into entity $64 in step 2: the boss death's update handler hands that step to the lightning effect, whose first picture
        (the update after the change; the step has moved on by the time it is recorded) is $14's at count 0: five pieces, the first among them (the port left
        it out)."""
        import enemy_data as ed
        import faxanadu_sprites as fs

        rec = run_probe(1, env={"BOSS": "1"})
        at = next(i for i, r in enumerate(rec) if r["slot"]["ent"] == 0x64)
        r, s = rec[at + 1], rec[at + 1]["slot"]
        seen = sorted((o[1], o[2], o[3] & 0xFF, o[4]) for o in r["oam"] if o[2] in EFFECT_TILES and abs(o[4] - s["x"]) < 60 and abs(o[1] - s["y"] - 32) < 60)
        base = self.rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", 0x64)
        want = []
        for number, dx, dy, mirror in ed.death_pieces(0x64, base, 8):
            want += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(fs.appearance(self.rom, number, "TILEINFO_ENTITY_ADDRS"), s["x"] + dx, s["y"] + dy, mirror)]
        self.assertEqual(len(want), 20)
        self.assertEqual(sorted(want), seen)


BURST_TILES = (110, 111, 112, 113)               # the tiles of the Tilte explosion (appearances $A5 to $A8)
BURST_ORDER = ((0, 0), (1, 0), (0, 1), (1, 1))   # corner k (0 top left, 1 top right, 2 bottom left, 3 bottom right): (right, bottom); appearance offsets 0, 2, 1, 3
BURST_APPEARANCE = (0, 2, 1, 3)


def burst_pieces(rom, x: int, y: int, counter: int) -> list[tuple[int, int, int, int]]:
    """The sprites (OAM y, tile, attribute, x) of the explosion for a counter of 1 to 15 (`CastMagic_FinishHandler_TilteAfterFirstHit`), in the order they are drawn:
    the four corners, bottom right first, each 2 * counter away from (x, y) along both axes; a corner's place is a byte."""
    import faxanadu_sprites as fs

    out = []
    for k in (3, 2, 1, 0):
        right, bottom = BURST_ORDER[k]
        px = (x + (2 * counter if right else -2 * counter)) & 255
        py = (y + (2 * counter if bottom else -2 * counter)) & 255
        out += [(sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(fs.appearance(rom, 0xA5 + BURST_APPEARANCE[k], "TILEINFO_ENTITY_ADDRS"), px, py, 0)]
    return out


def run_tilte(mode: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "tilte.json"
        subprocess.run(["node", "tiltehit.mjs", str(out), mode], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
        return json.loads(out.read_text())


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class TilteExplosionInTheRomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr

        cls.rom = fr.Rom(ROM)

    def test_tilte_that_hits_an_enemy_explodes_in_four_pieces_for_15_frames(self) -> None:
        """The enemy is hit (type 11, counter 0, no more movement), the counter counts 1 to 15 and at 16 the spell is gone; the sprites of the frame after each
        state are the four pieces 2 * counter away from the place of the hit, in both directions, as `burst_pieces` says."""
        rec = run_tilte("hit")
        types = [r["type"] for r in rec]
        first = types.index(11)
        self.assertEqual([r["counter"] for r in rec[first:first + 17]], list(range(0, 16)) + [16])
        self.assertEqual(types[first + 16], 255)
        hit = rec[first]
        self.assertEqual((rec[first - 1]["type"], rec[first - 1]["phase"]), (4, 0), "the spell was flying")
        self.assertTrue(all((r["x"], r["y"]) == (hit["x"], hit["y"]) for r in rec[first:first + 16]), "it does not move")
        self.assertEqual(hit["slots"][7][2] < 200, True, "the enemy lost hit points")
        seen = []
        for i in range(first, first + 16):
            now = sorted((o[1], o[2], o[3] & 0xFF, o[4]) for o in rec[i + 1]["oam"] if o[2] in BURST_TILES)
            c = rec[i]["counter"]
            if c == 0:
                self.assertEqual(now, [], "the frame of the hit draws the spell as it was")
                continue
            self.assertEqual(now, sorted(burst_pieces(self.rom, hit["x"], hit["y"], c)), f"counter {c}")
            seen.append(c)
        self.assertEqual(seen, list(range(1, 16)))
        self.assertEqual([o for o in rec[first + 17]["oam"] if o[2] in BURST_TILES], [], "nothing is left after the 15th")

    def test_tilte_does_not_explode_at_a_wall_or_where_its_flight_ends(self) -> None:
        """No enemy: it passes through a wall (two blocks high, in its way), the curve and the missile follow, it is cleared where it leaves the screen
        (the ROM's `CastMagic_ClearTilte`), and the explosion's tiles are never in OAM. (The disassembly's hit-wall effect, appearances 2 and 3 of the
        entity table, belongs to Deluge and Fire and is switched off.)"""
        for mode in ("miss", "wall", "left"):
            rec = run_tilte(mode)
            self.assertNotIn(11, [r["type"] for r in rec], mode)
            self.assertEqual([o for r in rec for o in r["oam"] if o[2] in BURST_TILES], [], mode)
            end = next(r for r in rec if r["type"] == 255)
            self.assertGreaterEqual(end["x"], 0xF0, "it left by the side (x $F0 or more)")
            self.assertEqual(end["phase"], 1, "the missile phase: it flew its curve to the end")


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class DeathEffectOnTheStTests(unittest.TestCase):
    """Eolis screen 4, the hero at 240 facing left with Death chosen (MAGIC=3), the second Zozura taken away, the first given one hit point and hit at VBL 317 (the
    scene was found by trying): it becomes entity $14 at update 131 and the ST draws its picture, every other update, as `enemy_data.death_pieces` says."""

    def test_the_death_effect_of_a_spell_kill_is_drawn_as_in_the_rom(self) -> None:
        import enemy_data as ed
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import faxanadu_sprites as fs
        import hatari_shot as hs
        import st_convert as sc
        from test_viewer import ViewerTests

        rom = fr.Rom(ROM)
        run_scenario = ViewerTests.run_scenario.__get__(self)
        pal = fm.area(rom, 0).palette_index
        plan = sc.plan_for_set(rom, pal)
        palettes = sc.sprite_palettes(rom, pal)
        tiles = fs.common_tiles(rom)
        base = rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", 0x14)
        seen_frames, seen_blank = set(), 0
        for vbl in (319, 320, 322, 324, 326):                          # (the picture on show at VBL v is the previous pass's: 132, 134, 136, 138 are drawn with their count 1, 3, 5, 7 at VBL 320, 322, 324, 326, and 131 is blank)
            pokes = [(100, "w:hero_invinc", 30000), (255, "mem:enemies+210", 255), (257, "hp6", 1), (261, "joy", 0x81), (263, "joy", 0)]
            ram, word, log = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", "HERO=240,144,0,255,0,0,0", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym MAGIC=3"], pokes, vbl, "shots_death_effect")
            n = word("en_counter")
            raw = word.raw("enemies", 8 * 30)
            slot = raw[6 * 30:7 * 30]
            gone = slot[0] == 255                                         # (VBL 326: pass 139 has ended the effect, the picture on show is still pass 138's, count 7)
            self.assertIn(slot[0], (0x14, 255), f"VBL {vbl}: the slot holds the magic kill's effect")
            if gone:
                slot = bytes(slot[:11]) + bytes([8]) + bytes(slot[12:])
            self.assertIn(slot[11], range(1, 9), "its count is the updates since the kill (the pass that made it is number 131 with the cast at VBL 261: the program's start-up work moves the timing, and with it whether the effect's odd or even counts are drawn)")
            hud = word.raw("hud_state", 10)
            rows = hs.decode_screen(ram, hs.video_base(log))
            camera = word("camera")
            sx, sy = slot[2], slot[4]
            for k in (n, n - 1, n + 1):                                   # (the capture can fall between a pass's update and its show)
                d2 = slot[11] + (k - n)                                   # (the count the picture of pass k has)
                expected = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]),
                                              hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))))
                if k % 2 == 0:
                    sprites = []
                    for number, dx, dy, mirror in ed.death_pieces(0x14, base, d2):
                        sprites += fs.place(fs.appearance(rom, number, "TILEINFO_ENTITY_ADDRS"), sx + dx, sy + dy, mirror)
                    for (x, line), c in fs.sprite_layer(sprites, tiles, palettes).items():
                        y = line - camera
                        if sc.ST_TOP <= y < 200 and sc.ST_LEFT <= x + sc.ST_LEFT < sc.ST_LEFT + 256:
                            expected[y][x + sc.ST_LEFT] = plan.slot[c & 0x3F]
                hx, hy = word("hero_x") + sc.ST_LEFT, word("hero_y") + 32 - word("camera")
                bad = [(px, py) for py in range(200) for px in range(320) if rows[py][px] != expected[py][px] and not (hx - 24 <= px < hx + 40 and hy - 8 <= py < hy + 40)]
                if not bad:
                    if k % 2 == 0:
                        seen_frames.add(d2)
                    else:
                        seen_blank += 1
                    break
            else:
                self.fail(f"VBL {vbl}, pass {n}, count {slot[11]}: {len(bad)} pixels differ, e.g. {[(px, py, rows[py][px], expected[py][px]) for px, py in bad[:5]]}")
        self.assertEqual(sorted(seen_frames), [1, 3, 5, 7], "the four pictures")
        self.assertGreaterEqual(seen_blank, 1, "and not drawn in between")


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class TilteExplosionOnTheStTests(unittest.TestCase):
    """Eolis screen 4 as in `ViewerTests.magic_fight` (the hero at 85 facing right, Tilte chosen, cast at VBL 398 at the Zozura in slot 6, the hour glass holding the
    enemies still): the spell hits at about VBL 403 and the explosion follows for 15 updates; its counter is the VBL less 403."""

    def test_the_explosion_is_drawn_where_and_as_the_rom_does(self) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import faxanadu_sprites as fs
        import hatari_shot as hs
        import st_convert as sc
        from test_viewer import ViewerTests

        rom = fr.Rom(ROM)
        run_scenario = ViewerTests.run_scenario.__get__(self)
        pal = fm.area(rom, 0).palette_index
        plan = sc.plan_for_set(rom, pal)
        palettes = sc.sprite_palettes(rom, pal)
        tiles = fs.common_tiles(rom)
        seen = set()
        for vbl in (404, 407, 411, 415, 418, 421):
            pokes = [(395, "hp6", 200), (285, "w:hourglass", 60), (285, "w:hero_invinc", 30000), (398, "joy", 0x81), (400, "joy", 0)]
            ram, word, log = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", "HERO=85,144,0,255,0,0,1", "WORLD=1", "HUD=80,80,0,0,0", "VIEWER_DEFS=--defsym MAGIC=4"], pokes, vbl, "shots_burst")
            kind, sx, sy, counter = word("spell_state"), word("spell_state+4"), word("spell_state+8"), word("spell_state+12")
            hud = word.raw("hud_state", 10)
            rows = hs.decode_screen(ram, hs.video_base(log))
            camera = word("camera")
            raw = word.raw("enemies", 8 * 30)
            skip = [(word("hero_x") + sc.ST_LEFT - 24, word("hero_y") + 32 - camera - 8, 64, 48)]                      # his own picture is tested elsewhere
            skip += [(raw[i * 30 + 2] + sc.ST_LEFT - 8, raw[i * 30 + 4] + 32 - camera - 8, 32, 32) for i in range(8) if raw[i * 30] != 255]          # and the enemies'
            candidates = [counter, counter - 1, counter + 1] if kind == 11 else [None]                               # (a capture can fall between a pass's update and its show)
            for c in candidates:
                expected = sc.expected_screen(rom, 0, 4, camera, state=dict(hp=hud[0], mp=hud[1], experience=int.from_bytes(hud[2:4], "big"), gold=int.from_bytes(hud[4:8], "big"), seconds=hud[8]),
                                              hero=sc.Hero(word("hero_x"), word("hero_y"), 0, 255, 0, word("hero_frame"), bool(word("hero_flip"))))
                if c is not None and 1 <= c <= 15:
                    sprites = [fs.Sprite(x, y, t, a) for y, t, a, x in burst_pieces(rom, sx, sy, c)]
                    for (x, line), col in fs.sprite_layer(sprites, tiles, palettes).items():
                        y = line - camera
                        if sc.ST_TOP <= y < 200 and sc.ST_LEFT <= x + sc.ST_LEFT < sc.ST_LEFT + 256:
                            expected[y][x + sc.ST_LEFT] = plan.slot[col & 0x3F]
                bad = [(px, py) for py in range(200) for px in range(320) if rows[py][px] != expected[py][px] and not any(a <= px < a + w and b <= py < b + h for a, b, w, h in skip)]
                if not bad:
                    seen.add(c if c is not None else 0)
                    break
            else:
                self.fail(f"VBL {vbl}: type {kind}, counter {counter}: {len(bad)} pixels differ, e.g. {[(px, py, rows[py][px], expected[py][px]) for px, py in bad[:5]]}")
        self.assertGreaterEqual(len(seen), 5, f"counters seen {sorted(seen)}")


def run_node(script: str, *args: str) -> str:
    return subprocess.run(["node", script, *args], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True, text=True).stdout


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class RespawnInTheRomTests(unittest.TestCase):
    """What the ROM does when the hero leaves a screen and comes back (`tools/refnes/respawnprobe.mjs`, `visitprobe.mjs`): see AGENTS.md, Enemies, respawn."""

    def test_the_whole_placement_list_is_loaded_again_with_full_hit_points(self) -> None:
        """Eolis screen 4: the second Zozura is taken away and the first hurt (1 hit point, moved, another phase); after screen 5 and back both are there as at the
        first entry (entity, row, hit points, phase, value, behaviour)."""
        out = run_node("respawnprobe.mjs", "4")
        result = json.loads(out.split("RESULT ")[1])
        self.assertTrue(result["same"])
        self.assertEqual([r for r in result["back"] if r[0] != 255], [[71, 160, 9, 1, 255, 4]] * 2)

    def test_the_visit_count_is_one_for_all_random_items_and_counts_every_entry(self) -> None:
        """Trunk screen 14, entity $50 (behaviour 50): nine entries give the counts 1, 2, 3, 0, 1, 2, 3, 0, 1 and the item (hidden while an enemy is on the screen,
        flags $50) only where the count came round to 0."""
        rows = [json.loads(line) for line in run_node("visitprobe.mjs", "9").splitlines() if line.startswith("{")]
        self.assertEqual([r["count"] for r in rows], [1, 2, 3, 0, 1, 2, 3, 0, 1])
        self.assertEqual([r["there"] for r in rows], [False, False, False, True, False, False, False, True, False])


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class RespawnOnTheStTests(unittest.TestCase):
    def test_the_enemies_of_a_screen_are_all_there_again_after_leaving_and_coming_back(self) -> None:
        """Eolis screen 4, the hero invincible at 240: the slot 7 enemy is taken away (VBL 255), the other given 1 hit point (262); he walks off the screen (VBL 260 on,
        it scrolls to screen 3) and back (VBL 480 on); at VBL 760 he is on screen 4 and both Zozuras are there with full hit points, as in the ROM."""
        import faxanadu_rom as fr
        from test_viewer import ViewerTests

        rom = fr.Rom(ROM)
        run_scenario = ViewerTests.run_scenario.__get__(self)
        pokes = [(100, "w:hero_invinc", 30000), (255, "mem:enemies+210", 255), (262, "hp6", 1), (260, "joy", 8), (480, "joy", 4), (700, "joy", 0)]
        _, word, _ = run_scenario(["ALL=1", "AREA=0", "SCREEN=4", "HERO=240,144,0,255,0,0,0", "WORLD=1", "HUD=80,80,0,0,0"], pokes, 760, "shots_respawn")
        self.assertEqual(word("cur_screen"), 4)
        raw = word.raw("enemies", 8 * 30)
        self.assertEqual([raw[i * 30] for i in range(8)], [255] * 6 + [0x47, 0x47])
        self.assertEqual([raw[i * 30 + 15] for i in (6, 7)], [rom.byte("SPRITE_ENTITIES_HP", 0x47)] * 2)
