"""The interaction scripts (IScripts), the messages, the portraits, the town people and the item pictures of the Europe ROM, as program data for the ST.

`build(rom)` returns three files (all numbers big endian unless a field says it is the ROM's own bytes):

iscript.bin: the script blob (bank 12 $A0E6-$A712, the ROM's bytes), a word for each of the 152 script ids (the offset of its script in the blob), all 193 messages
  ($01-$C1, bank 13 from $8300, the ROM's raw bytes with their $FF ends) and a word for each (its offset in the block), and the 39 item pictures.
  Header: word scripts (152), word messages (193), then long offsets from the file start: script offsets, blob, message offsets, messages, item pictures, item colours.
  Script offsets and message offsets are indexed from 0: script id n is word n; message id m ($01-$C1) is word m - 1. A script's offset is its pointer minus $A0E6
  (ids the game never reaches point at the intro script, offset 4). Inside the blob every jump, branch and shop-list address is the ROM's absolute bank-12 address (little
  endian, as the ROM has it): the interpreter subtracts $A0E6. The first byte of a script is its entity byte ($00 no portrait, $80 + k portrait k), then the actions up to END.
  Item pictures: word tiles, the tiles (16 bytes each, the ROM's two bit planes: 8 bytes of plane 0, 8 of plane 1, leftmost pixel in bit 7), then 39 entries of four
  tile numbers (top left, top right, bottom left, bottom right; the picture of item index = 0 + n weapons, 4 + n armour, 8 + n shields, 12 + n spells, 17 + n items; for an item id
  that is (id >> 5 category: 0, 4, 8, 12, 17) + (id & 31)). Item colours: for each building palette set (10, building type 0-9) four palette slot bytes, the HUD's four colours.

portraits.bin: the 11 portraits, in the ROM's own form but re-packed. Header: word portraits (11), word sets (10), long offset of the colour table, then 11 long offsets of
  the portrait records. Colours: per building type (palette set $11 + type) 16 bytes: the palette slot of colour c (1-3) of sprite palette p (0-3) at p * 4 + c (colour 0 is see-through: 0),
  as the portrait palette (sprite palette set 2, `PALETTE_SPRITES_PORTRAIT`) comes out in that building's palette once the 16 words of `portrait_palette` are loaded;
  then per building type the 16 palette words (32 bytes) to load while a portrait is up (the building's palette with the spare slots given the portrait's colours).
  Portrait record: word tiles (n), the n tiles (16 bytes, ROM bit-plane form; tile k is the k-th of the portrait's list), five frames: base, eyes A, eyes B, mouth A, mouth B.
  Frame: byte columns, byte rows, signed byte x, signed byte y (pixels from the portrait's top left), then columns * rows cells of two bytes: tile number ($FF empty, then the attribute 0) and
  attribute (bits 0-1 sprite palette, bit 6 mirrored left-right). Base frames are 6 x 8 cells (48 x 64 pixels). Eyes and mouth cells never lie on a cell of the base picture: they fill
  holes in it (a hole shows the box, black). Every frame is drawn at the portrait's place; f = (counter >> 3) & 3 while a message is typed, else 0: frame 0 always, eyes frame 1 + (f & 1),
  mouth frame 3 + ((f >> 1) & 1).

npc.bin: the 18 people (entities $34-$45), where they stand and the colours. Header: word kinds (18), word sets (28), then long offsets: kind records (a table of 18 longs), set colours, building
  palettes, places. Kind record: byte entity, byte frames, byte animation rule, byte mirror rule, four bytes of bounds (left signed, top, width, height: `Sprite_GetBounds` bank 14 $B273),
  word tiles (n), the n tiles (16 bytes, ROM form; tile k = the entity's tile k), then a table of 2 * frames words (offset from the record start of the pose of frame f, mirrored = 0 / 1, at 2 * f + mirrored),
  then the poses: cells of four bytes (dx, dy signed bytes: ST screen coordinates relative to the person's x and y, the playfield x plus 32 and the line plus 32 + 1; tile; attribute: bits 0-1 sprite
  palette, bit 6 mirrored) ended by dx = $80. Animation rule: 0 frame = (counter >> 4) & 1, 1 walking: (0, 1, 0, 2)[(counter >> 3) & 3] (frame 0 while the phase is 2), 2 the King: ((counter >> 4) & 1)
  + (0, 2)[phase - 1]. Mirror rule: 0 never mirrored, 1 always, 2 mirrored when the person faces right (flag bit 0). Set colours: for each of the 28 palette sets 16 bytes: the palette slot of
  colour c (1-3) of sprite palette p (0-3) at p * 4 + c, for the sprite palettes the ROM loads there (inside palettes in the building sets $11-$1A, outside elsewhere). Building palettes: for each of the 10
  building sets the 16 palette words to load while the people stand there (the building palette with the spare slots given the inside colours). Places: records of six bytes (area, screen, entity, script id,
  x, y) ended by an area of $FF, sorted by area and screen: area 4 is the buildings (screen = the building number), the screen numbers are the ROM's. Entity $4F is the intro trigger.
"""
from __future__ import annotations

