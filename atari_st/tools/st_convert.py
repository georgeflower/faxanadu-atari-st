"""NES to Atari ST: colours and tiles.

The ST shows 16 colours at once; a Faxanadu screen has four background palettes and four sprite palettes of four NES colours
each, 9 to 19 different colours after rounding to the ST's 3 bits a channel. `palette_plan` makes one 16-colour palette per palette set (the colours of the
set's background and sprite palettes, with the closest pairs merged when there are more than 16). Block images are
ST planar: a 16x16 block is 16 lines of four plane words, 128 bytes.
"""
from __future__ import annotations

from dataclasses import dataclass

import faxanadu_gfx as gfx
import faxanadu_maps as fm
import faxanadu_rom as fr
import faxanadu_sprites as fs
import render_screen as rs
from nes_palette import NES_RGB

BLOCK_BYTES = 128
NO_IMAGE = 0xFFFF


def st_rgb(nes_colour: int) -> tuple[int, int, int]:
    """A NES master colour as the ST's three bits a channel."""
    r, g, b = NES_RGB[nes_colour & 0x3F]
    return r >> 5, g >> 5, b >> 5


def st_word(rgb: tuple[int, int, int]) -> int:
    return (rgb[0] << 8) | (rgb[1] << 4) | rgb[2]


@dataclass
class PalettePlan:
    colours: list[tuple[int, int, int]]          # the 16 ST colours (r, g, b 0-7), slot 0 is black
    slot: dict[int, int]                         # NES colour number -> slot
    merged: list[tuple[int, int, int]]           # (nes colour, nes colour it was merged into, distance squared)

    def words(self) -> bytes:
        padded = self.colours + [(0, 0, 0)] * (16 - len(self.colours))
        return b"".join(st_word(c).to_bytes(2, "big") for c in padded)


def palette_set(rom: fr.Rom, index: int, sprites: str = "outside") -> tuple[list[list[int]], list[list[int]]]:
    """(four background palettes, four sprite palettes) of NES colour numbers, as the game loads them (bank 11)."""
    b11 = rom.prg(11)
    bg = [list(b11[index * 16 + 4 * i:index * 16 + 4 * i + 4]) for i in range(4)]
    base = {"outside": 0x1C0, "inside": 0x1D0}[sprites]
    sp = [list(b11[base + 4 * i:base + 4 * i + 4]) for i in range(4)]
    return bg, sp


def palette_plan(nes_colours: set[int]) -> PalettePlan:
    """One slot for each different ST colour; black first. Over 16, the two closest colours are merged until 16 are left
    (the colour that is used by fewer NES entries goes into the other)."""
    by_rgb: dict[tuple[int, int, int], list[int]] = {}
    for c in sorted(nes_colours):
        by_rgb.setdefault(st_rgb(c), []).append(c)
    black = st_rgb(0x0F)
    by_rgb.setdefault(black, [])
    merged: list[tuple[int, int, int]] = []

    def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
        return sum((x - y) ** 2 for x, y in zip(a, b))

    while len(by_rgb) > 16:
        keys = [k for k in by_rgb if k != black]
        a, b = min(((x, y) for i, x in enumerate(keys) for y in keys[i + 1:]), key=lambda p: dist(*p))
        small, big = (a, b) if len(by_rgb[a]) <= len(by_rgb[b]) else (b, a)
        merged.append((by_rgb[small][0] if by_rgb[small] else -1, by_rgb[big][0], dist(small, big)))
        by_rgb[big] += by_rgb.pop(small)
    order = [black] + sorted(k for k in by_rgb if k != black)
    slot = {c: i for i, k in enumerate(order) for c in by_rgb[k]}
    return PalettePlan(order, slot, merged)


def plan_for_set(rom: fr.Rom, index: int, sprites: str = "outside") -> PalettePlan:
    bg, sp = palette_set(rom, index, sprites)
    return palette_plan({c for row in bg + sp for c in row})


def planar_line(pixels: list[int]) -> bytes:
    """Sixteen slot numbers (0-15) as four plane words, plane 0 first, leftmost pixel in the top bit."""
    out = bytearray()
    for plane in range(4):
        word = 0
        for px in pixels:
            word = (word << 1) | ((px >> plane) & 1)
        out += word.to_bytes(2, "big")
    return bytes(out)


