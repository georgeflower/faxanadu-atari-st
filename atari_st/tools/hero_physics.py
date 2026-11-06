"""The hero's movement as the ROM does it, in Python: the reference the ST code is checked against (golden runs from the jsnes harness,
`tools/refnes/walkgolden.mjs`). Positions are 8.8 fixed point: `x` (the game's Player_PosX_Block) and `frac` (Player_PosX_Frac).

Read from `Player_CheckHandleVertMovement`, `Player_CheckIfOnLadder`, `Player_CheckHandleClimbUp/Down`, `Player_CheckHandleJump`, `Player_TryMoveRight/Left`, `Player_UpdateAcceleration`, `Player_CheckIfPassable`, the `Area_CanPlayerMove*`
routines and `Player_HandleVertLadderOrJump` / `Player_UpdateClimbOrJump` (jumping, falling, landing). Magic is in `magic_model.py`. (There is no crouching
in the game: body frame 3 is the pose in the air.) `Player_HandleVertLadderOrJump` loads A instead of X before its down check, so with a ladder
in the top left corner of a screen it checks the wrong side; that cannot be seen (every outcome ends in the ladder grab), so it is not modelled.
"""
from __future__ import annotations

from dataclasses import dataclass

IMPASSABLE = (0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0)     # BLOCK_PROPERTY_IMPASSABLE_MAP, by block property
CLIMBABLE = tuple(int(p in (2, 10)) for p in range(16))            # Area_IsBlockClimbable: the block properties 2 and 10 are ladders
ACCELERATION_DELTA = (2, 4, 6, 8)                                  # PLAYER_ACCELERATION_DELTA_BY_RANK_GROUP

JOY_RIGHT, JOY_LEFT, JOY_DOWN, JOY_UP = 1, 2, 4, 8                 # the NES pad bits (Joy1_ButtonMask)
FLAG_JUMPING, FLAG_HOLDING, FLAG_FALLING, FLAG_CAN_CLIMB, FLAG_CLIMBING, FLAG_MOVING, FLAG_RIGHT, FLAG_ATTACKING = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80     # Player_Flags
BUTTON_B = 0x40                                                    # in Joy1_ChangedButtonMask: B was pressed this frame
ATTACK_PHASES = (8, 3, 8)                                          # PLAYER_ATTACK_ANIMATION_PHASES: thrust out, wait, withdraw
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
    climb: int = 0        # Player_ClimbFlySpeedModifier: the fraction of a pixel the climbing down adds up
    status: int = 0       # Player_StatusFlag (bit 0: the attack button is down)
    attack_timer: int = 0     # Player_AttackPhaseTimer
    attack_frame: int = 0     # Player_AttackPhaseAnimFrame (0-2)
    invinc: int = 0           # Player_InvincibilityPhase: $3C when he is hit, counts down to 0; he cannot be hurt meanwhile


def blocked(impassable: list[int], col: int, row: int) -> int:
    """impassable[row * 16 + col] is 1 for a block the hero cannot walk through."""
    return impassable[(row & 15) * 16 + (col & 15)] if row < 13 else 0


def column_blocked(impassable: list[int], pixel_x: int, y: int) -> int:
    row = y >> 4
    result = blocked(impassable, pixel_x >> 4, row) | blocked(impassable, pixel_x >> 4, row + 1)
    if y & 15:
        result |= blocked(impassable, pixel_x >> 4, row + 2)
    return result


def side_blocked(column: list[int] | None, y: int) -> int:
    """The neighbour screen's edge column (16 flags, one a block row) at his height: `FirstColumnInRightScreen` / `LastColumnLeftScreen`."""
    if column is None:
        return 0
    row = y >> 4
    result = column[row & 15] | column[(row + 1) & 15]
    if y & 15:
        result |= column[(row + 2) & 15]
    return result


STATUS_KNOCKBACK = 0x02                                            # Player_StatusFlag bit 1
HIT_INVINCIBILITY = 0x3C                                           # Player_SetDamagedBySprite
KNOCKBACK_END = 0x39                                               # the knockback ends when the phase has counted down to here


