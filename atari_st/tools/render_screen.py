#!/usr/bin/env python3
"""Draw a Faxanadu screen from the ROM's own data, with no emulator: tileset, blocks, attributes, palette.

    render_screen.py AREA SCREEN OUT.png [--rom ext/Faxanadu_Europe.nes] [--palette N] [--compare ref.ppm]

The picture is the 256x208 playfield. `--compare` takes a 256x240 PPM of the same screen from the ROM harness (`tools/refnes/refshot.mjs`, HUD in the
first 32 lines) and reports how many playfield pixels differ, leaving out sprites (`--oam`), the outer 8 pixels and the last 8 lines.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faxanadu_maps as fm  # noqa: E402
import faxanadu_rom as fr  # noqa: E402
from nes_palette import NES_RGB  # noqa: E402

# The tileset is loaded at the PPU address in TILE_INDEX_TO_PPU_ADDR_UPPER ($1800 for areas: tile $80 of the background
# pattern table at $1000; $1A00 for buildings).


BLANK_TILE = [[0] * 8 for _ in range(8)]


def decode_tile(data: bytes) -> list[list[int]]:
    """An NES tile: 16 bytes, 8 low-plane rows then 8 high-plane rows -> 8x8 colour indices 0-3."""
    return [[((data[y] >> (7 - x)) & 1) | (((data[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]


def tileset(rom: fr.Rom, tiles_index: int) -> dict[int, list[list[int]]]:
    """tile id -> pixels, for the area's tileset (bank 4)."""
    start = rom.word("TILE_INDEX_TO_ADDR", tiles_index) - 0x8000
    pages = rom.byte("TILE_INDEX_TO_NUM_CHR_PAGES", tiles_index)
    raw = rom.prg(4)[start:start + pages * 256]
    ppu_hi = rom.byte("TILE_INDEX_TO_PPU_ADDR_UPPER", tiles_index)
    first = ((ppu_hi << 8) - 0x1000) // 16
    return {first + i: decode_tile(raw[i * 16:(i + 1) * 16]) for i in range(len(raw) // 16)}


def bg_palettes(rom: fr.Rom, index: int) -> list[list[int]]:
    """Four background palettes of four NES colour numbers (PALETTE_TILES_*, bank 11, 16 bytes each)."""
    raw = rom.prg(11)[index * 16:(index + 1) * 16]
    return [list(raw[i * 4:(i + 1) * 4]) for i in range(4)]


def block_palette(attributes: bytes, block: int, row: int, col: int) -> int:
    """The attribute byte of a block holds a palette for each corner of a 2x2 group; the block's own corner is picked
    by the parity of its column and row (Area_SetBlocks_SetAttributes)."""
    corner = (col & 1) | ((row & 1) << 1)
    return (attributes[block] >> (2 * corner)) & 3


def render(rom: fr.Rom, area_index: int, screen: int, palette_index: int | None = None) -> list[list[tuple[int, int, int]]]:
    a = fm.area(rom, area_index)
    blocks = fm.decode_screen(rom, a, screen)
    tiles = tileset(rom, a.tiles_index)
    pal = bg_palettes(rom, a.palette_index if palette_index is None else palette_index)
    attrs = rom.prg(3)[a.attributes:a.attributes + 256]
    image = [[(0, 0, 0)] * 256 for _ in range(fm.SCREEN_ROWS * 16)]
    for r in range(fm.SCREEN_ROWS):
        for c in range(fm.SCREEN_COLS):
            block = blocks[r * 16 + c]
            p = pal[block_palette(attrs, block, r, c)]
            for q, tile_id in enumerate(fm.block_tiles(rom, a, block)):
                px = tiles.get(tile_id, BLANK_TILE)       # tile 0 is blank and is not part of the tileset
                ox, oy = c * 16 + (q & 1) * 8, r * 16 + (q >> 1) * 8
                for y in range(8):
                    for x in range(8):
                        image[oy + y][ox + x] = NES_RGB[p[px[y][x]] & 0x3F]
    return image


def write_png(path: Path, image: list[list[tuple[int, int, int]]]) -> None:
    raw = b"".join(b"\0" + bytes(v for px in row for v in px) for row in image)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", len(image[0]), len(image), 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def read_ppm(path: Path) -> list[list[tuple[int, int, int]]]:
    data = path.read_bytes()
    head, rest = data.split(b"255\n", 1)
    width, height = (int(v) for v in head.split()[1:3])
    return [[tuple(rest[(y * width + x) * 3:(y * width + x) * 3 + 3]) for x in range(width)] for y in range(height)]


def compare(mine: list[list[tuple[int, int, int]]], ref: list[list[tuple[int, int, int]]], oam: list[list[int]] | None = None,
            top: int = 32) -> tuple[int, tuple | None]:
    """Playfield pixels that differ from the reference picture, leaving out what a picture of the data alone cannot have:
    the sprites (8x8 boxes from `oam`), the outer 8 pixels on each side (the game blanks them), and the last 8 lines of the
    playfield (jsnes shows the NTSC window and blanks them)."""
    covered = set()
    for y, _tile, _attr, x in oam or []:
        if y >= 0xEF:
            continue
        for dy in range(8):
            for dx in range(8):
                covered.add((x + dx, y + 1 + dy - top))
    bad = [(x, y) for y in range(len(mine) - 8) for x in range(8, 248) if mine[y][x] != ref[top + y][x] and (x, y) not in covered]
    box = None
    if bad:
        box = (min(x for x, _ in bad), min(y for _, y in bad), max(x for x, _ in bad), max(y for _, y in bad))
    return len(bad), box


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("area", type=int)
    parser.add_argument("screen", type=int)
    parser.add_argument("out", type=Path)
    parser.add_argument("--rom", type=Path, default=fr.DEFAULT_ROM)
    parser.add_argument("--palette", type=int, help="PALETTE_TILES_* index (default: the area's)")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--oam", type=Path, help="the sprites of the reference picture (refshot.mjs PREFIX.oam.json)")
    args = parser.parse_args()
    image = render(fr.Rom(args.rom), args.area, args.screen, args.palette)
    write_png(args.out, image)
    print(f"wrote {args.out}")
    if args.compare:
        oam = json.loads(args.oam.read_text()) if args.oam else None
        count, box = compare(image, read_ppm(args.compare), oam)
        print(f"{count} playfield pixels differ" + (f", inside x {box[0]}-{box[2]}, y {box[1]}-{box[3]}" if box else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