def block_pixels(rom: fr.Rom, a: fm.Area, tiles: dict, bg: list[list[int]], plan: PalettePlan, block: int, corner: int) -> list[list[int]]:
    """A block's 16x16 pixels as slot numbers, drawn with the palette of the given corner."""
    attr = rom.prg(3)[a.attributes + block]
    palette = bg[(attr >> (2 * corner)) & 3]
    out = [[0] * 16 for _ in range(16)]
    for q, tile_id in enumerate(fm.block_tiles(rom, a, block)):
        px = tiles.get(tile_id, rs.BLANK_TILE)
        for y in range(8):
            for x in range(8):
                out[(q >> 1) * 8 + y][(q & 1) * 8 + x] = plan.slot[palette[px[y][x]] & 0x3F]
    return out


def block_image(pixels: list[list[int]]) -> bytes:
    return b"".join(planar_line(row) for row in pixels)


def used_block_corners(rom: fr.Rom, a: fm.Area, screens: list[int] | None = None) -> list[tuple[int, int]]:
    """The (block id, corner) pairs the area's screens use (the corner is the parity of the block's column and row)."""
    used = set()
    for s in screens if screens is not None else range(fm.screen_count(rom, a)):
        blocks = fm.decode_screen(rom, a, s)
        for r in range(fm.SCREEN_ROWS):
            for c in range(fm.SCREEN_COLS):
                used.add((blocks[r * 16 + c], (c & 1) | ((r & 1) << 1)))
    return sorted(used)


def build_area_blocks(rom: fr.Rom, area_index: int, palette_index: int | None = None, screens: list[int] | None = None):
    """(plan, image table, images): `images` is the list of 128-byte block images, `table[id * 4 + corner]` the number of the
    image or NO_IMAGE."""
    a = fm.area(rom, area_index)
    pal = a.palette_index if palette_index is None else palette_index
    bg, _ = palette_set(rom, pal)
    plan = plan_for_set(rom, pal)
    tiles = rs.tileset(rom, a.tiles_index)
    table = [NO_IMAGE] * 1024
    images: list[bytes] = []
    for block, corner in used_block_corners(rom, a, screens):
        table[block * 4 + corner] = len(images)
        images.append(block_image(block_pixels(rom, a, tiles, bg, plan, block, corner)))
    return plan, table, images


def expected_window(rom: fr.Rom, area_index: int, screen: int, camera: int, lines: int, palette_index: int | None = None,
                    screens: list[int] | None = None) -> list[list[int]]:
    """What the ST should show of a screen: `lines` lines of the 208-line playfield from line `camera`, 256 pixels wide, as slot numbers."""
    a = fm.area(rom, area_index)
    pal = a.palette_index if palette_index is None else palette_index
    bg, _ = palette_set(rom, pal)
    plan = plan_for_set(rom, pal)
    tiles = rs.tileset(rom, a.tiles_index)
    blocks = fm.decode_screen(rom, a, screen)
    rows = []
    for y in range(lines):
        line = camera + y
        r, ly = line >> 4, line & 15
        row: list[int] = []
        for c in range(16):
            px = block_pixels(rom, a, tiles, bg, plan, blocks[r * 16 + c], (c & 1) | ((r & 1) << 1))
            row += px[ly]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------------------------------------- HUD
HUD_TILES_ST = 64
HUD_START = dict(hp=16, mp=0, experience=0, gold=0, seconds=0)     # the game's state at the start of a new game


def ui_palette_row(rom: fr.Rom, palette_index: int) -> int:
    """Which of the four background palettes the HUD is drawn with (`PALETTE_INDEX_TO_UI_BG_ATTRIBUTE_INDEX`, bank 11)."""
    return rom.prg(11)[0x1F0 + palette_index]


def st_tile_image(raw: bytes, palette: list[int], plan: PalettePlan) -> bytes:
    """A background tile (16 bytes) for the ST: 8 lines of four plane bytes (32 bytes), drawn with a palette of NES colours."""
    px = rs.decode_tile(raw)
    out = bytearray()
    for y in range(8):
        slots = [plan.slot[palette[v] & 0x3F] for v in px[y]]
        for plane in range(4):
            byte = 0
            for slot in slots:
                byte = (byte << 1) | ((slot >> plane) & 1)
            out.append(byte)
    return bytes(out)


def hud_tile_images(rom: fr.Rom, palette_index: int, plan: PalettePlan, hp: int, mp: int) -> bytes:
    """The HUD tiles for the ST: 8 lines of four plane bytes (32 bytes a tile), in the set's HUD palette. The 60 tiles of bank 10 are
    followed by four blank ones: the item box uses tiles $3C-$3F for the item's picture, which is blank when no item is selected."""
    bg, _ = palette_set(rom, palette_index)
    palette = bg[ui_palette_row(rom, palette_index)]
    out = b"".join(st_tile_image(raw, palette, plan) for raw in gfx.hud_tile_data(rom, hp, mp))
    return out + bytes(32 * (HUD_TILES_ST - gfx.HUD_TILE_COUNT))


