#!/usr/bin/env python3
"""The title screen, the intro and the ending for the ST, from the ROM: TITLE.DAT, INTRO.DAT, OUTRO.DAT and splash.inc.

    splash.py [--rom ext/Faxanadu_Europe.nes] [--out build/generated]       (build_assets.py calls `emit(out)`)

The program reads one of the files from the disk before it needs it (unpack with tools/lz.py's format, `unpack` in src/unpack.s), shows the
scene and frees the memory before play. Nothing here is resident. All numbers are big endian.

A file is one packed block (`lz.pack`). Unpacked it is: a long offset from its start for each part (the `*_PARTS` lists below, in order), the header
words (`*_WORDS`), padded to a multiple of 4, then the parts, each on a multiple of 4.

The picture is 320x200, one 16-colour palette per file (slot 0 black, `st_convert.palette_plan` over the colours of the scene's palettes) and a 256-pixel wide
scene 32 pixels from the left (`ST_X`), like the playfield. A background is 8x8 tiles of 8 lines of four plane bytes (32 bytes; plane 0 first, leftmost pixel in
the top bit) and a map of 25 rows of 32 words: a tile number, or $FFFF for a tile of colour 0 only (the screen is cleared to slot 0 first). Tile column c of
the map is at x = 32 + 8c, row r at line 8r. A sprite image is 8 lines of a mask byte and four plane bytes (40 bytes, `st_convert.sprite_image`, the format of
`blit_tile`).

TITLE.DAT   the title: the NES screen with rows 2-27 re-laid out in the 25 rows of the ST: the NES rows 2-17 (the logo) are rows 0-15, 18 (blank) is dropped, 19-27 are
            rows 16-24, so START and CONTINUE are on row 17 and the three lines of small print on rows 20, 22 and 24, nothing else moves. The arrow (one sprite image)
            is drawn at the cursor's place: 1 line above the row of START.
INTRO.DAT   the hero walks up the road, the palette fades out. OUTRO.DAT: the ending (the hero walks away down the road, two sparkles, a waterfall). Both: the
            background as above from NES rows 3-27 (NES line 24 is ST line 0), the sprite images, the frame descriptors as "poses" and the engine's tables.
            A pose is a list of triples (x offset, line offset, image number) as words ended by $FFFF in x; the sprite is drawn at x = X + x offset (ST pixels),
            line = Y + line offset (ST lines), X and Y being the hero's (or sparkle's, or waterfall's) NES position. A triple is skipped when
            Y + line offset >= CUTOFF (the ROM draws nothing from NES line $F0 on). Poses are indexed by the ROM's frame numbers 0-31 (a word offset from the poses part, 0 =
            not used in this scene). Sprites overlap only between the hero, the sparkles and the waterfall: the ROM's OAM order is hero, sparkle 0, sparkle 1, waterfall with
            the first in front, so draw them waterfall, sparkle 1, sparkle 0, hero. The engines are `splash_model.Intro` and `Outro`; the `tables` part has what they read.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faxanadu_rom as fr  # noqa: E402
import lz  # noqa: E402
import splash_model as sm  # noqa: E402
import st_convert as sc  # noqa: E402
import render_screen as rs  # noqa: E402

ST_X = 32                       # the scene's left edge on the 320-pixel screen
ST_ROWS, MAP_COLS = 25, 32
CROP_ROW = 3                    # intro and outro: NES tile row 3 is the first row of the screen (NES line 24)
CROP_LINE = CROP_ROW * 8
CUTOFF = sm.NO_DRAW_Y + 1 - CROP_LINE          # a triple is skipped when Y + line offset >= CUTOFF (NES line $F0 = OAM y $F0 - 1 + 1)
BLANK = 0xFFFF
FADE_STEPS = 4

TITLE_NES_ROWS = range(2, 28)                   # the rows that hold something
TITLE_DROPPED_ROW = 18
INTRO_PARTS = OUTRO_PARTS = ("palette", "fade", "tiles", "map", "images", "poses", "tables")
INTRO_WORDS = OUTRO_WORDS = ("tile_count", "image_count", "map_cols", "map_rows", "map_x", "crop_line", "cutoff", "pad")
TITLE_PARTS = ("palette", "tiles", "map", "arrow", "cursor")
TITLE_WORDS = ("tile_count", "map_cols", "map_rows", "map_x")

# The `tables` part, in bytes (offsets are written to splash.inc as INTRO_T_x / OUTRO_T_x):
INTRO_TABLE = (("start", 4), ("threshold", 5), ("vx", 4), ("vy", 4), ("frame", 20))
OUTRO_TABLE = (("start", 4), ("threshold", 5), ("vx", 4), ("vy", 4), ("frame", 20), ("sparkle_frame", 8), ("sparkle_start", 8), ("waterfall", 3))


def nes_row_of_title_row(r: int) -> int:
    return r + 2 if r < TITLE_DROPPED_ROW - 2 else r + 3


# ------------------------------------------------------------------------------------------------------------ reading the ROM
@dataclass
class Scene:
    """A screen of the ROM as it is in the PPU: 30x32 name table, attributes, 4 background and 4 sprite palettes of NES colours, background tiles (id -> 16 bytes)."""
    nt: bytes
    attr: bytes
    bg: list[list[int]]
    spr: list[list[int]]
    bg_tiles: dict[int, bytes]
    spr_tiles: dict[int, bytes] = field(default_factory=dict)


def _tiles(rom: fr.Rom, bank: int, addr: int, n: int) -> list[bytes]:
    raw = rom.cpu(bank, addr, 16 * n)
    return [raw[i * 16:(i + 1) * 16] for i in range(n)]


def _quads(raw: bytes) -> list[list[int]]:
    return [list(raw[i * 4:i * 4 + 4]) for i in range(len(raw) // 4)]


# Europe: bank 12 $9E01.. holds the strings (tile ids, $20 = space, ended by 0); where they go is in StartScreen_Draw ($9E6C).
TITLE_STRINGS = ((0x9E01, 0x2288), (0x9E07, 0x2290), (0x9E10, 0x22E4), (0x9E2A, 0x2324), (0x9E44, 0x2366))


def title_scene(rom: fr.Rom) -> Scene:
    """The title as StartScreen_Draw makes it: the logo's 16x28 tiles at $2042, the strings, the attributes from bank 10 $9B60, the palettes (bank 11 $8100, bank 12 $9DF1)."""
    logo = rom.cpu(12, 0x8000, 16 * 28)                  # the name table is in bank 12 (the disassembly's START_SCREEN_LOGO_TILES label is misplaced)
    nt = bytearray(960)
    for r in range(16):
        nt[(2 + r) * 32 + 2:(2 + r) * 32 + 30] = logo[r * 28:(r + 1) * 28]
    for addr, ppu in TITLE_STRINGS:
        text = bytearray()
        while rom.cpu(12, addr + len(text), 1)[0]:
            b = rom.cpu(12, addr + len(text), 1)[0]
            text.append(0 if b == 0x20 else b)
        nt[ppu - 0x2000:ppu - 0x2000 + len(text)] = text
    tiles = {i: t for i, t in enumerate(_tiles(rom, 10, 0x8E00, 224))}          # logo -> BG tiles $00-$DF
    tiles.update({0xD6 + i: t for i, t in enumerate(_tiles(rom, 10, 0x8440, 10))})   # digits over the unused last logo tiles
    tiles.update({0xE0 + i: t for i, t in enumerate(_tiles(rom, 10, 0x8240, 27))})   # letters (A-Z, $FA = the copyright sign)
    return Scene(bytes(nt), rom.cpu(10, 0x9B60, 64), _quads(rom.cpu(11, 0x8100, 16)), _quads(rom.cpu(12, 0x9DF1, 16)), tiles,
                 {0x72: rom.cpu(8, 0x8F24, 16)})        # the arrow (common sprite tile $72)


