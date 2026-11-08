"""The enemies' data from the ROM: what is where on each screen (bank 11), what each kind is (hit points, hit box, experience, what it drops;
bank 14) and the script that drives it (`BSCRIPTS_*`, bank 14), cut out of the ROM and rebased so that a package holds only the scripts of the
enemies of its area. `enemy_model.py` runs a script as the ROM does; the ST code runs the same bytes."""
from __future__ import annotations

import faxanadu_rom as fr
import faxanadu_sprites as fs

ENTITIES = 101                      # SPRITE_* ids 0 to 100
NONE = 0xFF
E_BOSS_DEATH = 0x64
CATEGORY_ENEMY, CATEGORY_DROPPED, CATEGORY_NPC, CATEGORY_EFFECT, CATEGORY_TRIGGER, CATEGORY_ITEM, CATEGORY_MAGIC, CATEGORY_BOSS = range(8)

# The kinds the ST code runs so far: entity -> (frames of pictures, the picture rule of `enemy_model.appearance_offset`).
ENEMIES = (0x47, 0x2A, 0x0C, 0x06, 0x26, 0x1B, 0x0B, 0x07, 0x15,
           0x04, 0x19, 0x28, 0x1E, 0x20, 0x17, 0x08, 0x1F, 0x21, 0x1C, 0x22, 0x1A, 0x18, 0x05, 0x0D, 0x23, 0x2C, 0x10, 0x0E, 0x0F, 0x11, 0x2F, 0x2D, 0x32, 0x2E, 0x30, 0x31)      # Zozura, Monodron, Snowman, Zombie, Ikeda, Myconid, Yuinaru, Hornet, Charron, Raiden, Grimlock, Lamprey, Giant Strider, Maskman, Geributa, Bihoruda, Sir Gawaine, Wolfman, Naga, Yareeka, Giant Bees, Sugata, Necron Aides, Nash, Magman, Tamazutsu, Execution Hood, Fire Giant, Ishiisu, Rokusutahn, Borabohra, Ripasheiku, King Grieve
KINDS = {0x47: 2, 0x2A: 3, 0x0C: 2, 0x06: 3, 0x26: 3, 0x1B: 2, 0x0B: 2, 0x07: 2, 0x15: 3, 0x54: 4, 0x04: 4, 0x19: 4, 0x28: 2, 0x1E: 3, 0x20: 5, 0x17: 3, 0x08: 2, 0x1F: 3, 0x21: 3, 0x1C: 2, 0x22: 2, 0x1A: 2, 0x18: 2, 0x05: 2, 0x0D: 3, 0x23: 2, 0x2C: 7, 0x10: 2, 0x0E: 3, 0x0F: 4, 0x11: 4, 0x2F: 8, 0x2D: 4, 0x32: 3, 0x2E: 4, 0x30: 3, 0x31: 3, 3: 2, 9: 2, 0x0A: 2, 0x51: 2, 0x13: 8, 0x64: 16, 1: 1, 2: 2}      # + the death effect (a picture for each of its 8 frames), bread, coin
RULE = {0x47: 0, 0x2A: 1, 0x0C: 5, 0x06: 6, 0x26: 7, 0x1B: 8, 0x0B: 9, 0x07: 10, 0x15: 11, 0x54: 12, 0x04: 13, 0x19: 14, 0x28: 15, 0x1E: 16, 0x20: 17, 0x17: 18, 0x08: 19, 0x1F: 20, 0x21: 20, 0x1C: 21, 0x22: 21, 0x1A: 21, 0x18: 21, 0x05: 22, 0x0E: 23, 0x2C: 24, 0x0D: 25, 0x10: 26, 0x23: 27, 0x51: 28, 0x0F: 29, 0x11: 30, 0x2F: 32, 0x2D: 33, 0x32: 34, 0x2E: 35, 0x30: 36, 0x31: 37, 3: 38, 9: 21, 0x0A: 10, 0x64: 31, 0x13: 2, 1: 3, 2: 4}
SPAWNED = {0x15: 0x54, 0x0D: 0x51, 0x10: 0x51, 0x0F: 0x51, 0x2D: 0x0A, 0x32: 0x0A, 0x30: 9, 0x31: 3}                 # what an enemy makes: Charron's fireball (it is in a package whenever its maker is, but is never placed on a screen)
ROM_FRAMES = {3: (3, 5)}                # kinds that use only some of the ROM's frames (the rock: 3 and 5): the pictures are made for those, and the rule counts them 0, 1
EXTRAS = (0x13, 1, 2, 0x64)             # what an enemy leaves: they are in every package that has enemies (the boss death only where a boss is); their tiles are the common sprite tiles
KIND_BYTES = 32
PLACE_BYTES = 6

