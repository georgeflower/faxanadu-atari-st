"""The hero's sprites, read from the ROM the way the game builds them.

The game does not keep the hero's pictures in one place. Three lists of tile numbers (armour, weapon, shield) say which of the
bank-8 tiles go to the sprite pattern table, and frames ("appearances", bank 7) say which of those tiles go where. This module
follows the game's own routines (`Player_LoadArmorTilesToPPU` and friends, `Player_DrawBody`, `Player_DrawWeapon`,
`Player_DrawShield`, `Sprite_Draw`) and returns what the PPU would hold: sprite tiles (by pattern-table number) and sprites
(x, y, tile, attribute) in NES terms. `tests/test_data.py` compares them with jsnes running the game.

Positions are the game's own: x is the hero's `Player_PosX_Block` (0-255 on a screen), y is `Player_PosY`; a sprite's y is the
OAM value (the line above it, with the 32-line HUD added).
"""
from __future__ import annotations

from dataclasses import dataclass

from faxanadu_rom import Rom

HUD_LINES = 32
SHIELD_FIRST_TILE = 0x30        # pattern table address $0300
WEAPON_FIRST_TILE = {0: 0x38, 1: 0x38, 2: 0x38, 3: 0x34}   # $0380, and $0340 for the Dragon Slayer
NO_ITEM = 0xFF


@dataclass(frozen=True)
class Appearance:
    """A frame: `cols` x `rows` cells, each (tile, attribute) or None (empty)."""
    cols: int
    rows: int
    off_x: int          # signed, from the hero's x
    off_y: int          # signed, from the hero's y
    pivot: int          # the x the sprite turns around when it faces left
    cells: tuple        # row by row


@dataclass(frozen=True)
class Sprite:
    x: int
    y: int              # OAM y
    tile: int
    attr: int


def _s8(v: int) -> int:
    return v - 256 if v > 127 else v


def _ptr(rom: Rom, bank: int, table_addr: int, index: int) -> int:
    """The CPU address a `bank_offset_16` entry points at (the table's entries are the address minus $8000)."""
    raw = rom.cpu(bank, table_addr + 2 * index, 2)
    return 0x8000 + (raw[0] | (raw[1] << 8))


def appearance(rom: Rom, index: int) -> Appearance:
    """Frame `index` of `TILEINFO_PLAYER_ADDRS` (bank 7). The header is four bytes (rows-1 and columns-1 in the two nibbles,
    x offset, y offset, pivot), then the cells; an empty cell is the single byte $FF, any other is a tile number and an attribute."""
    addr = _ptr(rom, 7, rom.label("TILEINFO_PLAYER_ADDRS").addr, index)
    head = rom.cpu(7, addr, 4)
    rows, cols = (head[0] >> 4) + 1, (head[0] & 15) + 1
    body = rom.cpu(7, addr + 4, 2 * rows * cols)
    cells, pos = [], 0
    for _ in range(rows * cols):
        if body[pos] == 0xFF:
            cells.append(None)
            pos += 1
        else:
            cells.append((body[pos], body[pos + 1]))
            pos += 2
    return Appearance(cols, rows, _s8(head[1]), _s8(head[2]), head[3], tuple(cells))


def place(app: Appearance, x: int, y: int, flip: int, tile_base: int = 0, scroll_x: int = 0) -> list[Sprite]:
    """The sprites `Sprite_Draw` writes for a frame at hero position (x, y). `flip` is the flip mask ($40 = faces left, $80 = upside down)."""
    out = []
    norm_x = (x + app.off_x) & 0xFFFF
    norm_y = y + app.off_y + HUD_LINES
    facing_left = bool(flip & 0x40)
    if facing_left:
        norm_x += 2 * app.pivot - 8 * app.cols
    norm_x -= scroll_x
    for i, cell in enumerate(app.cells):
        if cell is None:
            continue
        row, col = divmod(i, app.cols)
        tx = (app.cols - 1 - col) if facing_left else col
        sx = norm_x + 8 * tx
        sy = norm_y + 8 * row
        if not (0 <= sx < 256 and 0 <= sy < 256):
            continue            # the game skips what does not fit a byte
        out.append(Sprite(sx, sy, (cell[0] + tile_base) & 0xFF, (cell[1] ^ (flip & 0xC0)) & 0xFF))
    return out


# ---- the tiles -------------------------------------------------------------------------------------------------------