def update_acceleration(h: Hero, joy: int) -> None:
    if h.status & STATUS_KNOCKBACK:                                  # Player_UpdatePosFromKnockback: 8 pixels a frame
        h.acc = 0x0800
        return
    if joy & (JOY_UP | JOY_DOWN) and h.flags & FLAG_CAN_CLIMB:       # stepping to a ladder: the standard speed, no acceleration
        h.acc = 0xC0
        return
    if h.acc >= 0x180:
        return
    h.acc += ACCELERATION_DELTA[(h.title >> 2) & 3]


def try_move_right(h: Hero, joy: int, impassable: list[int], right_col: list[int] | None = None) -> str | None:
    if not h.flags & FLAG_MOVING:
        h.acc = 0xC0
    update_acceleration(h, joy)
    h.flags |= FLAG_MOVING | FLAG_RIGHT
    pos = (h.x << 8 | h.frac) + h.acc
    h.x, h.frac = (pos >> 8) & 0xFF, pos & 0xFF
    if (column_blocked(impassable, h.x + 16, h.y) if h.x + 16 < 256 else side_blocked(right_col, h.y)):       # at x $F0 and over: the next screen's first column
        h.x &= 0xF0
        return None
    if h.x >= 0xF1:
        return "edge_right"
    return None


def try_move_left(h: Hero, joy: int, impassable: list[int], left_col: list[int] | None = None) -> str | None:
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
    if column_blocked(impassable, h.x - 1, h.y) if h.x >= 1 else side_blocked(left_col, h.y):       # at x 0: the last column of the screen to the left
        if h.x & 15:
            h.x = (h.x & 0xF0) + 0x10
        return None
    if borrow:
        return "edge_left"
    return None


def hit(h: Hero, enemy_faces_right: bool) -> None:
    """Player_SetDamagedBySprite: 60 frames of invincibility, he turns to face the enemy (the sprite's direction bit gives the opposite facing) and
    is knocked back. (The damage itself is the caller's: `Player_ApplyDamage`.)"""
    h.invinc = HIT_INVINCIBILITY
    h.flags = (h.flags & ~FLAG_RIGHT & 0xFF) | (0 if enemy_faces_right else FLAG_RIGHT)
    h.status |= STATUS_KNOCKBACK


def knockback_step(h: Hero, impassable: list[int], left_col: list[int] | None = None, right_col: list[int] | None = None) -> str | None:
    """Player_HandleKnockback: one move backwards (he faces the enemy; the facing is put back afterwards). The jump and the attack end: a hero in the
    air falls from then on."""
    facing = h.flags & FLAG_RIGHT
    h.flags = facing ^ FLAG_RIGHT                                    # the ROM stores only the flipped facing bit: every other flag (jumping, attacking ...) is gone
    event = try_move_right(h, 0, impassable, right_col) if h.flags & FLAG_RIGHT else try_move_left(h, 0, impassable, left_col)
    h.flags = (h.flags & ~FLAG_RIGHT & 0xFF) | facing
    return event


def iframes_step(h: Hero) -> None:
    """Player_HandleIFrames: the phase counts down; the knockback lasts until it has reached $39."""
    if not h.invinc:
        h.status &= ~STATUS_KNOCKBACK
        return
    h.invinc -= 1
    if h.invinc > KNOCKBACK_END:
        h.acc = 0xC0
        return
    if h.invinc == KNOCKBACK_END:
        h.acc = 0xC0
    h.status &= ~STATUS_KNOCKBACK


ATTACK_FRAMES = (4, 5, 6)                                          # BYTE_ARRAY_PRG15_MIRROR__ecf3: the body frames of the three attack phases
WALK_FRAMES = (0, 1, 2, 1)                                         # BYTE_ARRAY_PRG15_MIRROR__ecef


def body_frame(h: Hero, joy: int) -> int:
    """Player_GetBodySpriteFrameOffset (also Maybe_Player_CalcAnimFrame, which the weapon uses): 3 in the air, 7 climbing, 4-6 attacking, 3 flying,
    else the walk frames by the movement tick."""
    if h.flags & FLAG_JUMPING:
        return ATTACK_FRAMES[h.attack_frame] if h.flags & FLAG_ATTACKING else 3
    if is_climbing(h):
        return 7
    if h.flags & FLAG_ATTACKING:
        return ATTACK_FRAMES[h.attack_frame]
    if flying(h, joy):
        return 3
    return WALK_FRAMES[(h.tick >> 3) & 3] if h.flags & FLAG_MOVING else 0


