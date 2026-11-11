| The springs of Trunk, the fountain and the way to Mascon (AGENTS.md, 5e "The springs and the fountain").
|
| beh_water         SpriteBehavior_Fountain ($52, behaviour 57) and _SpringOfFortress, _SpringOfSky, _SpringOfJoker ($61 to $63, behaviours 58 to 60)
| mascon_tick       once a frame after the door: the screen's event 0 on its first tick (ScreenEvents_HandlePathToMasconEvent) and the stone pushed
|                   (Player_CheckPushingBlock)
| mascon_open       Game_OpenPathToMascon and Game_DropLadderToMascon: the stone moves a block, is gone, the ladder drops; the game stands still meanwhile

    .section .text.late,"ax"                | (behind blit.s: the code in .text has no reach to spare; .data is reached through a6 = the image's start, all of .data
    .even                                   | lies in its first 32 KB, see WATER_BASE)
mascon_new:   .word 0                       | a screen was entered (enemies_load): its event runs on the next tick (these two are in .text, beside their code:
mascon_push:  .word 0                       | BlockPushCounter                        nothing in .data moves and the data reach is not used)

    .macro WATER_BASE                       | a6 = where the image starts (game_start): link addresses of .data are offsets from it
    lea 77f(%pc), %a6
77: suba.l #77b, %a6
    .endm

| a3 = the slot, d0 = the behaviour (57 to 60). The ROM's Sprite_SetVisible sets the flag bit 4, which here means hidden: the fountain shows only when all three springs flow
| (Quests & 7); a spring is dry (step 0, hidden, nothing drawn) until its quest bit is set, then rises (step 1: the count d3 goes up each update, d2 every 4th, pictures
| 0 to 3) and flows (step 2) from d2 = 4. It rises again each time the screen is entered.
beh_water:
    btst #6, E_FLAGS(%a3)                   | Sprite_IsBehaviorNotReady: Sprites_MaybeResetPhaseAndEnable
    bne.s 1f
    clr.b E_PHASE(%a3)
    bset #6, E_FLAGS(%a3)
1:  move.l %a6, -(%sp)
    WATER_BASE
    move.b inv+INV_QUESTS(%a6), %d1
    movea.l (%sp)+, %a6
    subi.w #57, %d0
    bne.s 3f
    andi.b #7, %d1                          | the fountain
    cmpi.b #7, %d1
    bne.s 2f
    bclr #4, E_FLAGS(%a3)
    bra.w en_behaviour_end
2:  bset #4, E_FLAGS(%a3)
    bra.w en_behaviour_end
3:  subq.w #1, %d0                          | a spring: quest bit 0, 1 or 2
    tst.b E_PHASE(%a3)
    bne.s 4f
    btst %d0, %d1
    beq.s 2b
4:  bclr #4, E_FLAGS(%a3)                   | (SpriteBehavior_Springs_UpdateFlowing: Sprites_HideSprite, which shows it)
    move.b E_PHASE(%a3), %d1
    bne.s 5f
    moveq #1, %d1
    move.b %d1, E_PHASE(%a3)
    clr.b E_D2(%a3)
    clr.b E_D3(%a3)
5:  subq.b #1, %d1
    bne.s 7f
    addq.b #1, E_D3(%a3)
    moveq #3, %d1
    and.b E_D3(%a3), %d1
    bne.w en_behaviour_end
    addq.b #1, E_D2(%a3)
    cmpi.b #4, E_D2(%a3)
    bcs.w en_behaviour_end
7:  move.b #2, E_PHASE(%a3)                 | Sprite_SetPhase2
    bra.w en_behaviour_end