SCENE_ADDRS = {"intro": (0xACA0, 0xA713), "outro": (0xB0A0, 0xA733)}   # name table + attributes in bank 10, palettes (16 + 16) in bank 12


def splash_scene(rom: fr.Rom, which: str) -> Scene:
    """The intro's or the outro's scene (`SplashAnimation_DrawScenery`, $A77B: the same tiles for both, 144 sprite tiles to $0000 and 128 background tiles to $1800)."""
    nt_addr, pal_addr = SCENE_ADDRS[which]
    nt = rom.cpu(10, nt_addr, 1024)
    pal = rom.cpu(12, pal_addr, 32)
    bg = {0x80 + i: t for i, t in enumerate(_tiles(rom, 10, 0xA4A0, 128))}
    spr = {i: t for i, t in enumerate(_tiles(rom, 10, 0x9BA0, 144))}
    return Scene(nt[:960], nt[960:], _quads(pal[:16]), _quads(pal[16:]), bg, spr)


def cell_palette(scene: Scene, r: int, c: int) -> list[int]:
    a = scene.attr[(r // 4) * 8 + c // 4]
    return scene.bg[(a >> (((r // 2) & 1) * 4 + ((c // 2) & 1) * 2)) & 3]


# ------------------------------------------------------------------------------------------------------------ the ST data
def _pad4(b: bytes) -> bytes:
    return b + bytes(-len(b) % 4)


def make_blob(parts: list[bytes], words: list[int]) -> bytes:
    """A long offset for each part, the header words (padded to a multiple of 4 bytes), the parts each on a multiple of 4."""
    head = 4 * len(parts) + 2 * len(words)
    head += -head % 4
    offsets, body = [], b""
    for p in parts:
        offsets.append(head + len(body))
        body += _pad4(p)
    w = b"".join(v.to_bytes(2, "big", signed=v < 0) for v in words)
    return b"".join(o.to_bytes(4, "big") for o in offsets) + w + bytes(head - 4 * len(parts) - len(w)) + body


def split_blob(blob: bytes, parts: tuple, words: tuple) -> tuple[dict[str, bytes], dict[str, int]]:
    """The reverse of `make_blob`: (parts, header words). A part ends where the next one starts (padding included), the last at the end of the blob."""
    offs = [int.from_bytes(blob[4 * i:4 * i + 4], "big") for i in range(len(parts))]
    w = {n: int.from_bytes(blob[4 * len(parts) + 2 * i:4 * len(parts) + 2 * i + 2], "big") for i, n in enumerate(words)}
    ends = offs[1:] + [len(blob)]
    return {n: blob[a:b] for n, a, b in zip(parts, offs, ends)}, w


class TilePool:
    """Different 8x8 tile images (32 bytes), a tile of colour 0 only is BLANK."""

    def __init__(self) -> None:
        self.images: list[bytes] = []
        self.index: dict[bytes, int] = {}

    def add(self, image: bytes) -> int:
        if not any(image):
            return BLANK
        if image not in self.index:
            self.index[image] = len(self.images)
            self.images.append(image)
        return self.index[image]


def _plan(*palette_sets: list[list[int]]) -> sc.PalettePlan:
    return sc.palette_plan({c & 0x3F for pals in palette_sets for p in pals for c in p})


def _backdrop_ok(scene: Scene) -> None:
    assert all(p[0] == scene.bg[0][0] for p in scene.bg), "colour 0 of the background palettes differs: the backdrop would show"


def background(scene: Scene, plan: sc.PalettePlan, rows: list[int | None]) -> tuple[list[bytes], bytes]:
    """(tile images, map of len(rows) x 32 words) of the name table rows `rows` (None = a blank row)."""
    _backdrop_ok(scene)
    pool, cells = TilePool(), []
    for nes_row in rows:
        for c in range(MAP_COLS):
            if nes_row is None:
                cells.append(BLANK)
                continue
            t = scene.nt[nes_row * 32 + c]
            raw = scene.bg_tiles.get(t)
            if raw is None:
                assert t == 0, f"tile {t:02X} at row {nes_row} col {c} is not in the tile set"
                cells.append(BLANK)
                continue
            cells.append(pool.add(sc.st_tile_image(raw, cell_palette(scene, nes_row, c), plan)))
    return pool.images, b"".join(v.to_bytes(2, "big") for v in cells)


def fade_palettes(nes_palette: list[int], plan: sc.PalettePlan) -> tuple[bytes, list[tuple]]:
    """The ST palette after each of FADE_STEPS fade steps (`splash_model.fade` on the 32 NES palette bytes): the colours of a slot are faded one by one;
    returns (4 x 32 bytes, [(step, slot, different ST colours)] for slots whose colours would fade to different ST colours: none is expected)."""
    out, clashes = b"", []
    for step in range(1, FADE_STEPS + 1):
        faded = sm.fade(nes_palette, step)
        words = []
        for slot in range(16):
            rgbs = {sc.st_rgb(f) for n, f in zip(nes_palette, faded) if (n & 0x3F) in plan.slot and plan.slot[n & 0x3F] == slot}
            if len(rgbs) > 1:
                clashes.append((step, slot, sorted(rgbs)))
            words.append(sc.st_word(sorted(rgbs)[0]) if rgbs else 0)
        out += b"".join(w.to_bytes(2, "big") for w in words)
    return out, clashes


@dataclass
class Result:
    name: str
    blob: bytes                              # unpacked
    packed: bytes
    extra: dict = field(default_factory=dict)

    @property
    def overrun(self) -> int:
        return lz.overrun(self.packed)


def build_title(rom: fr.Rom) -> Result:
    scene = title_scene(rom)
    plan = _plan(scene.bg, scene.spr[:1])
    rows = [nes_row_of_title_row(r) for r in range(ST_ROWS)]
    tiles, tmap = background(scene, plan, rows)
    arrow = sc.sprite_image(scene.spr_tiles[0x72], False, scene.spr[0], plan)
    # the cursor: sprite x, y from the ROM's OAM (StartScreen_Draw: y 158, x 52 for START and 116 for CONTINUE); line = NES line - 24 (3 rows up)
    cursor = b"".join(v.to_bytes(2, "big") for x in (52, 116) for v in (x + ST_X, 158 + 1 - 8 * 3))
    blob = make_blob([plan.words(), b"".join(tiles), tmap, arrow, cursor], [len(tiles), MAP_COLS, ST_ROWS, ST_X])
    return Result("TITLE", blob, lz.pack(blob), dict(plan=plan, tiles=tiles, scene=scene))


class SpriteSet:
    """The sprite images of a scene (different (tile, palette, flips) with something in them) and the poses of its frames."""

    def __init__(self, scene: Scene, plan: sc.PalettePlan):
        self.scene, self.plan = scene, plan
        self.images: list[bytes] = []
        self.index: dict[bytes, int] = {}

    def image(self, tile: int, attr: int) -> int | None:
        """Image number of a cell (tile, attributes), None when it is see-through."""
        assert not attr & 0x20, "a sprite behind the background: not handled"
        raw = self.scene.spr_tiles.get(tile, bytes(16))
        img = sc.sprite_image(raw, bool(attr & 0x40), self.scene.spr[attr & 3], self.plan, bool(attr & 0x80))
        if not any(img[::5]):
            return None
        if img not in self.index:
            self.index[img] = len(self.images)
            self.images.append(img)
        return self.index[img]

    def pose(self, frame: dict) -> bytes:
        out = b""
        for r, row in enumerate(frame["cells"]):
            for c, cell in enumerate(row):
                if cell is None:
                    continue
                img = self.image(*cell)
                if img is None:
                    continue
                for v in (frame["dx"] + 8 * c + ST_X, frame["dy"] + 8 * r + 1 - CROP_LINE, img):
                    out += v.to_bytes(2, "big", signed=True)
        return out + b"\xff\xff"


def build_scene(rom: fr.Rom, which: str) -> Result:
    data = sm.Data(rom)
    scene = splash_scene(rom, which)
    plan = _plan(scene.bg, scene.spr)
    nes_pal = [c for p in scene.bg + scene.spr for c in p]
    fade, clashes = fade_palettes(nes_pal, plan)
    tiles, tmap = background(scene, plan, list(range(CROP_ROW, CROP_ROW + ST_ROWS)))
    sprites = SpriteSet(scene, plan)
    if which == "intro":
        used = set(data.intro_frame)
        table = bytes([0x18, 0xFF, 0x20, 0xE0, *data.intro_th, *data.intro_vx, *data.intro_vy, *data.intro_frame])
        parts_names, words_names = INTRO_PARTS, INTRO_WORDS
    else:
        used = set(data.outro_frame) | set(data.sparkle_frame[:3]) | set(data.sparkle_frame[4:7]) | {sm.WATERFALL[0], sm.WATERFALL[0] + 1}
        sp = data.sparkles
        table = bytes([0x70, 0xAE, 0xFD, 0x01, *data.outro_th, 0xFB, *data.outro_vx, *data.outro_vy, *data.outro_frame, *data.sparkle_frame,
                       sp[0]["x"], sp[1]["x"], sp[0]["y"], sp[1]["y"], sp[0]["vx"], sp[1]["vx"], sp[0]["vy"], sp[1]["vy"], *sm.WATERFALL])
        parts_names, words_names = OUTRO_PARTS, OUTRO_WORDS
    poses = {f: sprites.pose(data.frames[f]) for f in sorted(used)}
    head, body, offsets = 64, b"", [0] * 32
    for f, p in poses.items():
        offsets[f] = head + len(body)
        body += p
    pose_part = b"".join(o.to_bytes(2, "big") for o in offsets) + body
    blob = make_blob([plan.words(), fade, b"".join(tiles), tmap, b"".join(sprites.images), pose_part, table],
                     [len(tiles), len(sprites.images), MAP_COLS, ST_ROWS, ST_X, CROP_LINE, CUTOFF, 0])
    return Result(which.upper(), blob, lz.pack(blob), dict(plan=plan, tiles=tiles, sprites=sprites, scene=scene, clashes=clashes, data=data, poses=poses))


def table_offsets(layout: tuple) -> dict[str, int]:
    out, at = {}, 0
    for name, n in layout:
        out[name] = at
        at += n
    out["size"] = at
    return out


def inc_text(results: dict[str, Result]) -> str:
    """splash.inc: the sizes (for the buffers: a file is unpacked where it lies, the packed bytes at the end of the span) and the offsets of parts, words and tables."""
    lines = ["| generated by tools/splash.py from the ROM: the title, the intro and the ending\n"]
    for name, parts, words in (("TITLE", TITLE_PARTS, TITLE_WORDS), ("INTRO", INTRO_PARTS, INTRO_WORDS), ("OUTRO", OUTRO_PARTS, OUTRO_WORDS)):
        r = results[name]
        lines.append(f"    .equ {name}_SIZE, {len(r.blob)}\n    .equ {name}_PACKED, {len(r.packed)}\n    .equ {name}_OVERRUN, {r.overrun}\n")
        lines += [f"    .equ {name}_PART_{p.upper()}, {4 * i}\n" for i, p in enumerate(parts)]
        head = 4 * len(parts)
        lines += [f"    .equ {name}_W_{w.upper()}, {head + 2 * i}\n" for i, w in enumerate(words)]
    for name, layout in (("INTRO", INTRO_TABLE), ("OUTRO", OUTRO_TABLE)):
        offs = table_offsets(layout)
        lines += [f"    .equ {name}_T_{k.upper()}, {v}\n" for k, v in offs.items()]
    span = max(max(-(-len(r.blob) // 4) * 4, -(-len(r.packed) // 4) * 4 + r.overrun + 4) for r in results.values())
    lines.append(f"    .equ SPLASH_SPAN, {span}\n    .equ SPLASH_CROP_LINE, {CROP_LINE}\n    .equ SPLASH_CUTOFF, {CUTOFF}\n    .equ SPLASH_ST_X, {ST_X}\n")
    lines.append(f"    .equ INTRO_FOOTSTEP_SFX, 0x15\n    .equ INTRO_FADE_EVERY, 8\n    .equ INTRO_END_STAGE, 0x20\n    .equ INTRO_TICKS, 659\n")
    lines.append(f"    .equ OUTRO_END_Y, {sm.OUTRO_END_Y}\n    .equ OUTRO_LOOP3_COUNT, {sm.LOOP3_START_COUNT}\n    .equ OUTRO_MUSIC_TICKS, {OUTRO_MUSIC_TICKS}\n")
    return "".join(lines)


OUTRO_MUSIC_TICKS = 2331        # loop 2 ends at this pass: Music_Current is cleared when song 12 ends, 2330 frames after it starts (see splash_model.Outro)


def build_all(rom: fr.Rom) -> dict[str, Result]:
    return {"TITLE": build_title(rom), "INTRO": build_scene(rom, "intro"), "OUTRO": build_scene(rom, "outro")}


def emit(outdir: Path | str, rom: fr.Rom | None = None) -> dict[str, tuple[int, int]]:
    """Writes TITLE.DAT, INTRO.DAT, OUTRO.DAT and splash.inc into `outdir`; returns {name: (unpacked size, packed size)}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rom = rom or fr.Rom()
    results = build_all(rom)
    for name, r in results.items():
        (outdir / f"{name}.DAT").write_bytes(r.packed)
    (outdir / "splash.inc").write_text(inc_text(results), encoding="ascii")
    return {n: (len(r.blob), len(r.packed)) for n, r in results.items()}


# ------------------------------------------------------------------------------------------------------------ a reference renderer (what the 68000 must make)
def tile_rows(image: bytes) -> list[list[int]]:
    """A 32-byte tile image as 8 lines of 8 slot numbers."""
    return [[sum(((image[y * 4 + p] >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)] for y in range(8)]


def render_background(parts: dict[str, bytes], words: dict[str, int], rows: int = ST_ROWS) -> list[list[int]]:
    """The 320x200 screen as slot numbers from the tiles and the map of a file's parts."""
    screen = [[0] * 320 for _ in range(8 * rows)]
    tiles, tmap = parts["tiles"], parts["map"]
    for r in range(words["map_rows"]):
        for c in range(words["map_cols"]):
            n = int.from_bytes(tmap[2 * (r * words["map_cols"] + c):][:2], "big")
            if n == BLANK:
                continue
            for y, line in enumerate(tile_rows(tiles[32 * n:32 * n + 32])):
                screen[r * 8 + y][words["map_x"] + 8 * c:words["map_x"] + 8 * c + 8] = line
    return screen


def sprite_rows(image: bytes) -> list[list[int | None]]:
    """A 40-byte sprite image as 8 lines of slot numbers, None where the mask is clear."""
    return [[(sum(((image[y * 5 + 1 + p] >> (7 - x)) & 1) << p for p in range(4)) if (image[y * 5] >> (7 - x)) & 1 else None) for x in range(8)] for y in range(8)]


def draw_sprites(screen: list[list[int]], sprites: list[tuple[int, int, int]], images: list[bytes]) -> None:
    """Draws (x, line, image number) in the order given, clipped to the screen (later on top)."""
    for x, line, n in sprites:
        for y, row in enumerate(sprite_rows(images[n])):
            for dx, v in enumerate(row):
                if v is not None and 0 <= line + y < len(screen) and 0 <= x + dx < 320:
                    screen[line + y][x + dx] = v


def pose_triples(poses: bytes, frame: int, X: int, Y: int) -> list[tuple[int, int, int]]:
    """What the 68000 engine makes of a pose: the triples at the position (X, Y) (NES x and y of the object), those at or past the cutoff left out."""
    off = int.from_bytes(poses[2 * frame:2 * frame + 2], "big")
    out = []
    while True:
        x = int.from_bytes(poses[off:off + 2], "big", signed=True)
        if poses[off:off + 2] == b"\xff\xff":
            return out
        line = int.from_bytes(poses[off + 2:off + 4], "big", signed=True)
        img = int.from_bytes(poses[off + 4:off + 6], "big")
        off += 6
        if Y + line < CUTOFF:
            out.append((X + x, Y + line, img))


def palette_rgb(palette: bytes) -> list[tuple[int, int, int]]:
    """The 16 ST colour words as (r, g, b) 0-7."""
    out = []
    for i in range(16):
        w = int.from_bytes(palette[2 * i:2 * i + 2], "big")
        out.append(((w >> 8) & 7, (w >> 4) & 7, w & 7))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, default=fr.DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "build" / "generated")
    args = parser.parse_args()
    if not args.rom.is_file():
        raise SystemExit(f"{args.rom} is missing: put your Faxanadu (Europe) ROM there (it is never committed)")
    sizes = emit(args.out, fr.Rom(args.rom))
    for name, (raw, packed) in sizes.items():
        print(f"{name}.DAT: {raw} bytes unpacked, {packed} packed -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