def attack_step(h: Hero, changed: int) -> None:
    """Player_CheckHandleAttack: B pressed (not held) starts an attack of 8 + 3 + 8 frames, unless he is climbing."""
    if not h.flags & FLAG_ATTACKING:
        if is_climbing(h) or not changed & BUTTON_B:
            h.status &= ~1
            return
        if h.status & 1:
            return
        h.flags |= FLAG_ATTACKING
        h.status |= 1
        h.attack_timer = h.attack_frame = 0
    h.attack_timer += 1
    if h.attack_timer < ATTACK_PHASES[h.attack_frame]:
        return
    h.attack_timer = 0
    if h.attack_frame + 1 >= 3:
        h.flags &= ~FLAG_ATTACKING & 0xFF
    else:
        h.attack_frame += 1


def walk_step(h: Hero, joy: int, impassable: list[int], left_col: list[int] | None = None, right_col: list[int] | None = None) -> str | None:
    """One frame of walking on the ground with `joy` held (right, then left wins nothing: right first, as in the ROM). Returns 'edge_right' or
    'edge_left' when he has walked to the end of the screen. Attacking on the ground he stands still."""
    if h.flags & FLAG_ATTACKING:
        h.flags &= ~FLAG_MOVING & 0xFF
        return None
    if joy & (JOY_RIGHT | JOY_LEFT):
        h.tick = (h.tick + 1) & 0xFF
        if joy & JOY_RIGHT:
            return try_move_right(h, joy, impassable, right_col)
        return try_move_left(h, joy, impassable, left_col)
    if joy & (JOY_UP | JOY_DOWN) and h.x & 15 and h.flags & FLAG_CAN_CLIMB:       # up or down on a ladder when not on it: step to it
        h.tick = (h.tick + 1) & 0xFF
        if h.x & 15 < 8:
            return try_move_left(h, joy, impassable, left_col)
        return try_move_right(h, joy, impassable, right_col)
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


def _climbable(ladder: list[int] | None, index: int) -> int:
    return ladder[index] if ladder and 0 <= index < 208 else 0


def check_on_ladder(h: Hero, ladder: list[int] | None) -> None:
    """Player_CheckIfOnLadder: Can Climb is set when a ladder block is at his head or his feet (x + 7; the next block too when x & 15 is 8)."""
    column = ((h.x + 7) & 0xFF) >> 4
    found = 0
    for y in (h.y, (h.y + 0x1F) & 0xFF):
        index = (y >> 4) * 16 + column
        found = _climbable(ladder, index) or (h.x & 15 == 8 and _climbable(ladder, index + 1))
        if found:
            break
    h.flags &= ~FLAG_CAN_CLIMB & 0xFF
    if found:
        h.flags |= FLAG_CAN_CLIMB
    else:
        h.flags &= ~FLAG_CLIMBING & 0xFF


def is_climbing(h: Hero) -> bool:
    if not h.flags & FLAG_CAN_CLIMB:
        return False
    if h.x & 15 and h.flags & FLAG_FALLING:
        return False
    return bool(h.flags & FLAG_CLIMBING)


def flying(h: Hero, joy: int) -> bool:
    """Wing boots active (Player_StatusFlag bit 7) and the A button held (Joy1_ButtonMask bit 7)."""
    return bool(h.status & 0x80 and joy & BUTTON_A)