def hud_partial_images(rom: fr.Rom, palette_index: int, plan: PalettePlan) -> bytes:
    """The partial bar tile for every value & 7 (8 of 32 bytes), first of the power bar, then of the magic bar (its halves swapped)."""
    bg, _ = palette_set(rom, palette_index)
    palette = bg[ui_palette_row(rom, palette_index)]
    return b"".join(st_tile_image(gfx.partial_tile(rom, v, bar), palette, plan) for bar in (0, 1) for v in range(8))


def hud_state_bytes(state: dict) -> bytes:
    """The viewer's state block: power, magic (bytes), experience (word), gold (long), seconds (byte), a pad byte."""
    return (bytes([state["hp"], state["mp"]]) + state["experience"].to_bytes(2, "big") + state["gold"].to_bytes(4, "big")
            + bytes([state["seconds"], 0]))


def hud_pixels(rom: fr.Rom, palette_index: int, plan: PalettePlan, state: dict | None = None) -> list[list[int]]:
    """The HUD's 32 lines of 256 pixels as slot numbers."""
    state = state or HUD_START
    layout = gfx.hud_layout(state["hp"], state["mp"], state["experience"], state["gold"], state["seconds"])
    bg, _ = palette_set(rom, palette_index)
    palette = bg[ui_palette_row(rom, palette_index)]
    tiles = [rs.decode_tile(t) for t in gfx.hud_tile_data(rom, state["hp"], state["mp"])]
    rows = [[0] * 256 for _ in range(32)]
    for r in range(4):
        for c in range(32):
            tile = layout[r][c]
            px = tiles[tile] if tile < len(tiles) else rs.BLANK_TILE
            for y in range(8):
                for x in range(8):
                    rows[r * 8 + y][c * 8 + x] = plan.slot[palette[px[y][x]] & 0x3F]
    return rows


# -------------------------------------------------------------------------------------------------------------------- hero
SPRITE_IMAGE_BYTES = 40     # 8 lines of: mask, plane 0, plane 1, plane 2, plane 3 (one byte each, leftmost pixel in the top bit)
ST_LEFT = 32                # the playfield's left edge on the 320-pixel screen
ST_TOP = 32                 # the first line below the HUD


@dataclass(frozen=True)
class Hero:
    """Where and how the hero stands: his position (`Player_PosX_Block`, `Player_PosY`), equipment (armour 0-3, shield 0-2 or 255,
    weapon 0-3 or 255), the frame (0-7) and which way he faces."""
    x: int = 144
    y: int = 144
    armor: int = 0
    shield: int = 255
    weapon: int = 0
    frame: int = 0
    left: bool = True

    def sprites(self, rom: fr.Rom) -> list[fs.Sprite]:
        return fs.hero_sprites(rom, self.x, self.y, self.armor, self.shield, self.weapon, self.frame, self.left)


def sprite_palettes(rom: fr.Rom, palette_index: int) -> list[list[int]]:
    return palette_set(rom, palette_index)[1]


def hero_layer(rom: fr.Rom, hero: Hero, palette_index: int, plan: PalettePlan) -> dict[tuple[int, int], int]:
    """The hero as {(ST x, ST line before the camera): slot}: x already moved to the 320-pixel screen, lines still as on the NES screen."""
    tiles = fs.pattern_tiles(rom, hero.armor, hero.shield, hero.weapon)
    layer = fs.sprite_layer(hero.sprites(rom), tiles, sprite_palettes(rom, palette_index))
    return {(x + ST_LEFT, line): plan.slot[c & 0x3F] for (x, line), c in layer.items()}


def sprite_image(raw: bytes, hflip: bool, palette: list[int], plan: PalettePlan) -> bytes:
    """One 8x8 sprite tile for the ST: 8 lines of mask and four plane bytes in the sprite palette (colour 0 is see-through)."""
    px = fs.tile_pixels(raw, hflip)
    out = bytearray()
    for row in px:
        mask, planes = 0, [0, 0, 0, 0]
        for v in row:
            mask <<= 1
            for p in range(4):
                planes[p] <<= 1
            if v:
                mask |= 1
                slot = plan.slot[palette[v] & 0x3F]
                for p in range(4):
                    planes[p] |= (slot >> p) & 1
        out += bytes([mask, *planes])
    return bytes(out)