import hashlib

import enemy_data as ed
import faxanadu_rom as fr
import faxanadu_sprites as fs
import faxanadu_text as ft
import st_convert as sc

SCRIPT_BANK = 12
BLOB_START, BLOB_END = 0xA0E6, 0xA712          # the script data, the last byte included
BLOB_SIZE = BLOB_END - BLOB_START + 1
SCRIPT_COUNT = 152
TABLE_L, TABLE_U = 0x9FB6, 0xA04E               # the low and the high bytes of each script's address
INTRO = 0xA0EA                                  # where the unused ids point
BLOB_SHA1 = "38aeaf4e6dea2f10b73310befbc0ca20ccb65064"

MESSAGE_BANK, MESSAGES_START, MESSAGES_END = 13, 0x8300, 0xB3BA
MESSAGE_COUNT = 193
MESSAGES_SIZE = MESSAGES_END - MESSAGES_START
MESSAGES_SHA1 = "cff9ea4974bf6f1bc32bcf729679e29ed2b42c2c"

PORTRAITS = 11
PORTRAIT_FRAMES = 5
PORTRAIT_TILE_INDEX, PORTRAIT_TILES = 0x9224, 0x936B     # bank 8: a word a portrait (the CPU address minus $8000) of its list of tile numbers; the tiles
PORTRAIT_FRAME_TABLE = 0xAFD5                            # bank 7: 55 words (the CPU address minus $8000)
PORTRAIT_NAMES = ("King", "Guru", "MartialArtist", "Magician", "Doctor", "Nurse", "PinkShirt", "SmokingGuy", "MeatSalesman", "ToolsSalesman", "KeySalesman")
PORTRAIT_PALETTE_ENTRY, INSIDE_PALETTE_ENTRY = 0x1E0, 0x1D0     # bank 11: sprite palette sets 2 and 1

FIRST_NPC, LAST_NPC, TRIGGER_INTRO = 0x34, 0x45, 0x4F
NPC_KINDS = LAST_NPC - FIRST_NPC + 1
BOUNDS_TABLE = 0xB273                                      # bank 14, four bytes an entity
# the update handlers (bank 14 SPRITE_UPDATE_HANDLERS): (animation rule, mirror rule)
NPC_RULES = {0x34: (1, 2), 0x35: (1, 2), 0x36: (1, 2), 0x37: (0, 0), 0x38: (0, 2), 0x39: (0, 2), 0x3A: (2, 1), 0x3B: (0, 2), 0x3C: (0, 1), 0x3D: (0, 1),
             0x3E: (0, 1), 0x3F: (0, 1), 0x40: (0, 2), 0x41: (0, 2), 0x42: (0, 2), 0x43: (0, 0), 0x44: (0, 2), 0x45: (0, 2)}

BUILDING_SETS = tuple(range(0x11, 0x1B))                  # BUILDING_PALETTES: the palette set of building type 0-9
PALETTE_SETS = 28

ITEM_PICTURES = {0: (0xB4A0, 4), 1: (0xB4B0, 4), 2: (0xB4C0, 4), 3: (0xB4D0, 5), 4: (0xB4E4, 22)}      # bank 10: the tile numbers (4 an item) by category
ITEM_FIRST = (0, 4, 8, 12, 17)
ITEM_COUNT = 39
ITEM_TILES = 0x8500                                       # bank 10: tile n is at $8500 + 16 n

# ---------------------------------------------------------------------------------------------------------------------------------- the scripts
OPERANDS = {0x00: "", 0x01: "m", 0x02: "m", 0x03: "m", 0x04: "a", 0x05: "w", 0x06: "n", 0x07: "i", 0x08: "a", 0x09: "w", 0x0A: "n", 0x0B: "na", 0x0C: "na", 0x0D: "a",
            0x0E: "n", 0x0F: "a", 0x10: "i", 0x11: "a", 0x12: "ia", 0x13: "n", 0x14: "", 0x15: "", 0x16: "ma", 0x17: "a"}
