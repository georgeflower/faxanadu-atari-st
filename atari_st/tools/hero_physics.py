"""The hero's movement as the ROM does it, in Python: the reference the ST code is checked against (golden runs from the jsnes harness,
`tools/refnes/walkgolden.mjs`). Positions are 8.8 fixed point: `x` (the game's Player_PosX_Block) and `frac` (Player_PosX_Frac).

Read from `Player_CheckHandleJump`, `Player_TryMoveRight/Left`, `Player_UpdateAcceleration`, `Player_CheckIfPassable`, the `Area_CanPlayerMove*`
routines and `Player_HandleVertLadderOrJump` / `Player_UpdateClimbOrJump` (jumping, falling, landing). Not here yet: ladders, knockback, flying, the
screen edges' neighbour columns (the hero is taken as free to move there; the caller sees `edge` when he has walked off), crouching. One ROM quirk is
left out: `Player_HandleVertLadderOrJump` loads A instead of X before its down check, so with the hero in the top left corner of a screen it checks
the wrong side.
"""
from __future__ import annotations

from dataclasses import dataclass

IMPASSABLE = (0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0)     # BLOCK_PROPERTY_IMPASSABLE_MAP, by block property
ACCELERATION_DELTA = (2, 4, 6, 8)                                  # PLAYER_ACCELERATION_DELTA_BY_RANK_GROUP

JOY_RIGHT, JOY_LEFT, JOY_DOWN, JOY_UP = 1, 2, 4, 8                 # the NES pad bits (Joy1_ButtonMask)
FLAG_JUMPING, FLAG_HOLDING, FLAG_FALLING, FLAG_MOVING, FLAG_RIGHT = 0x01, 0x02, 0x04, 0x20, 0x40     # Player_Flags
BUTTON_A = 0x80                                                    # in Joy1_ChangedButtonMask: A was pressed this frame

# PLAYER_JUMP_CURVE: how far up (index < 16) or down (index >= 16) the hero moves each frame of a jump
JUMP_CURVE = (8, 4, 4, 4, 4, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 0,
              0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 4, 4, 4, 4, 8)


@dataclass
class Hero:
    x: int = 0
    frac: int = 0
    y: int = 0
    acc: int = 0          # Player_MoveAcceleration (lower byte) and _U (upper) as one 16-bit value
    flags: int = 0
    tick: int = 0         # Player_MovementTick
    title: int = 0        # PlayerTitle (rank): the acceleration steps by rank group title >> 2
    jump: int = 0         # Player_JumpCurveIndex


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


def _row_blocked(impassable: list[int], index: int) -> int:
    return impassable[index] if 0 <= index < 208 else 0


def _body_blocked(h: Hero, impassable: list[int], pixel_y: int) -> int:
    """Area_CanMoveImmediatelyRight: the block under the hero's middle (x + 4) at `pixel_y`, and the next one when he straddles two."""
    index = (pixel_y >> 4) * 16 + ((h.x + 4) & 0xFF) // 16
    result = _row_blocked(impassable, index)
    if ((h.x & 15) - 4) & 0xFF < 8:
        result |= _row_blocked(impassable, index + 1)
    return result


def blocked_below(h: Hero, impassable: list[int], below_row: list[int] | None = None) -> int:
    """Player_CheckIfPassable with X = 3: is there something under his feet? `below_row` is the first row of the screen below (16 flags)."""
    pixel_y = (h.y + 32) & 0xFF
    if pixel_y < 0xD0:
        return _body_blocked(h, impassable, pixel_y)
    row = below_row or [0] * 17
    result = row[h.x >> 4]
    if h.x & 15:
        result |= row[(h.x >> 4) + 1] if (h.x >> 4) + 1 < len(row) else 0
    return result