# The bytes of data a behaviour takes from the script when it starts (the number it adds to Sprites_ReadInfoAddr), for the behaviours modelled.
BEHAVIOUR_DATA = {0: 2, 1: 0, 2: 0, 4: 2, 7: 0, 9: 3, 21: 0, 23: 0, 25: 0, 27: 0, 30: 0, 22: 0, 26: 0, 31: 0, 32: 0, 33: 0, 34: 0, 35: 0, 39: 0, 40: 0, 10: 0, 12: 0, 15: 0, 13: 0, 18: 3, 19: 2, 24: 0, 28: 0, 62: 0, 14: 0, 3: 0, 63: 0, 64: 0, 65: 0}
# The length of each op's own bytes; op 0 (switch behaviour) is followed by its behaviour's data.
OP_BYTES = {0: 3, 1: 3, 2: 2, 3: 7, 4: 1, 5: 3, 7: 2}
JUMPS = {1: (1,), 5: (1,), 3: (3, 5)}       # the byte offsets of the addresses in an op


def placements(rom: fr.Rom, area: int, screen: int) -> list[tuple[int, int, int]]:
    """The sprites the ROM puts on a screen, in the order it does (the first goes to slot 7): (entity, x, y)."""
    b11 = rom.prg(11)

    def word(addr: int) -> int:
        return b11[addr - 0x8000] | b11[addr - 0x8000 + 1] << 8

    table = word(rom.label("AREA_SPRITE_ADDRESSES").addr + 2 * area)
    if b11[table - 0x8000 + 1] == 0xFF:
        return []
    p, out = word(table + 2 * screen), []
    while b11[p - 0x8000] != 0xFF:
        v = b11[p - 0x8000 + 1]
        out.append((b11[p - 0x8000], (v & 15) * 16, v & 0xF0))
        p += 2
    return out


def entity(rom: fr.Rom, ent: int) -> dict:
    """The per-kind tables: hit box type, category, hit points, experience (`ENEMY_EXPERIENCE`), the drop (`SPRITE_ENTITY_DROP_VALUES_INDEX`), the
    script address and the tiles' count."""
    return {
        "hitbox": rom.byte("SPRITE_ENTITIES_HITBOX_TYPES", ent), "category": rom.byte("SPRITE_CATEGORIES_BY_ENTITY", ent),
        "hp": rom.byte("SPRITE_ENTITIES_HP", ent), "script": rom.word("SPRITE_BSCRIPTS", ent),
        "appearance": rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", ent), "tiles": rom.byte("SPRITES_PPU_TILE_COUNTS", ent),
    }


BOUNDS_TABLE = 0xB273                 # Sprite_GetBounds: four bytes an entity (left, top, width, height), in bank 14


def kind_info(rom: fr.Rom, ent: int) -> dict:
    """What combat needs to know of an entity (`Player_HitSpriteWithWeapon`, `CurrentSprite_CheckHitPlayer`, `Sprite_RunDeathDropHandler`): its category, hit points,
    experience, the damage it does, the weapon's reach test's extents (`MAYBE_SPRITE_EXTENTS`), the box a touch is tested with and what it drops: (1 bread or 2 coin, value) or None."""
    b14 = rom.prg(14)
    idx = rom.byte("SPRITE_ENTITY_DROP_VALUES_INDEX", ent)
    drop = None if idx == 0xFF or idx >= 0x40 else (2 if idx < 0x30 else 1, rom.byte("SPRITE_DROP_VALUES", idx))
    return {
        "category": rom.byte("SPRITE_CATEGORIES_BY_ENTITY", ent), "hbox": rom.byte("SPRITE_ENTITIES_HITBOX_TYPES", ent), "hp": rom.byte("SPRITE_ENTITIES_HP", ent),
        "exp": rom.byte("ENEMY_EXPERIENCE", ent), "damage": rom.byte("SPRITE_ENTITY_DAMAGES", ent), "script": rom.word("SPRITE_BSCRIPTS", ent), "drop": drop,
        "extent": (rom.byte("MAYBE_SPRITE_EXTENTS", 2 * ent), rom.byte("MAYBE_SPRITE_EXTENTS_1_", 2 * ent)),
        "bounds": tuple(b14[BOUNDS_TABLE - 0x8000 + 4 * ent + i] for i in range(4)),
    }