def _tile_list(rom: Rom, index_table: str, entry: int, count: int) -> list[int]:
    start = _ptr(rom, 8, rom.label(index_table).addr, entry)
    return list(rom.cpu(8, start, count))


def _tiles(rom: Rom, first: int, ids: list[int], base_label: str) -> dict[int, bytes]:
    base = rom.label(base_label).addr
    return {first + n: bytes(rom.cpu(8, base + 16 * tid, 16)) for n, tid in enumerate(ids)}


def armor_lookup(armor: int, shield: int) -> int:
    """`Player_ArmorLookupIndex`: armour * 2, plus 1 with a shield (not with the Battle Helmet, 3, or none, $FF)."""
    return armor * 2 + (1 if shield < 3 else 0)


def pattern_tiles(rom: Rom, armor: int, shield: int, weapon: int) -> dict[int, bytes]:
    """The sprite pattern table the game builds for this equipment: tile number -> 16 bytes (two bit planes of 8 lines)."""
    lookup = armor_lookup(armor, shield)
    count = rom.byte("PLAYER_ARMOR_TILE_COUNTS", lookup) + 1       # the game's loop runs count+1 times
    tiles = _tiles(rom, 0, _tile_list(rom, "TILES_PLAYER_ARMOR_ADDRS_INDEX", lookup, count), "TILES_ARMOR_START")
    if weapon != NO_ITEM:
        n = rom.byte("PLAYER_WEAPON_TILE_COUNTS", weapon) + 1
        tiles.update(_tiles(rom, WEAPON_FIRST_TILE[weapon], _tile_list(rom, "TILES_PLAYER_WEAPON_ADDRS_INDEX", weapon, n), "TILES_WEAPONS_START"))
    if shield < 3:
        tiles.update(_tiles(rom, SHIELD_FIRST_TILE, _tile_list(rom, "TILES_SHIELDS_ADDRS_INDEX", shield, 6), "TILES_SHIELDS_START"))
    return tiles


# ---- the frames ------------------------------------------------------------------------------------------------------

def body_frame(flags: int, tick: int, attack_frame: int, status: int = 0, joy: int = 0, climbing: bool = False) -> tuple[int, int]:
    """(frame 0-7, extra flip mask) the way `Player_GetBodySpriteFrameOffset` picks it. `flags` is `Player_Flags` (bit 0 in the air or
    crouching, bit 5 walking, bit 6 faces left, bit 7 attacking), `status` is `Player_StatusFlag`, `joy` the buttons (bit 7 = A... the
    game tests it for the crouch), `climbing` is `Player_IsClimbing`. Frames: 0-2 walking, 3 crouching or in the air, 4-6 attacking,
    7 climbing (the picture flips every 16 ticks)."""
    attack = (4, 5, 6)[min(attack_frame, 2)]
    if flags & 1:
        return (attack, 0) if flags & 0x80 else (3, 0)
    if climbing:
        return 7, (tick & 0x10) << 2
    if flags & 0x80:
        return attack, 0
    if status & 0x80 and joy & 0x80:
        return 3, 0
    if flags & 0x20:
        return (0, 1, 2, 1)[(tick >> 3) & 3], 0
    return 0, 0


def hero_sprites(rom: Rom, x: int, y: int, armor: int, shield: int, weapon: int, frame: int, facing_left: bool, flip_extra: int = 0,
                 scroll_x: int = 0, attacking_frame: int = -1) -> list[Sprite]:
    """Body, then the weapon, then the shield, as the game draws them (`Player_DrawBody`, `Player_DrawWeapon`, `Player_DrawShield`)."""
    flip = (0x40 if facing_left else 0) | flip_extra
    # the body: armour * 16 + shield * 8 for the combination, plus the frame (Battle Suit uses the same frames with or without a shield)
    offs = [rom.byte("PLAYER_BODY_TILEINFO_START_OFFSETS", i) for i in range(8)]
    combo = armor * 2 + (1 if shield < 3 else 0)
    sprites = place(appearance(rom, offs[combo] + frame), x, y, flip, 0, scroll_x)
    if attacking_frame == 2:
        sprites += _attack_arm_sprites(rom, x, y, armor, shield, facing_left, scroll_x)
    if weapon != NO_ITEM:
        sprites += _weapon_sprites(rom, x, y, armor, shield, weapon, frame, facing_left, scroll_x)
    if shield < 3:
        sprites += _shield_sprites(rom, x, y, frame, facing_left, scroll_x)
    return sprites


