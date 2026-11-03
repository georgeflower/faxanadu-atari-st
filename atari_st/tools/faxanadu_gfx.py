"""Tiles that are not part of an area's tileset: the HUD and letters (bank 10), decoded from the ROM."""
from __future__ import annotations

import faxanadu_rom as fr
from render_screen import decode_tile

HUD_TILE_COUNT = 0x3C      # UI_DrawHUDSprites writes 60 tiles from HUD_TILES_START to PPU $1000 (background tiles 0-59)


def hud_tiles(rom: fr.Rom) -> list[list[list[int]]]:
    """Background tiles $00-$3B: the HUD symbols, digits, bars and letters, as 8x8 colour indices 0-3."""
    raw = rom.at("HUD_TILES_START", HUD_TILE_COUNT * 16)
    return [decode_tile(raw[i * 16:(i + 1) * 16]) for i in range(HUD_TILE_COUNT)]
