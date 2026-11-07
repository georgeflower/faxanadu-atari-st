"""The enemy engine as the ROM does it, in Python: the reference the ST code is checked against (golden runs from the jsnes harness,
`tools/refnes/enemyprobe.mjs`). Read from `Sprites_UpdateAll`, `Sprites_UpdateBehavior`, the `BScript_Op_*` routines, the `SpriteBehavior_*`
routines, `CurrentSprite_CanMoveInDirection`, `MoveSpriteHorizIfPossible` and `MoveSpriteVerticalIfPossible`.

An enemy is a slot (`Sprite`) with a script: a list of ops in bank 14 (`BSCRIPTS_*`). `Sprites_UpdateBehavior` runs the next op when the
running behaviour has finished (bit 7 of `beh`), then runs the behaviour. Behaviours modelled so far: 1 Wait, 4 WalkForward, 9 Hop, 21 Fall.
Positions are 8.8 fixed point: `x`/`xf` (CurrentSprites_XPos_Full/Frac) and `y`/`yf`. Flags: bit 0 facing right, bit 1 ignore the floor (flies),
bit 2 airborne (set by SetCurrentSpriteCanMove), bit 6 behaviour ready, bit 7 falling (down; clear = up).
"""
from __future__ import annotations

from dataclasses import dataclass

IMPASSABLE = (0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0)     # BLOCK_PROPERTY_IMPASSABLE_MAP, by block property
LADDER = 2                                                         # block property: a ladder (counts as solid for Area_IsBlockImpassableOrLadder)

F_RIGHT, F_FLY, F_AIR, F_READY, F_DOWN = 0x01, 0x02, 0x04, 0x40, 0x80
NONE = 0xFF

BEH_MOVE, BEH_WAIT, BEH_BOUNCE, BEH_WALK, BEH_DEATH, BEH_HOP, BEH_FALL, BEH_BIHORUDA, BEH_WAVE, BEH_FIREBALL, BEH_FINISH, BEH_GAWAINE, BEH_BUZZ = 0, 1, 2, 4, 7, 9, 21, 23, 25, 27, 30, 40, 63
BUZZ_Y = (0x00, 0x00, 0x80, 0x40, 0x00, 0x40, 0x80, 0x00)        # SPRITE_BEHAVIOR_BUZZ_AROUND_Y_FRAC and ..._X_FRAC (the whole pixels of the vertical step)
BUZZ_Y_FULL = (2, 1, 0, 0, 0, 0, 0, 1)
E_BREAD, E_COIN, E_DEATH, E_BOSS_DEATH, E_FIREBALL = 1, 2, 0x13, 0x64, 0x54

# SPRITE_BEHAVIOR_HOP_* (indexed by the hop kind, the third script byte), SPRITE_BEHAVIOR_HOP_PEAK_TICKS and SPRITES_MAYBE_GRAVITY (by gravity)
HOP_START = (0x40, 0x20, 0x10, 0x08, 0x10)
HOP_GRAVITY = (2, 3, 4, 5, 4)
HOP_STRENGTH = (4, 5, 6, 7, 7)
HOP_GROUND = (0xC0, 0x60, 0x30, 0x18, 0x30)
PEAK_TICKS = (0xFF, 0x7F, 0x3F, 0x1F, 0x0F, 0x07, 0x03, 0x01)
MAYBE_GRAVITY = (0x00, 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02)
HITBOX_WIDTH = (0x0F, 0x0F, 0x1F, 0x1F, 0x1F, 0x3F, 0x2F)
HITBOX_HEIGHT = (0x0F, 0x1F, 0x2F, 0x3F, 0x1F, 0x1F, 0x4F)


@dataclass
class Sprite:
    ent: int = NONE
    x: int = 0
    xf: int = 0
    y: int = 0
    yf: int = 0
    flags: int = 0
    phase: int = 0
    beh: int = 0
    arg1: int = 0
    d2: int = 0           # CurrentSprites_BehaviorData2 / 3: the walk speed, the hop's tick
    d3: int = 0
    hbox: int = 1         # CurrentSprites_HitBoxTypes
    internal: int = 0     # CurrentSprites_InternalBehaviorStates: the hop kind
    bxf: int = 0          # CurrentSprites_BehaviorState_XFrac / XFull: the hop's sideways speed
    bxfull: int = 0
    script: int = 0       # CurrentSprites_BehaviorAddrs: the next op (a CPU address in bank 14)
    hit: int = 0          # CurrentSprites_HitCounter: 8 when the weapon has hit it, counts down; the sprite stands still meanwhile
    hp: int = 0           # CurrentSprites_HP
    value: int = 0        # CurrentSprites_Values: what a coin is worth, how much a bread heals


