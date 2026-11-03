"""Tiles that are not part of an area's tileset: the HUD and letters (bank 10), decoded from the ROM."""
from __future__ import annotations

import faxanadu_rom as fr
from render_screen import decode_tile

HUD_TILE_COUNT = 0x3C      # UI_DrawHUDSprites writes 60 tiles from HUD_TILES_START to PPU $1000 (background tiles 0-59)


def hud_tiles(rom: fr.Rom) -> list[list[list[int]]]:
    """Background tiles $00-$3B: the HUD symbols, digits, bars and letters, as 8x8 colour indices 0-3."""
    raw = rom.at("HUD_TILES_START", HUD_TILE_COUNT * 16)
    return [decode_tile(raw[i * 16:(i + 1) * 16]) for i in range(HUD_TILE_COUNT)]


# ---------------------------------------------------------------------------------------------------------------- the HUD
# Rows 2 and 3 of the nametable (screen lines 16 to 31) hold the HUD; rows 0 and 1 are blank. `UI_DrawHUDSprites` lays out the
# static symbols, `UI_SetHUDBarValue` the two bars, `UI_DrawDigits*` the numbers (digit n is tile $30 + n).

BAR_WIDTH = 10
BAR_FILL = (0x08, 0x09)         # power, magic
BAR_PARTIAL = (0x0C, 0x0D)
BAR_EMPTY = 0x07
BAR_END = 0x0B
DIGIT_0 = 0x30
BAR_COL = 3                     # the bars start at column 3 (11 tiles with the end decoration)

# static tiles, (row, column) -> tile (UI_STATUS_TILES at UI_STATUS_SYMBOL_PPU_ADDR_L)
HUD_STATIC = {
    (2, 1): 0x1C, (2, 2): 0x0A,                         # "M:"
    (3, 1): 0x1F, (3, 2): 0x0A,                         # "P:"
    (2, 14): 0x14, (2, 15): 0x3A,                       # "E:"
    (3, 14): 0x16, (3, 15): 0x3A,                       # "G:"
    (2, 22): 0x23, (2, 23): 0x3A,                       # "T:"
    (2, 27): 0x2C, (2, 28): 0x3C, (2, 29): 0x3D, (2, 30): 0x2E,     # the item box
    (3, 27): 0x2D, (3, 28): 0x3E, (3, 29): 0x3F, (3, 30): 0x2F,
}


def bar_tiles(value: int, bar: int) -> list[int]:
    """The 11 tiles of a bar (bar 0 = power, 1 = magic): full tiles, one partial tile unless the bar is full, empty tiles, the end."""
    value = min(value, BAR_WIDTH * 8)
    full = value >> 3
    tiles = [BAR_FILL[bar]] * full
    if full < BAR_WIDTH:
        tiles.append(BAR_PARTIAL[bar])
        tiles += [BAR_EMPTY] * (BAR_WIDTH - full - 1)
    tiles.append(BAR_END)
    return tiles


def partial_tile(rom: fr.Rom, value: int, bar: int) -> bytes:
    """The 16 bytes the game writes into CHR RAM for the partial tile: the pattern for value & 7. The magic bar's tile has the two
    halves of the entry swapped (`UI_SetHUDBarValue`)."""
    value = min(value, BAR_WIDTH * 8)
    entry = rom.at("STATUS_BAR_PARTIAL_PPU_TILES", 16, 16 * (value & 7))
    return entry if bar == 0 else entry[8:] + entry[:8]


def digit_tiles(value: int, digits: int) -> list[int]:
    return [DIGIT_0 + int(c) for c in f"{value % 10 ** digits:0{digits}d}"]


def hud_layout(hp: int, mp: int, experience: int, gold: int, seconds: int) -> list[list[int]]:
    """The four nametable rows (32 tile ids each) of the HUD, as the game draws them (no item in the box)."""
    rows = [[0] * 32 for _ in range(4)]
    for (r, c), tile in HUD_STATIC.items():
        rows[r][c] = tile
    for r, bar, value in ((3, 0, hp), (2, 1, mp)):
        rows[r][BAR_COL:BAR_COL + BAR_WIDTH + 1] = bar_tiles(value, bar)
    rows[2][16:21] = digit_tiles(experience, 5)
    rows[2][24:26] = digit_tiles(seconds, 2)
    rows[3][16:23] = digit_tiles(gold, 7)
    return rows


def hud_tile_data(rom: fr.Rom, hp: int, mp: int) -> list[bytes]:
    """The 60 HUD background tiles as 16 bytes each, with the two bar tiles as they are for these values."""
    raw = rom.at("HUD_TILES_START", HUD_TILE_COUNT * 16)
    tiles = [raw[i * 16:(i + 1) * 16] for i in range(HUD_TILE_COUNT)]
    tiles[BAR_PARTIAL[0]] = partial_tile(rom, hp, 0)
    tiles[BAR_PARTIAL[1]] = partial_tile(rom, mp, 1)
    return tiles
