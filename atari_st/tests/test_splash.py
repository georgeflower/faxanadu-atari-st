"""The title screen, the intro and the ending: the ST data (tools/splash.py) and the sprite engines (tools/splash_model.py) against the ROM running in jsnes.

The ROM's pictures, name tables, pattern tables, palettes and sprite lists come from `tools/refnes/splashgolden.mjs` (about 7 s, cached in
build/refnes/ per ROM and script). Needs the ROM (ext/Faxanadu_Europe.nes); the comparisons with jsnes also need node and the harness' packages.
No Hatari, no 68000: a later 68000 player is tested against the same lists.
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import st_convert as sc  # noqa: E402
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
REFNES = ROOT / "tools" / "refnes"
NODE = bool(shutil.which("node") and (REFNES / "node_modules" / "jsnes").is_dir())

_cache: dict = {}


def rom():
    if "rom" not in _cache:
        import faxanadu_rom as fr
        _cache["rom"] = fr.Rom(ROM)
    return _cache["rom"]


def built():
    if "built" not in _cache:
        import splash
        _cache["built"] = splash.build_all(rom())
    return _cache["built"]


def golden() -> dict:
    """jsnes' record of the title, the intro and the outro (made once per ROM and script)."""
    if "golden" not in _cache:
        script = REFNES / "splashgolden.mjs"
        key = hashlib.sha1(ROM.read_bytes() + script.read_bytes()).hexdigest()[:12]
        path = ROOT / "build" / "refnes" / f"splash_golden_{key}.json"
        if not path.exists():
            if not (ROOT / "build" / "refnes" / "ram_labels.json").exists():
                subprocess.run(["python3", str(ROOT / "tools" / "ram_labels.py")], check=True, capture_output=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            subprocess.run(["node", "splashgolden.mjs", str(tmp)], cwd=REFNES, check=True, capture_output=True, timeout=600)
            tmp.rename(path)
        _cache["golden"] = json.loads(path.read_text())
    return _cache["golden"]


def rgb(shot: dict) -> bytes:
    return base64.b64decode(shot["rgb"])


def oam_list(flat: list[int]) -> list[tuple[int, int, int, int]]:
    return [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]


ARROW = (158, 114, 0, 52)       # the title's cursor, still in the OAM for the first frames of the intro and the outro


def real(oam: list[tuple]) -> list[tuple]:
    """What jsnes lists (without the sprites at line $EF and below, which are not on the screen) and the title's arrow left over, as a model list."""
    return [s for s in oam if s != ARROW]


def shown(sprites: list[tuple]) -> list[tuple]:
    return [s for s in sprites if s[0] < 0xEF]


def unpacked(name: str) -> tuple[dict, dict]:
    import lz
    import splash
    r = built()[name]
    parts = {"TITLE": splash.TITLE_PARTS, "INTRO": splash.INTRO_PARTS, "OUTRO": splash.OUTRO_PARTS}[name]
    words = {"TITLE": splash.TITLE_WORDS, "INTRO": splash.INTRO_WORDS, "OUTRO": splash.OUTRO_WORDS}[name]
    return splash.split_blob(lz.unpack(r.packed), parts, words)


def compare(screen: list[list[int]], palette: list[tuple], shot: bytes, nes_line_of, scene: bool = False) -> int:
    """Pixels of the ST screen (slot numbers) that differ from jsnes' picture, in the part jsnes shows (x 8-247, lines 8-231) and the ST has."""
    bad = 0
    for line in range(200):
        nl = nes_line_of(line)
        if not 8 <= nl < 232:
            continue
        for x in range(40, 280):
            o = (nl * 256 + x - 32) * 3
            want = sc.st_from_jsnes((shot[o], shot[o + 1], shot[o + 2]), scene)
            if palette[screen[line][x]] != want:
                bad += 1
    return bad


@unittest.skipUnless(ROM.exists(), "needs the ROM")
class FormatTests(unittest.TestCase):
    def test_the_files_unpack_to_what_was_made(self) -> None:
        import lz
        for name, r in built().items():
            self.assertEqual(lz.unpack(r.packed), r.blob, name)

    def test_sizes(self) -> None:
        sizes = {n: (len(r.blob), len(r.packed)) for n, r in built().items()}
        self.assertEqual({n: s[0] for n, s in sizes.items()}, {"TITLE": 9452, "INTRO": 9844, "OUTRO": 10084})
        for n, (raw, packed) in sizes.items():
            self.assertLess(packed, 8000, n)
            self.assertLess(packed, raw, n)

    def test_the_parts_follow_the_header_in_order_on_multiples_of_4(self) -> None:
        import splash
        for name, parts in (("TITLE", splash.TITLE_PARTS), ("INTRO", splash.INTRO_PARTS), ("OUTRO", splash.OUTRO_PARTS)):
            blob = built()[name].blob
            offs = [int.from_bytes(blob[4 * i:4 * i + 4], "big") for i in range(len(parts))]
            self.assertEqual(offs, sorted(offs))
            self.assertTrue(all(o % 4 == 0 and o < len(blob) for o in offs))
            self.assertEqual(len(blob) % 4, 0)

    def test_counts_and_palettes(self) -> None:
        import splash
        title, intro, outro = (unpacked(n) for n in ("TITLE", "INTRO", "OUTRO"))
        self.assertEqual((title[1]["tile_count"], intro[1]["tile_count"], outro[1]["tile_count"]), (242, 148, 124))
        self.assertEqual((intro[1]["image_count"], outro[1]["image_count"]), (68, 87))
        for parts, words in (title, intro, outro):
            self.assertEqual(len(parts["tiles"]), 32 * words["tile_count"] + (-32 * words["tile_count"]) % 4)
            self.assertEqual(len(parts["palette"]), 32)
            self.assertEqual(len(parts["map"]), 2 * 25 * 32)
            self.assertEqual((words["map_cols"], words["map_rows"], words["map_x"]), (32, 25, 32))
            n = words["tile_count"]
            cells = [int.from_bytes(parts["map"][2 * i:2 * i + 2], "big") for i in range(25 * 32)]
            self.assertTrue(all(c == splash.BLANK or c < n for c in cells))
            self.assertEqual(splash.palette_rgb(parts["palette"])[0], (0, 0, 0), "slot 0 is black")
        for name in ("INTRO", "OUTRO"):
            parts, words = unpacked(name)
            self.assertEqual((words["crop_line"], words["cutoff"]), (24, 217))
            self.assertEqual(len(parts["fade"]), 4 * 32)
            self.assertEqual(parts["fade"][96:], bytes(32), "after the fourth step everything is black")
            self.assertEqual(built()[name].extra["clashes"], [], "colours of one slot fade to different colours")
            self.assertEqual(len(parts["poses"]) >= 64, True)
            self.assertEqual(len(parts["tables"]) >= 37, True)

    def test_the_title_cursor_part(self) -> None:
        parts, _ = unpacked("TITLE")
        self.assertEqual([int.from_bytes(parts["cursor"][2 * i:2 * i + 2], "big") for i in range(4)], [84, 135, 148, 135])

    def test_only_the_poses_a_scene_uses_are_there(self) -> None:
        for name, used in (("INTRO", set(range(0, 12))), ("OUTRO", set(range(12, 32)))):
            parts, _ = unpacked(name)
            have = {f for f in range(32) if int.from_bytes(parts["poses"][2 * f:2 * f + 2], "big")}
            self.assertEqual(have, used, name)

    def test_emit_writes_the_files(self) -> None:
        import splash
        with tempfile.TemporaryDirectory() as tmp:
            sizes = splash.emit(tmp, rom())
            for name in ("TITLE", "INTRO", "OUTRO"):
                self.assertEqual((Path(tmp) / f"{name}.DAT").stat().st_size, sizes[name][1])
            text = (Path(tmp) / "splash.inc").read_text()
            self.assertIn(f".equ TITLE_SIZE, {sizes['TITLE'][0]}", text)
            self.assertIn(".equ SPLASH_SPAN,", text)
            self.assertTrue(text.isascii())

    def test_the_fade_rule(self) -> None:
        import splash_model as sm
        self.assertEqual(sm.fade([0x0F, 0x07, 0x17, 0x27, 0x30], 1), [0x0F, 0x0F, 0x07, 0x17, 0x20])
        self.assertEqual(sm.fade([0x30], 3), [0x00])
        self.assertEqual(sm.fade([0x30], 4), [0x0F])


@unittest.skipUnless(ROM.exists() and NODE, "needs the ROM, node and the jsnes harness")
class TitleTests(unittest.TestCase):
    def test_the_name_table_attributes_palettes_and_tiles_are_the_ppu_s(self) -> None:
        g = golden()["title"]
        scene = built()["TITLE"].extra["scene"]
        nt, chr_ = bytes.fromhex(g["nametable"]), bytes.fromhex(g["chr"])
        self.assertEqual(scene.nt, nt[:960])
        self.assertEqual(scene.attr, nt[960:])
        pal = bytes.fromhex(g["palette"])
        self.assertEqual([c for p in scene.bg for c in p], list(pal[:16]))
        self.assertEqual([c for p in scene.spr for c in p], list(pal[16:]))
        for t in set(scene.nt):
            if t:
                self.assertEqual(scene.bg_tiles[t], chr_[0x1000 + 16 * t:0x1000 + 16 * t + 16], f"tile {t:02X}")
        self.assertEqual(scene.spr_tiles[0x72], chr_[0x720:0x730])

    def test_the_cursor_is_where_the_rom_puts_it(self) -> None:
        g = golden()["title"]
        parts, _ = unpacked("TITLE")
        cur = [int.from_bytes(parts["cursor"][2 * i:2 * i + 2], "big") for i in range(4)]
        for oam, k in ((g["oam_start"], 0), (g["oam_continue"], 2)):
            (y, tile, attr, x), = oam
            self.assertEqual((tile, attr), (0x72, 0))
            self.assertEqual((cur[k], cur[k + 1]), (x + 32, y + 1 - 24))
        self.assertEqual((golden()["title"]["cursor_start"], golden()["title"]["cursor_continue"]), (0, 1))

    def test_the_picture_equals_jsnes_pixel_for_pixel(self) -> None:
        import splash
        parts, words = unpacked("TITLE")
        screen = splash.render_background(parts, words)
        arrow = parts["arrow"][:40]
        cx, cy = (int.from_bytes(parts["cursor"][2 * i:2 * i + 2], "big") for i in (0, 1))
        splash.draw_sprites(screen, [(cx, cy, 0)], [arrow])
        palette = splash.palette_rgb(parts["palette"])
        shot = rgb(golden()["title"])
        bad = compare(screen, palette, shot, lambda line: splash.nes_row_of_title_row(line // 8) * 8 + line % 8)
        self.assertEqual(bad, 0)
        for line in range(200):                     # outside the 256 pixels of the picture the screen is black
            self.assertEqual(set(screen[line][:32]) | set(screen[line][288:]), {0})

    def test_all_rows_of_the_nes_picture_but_one_are_on_the_st_screen(self) -> None:
        import splash
        rows = [splash.nes_row_of_title_row(r) for r in range(25)]
        self.assertEqual(rows, [r for r in range(2, 28) if r != 18])
        nt = built()["TITLE"].extra["scene"].nt
        self.assertFalse(any(nt[18 * 32:19 * 32]), "the dropped row is blank")
        self.assertFalse(any(nt[:2 * 32]) or any(nt[28 * 32:]), "rows 0-1 and 28-29 are blank")


def first_record(oams: list[list[int]], enough: int = 1) -> int:
    return next(i for i, r in enumerate(oams) if len(real(oam_list(r))) >= enough)


@unittest.skipUnless(ROM.exists() and NODE, "needs the ROM, node and the jsnes harness")
class IntroTests(unittest.TestCase):
    def test_the_scene_is_the_ppu_s(self) -> None:
        g = golden()["intro"]["vram"]
        nt, chr_ = bytes.fromhex(g["nametable"]), bytes.fromhex(g["chr"])
        scene = built()["INTRO"].extra["scene"]
        self.assertEqual((scene.nt, scene.attr), (nt[:960], nt[960:]))
        pal = bytes.fromhex(g["palette"])
        self.assertEqual([c for p in scene.bg + scene.spr for c in p], list(pal))
        for t in range(0x80, 0x100):
            self.assertEqual(scene.bg_tiles[t], chr_[0x1000 + 16 * t:0x1000 + 16 * t + 16], f"background tile {t:02X}")
        for t in range(0x90):
            self.assertEqual(scene.spr_tiles[t], chr_[16 * t:16 * t + 16], f"sprite tile {t:02X}")
        self.assertTrue(all(t >= 0x80 or t == 0 for t in set(scene.nt)))

    def test_the_sprites_equal_jsnes_in_every_frame_and_in_order(self) -> None:
        import splash_model as sm
        oams = golden()["intro"]["oam"]
        first = first_record(oams)
        data = sm.Data(rom())
        m = sm.Intro(data)
        steps, sounds, fades, done_at = 0, [], [], None
        for k in range(1, 700):
            sprites, sound, done = m.tick()
            steps += 1
            self.assertEqual(real(oam_list(oams[first + k - 1])), shown(sprites), f"pass {k}")
            if sound:
                sounds.append(k)
            if m.stage and m.stage & 7 == 0:
                fades.append(k)
            if done:
                done_at = k
                break
        self.assertEqual(done_at, 659)
        self.assertEqual(sounds, list(range(16, 433, 32)))
        self.assertEqual(len(sounds), 14)
        changes = [i for i, _ in golden()["intro"]["palette_changes"] if i > 5]
        self.assertEqual([first + k - 1 for k in fades], changes)

    def test_the_fade_is_the_palette_jsnes_shows(self) -> None:
        import splash_model as sm
        changes = golden()["intro"]["palette_changes"]
        pal = list(bytes.fromhex(changes[1][1]))
        for step, (_, hexpal) in enumerate(changes[1:], 0):
            self.assertEqual(list(bytes.fromhex(hexpal)), sm.fade(pal, step), f"step {step}")
        self.assertEqual(len(changes), 6)

    def test_the_hero_starts_the_game_where_the_rom_puts_him(self) -> None:
        s = golden()["intro"]["start_state"]
        self.assertEqual((s["x"], s["y"], s["screen"], s["area"], s["hp"], s["start_pos"]), (16, 144, 0, 0, 16, 0x91))
        self.assertEqual(rom().cpu(15, rom().label("Game_LoadFirstLevel").addr, 0x80).find(bytes([0xA9, 0x91, 0x85, 0x6C])) > 0, True)

    def test_the_poses_make_the_same_sprites_as_the_oam(self) -> None:
        import splash
        import splash_model as sm
        r = built()["INTRO"]
        parts, _ = unpacked("INTRO")
        m = sm.Intro(sm.Data(rom()))
        for k in range(1, 660):
            sprites, _, _ = m.tick()
            mine = [t for frame, x, y in m.drawn for t in splash.pose_triples(parts["poses"], frame, x, y)]
            want = []
            for (y, tile, attr, x) in sprites:
                img = r.extra["sprites"].image(tile, attr)
                if img is not None:
                    want.append((x + splash.ST_X, y + 1 - splash.CROP_LINE, img))
            self.assertEqual(mine, want, f"pass {k}")

    def test_pictures_equal_jsnes(self) -> None:
        import splash
        import splash_model as sm
        g = golden()["intro"]
        oams = g["oam"]
        first = first_record(oams)
        parts, words = unpacked("INTRO")
        bg = splash.render_background(parts, words)
        images = [parts["images"][40 * i:40 * i + 40] for i in range(words["image_count"])]
        base = splash.palette_rgb(parts["palette"])
        fades = [base] + [splash.palette_rgb(parts["fade"][32 * i:32 * i + 32]) for i in range(4)]
        changes = [i for i, _ in g["palette_changes"] if i > 5]
        poses = parts["poses"]
        m = sm.Intro(sm.Data(rom()))
        states = {}
        for k in range(1, 660):
            m.tick()
            states[first + k - 1] = list(m.drawn)
        for i, shot in sorted(g["pictures"].items(), key=lambda kv: int(kv[0])):
            i = int(i)
            screen = [row[:] for row in bg]
            triples = [t for frame, x, y in states.get(i, []) for t in splash.pose_triples(poses, frame, x, y)]
            splash.draw_sprites(screen, triples[::-1], images)
            step = sum(1 for c in changes if c <= i)
            bad = compare(screen, fades[step], rgb(shot), lambda line: line + splash.CROP_LINE, True)
            self.assertEqual(bad, 0, f"record {i} (fade step {step})")


@unittest.skipUnless(ROM.exists() and NODE, "needs the ROM, node and the jsnes harness")
class OutroTests(unittest.TestCase):
    def test_the_scene_is_the_ppu_s_and_the_tile_set_is_the_intro_s(self) -> None:
        g = golden()["outro"]["vram"]
        nt, chr_ = bytes.fromhex(g["nametable"]), bytes.fromhex(g["chr"])
        scene = built()["OUTRO"].extra["scene"]
        self.assertEqual((scene.nt, scene.attr), (nt[:960], nt[960:]))
        pal = bytes.fromhex(g["palette"])
        self.assertEqual([c for p in scene.bg + scene.spr for c in p], list(pal))
        for t in range(0x80, 0x100):
            self.assertEqual(scene.bg_tiles[t], chr_[0x1000 + 16 * t:0x1000 + 16 * t + 16], f"background tile {t:02X}")
        for t in range(0x90):
            self.assertEqual(scene.spr_tiles[t], chr_[16 * t:16 * t + 16], f"sprite tile {t:02X}")
        self.assertTrue(all(t >= 0x80 or t == 0 for t in set(scene.nt)))
        self.assertEqual(len(golden()["outro"]["palette_changes"]), 2, "the outro does not fade")

    def run_model(self):
        import splash
        import splash_model as sm
        g = golden()["outro"]
        off = first_record(g["oam"], 10)
        m = sm.Outro(sm.Data(rom()), splash.OUTRO_MUSIC_TICKS, count=(g["ic"][off] - 2) & 255)
        out = []
        while not m.done:
            loop = m.loop                                   # the loop this pass belongs to
            sprites = m.tick()
            out.append((sprites, list(m.drawn), loop))
        return off, out

    def test_the_sprites_equal_jsnes_in_every_frame_and_in_order(self) -> None:
        g = golden()["outro"]
        off, out = self.run_model()
        self.assertEqual(off, 7)
        self.assertEqual(len(out), 2571)
        for k, (sprites, _, _) in enumerate(out[:-1], 1):      # the ROM goes on to Game_Init after the last pass and never shows its sprites
            self.assertEqual(real(oam_list(g["oam"][off + k - 1])), shown(sprites), f"pass {k}")
        self.assertEqual(real(oam_list(g["oam"][off + len(out) - 1])), [], "nothing is left at the end")

    def test_the_phases_follow_the_music(self) -> None:
        import splash
        g = golden()["outro"]
        off, out = self.run_model()
        loops = [loop for _, _, loop in out]
        self.assertEqual((loops.count(1), loops.count(2), loops.count(3)), (867, splash.OUTRO_MUSIC_TICKS - 867, 240))
        silent = next(i for i, v in enumerate(g["music"]) if i > 20 and v == 0)       # the ROM's sound engine has ended song 12
        self.assertEqual(silent, off + splash.OUTRO_MUSIC_TICKS - 2)
        self.assertEqual(len(out) - splash.OUTRO_MUSIC_TICKS, 240)

    def test_hero_loop_lasts_867_passes_and_the_sizes_change_where_the_rom_does(self) -> None:
        import splash_model as sm
        m = sm.Outro(sm.Data(rom()), 2331)
        sizes, n = {}, 0
        while m.loop == 1:
            m.tick()
            n += 1
            sizes.setdefault(m.size, n)
        self.assertEqual(n, 867)
        self.assertEqual(sizes, {0: 1, 1: 256, 2: 427, 3: 555, 4: 683})

    def test_the_poses_make_the_same_sprites_as_the_oam(self) -> None:
        import splash
        r = built()["OUTRO"]
        parts, _ = unpacked("OUTRO")
        _, out = self.run_model()
        for k, (sprites, drawn, _) in enumerate(out, 1):
            if k % 3 and k > 900 and k < 2300:           # the middle is the waterfall alone, twice as often as needed
                continue
            mine = [t for frame, x, y in drawn for t in splash.pose_triples(parts["poses"], frame, x, y)]
            want = []
            for (y, tile, attr, x) in sprites:
                img = r.extra["sprites"].image(tile, attr)
                if img is not None:
                    want.append((x + splash.ST_X, y + 1 - splash.CROP_LINE, img))
            self.assertEqual(mine, want, f"pass {k}")

    def test_pictures_equal_jsnes(self) -> None:
        import splash
        g = golden()["outro"]
        parts, words = unpacked("OUTRO")
        bg = splash.render_background(parts, words)
        images = [parts["images"][40 * i:40 * i + 40] for i in range(words["image_count"])]
        palette = splash.palette_rgb(parts["palette"])
        off, out = self.run_model()
        for i, shot in sorted(g["pictures"].items(), key=lambda kv: int(kv[0])):
            i = int(i)
            screen = [row[:] for row in bg]
            drawn = out[i - off][1] if i >= off else []              # record i shows the sprites of pass i - off + 1
            triples = [t for frame, x, y in drawn for t in splash.pose_triples(parts["poses"], frame, x, y)]
            splash.draw_sprites(screen, triples[::-1], images)
            self.assertEqual(compare(screen, palette, rgb(shot), lambda line: line + splash.CROP_LINE, True), 0, f"record {i}")


if __name__ == "__main__":
    unittest.main()
