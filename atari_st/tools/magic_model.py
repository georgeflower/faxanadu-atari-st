"""Cast magic as the ROM does it, in Python: the reference the ST code is checked against (golden run from the jsnes harness,
`tools/refnes/magicgolden.mjs`).

Read from `Player_CastMagic`, `Player_ReduceMP`, `CastMagic_UpdateDeluge/ThunderOrDeath/Fire/Tilte`, `CastMagic_UpdateXPosition`, `_UpdateYPosition`,
`CastMagic_CheckDirection*`, `Sprites_CalcYFromGravity` and the finish handlers (`CastMagic_FinishHandler_*`) that choose the picture. A spell is
`Spell`: its type (0 Deluge, 1 Thunder, 2 Fire, 3 Death, 4 Tilte; -1 none on the screen), flags (bit 6: flies right, bit 7: Tilte falls), position (full
and fraction), counter and phase. What an enemy does to a spell (the hit handlers: types 5 to 11) is not here, there are no enemies yet.
"""
from __future__ import annotations

from dataclasses import dataclass

import hero_physics as hp

DELUGE, THUNDER, FIRE, DEATH, TILTE = range(5)
COSTS = (2, 4, 6, 10, 16)                       # MAGIC_COSTS
START_Y = (8, 0, 0, 8, 8)                       # CAST_MAGIC_START_Y (the start x is 0 for all)
SPEED = (3, 2, 4, 2, 1)                         # the pixels a frame the update handlers move it
WIDTHS = (0x0F, 0x0F, 0x1F, 0x0F, 0x0F)         # CAST_MAGIC_WIDTHS: how far to the right of its x the wall check looks
HEIGHTS = (0x0F, 0x1F, 0x0F, 0x0F, 0x0F)        # CAST_MAGIC_HEIGHTS
MAX_X = (0xF0, 0xF0, 0xE0, 0xF0, 0xF0)          # CAST_MAGIC_MAX_SCREEN_WIDTHS: off the screen at the right from here
FIRST_APPEARANCE = (0x95, 0x99, 0x9B, 0x9D, 0xA1)   # SPRITE_MAGIC_IMAGE_ADDRS_U (appearances of the entity table, bank 7)
FRAMES = (4, 2, 2, 4, 4)                        # the pictures each type uses (Tilte: 0-1 on its curve, 2-3 as a missile)
SOUND_CAST, SOUND_TILTE, SOUND_HIT = 0x05, 0x14, 0x0A

RIGHT, FALLING = 0x40, 0x80


@dataclass
class Spell:
    type: int = -1
    flags: int = 0
    x: int = 0
    xfrac: int = 0
    y: int = 0
    yfrac: int = 0
    counter: int = 0
    phase: int = 0


def cast(spell: Spell, hero_x: int, hero_y: int, hero_flags: int, mp: int, selected: int, joy: int, changed: int) -> tuple[int, int | None]:
    """Player_CastMagic when no spell is on the screen: Up held and B just pressed (not on a ladder) with a spell chosen and the power for it starts
    the spell and takes the power. Returns the power left and the sound effect (or None)."""
    if hp.is_climbing(hp.Hero(x=hero_x, y=hero_y, flags=hero_flags)):
        return mp, None
    if not joy & hp.JOY_UP or not changed & hp.BUTTON_B:
        return mp, None
    if not 0 <= selected < 5 or mp < COSTS[selected]:
        return mp, None
    spell.type = selected
    spell.flags = hero_flags & RIGHT
    spell.x = hero_x
    spell.y = (hero_y + START_Y[selected]) & 0xFF
    spell.xfrac = spell.yfrac = spell.counter = spell.phase = 0
    if selected == TILTE:
        spell.flags |= FALLING
        spell.counter = 0x21
    return mp - COSTS[selected], SOUND_TILTE if selected == TILTE else SOUND_CAST


def _blocked(impassable: list[int], index: int) -> int:
    return impassable[index] if 0 <= index < 208 else 0


def _wall_check(spell: Spell, impassable: list[int], pixel_x: int) -> int:
    """CastMagic_CheckDirection_CheckImpassable: the block at the spell's y (and the one below when it is two blocks high, and the one under that when
    its y is not on a block row)."""
    y = spell.y
    index = (y & 0xF0) | (pixel_x >> 4)
    result = _blocked(impassable, index)
    if result:
        return result
    if HEIGHTS[spell.type] >= 0x10:
        index = (index + 0x10) & 0xFF
        result = _blocked(impassable, index)
        if result:
            return result
    if y & 15:
        index = (index + 0x10) & 0xFF
        result = _blocked(impassable, index)
    return result


