#!/usr/bin/env python3
"""Dump the graphics of your ROM to PNG sheets (nothing is committed: `build/graphics/` is ignored).

    python3 tools/dump_graphics.py [OUT_DIR]

- bank_NN.png        every 8x8 tile of a PRG bank (4, 6, 7, 8, 9, 10, 12, 13; 2 bits a pixel, grey), 32 tiles a row, tile number = row * 32 + column
- tileset_N.png      the nine area tilesets (bank 4) in the four background palettes of the first area that uses them, tile numbers as the game loads them
- sprites_NAME.png   the labelled sprite tiles of banks 6-8 (enemies, NPCs, the hero's armour, weapons and shields, portraits), one sheet a group,
                     with a fixed four-colour palette (the game picks the real one per sprite)
- hud_and_text.png   the 60 HUD and letter tiles (bank 10)
- index.txt          what is where

Needs Pillow (`pip install pillow`).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faxanadu_maps as fm  # noqa: E402
import faxanadu_rom as fr  # noqa: E402
import render_screen as rs  # noqa: E402
from nes_palette import NES_RGB  # noqa: E402

GREY = [(0, 0, 0), (96, 96, 96), (176, 176, 176), (255, 255, 255)]
SPRITE = [(40, 40, 60), (200, 60, 50), (240, 170, 60), (250, 240, 220)]
SCALE = 3


def tile_sheet(tiles: list[bytes], palette: list[tuple[int, int, int]], per_row: int, scale: int = SCALE, gap: int = 0) -> Image.Image:
    rows = (len(tiles) + per_row - 1) // per_row
    cell = 8 * scale + gap
    img = Image.new("RGB", (per_row * cell, max(rows, 1) * cell), (24, 24, 24))
    px = img.load()
    for n, data in enumerate(tiles):
        if len(data) < 16:
            continue
        pixels = rs.decode_tile(data)
        ox, oy = (n % per_row) * cell, (n // per_row) * cell
        for y in range(8):
            for x in range(8):
                c = palette[pixels[y][x]]
                for dy in range(scale):
                    for dx in range(scale):
                        px[ox + x * scale + dx, oy + y * scale + dy] = c
    return img


def tiles_of(data: bytes) -> list[bytes]:
    return [data[i:i + 16] for i in range(0, len(data) - 15, 16)]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "build" / "graphics"
    out.mkdir(parents=True, exist_ok=True)
    rom = fr.Rom()
    index: list[str] = []

    for bank in (4, 6, 7, 8, 9, 10, 12, 13):
        sheet = tile_sheet(tiles_of(rom.prg(bank)), GREY, 32, 2)
        sheet.save(out / f"bank_{bank:02d}.png")
        index.append(f"bank_{bank:02d}.png: all 1024 tiles of PRG bank {bank} (code and data show as noise)")

    # the nine tilesets, each in the four background palettes of the first area that uses it
    seen: dict[int, int] = {}
    for ai in range(8):
        a = fm.area(rom, ai)
        seen.setdefault(a.tiles_index, ai)
    for tiles_index, ai in sorted(seen.items()):
        a = fm.area(rom, ai)
        ts = rs.tileset(rom, tiles_index)
        pals = rs.bg_palettes(rom, a.palette_index)
        first = min(ts)
        count = max(ts) - first + 1
        panels = []
        for pal in pals:
            colours = [NES_RGB[c & 0x3F] for c in pal]
            raw = []
            for i in range(count):
                t = ts.get(first + i)
                raw.append(bytes(0) if t is None else _encode(t))
            panels.append(tile_sheet(raw, colours, 16, 2))
        w = sum(p.width for p in panels) + 8 * (len(panels) - 1)
        img = Image.new("RGB", (w, panels[0].height), (24, 24, 24))
        x = 0
        for p in panels:
            img.paste(p, (x, 0))
            x += p.width + 8
        img.save(out / f"tileset_{tiles_index}.png")
        index.append(f"tileset_{tiles_index}.png: tileset {tiles_index} (area {ai}), tiles ${first:02X}-${first + count - 1:02X}, 16 a row, four palettes side by side")

    # labelled sprite tiles
    labels = fr.labels()
    groups: dict[str, list[tuple[int, bytes]]] = {}
    for name, lab in sorted(labels.items(), key=lambda kv: (kv[1].bank, kv[1].addr, kv[0])):
        if lab.bank not in (6, 7, 8) or "TILES" not in name or name.endswith("_START") or "_REF" in name:
            continue
        m = re.match(r"(.*?)(?:_(\d+))?$", name)
        base = m.group(1)
        data = rom.data[lab.offset:lab.offset + 16]
        groups.setdefault(base, []).append((lab.offset, data))
    done = 0
    for base, items in sorted(groups.items()):
        uniq = sorted({o: d for o, d in items}.items())
        tiles = [d for _, d in uniq]
        if not tiles:
            continue
        sheet = tile_sheet(tiles, SPRITE, min(16, len(tiles)), 4, 2)
        safe = base.replace("SPRITE_TILES_", "").replace("TILES_", "").lower()
        sheet.save(out / f"sprites_{safe}.png")
        done += 1
        index.append(f"sprites_{safe}.png: {len(tiles)} tiles (label {base}_NN)")

    # HUD and the text font
    hud = tiles_of(rom.at("HUD_TILES_START", 60 * 16))
    sheet = tile_sheet(hud, GREY, 16, 4, 2)
    sheet.save(out / "hud_and_text.png")
    index.append("hud_and_text.png: the 60 HUD and letter tiles (bank 10). The text font of the Europe ROM (banks 12 and 13 differ from the US build) is on bank_12.png / bank_13.png, not located yet")

    (out / "index.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Wrote {len(index)} sheets to {out} ({done} sprite groups)")
    return 0


def _encode(pixels: list[list[int]]) -> bytes:
    lo = bytearray(8)
    hi = bytearray(8)
    for y in range(8):
        for x in range(8):
            lo[y] |= (pixels[y][x] & 1) << (7 - x)
            hi[y] |= ((pixels[y][x] >> 1) & 1) << (7 - x)
    return bytes(lo + hi)


if __name__ == "__main__":
    raise SystemExit(main())