def tables(rom: fr.Rom) -> dict:
    """The small tables combat uses: WEAPON_STRENGTHS, WEAPON_TO_GLOVE_STRENGTH, ARMOR_DEFENSE_MULTIPLIERS."""
    return {"weapon": [rom.byte("WEAPON_STRENGTHS", i) for i in range(4)], "glove": [rom.byte("WEAPON_TO_GLOVE_STRENGTH", i) for i in range(4)],
            "armour": [rom.byte("ARMOR_DEFENSE_MULTIPLIERS", i) for i in range(4)]}


def script_extent(rom: fr.Rom, start: int) -> tuple[list[tuple[int, int]], list[tuple[int, int, int]]]:
    """Follow a script from `start` (a CPU address in bank 14): ((address, length) of its ops, (op address, byte offset, target) of its jump words). Raises for an op or
    a behaviour that is not modelled."""
    b14 = rom.prg(14)
    ops, words, todo, seen = [], [], [start], set()
    while todo:
        at = todo.pop()
        while at not in seen:
            seen.add(at)
            op = b14[at - 0x8000]
            if op == 0xFF:
                ops.append((at, 1))
                break
            if op not in OP_BYTES:
                raise NotImplementedError(f"script op {op} at {at:#x}")
            length = OP_BYTES[op]
            if op == 0:
                beh = b14[at - 0x8000 + 1]
                if beh not in BEHAVIOUR_DATA:
                    raise NotImplementedError(f"behaviour {beh} at {at:#x}")
                length += BEHAVIOUR_DATA[beh]
            ops.append((at, length))
            for j in JUMPS.get(op, ()):
                target = b14[at - 0x8000 + j] | b14[at - 0x8000 + j + 1] << 8
                words.append((at, j, target))
                todo.append(target)
            if op in JUMPS:                              # goes on only at its targets
                break
            at += length
    return sorted(ops), sorted(words)


def script_chunk(rom: fr.Rom, start: int, base: int) -> tuple[bytes, int, dict[int, int]]:
    """The script at `start` as bytes for a package: only what it reaches, in address order, with every jump rebased to `base` + the position in
    the chunk. (the chunk, the entry offset, the new offset of each op by its old address)"""
    b14 = rom.prg(14)
    ops, words = script_extent(rom, start)
    out = bytearray()
    new_at = {}
    for at, length in ops:
        new_at[at] = base + len(out)
        out += b14[at - 0x8000:at - 0x8000 + length]
    for at, j, target in words:
        pos = new_at[at] - base + j
        out[pos:pos + 2] = new_at[target].to_bytes(2, "little")
    return bytes(out), new_at[start] - base, {old: new - base for old, new in new_at.items()}


