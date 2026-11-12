#!/usr/bin/env python3
"""The ROM and the port side by side: one segment of play, the same buttons in both, the state of every frame compared.

    python3 tools/sidebyside.py SEGMENT.json [--out DIR] [--shots N] [--video]

The ROM side (`tools/refnes/botplay.mjs`) puts a game in play, writes the segment's start state into the RAM (a cheat: place, power, magic, experience,
gold, rank, equipment), loads the screen's sprites afresh, and plays: a bot (policy "fight": walk to the nearest enemy, swing when near, pick up the drop)
or a stream of pads (policy "pads"). It writes the pads it pressed and a trace. The port is built with `--defsym REPLAY=n` (src/replay.s, never on the
disk), its start state from the same segment (HERO=, HUD=, AREA=, SCREEN=), and plays the same pads, one a poll of the main loop; its trace is read from
Hatari's memory at the end. Both traces have the record layout of src/replay.s: record k is the state after k frames, before the pad of frame k.

The comparison resynchronises at screen changes (a scroll or a door can take a different number of frames on the ST by design, AGENTS.md section 8 and
5d): from the n-th change of screen on, record k of the port is compared with record k + d of the ROM, d the difference of the n-th change. The pads stay
those of the ROM's frames, so after such an event the port gets them d frames early or late: a long segment through doors needs the stream re-timed
(`retime`, the port's stream gets d pads of 0 more or fewer before the event; `--retime` does one pass of it).

SEGMENT (JSON): area, screen, x, y, left (the flip bit: 1 faces left), hp, mp, exp, gold, title, weapon (255: none), armour, shield (255: none), magic,
item, frames, policy, pads (a file, policy "pads"), reach (the bot's), jump (the bot jumps at enemies), heal (power under 40 is made 80 at the start of a pass, on both
sides), world ("1,2,3": the WORLD of the build), all (ALL=1), defs (more VIEWER_DEFS).

Output (DIR, default build/sidebyside/NAME): rom/ (pads.bin, trace.bin, the ROM's pictures), port_trace.bin, report.txt (the first divergence of each
field with the frames round it), side_NNNNN.png (NES left, ST right, the same frame) and, with --video, sidebyside.mp4.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import hatari_shot as hs  # noqa: E402

REC = 64
RING, STEP = 256, 150                                                   # the port's ring of records (src/replay.s) and how often it is read
SLOT_FIELDS = ("ent", "x", "y", "hp")


def decode(trace: bytes) -> list[dict]:
    """The records of a trace as dicts (the fields of src/replay.s)."""
    out = []
    for k in range(len(trace) // REC):
        r = trace[k * REC:(k + 1) * REC]
        d = {"x": int.from_bytes(r[0:2], "big"), "y": int.from_bytes(r[2:4], "big"), "facing": r[4], "area": r[5], "screen": r[6], "hp": r[7], "mp": r[8],
             "hpl": r[9], "exp": int.from_bytes(r[10:12], "big"), "gold": int.from_bytes(r[12:16], "big"), "music": r[48], "spell": r[49],
             "spell_x": r[50], "spell_y": r[51], "vbl": int.from_bytes(r[52:56], "big"), "xf": r[56], "acc": int.from_bytes(r[57:59], "big"), "s6_xf": r[59], "s7_xf": r[60]}
        for i in range(8):
            for j, f in enumerate(SLOT_FIELDS):
                d[f"s{i}_{f}"] = r[16 + i * 4 + j]
        out.append(d)
    return out


# Fields compared, and what is let off: an empty slot's other bytes, the spell's place when there is none; the ROM's music byte is Music_Current, which
# the ROM clears when a song ends, the port's the song it started (not compared); hpl is the power's fraction (compared).
COMPARED = ["s6_xf", "s7_xf", "x", "xf", "acc", "y", "facing", "area", "screen", "hp", "mp", "hpl", "exp", "gold", "spell"] + [f"s{i}_{f}" for i in range(8) for f in SLOT_FIELDS]


def value(rec: dict, field: str):
    if field.startswith("s") and field[1].isdigit():                    # (s6_xf and s7_xf: the fraction of slots 6 and 7, empty or not)
        if field.endswith("_xf"):
            return rec[field]
        slot = field[:2]
        if rec[f"{slot}_ent"] == 255 and not field.endswith("_ent"):
            return None
    if field == "spell" and rec["spell"] == 255:
        return 255
    return rec[field]


def screen_changes(recs: list[dict]) -> list[int]:
    return [k for k in range(1, len(recs)) if (recs[k]["area"], recs[k]["screen"]) != (recs[k - 1]["area"], recs[k - 1]["screen"])]


def offsets(rom: list[dict], port: list[dict]) -> list[tuple[int, int]]:
    """(from port record, d): from that record on the port's k is the ROM's k + d."""
    out = [(0, 0)]
    for a, b in zip(screen_changes(rom), screen_changes(port)):
        out.append((b, a - b))
    return out


def compare(rom: list[dict], port: list[dict]) -> dict:
    """For each field the first port record that differs from its ROM record: {field: (port k, rom k, rom value, port value)}; and the counts."""
    offs = offsets(rom, port)
    first: dict = {}
    differ = {f: 0 for f in COMPARED}
    compared = 0
    for k, p in enumerate(port):
        d = [o for start, o in offs if start <= k][-1]
        if not 0 <= k + d < len(rom):
            continue
        r = rom[k + d]
        compared += 1
        for f in COMPARED:
            if value(r, f) != value(p, f):
                differ[f] += 1
                first.setdefault(f, (k, k + d, value(r, f), value(p, f)))
    return {"first": first, "differ": differ, "compared": compared, "offsets": offs}


def context(rom: list[dict], port: list[dict], k_port: int, k_rom: int, fields: list[str], n: int = 3) -> str:
    lines = []
    for j in range(-n, n + 1):
        kp, kr = k_port + j, k_rom + j
        if 0 <= kp < len(port) and 0 <= kr < len(rom):
            lines.append(f"    port {kp:5d} / rom {kr:5d}: " + "  ".join(f"{f} {value(rom[kr], f)}|{value(port[kp], f)}" for f in fields))
    return "\n".join(lines)


def report(rom: list[dict], port: list[dict], pads: bytes) -> str:
    c = compare(rom, port)
    out = [f"{c['compared']} frames compared; offsets at screen changes (port record, rom - port): {c['offsets']}"]
    if not c["first"]:
        out.append("every compared field agrees in every frame")
    for f, (kp, kr, a, b) in sorted(c["first"].items(), key=lambda t: t[1][0]):
        group = [g for g in COMPARED if g == f or (f[:2] == g[:2] and f[0] == "s")] if f.startswith("s") and f[1].isdigit() else ["x", "y", "hp", f]
        group = list(dict.fromkeys(group))
        out.append(f"{f}: first differs at port frame {kp} (rom frame {kr}): rom {a}, port {b}; differs in {c['differ'][f]} frames; pad {pads[kr]:#04x}" if kr < len(pads) else f"{f}: port {kp} rom {kr}")
        out.append(context(rom, port, kp, kr, group))
    return "\n".join(out)


def make_args(seg: dict, frames: int) -> list[str]:
    hero = f"{seg['x']},{seg['y']},{seg.get('armour', 0)},{seg.get('shield', 255)},{seg.get('weapon', 255)},0,{seg.get('left', 0)}"
    hud = f"{seg.get('hp', 80)},{seg.get('mp', 0)},{seg.get('exp', 0)},{seg.get('gold', 0)},0"
    defs = f"--defsym REPLAY={frames}"
    for key, sym in (("title", "TITLE"), ("magic", "MAGIC"), ("item", "ITEM")):
        if seg.get(key) not in (None, 0) or (key == "magic" and seg.get(key) is not None):
            defs += f" --defsym {sym}={seg[key]}"
    if seg.get("heal"):
        defs += " --defsym REPLAY_HEAL=1"                            # (both sides: botplay.mjs heals the ROM's hero at the same place of the pass)
    defs += " " + seg.get("defs", "")
    args = [f"AREA={seg['area']}", f"SCREEN={seg['screen']}", f"HERO={hero}", f"HUD={hud}", f"VIEWER_DEFS={defs.strip()}"]
    if seg.get("all", True) or seg.get("world"):
        args.append("ALL=1")                                            # (then the port's screen numbers are the ROM's)
    if seg.get("world"):
        args.append(f"WORLD={seg['world']}")
    return args


def run_rom(seg_file: Path, out: Path) -> tuple[bytes, list[dict]]:
    subprocess.run(["node", str(ROOT / "tools" / "refnes" / "botplay.mjs"), str(seg_file), str(out)], check=True, capture_output=True, cwd=ROOT / "tools" / "refnes")
    return (out / "pads.bin").read_bytes(), decode((out / "trace.bin").read_bytes())


class Port:
    """The port built with the stream and run in Hatari (EmuTOS, the TOS environment variable)."""

    def __init__(self, seg: dict, pads: bytes, work: Path):
        self.seg, self.pads, self.work = seg, pads, work
        gen = ROOT / "build" / "generated"
        gen.mkdir(parents=True, exist_ok=True)
        (gen / "replay.bin").write_bytes(pads)
        subprocess.run(["make", "-C", str(ROOT), "viewer", *make_args(seg, len(pads))], check=True, capture_output=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        self.sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        self.image = (ROOT / "build" / "viewer.bin").read_bytes()
        self.prg = ROOT / "build" / "VIEWER.PRG"
        self.hatari = shutil.which("hatari")
        self.tos = Path(__import__("os").environ.get("TOS", ""))
        work.mkdir(parents=True, exist_ok=True)
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        hs.run_hatari(self.hatari, self.tos, self.prg, work, 500, "0", f"b VBL > 499 :once :file {work / 'c0.ini'}\n", None)
        ram = (work / "ram0.bin").read_bytes()
        self.base = ram.find(self.image[self.sym["start"]:self.sym["start"] + 48]) - self.sym["start"]
        assert self.base > 0, "the program is in memory"

    def captures(self, vbls: list[int], name: str) -> list[tuple[bytes, list[list[int]], list[int]]]:
        """RAM, screen rows and palette at each VBL (at most 15 a run: Hatari's breakpoints)."""
        out = []
        for start in range(0, len(vbls), 15):
            part = vbls[start:start + 15]
            script = ""
            for i, vbl in enumerate(part):
                (self.work / f"{name}{i}.ini").write_text(f"savebin {self.work / f'{name}_{i}.bin'} 0 $80000\nm $ff8200-$ff8270\ncont\n", encoding="utf-8")
                script += f"b VBL > {vbl} :once :file {self.work / f'{name}{i}.ini'}\n"
            log = hs.run_hatari(self.hatari, self.tos, self.prg, self.work, max(part) + 1, "0", script, None)
            chunks = re.split(r"(?m)^(?=00FF8200:)", log)[1:]
            assert len(chunks) == len(part), "every capture was made"
            for i, chunk in enumerate(chunks):
                ram = (self.work / f"{name}_{i}.bin").read_bytes()
                out.append((ram, hs.decode_screen(ram, hs.video_base(chunk)), hs.read_palette(chunk)))
        return out

    def trace(self) -> tuple[list[dict], int]:
        """The whole trace and the offset from frame_count to Hatari's VBL. The port keeps the last RING records (src/replay.s), so the RAM is read
        every STEP VBLs from VBL 300 (a pass of the loop takes at least a VBL, so no record is overwritten between two reads) until the stream has been played."""
        n = len(self.pads)
        recs: list[dict] = []
        at = self.base + self.sym["replay_trace"]
        vbls = [300 + STEP * k for k in range(0, (n + 400) // STEP + 3)]
        while True:
            caps = self.captures(vbls, "end")
            got, ram = 0, None
            for ram, _, _ in caps:
                count = int.from_bytes(ram[self.base + self.sym["replay_count"]:self.base + self.sym["replay_count"] + 2], "big")
                assert count - got <= RING, "the ring was read in time"
                for k in range(got, min(count, n)):
                    recs.append(decode(ram[at + (k % RING) * REC:at + (k % RING + 1) * REC])[0])
                got = max(got, min(count, n))
            if got >= n or len(vbls) > 60:
                break
            vbls += [vbls[-1] + STEP * k for k in range(1, (n - got) // STEP + 3)]
        frame_count = int.from_bytes(ram[self.base + self.sym["frame_count"]:self.base + self.sym["frame_count"] + 4], "big")
        return recs, vbls[-1] + 1 - frame_count


def st_png(rows: list[list[int]], palette: list[int]):
    from PIL import Image

    img = Image.new("RGB", (320, 200))
    rgb = [(((c >> 8) & 7) * 255 // 7, ((c >> 4) & 7) * 255 // 7, (c & 7) * 255 // 7) for c in palette]
    img.putdata([rgb[p] for row in rows for p in row])
    return img


def side_by_side(nes_ppm: Path, st, label: str):
    from PIL import Image, ImageDraw

    nes = Image.open(nes_ppm).convert("RGB")
    out = Image.new("RGB", (256 * 2 + 320 * 2 + 16, 480 + 20), (24, 24, 24))
    out.paste(nes.resize((512, 480), Image.NEAREST), (0, 20))
    out.paste(st.resize((640, 400), Image.NEAREST), (528, 20 + 40))
    ImageDraw.Draw(out).text((4, 4), label, fill=(230, 230, 230))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("segment", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--shots", type=int, default=0, help="a side-by-side picture every N frames (0: none)")
    ap.add_argument("--video", action="store_true", help="and an mp4 of them (ffmpeg)")
    args = ap.parse_args()
    seg = json.loads(args.segment.read_text(encoding="utf-8"))
    out = args.out or ROOT / "build" / "sidebyside" / args.segment.stem
    out.mkdir(parents=True, exist_ok=True)
    seg_file = out / "segment.json"
    seg_file.write_text(json.dumps(dict(seg, png_every=args.shots)), encoding="utf-8")
    pads, rom = run_rom(seg_file, out / "rom")
    port = Port(seg, pads, out / "hatari")
    recs, offset = port.trace()
    (out / "port_trace.json").write_text(json.dumps(recs), encoding="utf-8")
    text = report(rom, recs, pads)
    (out / "report.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.shots:
        frames = list(range(args.shots, min(len(recs), len(rom)), args.shots))
        caps = port.captures([recs[f]["vbl"] + offset for f in frames], "pic")
        names = []
        for f, (_, rows, palette) in zip(frames, caps):
            img = side_by_side(out / "rom" / f"rom_{f:05d}.ppm", st_png(rows, palette), f"frame {f}   NES (left)   ST (right)")
            name = out / f"side_{f:05d}.png"
            img.save(name)
            names.append(name)
        if args.video and names and shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "5", "-pattern_type", "glob", "-i", str(out / "side_*.png"), "-pix_fmt", "yuv420p",
                            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", str(out / "sidebyside.mp4")], check=True)
        print(f"{len(names)} pictures in {out}")


if __name__ == "__main__":
    main()
