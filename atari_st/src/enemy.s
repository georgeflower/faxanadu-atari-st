| Enemies: the ROM's sprite engine (Sprites_UpdateAll and what it calls) for the kinds in the package. tools/enemy_model.py is the reference
| (tests/test_enemy.py checks it against the game), this is the same in 68000. A slot (E_xxx) holds what CurrentSprites_xxx holds; the script
| is a few bytes of the package (enemy_scripts), E_SCRIPT the offset of its next op. The kinds (enemy_kinds) say how a kind starts and looks.

    .equ E_ENT, 0                           | the kind (the ROM's entity), $FF: the slot is empty
    .equ E_FLAGS, 1                         | bit 0 faces right, 1 flies, 2 in the air, 6 behaviour ready, 7 falling (down; clear: up)
    .equ E_X, 2                             | x and its fraction: one word, 8.8
    .equ E_XF, 3
    .equ E_Y, 4
    .equ E_YF, 5
    .equ E_PHASE, 6
    .equ E_BEH, 7                           | the behaviour; bit 7: it has finished, the next op runs
    .equ E_ARG1, 8                          | the countdown
    .equ E_INT, 9                           | the hop kind
    .equ E_D3, 10                           | the walk's speed (whole pixels, then the fraction), the hop's tick (the whole pixels' byte)
    .equ E_D2, 11
    .equ E_BXFULL, 12                       | the hop's sideways speed (whole pixels, then the fraction)
    .equ E_BXF, 13
    .equ E_HBOX, 14
    .equ E_HP, 15
    .equ E_SCRIPT, 16                       | word
    .equ E_KIND, 18                         | long: the kind's record in the package
    .equ E_HIT, 22                          | CurrentSprites_HitCounter: 8 when the sword hit it, counts down; it stands still (and blinks) meanwhile
    .equ E_VAL, 23                          | CurrentSprites_Values: what a dropped coin is worth, how much bread heals
    .equ E_PREV, 24                         | long: the kind record of what a dying enemy was (its drop, CurrentSprites_InternalBehaviorStates)
    .equ E_BYTES, 28
    .equ K_HBOX, 2                          | in a kind's record: the hit box type, the script's offset, the first pose, the picture rule, experience, drop (kind << 8 | value),
    .equ K_SCRIPT, 6                        | the weapon's extents, the touch box (left, top, width, height) and the damage (all words)
    .equ K_POSE, 8
    .equ K_RULE, 10
    .equ K_EXP, 12
    .equ K_DROP, 14
    .equ K_EXTX, 16
    .equ K_EXTY, 18
    .equ K_BL, 20
    .equ K_BT, 22
    .equ K_BW, 24
    .equ K_BH, 26
    .equ K_DMG, 28
    .equ KIND_BYTES, 32
    .equ E_BREAD, 1                         | the entities that are not enemies: bread and a coin (drops), the death effect
    .equ E_COIN, 2
    .equ E_DEATH, 0x13
    .equ E_FIREBALL, 0x54                   | Charron's fireball (cast, never placed)
    .equ E_MAGIC, 0x51                      | the magic of Nash and the Execution Hood

    .text
| All slots empty, their drawn boxes forgotten (the screens are clean when this is called).
enemies_clear:
    movem.l %d0/%a0, -(%sp)
    lea enemies(%pc), %a0
    moveq #8-1, %d0
1:  move.b #0xFF, E_ENT(%a0)
    lea E_BYTES(%a0), %a0
    dbra %d0, 1b
    lea enemy_rects(%pc), %a0
    moveq #(2*8*8/4)-1, %d0
2:  clr.l (%a0)+
    dbra %d0, 2b
    movem.l (%sp)+, %d0/%a0
    rts

| The enemies of the screen cur_screen, from the package, in the slots from 7 down (Screen_LoadSpriteInfo, Sprites_PopulateNextAvailableSprite).
enemies_load:
    movem.l %d0-%d4/%a0-%a3, -(%sp)
    bsr.s enemies_clear
    .ifdef NO_ENEMIES                       | (the picture tests of the screens and the doors want an empty field)
    bra.w 9f
    .endif
    movea.l pkg_ptr+PKG_ENEMY_PLACES(%pc), %a2
    move.w cur_screen(%pc), %d0
    add.w %d0, %d0
    moveq #0, %d1
    move.w (%a2,%d0.w), %d1
    adda.l %d1, %a2                         | this screen's list
    lea enemies(%pc), %a3
    adda.w #7*E_BYTES, %a3
    moveq #7, %d4
1:  move.w (%a2)+, %d0
    bmi.w 9f
    move.w (%a2)+, %d1                      | x
    move.w (%a2)+, %d2                      | y
    movea.l pkg_ptr+PKG_ENEMY_KINDS(%pc), %a0
2:  move.w (%a0), %d3
    bmi.s 1b                                | a kind that is not known yet: not put on the screen
    cmp.w %d3, %d0
    beq.s 3f
    lea KIND_BYTES(%a0), %a0
    bra.s 2b
3:  move.b %d0, E_ENT(%a3)
    clr.b E_FLAGS(%a3)
    move.b %d1, E_X(%a3)
    clr.b E_XF(%a3)
    move.b %d2, E_Y(%a3)
    clr.b E_YF(%a3)
    clr.b E_PHASE(%a3)
    move.b #0xFF, E_BEH(%a3)
    clr.b E_ARG1(%a3)
    clr.b E_INT(%a3)
    clr.w E_D3(%a3)
    clr.w E_BXFULL(%a3)
    move.b 3(%a0), E_HBOX(%a3)
    move.b 5(%a0), E_HP(%a3)
    move.w 6(%a0), E_SCRIPT(%a3)
    move.l %a0, E_KIND(%a3)
    clr.b E_HIT(%a3)
    clr.b E_VAL(%a3)
    clr.l E_PREV(%a3)
    lea -E_BYTES(%a3), %a3
    subq.w #1, %d4
    bpl.s 1b
9:  movem.l (%sp)+, %d0-%d4/%a0-%a3
    rts

| Puts the background back where the enemies were drawn in screen a4 (two frames ago) and forgets the boxes.
enemies_erase:
    movem.l %d0/%a0, -(%sp)
    lea enemy_rects(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #6, %d0
    adda.w %d0, %a0
    moveq #8-1, %d0
1:  tst.w 2(%a0)
    beq.s 2f
    bsr.w restore_rect
    clr.l (%a0)
    clr.l 4(%a0)
2:  addq.l #8, %a0
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0
    rts

| Sprites_UpdateAll: one frame of every enemy, the highest slot first. en_counter is SpriteUpdateCounter.
enemies_update:
    movem.l %d0-%d7/%a0-%a5, -(%sp)
    lea en_counter(%pc), %a0
    addq.w #1, (%a0)
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags
    lea en_blocks(%pc), %a1
    move.l %a2, (%a1)+
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a0
    adda.l %d0, %a0
    move.l %a0, (%a1)
    movea.l pkg_ptr+PKG_ENEMY_SCRIPTS(%pc), %a5
    lea enemies(%pc), %a3
    adda.w #7*E_BYTES, %a3
    moveq #7, %d7
1:  cmpi.b #0xFF, E_ENT(%a3)
    beq.s 2f
    tst.b E_HIT(%a3)
    beq.s 3f
    subq.b #1, E_HIT(%a3)                   | hit: it stands still, and is pushed two pixels the way it faces (Tamazutsu is not)
    cmpi.b #0x2C, E_ENT(%a3)
    beq.s 2f
    move.w #0x0200, %d3
    bsr.w en_step_x
    bra.s 2f
3:  bsr.s en_behaviour
    cmpi.b #0xFF, E_ENT(%a3)                | (it expired, or left its drop)
    beq.s 2f
    bsr.w en_weapon
    bsr.w en_touch
2:  lea -E_BYTES(%a3), %a3
    dbra %d7, 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a5
    rts

| Sprites_UpdateBehavior for the slot a3: the next op when the behaviour has finished, then the behaviour. a5 = the scripts, d6 = the script's offset.
en_behaviour:
    moveq #0, %d6
    move.w E_SCRIPT(%a3), %d6
    bsr.w en_ops
    moveq #0, %d0
    move.b E_BEH(%a3), %d0
    andi.w #0x7F, %d0
    cmpi.w #0x42, %d0
    bcc.w en_behaviour_end
    cmpi.w #4, %d0
    beq.w beh_walk
    cmpi.w #23, %d0
    beq.w beh_bihoruda
    cmpi.w #25, %d0
    beq.w beh_wave
    cmpi.w #27, %d0
    beq.w beh_fireball
    cmpi.w #30, %d0
    beq.w beh_finish
    cmpi.w #22, %d0
    beq.w beh_necron
    cmpi.w #26, %d0
    beq.w beh_nash
    cmpi.w #31, %d0
    beq.w beh_flash
    cmpi.w #32, %d0
    beq.w beh_bees
    cmpi.w #35, %d0
    beq.w beh_magman
    cmpi.w #39, %d0
    beq.w beh_tamazutsu
    cmpi.w #65, %d0
    beq.w beh_hood
    cmpi.w #33, %d0
    beq.w beh_naga
    cmpi.w #34, %d0
    beq.w beh_yareeka
    cmpi.w #40, %d0
    beq.w beh_gawaine
    cmpi.w #63, %d0
    beq.w beh_buzz
    tst.w %d0
    beq.w beh_move_toward
    cmpi.w #2, %d0
    beq.w beh_bounce
    cmpi.w #7, %d0
    beq.w beh_death
    cmpi.w #9, %d0
    beq.w beh_hop
    cmpi.w #21, %d0
    beq.w beh_fall
    cmpi.w #1, %d0
    bne.s en_behaviour_end
    bsr.w en_ready                          | Wait
    bsr.w en_countdown
en_behaviour_end:
    move.w %d6, E_SCRIPT(%a3)
    rts

en_finish:                                  | Sprite_FinishBehavior
    bclr #6, E_FLAGS(%a3)
    bset #7, E_BEH(%a3)
    rts

en_ready:                                   | Sprite_SetBehaviorReady
    bset #6, E_FLAGS(%a3)
    rts

en_countdown:                               | Sprites_CountdownBehavior
    tst.b E_ARG1(%a3)
    beq.s 1f
    subq.b #1, E_ARG1(%a3)
    bne.s 1f
    bra.s en_finish
1:  rts

| BScripts_LoadNextOp: runs ops while they chain. d6 = offset of the next op (updated).
en_ops:
1:  move.b (%a5,%d6.w), %d0
    cmpi.b #0xFF, %d0
    bne.s 2f
    bclr #7, E_BEH(%a3)                     | the end: the behaviour goes on
    rts
2:  tst.b %d0
    beq.s op_switch
    cmpi.b #4, %d0
    beq.s op_finish
    cmpi.b #3, %d0
    beq.s op_distance
    tst.b E_BEH(%a3)                        | the other ops wait for a finished behaviour
    bpl.s 9f
    cmpi.b #5, %d0
    beq.s op_goto
    cmpi.b #1, %d0
    beq.s op_goto
    cmpi.b #2, %d0
    beq.s op_action
    cmpi.b #7, %d0
    beq.s op_phase
9:  rts

op_switch:                                  | 0: behaviour, countdown
    tst.b E_BEH(%a3)
    bpl.s 9b
    addq.b #1, E_PHASE(%a3)
    move.b 1(%a5,%d6.w), E_BEH(%a3)
    move.b 2(%a5,%d6.w), E_ARG1(%a3)
    addq.w #3, %d6
    rts

op_finish:                                  | 4: ends the behaviour at once
    addq.w #1, %d6
    bsr.w en_finish
    bra.s 1b

op_phase:                                   | 7: set the phase
    move.b 1(%a5,%d6.w), E_PHASE(%a3)
    addq.w #2, %d6
    bra.s 1b

op_goto:                                    | 1 and 5: go to an address (5 also sets the phase to 0) and end the behaviour
    cmpi.b #5, %d0
    bne.s 3f
    clr.b E_PHASE(%a3)
3:  moveq #0, %d0
    move.b 2(%a5,%d6.w), %d0
    lsl.w #8, %d0
    move.b 1(%a5,%d6.w), %d0
    move.w %d0, %d6
    bsr.w en_finish
    bra.w 1b

op_action:                                  | 2: an action
    moveq #0, %d0
    move.b 1(%a5,%d6.w), %d0
    addq.w #2, %d6
    bsr.s en_action
    bra.w 1b

op_distance:                                | 3: the distance to the hero, sideways or up and down, below a value or not: two addresses
    tst.b E_BEH(%a3)
    bpl.s 4f
    addq.w #7, %d6                          | finished: skipped (the check is made while the behaviour runs)
    bra.w 1b
4:  tst.b 1(%a5,%d6.w)
    bne.s 5f
    bsr.w en_distance_x
    bra.s 6f
5:  bsr.w en_distance_y
6:  cmp.b 2(%a5,%d6.w), %d0
    bcs.s 7f
    addq.w #2, %d6                          | not below: the second address
7:  moveq #0, %d0
    move.b 4(%a5,%d6.w), %d0
    lsl.w #8, %d0
    move.b 3(%a5,%d6.w), %d0
    move.w %d0, %d6
    rts

| BSCRIPT_ACTIONS: d0 = the action.
en_action:
    tst.w %d0
    beq.w ac_face_x
    cmpi.w #1, %d0
    beq.w ac_flip_x
    cmpi.w #2, %d0
    beq.w ac_face_y
    cmpi.w #3, %d0
    beq.w ac_flip_y
    cmpi.w #4, %d0
    beq.w ac_random_x
    cmpi.w #5, %d0
    beq.w ac_random_y
    cmpi.w #6, %d0
    bne.s 8f
    bclr #7, E_FLAGS(%a3)                   | fly up
    rts
8:  cmpi.w #7, %d0
    beq.s ac_cast
9:  rts
ac_flip_x:
    eori.b #1, E_FLAGS(%a3)
    rts
ac_flip_y:
    eori.b #0x80, E_FLAGS(%a3)
    rts
ac_face_x:                                  | towards the hero, unless he is at the same x
    move.w hero_x(%pc), %d1
    cmp.b E_X(%a3), %d1
    beq.s 9b
    bcs.s 1f
    bset #0, E_FLAGS(%a3)
    rts
1:  bclr #0, E_FLAGS(%a3)
    rts
ac_face_y:
    move.w hero_y(%pc), %d1
    cmp.b E_Y(%a3), %d1
    beq.s 9b
    bcs.s 1f
    bset #7, E_FLAGS(%a3)
    rts
1:  bclr #7, E_FLAGS(%a3)
    rts
ac_random_x:
    bsr.w en_random
    bclr #0, E_FLAGS(%a3)
    cmpi.b #0x80, %d0
    bcs.s 9b
    bset #0, E_FLAGS(%a3)
    rts
ac_random_y:
    bsr.w en_random
    bclr #7, E_FLAGS(%a3)
    cmpi.b #0x80, %d0
    bcs.s 9b
    bset #7, E_FLAGS(%a3)
    rts

| GetRandom: a byte of the ROM's own code, mixed with the buttons held. Out: d0.b. Clobbers a0, d1.
ac_cast:                                    | BScript_Action_CastMagic: a fireball from the caster's x, 8 lines below its top
    movem.l %d0-%d2, -(%sp)
    moveq #E_FIREBALL, %d0
    moveq #0, %d1
    moveq #8, %d2
    bsr.s ac_cast_at
    movem.l (%sp)+, %d0-%d2
    rts
ac_cast_at:                                 | a magic sprite (d0.b = its kind) in the highest free slot, from the caster's x + d1.b and y + d2.b, the way it faces
    movem.l %d0-%d5/%a0-%a1, -(%sp)
    move.b %d1, %d4
    move.b %d2, %d5
    lea enemies(%pc), %a0
    adda.w #7*E_BYTES, %a0
    moveq #7, %d3
1:  cmpi.b #0xFF, E_ENT(%a0)
    beq.s 2f
    lea -E_BYTES(%a0), %a0
    dbra %d3, 1b
    bra.s 8f
2:  movea.l %a0, %a1
    andi.w #0xFF, %d0
    bsr.w en_find_kind
    move.l %a0, %d1
    beq.s 8f
    move.b %d0, E_ENT(%a1)
    move.b E_FLAGS(%a3), %d1
    andi.b #1, %d1
    move.b %d1, E_FLAGS(%a1)
    move.b E_X(%a3), %d1
    add.b %d4, %d1
    move.b %d1, E_X(%a1)
    move.b E_Y(%a3), %d1
    add.b %d5, %d1
    move.b %d1, E_Y(%a1)
    clr.b E_PHASE(%a1)
    move.b #0xFF, E_BEH(%a1)
    move.b 3(%a0), E_HBOX(%a1)
    move.w 6(%a0), E_SCRIPT(%a1)
    move.l %a0, E_KIND(%a1)
8:  movem.l (%sp)+, %d0-%d5/%a0-%a1
    rts
en_random:
    lea en_rnd(%pc), %a0
    moveq #0, %d1
    move.b (%a0), %d1
    addq.b #1, (%a0)
    lea random_table(%pc), %a0
    move.b (%a0,%d1.w), %d0
    lea input_state(%pc), %a0
    move.b IN_PAD(%a0), %d1
    eor.b %d1, %d0
    rts

| Sprite_CalcDistanceXToPlayer and ...Y: out d0.b. Clobbers d1-d2, a0.
en_distance_x:
    move.w hero_x(%pc), %d1
    moveq #0, %d0
    move.b E_X(%a3), %d0
    sub.w %d1, %d0                          | sprite - hero
    bmi.s 1f
    subi.w #0x10, %d0
    bpl.s 2f
    moveq #0, %d0
    rts
1:  neg.w %d0
    moveq #0, %d2
    move.b E_HBOX(%a3), %d2
    lea hbox_width(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d2.w), %d1
    sub.w %d1, %d0
    bpl.s 2f
    moveq #0, %d0
2:  rts
en_distance_y:
    move.w hero_y(%pc), %d1
    moveq #0, %d0
    move.b E_Y(%a3), %d0
    sub.w %d1, %d0
    bpl.s 1f
    neg.w %d0
1:  rts

| ---------------------------------------------------------------------------------------------------------------------- the behaviours
| WalkForward: the speed from the script, one step forward, turning round at a wall; in the air it turns round and falls instead.
beh_walk:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b (%a5,%d6.w), E_D2(%a3)
    move.b 1(%a5,%d6.w), E_D3(%a3)
    addq.w #2, %d6
    bsr.w en_ready
1:  bsr.w en_can_move
    tst.w %d0
    beq.s 2f
    eori.b #1, E_FLAGS(%a3)
    bsr.w en_fall_step
    bra.w en_behaviour_end
2:  move.w E_D3(%a3), %d3
    bsr.w en_step_x
    tst.w %d0
    beq.s 3f
    eori.b #1, E_FLAGS(%a3)
3:  bsr.w en_countdown
    bra.w en_behaviour_end

| MoveTowardPlayer: forward at a steady pace (the script turns it to the hero by an action), falling when there is no floor, not turning at a wall.
beh_move_toward:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b (%a5,%d6.w), E_D2(%a3)
    move.b 1(%a5,%d6.w), E_D3(%a3)
    addq.w #2, %d6
    bsr.w en_ready
    bclr #1, E_FLAGS(%a3)
1:  bsr.w en_can_move
    tst.w %d0
    beq.s 2f
    bsr.w en_fall_step
    btst #1, E_FLAGS(%a3)
    bne.w en_behaviour_end
2:  move.w E_D3(%a3), %d3
    bsr.w en_step_x
    bsr.w en_countdown
    bra.w en_behaviour_end

| Yuinaru: through everything, sideways on one triangle wave (the count in E_D2) and up and down on another (E_D3), turning at the edges of the screen.
beh_wave:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D2(%a3)
    move.b #0x80, E_D3(%a3)
    bsr.w en_ready
1:  moveq #0, %d0
    move.b E_D2(%a3), %d0
    move.w %d0, %d1
    andi.w #0x7F, %d1
    btst #7, %d0
    beq.s 2f
    moveq #0x7F, %d2
    sub.w %d1, %d2
    move.w %d2, %d1
2:  move.w %d1, %d2                         | the step: the wave's value x 8 (whole pixels in the high byte, at most 3)
    lsl.w #3, %d1
    andi.w #0xFF, %d1
    lsr.w #5, %d2
    andi.w #3, %d2
    lsl.w #8, %d2
    or.w %d1, %d2
    move.w E_X(%a3), %d0
    btst #0, E_FLAGS(%a3)
    beq.s 3f
    add.w %d2, %d0
    bra.s 4f
3:  sub.w %d2, %d0
4:  move.w %d0, E_X(%a3)
    cmpi.w #0xF000, %d0
    bcs.s 5f                                | at the right edge (or wrapped round the left one): put on a block edge, turn
    move.b E_X(%a3), %d0
    andi.b #0xF0, %d0
    btst #0, E_FLAGS(%a3)
    bne.s 6f
    addi.b #0x10, %d0
6:  move.b %d0, E_X(%a3)
    eori.b #1, E_FLAGS(%a3)
5:  addq.b #1, E_D2(%a3)
    moveq #0, %d0
    move.b E_D3(%a3), %d0
    move.w %d0, %d1
    andi.w #0x3F, %d1
    btst #6, %d0
    beq.s 7f
    moveq #0x3F, %d2
    sub.w %d1, %d2
    move.w %d2, %d1
7:  move.w %d1, %d2
    lsl.w #3, %d1
    andi.w #0xFF, %d1
    lsr.w #5, %d2
    andi.w #1, %d2
    lsl.w #8, %d2
    or.w %d1, %d2
    move.w E_Y(%a3), %d0
    btst #7, E_FLAGS(%a3)
    beq.s 8f
    add.w %d2, %d0
    bra.s 9f
8:  sub.w %d2, %d0
9:  move.w %d0, E_Y(%a3)
    cmpi.w #0xE000, %d0
    bcs.s 10f                               | at the bottom of the screen: put on a block edge, turn
    move.b E_Y(%a3), %d0
    andi.b #0xF0, %d0
    btst #7, E_FLAGS(%a3)
    bne.s 11f
    addi.b #0x10, %d0
11: move.b %d0, E_Y(%a3)
    eori.b #0x80, E_FLAGS(%a3)
10: addq.b #1, E_D3(%a3)
    bra.w en_behaviour_end

| The thunk to Sprite_FinishBehavior (Geributa's first behaviour): over at once, the script goes on.
beh_finish:
    bsr.w en_finish
    bra.w en_behaviour_end

| Charron's fireball (EnemyMagic): two pixels forward a frame, through everything; at the edge of the screen it is put on a block edge, turned round and gone.
beh_fireball:
    bsr.w en_ready
    move.w E_X(%a3), %d0
    btst #0, E_FLAGS(%a3)
    beq.s 1f
    addi.w #0x0200, %d0
    bra.s 2f
1:  subi.w #0x0200, %d0
2:  move.w %d0, E_X(%a3)
    cmpi.w #0xF000, %d0
    bcs.s 3f
    move.b E_X(%a3), %d0
    andi.b #0xF0, %d0
    btst #0, E_FLAGS(%a3)
    bne.s 4f
    addi.b #0x10, %d0
4:  move.b %d0, E_X(%a3)
    eori.b #1, E_FLAGS(%a3)
    move.b #0xFF, E_ENT(%a3)
3:  bra.w en_behaviour_end

| Hornet (BuzzAround): two pixels sideways a frame, turning at a wall; up and down by a table of eight steps, each for eight frames.
beh_buzz:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_PHASE(%a3)
    clr.b E_D2(%a3)
    bsr.w en_ready
1:  move.w #0x0200, %d3
    bsr.w en_step_x
    tst.w %d0
    beq.s 2f
    eori.b #1, E_FLAGS(%a3)
2:  moveq #0, %d0
    move.b E_D2(%a3), %d0
    lsr.w #3, %d0
    andi.w #7, %d0
    lea buzz_frac(%pc), %a0
    moveq #0, %d3
    move.b (%a0,%d0.w), %d3
    lea buzz_full(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    lsl.w #8, %d1
    or.w %d1, %d3
    bsr.w en_step_y
    tst.w %d0
    beq.s 3f
    eori.b #0x80, E_FLAGS(%a3)
3:  addq.b #1, E_D2(%a3)
    bra.w en_behaviour_end

| Bihoruda: it flies, sideways and up and down each on a triangle wave of 64 ticks (E_D2 counts the sideways one, E_D3 the other, started 64 ticks
| later), turning at a wall.
beh_bihoruda:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D2(%a3)
    move.b #0x40, E_D3(%a3)
    bsr.w en_ready
1:  moveq #0, %d0
    move.b E_D2(%a3), %d0
    bsr.w en_triangle
    move.w %d0, %d3
    bsr.w en_step_x
    tst.w %d0
    beq.s 2f
    eori.b #1, E_FLAGS(%a3)
2:  addq.b #1, E_D2(%a3)
    moveq #0, %d0
    move.b E_D3(%a3), %d0
    bsr.w en_triangle
    move.w %d0, %d3
    bsr.w en_step_y
    tst.w %d0
    beq.s 3f
    eori.b #0x80, E_FLAGS(%a3)
3:  addq.b #1, E_D3(%a3)
    bra.w en_behaviour_end

| Sprites_CalcYFromGravity for gravity 2 and the shift of the step: in d0.w = a count, out d0.w = its triangle wave (0 to 63) times 8, which is a step
| with the whole pixels in the high byte. Clobbers d1.
en_triangle:
    move.w %d0, %d1
    andi.w #0x3F, %d0
    btst #6, %d1
    beq.s 1f
    moveq #0x3F, %d1
    sub.w %d0, %d1
    move.w %d1, %d0
1:  lsl.w #3, %d0
    rts

| Sir Gawaine and the Wolfman: walks to the hero (a pixel a frame) until it is 24 away, then stands facing him; when he is in the air it rushes at him,
| two pixels a frame. The step it is in (E_PHASE) is the picture.
beh_gawaine:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  bsr.w en_can_move
    tst.w %d0
    beq.s 2f
    bsr.w en_fall_step
2:  clr.b E_PHASE(%a3)
    bsr.w en_distance_x
    cmpi.b #0x18, %d0
    beq.w en_behaviour_end
    bcs.s 4f
    bsr.w ac_face_x
    move.w #0x0100, %d3
    bsr.w en_step_x
    move.w en_counter(%pc), %d0
    btst #3, %d0
    beq.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    bra.w en_behaviour_end
4:  move.b #1, E_PHASE(%a3)
    move.w hero_air(%pc), %d0
    btst #0, %d0
    bne.s 5f
    bsr.w ac_face_x
    moveq #0, %d0
    move.w en_counter(%pc), %d1
    btst #4, %d1
    beq.s 6f
    moveq #2, %d0
6:  move.b %d0, E_PHASE(%a3)
    bra.w en_behaviour_end
5:  clr.b E_PHASE(%a3)
    bsr.w ac_face_x
    move.w #0x0200, %d3
    bsr.w en_step_x
    move.w en_counter(%pc), %d0
    btst #2, %d0
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    bra.w en_behaviour_end

| Naga: it faces the hero and bobs up and down on a triangle wave of 32 ticks (E_D3 counts them), turning up or down every 32 ticks; when he is
| 16 or more lines above or below it also creeps towards his height, 3/4 of a pixel a frame, without changing the way it bobs.
beh_naga:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D3(%a3)
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  bsr.w ac_face_x
    moveq #0, %d0
    move.b E_D3(%a3), %d0
    move.w %d0, %d1
    andi.w #0x0F, %d0
    btst #4, %d1
    beq.s 2f
    moveq #0x0F, %d1
    sub.w %d0, %d1
    move.w %d1, %d0
2:  lsl.w #5, %d0                           | the step: 16 bits, the whole pixels (0 or 1) in the high byte
    move.w %d0, %d3
    bsr.w en_step_y
    addq.b #1, E_D3(%a3)
    move.b E_D3(%a3), %d0
    andi.b #0x1F, %d0
    bne.s 3f
    eori.b #0x80, E_FLAGS(%a3)
3:  bsr.w en_distance_y
    cmpi.b #0x10, %d0
    bcs.w en_behaviour_end
    move.b E_FLAGS(%a3), -(%sp)
    bsr.w ac_face_y
    move.w #0x00C0, %d3
    bsr.w en_step_y
    move.b (%sp)+, E_FLAGS(%a3)
    bra.w en_behaviour_end

| Yareeka: three steps (E_PHASE), E_D2 counting. 0: sideways on the rising half of a triangle wave (64 ticks); 1: two pixels a frame for 64 frames;
| 2: the falling half of the wave (64 ticks); then again.
beh_yareeka:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D2(%a3)
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  move.b E_PHASE(%a3), %d0
    cmpi.b #2, %d0
    beq.s 4f
    cmpi.b #1, %d0
    beq.s 5f
    bsr.w en_yareeka_wave
    cmpi.b #0x40, E_D2(%a3)
    bcs.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x40, E_D2(%a3)
    bra.w en_behaviour_end
5:  move.w #0x0200, %d3
    bsr.w en_step_x
    tst.w %d0
    beq.s 6f
    eori.b #1, E_FLAGS(%a3)
6:  subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x40, E_D2(%a3)
    bra.w en_behaviour_end
4:  bsr.w en_yareeka_wave
    cmpi.b #0x80, E_D2(%a3)
    bcs.w en_behaviour_end
    clr.b E_PHASE(%a3)
    clr.b E_D2(%a3)
    bra.w en_behaviour_end

en_yareeka_wave:                            | one step sideways on the triangle wave of E_D2, turning at a wall
    moveq #0, %d0
    move.b E_D2(%a3), %d0
    bsr.w en_triangle
    move.w %d0, %d3
    addq.b #1, E_D2(%a3)
    bsr.w en_step_x
    tst.w %d0
    beq.s 9f
    eori.b #1, E_FLAGS(%a3)
9:  rts

| Sprite_Maybe_TurnAroundIfAtScreenEdgeHoriz: d3.w = the step; forward through everything; at the screen's edge it is put on a block edge and turns round.
en_edge_x:
    move.w E_X(%a3), %d0
    btst #0, E_FLAGS(%a3)
    beq.s 1f
    add.w %d3, %d0
    bra.s 2f
1:  sub.w %d3, %d0
2:  move.w %d0, E_X(%a3)
    cmpi.b #0xF0, E_X(%a3)
    bcs.s 9f
    move.b E_X(%a3), %d0
    andi.b #0xF0, %d0
    btst #0, E_FLAGS(%a3)
    bne.s 3f
    addi.b #0x10, %d0
3:  move.b %d0, E_X(%a3)
    eori.b #1, E_FLAGS(%a3)
9:  rts

| Sprite_Maybe_TurnAroundIfAtScreenEdgeVert: d3.w = the step; up or down through everything; below line 224 it is put on a block edge and turns round.
en_edge_y:
    move.w E_Y(%a3), %d0
    btst #7, E_FLAGS(%a3)
    beq.s 1f
    add.w %d3, %d0
    bra.s 2f
1:  sub.w %d3, %d0
2:  move.w %d0, E_Y(%a3)
    cmpi.b #0xE0, E_Y(%a3)
    bcs.s 9f
    move.b E_Y(%a3), %d0
    andi.b #0xF0, %d0
    btst #7, E_FLAGS(%a3)
    bne.s 3f
    addi.b #0x10, %d0
3:  move.b %d0, E_Y(%a3)
    eori.b #0x80, E_FLAGS(%a3)
9:  rts

| Sprites_CalcYFromGravity: d0.w = a count, d1.w = its peak mask, d2.w = the bit that turns the wave: out d0.w = the count as a triangle wave.
en_wave:
    move.w %d0, -(%sp)
    and.w %d1, %d0
    and.w (%sp)+, %d2
    beq.s 1f
    sub.w %d0, %d1
    move.w %d1, %d0
1:  rts

| Giant Bees: phase 0 flies up four lines a frame to line 32; phase 1 dives at the hero (a pixel sideways a frame, the dive slowing by 4 a frame) until it is
| level with him; phase 2 hovers 128 frames on a wave of 16 ticks, drifting towards him, and starts again.
beh_bees:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  move.b E_PHASE(%a3), %d0
    beq.s 2f
    cmpi.b #1, %d0
    beq.s 4f
    bra.w 6f
2:  move.w #0x0400, %d3
    bsr.w en_edge_y
    cmpi.b #0x20, E_Y(%a3)
    bcc.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0xFF, E_D2(%a3)
    move.b #0xFF, E_D3(%a3)
    bsr.w ac_face_x
    bsr.w ac_face_y
    bra.w en_behaviour_end
3:  addq.b #1, E_PHASE(%a3)
    move.b #0x40, E_D2(%a3)
    clr.b E_D3(%a3)
    bra.w en_behaviour_end
4:  tst.b E_D3(%a3)
    beq.s 3b
    bsr.w en_distance_y
    cmpi.b #8, %d0
    bcs.s 3b
    move.w #0x0100, %d3
    bsr.w en_edge_x
    moveq #0, %d3
    move.b E_D3(%a3), %d3
    lsl.w #2, %d3
    bsr.w en_edge_y
    move.b E_D3(%a3), %d0
    subq.b #4, %d0
    bcc.s 5f
    moveq #0, %d0
5:  move.b %d0, E_D3(%a3)
    bra.w en_behaviour_end
6:  bsr.w ac_face_x
    move.w #0x00C0, %d3
    bsr.w en_edge_x
    moveq #0, %d0
    move.b E_D3(%a3), %d0
    moveq #0x0F, %d1
    moveq #0x10, %d2
    bsr.w en_wave
    lsl.w #4, %d0
    move.w %d0, %d3
    bsr.w en_edge_y
    addq.b #1, E_D3(%a3)
    move.b E_D3(%a3), %d0
    andi.b #0x0F, %d0
    bne.s 7f
    eori.b #0x80, E_FLAGS(%a3)
7:  move.b E_D3(%a3), %d0
    andi.b #0x7F, %d0
    bne.w en_behaviour_end
    clr.b E_PHASE(%a3)
    andi.b #0x7F, E_FLAGS(%a3)
    bra.w en_behaviour_end

| Necron Aides: it climbs a ladder, up and down in steps of a wave of 4 (turning where the ladder ends or at two moments), until it has hit the hero or been
| hit: then (phase bit 7) it falls if it must and walks a pixel a frame, turning round at three moments.
beh_necron:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D2(%a3)
    clr.b E_D3(%a3)
    bsr.w en_ready
1:  tst.b E_PHASE(%a3)
    bmi.w 6f
    moveq #0, %d0
    move.b E_Y(%a3), %d0
    btst #7, E_FLAGS(%a3)
    beq.s 2f
    addi.w #0x20, %d0
    bra.s 3f
2:  subq.w #1, %d0
3:  andi.w #0xF0, %d0                       | the block above its top or below its feet, at its x
    moveq #0, %d1
    move.b E_X(%a3), %d1
    lsr.w #4, %d1
    or.w %d1, %d0
    cmpi.w #208, %d0
    bge.s 4f
    movea.l en_ids(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    movea.l pkg_ptr+PKG_BLOCK_FLAGS(%pc), %a0
    btst #2, (%a0,%d1.w)                    | a ladder: go on
    bne.s 5f
4:  eori.b #0x80, E_FLAGS(%a3)
5:  move.w en_counter(%pc), %d0
    cmpi.b #0x17, %d0
    beq.s 7f
    cmpi.b #0x75, %d0
    bne.s 8f
7:  eori.b #0x80, E_FLAGS(%a3)
8:  lsr.w #2, %d0
    andi.w #3, %d0
    lea necron_steps(%pc), %a0
    moveq #0, %d3
    move.b (%a0,%d0.w), %d3
    cmpi.w #3, %d0
    bne.s 9f
    move.w #0x0100, %d3
9:  move.w E_Y(%a3), %d0
    btst #7, E_FLAGS(%a3)
    beq.s 10f
    add.w %d3, %d0
    bra.s 11f
10: sub.w %d3, %d0
11: move.w %d0, E_Y(%a3)
    bra.w en_behaviour_end
6:  bsr.w en_can_move
    tst.w %d0
    beq.s 12f
    bsr.w en_fall_step
    bra.w en_behaviour_end
12: move.w en_counter(%pc), %d0
    cmpi.b #0x26, %d0
    beq.s 13f
    cmpi.b #0x48, %d0
    beq.s 13f
    cmpi.b #0x93, %d0
    bne.s 14f
13: eori.b #1, E_FLAGS(%a3)
14: move.w #0x0100, %d3
    bsr.w en_step_x
    bra.w en_behaviour_end

| Sugata's flash (SpriteBehavior_FlashScreenHitPlayer): two frames after it starts he loses 10 power, whatever he wears, and is invincible for 60 frames.
beh_flash:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b #2, E_D2(%a3)
    bsr.w en_ready
1:  subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    moveq #4, %d0
    bsr.w sound_play_sfx
    lea hero_invinc(%pc), %a2
    move.w #0x3C, (%a2)
    move.w #1, hero_knock-hero_invinc(%a2)
    move.w #0x0A00, %d0
    bsr.w en_reduce_hp
    bsr.w en_finish
    bra.w en_behaviour_end

| Nash: phase 0 it is hidden for 120 frames; then it appears 32 pixels in front of or behind the hero (phase 1, 60 frames, facing him); phase 2 (60 frames) it
| casts magic at the 10th frame left, then it hides again.
beh_nash:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b #0x78, E_D2(%a3)
    bsr.w en_ready
1:  move.b E_PHASE(%a3), %d0
    beq.s 2f
    cmpi.b #1, %d0
    beq.s 5f
    subq.b #1, E_D2(%a3)
    beq.s 7f
    cmpi.b #0x0A, E_D2(%a3)
    bne.w en_behaviour_end
    moveq #E_MAGIC, %d0
    moveq #4, %d1
    moveq #0x0C, %d2
    bsr.w ac_cast_at
    bra.w en_behaviour_end
7:  clr.b E_PHASE(%a3)
    move.b #0x78, E_D2(%a3)
    bra.w en_behaviour_end
2:  bset #4, E_FLAGS(%a3)
    subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    bclr #4, E_FLAGS(%a3)
    addq.b #1, E_PHASE(%a3)
    move.b #0x3C, E_D2(%a3)
    move.w hero_x(%pc), %d1
    move.w %d1, %d0
    move.w hero_flip(%pc), %d2
    tst.w %d2
    bne.s 3f
    addi.w #0x20, %d0
    cmpi.w #0xF0, %d0
    bcs.s 4f
    move.w %d1, %d0
    subi.w #0x20, %d0
    bra.s 4f
3:  subi.w #0x20, %d0
    bpl.s 4f
    move.w %d1, %d0
    addi.w #0x20, %d0
4:  move.b %d0, E_X(%a3)
    bra.w en_behaviour_end
5:  bsr.w ac_face_x
    subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    move.b #0x3C, E_D2(%a3)
    addq.b #1, E_PHASE(%a3)
    bra.w en_behaviour_end

| Magman: out of sight (line 208, x 240) for 60 frames, then 48 pixels from the hero, level with him, facing him, for 120 frames.
beh_magman:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b #0x3C, E_D2(%a3)
    clr.b E_PHASE(%a3)
    move.b #0xD0, E_Y(%a3)
    move.b #0xF0, E_X(%a3)
    bsr.w en_ready
1:  btst #0, E_PHASE(%a3)
    bne.s 3f
    subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x78, E_D2(%a3)
    move.w hero_x(%pc), %d0
    move.w hero_flip(%pc), %d2
    tst.w %d2
    beq.s 2f
    addi.b #0x30, %d0
    bra.s 4f
2:  addi.b #0xD0, %d0
4:  move.b %d0, E_X(%a3)
    move.w hero_y(%pc), %d0
    move.b %d0, E_Y(%a3)
    bra.w en_behaviour_end
3:  bsr.w ac_face_x
    subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x3C, E_D2(%a3)
    move.b #0xD0, E_Y(%a3)
    move.b #0xF0, E_X(%a3)
    bra.w en_behaviour_end

| Tamazutsu: it faces the hero; hidden for 60 frames, hidden 11, in sight for 60, hidden 11, and again (its phase is kept to 0 to 3).
beh_tamazutsu:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b #0x3C, E_D2(%a3)
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  bsr.w ac_face_x
    moveq #0x3C, %d2
    move.b E_PHASE(%a3), %d0
    cmpi.b #2, %d0
    bne.s 2f
    bclr #4, E_FLAGS(%a3)
    moveq #0x0B, %d2
    bra.s 4f
2:  bset #4, E_FLAGS(%a3)
    tst.b %d0
    bne.s 4f
    moveq #0x0B, %d2
4:  subq.b #1, E_D2(%a3)
    bne.s 5f
    addq.b #1, E_PHASE(%a3)
    move.b %d2, E_D2(%a3)
5:  andi.b #3, E_PHASE(%a3)
    bra.w en_behaviour_end

| Execution Hood: half a pixel sideways a frame, bobbing on a wave of 16 ticks (turning up or down every 8); after 16 ticks it goes on to the next step, and
| in the fourth it stands facing him for 15 frames and casts magic.
beh_hood:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D3(%a3)
    clr.b E_PHASE(%a3)
    bsr.w en_ready
1:  move.b E_PHASE(%a3), %d0
    andi.b #3, %d0
    cmpi.b #3, %d0
    bne.s 2f
    bsr.w ac_face_x
    subq.b #1, E_D2(%a3)
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    clr.b E_D3(%a3)
    moveq #E_MAGIC, %d0
    moveq #4, %d1
    moveq #0, %d2
    bsr.w ac_cast_at
    bra.w en_behaviour_end
2:  move.w #0x0080, %d3
    bsr.w en_step_x
    tst.w %d0
    beq.s 3f
    eori.b #1, E_FLAGS(%a3)
3:  moveq #0, %d0
    move.b E_D3(%a3), %d0
    moveq #7, %d1
    moveq #8, %d2
    bsr.w en_wave
    lsl.w #5, %d0
    move.w %d0, %d3
    bsr.w en_edge_y
    addq.b #1, E_D3(%a3)
    move.b E_D3(%a3), %d0
    andi.b #7, %d0
    bne.s 4f
    eori.b #0x80, E_FLAGS(%a3)
4:  move.b E_D3(%a3), %d0
    andi.b #0x0F, %d0
    bne.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x0F, E_D2(%a3)
    bra.w en_behaviour_end

beh_fall:
    bsr.w en_ready
    bsr.w en_can_move
    tst.w %d0
    beq.s 1f
    bsr.w en_fall_step
1:  bsr.w en_countdown
    bra.w en_behaviour_end

| Hop: sideways at a steady speed, up and down along a curve whose shape the hop kind (the script's third byte) gives.
beh_hop:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    move.b (%a5,%d6.w), E_BXF(%a3)
    move.b 1(%a5,%d6.w), E_BXFULL(%a3)
    move.b 2(%a5,%d6.w), E_INT(%a3)
    addq.w #3, %d6
    clr.b E_ARG1(%a3)
    bsr.w en_ready
    bclr #7, E_FLAGS(%a3)
    moveq #0, %d0
    move.b E_INT(%a3), %d0
    lea hop_start(%pc), %a0
    move.b (%a0,%d0.w), E_D3(%a3)
1:  move.w E_BXFULL(%a3), %d3
    bsr.w en_step_x
    bsr.w hop_masks                         | d1 = the gravity, d2 = its mask of ticks
    moveq #0, %d4
    move.b E_D3(%a3), %d4
    move.w %d4, %d5
    and.w %d2, %d5                          | d5 = tick & mask
    lea hop_maybe(%pc), %a0
    move.b (%a0,%d1.w), %d0
    and.b %d4, %d0
    beq.s 2f
    sub.w %d5, %d2
    move.w %d2, %d5                         | mask - (tick & mask) in the second half of the curve
2:  moveq #0, %d0
    move.b E_INT(%a3), %d0
    lea hop_strength(%pc), %a0
    moveq #0, %d3
    move.b (%a0,%d0.w), %d3
    lsl.w %d3, %d5                          | the step: that shifted left strength times, the whole pixels in the high byte
    move.w %d5, %d3
    bsr.w en_step_y
    tst.w %d0
    beq.s 3f
    btst #7, E_FLAGS(%a3)
    beq.s 3f
    bsr.w en_finish                         | down on the ground: done
    bra.w en_behaviour_end
3:  addq.b #1, E_D3(%a3)
    bsr.w hop_masks
    moveq #0, %d4
    move.b E_D3(%a3), %d4
    and.w %d2, %d4
    bne.w en_behaviour_end                  | (only at a multiple of the mask + 1 ticks does the curve turn)
    btst #7, E_FLAGS(%a3)
    bne.s 4f
    eori.b #0x80, E_FLAGS(%a3)              | the top: now down
    bra.w en_behaviour_end
4:  moveq #0, %d0
    move.b E_INT(%a3), %d0
    lea hop_ground(%pc), %a0
    move.b E_D3(%a3), %d4
    cmp.b (%a0,%d0.w), %d4
    bcs.w en_behaviour_end
    subq.b #1, E_D3(%a3)
    bra.w en_behaviour_end

hop_masks:                                  | out d1 = SPRITE_BEHAVIOR_HOP_GRAVITY[hop kind], d2 = SPRITE_BEHAVIOR_HOP_PEAK_TICKS[d1]
    moveq #0, %d0
    move.b E_INT(%a3), %d0
    lea hop_gravity(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    lea hop_peak(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d1.w), %d2
    rts

| ---------------------------------------------------------------------------------------------------------------------- moving and the blocks
| d5.w = a block position (row * 16 + column): d0.w = 1 when it is one the enemy cannot walk through (Z set: free). Clobbers a0.
en_cell:
    moveq #0, %d0
    cmpi.w #208, %d5
    bge.s 1f
    movea.l en_blocks(%pc), %a0
    move.b (%a0,%d5.w), %d0
1:  tst.w %d0
    rts

| CurrentSprite_CanMoveInDirection: d3.w = 0 left, 1 right, 2 up, 3 down. Out: d0.w = 1 when a block he cannot pass is in the way
| (Z set: free). Clobbers d1-d2, d4-d5, a0.
en_blocked:
    moveq #0, %d4
    move.b E_HBOX(%a3), %d4
    moveq #0, %d1
    move.b E_X(%a3), %d1
    moveq #0, %d2
    move.b E_Y(%a3), %d2
    cmpi.w #2, %d3
    bge.s 5f
    tst.w %d3                               | sideways: the column at the sprite's x (right: at its right edge), from its y down
    bne.s 1f
    cmpi.w #0xF1, %d1
    bcc.w eb_yes
    bra.s 2f
1:  lea hbox_width(%pc), %a0
    moveq #0, %d0
    move.b (%a0,%d4.w), %d0
    add.w %d0, %d1
    cmpi.w #0xFF, %d1
    bhi.w eb_yes
2:  move.w %d2, %d5
    andi.w #0xF0, %d5
    lsr.w #4, %d1
    or.w %d1, %d5
    bsr.s en_cell
    bne.w eb_yes
    lea hbox_height(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
3:  subi.w #0x10, %d1
    bmi.s 4f
    addi.w #0x10, %d5
    andi.w #0xFF, %d5
    bsr.s en_cell
    bne.s eb_yes
    bra.s 3b
4:  move.b E_Y(%a3), %d0
    andi.b #0x0F, %d0
    beq.s eb_no
    addi.w #0x10, %d5
    andi.w #0xFF, %d5
    bra.w en_cell
5:  cmpi.w #3, %d3                          | up or down: the row at the sprite's top (down: under its feet), from its x across
    bne.s 6f
    lea hbox_height(%pc), %a0
    moveq #0, %d0
    move.b (%a0,%d4.w), %d0
    add.w %d0, %d2
    andi.w #0xFF, %d2
6:  cmpi.w #0xF0, %d2
    bcc.s eb_yes
    move.w %d1, %d5
    lsr.w #4, %d5
    andi.w #0xF0, %d2
    or.w %d2, %d5
    bsr.w en_cell
    bne.s eb_yes
    lea hbox_width(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
7:  subi.w #0x10, %d1
    bmi.s 8f
    addq.w #1, %d5
    andi.w #0xFF, %d5
    bsr.w en_cell
    bne.s eb_yes
    bra.s 7b
8:  move.b E_X(%a3), %d0
    andi.b #0x0F, %d0
    beq.s eb_no
    addq.w #1, %d5
    andi.w #0xFF, %d5
    bra.w en_cell
eb_yes:
    moveq #1, %d0
    rts
eb_no:
    moveq #0, %d0
    rts

| Sprite_MoveForwardX and MoveSpriteHorizIfPossible: d3.w = the step (whole pixels in the high byte). Out: d0.w = 1 when a wall stopped it
| (the sprite is put against it). Clobbers d1-d5, a0.
en_step_x:
    move.w E_X(%a3), %d0
    btst #0, E_FLAGS(%a3)
    beq.s 1f
    add.w %d3, %d0
    bra.s 2f
1:  sub.w %d3, %d0
2:  move.w %d0, E_X(%a3)
    moveq #0, %d3
    move.b E_FLAGS(%a3), %d3
    andi.w #1, %d3
    bsr.w en_blocked
    tst.w %d0
    beq.s 9f
    move.b E_X(%a3), %d0
    andi.b #0xF0, %d0
    btst #0, E_FLAGS(%a3)
    bne.s 3f
    addi.b #0x10, %d0
3:  move.b %d0, E_X(%a3)
    moveq #1, %d0
9:  rts

| Sprite_MoveVertical: the same up or down by the falling flag. Out: d0.w = 1 when it hit something (put against it).
en_step_y:
    move.w E_Y(%a3), %d0
    btst #7, E_FLAGS(%a3)
    beq.s 1f
    add.w %d3, %d0
    bra.s 2f
1:  sub.w %d3, %d0
2:  move.w %d0, E_Y(%a3)
    moveq #2, %d3
    btst #7, E_FLAGS(%a3)
    beq.s 3f
    moveq #3, %d3
3:  bsr.w en_blocked
    tst.w %d0
    beq.s 9f
    move.b E_Y(%a3), %d0
    andi.b #0xF0, %d0
    btst #7, E_FLAGS(%a3)
    bne.s 4f
    addi.b #0x10, %d0
4:  move.b %d0, E_Y(%a3)
    moveq #1, %d0
9:  rts

| Sprites_SetCurrentSpriteCanMove: d0.w = 1 when nothing solid is under the sprite (and it does not fly): it is in the air and must fall.
| (Sprites_CanMoveDownByHitbox: the block under its lower corner on the side it faces; a ladder is as good as a floor.)
en_can_move:
    btst #1, E_FLAGS(%a3)
    bne.s 2f
    moveq #0, %d4
    move.b E_HBOX(%a3), %d4
    lea hbox_height(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d4.w), %d2
    moveq #0, %d0
    move.b E_Y(%a3), %d0
    add.w %d0, %d2
    addq.w #1, %d2
    andi.w #0xFF, %d2
    moveq #0, %d1
    move.b E_X(%a3), %d1
    btst #0, E_FLAGS(%a3)
    beq.s 1f
    addi.w #15, %d1
    andi.w #0xFF, %d1
1:  lsr.w #4, %d1
    andi.w #0xF0, %d2
    or.w %d2, %d1
    cmpi.w #208, %d1
    bge.s 3f
    movea.l en_ids(%pc), %a0
    moveq #0, %d0
    move.b (%a0,%d1.w), %d0
    movea.l pkg_ptr+PKG_BLOCK_FLAGS(%pc), %a0
    move.b (%a0,%d0.w), %d0
    andi.b #5, %d0                          | impassable, or a ladder of the kind that counts
    bne.s 2f
3:  bset #2, E_FLAGS(%a3)
    moveq #1, %d0
    rts
2:  bclr #2, E_FLAGS(%a3)
    moveq #0, %d0
    rts

| CurrentSprite_HandleFall: 8 lines down; off the bottom: gone; on something: onto the row.
en_fall_step:
    btst #2, E_FLAGS(%a3)
    beq.s 9f
    move.b E_Y(%a3), %d0
    addq.b #8, %d0
    move.b %d0, E_Y(%a3)
    cmpi.b #0xC0, %d0
    bcs.s 1f
    move.b #0xFF, E_ENT(%a3)
    rts
1:  moveq #3, %d3
    bsr.w en_blocked
    tst.w %d0
    beq.s 9f
    andi.b #0xF0, E_Y(%a3)
9:  rts

| ---------------------------------------------------------------------------------------------------------------------- combat
| Player_HitSpriteWithWeapon for the slot a3: the sword is out (attack phase 1 or 2), the enemy is inside its reach (Sprites_IsSpriteOutOfWeaponRange: the
| weapon's place plus its reach, minus the enemy's place, below the enemy's extent plus the reach, in x and in y, as bytes), and it is not the drop or the
| death effect. It loses the weapon's strength plus a quarter (no pendant, the pendant bug), turns the way the hero faces, stands still for 8 frames; at
| none left it dies: its experience, and the death effect takes its place.
en_weapon:
    movem.l %d0-%d5/%a0-%a2, -(%sp)
    move.b E_ENT(%a3), %d0
    cmpi.b #E_BREAD, %d0
    beq.w 9f
    cmpi.b #E_COIN, %d0
    beq.w 9f
    cmpi.b #E_DEATH, %d0
    beq.w 9f
    btst #4, E_FLAGS(%a3)                   | hidden (Tamazutsu, Nash): it cannot be hit
    bne.w 9f
    btst #7, hero_air+1(%pc)                | Player_Flags bit 7: attacking
    beq.w 9f
    move.w hero_atk_phase(%pc), %d0
    subq.w #1, %d0
    cmpi.w #2, %d0
    bcc.w 9f
    move.w hero_weapon(%pc), %d1            | Player_CurWeapon, 255: none
    cmpi.w #4, %d1
    bcc.w 9f
    movea.l E_KIND(%a3), %a0
    lea weapon_x(%pc), %a1
    move.w 4(%a1), %d2                      | the reach in x
    move.w (%a1), %d0
    add.w %d2, %d0
    moveq #0, %d4
    move.b E_X(%a3), %d4
    sub.w %d4, %d0
    andi.w #0xFF, %d0
    add.w K_EXTX(%a0), %d2
    andi.w #0xFF, %d2
    cmp.w %d2, %d0
    bcc.w 9f                                | out of reach
    move.w 6(%a1), %d3                      | the reach in y
    move.w 2(%a1), %d0
    add.w %d3, %d0
    moveq #0, %d4
    move.b E_Y(%a3), %d4
    sub.w %d4, %d0
    andi.w #0xFF, %d0
    add.w K_EXTY(%a0), %d3
    andi.w #0xFF, %d3
    cmp.w %d3, %d0
    bcc.w 9f
    cmpi.b #5, E_ENT(%a3)                   | Necron Aides, hit: it comes off the ladder (phase bit 7)
    bne.s 1f
    ori.b #0x80, E_PHASE(%a3)
1:  moveq #2, %d0                           | a hit
    bsr.w sound_play_sfx
    move.w hero_flip(%pc), %d0              | it faces the way he does
    andi.b #1, %d0
    andi.b #0xFE, E_FLAGS(%a3)
    or.b %d0, E_FLAGS(%a3)
    move.b #8, E_HIT(%a3)
    lea weapon_damage(%pc), %a1
    move.b (%a1,%d1.w), %d0
    move.b E_HP(%a3), %d2
    move.b %d2, %d4
    sub.b %d0, %d4
    move.b %d4, E_HP(%a3)
    cmp.b %d0, %d2                          | it had less than the blow: dead
    bcc.w 9f
    moveq #3, %d0
    bsr.w sound_play_sfx
    clr.b E_HIT(%a3)
    move.w K_EXP(%a0), %d0                  | Player_AddExperienceFromSprite (the rank does not rise yet)
    lea hud_state(%pc), %a1
    add.w %d0, 2(%a1)
    bcc.s 1f
    move.w #0xFFFF, 2(%a1)
1:  lea hud_dirty(%pc), %a1
    st (%a1)
    move.l %a0, E_PREV(%a3)                 | Sprite_SetDeathEntity: what it was, the death effect's script
    moveq #E_DEATH, %d0
    bsr.w en_find_kind
    move.l %a0, E_KIND(%a3)
    move.w K_SCRIPT(%a0), E_SCRIPT(%a3)
    move.b #E_DEATH, E_ENT(%a3)
    move.b #0xFF, E_BEH(%a3)
    clr.b E_D2(%a3)
    bclr #6, E_FLAGS(%a3)
9:  movem.l (%sp)+, %d0-%d5/%a0-%a2
    rts

| The kind record of the entity d0.w in the package: a0 (0 if there is none). Clobbers d1.
en_find_kind:
    movea.l pkg_ptr+PKG_ENEMY_KINDS(%pc), %a0
1:  move.w (%a0), %d1
    bmi.s 2f
    cmp.w %d1, %d0
    beq.s 3f
    lea KIND_BYTES(%a0), %a0
    bra.s 1b
2:  suba.l %a0, %a0
3:  rts

| CurrentSprite_CheckHitPlayer for the slot a3: the touch box (the sprite's place plus the kind's left and top, its width and height) against the hero's
| (Player_PosX_Block + 11 and Player_PosY + 27, as bytes). An enemy hurts him (Player_HandleTouchEnemy: nothing in the 60 frames of invincibility; he turns to
| the enemy and is knocked back; Player_ApplyDamage: its damage less an eighth for each step of the armour's multiplier), bread heals him and a coin is gold.
en_touch:
    movem.l %d0-%d5/%a0-%a2, -(%sp)
    move.b E_ENT(%a3), %d5
    cmpi.b #E_DEATH, %d5
    beq.w 9f
    btst #4, E_FLAGS(%a3)                   | hidden: it cannot touch him
    bne.w 9f
    movea.l E_KIND(%a3), %a0
    lea touch_box(%pc), %a1                 | the box (left, top, width, height): the kind's, but Sprite_GetBounds gives these a wide one in some steps
    move.l K_BL(%a0), (%a1)
    move.l K_BW(%a0), 4(%a1)
    cmpi.b #0x20, %d5
    beq.s 11f
    cmpi.b #0x1F, %d5
    beq.s 10f
    cmpi.b #0x21, %d5
    bne.s 12f
10: cmpi.b #2, E_PHASE(%a3)                 | Sir Gawaine and the Wolfman in step 2
    bne.s 12f
    move.l #0x00300008, (%a1)
    move.l #0x00F00000, 4(%a1)
    bra.s 12f
11: move.b E_PHASE(%a3), %d0                | the Maskman in steps 0 and 4
    beq.s 13f
    cmpi.b #4, %d0
    bne.s 12f
13: move.l #0x00200010, (%a1)
    move.l #0x00F80000, 4(%a1)
12: moveq #0, %d0
    move.b E_X(%a3), %d0
    add.w (%a1), %d0                    | the box's left
    move.w hero_x(%pc), %d1
    addi.w #0x0B, %d1
    sub.w %d0, %d1
    andi.w #0xFF, %d1
    move.w 4(%a1), %d2
    addi.w #0x0B, %d2
    andi.w #0xFF, %d2
    cmp.w %d2, %d1
    bcc.w 9f
    moveq #0, %d0
    move.b E_Y(%a3), %d0
    add.w 2(%a1), %d0                    | its top
    move.w hero_y(%pc), %d1
    addi.w #0x1B, %d1
    sub.w %d0, %d1
    andi.w #0xFF, %d1
    move.w 6(%a1), %d2
    addi.w #0x1B, %d2
    andi.w #0xFF, %d2
    cmp.w %d2, %d1
    bcc.w 9f
    lea hud_state(%pc), %a1
    cmpi.b #E_BREAD, %d5
    beq.s 5f
    cmpi.b #E_COIN, %d5
    beq.w 6f
    move.w hero_invinc(%pc), %d0            | an enemy: nothing happens while he is invincible
    bne.w 9f
    cmpi.b #5, %d5                          | Necron Aides, touching him: it comes off the ladder
    bne.s 14f
    ori.b #0x80, E_PHASE(%a3)
14:
    moveq #4, %d0
    bsr.w sound_play_sfx
    lea hero_invinc(%pc), %a2
    move.w #0x3C, (%a2)
    moveq #1, %d0                           | he faces it (it faces left: he faces right) and is knocked back
    btst #0, E_FLAGS(%a3)
    beq.s 1f
    moveq #0, %d0
1:  move.w %d0, hero_flip-hero_invinc(%a2)
    move.w #1, hero_knock-hero_invinc(%a2)
    move.w K_DMG(%a0), %d1
    move.w %d1, %d0
    lsl.w #8, %d0                           | the damage, 8.8
    lsl.w #5, %d1                           | an eighth of it
    moveq #HERO_ARMOUR, %d2                 | Player_ApplyDamage: the armour's multiplier takes that many eighths off (Leather and the Battle Suit's slot none)
    beq.s 2f
    cmpi.w #4, %d2
    bcc.s 2f
    lea armour_multiplier(%pc), %a2
    moveq #0, %d3
    move.b (%a2,%d2.w), %d3
    bra.s 4f
3:  sub.w %d1, %d0
4:  dbra %d3, 3b
2:  bsr.w en_reduce_hp
    cmpi.b #E_FIREBALL, E_ENT(%a3)          | (magic is gone when it has hurt him)
    beq.s 15f
    cmpi.b #E_MAGIC, E_ENT(%a3)
    bne.s 9f
15: move.b #0xFF, E_ENT(%a3)
    bra.s 9f
5:  move.b #0xFF, E_ENT(%a3)                | bread: Player_AddHP, at most 80
    moveq #0x1B, %d0
    bsr.w sound_play_sfx
    move.b (%a1), %d0
    add.b E_VAL(%a3), %d0
    cmpi.b #80, %d0
    bcs.s 7f
    moveq #80, %d0
7:  move.b %d0, (%a1)
    lea hud_dirty(%pc), %a1
    st (%a1)
    bra.s 9f
6:  move.b #0xFF, E_ENT(%a3)                | a coin
    moveq #9, %d0
    bsr.w sound_play_sfx
    moveq #0, %d0
    move.b E_VAL(%a3), %d0
    add.l 4(%a1), %d0
    andi.l #0xFFFFFF, %d0
    move.l %d0, 4(%a1)
    lea hud_dirty(%pc), %a1
    st (%a1)
9:  movem.l (%sp)+, %d0-%d5/%a0-%a2
    rts

| Player_ReduceHP: d0.w = the damage, 8.8. The power is the HUD's byte and a fraction (hero_hpl); below nothing he is dead (no Elixir yet).
en_reduce_hp:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    lea hud_state(%pc), %a0
    lea hero_hpl(%pc), %a1
    moveq #0, %d1
    move.b (%a0), %d1
    lsl.w #8, %d1
    move.b (%a1), %d1
    sub.w %d0, %d1
    bcs.s 1f
    move.b %d1, (%a1)
    lsr.w #8, %d1
    move.b %d1, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    bra.s 9f
1:  move.b %d1, (%a1)
    clr.b (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    lea hero_x(%pc), %a1
    bsr.w death_start
9:  movem.l (%sp)+, %d0-%d1/%a0-%a1
    rts

| SpriteBehavior_EnemyDeath: 8 frames of the effect, then it is gone and leaves its drop (Sprite_HandleDeathDropIfPossible) in the highest free slot.
beh_death:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_D2(%a3)
    bsr.w en_ready
1:  addq.b #1, E_D2(%a3)
    cmpi.b #8, E_D2(%a3)
    bcs.w en_behaviour_end
    bsr.s en_drop
    move.b #0xFF, E_ENT(%a3)
    bra.w en_behaviour_end

| Sprite_RunDeathDropHandler: the enemy a3 was had a drop (its kind's K_DROP: bread or a coin and the value).
en_drop:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    lea enemies+7*E_BYTES(%pc), %a2
    moveq #7, %d2
1:  cmpi.b #0xFF, E_ENT(%a2)
    beq.s 2f
    lea -E_BYTES(%a2), %a2
    dbra %d2, 1b
    bra.s 9f                                | no room
2:  movea.l E_PREV(%a3), %a0
    move.w K_DROP(%a0), %d0
    beq.s 9f
    move.b %d0, E_VAL(%a2)
    move.b E_X(%a3), E_X(%a2)
    move.b E_Y(%a3), E_Y(%a2)
    clr.b E_HIT(%a2)
    lsr.w #8, %d0                           | 1 bread, 2 a coin
    move.b %d0, E_ENT(%a2)
    cmpi.b #E_COIN, %d0
    bne.s 3f
    moveq #0x10, %d0
    bsr.w sound_play_sfx
    moveq #E_COIN, %d0
3:  bsr.w en_find_kind
    move.l %a0, E_KIND(%a2)
    move.w K_SCRIPT(%a0), E_SCRIPT(%a2)
    move.b #0xFF, E_BEH(%a2)
    bclr #6, E_FLAGS(%a2)
    moveq #E_COIN, %d0                      | both have the coin's hit box type
    bsr.w en_find_kind
    move.b K_HBOX+1(%a0), E_HBOX(%a2)
9:  movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| SpriteBehavior_BounceAndExpire (the dropped coin): falls 4 pixels a frame until it lands, then bounces on a curve (a rise and a fall of 32 ticks each,
| Sprites_CalcYFromGravity with 3 and Sprites_CalcVerticalSpriteMovement with 4); after 256 frames it is gone.
beh_bounce:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    clr.b E_PHASE(%a3)
    clr.b E_INT(%a3)
    move.b #0xC0, E_FLAGS(%a3)              | falling, ready
1:  addq.b #1, E_INT(%a3)
    bne.s 2f
    move.b #0xFF, E_ENT(%a3)
    bra.w en_behaviour_end
2:  tst.b E_PHASE(%a3)
    bne.s 3f
    move.w #0x0400, %d3
    bsr.w en_step_y
    tst.w %d0
    beq.w en_behaviour_end
    addq.b #1, E_PHASE(%a3)
    move.b #0x20, E_D3(%a3)
    bclr #7, E_FLAGS(%a3)
    bra.w en_behaviour_end
3:  moveq #0, %d4
    move.b E_D3(%a3), %d4
    move.w %d4, %d5
    andi.w #0x1F, %d5
    btst #5, %d4
    beq.s 4f
    moveq #0x1F, %d0
    sub.w %d5, %d0
    move.w %d0, %d5
4:  lsl.w #4, %d5
    move.w %d5, %d3
    bsr.w en_step_y
    addq.b #1, E_D3(%a3)
    move.b E_D3(%a3), %d0
    andi.b #0x1F, %d0
    bne.w en_behaviour_end
    eori.b #0x80, E_FLAGS(%a3)
    bra.w en_behaviour_end

| ---------------------------------------------------------------------------------------------------------------------- the pictures
| The enemies' pictures drawn into screen a4, their boxes noted for erasing. The pose: the kind's first, then 2 a frame (the kind's rule picks the
| frame: 0 two by the counter, 1 by the script's step, 5 the Snowman's) and 1 more when it faces right (mirrored).
draw_enemies:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    lea enemies(%pc), %a3
    movea.l pkg_ptr+PKG_ENEMY_IMAGES(%pc), %a6
    moveq #0, %d7
1:  cmpi.b #0xFF, E_ENT(%a3)
    beq.w 8f
    move.b E_HIT(%a3), %d0
    andi.b #2, %d0
    bne.w 8f                                | hit: it blinks (CurrentSprite_UpdateState draws when the counter's bit 1 is clear)
    movea.l E_KIND(%a3), %a0
    move.w K_POSE(%a0), %d6
    move.w K_RULE(%a0), %d0
    beq.w 2f
    cmpi.w #1, %d0
    beq.w 3f
    cmpi.w #5, %d0
    beq.w 9f
    cmpi.w #6, %d0
    beq.w 11f
    cmpi.w #7, %d0
    beq.w 12f
    cmpi.w #8, %d0
    beq.w 13f
    cmpi.w #9, %d0
    beq.w 16f
    cmpi.w #10, %d0
    beq.w 17f
    cmpi.w #11, %d0
    beq.w 18f
    cmpi.w #12, %d0
    beq.w 19f
    cmpi.w #13, %d0
    beq.w 21f
    cmpi.w #14, %d0
    beq.w 23f
    cmpi.w #15, %d0
    beq.w 20f
    cmpi.w #16, %d0
    beq.w 24f
    cmpi.w #17, %d0
    beq.w 25f
    cmpi.w #18, %d0
    beq.w 26f
    cmpi.w #19, %d0
    beq.w 27f
    cmpi.w #20, %d0
    beq.w 28f
    cmpi.w #21, %d0
    beq.w 29f
    cmpi.w #22, %d0
    beq.w 30f
    cmpi.w #23, %d0
    beq.w 31f
    cmpi.w #24, %d0
    beq.w 32f
    cmpi.w #25, %d0
    beq.w 33f
    cmpi.w #26, %d0
    beq.w 34f
    cmpi.w #27, %d0
    beq.w 35f
    cmpi.w #28, %d0
    beq.w 36f
    moveq #0, %d1
    cmpi.w #2, %d0
    bne.s 5f
    move.w en_counter(%pc), %d0             | the death effect: its frame is the behaviour's count; drawn on every other update
    btst #0, %d0
    bne.w 8f
    move.b E_D2(%a3), %d1
    bra.w 6f
5:  cmpi.w #4, %d0
    bne.w 6f
    btst #3, E_INT(%a3)                     | a coin: the second picture while bit 3 of its count is set
    beq.w 6f
    moveq #1, %d1
6:  add.w %d1, %d6                          | (these have one picture, whichever way they face)
    bra.w 4f
2:  move.w en_counter(%pc), %d0             | rule 0: two pictures by the counter
    lsr.w #4, %d0
    andi.w #1, %d0
    bra.w 7f
9:  moveq #0, %d0                           | rule 5, the Snowman: picture 0 while its step is 0, then by the counter (half as fast in step 1)
    moveq #0, %d2
    move.b E_PHASE(%a3), %d2
    beq.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    subq.b #1, %d2
    bne.s 10f
    lsr.w #1, %d0
10: andi.w #1, %d0
    bra.w 7f
11: moveq #0, %d0                           | rule 6, the Zombie: picture 0 while the step before is odd, else by the counter (0, 1, 2, 1)
    moveq #0, %d2
    move.b E_PHASE(%a3), %d2
    subq.b #1, %d2
    btst #0, %d2
    bne.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #3, %d0
    lea zombie_frames(%pc), %a1
    move.b (%a1,%d0.w), %d0
    bra.w 7f
12: moveq #0, %d2                           | rule 7, Ikeda: picture 2 while the step before is odd, else a change every 4 updates
    move.b E_PHASE(%a3), %d2
    subq.b #1, %d2
    moveq #2, %d0
    btst #0, %d2
    bne.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.w 7f
13: moveq #0, %d0                           | rule 8, the Myconid: moves in steps 1, 3 (a change every 16 updates) and 5 (every 8)
    moveq #0, %d2
    move.b E_PHASE(%a3), %d2
    moveq #4, %d1
    cmpi.b #5, %d2
    bne.s 14f
    moveq #3, %d1
    bra.s 15f
14: cmpi.b #1, %d2
    beq.s 15f
    cmpi.b #3, %d2
    bne.w 7f
15: move.w en_counter(%pc), %d0
    lsr.w %d1, %d0
    andi.w #1, %d0
    bra.w 7f
20: move.w en_counter(%pc), %d0              | rule 15, the Lamprey: eight pictures of 8 updates, some mirrored whichever way it faces
    lsr.w #3, %d0
    andi.w #7, %d0
    lea lamprey_poses(%pc), %a1
    moveq #0, %d1
    move.b (%a1,%d0.w), %d1                 | 2 * picture + mirrored
    move.b E_FLAGS(%a3), %d0
    eor.b %d1, %d0
    andi.w #1, %d0
    andi.w #2, %d1
    add.w %d1, %d6
    add.w %d0, %d6
    bra.w 4f
21: moveq #0, %d2                           | rule 13, Raiden: step 2: pictures 2 and 3 (every 8 updates), else 0 and 1 (every 4)
    move.b E_PHASE(%a3), %d2
    cmpi.b #2, %d2
    bne.s 22f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #1, %d0
    ori.w #2, %d0
    bra.w 7f
22: move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.w 7f
23: moveq #0, %d2                           | rule 14, Grimlock: picture 3 in steps 9 and 11, 0 below 8, else 0, 1, 2, 1
    move.b E_PHASE(%a3), %d2
    moveq #3, %d0
    cmpi.b #9, %d2
    beq.w 7f
    cmpi.b #11, %d2
    beq.w 7f
    moveq #0, %d0
    cmpi.b #8, %d2
    bcs.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #3, %d0
    lea zombie_frames(%pc), %a1
    move.b (%a1,%d0.w), %d0
    bra.w 7f
24: moveq #2, %d0                           | rule 16, Giant Strider: picture 2 in step 2, else a change every 4 updates
    cmpi.b #2, E_PHASE(%a3)
    beq.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.w 7f
25: moveq #4, %d0                           | rule 17, Maskman: picture 4 in the even steps, else a change every 8 updates
    btst #0, E_PHASE(%a3)
    beq.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #1, %d0
    bra.w 7f
26: moveq #2, %d0                           | rule 18, Geributa: picture 2 in step 0, else a change every 4 updates
    tst.b E_PHASE(%a3)
    beq.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.w 7f
27: moveq #0, %d0                           | rule 19, Bihoruda: picture 0 while its sideways count (modulo 128) is 48 to 95, else 1
    move.b E_D2(%a3), %d1
    andi.b #0x7F, %d1
    subi.b #0x30, %d1
    cmpi.b #0x30, %d1
    bcs.w 7f
    moveq #1, %d0
    bra.w 7f
28: moveq #0, %d0                           | rule 20, Sir Gawaine and the Wolfman: the step is the picture
    move.b E_PHASE(%a3), %d0
    bra.w 7f
29: move.w en_counter(%pc), %d0              | rule 21, Naga and Yareeka: a change every 8 updates
    lsr.w #3, %d0
    andi.w #1, %d0
    bra.w 7f
30: move.w en_counter(%pc), %d0              | rule 22, Necron Aides: a change every 8 updates, every 4 once it has hit or been hit
    lsr.w #2, %d0
    tst.b E_PHASE(%a3)
    bmi.s 40f
    lsr.w #1, %d0
40: andi.w #1, %d0
    bra.w 7f
31: moveq #2, %d0                           | rule 23, Fire Giant: picture 2, in step 2 a change every 4 updates
    cmpi.b #2, E_PHASE(%a3)
    bne.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.w 7f
32: moveq #0, %d2                           | rule 24, Tamazutsu: by its step (E_PHASE and 3) and its count
    move.b E_PHASE(%a3), %d2
    andi.w #3, %d2
    moveq #0, %d1
    move.b E_D2(%a3), %d1
    moveq #0, %d0
    tst.w %d2
    bne.s 41f
    cmpi.b #0x1E, %d1                       | step 0: not drawn until the count is below 30, then picture 0 or 1
    bcc.w 8f
    btst #3, %d1
    beq.w 7f
    moveq #1, %d0
    bra.w 7f
41: cmpi.w #2, %d2
    bne.s 42f
    moveq #5, %d0                           | step 2 (the one in sight): picture 5 or 6
    btst #3, %d1
    beq.w 7f
    moveq #6, %d0
    bra.w 7f
42: lsr.w #2, %d1                           | steps 1 and 3: the count in fours picks 4, 3, 2 or 2, 3, 4
    lea tamazutsu_frames(%pc), %a1
    cmpi.w #1, %d2
    beq.s 43f
    addq.w #3, %d1
43: move.b (%a1,%d1.w), %d0
    bra.w 7f
33: moveq #0, %d0                           | rule 25, Nash: not drawn in step 0 (nor in step 1 for 4 updates of 8), picture 0 in step 1, then 0, 1, 2 by the count
    tst.b E_PHASE(%a3)
    beq.w 8f
    cmpi.b #1, E_PHASE(%a3)
    bne.s 44f
    btst #2, en_counter+1(%pc)
    bne.w 8f
44: cmpi.b #2, E_PHASE(%a3)
    bne.w 7f
    moveq #0, %d1
    move.b E_D2(%a3), %d1
    subi.b #0x0A, %d1
    cmpi.b #0x28, %d1
    bcc.w 7f
    moveq #1, %d0
    cmpi.b #0x14, %d1
    bcc.w 7f
    moveq #2, %d0
    bra.w 7f
34: moveq #0, %d0                           | rule 26, Execution Hood: picture 1 in the fourth step, every other 4 updates
    moveq #0, %d1
    move.b E_PHASE(%a3), %d1
    andi.b #3, %d1
    cmpi.b #3, %d1
    bne.w 7f
    move.w en_counter(%pc), %d1
    btst #2, %d1
    beq.w 7f
    moveq #1, %d0
    bra.w 7f
35: moveq #0, %d0                           | rule 27, Magman: a change every 8 updates in the odd steps
    btst #0, E_PHASE(%a3)
    beq.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #1, %d0
    bra.w 7f
36: move.w en_counter(%pc), %d0              | rule 28, the magic of Nash and the Hood: a change every 4 updates, never mirrored
    lsr.w #2, %d0
    andi.w #1, %d0
    add.w %d0, %d0
    add.w %d0, %d6
    bra.w 4f
18: moveq #0, %d2                           | rule 11, Charron: picture 2 in step 5, 1 in step 0 and the odd ones, else a change every 8 updates
    move.b E_PHASE(%a3), %d2
    moveq #2, %d0
    cmpi.b #5, %d2
    beq.w 7f
    moveq #1, %d0
    tst.b %d2
    beq.w 7f
    btst #0, %d2
    bne.w 7f
    move.w en_counter(%pc), %d0
    lsr.w #3, %d0
    andi.w #1, %d0
    bra.w 7f
19: move.w en_counter(%pc), %d0              | rule 12, the fireball: four pictures, a change every 4 updates
    lsr.w #2, %d0
    andi.w #3, %d0
    bra.w 7f
16: moveq #0, %d0                           | rule 9, Yuinaru: the second picture while bit 3 of its count is set
    btst #3, E_D2(%a3)
    beq.w 7f
    moveq #1, %d0
    bra.w 7f
17: move.w en_counter(%pc), %d0              | rule 10, the Hornet: a change every 4 updates
    lsr.w #2, %d0
    andi.w #1, %d0
    bra.s 7f
3:  moveq #0, %d0                           | rule 1: by the script's step
    move.b E_PHASE(%a3), %d0
    subq.b #1, %d0
    andi.w #3, %d0
    lea monodron_frames(%pc), %a1
    move.b (%a1,%d0.w), %d0
7:  add.w %d0, %d0
    add.w %d0, %d6
    btst #0, E_FLAGS(%a3)
    beq.s 4f
    addq.w #1, %d6
4:  movea.l pkg_ptr+PKG_ENEMY_ANIM(%pc), %a5
    add.w %d6, %d6
    move.w (%a5,%d6.w), %d0
    adda.w %d0, %a5                         | the pose's record
    lea enemy_rects(%pc), %a2
    move.w slot_index(%pc), %d0
    lsl.w #6, %d0
    adda.w %d0, %a2
    move.w %d7, %d0
    lsl.w #3, %d0
    adda.w %d0, %a2                         | this enemy's box in this screen
    moveq #0, %d4
    move.b E_X(%a3), %d4
    moveq #0, %d5
    move.b E_Y(%a3), %d5
    sub.w camera(%pc), %d5
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a2)
    move.w %d7, -(%sp)
5:  move.w (%a5)+, %d0
    bmi.s 7f
    moveq #0, %d4
    move.b E_X(%a3), %d4
    add.w %d4, %d0
    moveq #0, %d1
    move.b E_Y(%a3), %d1
    sub.w camera(%pc), %d1
    add.w (%a5)+, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a6,%d2.l), %a1
    bsr.w blit_tile                         | (clobbers d0-d7, a0-a2)
    bra.s 5b
7:  move.w (%sp)+, %d7
    lea enemy_rects(%pc), %a0               | what of it reached into a side margin is cleared again
    move.w slot_index(%pc), %d0
    lsl.w #6, %d0
    adda.w %d0, %a0
    move.w %d7, %d0
    lsl.w #3, %d0
    adda.w %d0, %a0
    movem.w (%a0), %d0-%d3
    bsr.w clear_box
8:  lea E_BYTES(%a3), %a3
    addq.w #1, %d7
    cmpi.w #8, %d7
    blt.w 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

    .section .rodata
hbox_width:                                 | SPRITE_HITBOX_WIDTHS and ...HEIGHTS (the hit box types)
    .byte 0x0F, 0x0F, 0x1F, 0x1F, 0x1F, 0x3F, 0x2F
hbox_height:
    .byte 0x0F, 0x1F, 0x2F, 0x3F, 0x1F, 0x1F, 0x4F
hop_start:                                  | SPRITE_BEHAVIOUR_HOP_START_TICKS, ..._GRAVITY, ..._JUMP_STRENGTH, ..._GROUND_TICKS, by the hop kind
    .byte 0x40, 0x20, 0x10, 0x08, 0x10
hop_gravity:
    .byte 2, 3, 4, 5, 4
hop_strength:
    .byte 4, 5, 6, 7, 7
hop_ground:
    .byte 0xC0, 0x60, 0x30, 0x18, 0x30
hop_peak:                                   | SPRITE_BEHAVIOR_HOP_PEAK_TICKS and SPRITES_MAYBE_GRAVITY, by the gravity
    .byte 0xFF, 0x7F, 0x3F, 0x1F, 0x0F, 0x07, 0x03, 0x01
weapon_damage:                              | WEAPON_STRENGTHS (4, 8, 12, 16) plus a quarter: the pendant bug
    .byte 5, 10, 15, 20
armour_multiplier:                          | ARMOR_DEFENSE_MULTIPLIERS
    .byte 0, 1, 2, 4
hop_maybe:
    .byte 0x00, 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02
buzz_frac:                                  | SPRITE_BEHAVIOR_BUZZ_AROUND_Y_FRAC, ..._X_FRAC (the whole pixels of the vertical step)
    .byte 0x00, 0x00, 0x80, 0x40, 0x00, 0x40, 0x80, 0x00
buzz_full:
    .byte 2, 1, 0, 0, 0, 0, 0, 1
lamprey_poses:                              | 2 * the picture (BYTE_ARRAY_PRG14__978b) + the mirror bit (LAMPREY_HORIZ_FLIP_BITS) for each eighth of a 64-update turn
    .byte 0, 2, 3, 1, 3, 2, 0, 3
zombie_frames:                              | SPRITEBEHAVIOR_ENEMY_ZOMBIE_PHASES
    .byte 0, 1, 2, 1
monodron_frames:                            | SPRITE_MONODRON_APPEARANCE_PHASES
    .byte 0, 2, 0, 1
tamazutsu_frames:                           | BYTE_ARRAY_PRG14__9905 and ..9908 halved: the pictures of Tamazutsu's steps 1 and 3
    .byte 4, 3, 2, 2, 3, 4
necron_steps:                               | BYTE_ARRAY_PRG14__8e3c: the fraction of Necron Aides' step on the ladder, by the counter in fours
    .byte 0x20, 0x40, 0x80, 0x00
random_table:                               | the 256 bytes of the ROM's code GetRandom reads (build_assets.py)
    .incbin "random.bin"
    .even

    .section .data
enemies:
    .space 8*E_BYTES
enemy_rects:
    .space 2*8*8                            | two screens, 8 enemies, each x0, x1, y0, y1 (words)
touch_box:
    .space 8
en_counter:
    .word 0
hero_weapon:
    .word HERO_WEAPON                       | Player_CurWeapon, 255: none
hero_hpl:
    .byte 0                                 | Player_HP_L, the fraction of the power
    .even
en_rnd:
    .byte 0, 0
en_blocks:
    .long 0                                 | this screen's flags of the blocks he cannot walk through
en_ids:
    .long 0                                 | its block ids
