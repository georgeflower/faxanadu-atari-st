"""The sprites of the intro and of the ending, frame by frame, as the ROM's routines make them (bank 12, Europe addresses).

`SplashAnimation_RunIntro` ($A7E5, the hero walks away up the road) and `RunOutro` ($A97D, the hero walks away down to the left, two sparkles
and a waterfall) are loops of one pass per NMI. Each pass moves the hero in 8.8 fixed point, picks one of the frame descriptors (`Frames`,
tables at $AB62/$AB82) and writes its cells to the sprite list. `Intro` and `Outro` do the same in Python and return the sprites as the
NES' OAM has them: (y, tile, attributes, x) with y the line above the sprite, earlier entries in front. tests/test_splash.py compares them
with jsnes frame by frame (tools/refnes/splashgolden.mjs). The 68000 player is tested against the same lists.

All counts are NMIs: the PAL ROM runs at 50 Hz like the ST, so a tick is one VBL.
"""
from __future__ import annotations

import faxanadu_rom as fr

FRAME_LO, FRAME_HI = 0xAB62, 0xAB82      # 32 frame descriptors: low and high bytes of their addresses
INTRO_FRAMES = 0xA929                     # frame by (size * 4 + (count >> 4) & 3), 5 sizes (US $A8DE)
OUTRO_FRAMES = 0xA946                     # the same for the outro's hero (US $A8FB)
SPARKLE_FRAMES = 0xAA63                   # 2 sparkles x (3 frames + 1 unused) (US $AA18)
INTRO_THRESHOLDS = 0xA8A4                 # y limits for sizes 1-4 (+ a last 0), speeds vx at $A8A9, vy at $A8AD
OUTRO_THRESHOLDS = 0xA8B1                 # y limits (hero y >= limit), vx at $A8B5, vy at $A8B9
SPARKLE_START = 0xA9DF                    # x[2], y[2], vx[2], vy[2]
WATERFALL = (0x18, 0xE0, 0x78)            # first frame (2 frames, swapped every 16 NMIs), x, y
OUTRO_END_Y = 0xFA                        # loop 1 ends when the hero's y reaches this
LOOP3_START_COUNT = 0x10                  # loop 3 sets the interrupt counter to $10 and waits for it to wrap: 240 NMIs
NO_DRAW_Y = 0xF0                          # nothing is drawn at a line of $F0 or more


def s8(v: int) -> int:
    return v - 256 if v > 127 else v


class Data:
    """The tables the engines read, from the Europe ROM (bank 12)."""

    def __init__(self, rom: fr.Rom):
        self.b12 = rom.prg(12)
        self.frames = self._frames()
        self.intro_frame = list(self.at(INTRO_FRAMES, 20))
        self.outro_frame = list(self.at(OUTRO_FRAMES, 20))
        self.sparkle_frame = list(self.at(SPARKLE_FRAMES, 8))
        self.intro_th, self.intro_vx, self.intro_vy = (list(self.at(a, n)) for a, n in ((INTRO_THRESHOLDS, 5), (0xA8A9, 4), (0xA8AD, 4)))
        self.outro_th, self.outro_vx, self.outro_vy = (list(self.at(a, 4)) for a in (OUTRO_THRESHOLDS, 0xA8B5, 0xA8B9))
        s = self.at(SPARKLE_START, 8)
        self.sparkles = [dict(x=s[i], y=s[2 + i], vx=s[4 + i], vy=s[6 + i]) for i in range(2)]

    def at(self, addr: int, n: int) -> bytes:
        return self.b12[addr - 0x8000:addr - 0x8000 + n]

    def _frames(self) -> list[dict]:
        """The 32 frame descriptors: dx, dy (signed), columns, rows, then rows * columns cells (tile, attributes) or None ($FF), row by row."""
        out = []
        for i in range(32):
            p = self.at(FRAME_HI + i, 1)[0] << 8 | self.at(FRAME_LO + i, 1)[0]
            d = self.at(p, 4)
            q, cells = p + 4, []
            for _ in range(d[3]):
                row = []
                for _ in range(d[2]):
                    t = self.at(q, 1)[0]
                    q += 1
                    if t == 0xFF:
                        row.append(None)
                    else:
                        row.append((t, self.at(q, 1)[0]))
                        q += 1
                cells.append(row)
            out.append(dict(addr=p, dx=s8(d[0]), dy=s8(d[1]), cols=d[2], rows=d[3], cells=cells, end=q))
        return out


def draw(data: Data, frame: int, x: int, y: int) -> list[tuple[int, int, int, int]]:
    """`FuncAA94`: the sprites of a frame at the working position (x, y). The ROM adds in 8 bits, writes nothing at all when y + dy is $F0 or more,
    and stops at the first cell that falls to $F0 or more."""
    f = data.frames[frame]
    x = (x + f["dx"]) & 0xFF
    y = (y + f["dy"]) & 0xFF
    if y >= NO_DRAW_Y:
        return []
    out = []
    for row in f["cells"]:
        cx = x
        for cell in row:
            if y >= NO_DRAW_Y:
                return out
            if cell is not None:
                out.append((y, cell[0], cell[1], cx))
            cx = (cx + 8) & 0xFF
        y = (y + 8) & 0xFF
    return out


def step16(hi: int, lo: int, v: int, shift: int) -> tuple[int, int]:
    """(hi:lo) += signed v * 2 ** (8 - shift): 8.8 fixed point (shift 7 for the hero, 1 for the sparkles)."""
    n = (((hi << 8) | lo) + ((s8(v) << 8) >> shift)) & 0xFFFF
    return n >> 8, n & 0xFF


