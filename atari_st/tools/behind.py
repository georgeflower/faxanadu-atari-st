"""Sprites behind the background: the package part `behind`.

The ROM draws a sprite with the attribute bit "behind the background" for each of its 8-pixel columns when the block under the sprite's x + 4 (left) or x + 12 (right),
in the row of its y, has the property 4, 9 or 13 (`Player_CalculateVisibility`, `CurrentSprite_CalculateVisibility`, `CastMagic_CalculateVisibility`). The NES then shows a
sprite pixel only where the background pixel under it, whatever block it belongs to, is colour 0. On the ST the colours of the screen cannot always say which background pixels
are colour 0 (in four of the thirteen palette sets a colour that is not 0 is black, the same ST colour as colour 0), so the package holds a mask for each block a column that is behind can lie over.

Which blocks: a column that is behind has its block (a "pillar block") at (r, c); the sprite's tiles then lie over the blocks `region` gives (the biggest sprites are the death effects,
28 pixels each way from the sprite, and the enemies are up to 41 lines tall; `tests/test_behind.py` checks the numbers against the ROM's pictures). Every block id on those positions
of the package's screens gets a mask; blocks with no opaque pixel need none.

Layout: a word o (0: no pillar block in the package, nothing follows), the words dn and dp (how many masks the program makes itself, see below), 256 bytes (for each block id
0, a number k 1 to 127 for a pillar block, or -k, -1 to -128, for another block with opaque pixels), the masks, each 16 words (a row each, bit 15 the left pixel; a bit is set where
the sprite shows, i.e. the background pixel is colour 0, clear where the background is in front of it, so that the program can use a window of it as it is for the sprite's mask bytes):
the masks -m to -1, a mask that is all ones (at offset o from the start: the mask of a block position that has none), then the masks 1 to p. A mask is kept once for
all the blocks that have it.

Where the block's image in the package has the same opaque pixels (a pixel whose slot is not 0; the image is the first of the block's corners that the package has), the program
makes the mask from the image when it attaches the package (`behind_expand` in src/enemy.s): the file holds zeros there, which pack to nothing. These are the masks 1 to dp and -1 to
-dn, each made from the image of every block that has the number. The others (a block of a palette set in which a colour other than 0 is black) are in the file as they are.
"""
from __future__ import annotations

import functools

import faxanadu_maps as fm
import faxanadu_rom as fr
import render_screen as rs

BEHIND_PROPERTIES = (4, 9, 13)
ONES = b"\xff" * 32                      # the mask of a block position without a mask: the sprite is nowhere hidden
NO_IMAGE = 0xFFFF
HEADER = 6                               # o, dn, dp

# How far a tile of a sprite that is behind a pillar block can lie from it. A part of the hero, an enemy or a spell at x, y is behind the block (r, c) when
# (x + 4) & 255 or (x + 12) & 255 is in the block's columns (`halves`: that wraps, so a sprite at x 244 to 255 can be behind a block in column 0) and y in its rows; its tiles then lie at
# TILE_DX and TILE_DY from x and y at the most (the extremes over every picture a sprite can have: the death effects' pieces are 28 pixels from the sprite and the enemies are up
# to 41 lines tall; tests/test_behind.py takes them from the ROM). A tile is 8 pixels wide and high.
TILE_DX = (-28, 36)
TILE_DY = (-27, 41)


@functools.lru_cache(maxsize=None)
def region(r: int, c: int) -> tuple[tuple[int, int], ...]:
    """The block positions (row, column) that a tile of a sprite that is behind the block at (r, c) can lie over."""
    columns, rows = set(), set()
    for x in range(256):
        if (((x + 4) & 0xFF) >> 4 == c) or (((x + 12) & 0xFF) >> 4 == c):
            columns |= set(range((x + TILE_DX[0]) >> 4, ((x + TILE_DX[1] + 7) >> 4) + 1))
    for y in range(16 * r, min(16 * r + 16, 208)):
        rows |= set(range((y + TILE_DY[0]) >> 4, ((y + TILE_DY[1] + 7) >> 4) + 1))
    return tuple((rr, cc) for rr in sorted(rows) for cc in sorted(columns) if 0 <= rr < fm.SCREEN_ROWS and 0 <= cc < fm.SCREEN_COLS)


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


def mask_of(rows: list[int]) -> bytes:
    """The mask (16 words, a bit set where the sprite shows) of a block's opaque rows."""
    return b"".join((~r & 0xFFFF).to_bytes(2, "big") for r in rows)


def image_mask(image: bytes) -> bytes:
    """What `behind_expand` makes of a block image (16 lines of four plane words): a bit set where the four planes are all 0, i.e. the pixel's slot is 0."""
    out = bytearray()
    for line in range(16):
        w = 0
        for plane in range(4):
            w |= int.from_bytes(image[8 * line + 2 * plane:8 * line + 2 * plane + 2], "big")
        out += (~w & 0xFFFF).to_bytes(2, "big")
    return bytes(out)


def pillar_positions(rom: fr.Rom, a: fm.Area, screens: list[int]):
    """(screen, row, column, block) of every block of property 4, 9 or 13 on the given screens."""
    props = fm.block_properties(rom, a)
    for sid in screens:
        blocks = fm.decode_screen(rom, a, sid)
        for r in range(fm.SCREEN_ROWS):
            for c in range(fm.SCREEN_COLS):
                if props[blocks[r * 16 + c]] in BEHIND_PROPERTIES:
                    yield sid, r, c, blocks[r * 16 + c]