| Once a frame after door_check. The first tick of a screen whose event is 0 (Trunk's screen 40): with the way to Mascon open (quest bit 5) the stone is taken away and
| the ladder drops again (the ROM keeps nothing of a screen: it is made from the data each time). Then the push: left or right held, the Ruby Ring, all three springs, and
| the block in front of his head (x + 16 facing right, x - 1 facing left, 8 bits; the row of his y) is the stone (block property 6): the count goes up, sound $0F at 63,
| the way opens at 96 (the stone moves to the side he pushes); anything else sets the count to 0.
mascon_tick:
    movem.l %d0-%d7/%a0-%a2/%a6, -(%sp)
    WATER_BASE
    lea mascon_new(%pc), %a0
    tst.w (%a0)
    beq.s 1f
    clr.w (%a0)
    movea.l pkg_ptr+PKG_SCREEN_EVENTS(%a6), %a1
    move.w cur_screen(%a6), %d1
    tst.b (%a1,%d1.w)
    bne.s 1f
    btst #5, inv+INV_QUESTS(%a6)
    beq.s 1f
    moveq #0x56, %d3                        | (PathToMascon_FountainCoverPos: X = 6, Y = 5)
    moveq #1, %d4
    moveq #0, %d5                           | no wait: the way is open already
    bsr.w mascon_open
    bra.w 9f
1:  lea mascon_push(%pc), %a2
    move.b input_state+IN_PAD(%a6), %d4
    andi.w #NES_LEFT+NES_RIGHT, %d4
    beq.w 8f
    btst #6, inv+INV_SPECIAL(%a6)           | the Ruby Ring
    beq.w 8f
    moveq #7, %d1
    and.b inv+INV_QUESTS(%a6), %d1
    cmpi.b #7, %d1
    bne.w 8f
    move.w hero_x(%a6), %d1
    moveq #-1, %d0
    move.w hero_flip(%a6), %d2
    beq.s 2f
    moveq #16, %d0
2:  add.w %d0, %d1
    andi.w #0xF0, %d1
    lsr.w #4, %d1
    move.w hero_y(%a6), %d2
    andi.w #0xF0, %d2
    cmpi.w #13*16, %d2
    bcc.s 8f                                | (rows 13 to 15 of the ROM's buffer are zeros)
    move.w %d2, %d3
    or.w %d1, %d3                           | the place
    move.w cur_screen(%a6), %d0
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%a6), %a0
    adda.l %d0, %a0
    moveq #0, %d0
    move.b (%a0,%d3.w), %d0
    movea.l pkg_ptr+PKG_BLOCK_FLAGS(%a6), %a0
    btst #3, (%a0,%d0.w)                    | property 6: the stone
    beq.s 8f
    addq.w #1, (%a2)
    cmpi.w #0x3F, (%a2)
    bne.s 3f
    moveq #0x0F, %d0
    bsr.w sound_play_sfx
3:  cmpi.w #0x60, (%a2)
    bcs.s 9f
    moveq #1, %d5                           | the first time: 30 frames of the stone at its new place
    btst #5, inv+INV_QUESTS(%a6)
    beq.s 4f
    moveq #0, %d5
4:  lsr.w #1, %d4                           | Right: one block right, Left: one block left (GAME_LADDER_TO_MASCON_BLOCK_OFFSETS)
    bcc.s 5f
    moveq #1, %d4
    bra.s 6f
5:  moveq #-1, %d4
6:  bsr.s mascon_open
    bra.s 9f
8:  clr.w (%a2)
9:  movem.l (%sp)+, %d0-%d7/%a0-%a2/%a6
    rts

| d3 = the stone's place (row * 16 + column, the top of its two blocks), d4 = +1 or -1 (where it goes), d5 = 1: wait 30 frames before it is gone; a6 = WATER_BASE. Frames as the ROM's:
| the move at 0, gone at 30 (or at once), then 7 ladder blocks 4 frames apart from row 2 of column 2 down (sound $17 each), quest bit 5 set; the game stands still and the
| sprites stay as they were drawn (mattock_sprites). What is changed is noted for mattock_restore: the screen is whole again when it is drawn next. Keeps nothing.
mascon_open:
    move.w cur_screen(%a6), %d0
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%a6), %a2
    adda.l %d0, %a2                         | this screen's block ids
    move.w %d3, %d7
    bsr.w mattock_record                    | (the stone's two blocks)
    add.w %d4, %d3
    bsr.w mattock_record                    | (and the two it goes to)
    move.w %d7, %d3
    moveq #0x42, %d6                        | MASCON_FOUNTAIN_BLOCK_1_AIR
    bsr.w mascon_pair
    add.w %d4, %d3
    move.w %d3, %d7
    tst.w %d5
    beq.s 2f                                | (the ROM puts it there and takes it away in the same frame: nothing is seen)
    move.w #0x88, %d6                       | MASCON_FOUNTAIN_BLOCK_1_STONE (the ids are the ROM's: tools/build_assets.py mascon_blocks makes their images)
    bsr.w mascon_pair
    move.w %d7, %d3
    bsr.w mascon_present
    moveq #30-2-1, %d1
1:  bsr.w wait_vbl
    dbra %d1, 1b
2:  moveq #0x42, %d6
    move.w %d7, %d3
    bsr.w mascon_pair
    bsr.w mascon_present
    lea inv+INV_QUESTS(%a6), %a0            | Game_DropLadderToMascon: the way to Mascon is open
    bset #5, (%a0)
    moveq #0x22, %d3                        | (PathToMascon_LadderPos: X = 2, Y = 2; the column is noted two rows at a time)
    moveq #3, %d1
3:  bsr.w mattock_record
    addi.w #32, %d3
    dbra %d1, 3b
    moveq #0x22, %d3
    moveq #7-1, %d7
4:  bsr.w wait_vbl
    bsr.w wait_vbl
    moveq #0x17, %d0
    bsr.w sound_play_sfx
    moveq #0x20, %d6                        | DROP_LADDER_TO_MASCON_LADDER_BLOCK
    bsr.w mascon_block
    bsr.w mascon_present
    addi.w #16, %d3
    dbra %d7, 4b
    bsr.w mattock_flags_reset
    lea mascon_push(%pc), %a0
    clr.w (%a0)
    rts

mascon_pair:                                | the block d6 at the place d3 and the one under it
    bsr.w mascon_block
    addi.w #16, %d3
    bsr.w mascon_block
    subi.w #16, %d3
    rts

mascon_block:                               | the block d6 at the place d3 of the ids a2, drawn into the playfield
    movem.l %d1-%d2, -(%sp)
    cmpi.w #208, %d3
    bcc.s 9f
    move.b %d6, (%a2,%d3.w)
    move.w %d3, %d1
    andi.w #15, %d1
    move.w %d3, %d2
    lsr.w #4, %d2
    bsr.w mattock_draw_block
9:  movem.l (%sp)+, %d1-%d2
    rts

mascon_present:                             | both screens get the blocks at d3 and under it (two frames), the sprites drawn again over them
    movem.l %d1-%d2/%d7, -(%sp)
    bsr.w mattock_flags_reset
    move.w %d3, %d1
    andi.w #15, %d1
    move.w %d3, %d2
    lsr.w #4, %d2
    moveq #1, %d7
1:  bsr.w mattock_show
    bsr.w mattock_sprites
    bsr.w present_swap
    dbra %d7, 1b
    movem.l (%sp)+, %d1-%d2/%d7
    rts
    .text