def update_x(spell: Spell, impassable: list[int], full: int, frac: int = 0) -> tuple[bool, int]:
    """CastMagic_UpdateXPosition: moves it along its way; returns (off the screen, the wall check's result)."""
    if spell.flags & RIGHT:
        total = spell.xfrac + frac
        spell.xfrac = total & 0xFF
        spell.x = spell.x + full + (total >> 8)
        carry = spell.x > 0xFF
        spell.x &= 0xFF
        blocked = 1 if spell.x + WIDTHS[spell.type] > 0xFF else _wall_check(spell, impassable, spell.x + WIDTHS[spell.type])
        return spell.x >= MAX_X[spell.type], blocked
    total = spell.xfrac - frac
    spell.xfrac = total & 0xFF
    spell.x = (spell.x - full + (total >> 8)) & 0xFF       # total >> 8 is -1 on a borrow
    blocked = 1 if spell.x >= 0xF0 else _wall_check(spell, impassable, spell.x)
    return spell.x >= 0xF0, blocked


def update_y(spell: Spell, full: int, frac: int) -> bool:
    """CastMagic_UpdateYPosition (it never meets a wall going up or down): returns whether it is off the screen."""
    if spell.flags & FALLING:
        total = spell.yfrac + frac
        spell.yfrac = total & 0xFF
        y = spell.y + full + (total >> 8)
        spell.y = y & 0xFF
        return y > 0xFF
    total = spell.yfrac - frac
    spell.yfrac = total & 0xFF
    spell.y = (spell.y - full + (total >> 8)) & 0xFF
    return spell.y >= 0xF0


def tilte_delta(counter: int) -> int:
    """Sprites_CalcYFromGravity with Y = 3 and Sprites_CalcVerticalSpriteMovement: the fraction the curve moves it a frame (a triangle over 64 ticks)."""
    t = counter & 0x1F
    return ((0x1F - t) if counter & 0x20 else t) << 3 & 0xFF


def step(spell: Spell, impassable: list[int]) -> int | None:
    """The update handler of the spell on the screen (Player_CastMagic runs it every frame, in the frame it is cast too). Returns a sound effect or None."""
    t = spell.type
    if t in (DELUGE, FIRE):
        off, blocked = update_x(spell, impassable, SPEED[t])
        if off:
            spell.type = -1
        elif blocked:
            spell.type = -1
            return SOUND_HIT
    elif t in (THUNDER, DEATH):
        off, _ = update_x(spell, impassable, SPEED[t])
        if off:
            spell.type = -1
    elif t == TILTE:
        _tilte(spell, impassable)
    return None


def _tilte(spell: Spell, impassable: list[int]) -> None:
    if spell.phase & 1:                                     # the missile: 4 pixels along and 4 up
        if update_x(spell, impassable, 4)[0] or update_y(spell, 4, 0):
            spell.type = -1
        return
    if update_x(spell, impassable, 1)[0]:
        spell.type = -1
        return
    if update_y(spell, 0, tilte_delta(spell.counter)):
        spell.type = -1
        return
    if spell.counter & 0x1F:
        spell.counter = (spell.counter + 1) & 0xFF
        return
    spell.flags ^= FALLING                                  # every 32 ticks the curve turns
    if not spell.flags & FALLING:
        spell.counter = (spell.counter + 1) & 0xFF
        return
    spell.phase += 1
    spell.flags &= ~FALLING & 0xFF


def appearance(spell: Spell, ic: int) -> int | None:
    """The picture (the appearance number of the entity table) the finish handler picks for the interrupt counter `ic`, or None when it draws nothing
    this frame (Thunder, Fire and the Tilte missile blink)."""
    t = spell.type
    if t == DELUGE:
        return FIRST_APPEARANCE[t] + (ic >> 2 & 3)
    if t == THUNDER:
        return None if ic & 2 else FIRST_APPEARANCE[t] + (ic >> 2 & 1)
    if t == FIRE:
        return FIRST_APPEARANCE[t] + (ic >> 2 & 1) if ic & 2 else None
    if t == DEATH:
        return FIRST_APPEARANCE[t] + (ic >> 3 & 3)
    if t == TILTE:
        if spell.phase & 1:
            return None if ic & 2 else FIRST_APPEARANCE[t] + 2 + (ic >> 2 & 1)
        return FIRST_APPEARANCE[t] + (1 if ic & 8 else 0)
    return None
