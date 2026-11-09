#!/usr/bin/env python3
"""Make the YM2149 sound data from the sounds the ROM plays: sound.bin for src/sound.s.

    build_sound.py [--rec build/refnes/sound] [--out build/generated/sound.bin]

tools/record_sounds.py has the ROM's own sound engine play every song and sound effect in the headless NES (tools/refnes/soundrec.mjs)
and writes what each channel sounds like after every frame. This turns that into YM2149 registers, one frame every 20 ms (the PAL
NES also runs its sound engine at 50 Hz, so one NES frame is one ST frame):

    pulse 1 -> tone A, pulse 2 -> tone B, triangle -> tone C (an octave down), noise -> the noise generator on channel C.

A frame is the registers 0-10 (tone periods A, B, C, noise period, mixer, volumes A, B, C). A song is stored as the changes from one frame
to the next: a mask byte (bit 0 period A, 1 B, 2 C, 3 noise, 4 mixer, 5-7 volume A, B, C) and the registers it names (a period is two
bytes). The first frame and the frame a song loops back to have every bit set. A sound effect is plain frames of 12 bytes: the 11
registers and the channels it takes over from the music (bit 0 A, 1 B, 2 C's tone, 3 the noise). A song is cut where it starts to
repeat and loops back to there. Nothing here is committed: it all comes from the ROM.

sound.bin: word n_music, word n_sfx, then a long offset for each song (id 1 up) and each sound effect (id 1 up), then the records:
    song: word frames, word frames from the loop point to the end (0: the song ends), long byte offset of the loop point in the stream, the stream
    sound effect: word frames, byte priority, byte busy, the frames
(the priority is the effect's handler index in the ROM's sound engine, 4 to $70, and a LOWER number wins: the engine refuses a new effect while it
runs one with a lower index, see `Engine`; busy is how many more ticks the engine counts the effect as running after the tick that starts it).
Every record starts on an even address. In the file a song is packed (tools/lz.py; five times smaller): the player unpacks the one it plays
into a buffer of SONG_MAX bytes (`pack_songs`, `unpack_songs`).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import operator
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lz  # noqa: E402

PAL_CPU = 1662607.0                             # the Europe NES; its sound engine's note table is tuned for it
YM_CLOCK = 2000000.0
FRAME = 12
SONG_MAX = 15360                                # the player's buffer for the unpacked song (SND_SONG_MAX in src/sound.s); the biggest song is 15,304

# the NES volume 0-15 as a YM2149 level (3 dB a step); the triangle has no volume, it sounds like a pulse about this loud
TRIANGLE_LEVEL = 12


def ym_volume(v: int) -> int:
    if v <= 0:
        return 0
    return max(1, min(15, round(15 + 20 / 3 * math.log10(v / 15))))


def pulse_period(t: int) -> int:
    return min(4095, max(1, round((t + 1) * YM_CLOCK / PAL_CPU)))


def triangle_period(t: int) -> int:
    return min(4095, max(1, round(2 * (t + 1) * YM_CLOCK / PAL_CPU)))


def noise_period(p: int) -> int:
    return min(31, max(1, round(p * YM_CLOCK / (16 * PAL_CPU))))


def ym_frame(state: list) -> tuple[bytes, int]:
    """A recorded frame ([pulse1, pulse2, triangle, noise]) as the 11 YM registers and the channels that sound: (registers, bits).
    The bits are 1 pulse 1, 2 pulse 2, 4 triangle, 8 noise."""
    (p1, v1, _), (p2, v2, _), (pt, on), (pn, vn, _) = state
    regs = [0] * 11
    bits = 0
    mixer = 0x3F | 0xC0
    for ch, (period, vol) in enumerate(((p1, v1), (p2, v2))):
        if vol > 0 and period:
            f = pulse_period(period)
            regs[ch * 2], regs[ch * 2 + 1] = f & 255, f >> 8
            regs[8 + ch] = ym_volume(vol)
            mixer &= ~(1 << ch)
            bits |= 1 << ch
    volume_c = 0
    if on and pt:
        f = triangle_period(pt)
        regs[4], regs[5] = f & 255, f >> 8
        volume_c = TRIANGLE_LEVEL
        mixer &= ~4
        bits |= 4
    if vn > 0:
        regs[6] = noise_period(pn)
        volume_c = max(volume_c, ym_volume(vn))
        mixer &= ~(8 << 2)
        bits |= 8
    regs[7] = mixer
    regs[10] = volume_c
    return bytes(regs), bits


def music_frames(rec: dict) -> list[bytes]:
    """A song's frames, up to where the ROM stopped it (Music_Current went to 0) or the end of the recording."""
    mc = rec["musicCurrent"]
    n = mc.index(0) if 0 in mc else len(mc)
    frames = [ym_frame(s)[0] + b"\0" for s in rec["state"][:n]]
    if 0 in mc:                                 # a song that ends: its silence is cut and one silent frame ends it (the player goes quiet there)
        while frames and frames[-1][8:11] == b"\0\0\0":
            frames.pop()
        if frames:
            frames.append(frames[-1][:7] + b"\xFF\0\0\0" + b"\0")
    return frames