SIZES = {"m": 1, "a": 2, "w": 2, "i": 1, "n": 1}
NAMES = {0x00: "END", 0x01: "MSG_UNSKIPPABLE", 0x02: "MSG_QUESTION", 0x03: "MSG", 0x04: "CHECK_UPDATE_TITLE", 0x05: "PAY_GOLD", 0x06: "SET_SPAWN", 0x07: "ADD_ITEM", 0x08: "OPEN_SHOP",
         0x09: "ADD_GOLD", 0x0A: "ADD_MP", 0x0B: "IF_QUEST", 0x0C: "IF_RANK_AT_LEAST", 0x0D: "IF_GOLD", 0x0E: "SET_QUEST", 0x0F: "BUY_SELL_MENU", 0x10: "CONSUME_ITEM",
         0x11: "SELL_MENU", 0x12: "IF_HAS_ITEM", 0x13: "ADD_HP", 0x14: "SHOW_PASSWORD", 0x15: "FINISH_GAME", 0x16: "MSG_QUESTION_JUMP", 0x17: "JUMP"}
JUMPS_AFTER = (0x04, 0x0B, 0x0C, 0x0D, 0x0F, 0x12, 0x16)    # these go on at their address or at the next action
LIST_OPS = (0x08, 0x11)                                      # their address is a shop list
ENDS = (0x00, 0x15, 0x17)                                    # no next action


def script_blob(rom: fr.Rom) -> bytes:
    return bytes(rom.cpu(SCRIPT_BANK, BLOB_START, BLOB_SIZE))


def script_pointers(rom: fr.Rom) -> list[int]:
    """The 152 addresses (bank 12) of the scripts by id."""
    low, high = rom.cpu(SCRIPT_BANK, TABLE_L, SCRIPT_COUNT), rom.cpu(SCRIPT_BANK, TABLE_U, SCRIPT_COUNT)
    return [low[i] | high[i] << 8 for i in range(SCRIPT_COUNT)]


def script_offsets(rom: fr.Rom) -> list[int]:
    return [p - BLOB_START for p in script_pointers(rom)]


def decode(blob: bytes, pos: int) -> tuple[int, list[int], int]:
    """The action at `pos` of the blob: (opcode, operands, position of the next byte). A gold amount is a number (low byte first in the ROM), an address is the ROM's address."""
    op = blob[pos]
    if op not in OPERANDS:
        raise ValueError(f"unknown action ${op:02X} at offset {pos}")
    at, values = pos + 1, []
    for kind in OPERANDS[op]:
        n = SIZES[kind]
        if at + n > len(blob):
            raise ValueError(f"action at offset {pos} runs past the blob")
        values.append(int.from_bytes(blob[at:at + n], "little"))
        at += n
    return op, values, at


def walk(blob: bytes, offset: int) -> dict[int, tuple[int, list[int]]]:
    """Every action a script can reach from its offset (the entity byte skipped), following jumps and both ways of a branch: {offset: (opcode, operands)}.
    Raises when a path runs out of the blob, meets an unknown action or never ends."""
    seen: dict[int, tuple[int, list[int]]] = {}
    todo = [offset + 1]
    while todo:
        pos = todo.pop()
        while pos not in seen:
            if not 0 <= pos < len(blob):
                raise ValueError(f"script path leaves the blob at {pos}")
            op, values, nxt = decode(blob, pos)
            seen[pos] = (op, values)
            if op in JUMPS_AFTER or op == 0x17:
                target = values[-1] - BLOB_START
                if not 0 <= target < len(blob):
                    raise ValueError(f"jump at offset {pos} leaves the blob")
                todo.append(target)
            if op in ENDS:
                break
            pos = nxt
    return seen


def shop_list(blob: bytes, address: int) -> list[tuple[int, int]]:
    """A shop list (an absolute ROM address): (item id, price) until the $FF."""
    pos, out = address - BLOB_START, []
    while blob[pos] != 0xFF:
        out.append((blob[pos], blob[pos + 1] | blob[pos + 2] << 8))
        pos += 3
    return out


def script_data(rom: fr.Rom) -> tuple[bytes, list[int]]:
    return script_blob(rom), script_offsets(rom)


