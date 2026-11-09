"""Sprites behind the background: the package part `behind`.

The ROM draws a sprite with the attribute bit "behind the background" for each of its 8-pixel columns when the block under the sprite's x + 4 (left) or x + 12 (right),
in the row of its y, has the property 4, 9 or 13 (`Player_CalculateVisibility`, `CurrentSprite_CalculateVisibility`, `CastMagic_CalculateVisibility`). The NES then shows a
sprite pixel only where the background pixel is colour 0. On the ST the colours of the screen cannot say which background pixels are colour 0 (the palettes' colour 1
is black in most areas, the same ST colour as colour 0), so the package holds, for each such block the area's screens use, which of its 16x16 pixels are not colour 0.

Layout: a word n (0: no such block, nothing follows), 256 bytes (for each block id 0 or its number 1 to n), then n masks of 16 words (a row each, bit 15 the left pixel).
"""
from __future__ import annotations

import faxanadu_maps as fm
import faxanadu_rom as fr
import render_screen as rs

BEHIND_PROPERTIES = (4, 9, 13)


def opaque_rows(rom: fr.Rom, a: fm.Area, tiles: dict, block: int) -> list[int]:
    """The 16 rows of a block, a word each: a bit set where the pixel's colour number is not 0."""
    rows = [0] * 16
    for q, tile_id in enumerate(fm.block_tiles(rom, a, block)):
        px = tiles.get(tile_id, rs.BLANK_TILE)
        for y in range(8):
            for x in range(8):
                if px[y][x]:
                    rows[(q >> 1) * 8 + y] |= 0x8000 >> ((q & 1) * 8 + x)
    return rows


def behind_blocks(rom: fr.Rom, a: fm.Area, screens: list[int]) -> list[int]:
    """The ids of the blocks (property 4, 9 or 13) that the given screens use, in order."""
    props = fm.block_properties(rom, a)
    used = set()
    for sid in screens:
        used |= {b for b in fm.decode_screen(rom, a, sid)[:fm.SCREEN_ROWS * fm.SCREEN_COLS] if props[b] in BEHIND_PROPERTIES}
    return sorted(used)


def behind_part(rom: fr.Rom, a: fm.Area, screens: list[int], tiles_index: int | None = None) -> bytes:
    ids = behind_blocks(rom, a, screens)
    if not ids:
        return b"\0\0"
    tiles = rs.tileset(rom, a.tiles_index if tiles_index is None else tiles_index)
    index = bytearray(256)
    out = bytearray(len(ids).to_bytes(2, "big"))
    for n, b in enumerate(ids, 1):
        index[b] = n
    out += index
    for b in ids:
        out += b"".join(r.to_bytes(2, "big") for r in opaque_rows(rom, a, tiles, b))
    return bytes(out)


# ---- what the picture should be (tests) --------------------------------------------------------------------------------------------------

def opaque_screen(rom: fr.Rom, a: fm.Area, screen: int, only_behind: bool, tiles_index: int | None = None) -> list[list[bool]]:
    """The 208 rows of 256 pixels of a screen: True where the background is not colour 0 (so a sprite behind it is hidden). `only_behind`: only the blocks of
    the package part count (properties 4, 9, 13), as on the ST; otherwise every block, as on the NES."""
    props = fm.block_properties(rom, a)
    tiles = rs.tileset(rom, a.tiles_index if tiles_index is None else tiles_index)
    blocks = fm.decode_screen(rom, a, screen)
    out = [[False] * 256 for _ in range(208)]
    for r in range(fm.SCREEN_ROWS):
        for c in range(fm.SCREEN_COLS):
            b = blocks[r * 16 + c]
            if only_behind and props[b] not in BEHIND_PROPERTIES:
                continue
            for y, bits in enumerate(opaque_rows(rom, a, tiles, b)):
                for x in range(16):
                    out[r * 16 + y][c * 16 + x] = bool(bits & (0x8000 >> x))
    return out


def halves(rom: fr.Rom, a: fm.Area, screen: int, x: int, y: int) -> int:
    """`Player_CalculateVisibility` / `CurrentSprite_CalculateVisibility`: bit 0 when the block under x + 4, bit 1 when the one under x + 12 (a byte) has property 4, 9 or 13."""
    props = fm.block_properties(rom, a)
    blocks = fm.decode_screen(rom, a, screen)
    out = 0
    for bit, add in ((1, 4), (2, 12)):
        index = (y & 0xF0) | (((x + add) & 0xFF) >> 4)
        if index < 208 and props[blocks[index]] in BEHIND_PROPERTIES:
            out |= bit
    return out


def drop_behind(layer: dict, ox: int, behind: int, opaque: list[list[bool]]) -> dict:
    """A sprite layer ({(x, NES line): colour}, the sprite's x at ox) without the pixels of its columns that are behind the background (column parity counted from ox) over
    background pixels that are not colour 0."""
    out = {}
    for (x, line), c in layer.items():
        row = line - 32
        if behind & (1 << (((x - ox) >> 3) & 1)) and 0 <= row < 208 and 0 <= x < 256 and opaque[row][x]:
            continue
        out[(x, line)] = c
    return out