def hero_assets(rom: fr.Rom, hero: Hero, palette_index: int, plan: PalettePlan, camera: int) -> tuple[bytes, bytes]:
    """(sprite list, images) for the viewer. The list is 6 bytes a sprite: ST x, ST line (word, signed), image number (word), ended by
    a word of -1; the images are 40 bytes each, made for each different (tile, palette, flip) the pose uses."""
    tiles = fs.pattern_tiles(rom, hero.armor, hero.shield, hero.weapon)
    palettes = sprite_palettes(rom, palette_index)
    images: list[bytes] = []
    index: dict[tuple, int] = {}
    entries = bytearray()
    for s in hero.sprites(rom):
        key = (s.tile, s.attr & 3, bool(s.attr & 0x40))
        if key not in index:
            index[key] = len(images)
            images.append(sprite_image(tiles.get(s.tile, bytes(16)), key[2], palettes[key[1]], plan))
        entries += (s.x + ST_LEFT).to_bytes(2, "big") + (s.y + 1 - camera).to_bytes(2, "big", signed=True) + index[key].to_bytes(2, "big")
    entries += b"\xff\xff"
    return bytes(entries), b"".join(images)


ANIM_BASE = 128             # the pose lists are made with the hero here, so that no sprite coordinate wraps at 8 bits


def hero_anim_assets(rom: fr.Rom, hero: Hero, palette_index: int, plan: PalettePlan) -> tuple[bytes, bytes]:
    """(poses, images) for a walking hero: six poses, pose = frame (0-2) + 3 * faces-left, with the equipment of `hero`.

    poses is a table of six words (the offset of each pose record from the start of the table), then the records: the box the pose
    covers as four signed words (x0, x1 exclusive, y0, y1 exclusive) and the sprites as (x, line, image) words, ended by -1. All
    x is relative to the hero's NES x (the ST screen's left margin is in it), y to his NES y (the one-line shift of the sprites is in
    it); the line on the screen is that y minus the camera. images are shared by the six poses."""
    tiles = fs.pattern_tiles(rom, hero.armor, hero.shield, hero.weapon)
    palettes = sprite_palettes(rom, palette_index)
    images: list[bytes] = []
    index: dict[tuple, int] = {}
    records = []
    for left in (False, True):
        for frame in range(3):
            pose = Hero(ANIM_BASE, ANIM_BASE, hero.armor, hero.shield, hero.weapon, frame, left)
            entries = []
            for sp in pose.sprites(rom):
                key = (sp.tile, sp.attr & 3, bool(sp.attr & 0x40))
                if key not in index:
                    index[key] = len(images)
                    images.append(sprite_image(tiles.get(sp.tile, bytes(16)), key[2], palettes[key[1]], plan))
                entries.append((sp.x - ANIM_BASE + ST_LEFT, sp.y + 1 - ANIM_BASE, index[key]))
            x0 = min(e[0] for e in entries)
            y0 = min(e[1] for e in entries)
            box = (x0, max(e[0] for e in entries) + 8, y0, max(e[1] for e in entries) + 8)
            record = b"".join(v.to_bytes(2, "big", signed=True) for v in box)
            for e in entries:
                record += b"".join(v.to_bytes(2, "big", signed=True) for v in e)
            records.append(record + b"\xff\xff")
    offsets, at = [], 12
    for record in records:
        offsets.append(at)
        at += len(record)
    return b"".join(o.to_bytes(2, "big") for o in offsets) + b"".join(records), b"".join(images)


def expected_screen(rom: fr.Rom, area_index: int, screen: int, camera: int, palette_index: int | None = None,
                    state: dict | None = None, hero: Hero | None = None) -> list[list[int]]:
    """The whole 320x200 ST screen as slot numbers: the HUD in lines 0-31, then the playfield window of 168 lines, both 256 wide
    and 32 pixels from the left."""
    a = fm.area(rom, area_index)
    pal = a.palette_index if palette_index is None else palette_index
    plan = plan_for_set(rom, pal)
    hud = hud_pixels(rom, pal, plan, state)
    window = expected_window(rom, area_index, screen, camera, 168, palette_index)
    out = [[0] * 320 for _ in range(200)]
    for y in range(32):
        out[y][32:288] = hud[y]
    for y in range(168):
        out[32 + y][32:288] = window[y]
    if hero is not None:
        for (x, line), slot in hero_layer(rom, hero, pal, plan).items():
            y = line - camera
            if ST_TOP <= y < 200 and 0 <= x < 320:
                out[y][x] = slot
    return out