def package_parts(rom: fr.Rom, area: int, screens: list[int], palette_index: int, plan) -> dict[str, bytes]:
    """The enemy data of an area's package (`screens` are the ROM's screen numbers in package order, None for a building's):
    enemy_places: a word a screen (the offset of its list from the start of the part), then the lists, each place being the entity, x and y (words), ended by -1;
    enemy_kinds: a record of KIND_BYTES for each kind in the area (and the death effect, bread and coin): entity, hit box type, hit points, the script's offset in
      enemy_scripts, its first pose (frame f facing left is pose first + 2f, facing right + 1), the rule, experience, what it drops (kind << 8 | value), the weapon's
      extents x and y, the touch box left, top, width, height, the damage it does, 1 for a boss (words);
    enemy_anim, enemy_images: the poses and the 8x8 images, as for the spells; enemy_scripts: the scripts, jumps as offsets within them."""
    import st_convert as sc

    lists = []
    for sid in screens:
        lists.append([p for p in placements(rom, area, sid) if p[0] in ENEMIES] if sid is not None else [])
    used = sorted({p[0] for items in lists for p in items})
    used += [SPAWNED[e] for e in used if e in SPAWNED]
    if used:
        bosses = any(entity(rom, e)["category"] == CATEGORY_BOSS for e in used)
        used += [e for e in EXTRAS if bosses or e != E_BOSS_DEATH]
    palettes = sc.sprite_palettes(rom, palette_index)
    images: list[bytes] = []
    index: dict[tuple, int] = {}
    records, firsts = [], {}
    scripts, entries = bytearray(), {}
    for ent in used:
        chunk, entry, _ = script_chunk(rom, rom.word("SPRITE_BSCRIPTS", ent), len(scripts))
        entries[ent] = len(scripts) + entry
        scripts += chunk
        tiles = fs.common_tiles(rom) if ent in EXTRAS else fs.entity_tiles(rom, ent)
        firsts[ent] = len(records)
        for count in range(KINDS[ent]):
            frame = ROM_FRAMES[ent][count] if ent in ROM_FRAMES else count
            base = rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", ent)
            # an enemy's picture is mirrored when it faces right; the others have one picture (the same record serves both poses)
            for flip in ((0, 0x40) if ent in ENEMIES or ent in SPAWNED.values() else (0,)):
                entries_ = []
                # the death effect (SpriteUpdateHandler_Effect_EnemyDeath) is three pieces: the first where the enemy was, the second 4 * frame lines above it, the third as far below
                pieces = [(base + 0, 0, 0, 0), (base + 1, 0, -4 * frame, 0), (base + 2, 0, 4 * frame, 0)] if ent == 0x13 or (ent == E_BOSS_DEATH and frame < 8) else [(base + frame, 0, 0, 0)]
                if ent == E_BOSS_DEATH and frame >= 8:      # (SpriteUpdateHandler_Effect_LightningBall20: four pieces flying up, down, left and right)
                    d = 4 * (frame - 8)
                    pieces = [(base + 1, 0, -d, 0), (base + 2, 0, d, 0), (base + 3, -d, 0, 0), (base + 3, d, 0, 0x40)]
                for number, dx, dy, mirror in pieces:
                    app = fs.appearance(rom, number, "TILEINFO_ENTITY_ADDRS")
                    for sp in fs.place(app, sc.ANIM_BASE + dx, sc.ANIM_BASE + dy, flip ^ mirror):
                        key = (ent, sp.tile, sp.attr & 3, bool(sp.attr & 0x40), bool(sp.attr & 0x80))
                        if key not in index:
                            index[key] = len(images)
                            images.append(sc.sprite_image(tiles.get(sp.tile, bytes(16)), key[3], palettes[key[2]], plan, key[4]))
                        entries_.append((sp.x - sc.ANIM_BASE + sc.ST_LEFT, sp.y + 1 - sc.ANIM_BASE, index[key]))
                x0, y0 = min(e[0] for e in entries_), min(e[1] for e in entries_)
                box = (x0, max(e[0] for e in entries_) + 8, y0, max(e[1] for e in entries_) + 8)
                record = b"".join(v.to_bytes(2, "big", signed=True) for v in box)
                for e in entries_:
                    record += b"".join(v.to_bytes(2, "big", signed=True) for v in e)
                records.append(record + b"\xff\xff")
    offsets, at = [], 2 * len(records)
    for record in records:
        offsets.append(at)
        at += len(record)
    kinds = bytearray()
    for ent in used:
        info, kind = entity(rom, ent), kind_info(rom, ent)
        drop = 0 if kind["drop"] is None else kind["drop"][0] << 8 | kind["drop"][1]
        row = [ent, info["hitbox"], info["hp"], entries[ent], firsts[ent], RULE[ent], kind["exp"], drop, *kind["extent"], *kind["bounds"], kind["damage"], int(kind["category"] == CATEGORY_BOSS)]
        kinds += b"".join(v.to_bytes(2, "big") for v in row)
    head = 2 * len(lists)
    body, places = bytearray(), []
    for items in lists:
        places.append(head + len(body))
        for ent, x, y in items:
            body += ent.to_bytes(2, "big") + x.to_bytes(2, "big") + y.to_bytes(2, "big")
        body += b"\xff\xff"
    return {
        "enemy_places": b"".join(o.to_bytes(2, "big") for o in places) + bytes(body), "enemy_kinds": bytes(kinds) + b"\xff\xff",
        "enemy_anim": b"".join(o.to_bytes(2, "big") for o in offsets) + b"".join(records), "enemy_images": b"".join(images), "enemy_scripts": bytes(scripts),
    }


def random_table(rom: fr.Rom) -> bytes:
    """The 256 bytes GetRandom reads: the start of `Sprites_UpdateAll` (bank 14)."""
    o = rom.label("Sprites_UpdateAll").offset - fr.HEADER - 14 * fr.BANK
    return rom.prg(14)[o:o + 256]