def behind_blocks(rom: fr.Rom, a: fm.Area, screens: list[int]) -> tuple[list[int], list[int]]:
    """(the ids of the pillar blocks the screens use, the ids of the other blocks on the positions `region` gives), each in order."""
    pillars, others = set(), set()
    for sid in screens:
        blocks = fm.decode_screen(rom, a, sid)
        for _, r, c, block in pillar_positions(rom, a, [sid]):
            pillars.add(block)
            others |= {blocks[rr * 16 + cc] for rr, cc in region(r, c)}
    return sorted(pillars), sorted(others - pillars)


def first_image(table: list[int], block: int) -> int | None:
    """The number of the image of the block's first corner that the package has (what `behind_expand` uses), or None."""
    for corner in range(4):
        if table[block * 4 + corner] != NO_IMAGE:
            return table[block * 4 + corner]
    return None


def behind_part(rom: fr.Rom, a: fm.Area, screens: list[int], tiles_index: int | None = None, table: list[int] | None = None, images: list[bytes] | None = None) -> bytes:
    """The part for a package whose block images are `images` and whose block index is `table` (`st_convert.build_area_blocks`)."""
    pillars, others = behind_blocks(rom, a, screens)
    if not pillars:
        return b"\0\0"
    tiles = rs.tileset(rom, a.tiles_index if tiles_index is None else tiles_index)
    exact = {b: mask_of(opaque_rows(rom, a, tiles, b)) for b in pillars + others}

    def made(block: int) -> bool:
        n = first_image(table, block) if table is not None else None
        return n is not None and image_mask(images[n]) == exact[block]

    def group(ids: list[int], keep_all: bool):
        """[(mask, ids, made by the program)]: the different masks of the blocks `ids`, the ones the program makes first."""
        found: dict[tuple, list[int]] = {}
        for b in ids:
            if keep_all or exact[b] != ONES:
                found.setdefault((exact[b], made(b)), []).append(b)
        return sorted(((m, bs, mk) for (m, mk), bs in found.items()), key=lambda e: not e[2])

    pos, neg = group(pillars, True), group(others, False)
    assert len(pos) <= 127 and len(neg) <= 128, (len(pos), len(neg))
    index = bytearray(256)
    for sign, groups in ((1, pos), (-1, neg)):
        for k, (_, bs, _) in enumerate(groups, 1):
            for b in bs:
                index[b] = sign * k & 0xFF
    slots = b"".join(m if not mk else bytes(32) for m, _, mk in reversed(neg)) + ONES + b"".join(m if not mk else bytes(32) for m, _, mk in pos)
    ones_at = HEADER + 256 + 32 * len(neg)
    dn, dp = sum(e[2] for e in neg), sum(e[2] for e in pos)
    return ones_at.to_bytes(2, "big") + dn.to_bytes(2, "big") + dp.to_bytes(2, "big") + bytes(index) + slots


def expand(part: bytes, table: list[int], images: list[bytes]) -> bytes:
    """What `behind_expand` (src/enemy.s) makes of the part in memory."""
    if part[:2] == b"\0\0":
        return part
    out = bytearray(part)
    o, dn, dp = (int.from_bytes(part[i:i + 2], "big") for i in (0, 2, 4))
    for block in range(256):
        k = part[HEADER + block]
        k = k - 256 if k > 127 else k
        if (k > 0 and k <= dp) or (k < 0 and -k <= dn):
            out[o + 32 * k:o + 32 * k + 32] = image_mask(images[first_image(table, block)])
    return bytes(out)


def masks(part: bytes) -> dict[int, bytes]:
    """{block id: mask} of an expanded part (`expand`): the blocks that have none are not in it."""
    if part[:2] == b"\0\0":
        return {}
    o = int.from_bytes(part[:2], "big")
    out = {}
    for b in range(256):
        k = part[HEADER + b]
        k = k - 256 if k > 127 else k
        if k:
            out[b] = part[o + 32 * k:o + 32 * k + 32]
    return out


# ---- what the picture should be (tests) --------------------------------------------------------------------------------------------------

def opaque_screen(rom: fr.Rom, a: fm.Area, screen: int, tiles_index: int | None = None, only_pillars: bool = False) -> list[list[bool]]:
    """The 208 rows of 256 pixels of a screen: True where the background is not colour 0 (so a sprite behind it is hidden), every block counting, as on the NES.
    `only_pillars`: only the blocks of property 4, 9 and 13 (what the ST knew before it had the masks of the blocks around them: the tests use it to show that the
    neighbours of a pillar matter)."""
    props = fm.block_properties(rom, a)
    tiles = rs.tileset(rom, a.tiles_index if tiles_index is None else tiles_index)
    blocks = fm.decode_screen(rom, a, screen)
    out = [[False] * 256 for _ in range(208)]
    for r in range(fm.SCREEN_ROWS):
        for c in range(fm.SCREEN_COLS):
            if only_pillars and props[blocks[r * 16 + c]] not in BEHIND_PROPERTIES:
                continue
            for y, bits in enumerate(opaque_rows(rom, a, tiles, blocks[r * 16 + c])):
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