@dataclass
class Hero:
    """What the sprites ask of the hero and change in him (`Player_*`): Player_PosX_Block/PosY, Player_Flags (bit 7 attacking, bit 6 facing right),
    Player_AttackPhaseAnimFrame, the weapon's place and reach, the invincibility phase, the status flag (bit 1 knock-back), the power (HP_U.HP_L), the
    equipment and the experience and gold."""
    x: int = 0
    y: int = 0
    flags: int = 0
    atk: int = 0
    wx: int = 0
    wy: int = 0
    rx: int = 0
    ry: int = 0
    inv: int = 0
    status: int = 0
    hp_u: int = 80
    hp_l: int = 0
    weapon: int = 0
    armour: int = 0
    special: int = 0
    glove: int = 0xFF
    ointment: int = 0xFF
    exp: int = 0
    gold: int = 0
    dead: int = 0
    events: list = None   # (sound effect numbers played, in order)


class Engine:
    """One screen's worth of enemies. `blocks` is the 256 bytes of ScreenBuffer, `props` the area's block properties (by block)."""

    def __init__(self, bank14: bytes, random_table: bytes, blocks: bytes, props: bytes):
        self.rom = bank14
        self.random_table = random_table
        self.blocks = blocks
        self.props = props
        self.sprites = [Sprite() for _ in range(8)]
        self.rnd = 0                  # Random_Offset
        self.counter = 0              # SpriteUpdateCounter (a byte, one more at the start of every update)
        self.mask = 0                 # Joy1_ButtonMask
        self.i = 0                    # CurrentSpriteIndex
        self.ip = 0                   # Sprites_ReadInfoAddr
        self.kinds: dict = {}         # enemy_data.kind_info by entity
        self.combat: dict = {}        # enemy_data.tables
        self.hero = Hero(events=[])

    @property
    def hero_x(self) -> int:
        return self.hero.x

    @hero_x.setter
    def hero_x(self, v: int) -> None:
        self.hero.x = v

    @property
    def hero_y(self) -> int:
        return self.hero.y

    @hero_y.setter
    def hero_y(self, v: int) -> None:
        self.hero.y = v

    # -- the random numbers: a byte of the ROM's own code, mixed with the buttons held
    def random(self) -> int:
        v = self.random_table[self.rnd] ^ self.mask
        self.rnd = (self.rnd + 1) & 255
        return v

    def byte(self, addr: int) -> int:
        return self.rom[addr - 0x8000]

    # -- blocks
    def prop(self, index: int) -> int:
        return self.props[self.blocks[index & 255]] & 15

    def impassable(self, x: int, y: int) -> int:
        return IMPASSABLE[self.prop((y & 0xF0) | (x >> 4))]

    def impassable_or_ladder(self, x: int, y: int) -> int:
        p = self.prop((y & 0xF0) | (x >> 4))
        return 1 if p == LADDER else IMPASSABLE[p]

    def blocked(self, s: Sprite, direction: int) -> int:
        """CurrentSprite_CanMoveInDirection: 0 left, 1 right, 2 up, 3 down; nonzero when a solid block is in the way."""
        if direction == 3 or direction == 2:
            if direction == 3:
                py = (s.y + HITBOX_HEIGHT[s.hbox]) & 255
                if py >= 0xF0:
                    return 1
            else:
                py = s.y
                if py >= 0xF0:
                    return 1
            idx = (py & 0xF0) | (s.x >> 4)
            if IMPASSABLE[self.prop(idx)]:
                return 1
            left = HITBOX_WIDTH[s.hbox]
            while True:
                left -= 0x10
                if left < 0:
                    break
                idx = (idx + 1) & 0xFF
                if IMPASSABLE[self.prop(idx)]:
                    return 1
            if s.x & 0x0F:
                idx = (idx + 1) & 0xFF
                return IMPASSABLE[self.prop(idx)]
            return 0
        if direction == 0:
            if s.x >= 0xF1:
                return 1
            px = s.x
        else:
            px = s.x + HITBOX_WIDTH[s.hbox]
            if px > 0xFF:
                return 1
        idx = (s.y & 0xF0) | (px >> 4)
        if IMPASSABLE[self.prop(idx)]:
            return 1
        left = HITBOX_HEIGHT[s.hbox]
        while True:
            left -= 0x10
            if left < 0:
                break
            idx = (idx + 0x10) & 0xFF
            if IMPASSABLE[self.prop(idx)]:
                return 1
        if s.y & 0x0F:
            idx = (idx + 0x10) & 0xFF
            return IMPASSABLE[self.prop(idx)]
        return 0

    # -- moving
    def add_x(self, s: Sprite, frac: int, full: int, sign: int) -> None:
        v = (s.x << 8 | s.xf) + sign * (full << 8 | frac)
        s.x, s.xf = (v >> 8) & 255, v & 255

    def move_horiz(self, s: Sprite, frac: int, full: int) -> int:
        """Sprites_Something_SomethingAndMoveHoriz: a step forward; returns 1 when a wall stopped it (the sprite is put against it)."""
        self.add_x(s, frac, full, 1 if s.flags & F_RIGHT else -1)
        if not self.blocked(s, s.flags & 1):
            return 0
        s.x &= 0xF0
        if not s.flags & F_RIGHT:
            s.x = (s.x + 0x10) & 255
        return 1

    def move_horiz_and_turn(self, s: Sprite, frac: int, full: int) -> None:
        if self.move_horiz(s, frac, full):
            s.flags ^= F_RIGHT

    def move_vertical(self, s: Sprite, frac: int, full: int) -> int:
        v = (s.y << 8 | s.yf) + (full << 8 | frac) * (1 if s.flags & F_DOWN else -1)
        s.y, s.yf = (v >> 8) & 255, v & 255
        if not self.blocked(s, 3 if s.flags & F_DOWN else 2):
            return 0
        s.y &= 0xF0
        if not s.flags & F_DOWN:
            s.y = (s.y + 0x10) & 255
        return 1

    def floor_below(self, s: Sprite) -> int:
        """Sprites_CanMoveDownByHitbox: the block under the sprite's lower corner on the side it faces (a ladder counts as solid)."""
        py = (s.y + HITBOX_HEIGHT[s.hbox] + 1) & 255
        px = (s.x + (0x0F if s.flags & 1 else 0)) & 255
        return self.impassable_or_ladder(px, py)

    def can_move(self, s: Sprite) -> int:
        """Sprites_SetCurrentSpriteCanMove: 1 when the sprite is in the air (it must fall), 0 when it stands or flies."""
        if not s.flags & F_FLY and not self.floor_below(s):
            s.flags |= F_AIR
            return 1
        s.flags &= ~F_AIR & 255
        return 0

    def handle_fall(self, s: Sprite) -> None:
        if not s.flags & F_AIR:
            return
        s.y = (s.y + 8) & 255
        if s.y >= 0xC0:
            s.ent = NONE
            return
        if self.blocked(s, 3):
            s.y &= 0xF0

    # -- distances to the hero
    def distance_x(self, s: Sprite) -> int:
        d = s.x - self.hero_x
        if d >= 0:
            return max(d - 0x10, 0)
        return max(-d - HITBOX_WIDTH[s.hbox], 0)

    def distance_y(self, s: Sprite) -> int:
        return abs(s.y - self.hero_y)

    # -- behaviours
    def finish(self, s: Sprite) -> None:
        s.flags &= ~F_READY & 255
        s.beh |= 0x80

    def countdown(self, s: Sprite) -> None:
        if s.arg1:
            s.arg1 -= 1
            if not s.arg1:
                self.finish(s)

    def behaviour_wait(self, s: Sprite) -> None:
        s.flags |= F_READY
        self.countdown(s)

    def behaviour_move_toward(self, s: Sprite) -> None:
        """SpriteBehavior_MoveTowardPlayer: on the way it faces (the script turns it to the hero with an action), falling when there is no floor, not turning at a wall."""
        if not s.flags & F_READY:
            s.d2, s.d3 = self.byte(self.ip), self.byte(self.ip + 1)
            self.ip += 2
            s.flags |= F_READY
            s.flags &= ~F_FLY & 255
        if self.can_move(s):
            self.handle_fall(s)
            if s.flags & F_FLY:
                return
        self.move_horiz(s, s.d2, s.d3)
        self.countdown(s)

    @staticmethod
    def triangle(a: int, peak: int, top: int) -> int:
        """Sprites_CalcYFromGravity: a counter as a wave that rises to `peak` and falls again (`top` is the counter's bit that turns it)."""
        t = a & peak
        return peak - t if a & top else t

    def behaviour_wave(self, s: Sprite) -> None:
        """SpriteBehavior_Yuinaru: it flies through walls, sideways and up and down on two triangle waves of different length, turning at the edges of the screen."""
        if not s.flags & F_READY:
            s.d2, s.d3 = 0, 0x80
            s.flags |= F_READY
        t = self.triangle(s.d2, 0x7F, 0x80)
        self.add_x(s, (t << 3) & 255, (t >> 5) & 3, 1 if s.flags & F_RIGHT else -1)
        if s.x >= 0xF0:
            s.x = (s.x & 0xF0) + (0 if s.flags & F_RIGHT else 0x10) & 255
            s.flags ^= F_RIGHT
        s.d2 = (s.d2 + 1) & 255
        t = self.triangle(s.d3, 0x3F, 0x40)
        v = (s.y << 8 | s.yf) + ((((t >> 5) & 1) << 8) | (t << 3) & 255) * (1 if s.flags & F_DOWN else -1)
        s.y, s.yf = (v >> 8) & 255, v & 255
        if s.y >= 0xE0:
            s.y = (s.y & 0xF0) if s.flags & F_DOWN else (s.y & 0xF0) + 0x10 & 255
            s.flags ^= F_DOWN
        s.d3 = (s.d3 + 1) & 255

    def behaviour_fireball(self, s: Sprite) -> None:
        """SpriteBehavior_EnemyMagic: two pixels forward a frame, through everything, gone at the edge of the screen."""
        s.flags |= F_READY
        self.add_x(s, 0, 2, 1 if s.flags & F_RIGHT else -1)
        if s.x >= 0xF0:                                            # (Sprite_Maybe_TurnAroundIfAtScreenEdgeHoriz still puts it on a block edge and turns it round)
            s.x = (s.x & 0xF0) + (0 if s.flags & F_RIGHT else 0x10) & 255
            s.flags ^= F_RIGHT
            s.ent = NONE

    def cast_magic(self, s: Sprite) -> None:
        """BScript_Action_CastMagic: a fireball from the sprite's x and 8 lines below its top, the way it faces, in the highest free slot (the x and y fractions stay what the slot had)."""
        free = next((i for i in range(7, -1, -1) if self.sprites[i].ent == NONE), None)
        if free is None:
            return
        d = self.sprites[free]
        d.flags = s.flags & 1
        d.x, d.y = s.x, (s.y + 8) & 255
        d.ent = E_FIREBALL
        d.script = self.kinds[E_FIREBALL]["script"]
        d.beh = 0xFF
        d.hbox = self.kinds[E_FIREBALL]["hbox"]
        d.phase = 0

    def behaviour_finish(self, s: Sprite) -> None:
        """The thunk to Sprite_FinishBehavior: the behaviour is over at once and the script goes on."""
        self.finish(s)

    def behaviour_buzz(self, s: Sprite) -> None:
        """SpriteBehavior_BuzzAround (the Hornet): two pixels sideways a frame, turning at a wall; up and down in steps from a table of 8, each for 8 frames."""
        if not s.flags & F_READY:
            s.phase = s.d2 = 0
            s.flags |= F_READY
        self.move_horiz_and_turn(s, 0, 2)
        i = (s.d2 >> 3) & 7
        if self.move_vertical(s, BUZZ_Y[i], BUZZ_Y_FULL[i]):
            s.flags ^= F_DOWN
        s.d2 = (s.d2 + 1) & 255

    def behaviour_bihoruda(self, s: Sprite) -> None:
        """SpriteBehavior_Bihoruda: it flies, sideways and up and down each on a triangle wave of 64 ticks (the two waves start 64 ticks apart), turning at a wall."""
        if not s.flags & F_READY:
            s.d2, s.d3 = 0, 0x40
            s.flags |= F_READY
        t = self.triangle(s.d2, 0x3F, 0x40)
        self.move_horiz_and_turn(s, (t << 3) & 255, (t >> 5) & 1)
        s.d2 = (s.d2 + 1) & 255
        t = self.triangle(s.d3, 0x3F, 0x40)
        if self.move_vertical(s, (t << 3) & 255, (t >> 5) & 1):
            s.flags ^= F_DOWN
        s.d3 = (s.d3 + 1) & 255

    def behaviour_gawaine(self, s: Sprite) -> None:
        """SpriteBehavior_SirGawaineWolfman: walks to the hero (a pixel a frame) until it is 24 away; then it stands facing him, and when he is in the air
        it rushes at him, two pixels a frame. The step is the picture."""
        if not s.flags & F_READY:
            s.phase = 0
            s.flags |= F_READY
        if self.can_move(s):
            self.handle_fall(s)
        s.phase = 0
        d = self.distance_x(s)
        if d == 0x18:
            return
        if d > 0x18:
            self.actions(s, 0)
            self.move_horiz(s, 0, 1)
            if self.counter & 8:
                s.phase += 1
            return
        s.phase = 1
        if not self.hero.flags & 1:                                # (Player_Flags bit 0: jumping)
            self.actions(s, 0)
            s.phase = 2 if self.counter & 0x10 else 0
            return
        s.phase = 0
        self.actions(s, 0)
        self.move_horiz(s, 0, 2)
        if not self.counter & 4:
            s.phase += 1

    def behaviour_walk(self, s: Sprite) -> None:
        if not s.flags & F_READY:
            s.d2, s.d3 = self.byte(self.ip), self.byte(self.ip + 1)
            self.ip += 2
            s.flags |= F_READY
        if self.can_move(s):
            s.flags ^= F_RIGHT
            self.handle_fall(s)
            return
        self.move_horiz_and_turn(s, s.d2, s.d3)
        self.countdown(s)

    def behaviour_fall(self, s: Sprite) -> None:
        s.flags |= F_READY
        if self.can_move(s):
            self.handle_fall(s)
        self.countdown(s)

    def behaviour_hop(self, s: Sprite) -> None:
        if not s.flags & F_READY:
            s.bxf, s.bxfull, s.internal = self.byte(self.ip), self.byte(self.ip + 1), self.byte(self.ip + 2)
            self.ip += 3
            s.arg1 = 0
            s.flags |= F_READY
            s.flags &= 0x7F
            s.d3 = HOP_START[s.internal]
        self.move_horiz(s, s.bxf, s.bxfull)
        g = HOP_GRAVITY[s.internal]
        t = s.d3 & PEAK_TICKS[g]
        a = PEAK_TICKS[g] - t if s.d3 & MAYBE_GRAVITY[g] else t
        strength = HOP_STRENGTH[s.internal]
        frac, full = (a << strength) & 255, a >> (8 - strength)
        hit = self.move_vertical(s, frac, full)
        if hit and s.flags & F_DOWN:
            self.finish(s)
            return
        s.d3 = (s.d3 + 1) & 255
        if s.d3 & PEAK_TICKS[g]:
            return
        if not s.flags & F_DOWN:
            s.flags ^= F_DOWN
        elif s.d3 >= HOP_GROUND[s.internal]:
            s.d3 = (s.d3 - 1) & 255

    BEHAVIOURS = {BEH_MOVE: "behaviour_move_toward", BEH_WAVE: "behaviour_wave", BEH_FIREBALL: "behaviour_fireball", BEH_FINISH: "behaviour_finish", BEH_BUZZ: "behaviour_buzz", BEH_BIHORUDA: "behaviour_bihoruda", BEH_GAWAINE: "behaviour_gawaine", BEH_WAIT: "behaviour_wait", BEH_BOUNCE: "behaviour_bounce", BEH_WALK: "behaviour_walk", BEH_DEATH: "behaviour_death",
                  BEH_HOP: "behaviour_hop", BEH_FALL: "behaviour_fall"}

    # -- the dropped coin: SpriteBehavior_BounceAndExpire
    def behaviour_bounce(self, s: Sprite) -> None:
        if not s.flags & F_READY:
            s.phase, s.internal = 0, 0
            s.flags = F_DOWN | F_READY
        s.internal = (s.internal + 1) & 255
        if s.internal == 0:
            s.ent = NONE
            return
        if s.phase == 0:                                           # falls 4 a frame until it lands
            if self.move_vertical(s, 0, 4):
                s.phase += 1
                s.d3 = 0x20
                s.flags &= 0x7F
            return
        t = s.d3 & PEAK_TICKS[3]
        a = PEAK_TICKS[3] - t if s.d3 & MAYBE_GRAVITY[3] else t    # Sprites_CalcYFromGravity with Y = 3
        self.move_vertical(s, (a << 4) & 255, a >> 4)              # Sprites_CalcVerticalSpriteMovement with Y = 4
        s.d3 = (s.d3 + 1) & 255
        if s.d3 & 0x1F == 0:
            s.flags ^= F_DOWN

    # -- the death effect: SpriteBehavior_EnemyDeath; after 8 frames it leaves what the enemy dropped
    def behaviour_death(self, s: Sprite) -> None:
        if not s.flags & F_READY:
            s.d2 = 0
            s.flags |= F_READY
        s.d2 = (s.d2 + 1) & 255
        if s.d2 >= 8:
            self.drop(s)
            s.ent = NONE

    def sound(self, n: int) -> None:
        self.hero.events.append(n)

    def drop(self, dead: Sprite) -> None:
        """Sprite_HandleDeathDropIfPossible: into the highest free slot, if there is one."""
        free = next((i for i in range(7, -1, -1) if self.sprites[i].ent == NONE), None)
        if free is None:
            return
        kind = self.kinds[dead.internal]
        if kind["drop"] is None:
            return
        which, value = kind["drop"]
        d = self.sprites[free]
        d.value, d.x, d.y, d.hit = value, dead.x, dead.y, 0
        if which == E_COIN:
            self.sound(0x10)
        d.ent = which
        d.script = self.kinds[which]["script"]
        d.beh = 0xFF
        d.hbox = self.kinds[E_COIN]["hbox"]
        d.flags &= 0xBF

    def set_death_entity(self, s: Sprite, ent: int) -> None:
        s.internal = s.ent
        s.ent = ent
        s.script = self.kinds[ent]["script"]
        s.beh = 0xFF
        s.d2 = 0
        s.flags &= 0xBF

    # -- the sword: Player_HitSpriteWithWeapon
    def weapon_hit(self, s: Sprite) -> None:
        h = self.hero
        if s.flags & 0x10 or not h.flags & 0x80 or ((h.atk - 1) & 255) >= 2 or h.weapon & 0x80:
            return
        kind = self.kinds[s.ent]
        if kind["category"] not in (0, 7):
            return
        ex, ey = kind["extent"]
        if ((h.wx + h.rx - s.x) & 255) >= ((ex + h.rx) & 255) or ((h.wy + h.ry - s.y) & 255) >= ((ey + h.ry) & 255):
            return
        if s.ent == 5:
            s.phase |= 0x80
        self.sound(2)
        h.flags &= 0xDF
        s.flags = (s.flags & 0xFE) | (1 if h.flags & 0x40 else 0)
        s.hit = 8
        damage = self.combat["weapon"][h.weapon]
        if not h.special & 2:                                      # the pendant bug: 25% more without it
            damage = (damage + (damage >> 2)) & 255
        if not h.glove & 0x80:
            damage = (damage + self.combat["glove"][h.weapon]) & 255
        before = s.hp
        s.hp = (before - damage) & 255
        if before >= damage:                                       # (the carry of the subtraction: still alive)
            return
        self.sound(3)
        s.hit = 0
        self.hero.exp = min(self.hero.exp + self.kinds[s.ent]["exp"], 0xFFFF)
        self.set_death_entity(s, E_BOSS_DEATH if self.kinds[s.ent]["category"] == 7 else E_DEATH)

    # -- the enemy touches the hero: Player_HandleTouchEnemy, Player_ApplyDamage, Player_ReduceHP; bread and coins
    def touch(self, s: Sprite) -> None:
        h = self.hero
        if s.ent == NONE or s.flags & 0x10:
            return
        kind = self.kinds[s.ent]
        bounds = kind["bounds"]
        if s.ent in (0x1F, 0x21) and s.phase == 2:                  # Sprite_GetBounds: a wide box (SPRITE_GETBOUNDS_COMMON) in step 2 ...
            bounds = (0x30, 0x08, 0xF0, 0x00)
        elif s.ent == 0x20 and s.phase in (0, 4):                   # ... and for the Maskman in steps 0 and 4 (SPRITE_GETBOUNDS_MASKMAN)
            bounds = (0x20, 0x10, 0xF8, 0x00)
        left, top, width, height = (s.x + bounds[0]) & 255, (s.y + bounds[1]) & 255, bounds[2], bounds[3]
        if ((h.x + 0x0B - left) & 255) >= ((width + 0x0B) & 255) or ((h.y + 0x1B - top) & 255) >= ((height + 0x1B) & 255):
            return
        cat = kind["category"]
        if cat in (0, 6, 7):                                        # (6: an enemy's magic, which is gone when it has hurt him)
            if h.inv or h.ointment < 0x80:
                return
            if s.ent == 5:
                s.phase |= 0x80
            self.sound(4)
            h.inv = 0x3C
            h.flags = (h.flags & 0xBF) | (0 if s.flags & 1 else 0x40)
            h.status |= 2
            step = kind["damage"] << 5                             # a eighth of the damage, 8.8
            delta = kind["damage"] << 8
            if 0 < h.armour < 4:
                delta -= self.combat["armour"][h.armour] * step
            if h.special & 1:
                delta -= step
            self.reduce_hp(delta)
            if cat == 6:
                s.ent = NONE
        elif cat == 1:
            if s.ent == E_BREAD:
                s.ent = NONE
                self.sound(0x1B)
                h.hp_u = min((h.hp_u + s.value) & 255, 0x50) if (h.hp_u + s.value) < 256 else 0x50
            else:
                s.ent = NONE
                self.sound(9)
                h.gold = (h.gold + s.value) & 0xFFFFFF

    def reduce_hp(self, delta: int) -> None:
        h = self.hero
        v = (h.hp_u << 8 | h.hp_l) - delta
        if v < 0:
            h.hp_u, h.hp_l = 0, v & 255
            h.dead = 1
        else:
            h.hp_u, h.hp_l = v >> 8, v & 255

    def update_frame(self) -> None:
        """Sprites_UpdateAll for the sprites the sword and the touch can reach (no magic yet), the hero as `self.hero`."""
        self.counter = (self.counter + 1) & 255
        for i in range(7, -1, -1):
            self.i = i
            s = self.sprites[i]
            if s.ent == NONE:
                continue
            if s.hit:
                s.hit -= 1
                if s.ent not in (0x2C, 0x30, 0x31):
                    self.move_horiz(s, 0, 2)
                continue
            self.update_behaviour(s)
            if s.ent == NONE:                                      # (it expired or left its drop)
                continue
            self.weapon_hit(s)
            self.touch(s)

    # -- the script
    def actions(self, s: Sprite, action: int) -> None:
        if action == 0:                                            # face the hero, sideways
            if self.hero_x != s.x:
                s.flags = (s.flags & 0xFE) | (1 if self.hero_x > s.x else 0)
        elif action == 1:
            s.flags ^= F_RIGHT
        elif action == 2:                                          # face the hero, up or down
            if self.hero_y != s.y:
                s.flags = (s.flags & 0x7F) | (F_DOWN if self.hero_y > s.y else 0)
        elif action == 3:
            s.flags ^= F_DOWN
        elif action == 4:
            s.flags = (s.flags & 0xFE) | (1 if self.random() >= 0x80 else 0)
        elif action == 5:
            s.flags = (s.flags & 0x7F) | (F_DOWN if self.random() >= 0x80 else 0)
        elif action == 6:
            s.flags &= 0x7F
        elif action == 7:
            self.cast_magic(s)
        else:
            raise NotImplementedError(f"script action {action}")

    def load_next_op(self, s: Sprite) -> None:
        while True:
            ready = bool(s.beh & 0x80)
            op = self.byte(self.ip)
            if op == 0xFF:
                s.beh &= 0x7F
                return
            if op == 0:                                            # switch behaviour
                if not ready:
                    return
                s.phase = (s.phase + 1) & 255
                s.beh, s.arg1 = self.byte(self.ip + 1), self.byte(self.ip + 2)
                self.ip += 3
                return
            if op in (1, 5):                                       # (maybe disable and) go to
                if not ready:
                    return
                self.ip = self.byte(self.ip + 1) | self.byte(self.ip + 2) << 8
                if op == 5:
                    s.phase = 0
                self.finish(s)
                continue
            if op == 2:                                            # run an action
                if not ready:
                    return
                self.actions(s, self.byte(self.ip + 1))
                self.ip += 2
                continue
            if op == 3:                                            # check the distance to the hero: while the behaviour runs (a finished one skips it)
                if ready:
                    self.ip += 7
                    continue
                d = self.distance_y(s) if self.byte(self.ip + 1) else self.distance_x(s)
                at = self.ip + (3 if d < self.byte(self.ip + 2) else 5)
                self.ip = self.byte(at) | self.byte(at + 1) << 8
                return
            if op == 4:                                            # finish the behaviour
                self.ip += 1
                self.finish(s)
                continue
            if op == 7:                                            # set the phase
                if not ready:
                    return
                s.phase = self.byte(self.ip + 1)
                self.ip += 2
                continue
            raise NotImplementedError(f"script op {op}")

    def update_behaviour(self, s: Sprite) -> None:
        self.ip = s.script
        self.load_next_op(s)
        b = s.beh & 0x7F
        if b < 0x42:
            name = self.BEHAVIOURS.get(b)
            if name is None:
                raise NotImplementedError(f"behaviour {b}")
            getattr(self, name)(s)
        s.script = self.ip

    def update_all(self) -> None:
        """Sprites_UpdateAll for slots without a hit in progress."""
        self.counter = (self.counter + 1) & 255
        for i in range(7, -1, -1):
            self.i = i
            s = self.sprites[i]
            if s.ent == NONE:
                continue
            self.update_behaviour(s)