def find_loop(frames: list[bytes]) -> tuple[int, int] | None:
    """(start, length) of the loop a recording of a song ends in: frames[k] is nearly frames[k + length] for k >= start.
    Nearly, because the NES' length counters tick at a pace of their own and now and then end a note a frame earlier or later; the
    shortest length with the fewest such differences is taken, and the start is after the last stretch of 32 frames of which half differ (an intro shorter than that is taken for part of the loop).
    None when nothing repeats at least once whole."""
    n = len(frames)
    ids = {f: i for i, f in enumerate(dict.fromkeys(frames))}
    a = [ids[f] for f in frames]
    probes = range(0, n, max(1, n // 300))
    ratios = {}
    for length in range(16, n // 2 + 1):
        span = n - length
        if sum(a[k] != a[k + length] for k in probes if k < span) > 0.3 * sum(1 for k in probes if k < span):
            continue
        ratios[length] = sum(map(operator.ne, a, itertools.islice(a, length, None))) / span
    if not ratios:
        return None
    best = min(ratios.values())
    length = min(l for l, r in ratios.items() if r <= best + 0.002)
    diff = [x != y for x, y in zip(a, itertools.islice(a, length, None))]
    start = 0
    for k in range(len(diff) - 32, -1, -1):
        if sum(diff[k:k + 32]) >= 16:                   # a note that comes a frame early or late differs for as long as it lasts: bursts of 20 are jitter
            start = max(j for j in range(k, k + 32) if diff[j]) + 1
            break
    return start, length


def sfx_frames(rec: dict) -> list[bytes]:
    """A sound effect's frames, with the channels it uses marked. It owns a channel from its first sound on it to its last.
    The recording's frame 0 is the frame in which the game asked for the effect: the engine only starts it at the next interrupt, so the
    first frame of the result is the recording's frame 1 (it is the frame the player gives at the first tick after the request)."""
    conv = [ym_frame(s) for s in rec["state"]]
    n = 0
    for i, (_, bits) in enumerate(conv):
        if bits:
            n = i + 1
    first, last = [None] * 4, [-1] * 4
    for i, (_, bits) in enumerate(conv[:n]):
        for b in range(4):
            if bits >> b & 1:
                if first[b] is None:
                    first[b] = i
                last[b] = i
    out = []
    for i in range(n):
        mask = 0
        for b in range(4):
            if first[b] is not None and first[b] <= i <= last[b]:
                mask |= 1 << b
        regs = bytearray(conv[i][0])
        out.append(bytes(regs) + bytes([mask]))
    return out[1:]


def sfx_engine(rec: dict) -> tuple[int, int]:
    """(priority, busy) of a sound effect from the engine's own note (`handler`, soundrec.mjs): the handler index it runs under and the number of
    ticks after the one that starts it for which the engine goes on counting it as running (when it has finished, any new effect is taken)."""
    if "handler" not in rec:
        raise SystemExit("the sound recordings have no `handler` (the engine's priority note): delete build/refnes/sound/s*.json and record again")
    handler = rec["handler"]
    first = next(i for i, v in enumerate(handler) if v)
    end = next((i for i in range(first, len(handler)) if handler[i] == 0), len(handler))
    return handler[first], end - 1


class Engine:
    """What the ROM's sound engine decides about sound effects (`SoundEffects_HandleOnInterrupt`; the code is the same in the US and the Europe ROM) and
    the port's `sound_play_sfx` and `sound_tick` do the same: the game asks for an effect (`SoundEffect_SetCurrent`, which only remembers the last
    one asked for since the last interrupt: its priority table is never used), and at the next interrupt the engine takes it unless it is running
    an effect whose handler index is lower (a lower index is more important; the same index is the same effect, which starts again). An effect
    that is taken replaces the one that ran, which does not come back; one that is refused is forgotten. `effects` maps an id to (priority, busy,
    frames); `tick()` gives the frame (12 bytes with the channel mask) the effect plays at this interrupt, or None."""

    def __init__(self, effects: dict[int, tuple[int, int, list[bytes]]]):
        self.effects = effects
        self.pending = 0
        self.priority = 0
        self.busy = 0                       # ticks left that the engine counts the running effect
        self.frames: list[bytes] = []
        self.at = 0

    def request(self, ident: int) -> None:
        if 0 < ident <= max(self.effects):
            self.pending = ident

    def tick(self) -> bytes | None:
        started = False
        if self.pending:
            priority, busy, frames = self.effects[self.pending]
            self.pending = 0
            if not (self.busy and priority > self.priority):
                self.priority, self.busy, self.frames, self.at = priority, busy, frames, 0
                started = True
        if not started and self.busy:
            self.busy -= 1
        if self.at < len(self.frames):
            self.at += 1
            return self.frames[self.at - 1]
        return None


def delta_stream(frames: list[bytes], full_at: int | None) -> tuple[bytes, int]:
    """The frames as changes; the first frame and frame full_at (the loop point) are written whole. Also the byte offset of full_at."""
    out = bytearray()
    prev = None
    loop_offset = 0
    for i, f in enumerate(frames):
        regs = f[:11]
        if i == full_at:
            loop_offset = len(out)
        if prev is None or i == full_at:
            out.append(0xFF)
            out.extend(regs)
        else:
            mask = 0
            body = bytearray()
            for bit, (a, b) in enumerate(((0, 2), (2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11))):
                if regs[a:b] != prev[a:b]:
                    mask |= 1 << bit
                    body.extend(regs[a:b])
            out.append(mask)
            out.extend(body)
        prev = regs
    return bytes(out), loop_offset


def song_record(frames: list[bytes], loop: int | None) -> bytes:
    stream, loop_offset = delta_stream(frames, loop)
    data = struct.pack(">HHL", len(frames), 0 if loop is None else len(frames) - loop, loop_offset) + stream
    return data + b"\0" * (len(data) & 1)


def sfx_record(frames: list[bytes], priority: int, busy: int) -> bytes:
    return struct.pack(">HBB", len(frames), priority, busy) + b"".join(frames)


def parse_song(data: bytes, offset: int) -> list[bytes]:
    """The frames of a song record (the reader the 68000 code does the same as); the loop is not followed."""
    frames, _, _ = struct.unpack_from(">HHL", data, offset)
    i = offset + 8
    regs = bytearray(11)
    out = []
    for _ in range(frames):
        mask = data[i]
        i += 1
        for bit, (a, b) in enumerate(((0, 2), (2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11))):
            if mask >> bit & 1:
                regs[a:b] = data[i:i + b - a]
                i += b - a
        out.append(bytes(regs))
    return out


def build(rec_dir: Path | None, n_music: int = 16, n_sfx: int = 28) -> tuple[bytes, dict]:
    """The sound data from the recordings in rec_dir; with None, an empty one (no songs, no effects)."""
    if rec_dir is None:
        return struct.pack(">HH", 0, 0), {}
    records = []
    info = {}
    for kind, count, name in (("music", n_music, "m"), ("sfx", n_sfx, "s")):
        for i in range(1, count + 1):
            rec = json.loads((rec_dir / f"{name}{i}.json").read_text())
            if kind == "music":
                frames = music_frames(rec)
                loop = None
                if 0 not in rec["musicCurrent"]:
                    found = find_loop(frames)
                    if found is None:
                        raise SystemExit(f"song {i} does not repeat within {len(frames)} frames: record it for longer")
                    loop = found[0]
                    frames = frames[:found[0] + found[1]]
                data = song_record(frames, loop)
            else:
                frames, loop = sfx_frames(rec), None
                data = sfx_record(frames, *sfx_engine(rec))
            records.append(data)
            info[f"{name}{i}"] = (len(frames), loop, len(data))
    head = struct.pack(">HH", n_music, n_sfx)
    base = len(head) + 4 * len(records)
    offsets = []
    for r in records:
        offsets.append(base)
        base += len(r)
    return head + b"".join(struct.pack(">L", o) for o in offsets) + b"".join(records), info


def _records(data: bytes) -> tuple[int, int, list[bytes]]:
    n_music, n_sfx = struct.unpack_from(">HH", data, 0)
    offsets = [struct.unpack_from(">L", data, 4 + 4 * i)[0] for i in range(n_music + n_sfx)] + [len(data)]
    return n_music, n_sfx, [data[offsets[i]:offsets[i + 1]] for i in range(n_music + n_sfx)]


def _assemble(n_music: int, n_sfx: int, records: list[bytes]) -> bytes:
    base = 4 + 4 * len(records)
    offsets = []
    for r in records:
        offsets.append(base)
        base += len(r)
    return struct.pack(">HH", n_music, n_sfx) + b"".join(struct.pack(">L", o) for o in offsets) + b"".join(records)


def pack_songs(data: bytes) -> bytes:
    """The sound data as it is on the disk and in the program: every song packed (and padded to an even length), the sound effects as they are."""
    n_music, n_sfx, records = _records(data)
    out = []
    for i, r in enumerate(records):
        if i < n_music:
            if len(r) > SONG_MAX:
                raise SystemExit(f"song {i + 1} is {len(r)} bytes: the player's buffer holds {SONG_MAX}")
            r = lz.pack(r)
            r += b"\0" * (len(r) & 1)
        out.append(r)
    return _assemble(n_music, n_sfx, out)


def unpack_songs(data: bytes) -> bytes:
    """What `build` makes, from what `pack_songs` made."""
    n_music, n_sfx, records = _records(data)
    return _assemble(n_music, n_sfx, [lz.unpack(r) if i < n_music else r for i, r in enumerate(records)])


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rec", type=Path, default=root / "build" / "refnes" / "sound")
    parser.add_argument("--out", type=Path, default=root / "build" / "generated" / "sound.bin")
    parser.add_argument("--record", action="store_true",
                        help="record what is missing first (tools/record_sounds.py); when that cannot be done, write a sound.bin without sounds")
    args = parser.parse_args()
    rec_dir = args.rec
    if args.record:
        try:
            import record_sounds
            record_sounds.record(rec_dir)
        except (Exception, SystemExit) as e:
            print(f"build_sound: no sounds ({e}); the ROM, node and the harness's packages are needed", file=sys.stderr)
            rec_dir = None
    data, info = build(rec_dir)
    data = pack_songs(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    for k, (frames, loop, size) in info.items():
        print(f"{k}: {frames} frames, loop {loop}, {size} bytes")
    print(f"{args.out}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