# -------------------------------------------------------------------------------------------------------------------------------- the messages
def messages(rom: fr.Rom) -> tuple[bytes, list[int]]:
    """(the block of all messages with their $FF ends, the offset of each message, message 1 first)."""
    block = bytes(rom.cpu(MESSAGE_BANK, MESSAGES_START, MESSAGES_SIZE))
    offsets, at = [], 0
    for _ in range(MESSAGE_COUNT):
        offsets.append(at)
        at = block.index(0xFF, at) + 1
    if at != len(block):
        raise ValueError("the messages do not fill the block")
    return block, offsets


# ------------------------------------------------------------------------------------------------------------------------------- item pictures
def item_pictures(rom: fr.Rom) -> tuple[list[bytes], list[tuple[int, int, int, int]]]:
    """(the tiles, the four tile numbers of each of the 39 items in the order of `ITEM_FIRST`) with the tiles numbered by first use."""
    tiles: list[bytes] = []
    index: dict[int, int] = {}
    entries = []
    for category in range(5):
        address, count = ITEM_PICTURES[category]
        for n in range(count):
            numbers = rom.cpu(10, address + 4 * n, 4)
            row = []
            for number in numbers:
                if number not in index:
                    index[number] = len(tiles)
                    tiles.append(bytes(rom.cpu(10, ITEM_TILES + 16 * number, 16)))
                row.append(index[number])
            entries.append(tuple(row))
    return tiles, entries


# --------------------------------------------------------------------------------------------------------------------------------- palettes
def sprite_palettes_at(rom: fr.Rom, entry: int) -> list[list[int]]:
    b11 = rom.prg(11)
    return [list(b11[entry + 4 * i:entry + 4 * i + 4]) for i in range(4)]


def patched_palette(rom: fr.Rom, palette_set: int, sprite: list[list[int]], extra_live: tuple[int, ...] = ()) -> tuple[list[tuple[int, int, int]], list[int], list[int]]:
    """The building palette of `palette_set` with its spare slots given the colours of the sprite palettes `sprite` (four of four NES colours) that it lacks.
    Spare = a slot that is free (the plan has fewer than 16 colours) or holds a colour only the outside sprite palettes 2 and 3 use (nothing in a building draws with them: the
    hero, his spells and the HUD use the background palettes and sprite palettes 0 and 1). Every colour of the existing plan keeps its slot, so the block, HUD and hero images are unchanged.
    Returns (the 16 ST colours, the slot map of the sprite palettes: slot of colour c of palette p at 4p + c with colour 0 as 0, the NES colours that had to be approximated)."""
    plan = sc.plan_for_set(rom, palette_set)
    bg, outside = sc.palette_set(rom, palette_set)
    live = {plan.slot[c & 0x3F] for row in bg for c in row} | {plan.slot[c & 0x3F] for row in outside[:2] for c in row}
    colours = list(plan.colours) + [(0, 0, 0)] * (16 - len(plan.colours))
    needed = {sc.st_rgb(c) for row in sprite for c in row[1:]}
    live |= {i for i, rgb in enumerate(colours[:len(plan.colours)]) if rgb in needed}          # a colour the sprites need stays where it is
    spare = [i for i in range(1, 16) if i >= len(plan.colours) or i not in live]
    slot_of: dict[tuple[int, int, int], int] = {rgb: i for i, rgb in reversed(list(enumerate(colours[:len(plan.colours)])))}
    approximated: list[int] = []
    for row in sprite:
        for c in row[1:]:
            rgb = sc.st_rgb(c)
            if rgb in slot_of:
                continue
            if spare:
                at = spare.pop(0)
                colours[at] = rgb
                slot_of[rgb] = at
            else:
                best = min(slot_of, key=lambda k: sum((x - y) ** 2 for x, y in zip(k, rgb)))
                slot_of[rgb] = slot_of[best]
                approximated.append(c)
    slots = [0] * 16
    for p, row in enumerate(sprite):
        for c in (1, 2, 3):
            slots[4 * p + c] = slot_of[sc.st_rgb(row[c])]
    return colours, slots, approximated


def words(colours: list[tuple[int, int, int]]) -> bytes:
    return b"".join(sc.st_word(c).to_bytes(2, "big") for c in colours)


def building_palettes(rom: fr.Rom, entry: int) -> list[tuple[list[tuple[int, int, int]], list[int], list[int]]]:
    """`patched_palette` for the ten building sets and the sprite palette set at `entry` of bank 11."""
    sprite = sprite_palettes_at(rom, entry)
    return [patched_palette(rom, s, sprite) for s in BUILDING_SETS]


