#!/usr/bin/env python3
"""Make the ST data of one Faxanadu screen from your ROM, for the viewer (src/viewer.s).

    build_assets.py [--rom ext/Faxanadu_Europe.nes] [--area 0] [--screen 1] [--camera 40] [--world 0,1] [--out build/generated]

Writes hero_list.bin and hero_images.bin (the hero's sprites for the ST), hud_tiles.bin (the 60 HUD tiles, 32 bytes each) and hud_layout.bin (its 4 rows of 32 tile ids, as at the start of a game),
palette.bin (16 ST colour words), blocks.bin (the 128-byte block images the screen uses), block_index.bin (1024 words:
image number of (block id * 4 + corner), $FFFF for none), screen.bin (the screen's 13 rows of 16 block ids) and assets.inc
(the numbers the assembly needs). Nothing here is committed: it all comes from the ROM and is rebuilt on each build.
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import enemy_data as ed
import faxanadu_gfx as gfx  # noqa: E402
import faxanadu_maps as fm
import hero_physics as hp  # noqa: E402
import lz
import faxanadu_rom as fr  # noqa: E402
import faxanadu_text as ft  # noqa: E402
import st_convert as sc  # noqa: E402


DOOR_BYTES = 8
EDGE_BYTES = 5
DOOR_SAME, DOOR_PALETTE, DOOR_BUILDING, DOOR_OUTSIDE = 0, 1, 2, 3
BUILDING_AREA = 4


def door_table(rom: fr.Rom, a: fm.Area, ids: list[int], palette_index: int, world: dict[int, list[int]]) -> tuple[bytes, list[tuple]]:
    """The doors on the screens in `ids`, 8 bytes each: screen (its number in the tables), block (row * 16 + column), kind, the screen it
    leads to (its number in the tables of the area it leads to), where the hero stands there (Y/16 << 4 | X/16), the palette set there, the key
    it needs (`Game_RunDoorRequirementHandler`'s number), the area it leads to (for a building: its number, the screen being the building's
    own). Kinds (`Player_CheckHandleEnterDoor`): 0 another screen of this area in this palette set, 1 the same with another palette set, 2 into
    a building (destination index $20 or more; all of area 3's; the layout is the building's number, which is also the screen in the
    building area; palette, tiles and start position come from the BUILDING_ tables), 3 out to another area (index $FE and $FF: the region
    and screen from the transition tables, the area's own palette). `world` says which areas (and their screens) have data: a door
    to anywhere else is left out. Also returns what the doors lead to, as (area, palette[, building])."""
    out, targets = bytearray(), []
    region = fm.area_region(rom, a.index)
    for d in fm.doors(rom, a):
        if d.screen not in ids:
            continue
        source = ids.index(d.screen)
        if d.destination >= 0xFE:
            if region is None:
                continue
            key, new_region, screen = fm.outside(rom, region, d.destination & 1)
            dest = fm.region_area(rom, new_region)
            if dest not in world or screen not in world[dest]:
                continue
            palette = fm.area(rom, dest).palette_index
            out += bytes([source, d.block, DOOR_OUTSIDE, world[dest].index(screen), d.start, palette, key, dest])
            targets.append((dest, palette))
            continue
        screen, second, key, _ = fm.door_destination(rom, a, d)
        if d.destination >= 0x20 or a.index == 3:
            info = fm.building(rom, second)
            out += bytes([source, d.block, DOOR_BUILDING, 0, info["start"], info["palette"], key, second])
            targets.append((BUILDING_AREA, info["palette"], second))
            continue
        if screen not in ids:
            continue
        kind = DOOR_SAME if second == palette_index else DOOR_PALETTE
        out += bytes([source, d.block, kind, ids.index(screen), d.start, second, key, a.index])
        targets.append((a.index, second))
    return bytes(out), targets


def edge_table(rom: fr.Rom, a: fm.Area, ids: list[int], world: dict[int, list[int]]) -> tuple[bytes, list[tuple]]:
    """Walking off a side of a screen that has no neighbour (`fm.edges`): screen, new area, new screen, start position, palette set; only those
    that lead to an area in `world`."""
    out, targets = bytearray(), []
    for screen, dest, dest_screen, start, palette in fm.edges(rom, a.index):
        if screen in ids and dest in world and dest_screen in world[dest]:
            out += bytes([ids.index(screen), dest, world[dest].index(dest_screen), start, palette])
            targets.append((dest, palette))
    return bytes(out), targets


# "blocking" and "ladders" hold no data: the program makes them (a flag a block position, in memory behind the package) from the screens and
# "block_flags" (a byte a block id: 1 a block he cannot walk through, 2 a ladder) when it loads a package, which keeps the disk smaller.
FLAG_ROOM = 6 * 2 * 208                  # the block flags of 6 screens (src/viewer.s: FLAG_SLOTS), made when asked for, behind the package
PACKAGE_PARTS = ("palette", "screens", "neighbours", "blocking", "ladders", "doors", "edges", "block_index", "blocks", "hud_tiles", "hud_partial",
                 "hero_list", "hero_images", "hero_colours", "magic_anim", "magic_images", "block_flags",
                 "enemy_places", "enemy_kinds", "enemy_anim", "enemy_images", "enemy_scripts")
HEADER_WORDS = ("door_count", "screen_count", "edge_count", "music")


def package_name(area: int, palette: int) -> str:
    return f"A{area}P{palette:02d}.DAT"


def make_package(parts: dict[str, bytes], counts: dict[str, int]) -> bytes:
    """An area's data in one palette set as one block: a long offset from its start for each of PACKAGE_PARTS, the HEADER_WORDS (the numbers
    of doors, screens and edges, and the music to play), then the parts, each on a multiple of 4."""
    head = 4 * len(PACKAGE_PARTS) + 2 * len(HEADER_WORDS)
    offsets, body = [], bytearray()
    for name in PACKAGE_PARTS:
        offsets.append(head + len(body))
        body += parts[name]
        body += b"\0" * (-len(body) % 4)
    return (b"".join(o.to_bytes(4, "big") for o in offsets) + b"".join(counts[n].to_bytes(2, "big") for n in HEADER_WORDS) + bytes(body))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, default=fr.DEFAULT_ROM)
    parser.add_argument("--area", type=int, default=0)
    parser.add_argument("--screen", type=int, default=1)
    parser.add_argument("--camera", type=int, default=40, help="first line of the 208-line playfield shown in the 168-line window (0-40)")
    parser.add_argument("--hero", default="144,144,0,255,0,0,1",
                        help="the hero: x,y,armour,shield,weapon,frame,faces-left (default: where he stands after the castle door, start equipment)")
    parser.add_argument("--reach", type=int, default=2, help="screens within this many steps of --screen are included (the viewer can scroll between them)")
    parser.add_argument("--all", action="store_true", help="every screen of the start area (their numbers in the tables are the ROM's)")
    parser.add_argument("--world", default="", help="more areas, comma separated (whole, ROM screen numbers): the doors and edges that lead there "
                        "work, and so do those into buildings (their packages are small). The other areas' packages are written when the start area "
                        "leads to them.")
    parser.add_argument("--hud", default="16,0,0,0,0", help="the HUD first drawn: power,magic,experience,gold,seconds")
    parser.add_argument("--hud2", default="", help="a second HUD state drawn over the first (default: the same)")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "build" / "generated")
    args = parser.parse_args()
    if not args.rom.is_file():
        raise SystemExit(f"{args.rom} is missing: put your Faxanadu (Europe) ROM there (it is never committed)")
    if not 0 <= args.camera <= 40:
        raise SystemExit("--camera is 0 to 40")
    rom = fr.Rom(args.rom)
    a = fm.area(rom, args.area)
    # the start screen first, then the screens around it (breadth first): the viewer scrolls between them
    ids, frontier = [args.screen], [args.screen]
    if args.all:
        ids = list(range(fm.screen_count(rom, a)))
        frontier = []
    for _ in range(args.reach):
        step = []
        for sid in frontier:
            for n in fm.neighbours(rom, a, sid):
                if n != 0xFF and n not in ids:
                    ids.append(n)
                    step.append(n)
        frontier = step
    world = {args.area: ids}
    for extra in (int(v) for v in args.world.split(",") if v.strip()):
        if extra != args.area:
            world[extra] = list(range(fm.screen_count(rom, fm.area(rom, extra))))
    args.out.mkdir(parents=True, exist_ok=True)
    keys = ("hp", "mp", "experience", "gold", "seconds")
    start = dict(zip(keys, (int(v) for v in args.hud.split(","))))
    second = dict(zip(keys, (int(v) for v in args.hud2.split(",")))) if args.hud2 else start
    (args.out / "hud_states.bin").write_bytes(sc.hud_state_bytes(start) + sc.hud_state_bytes(second))
    (args.out / "title_table.bin").write_bytes(sc.title_table_bytes(rom))
    # the font (96 glyphs of 8 bytes), then the texts the program shows, each ended by a 0 byte: text_data + TEXT_x is where one starts
    wrong, ask = ft.password_lines(rom)
    texts = {"DEATH": ft.message(rom, ft.MESSAGE_DEATH), "MEDITATE": ft.message(rom, ft.MESSAGE_MEDITATE), "WRONG": wrong, "ASK": ask}
    import enemy_model as em

    menu = ft.menu_strings(rom)
    for key, label in (("top", "TOP"), ("names", "NAME"), ("none", "NONE")):
        for i, text in enumerate(menu[key]):
            texts[f"{label}_{i}"] = text
    texts["GLOVE_GONE"], texts["OINTMENT_GONE"] = ft.message(rom, 0xBD), ft.message(rom, 0xBF)       # (IScripts $93 and $95)
    for message in sorted(set(em.Engine.ITEM_MESSAGES.values())):         # what the game says when an item is picked up (the ROM's messages)
        texts[f"MSG_{message:02X}"] = ft.message(rom, message)
    text_blob, text_equ = bytearray(ft.font(rom)), []
    text_blob[8 * (ord('>') - 32):8 * (ord('>') - 32) + 8] = bytes([0x00, 0x10, 0x18, 0xFC, 0xFC, 0x18, 0x10, 0x00])      # the ROM's font has no arrow (its menu cursor is a sprite): '>' is one
    for name, text in texts.items():
        text_equ.append(f"    .equ TEXT_{name}, {len(text_blob)}\n")
        text_blob += text.encode("ascii") + b"\0"
    for ent in range(0x48, 0x61):                  # TEXT of an item's message by entity (0 for what is no item): the table items.s reads
        text_equ.append(f"    .equ ITEMTXT_{ent:02X}, " + (f"TEXT_MSG_{em.Engine.ITEM_MESSAGES[ent]:02X}" if ent in em.Engine.ITEM_MESSAGES else "0") + "\n")
    (args.out / "text.bin").write_bytes(bytes(text_blob))
    (args.out / "random.bin").write_bytes(ed.random_table(rom))
    (args.out / "hero_equip.bin").write_bytes(sc.hero_equip_assets(rom))
    hero = sc.Hero(*[bool(v) if i == 6 else v for i, v in enumerate(int(t) for t in args.hero.split(","))])

    def package(area: int, pal_index: int, building: int | None = None) -> tuple[bytes, list[tuple], int]:
        """The data of an area in a palette set (everything that depends on the colours), as the file the viewer loads: (file, what its doors and
        edges lead to, number of block images). A building's package holds only its own screen, the hero without a weapon."""
        ar = fm.area(rom, area)
        if building is None:
            screens, tiles_index, who, music = world[area], None, hero, fm.music_for(rom, area, pal_index)
            doors, door_targets = door_table(rom, ar, screens, pal_index, world)
            edges, edge_targets = edge_table(rom, ar, screens, world)
        else:
            info = fm.building(rom, building)
            screens, tiles_index, who, music = [building], info["tiles"], dataclasses.replace(hero, weapon=255), info["music"]
            doors, door_targets, edges, edge_targets = b"", [], b"", []
        blocks = b"".join(fm.decode_screen(rom, ar, sid)[:fm.SCREEN_ROWS * fm.SCREEN_COLS] for sid in screens)
        around = bytearray()
        for sid in screens:
            around += bytes(screens.index(n) if n in screens else 0xFF for n in fm.neighbours(rom, ar, sid))
        props = fm.block_properties(rom, ar)
        plan, table, images = sc.build_area_blocks(rom, area, palette_index=pal_index, screens=screens, tiles_index=tiles_index)
        hero_list, hero_images = sc.hero_assets(rom, who, pal_index, plan, args.camera)
        magic, magic_images = sc.magic_anim_assets(rom, pal_index, plan)
        parts = {
            "palette": plan.words(), "screens": bytes(blocks), "neighbours": bytes(around),
            "blocking": b"", "ladders": b"",
            "block_flags": bytes(hp.IMPASSABLE[props[b] & 15] | hp.CLIMBABLE[props[b] & 15] << 1 | (props[b] & 15 == 2) << 2 for b in range(256)),
            "doors": doors, "edges": edges, "block_index": b"".join(v.to_bytes(2, "big") for v in table), "blocks": b"".join(images),
            "hud_tiles": sc.hud_tile_images(rom, pal_index, plan, start["hp"], start["mp"]), "hud_partial": sc.hud_partial_images(rom, pal_index, plan),
            "hero_list": hero_list, "hero_images": hero_images, "hero_colours": sc.hero_colours(rom, pal_index, plan),
            "magic_anim": magic, "magic_images": magic_images,
            **(ed.package_parts(rom, area, screens, pal_index, plan) if building is None else ed.package_parts(rom, area, [None], pal_index, plan)),
        }
        counts = dict(door_count=len(doors) // DOOR_BYTES, screen_count=len(screens), edge_count=len(edges) // EDGE_BYTES, music=music)
        return make_package(parts, counts), door_targets + edge_targets, len(images)

    first = (args.area, a.palette_index)
    initial, targets, n_images = package(*first)
    small = lz.pack(initial)
    names, biggest, packed, over = [package_name(*first)], len(initial), len(small), lz.overrun(small)
    expand = FLAG_ROOM
    (args.out / names[0]).write_bytes(small)
    pending, seen = list(targets), {first}
    while pending:                                   # every package the doors and edges lead to, and those they lead to
        target = pending.pop()
        if target[:2] in seen:
            continue
        seen.add(target[:2])
        data, more, _ = package(*target)
        names.append(package_name(*target[:2]))
        small = lz.pack(data)
        (args.out / names[-1]).write_bytes(small)
        biggest, packed, over = max(biggest, len(data)), max(packed, len(small)), max(over, lz.overrun(small))
        pending += more
    # a package is unpacked where it lies: the packed file sits at the end of the span, and the data never overtakes it
    span = max(-(-biggest // 4) * 4 + expand, -(-packed // 4) * 4 + over + 4)
    span += -span % 4
    layout = gfx.hud_layout(start["hp"], start["mp"], start["experience"], start["gold"], start["seconds"])
    (args.out / "hud_layout.bin").write_bytes(bytes(t for row in layout for t in row))
    (args.out / "assets.inc").write_text(
        f"| generated by tools/build_assets.py from the ROM: area {args.area}, screen {args.screen}\n"
        f"    .equ CAMERA, {args.camera}\n"
        f"    .equ START_SCREEN, {ids.index(args.screen)}\n"
        f"    .equ AREA_INDEX, {args.area}\n"
        f"    .equ PACKAGE_MAX, {-(-biggest // 4) * 4}\n    .equ PACKAGE_EXPAND, {expand}\n    .equ PACKAGE_COMP, {-(-packed // 4) * 4}\n    .equ PACKAGE_SPAN, {span}\n    .equ PACKAGE_AREA, {args.area}\n    .equ PACKAGE_PALETTE, {first[1]}\n"
        + "".join(f"    .equ PKG_{n.upper()}, {4 * i}\n" for i, n in enumerate(PACKAGE_PARTS))
        + "".join(f"    .equ PKG_{n.upper()}, {4 * len(PACKAGE_PARTS) + 2 * i}\n" for i, n in enumerate(HEADER_WORDS))
        + f"    .equ PKG_SIZE, {4 * len(PACKAGE_PARTS) + 2 * len(HEADER_WORDS)}\n"
        + "".join(text_equ) +
        f"    .equ HERO_ARMOUR, {hero.armor}\n    .equ HERO_SHIELD, {hero.shield}\n    .equ HERO_WEAPON, {hero.weapon}\n"
        f"    .equ HERO_X, {hero.x}\n    .equ HERO_Y, {hero.y}\n    .equ HERO_FLIP, {int(hero.left)}\n    .equ HERO_FRAME, {hero.frame % 3}\n", encoding="ascii")
    print(f"area {args.area} screens {ids}: {n_images} block images ({n_images * sc.BLOCK_BYTES} bytes); packages {', '.join(names)} "
          f"(the biggest {biggest} bytes) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
