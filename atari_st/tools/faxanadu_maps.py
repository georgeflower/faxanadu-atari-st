"""Faxanadu's areas, screens and blocks, decoded from the ROM with the game's own tables.

An area (Eolis, Trunk ...) is a set of screens. A screen is 16x13 blocks of 16x16 pixels (256x208). The block data of a
screen is compressed (2 control bits per block, `Area_LoadBlocks`); a block is four tiles (block lists 1 to 4, `Area_SetBlocks`).
Tiles of the area's tileset are in bank 4 and are loaded at tile $80 of the background pattern table.

Everything is read from the ROM given to `Rom`; nothing from it is stored.
"""
from __future__ import annotations

from dataclasses import dataclass

import faxanadu_rom as fr

SCREEN_COLS = 16
SCREEN_ROWS = 13
BUFFER_ROWS = 16        # the game's screen buffer is 16 rows of 16 blocks; the last rows are filled with zeros


@dataclass
class Area:
    index: int
    data_bank: int          # bank 0-2 holding the screens' block data
    bank_offset: int        # which of the bank's three area tables
    tiles_index: int        # the tileset (TILE_INDEX_TO_ADDR)
    palette_index: int
    attributes: int         # bank 3 offsets of the block tables
    lists: tuple[int, int, int, int]
    properties: int
    scrolling: int
    door_locations: int
    door_destinations: int
    screen_table: int       # offset in data_bank of the screens' pointers