def fade(palette: list[int], steps: int) -> list[int]:
    """The 32 palette bytes after `steps` fade steps: each byte loses $10, a result below 0 is $0F (`LA753`)."""
    out = list(palette)
    for _ in range(steps):
        out = [b - 0x10 if b >= 0x10 else 0x0F for b in out]
    return out


class Intro:
    """`SplashAnimation_RunIntro`. `tick()` is one pass of the loop at $A7F9 and returns (sprites, sound effect or None, done). The hero walks up
    the road in 5 sizes; once he is the smallest the palette fades (all 32 bytes -= $10 every 8th pass, `fades` counts them) and the loop ends
    after 32 more passes."""

    def __init__(self, data: Data):
        self.d = data
        self.x, self.xl, self.y, self.yl = 0x18, 0, 0xFF, 0                 # LA85E
        self.vx, self.vy = 0x20, 0xE0
        self.count = self.size = self.stage = self.fades = self.n = 0
        self.drawn: list[tuple[int, int, int]] = []          # (frame, x, y) of what the last pass drew, in OAM order

    def tick(self) -> tuple[list[tuple[int, int, int, int]], int | None, bool]:
        d = self.d
        self.n += 1
        self.x, self.xl = step16(self.x, self.xl, self.vx, 7)                # LA81A: move, then grow when y is under the limit of this size
        self.y, self.yl = step16(self.y, self.yl, self.vy, 7)
        if self.y < d.intro_th[self.size]:
            self.vx, self.vy = d.intro_vx[self.size], d.intro_vy[self.size]
            self.size += 1
        old = self.count                                                      # LA909: the pose from the count, the footstep
        self.count = (self.count + 1) & 0xFF
        index = self.size * 4 + ((old >> 4) & 3)
        sound = 0x15 if self.size < 3 and index & 1 == 0 and self.count & 15 == 0 else None
        self.drawn = [(d.intro_frame[index], self.x, self.y)]
        sprites = draw(d, *self.drawn[0])
        done = False
        if self.size == 4:                                                    # LA753
            self.stage += 1
            if self.stage & 7 == 0:
                self.fades += 1
            done = self.stage == 0x20
        return sprites, sound, done


class Outro:
    """`SplashAnimation_RunOutro`: loop 1 (the hero walks until his y is $FA), loop 2 (no hero, until the song ends: `music_ticks` passes in
    all, the ROM's sound engine clears Music_Current), loop 3 (240 more passes: the interrupt counter is set to $10 and the loop waits for it to
    wrap). The waterfall's frame is `$18 + ((interrupt counter & $10) >> 4)`; `count` is that counter, which runs free (+1 each pass, before the
    pass draws) and is set to $10 at the start of loop 3. `tick()` returns the sprites (`drawn` has what they were made of: (frame, x, y), in OAM order);
    `done` is set after the last pass, whose sprites the ROM never shows (it goes on to Game_Init)."""

    def __init__(self, data: Data, music_ticks: int, count: int = 0):
        self.d = data
        self.music_ticks = music_ticks
        self.x, self.xl, self.y, self.yl = 0x70, 0, 0xAE, 0                  # LA881
        self.vx, self.vy = 0xFD, 0x01
        self.hcount = self.size = self.n = 0
        self.count = count
        self.hero = True
        self.loop = 1
        self.done = False
        self.sparkle = [dict(ph=0, cnt=0, xl=0, yl=0, **s) for s in data.sparkles]

    def tick(self) -> list[tuple[int, int, int, int]]:
        d = self.d
        self.n += 1
        self.count = (self.count + 1) & 0xFF                                  # the wait for the NMI
        sprites: list[tuple[int, int, int, int]] = []
        self.drawn = []
        if self.loop == 1:                                                    # LA83C then LA93D
            self.x, self.xl = step16(self.x, self.xl, self.vx, 7)
            self.y, self.yl = step16(self.y, self.yl, self.vy, 7)
            if self.size < 4 and self.y >= (d.outro_th + [0xFB])[self.size]:
                self.vx, self.vy = d.outro_vx[self.size], d.outro_vy[self.size]
                self.size += 1
            old = self.hcount
            self.hcount = (self.hcount + 1) & 0xFF
            self.drawn.append((d.outro_frame[self.size * 4 + ((old >> 4) & 3)], self.x, self.y))
        for i, s in enumerate(self.sparkle):                                  # LAA14: move, count 8 passes a phase, 10 phases, then start again
            s["x"], s["xl"] = step16(s["x"], s["xl"], s["vx"], 1)
            s["y"], s["yl"] = step16(s["y"], s["yl"], s["vy"], 1)
            nxt = s["cnt"] + 1
            if nxt == 8:
                s["ph"] += 1
                if s["ph"] == 10:
                    s.update(ph=0, cnt=0, xl=0, yl=0, **d.sparkles[i])
                    continue
                nxt = 0
            s["cnt"] = nxt
        for i, s in enumerate(self.sparkle):                                  # LAA3D: phases 0-2 show a frame
            if s["ph"] < 3:
                self.drawn.append((d.sparkle_frame[i * 4 + s["ph"]], s["x"], s["y"]))
        first, x, y = WATERFALL                                               # LAAB7
        self.drawn.append((first + ((self.count & 0x10) >> 4), x, y))
        for frame, fx, fy in self.drawn:
            sprites += draw(d, frame, fx, fy)
        if self.loop == 1 and self.y >= OUTRO_END_Y:
            self.loop = 2
            self.hero = False
        elif self.loop == 2 and self.n >= self.music_ticks:
            self.loop = 3
            self.count = LOOP3_START_COUNT
        elif self.loop == 3 and self.count == 0:
            self.done = True
        return sprites