def outside_slots(rom: fr.Rom, palette_set: int) -> list[int]:
    """Slot map of the outside sprite palettes in a palette set's own plan (all their colours are in it)."""
    plan = sc.plan_for_set(rom, palette_set)
    sprite = sc.palette_set(rom, palette_set)[1]
    out = [0] * 16
    for p, row in enumerate(sprite):
        for c in (1, 2, 3):
            out[4 * p + c] = plan.slot[row[c] & 0x3F]
    return out


def item_colours(rom: fr.Rom, palette_set: int) -> bytes:
    """The HUD's palette of a set (the one the item pictures use) as four slots."""
    plan = sc.plan_for_set(rom, palette_set)
    bg, _ = sc.palette_set(rom, palette_set)
    return bytes(plan.slot[c & 0x3F] for c in bg[sc.ui_palette_row(rom, palette_set)])


# --------------------------------------------------------------------------------------------------------------------------------- portraits
def portraits(rom: fr.Rom) -> list[dict]:
    """Each portrait: {"tiles": [16 bytes], "frames": [(columns, rows, x, y, cells)] * 5} with a cell (tile number, attribute) or None."""
    out = []
    for pid in range(PORTRAITS):
        start = rom.cpu(8, PORTRAIT_TILE_INDEX + 2 * pid, 2)
        at = 0x8000 + (start[0] | start[1] << 8)
        numbers = []
        while rom.cpu(8, at, 1)[0] != 0xFF:
            numbers.append(rom.cpu(8, at, 1)[0])
            at += 1
        tiles = [bytes(rom.cpu(8, PORTRAIT_TILES + 16 * n, 16)) for n in numbers]
        frames = []
        for f in range(PORTRAIT_FRAMES):
            app = fs.appearance(rom, pid * PORTRAIT_FRAMES + f, "TILEINFO_PORTRAITS_ADDRS")
            frames.append((app.cols, app.rows, app.off_x, app.off_y, app.cells))
        out.append({"tiles": tiles, "frames": frames})
    return out


def pack_portrait(p: dict) -> bytes:
    out = bytearray(len(p["tiles"]).to_bytes(2, "big")) + b"".join(p["tiles"])
    for cols, rows, x, y, cells in p["frames"]:
        out += bytes([cols, rows, x & 255, y & 255])
        for cell in cells:
            out += bytes([0xFF, 0]) if cell is None else bytes(cell)
    return bytes(out)


def _s8(v: int) -> int:
    return v - 256 if v > 127 else v


def parse_portrait(data: bytes) -> tuple[dict, int]:
    """The inverse of `pack_portrait`: (the portrait, the bytes it took)."""
    n = int.from_bytes(data[:2], "big")
    tiles = [bytes(data[2 + 16 * i:18 + 16 * i]) for i in range(n)]
    at, frames = 2 + 16 * n, []
    for _ in range(PORTRAIT_FRAMES):
        cols, rows, x, y = data[at], data[at + 1], _s8(data[at + 2]), _s8(data[at + 3])
        at += 4
        cells = []
        for _ in range(cols * rows):
            cells.append(None if data[at] == 0xFF else (data[at], data[at + 1]))
            at += 2
        frames.append((cols, rows, x, y, tuple(cells)))
    return {"tiles": tiles, "frames": frames}, at


def portrait_file(rom: fr.Rom) -> bytes:
    head = 4 + 4 + 4 * PORTRAITS
    records = [pack_portrait(p) for p in portraits(rom)]
    palettes = building_palettes(rom, PORTRAIT_PALETTE_ENTRY)
    colours = b"".join(bytes(slots) for _, slots, _ in palettes) + b"".join(words(c) for c, _, _ in palettes)
    at = head + len(colours)
    offsets = []
    for record in records:
        offsets.append(at)
        at += len(record)
    return (PORTRAITS.to_bytes(2, "big") + len(BUILDING_SETS).to_bytes(2, "big") + head.to_bytes(4, "big")
            + b"".join(o.to_bytes(4, "big") for o in offsets) + colours + b"".join(records))


def parse_portrait_file(data: bytes) -> dict:
    count, sets, colours_at = int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big"), int.from_bytes(data[4:8], "big")
    offsets = [int.from_bytes(data[8 + 4 * i:12 + 4 * i], "big") for i in range(count)]
    slots = [list(data[colours_at + 16 * i:colours_at + 16 * i + 16]) for i in range(sets)]
    wat = colours_at + 16 * sets
    palettes = [[int.from_bytes(data[wat + 32 * i + 2 * j:wat + 32 * i + 2 * j + 2], "big") for j in range(16)] for i in range(sets)]
    return {"portraits": [parse_portrait(data[o:])[0] for o in offsets], "slots": slots, "palettes": palettes}