# ---- the pictures ---------------------------------------------------------------------------------------------------------------------

ZOMBIE_PHASES = (0, 1, 2, 1)           # SPRITEBEHAVIOR_ENEMY_ZOMBIE_PHASES, by (counter >> 3) & 3
MONODRON_PHASES = (0, 2, 0, 1)      # SPRITE_MONODRON_APPEARANCE_PHASES, by (phase - 1) & 3


def appearance_offset(ent: int, phase: int, counter: int, d2: int = 0) -> int:
    """The frame (added to SPRITE_APPEARANCE_PHASE_OFFSETS[ent]) the update handler of this kind picks. `counter` is SpriteUpdateCounter."""
    if ent == 0x47:                                  # Zozura: two frames, a change every 16 updates
        return (counter >> 4) & 1
    if ent == 0x2A:                                  # Monodron: by the step of the script
        return MONODRON_PHASES[(phase - 1) & 3]
    if ent == 0x0C:                                  # Snowman: still while the step is 0, then a change every 4 updates (every 8 in step 1)
        if phase == 0:
            return 0
        return (counter >> (3 if phase == 1 else 2)) & 1
    if ent == 0x06:                                  # Zombie: frame 0 while the step before is odd, else by the counter
        return 0 if (phase - 1) & 1 else ZOMBIE_PHASES[(counter >> 3) & 3]
    if ent == 0x26:                                  # Ikeda: frame 2 while the step before is odd, else a change every 4 updates
        return 2 if (phase - 1) & 1 else (counter >> 2) & 1
    if ent == 0x1B:                                  # Myconid: moves in steps 1, 3 and 5 only (step 5 twice as fast)
        if phase in (1, 3):
            return (counter >> 4) & 1
        return (counter >> 3) & 1 if phase == 5 else 0
    if ent == 0x15:                                  # Charron: picture 1 in steps 0, 1 and 3, 2 in step 5, else a change every 8 updates
        if phase == 5:
            return 2
        return 1 if phase == 0 or phase & 1 else (counter >> 3) & 1
    if ent == E_FIREBALL:
        return (counter >> 2) & 3
    if ent == 0x04:                                  # Raiden: step 2 changes every 8 updates (pictures 2, 3), the others every 4 (0, 1)
        return 2 | (counter >> 3) & 1 if phase == 2 else (counter >> 2) & 1
    if ent == 0x19:                                  # Grimlock: picture 3 in steps 9 and 11, 0 below 8, else 0, 1, 2, 1 by the counter
        if phase in (9, 11):
            return 3
        return 0 if phase < 8 else ZOMBIE_PHASES[(counter >> 3) & 3]
    if ent == 0x28:                                  # Lamprey: eight pictures of 8 updates, some of them mirrored (`flip_extra`)
        return LAMPREY_FRAMES[(counter >> 3) & 7]
    if ent == 0x1E:                                  # Giant Strider: picture 2 in step 2, else a change every 4 updates
        return 2 if phase == 2 else (counter >> 2) & 1
    if ent == 0x20:                                  # Maskman: picture 4 in the odd steps, else a change every 8 updates
        return 4 if phase & 1 else (counter >> 3) & 1
    if ent == 0x17:                                  # Geributa: picture 2 in step 0, else a change every 4 updates
        return 2 if phase == 0 else (counter >> 2) & 1
    if ent == 0x0B:                                  # Yuinaru: the second frame while bit 3 of the behaviour's count is set
        return (d2 >> 3) & 1
    if ent == 7:                                     # Hornet: a change every 4 updates
        return (counter >> 2) & 1
    if ent == 0x08:                                  # Bihoruda: picture 0 while d2 & 127 is 48 to 95, else 1
        return 0 if (d2 & 0x7F) - 0x30 & 255 < 0x30 else 1
    if ent in (0x1F, 0x21):                          # Sir Gawaine and the Wolfman: the step is the picture
        return phase
    raise NotImplementedError(f"the pictures of entity {ent}")


LAMPREY_FRAMES = (0, 1, 1, 0, 1, 1, 0, 1)        # BYTE_ARRAY_PRG14__978b
LAMPREY_FLIPS = (0, 0, 0x40, 0x40, 0x40, 0, 0, 0x40)      # LAMPREY_HORIZ_FLIP_BITS


def flip_extra(ent: int, counter: int) -> int:
    """What a kind's update handler does to the flip mask after the facing has set it (the Lamprey turns round on its own)."""
    return LAMPREY_FLIPS[(counter >> 3) & 7] if ent == 0x28 else 0


def flip_mask(flags: int) -> int:
    """CurrentSprite_UpdateFlipMask: facing right mirrors the picture."""
    return 0x40 if flags & 1 else 0