def vertical_step(h: Hero, joy: int, changed: int, impassable: list[int], *, ladder: list[int] | None = None, screen_above: bool = False,
                  screen_below: bool = False, above_row: list[int] | None = None, below_row: list[int] | None = None) -> str | None:
    """Player_CheckHandleVertMovement (with wing boots too): climbs a ladder with up and down; otherwise starts a jump on a new A press, follows the
    jump curve, lets him fall off ledges (8 pixels a frame) and lands him on a block row. Returns 'scroll_up' / 'scroll_down' when he has moved
    over the edge to a neighbour screen (his y is then set as the ROM does), else None."""
    check_on_ladder(h, ladder)
    if flying(h, joy):                                                # wing boots and A held: up and down fly, ladder or not
        if joy & JOY_DOWN:
            return _climb_down(h, impassable, screen_below, below_row, True)
        if joy & JOY_UP:
            return _climb_up(h, impassable, screen_above, above_row, True)
    elif h.flags & FLAG_CAN_CLIMB and joy & (JOY_UP | JOY_DOWN):
        h.flags |= FLAG_CLIMBING
        if h.x & 15 == 0:
            if joy & JOY_DOWN:
                return _climb_down(h, impassable, screen_below, below_row, bool(h.status & 0x80))        # the wing boots speed up the ladder too
            return _climb_up(h, impassable, screen_above, above_row, bool(h.status & 0x80))
    if h.jump >= 0x20:
        h.flags &= ~FLAG_JUMPING & 0xFF
    if not h.flags & FLAG_JUMPING:
        if not blocked_below(h, impassable, below_row):
            h.flags |= FLAG_FALLING
            if not h.flags & FLAG_CAN_CLIMB:                        # nothing under his feet and no ladder: he falls (glides a pixel a frame on wings with A held)
                h.y = (h.y + (1 if flying(h, joy) else 8)) & 0xFF
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
        h.flags &= ~FLAG_FALLING & 0xFF                             # standing or hanging on a ladder: Player_GrabClimbLadderOrJump
        if not changed & BUTTON_A:
            h.flags &= ~(FLAG_JUMPING | FLAG_HOLDING) & 0xFF
            return None
        if is_climbing(h):
            return None
        if blocked_above(h, impassable, above_row):
            return None
        h.flags |= FLAG_JUMPING | FLAG_HOLDING
        h.jump = 0
    else:
        h.flags &= ~FLAG_FALLING & 0xFF
    return _jump_frame(h, impassable, screen_above, above_row, below_row)


def _climb_up(h: Hero, impassable: list[int], screen_above: bool, above_row: list[int] | None, wings: bool = False) -> str | None:
    h.flags &= 0xDA
    if blocked_above(h, impassable, above_row):
        return None
    h.tick = (h.tick + 1) & 0xFF
    if wings:                                                       # flying up: one pixel a frame (the ROM's comments have it the wrong way round)
        borrow = h.y == 0
    else:
        modifier = h.climb - 0xA0                                   # climbing: 5/8 of a pixel a frame
        borrow = modifier < 0
        h.climb = modifier & 0xFF
    if borrow and h.y == 0:                                         # over the top of the screen
        if screen_above:
            h.y = 0xC0
            return "scroll_up"
        return None
    h.y -= 1 if wings else borrow
    return None


def _climb_down(h: Hero, impassable: list[int], screen_below: bool, below_row: list[int] | None, wings: bool = False) -> str | None:
    h.flags &= 0xDA
    if blocked_below(h, impassable, below_row):
        return None
    h.tick = (h.tick + 1) & 0xFF
    h.climb += 0x80 if wings else 0xC0                              # climbing: three quarters of a pixel a frame; flying: one and a half
    carry, h.climb = h.climb >> 8, h.climb & 0xFF
    h.y = (h.y + carry + wings) & 0xFF
    if h.y >= 0xC1:
        if screen_below:
            h.y = 0
            return "scroll_down"
        h.y = 0xC0
    return None


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


def air_step(h: Hero, joy: int, impassable: list[int], left_col: list[int] | None = None, right_col: list[int] | None = None) -> str | None:
    """Player_CheckHandleJump while he is in the air: he keeps going the way he was moving, he cannot turn."""
    if h.flags & FLAG_MOVING:
        return try_move_right(h, joy, impassable, right_col) if h.flags & FLAG_RIGHT else try_move_left(h, joy, impassable, left_col)
    return None


def step(h: Hero, joy: int, changed: int, impassable: list[int], left_col: list[int] | None = None, right_col: list[int] | None = None,
         **edges) -> str | None:
    """One frame of the hero as GameLoop_UpdatePlayer runs it (without magic): the vertical part first, then the horizontal part."""
    attack_step(h, changed)
    event = vertical_step(h, joy, changed, impassable, **edges)
    if h.status & STATUS_KNOCKBACK:
        event = knockback_step(h, impassable, left_col, right_col) or event
        iframes_step(h)
        return event
    event = _horizontal_step(h, joy, impassable, left_col, right_col) or event
    iframes_step(h)
    return event


def _horizontal_step(h: Hero, joy: int, impassable: list[int], left_col: list[int] | None, right_col: list[int] | None) -> str | None:
    if h.flags & (FLAG_JUMPING | FLAG_FALLING) and not h.status & 0x80:        # with wing boots on he steers in the air as on the ground
        return air_step(h, joy, impassable, left_col, right_col)
    return walk_step(h, joy, impassable, left_col, right_col)