# -------------------------------------------------------------------------------------------------------------------------------- the people
def npc_frames(rom: fr.Rom, ent: int) -> int:
    offsets = [rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", e) for e in (ent, ent + 1)]
    return offsets[1] - offsets[0]


def npc_pose(rom: fr.Rom, ent: int, frame: int, mirrored: bool) -> list[tuple[int, int, int, int]]:
    """The cells of one picture: (dx, dy, tile, attribute) in ST screen coordinates relative to the person's x and playfield y (see the file description)."""
    first = rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", ent)
    app = fs.appearance(rom, first + frame, "TILEINFO_ENTITY_ADDRS")
    return [(s.x - sc.ANIM_BASE + sc.ST_LEFT, s.y + 1 - sc.ANIM_BASE, s.tile, s.attr & 0x43) for s in fs.place(app, sc.ANIM_BASE, sc.ANIM_BASE, 0x40 if mirrored else 0)]


def npc_kind(rom: fr.Rom, ent: int) -> bytes:
    b14 = rom.prg(14)
    tiles = fs.entity_tiles(rom, ent)
    frames = npc_frames(rom, ent)
    anim, mirror = NPC_RULES[ent]
    head = bytes([ent, frames, anim, mirror]) + b14[BOUNDS_TABLE - 0x8000 + 4 * ent:BOUNDS_TABLE - 0x8000 + 4 * ent + 4] + len(tiles).to_bytes(2, "big")
    body = b"".join(tiles[n] for n in range(len(tiles)))
    poses, offsets = bytearray(), []
    base = len(head) + len(body) + 4 * frames
    for f in range(frames):
        for mirrored in (False, True):
            offsets.append(base + len(poses))
            for dx, dy, tile, attr in npc_pose(rom, ent, f, mirrored):
                if tile >= len(tiles):
                    raise ValueError(f"entity {ent:#x} frame {f}: tile {tile} is not one of its {len(tiles)}")
                poses += dx.to_bytes(1, "big", signed=True) + dy.to_bytes(1, "big", signed=True) + bytes([tile, attr])
            poses += b"\x80"
    out = head + body + b"".join(o.to_bytes(2, "big") for o in offsets) + bytes(poses)
    return out + b"\0" * (len(out) & 1)


def walk_file(rom: fr.Rom) -> bytes:
    """npcwalk.bin, what the people's behaviour needs (it is part of the program, not of TOWN.DAT, which has no room left): a record of four bytes for each of the 18
    kinds (entity - $34): the hit box type (`SPRITE_ENTITIES_HITBOX_TYPES`, which the wall tests use), 0 and the word offset of the kind's script in the blob that follows;
    then the blob: the ROM's behaviour scripts of the kinds (`SPRITE_BSCRIPTS`, bank 14), each cut out with `enemy_data.script_chunk` (only what it reaches, jumps rebased to offsets
    in the blob). The ops are those of the enemies' scripts and op 6, which adds a value to the sprite's x (`BScript_Op_AddToSpriteData`)."""
    blob, records = bytearray(), []
    for ent in range(FIRST_NPC, LAST_NPC + 1):
        chunk, entry, _ = ed.script_chunk(rom, rom.word("SPRITE_BSCRIPTS", ent), len(blob))
        records.append(bytes([ed.entity(rom, ent)["hitbox"], 0]) + (len(blob) + entry).to_bytes(2, "big"))
        blob += chunk
    return b"".join(records) + bytes(blob) + b"\0" * (len(blob) & 1)


def parse_npc_kind(data: bytes) -> dict:
    ent, frames, anim, mirror = data[0], data[1], data[2], data[3]
    bounds = tuple(data[4:8])
    n = int.from_bytes(data[8:10], "big")
    tiles = [bytes(data[10 + 16 * i:26 + 16 * i]) for i in range(n)]
    at = 10 + 16 * n
    table = [int.from_bytes(data[at + 2 * i:at + 2 * i + 2], "big") for i in range(2 * frames)]
    poses = []
    for o in table:
        cells = []
        while data[o] != 0x80:
            cells.append((_s8(data[o]), _s8(data[o + 1]), data[o + 2], data[o + 3]))
            o += 4
        poses.append(cells)
    return {"entity": ent, "frames": frames, "anim": anim, "mirror": mirror, "bounds": bounds, "tiles": tiles, "poses": poses}


def placements(rom: fr.Rom) -> list[tuple[int, int, int, int, int, int]]:
    """Every person and trigger the screens place: (area, screen, entity, script id, x, y), the value byte of a sprite being its script id."""
    b11 = rom.prg(11)

    def word(a: int) -> int:
        return b11[a - 0x8000] | b11[a - 0x8000 + 1] << 8

    categories = rom.at("SPRITE_CATEGORIES_BY_ENTITY", 101)
    first = rom.label("AREA_SPRITE_ADDRESSES").addr
    out = []
    for area in range(8):
        table = word(first + 2 * area)
        if b11[table - 0x8000 + 1] == 0xFF:
            continue
        for screen in range((word(table) - table) // 2):
            p, pairs = word(table + 2 * screen), []
            while b11[p - 0x8000] != 0xFF:
                pairs.append((b11[p - 0x8000], b11[p - 0x8000 + 1]))
                p += 2
            p += 1
            values = []
            for _ in pairs:
                v = b11[p - 0x8000]
                values.append(v)
                if v == 0xFF:
                    break
                p += 1
            values += [0xFF] * (len(pairs) - len(values))
            for (ent, yx), value in zip(pairs, values):
                if FIRST_NPC <= ent <= LAST_NPC or ent == TRIGGER_INTRO or categories[ent] in (2, 4):
                    out.append((area, screen, ent, value, (yx & 15) * 16, yx & 0xF0))
    return out


def npc_file(rom: fr.Rom) -> bytes:
    kinds = [npc_kind(rom, e) for e in range(FIRST_NPC, LAST_NPC + 1)]
    inside = building_palettes(rom, INSIDE_PALETTE_ENTRY)
    sets = bytearray()
    for s in range(PALETTE_SETS):
        sets += bytes(inside[s - BUILDING_SETS[0]][1]) if s in BUILDING_SETS else bytes(outside_slots(rom, s))
    palettes = b"".join(words(c) for c, _, _ in inside)
    places = b"".join(bytes(r) for r in placements(rom)) + b"\xff"
    head = 4 + 4 * 4
    table = head
    at = table + 4 * len(kinds)
    offsets = []
    for k in kinds:
        offsets.append(at)
        at += len(k)
    colours_at, palettes_at = at, at + len(sets)
    places_at = palettes_at + len(palettes)
    return (len(kinds).to_bytes(2, "big") + PALETTE_SETS.to_bytes(2, "big") + b"".join(v.to_bytes(4, "big") for v in (table, colours_at, palettes_at, places_at))
            + b"".join(o.to_bytes(4, "big") for o in offsets) + b"".join(kinds) + bytes(sets) + palettes + places + b"\0" * (len(places) & 1))


def parse_npc_file(data: bytes) -> dict:
    count, sets = int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big")
    table, colours_at, palettes_at, places_at = (int.from_bytes(data[4 + 4 * i:8 + 4 * i], "big") for i in range(4))
    kinds = [parse_npc_kind(data[int.from_bytes(data[table + 4 * i:table + 4 * i + 4], "big"):]) for i in range(count)]
    slots = [list(data[colours_at + 16 * i:colours_at + 16 * i + 16]) for i in range(sets)]
    palettes = [[int.from_bytes(data[palettes_at + 32 * i + 2 * j:palettes_at + 32 * i + 2 * j + 2], "big") for j in range(16)] for i in range(len(BUILDING_SETS))]
    places, at = [], places_at
    while data[at] != 0xFF:
        places.append(tuple(data[at:at + 6]))
        at += 6
    return {"kinds": kinds, "slots": slots, "palettes": palettes, "places": places}


# ----------------------------------------------------------------------------------------------------------------------------------- the files
def iscript_file(rom: fr.Rom) -> bytes:
    blob, offsets = script_data(rom)
    block, message_offsets = messages(rom)
    tiles, pictures = item_pictures(rom)
    colours = b"".join(item_colours(rom, s) for s in BUILDING_SETS)
    parts = [b"".join(o.to_bytes(2, "big") for o in offsets), blob, b"".join(o.to_bytes(2, "big") for o in message_offsets), block,
             len(tiles).to_bytes(2, "big") + b"".join(tiles) + b"".join(bytes(e) for e in pictures), colours]
    at, offs = 4 + 4 * len(parts), []
    for part in parts:
        offs.append(at)
        at += len(part) + len(part) % 2
    return (SCRIPT_COUNT.to_bytes(2, "big") + MESSAGE_COUNT.to_bytes(2, "big") + b"".join(o.to_bytes(4, "big") for o in offs)
            + b"".join(p + b"\0" * (len(p) % 2) for p in parts))


def parse_iscript_file(data: bytes) -> dict:
    scripts, count = int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big")
    o = [int.from_bytes(data[4 + 4 * i:8 + 4 * i], "big") for i in range(6)]
    n = int.from_bytes(data[o[4]:o[4] + 2], "big")
    return {"offsets": [int.from_bytes(data[o[0] + 2 * i:o[0] + 2 * i + 2], "big") for i in range(scripts)], "blob": bytes(data[o[1]:o[1] + BLOB_SIZE]),
            "message_offsets": [int.from_bytes(data[o[2] + 2 * i:o[2] + 2 * i + 2], "big") for i in range(count)], "messages": bytes(data[o[3]:o[3] + MESSAGES_SIZE]),
            "item_tiles": [bytes(data[o[4] + 2 + 16 * i:o[4] + 18 + 16 * i]) for i in range(n)],
            "item_pictures": [tuple(data[o[4] + 2 + 16 * n + 4 * i:o[4] + 6 + 16 * n + 4 * i]) for i in range(ITEM_COUNT)],
            "item_colours": [list(data[o[5] + 4 * i:o[5] + 4 * i + 4]) for i in range(len(BUILDING_SETS))], "offsets_at": o}


def build(rom: fr.Rom) -> dict[str, bytes]:
    return {"iscript.bin": iscript_file(rom), "portraits.bin": portrait_file(rom), "npc.bin": npc_file(rom)}


def equates(files: dict[str, bytes]) -> str:
    """Numbers for the assembly (iscript.inc)."""
    iscript = parse_iscript_file(files["iscript.bin"])["offsets_at"]
    names = ("OFFSETS", "BLOB", "MSG_OFFSETS", "MESSAGES", "ITEM_PICTURES", "ITEM_COLOURS")
    lines = [f"    .equ ISCRIPT_{n}, {v}\n" for n, v in zip(names, iscript)]
    lines += [f"    .equ ISCRIPT_COUNT, {SCRIPT_COUNT}\n", f"    .equ ISCRIPT_BASE, {BLOB_START}\n", f"    .equ MESSAGE_COUNT, {MESSAGE_COUNT}\n", f"    .equ ISCRIPT_BYTES, {len(files['iscript.bin'])}\n",
              f"    .equ PORTRAITS_BYTES, {len(files['portraits.bin'])}\n", f"    .equ NPC_BYTES, {len(files['npc.bin'])}\n"]
    kinds = parse_npc_file(files["npc.bin"])["kinds"]      # what a person's slot in the program needs (src/viewer.s: NPC_SLOT_RAM): the table and lists of poses, the keys and images
    lists = max(16 + sum(8 + 6 * len(cells) + 2 for cells in k["poses"]) for k in kinds)
    images = max(len({(c[2], c[3]) for cells in k["poses"] for c in cells}) for k in kinds)
    lines += [f"    .equ NPC_LIST_BYTES, {lists + -lists % 4}\n", f"    .equ NPC_IMAGE_SLOTS, {images}\n"]
    portraits_at = len(files["iscript.bin"])
    lines += [f"    .equ TOWN_PORTRAITS, {portraits_at}\n", f"    .equ TOWN_NPC, {portraits_at + len(files['portraits.bin'])}\n", f"    .equ TOWN_BYTES, {len(town_file(files))}\n"]
    return "| generated by tools/iscripts.py\n" + "".join(lines)


def town_file(files: dict[str, bytes]) -> bytes:
    """TOWN.DAT, the file the program reads: iscript.bin, portraits.bin and npc.bin one after the other (each an even length, so the words in them stay
    at even addresses); TOWN_PORTRAITS and TOWN_NPC in iscript.inc are where the second and the third start."""
    parts = [files[name] for name in ("iscript.bin", "portraits.bin", "npc.bin")]
    assert all(len(p) % 2 == 0 for p in parts)
    return b"".join(parts)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    rom_ = fr.Rom(Path(sys.argv[1]) if len(sys.argv) > 1 else fr.DEFAULT_ROM)
    for name, blob_ in build(rom_).items():
        print(f"{name}: {len(blob_)} bytes")
