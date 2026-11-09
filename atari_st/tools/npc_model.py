"""The town people's behaviour (entities $34-$45, category 2 of the sprite engine) in Python, as the ROM does it.

A person is a sprite like an enemy: it has a slot (the first of a screen's sprite list goes to slot 7), a behaviour script from bank 14 (`SPRITE_BSCRIPTS`) and an
update handler that picks its picture. `Sprites_UpdateAll` runs the script (`enemy_model.Engine`: the ops and the behaviours Wait (1), Walk (4), Hop (9), Fall (21,
a countdown) and MoveTowardPlayer (0); op 6 adds a value to the sprite's x) and then the handler; the sword and a touch do nothing to a person (`Player_HitSpriteWithWeapon`
and the touch handler only look at categories 0, 6 and 7). `tools/refnes/npcprobe.mjs` records the game and `tests/test_npc.py` compares: the state of every slot
each frame, and the sprites on show.

The scripts, what each kind does (frames of the game at 50 or 60 a second, 0.75 pixel a frame is a speed of $C0):
  $34 walking man: walk 60 (192 = 0.75 px), stand 30, face the hero, again.        $35 blue lady: walk 80 at 0.5, flip, walk 20, flip, walk 80, flip.
  $36 child: walk 60, two hops (kind 3), walk 10, stand 5, flip.                    $38 martial artist, $3B magic teacher: face the hero every frame.
  $39 priest: face the hero, x + 4, stand.  $3A King: stands; the hero nearer than 64 pixels: x + 8 (near picture); beyond 72: x - 8 (far picture).
  $3D smoking man: flip every 5 frames.  $3E man in a chair: face the hero every 5 frames.  $40 meat salesman: face the hero once.  $43 doctor: x + 8.
  $41 lady: move 192 at 0.5, stand 5, move 40, flip.  $42 guard: move 80 at 0.75, stand 5, flip.  $44 nurse: move 80, stand 10, flip, face the hero.
  $45 woman: move 60 at 0.5, flip, move 80 at 0.5, flip.  $37, $3C, $3F: stand.
"""
from __future__ import annotations

import enemy_data as ed
import enemy_model as em
import faxanadu_maps as fm
import iscripts as isc

FIRST, LAST = isc.FIRST_NPC, isc.LAST_NPC
ENTITIES = tuple(range(FIRST, LAST + 1))


def kind_info(rom, ent: int) -> dict:
    """What the engine asks of a person's kind: the ROM's own table entries (the script in bank 14, the hit box type the wall tests use)."""
    info = ed.kind_info(rom, ent)
    info["hitbox"] = ed.entity(rom, ent)["hitbox"]
    return info


def people(rom, area: int, screen: int) -> list[tuple[int, int, int, int]]:
    """The people of a screen in the order the ROM puts them in slots (the first in slot 7): (entity, script id, x, y). Area 4 is the buildings (the screen is the building's id)."""
    return [(ent, script, x, y) for a, s, ent, script, x, y in isc.placements(rom) if (a, s) == (area, screen) and ent in ENTITIES]


def engine(rom, area: int, screen: int, blocks: bytes, hero_x: int, hero_y: int = 144) -> em.Engine:
    """The model with the people of a screen as `Screen_LoadSpriteInfo` places them (behaviour ready, phase and flags 0), the hero where he is. `blocks` is the 256 bytes of
    the screen buffer; the block properties are those of the area (4 in a building: `screen` is then the building's id, the layout screen is up to the caller)."""
    props = fm.block_properties(rom, fm.area(rom, area))
    eng = em.Engine(rom.prg(14), ed.random_table(rom), blocks, props)
    eng.hero_x, eng.hero_y = hero_x, hero_y
    for ent in ENTITIES:
        eng.kinds[ent] = kind_info(rom, ent)
    for i, (ent, script, x, y) in enumerate(people(rom, area, screen)):
        s = eng.sprites[7 - i]
        s.ent, s.x, s.y, s.beh, s.hbox = ent, x, y, 0xFF, eng.kinds[ent]["hitbox"]
        s.script = eng.kinds[ent]["script"]
    return eng


def appearance(ent: int, phase: int, flags: int, counter: int) -> tuple[int, int]:
    """(frame, mirrored) the update handler of a kind picks (`SpriteUpdateHandler_NPC_*`; the pose is `Sprite_EnterNextAppearancePhase`'s offset): the walkers
    (counter >> 3 & 3 over frames 0, 1, 0, 2, frame 0 while the phase is 2), the King (counter >> 4 & 1, plus 2 from phase 2 on), the rest counter >> 4 & 1. Mirrored: `CurrentSprite_UpdateFlipMask`
    (facing right), or always ($3A, $3C-$3F: the handler sets the mask $40), or never ($37, $43)."""
    anim, mirror = isc.NPC_RULES[ent]
    if anim == 1:
        frame = 0 if phase == 2 else (0, 1, 0, 2)[(counter >> 3) & 3]
    elif anim == 2:
        frame = (counter >> 4 & 1) + (0, 2)[(phase - 1) & 1]
    else:
        frame = counter >> 4 & 1
    return frame, (flags & 1 if mirror == 2 else mirror)