def weapon_offset(rom, armor, shield, weapon, frame, facing_left) -> tuple[int, int]:
    """Where `Player_DrawWeapon` puts the weapon relative to the hero: (dx signed, dy as the byte the ROM adds to y) for a body frame."""
    with_shield = armor_lookup(armor, shield) & 1
    pos_table = rom.word("PTR_ARRAY_PRG14__b89f", (weapon * 2 + with_shield) if weapon < 3 else (6 + with_shield))
    dx = rom.cpu(14, pos_table, 16)[2 * frame + (1 if facing_left else 0)]
    y_table = rom.word("PTR_ARRAY_PRG14__b90f", weapon)
    return _s8(dx), rom.cpu(14, y_table, 8)[frame]


def weapon_range(rom, weapon) -> tuple[int, int]:
    """MAYBE_WEAPON_RANGES: how far the weapon reaches (Maybe_WeaponRange_X, _Y): a dagger 8 and 4, the others 16 and 8."""
    return rom.byte("MAYBE_WEAPON_RANGES", 2 * weapon), rom.byte("MAYBE_WEAPON_RANGES", 2 * weapon + 1)


def _weapon_sprites(rom, x, y, armor, shield, weapon, frame, facing_left, scroll_x):
    dx, dy = weapon_offset(rom, armor, shield, weapon, frame, facing_left)
    wx = (x + dx) & 0xFF
    wy = (y + dy) & 0xFF
    first = WEAPON_FIRST_TILE[weapon]
    base = rom.byte("WEAPONS_SPRITE_L", weapon)
    return place(appearance(rom, base + frame), wx, wy, 0x40 if facing_left else 0, first, scroll_x)


def _shield_sprites(rom, x, y, frame, facing_left, scroll_x):
    dx = rom.byte("SHIELD_SPRITE_OFFSETS_X", 2 * frame + (1 if facing_left else 0))
    sx = (x + dx) & 0xFF
    idx = rom.byte("MAYBE_SHIELD_SPRITE_PPU_OFFSETS", frame)
    return place(appearance(rom, idx), sx, y + 8, 0x40 if facing_left else 0, SHIELD_FIRST_TILE, scroll_x)


def _attack_arm_sprites(rom, x, y, armor, shield, facing_left, scroll_x):
    """The extra piece of the body at the third frame of an attack (`FUN_PRG15_MIRROR__ec58`): one frame of the 'arm' appearances
    ($63-$6A), 8 pixels behind the hero facing right and 16 in front when he faces left."""
    dx = _s8(rom.byte("BYTE_ARRAY_PRG15_MIRROR__eca2", 1 if facing_left else 0))
    ax = x + dx
    if not 0 <= ax <= 255:
        return []
    idx = rom.byte("BYTE_ARRAY_PRG15_MIRROR__eca4", armor * 2 + (1 if shield < 3 else 0))
    return place(appearance(rom, idx), ax, y, 0x40 if facing_left else 0, 0, scroll_x)


# ---- pixels ----------------------------------------------------------------------------------------------------------

def tile_pixels(data: bytes, hflip: bool = False) -> list[list[int]]:
    """A NES tile (16 bytes) as 8x8 colour numbers 0-3."""
    rows = [[((data[y] >> (7 - x)) & 1) | (((data[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]
    return [r[::-1] for r in rows] if hflip else rows


def sprite_layer(sprites: list[Sprite], tiles: dict[int, bytes], palettes: list[list[int]]) -> dict[tuple[int, int], int]:
    """The sprites as {(x, screen line): NES colour}. Colour 0 of a tile is see-through. A sprite later in the list covers an earlier one:
    body, then weapon, then shield, the order the game draws them in. (The game's OAM order is shuffled by its slot allocation; the picture
    of jsnes agrees with this order in all equipments tried, see tests/test_sprites.py.)"""
    layer: dict[tuple[int, int], int] = {}
    for s in sprites:
        px = tile_pixels(tiles.get(s.tile, bytes(16)), bool(s.attr & 0x40))
        pal = palettes[s.attr & 3]
        for y in range(8):
            for x in range(8):
                if px[y][x]:
                    layer[(s.x + x, s.y + 1 + y)] = pal[px[y][x]]
    return layer
