#!/usr/bin/env python3
"""Make the ST data of one Faxanadu screen from your ROM, for the viewer (src/viewer.s).

    build_assets.py [--rom ext/Faxanadu_Europe.nes] [--area 0] [--screen 1] [--camera 40] [--out build/generated]

Writes hero_list.bin and hero_images.bin (the hero's sprites for the ST), hud_tiles.bin (the 60 HUD tiles, 32 bytes each) and hud_layout.bin (its 4 rows of 32 tile ids, as at the start of a game),
palette.bin (16 ST colour words), blocks.bin (the 128-byte block images the screen uses), block_index.bin (1024 words:
image number of (block id * 4 + corner), $FFFF for none), screen.bin (the screen's 13 rows of 16 block ids) and assets.inc
(the numbers the assembly needs). Nothing here is committed: it all comes from the ROM and is rebuilt on each build.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faxanadu_gfx as gfx  # noqa: E402
import faxanadu_maps as fm
import hero_physics as hp  # noqa: E402
import faxanadu_rom as fr  # noqa: E402
import st_convert as sc  # noqa: E402


DOOR_BYTES = 8
DOOR_SAME, DOOR_PALETTE, DOOR_BUILDING, DOOR_OUTSIDE = 0, 1, 2, 3


def door_table(rom: fr.Rom, a: fm.Area, ids: list[int], palette_index: int | None = None) -> bytes:
    """The doors on the screens in `ids`, 8 bytes each: screen (its number in the tables), block (row * 16 + column), kind, the screen it
    leads to (its number in the tables, or the ROM's for another area), where the hero stands there (Y/16 << 4 | X/16), the destination's palette,
    the key it needs (`Game_RunDoorRequirementHandler`'s number), a pad. Kinds (`Player_CheckHandleEnterDoor`): 0 another screen of this area in
    the area's palette, 1 the same with another palette, 2 a building (the destination index is 32 or more; area 3's are all), 3 back outside
    (index $FE or $FF). Kind 0 or 1 is relative to `palette_index`, the palette set in use (the area's own by default). A door whose destination
    screen is not in `ids` is left out."""
    palette_index = a.palette_index if palette_index is None else palette_index
    out = bytearray()
    for d in fm.doors(rom, a):
        if d.screen not in ids:
            continue
        if d.destination >= 0xFE:
            out += bytes([ids.index(d.screen), d.block, DOOR_OUTSIDE, 0xFF, d.start, 0xFF, 0, 0])
            continue
        if d.destination >= 0x20 or a.index == 3:
            building = d.destination
            out += bytes([ids.index(d.screen), d.block, DOOR_BUILDING, building & 0xFF, d.start, 0xFF, 0, 0])
            continue
        screen, palette, key, _ = fm.door_destination(rom, a, d)
        if screen not in ids:
            continue
        kind = DOOR_SAME if palette == palette_index else DOOR_PALETTE
        out += bytes([ids.index(d.screen), d.block, kind, ids.index(screen), d.start, palette, key, 0])
    return bytes(out)


PACKAGE_PARTS = ("palette", "screens", "neighbours", "blocking", "ladders", "doors", "block_index", "blocks", "hud_tiles", "hud_partial",
                 "hero_list", "hero_images", "hero_anim", "hero_anim_images")


def package_name(area: int, palette: int) -> str:
    return f"A{area}P{palette:02d}.DAT"


def make_package(parts: dict[str, bytes], door_count: int, screen_count: int) -> bytes:
    """An area's data in one palette set as one block: a long offset from its start for each of PACKAGE_PARTS, the number of doors and of
    screens (words), then the parts, each on a multiple of 4."""
    head = 4 * len(PACKAGE_PARTS) + 4
    offsets, body = [], bytearray()
    for name in PACKAGE_PARTS:
        offsets.append(head + len(body))
        body += parts[name]
        body += b"\0" * (-len(body) % 4)
    return b"".join(o.to_bytes(4, "big") for o in offsets) + door_count.to_bytes(2, "big") + screen_count.to_bytes(2, "big") + bytes(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, default=fr.DEFAULT_ROM)
    parser.add_argument("--area", type=int, default=0)
    parser.add_argument("--screen", type=int, default=1)
    parser.add_argument("--camera", type=int, default=40, help="first line of the 208-line playfield shown in the 168-line window (0-40)")
    parser.add_argument("--hero", default="144,144,0,255,0,0,1",
                        help="the hero: x,y,armour,shield,weapon,frame,faces-left (default: where he stands after the castle door, start equipment)")
    parser.add_argument("--reach", type=int, default=2, help="screens within this many steps of --screen are included (the viewer can scroll between them)")
    parser.add_argument("--all", action="store_true", help="every screen of the area (their numbers in the tables are the ROM's)")
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
    blocks = b"".join(fm.decode_screen(rom, a, sid)[:fm.SCREEN_ROWS * fm.SCREEN_COLS] for sid in ids)
    around = bytearray()
    for sid in ids:
        around += bytes(ids.index(n) if n in ids else 0xFF for n in fm.neighbours(rom, a, sid))
    args.out.mkdir(parents=True, exist_ok=True)
    props = fm.block_properties(rom, a)
    keys = ("hp", "mp", "experience", "gold", "seconds")
    start = dict(zip(keys, (int(v) for v in args.hud.split(","))))
    second = dict(zip(keys, (int(v) for v in args.hud2.split(",")))) if args.hud2 else start
    (args.out / "hud_states.bin").write_bytes(sc.hud_state_bytes(start) + sc.hud_state_bytes(second))
    hero = sc.Hero(*[bool(v) if i == 6 else v for i, v in enumerate(int(t) for t in args.hero.split(","))])

    def package(pal_index: int) -> tuple[bytes, int, bytes]:
        """The data of this area in this palette set (everything that depends on the colours), as the file the viewer loads."""
        doors = door_table(rom, a, ids, pal_index)
        plan, table, images = sc.build_area_blocks(rom, args.area, palette_index=pal_index, screens=ids)
        hero_list, hero_images = sc.hero_assets(rom, hero, pal_index, plan, args.camera)
        anim, anim_images = sc.hero_anim_assets(rom, hero, pal_index, plan)
        parts = {
            "palette": plan.words(), "screens": bytes(blocks), "neighbours": bytes(around),
            "blocking": bytes(hp.IMPASSABLE[props[b] & 15] for b in blocks),          # 1 a block he cannot walk through
            "ladders": bytes(hp.CLIMBABLE[props[b] & 15] for b in blocks),             # 1 a ladder
            "doors": doors, "block_index": b"".join(v.to_bytes(2, "big") for v in table), "blocks": b"".join(images),
            "hud_tiles": sc.hud_tile_images(rom, pal_index, plan, start["hp"], start["mp"]), "hud_partial": sc.hud_partial_images(rom, pal_index, plan),
            "hero_list": hero_list, "hero_images": hero_images, "hero_anim": anim, "hero_anim_images": anim_images,
        }
        return make_package(parts, len(doors) // DOOR_BYTES, len(ids)), len(images), doors

    pal_index = a.palette_index
    initial, n_images, first_doors = package(pal_index)
    names = [package_name(args.area, pal_index)]
    (args.out / names[0]).write_bytes(initial)
    biggest = len(initial)
    if args.all:        # the palettes the area's doors lead to, and those their doors lead to
        pending = [first_doors]
        while pending:
            doors = pending.pop()
            for d in range(0, len(doors), DOOR_BYTES):
                if doors[d + 2] == DOOR_PALETTE and package_name(args.area, doors[d + 5]) not in names:
                    names.append(package_name(args.area, doors[d + 5]))
                    data, _, more = package(doors[d + 5])
                    (args.out / names[-1]).write_bytes(data)
                    biggest = max(biggest, len(data))
                    pending.append(more)
    layout = gfx.hud_layout(start["hp"], start["mp"], start["experience"], start["gold"], start["seconds"])
    (args.out / "hud_layout.bin").write_bytes(bytes(t for row in layout for t in row))
    (args.out / "assets.inc").write_text(
        f"| generated by tools/build_assets.py from the ROM: area {args.area}, screen {args.screen}\n"
        f"    .equ CAMERA, {args.camera}\n"
        f"    .equ START_SCREEN, {ids.index(args.screen)}\n"
        f"    .equ AREA_INDEX, {args.area}\n"
        f"    .equ PACKAGE_MAX, {biggest}\n    .equ PACKAGE_PALETTE, {pal_index}\n"
        + "".join(f"    .equ PKG_{n.upper()}, {4 * i}\n" for i, n in enumerate(PACKAGE_PARTS))
        + f"    .equ PKG_DOOR_COUNT, {4 * len(PACKAGE_PARTS)}\n    .equ PKG_SCREEN_COUNT, {4 * len(PACKAGE_PARTS) + 2}\n    .equ PKG_SIZE, {4 * len(PACKAGE_PARTS) + 4}\n"
        f"    .equ PACKAGE_NAME_AREA, {args.area}\n"
        f"    .equ HERO_X, {hero.x}\n    .equ HERO_Y, {hero.y}\n    .equ HERO_FLIP, {int(hero.left)}\n    .equ HERO_FRAME, {hero.frame % 3}\n", encoding="ascii")
    print(f"area {args.area} screens {ids}: {n_images} block images ({n_images * sc.BLOCK_BYTES} bytes); packages {', '.join(names)} "
          f"(the biggest {biggest} bytes) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
