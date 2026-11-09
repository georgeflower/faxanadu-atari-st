"""The pictures of the items for the player menu and the HUD, as `items.bin` (the program carries it; it does not need TOWN.DAT).

An item picture is 2x2 background tiles. The tiles and the lists of four tile numbers are the ones `iscripts.item_pictures` makes (that is the ROM's
`ITEM_TILEMAP_INDEXES` and the three lists beside it, bank 10, tiles from `$8500`); this module only lays them out for the 68000. All numbers are big endian.

    COLOURS   28 palette sets x 4 bytes: the ST palette slot of the HUD's four colours (`iscripts.item_colours`; colour 0 first)
    PICTURES  39 x 4 bytes: the tile numbers (top left, top right, bottom left, bottom right) of the picture of item index 0 + n weapons, 4 + n armour,
              8 + n shields, 12 + n spells, 17 + n items (22 of them: the id of the HUD's selected item is n)
    MATTOCK   32 bytes: `USE_MATTOCK_BLOCK_TRANSITIONS`, four block ids for each area: the one the Mattock breaks (the first), then the three it turns into
    TILES     the tiles, 16 bytes each in the ROM's form (8 bytes of plane 0, 8 of plane 1, leftmost pixel in bit 7)

The program turns a tile into ST planes when it draws it (`item_tile` in src/menu.s), with the slots of the palette set in use.
"""
from __future__ import annotations

import faxanadu_rom as fr
import iscripts as isc

PALETTE_SETS = isc.PALETTE_SETS
COLOURS_AT = 0
PICTURES_AT = COLOURS_AT + 4 * PALETTE_SETS
MATTOCK_AT = PICTURES_AT + 4 * isc.ITEM_COUNT
TILES_AT = MATTOCK_AT + 32
FIRST = isc.ITEM_FIRST                 # (0, 4, 8, 12, 17): the picture index of the first of each category


def mattock_table(rom: fr.Rom) -> bytes:
    return bytes(rom.at("USE_MATTOCK_BLOCK_TRANSITIONS", 32))


def mattock_blocks(rom: fr.Rom, area: int) -> list[int]:
    """The block ids the Mattock puts on a screen of this area (its images are in the area's packages even when no screen uses them)."""
    return sorted(set(mattock_table(rom)[4 * area:4 * area + 4]))


def item_file(rom: fr.Rom) -> bytes:
    tiles, pictures = isc.item_pictures(rom)
    colours = b"".join(isc.item_colours(rom, s) for s in range(PALETTE_SETS))
    assert len(pictures) == isc.ITEM_COUNT
    return colours + b"".join(bytes(p) for p in pictures) + mattock_table(rom) + b"".join(tiles)


def parse(data: bytes) -> dict:
    """{"colours": [4 slots] per set, "pictures": [4 tile indexes] per item, "tiles": [16 bytes]}."""
    return {"mattock": bytes(data[MATTOCK_AT:MATTOCK_AT + 32]),
            "colours": [list(data[COLOURS_AT + 4 * i:COLOURS_AT + 4 * i + 4]) for i in range(PALETTE_SETS)],
            "pictures": [list(data[PICTURES_AT + 4 * i:PICTURES_AT + 4 * i + 4]) for i in range(isc.ITEM_COUNT)],
            "tiles": [bytes(data[TILES_AT + 16 * i:TILES_AT + 16 * i + 16]) for i in range((len(data) - TILES_AT) // 16)]}


def picture_index(item_id: int) -> int:
    """The picture index of an item id (category * 32 + number, as the ROM's lists hold them)."""
    return FIRST[item_id >> 5] + (item_id & 31)


def st_tiles(rom: fr.Rom, item_index: int, palette_set: int) -> list[bytes]:
    """The four ST tiles (32 bytes: 8 lines of four plane bytes) of a picture in a palette set's HUD colours: what the 68000 has to draw."""
    import st_convert as sc

    tiles, pictures = isc.item_pictures(rom)
    plan = sc.plan_for_set(rom, palette_set)
    bg, _ = sc.palette_set(rom, palette_set)
    palette = bg[sc.ui_palette_row(rom, palette_set)]
    return [sc.st_tile_image(tiles[n], palette, plan) for n in pictures[item_index]]