def blocked_above(h: Hero, impassable: list[int], above_row: list[int] | None = None) -> int:
    """Player_CheckIfPassable with X = 2: is there something just over his head?"""
    pixel_y = (h.y - 1) & 0xFF
    if pixel_y < 0xF0:
        return _body_blocked(h, impassable, pixel_y)
    row = above_row or [0] * 17
    result = row[h.x >> 4]
    if h.x & 15:
        result |= row[(h.x >> 4) + 1] if (h.x >> 4) + 1 < len(row) else 0
    return result


def vertical_step(h: Hero, joy: int, changed: int, impassable: list[int], *, screen_above: bool = False, screen_below: bool = False,
                  above_row: list[int] | None = None, below_row: list[int] | None = None) -> str | None:
    """Player_CheckHandleVertMovement for a hero who is not on a ladder: starts a jump on a new A press, follows the jump curve, lets him fall off
    ledges (8 pixels a frame) and lands him on a block row. Returns 'scroll_up' / 'scroll_down' when he has moved over the edge to a neighbour
    screen (his y is then set as the ROM does), else None."""
    h.flags &= ~0x18 & 0xFF                                       # not on a ladder: Can Climb and Climbing stay clear
    if h.jump >= 0x20:
        h.flags &= ~FLAG_JUMPING & 0xFF
    if not h.flags & FLAG_JUMPING:
        if not blocked_below(h, impassable, below_row):             # nothing under his feet: he falls
            h.flags |= FLAG_FALLING
            h.y = (h.y + 8) & 0xFF
            if h.y >= 0xC1:
                if screen_below:
                    h.y = 0
                    return "scroll_down"
                h.y = 0xC0
                h.flags &= ~FLAG_FALLING & 0xFF
                return None
            if blocked_below(h, impassable, below_row):
                h.y &= 0xF0
            return None
        h.flags &= ~FLAG_FALLING & 0xFF                             # standing: Player_GrabClimbLadderOrJump
        if not changed & BUTTON_A:
            h.flags &= ~(FLAG_JUMPING | FLAG_HOLDING) & 0xFF
            return None
        if blocked_above(h, impassable, above_row):
            return None
        h.flags |= FLAG_JUMPING | FLAG_HOLDING
        h.jump = 0
    else:
        h.flags &= ~FLAG_FALLING & 0xFF
    return _jump_frame(h, impassable, screen_above, above_row, below_row)


def _jump_frame(h: Hero, impassable: list[int], screen_above: bool, above_row: list[int] | None, below_row: list[int] | None) -> str | None:
    delta = JUMP_CURVE[h.jump]
    if h.jump < 0x10:                                             # rising
        y = h.y - delta
        h.y = y & 0xFF
        if y < 0:                                                 # over the top of the screen
            if screen_above:
                h.y = 0xC0
                h.flags &= ~FLAG_JUMPING & 0xFF
                return "scroll_up"
            h.y = 0
            h.jump = 0x0F
        elif blocked_above(h, impassable, above_row):             # head against a block: down he comes
            if h.y & 15:
                h.y = (h.y & 0xF0) + 0x10
            h.jump = 0x0F
    else:                                                         # falling
        h.y = (h.y + delta) & 0xFF
        if blocked_below(h, impassable, below_row):
            h.y &= 0xF0
            h.flags &= ~FLAG_JUMPING & 0xFF
            return None
    h.jump += 1
    return None


def air_step(h: Hero, impassable: list[int]) -> str | None:
    """Player_CheckHandleJump while he is in the air: he keeps going the way he was moving, he cannot turn."""
    if h.flags & FLAG_MOVING:
        return try_move_right(h, 0, impassable) if h.flags & FLAG_RIGHT else try_move_left(h, 0, impassable)
    return None


def step(h: Hero, joy: int, changed: int, impassable: list[int], **edges) -> str | None:
    """One frame of the hero as GameLoop_UpdatePlayer runs it (without attack and ladders): the vertical part first, then the horizontal part."""
    event = vertical_step(h, joy, changed, impassable, **edges)
    if h.flags & (FLAG_JUMPING | FLAG_FALLING):
        return air_step(h, impassable) or event
    return walk_step(h, joy, impassable) or event
