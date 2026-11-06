"""The hero's movement as the ROM does it, in Python: the reference the ST code is checked against (golden runs from the jsnes harness,
`tools/refnes/walkgolden.mjs`). Positions are 8.8 fixed point: `x` (the game's Player_PosX_Block) and `frac` (Player_PosX_Frac).

Read from `Player_CheckHandleJump`, `Player_TryMoveRight/Left`, `Player_UpdateAcceleration`, `Player_CheckIfPassable` and the `Area_CanPlayerMove*`
routines. Not here yet: jumping and falling, ladders, knockback, flying, the screen edges' neighbour columns (the hero is taken as free to move
there; the caller sees `edge` when he has walked off), crouching.
"""
from __future__ import annotations

from dataclasses import dataclass

IMPASSABLE = (0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0)     # BLOCK_PROPERTY_IMPASSABLE_MAP, by block property
ACCELERATION_DELTA = (2, 4, 6, 8)                                  # PLAYER_ACCELERATION_DELTA_BY_RANK_GROUP

JOY_RIGHT, JOY_LEFT, JOY_DOWN, JOY_UP = 1, 2, 4, 8                 # the NES pad bits (Joy1_ButtonMask)
FLAG_MOVING, FLAG_RIGHT = 0x20, 0x40                               # Player_Flags


@dataclass
class Hero:
    x: int = 0
    frac: int = 0
    y: int = 0
    acc: int = 0          # Player_MoveAcceleration (lower byte) and _U (upper) as one 16-bit value
    flags: int = 0
    tick: int = 0         # Player_MovementTick
    title: int = 0        # PlayerTitle (rank): the acceleration steps by rank group title >> 2


def blocked(impassable: list[int], col: int, row: int) -> int:
    """impassable[row * 16 + col] is 1 for a block the hero cannot walk through."""
    return impassable[(row & 15) * 16 + (col & 15)] if row < 13 else 0


def column_blocked(impassable: list[int], pixel_x: int, y: int) -> int:
    row = y >> 4
    result = blocked(impassable, pixel_x >> 4, row) | blocked(impassable, pixel_x >> 4, row + 1)
    if y & 15:
        result |= blocked(impassable, pixel_x >> 4, row + 2)
    return result


def update_acceleration(h: Hero, joy: int) -> None:
    if h.acc >= 0x180:
        return
    h.acc += ACCELERATION_DELTA[(h.title >> 2) & 3]


def try_move_right(h: Hero, joy: int, impassable: list[int]) -> str | None:
    if not h.flags & FLAG_MOVING:
        h.acc = 0xC0
    update_acceleration(h, joy)
    h.flags |= FLAG_MOVING | FLAG_RIGHT
    pos = (h.x << 8 | h.frac) + h.acc
    h.x, h.frac = (pos >> 8) & 0xFF, pos & 0xFF
    if h.x + 16 < 256 and column_blocked(impassable, h.x + 16, h.y):
        h.x &= 0xF0
        return None
    if h.x >= 0xF1:
        return "edge_right"
    return None


def try_move_left(h: Hero, joy: int, impassable: list[int]) -> str | None:
    if not h.flags & FLAG_MOVING:
        h.acc = 0xC0
    update_acceleration(h, joy)
    h.flags = (h.flags & ~FLAG_RIGHT) | FLAG_MOVING
    pos = (h.x << 8 | h.frac) - h.acc
    borrow = pos < 0
    pos &= 0xFFFF
    h.x, h.frac = pos >> 8, pos & 0xFF
    if borrow:
        h.x = 0
    if h.x >= 1 and column_blocked(impassable, h.x - 1, h.y):
        if h.x & 15:
            h.x = (h.x & 0xF0) + 0x10
        return None
    if borrow:
        return "edge_left"
    return None


def walk_step(h: Hero, joy: int, impassable: list[int]) -> str | None:
    """One frame of walking on the ground with `joy` held (right, then left wins nothing: right first, as in the ROM). Returns 'edge_right' or
    'edge_left' when he has walked to the end of the screen."""
    if joy & (JOY_RIGHT | JOY_LEFT):
        h.tick = (h.tick + 1) & 0xFF
        if joy & JOY_RIGHT:
            return try_move_right(h, joy, impassable)
        return try_move_left(h, joy, impassable)
    h.flags &= ~FLAG_MOVING & 0xFF
    return None