def w(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def area(rom: fr.Rom, index: int) -> Area:
    data_bank = rom.byte("AREA_TO_SCREEN_DATA_BANKS", index)
    bank_offset = rom.byte("AREA_TO_BANK_OFFSET", index)
    bank = rom.prg(data_bank)
    screen_table = w(bank, 2 * bank_offset)             # pointers in a bank are the CPU address minus $8000
    b3 = rom.prg(3)
    areas_table = w(b3, 0)                              # AREAS_TABLE_PTR
    meta = w(b3, areas_table + 2 * index)               # this area's metadata table
    info = w(b3, meta + 0)                              # five words: attributes, block lists 1 to 4
    ptrs = [w(b3, info + 2 * i) for i in range(5)]
    return Area(index, data_bank, bank_offset, rom.byte("AREA_TO_TILES_INDEXES", index), rom.byte("AREA_PALETTE_INDEXES", index),
                ptrs[0], (ptrs[1], ptrs[2], ptrs[3], ptrs[4]), w(b3, meta + 2), w(b3, meta + 4), w(b3, meta + 6), w(b3, meta + 8),
                screen_table)


def screen_count(rom: fr.Rom, a: Area) -> int:
    """Screens in the area: the screen pointer table runs up to the first screen's data."""
    bank = rom.prg(a.data_bank)
    first = w(bank, a.screen_table)
    return (first - a.screen_table) // 2


def decode_screen(rom: fr.Rom, a: Area, screen: int, previous: bytes | None = None) -> bytes:
    """The 256 block ids of a screen (row by row, 16 rows of 16; the last three rows are zeros).

    Control bits, most significant first: 0 copy the block to the left, 1 the one above, 2 the one above and to the left,
    3 read the block as the next 8 bits. Offsets wrap in a 256-byte buffer; `previous` is what the buffer held before
    (the screen before), which matters only if a screen starts by copying."""
    bank = rom.prg(a.data_bank)
    start = w(bank, a.screen_table + 2 * screen)
    stream = bank[start:start + 0x400]
    buf = bytearray(previous if previous is not None else bytes(256))
    bit = 0

    def take() -> int:
        nonlocal bit
        v = (stream[bit >> 3] >> (7 - (bit & 7))) & 1
        bit += 1
        return v

    offsets = (0xFF, 0xF0, 0xEF)
    for count in range(256):
        control = (take() << 1) | take()
        if control == 3:
            value = 0
            for _ in range(8):
                value = (value << 1) | take()
        else:
            value = buf[(count + offsets[control]) & 0xFF]
        buf[count] = value
    for i in range(0xF0, 0x100):
        buf[i] = 0
    return bytes(buf)


def block_tiles(rom: fr.Rom, a: Area, block: int) -> tuple[int, int, int, int]:
    """The four tile ids of a block: (top left, top right, bottom left, bottom right)."""
    b3 = rom.prg(3)
    return tuple(b3[a.lists[i] + block] for i in range(4))  # type: ignore[return-value]


def nametable(rom: fr.Rom, a: Area, blocks: bytes) -> list[list[int]]:
    """The 32x26 tile ids of the playfield as the game writes them to the nametable (rows 4 to 29)."""
    rows = [[0] * 32 for _ in range(SCREEN_ROWS * 2)]
    for r in range(SCREEN_ROWS):
        for c in range(SCREEN_COLS):
            tl, tr, bl, br = block_tiles(rom, a, blocks[r * 16 + c])
            rows[2 * r][2 * c], rows[2 * r][2 * c + 1] = tl, tr
            rows[2 * r + 1][2 * c], rows[2 * r + 1][2 * c + 1] = bl, br
    return rows


def neighbours(rom: fr.Rom, a: Area, screen: int) -> tuple[int, int, int, int]:
    """The screens to the left, right, above and below ($FF for none): four bytes a screen in the area's scrolling data
    (`Area_LoadScrollData`)."""
    o = a.scrolling + 4 * screen
    return tuple(rom.prg(3)[o:o + 4])  # type: ignore[return-value]


BLOCK_AIR, BLOCK_SOLID, BLOCK_LADDER, BLOCK_DOOR = 0, 1, 2, 3     # property values 0-15; the rest are in the notes (AGENTS.md)


def block_properties(rom: fr.Rom, a: Area) -> bytes:
    """The property (0-15) of each of the 256 block ids. The game packs them two to a byte in RAM
    (`Area_LoadBlockProperties`: the first source byte is the low nibble, the second the high)."""
    return bytes(b & 0x0F for b in rom.prg(3)[a.properties:a.properties + 256])


@dataclass
class Door:
    screen: int
    block: int          # block position on that screen (row * 16 + column)
    destination: int    # index in the area's door destinations
    start: int          # where the hero stands on arrival: high nibble Y / 16, low nibble X / 16 (`Screen_StartPosYX`)


def doors(rom: fr.Rom, a: Area) -> list[Door]:
    """The door records: four bytes each, ended by $FF (`Area_SetStateFromDoorDestination`)."""
    b3 = rom.prg(3)
    out, o = [], a.door_locations
    while b3[o] != 0xFF:
        out.append(Door(*b3[o:o + 4]))
        o += 4
    return out


def door_destination(rom: fr.Rom, a: Area, door: Door) -> tuple[int, int, int, int]:
    """(screen, palette, key requirement, a fourth byte not read yet) for a door. In area 3 the index is 32 too high."""
    index = door.destination - (0x20 if a.index == 3 else 0)
    o = a.door_destinations + ((4 * index) & 0xFF)      # the game's index register is 8 bits wide: $FE and $FF wrap to records 62 and 63
    return tuple(rom.prg(3)[o:o + 4])  # type: ignore[return-value]


def edges(rom: fr.Rom, area_index: int) -> list[tuple[int, int, int, int, int]]:
    """Leaving an area at the left or right edge of a screen with no neighbour (`Player_CheckSwitchScreen_SwitchAreaHoriz`): records of
    five bytes (screen, new area, new screen, start position, palette), ended by $FF, one list a area (`AREA_TOWN_TRANSITIONS_DATA`).
    Buildings (area 4) have none of their own: there the edge leads out of the building."""
    table = rom.label("AREA_TOWN_TRANSITIONS_DATA").offset + 2 * area_index
    pointer = rom.data[table] | (rom.data[table + 1] << 8)
    b15 = rom.label("AREA_TOWN_TRANSITIONS_DATA")
    o = b15.offset - b15.addr + pointer       # the fixed bank: CPU address to file offset
    out = []
    while rom.data[o] != 0xFF:
        out.append(tuple(rom.data[o:o + 5]))
        o += 5
    return out


def building(rom: fr.Rom, index: int) -> dict:
    """What Player_EnterDoorToInside takes from the building tables: palette set, tileset, start position (Y/16 << 4 | X/16), music."""
    return dict(palette=rom.byte("BUILDING_PALETTES", index), tiles=rom.byte("BUILDING_MAYBE_TILES_INDEXES", index),
                start=rom.byte("BUILDING_START_POSITIONS", index), music=rom.byte("BUILDING_MUSIC", index))


def outside(rom: fr.Rom, region: int, which: int) -> tuple[int, int, int]:
    """A door to the outside ($FE is `which` 0, $FF 1) in a region: (key requirement, new region, new screen)."""
    y = 2 * region + which
    return rom.byte("DOOR_LOOKUP_REQUIREMENTS", y), rom.byte("MAYBE_REGION_TRANSITION_MAP", y), rom.byte("MAYBE_SCREEN_TRANSITION_MAP", y)


# the area of each region (`DOOR_OUTSIDE_REGION_INDEXES`) and its default music (`AREA_TO_MUSIC_TABLE`); palettes that change the music
# (`Palette_ARRAY_PRG15_MIRROR__e569`, `Music_ARRAY_PRG15_MIRROR__e570` in `Player_CheckHandleEnterDoor`)
def region_area(rom: fr.Rom, region: int) -> int:
    return rom.byte("DOOR_OUTSIDE_REGION_INDEXES", region)


def area_region(rom: fr.Rom, area_index: int) -> int | None:
    for r in range(6):
        if region_area(rom, r) == area_index:
            return r
    return None


def music_for(rom: fr.Rom, area_index: int, palette: int) -> int:
    for i in range(7):
        if rom.byte("Palette_ARRAY_PRG15_MIRROR__e569", i) == palette:
            return rom.byte("Music_ARRAY_PRG15_MIRROR__e570", i)
    return rom.byte("AREA_TO_MUSIC_TABLE", area_index)
