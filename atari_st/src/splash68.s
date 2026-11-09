| The title screen, the intro and the ending (F1). Included by viewer.s when SPLASH, INTRO or ENDING is defined.
|
| The data is TITLE.DAT, INTRO.DAT and OUTRO.DAT (tools/splash.py, layouts in splash.inc). The program reads one when it needs it into the
| room of the second playfield (next_ptr, which only a scroll uses), unpacks it where it lies and shows it; nothing stays resident.
|
| The code sits in its own section, .text.early, which link.ld puts in front of the variables: the main code is at the limit of what
| PC-relative addressing reaches from the variables, and four more kilobytes behind it would not reach them. (check_reach.py knows the section.)
|
| title_screen    d0 = 0 START, 1 CONTINUE, -1 no TITLE.DAT, 2 Esc
| intro_play      the hero walks away up the road; one pass of the ROM's loop for each VBL, 659 of them (the NES runs it at 60 Hz, the ST at
|                 50: the walk is a fifth slower than on an NTSC console and as fast as on a PAL one, which is what the Europe ROM runs on)
| ending_play     the ending: 2571 passes (the hero walks down the road, then the waterfall until song 12 has ended, then 240 more)
| splash_start    the whole flow: title, START to the intro and the game, CONTINUE to the mantra's entry; after ending_play call it again for the title
|
| Debug builds: SPLASH=1 (with MENU=1 or without) shows the title before the game, INTRO=1 plays the intro at the start and goes on to the game,
| ENDING=1 plays the ending first and then shows the title.

    .include "splash.inc"

    .equ ST_N, 0                            | the engine's state (sp_st): word fields
    .equ ST_X, 2                            | the hero's x and y in 8.8 fixed point, the velocities (signed words)
    .equ ST_Y, 4
    .equ ST_VX, 6
    .equ ST_VY, 8
    .equ ST_SIZE, 10
    .equ ST_COUNT, 12                       | the intro's walk counter; the ending's free-running counter (the waterfall)
    .equ ST_STAGE, 14                       | the intro: passes since the hero stopped growing
    .equ ST_FADES, 16                       | the intro: fade steps made
    .equ ST_LOOP, 18                        | the ending: 1 the hero walks, 2 waiting for the song, 3 the last 240 passes
    .equ ST_HCOUNT, 20                      | the ending's walk counter
    .equ ST_DONE, 22
    .equ ST_L3AT, 24                        | the ending: the pass loop 3 began at
    .equ ST_PALSTEP, 26                     | the fade step the palette has
    .equ ST_SPK, 28                         | two sparkles of 12 bytes: x, y (8.8), vx, vy, phase, count
    .equ ST_BYTES, 52

    .if INTRO_PART_POSES != OUTRO_PART_POSES
    .error "splash.py: the intro and the ending files have different layouts"
    .endif
    .if INTRO_T_THRESHOLD != OUTRO_T_THRESHOLD
    .error "splash.py: the intro and the ending tables have different layouts"
    .endif

    .macro CELL_COPY
    .set cell_o, 0
    .rept 8
    move.b (%a1)+, cell_o(%a0)
    move.b (%a1)+, cell_o+2(%a0)
    move.b (%a1)+, cell_o+4(%a0)
    move.b (%a1)+, cell_o+6(%a0)
    .set cell_o, cell_o+160
    .endr
    .endm

    .macro CELL_CLEAR
    .set cell_o, 0
    .rept 8
    clr.b cell_o(%a0)
    clr.b cell_o+2(%a0)
    clr.b cell_o+4(%a0)
    clr.b cell_o+6(%a0)
    .set cell_o, cell_o+160
    .endr
    .endm

    .section .text.early,"ax"
early_start:

| ------------------------------------------------------------------------------------------------------------------ the flow
| Called where the plain start menu would be. Esc leaves at once (the frame loop sees it).
splash_start:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    lea hud_dirty(%pc), %a0
    clr.b (%a0)                             | the title is not the place for the HUD
    .ifdef ENDING
    bsr.w ending_play
    .endif
    .ifdef INTRO
    bsr.w intro_play
    bra.w 6f
    .endif
1:  bsr.w title_screen
    tst.w %d0
    bmi.w 8f                                | no TITLE.DAT: the plain menu
    cmpi.w #2, %d0
    beq.w 9f                                | Esc
    tst.w %d0
    bne.s 3f
    bsr.w intro_play                        | START: the intro, then the game
6:  lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.w 9f
    bsr.w sp_leave
    .ifdef NEWGAME
    bsr.w new_game                          | the ROM's new game: Eolis screen 0, Eolis's song (src/flow.s)
    .else
    move.w cur_music(%pc), %d0              | the area's song, which was playing before the title
    bsr.w sound_play_music
    .endif
    bra.w 9f
3:  moveq #8, %d0                           | CONTINUE: the ROM leaves song 8 on through the password screen
    bsr.w sound_play_music
    bsr.w sp_leave                          | the game's picture, and the entry on it as the plain menu does it
    bsr.w mantra_entry
    tst.w %d0
    beq.s 4f
    bsr.w box_leave                         | accepted: the game begins as after a death, with what the mantra holds
    lea pw_block(%pc), %a1
    bsr.w mantra_apply
    bra.s 9f
4:  bsr.w box_leave                         | given up: back to the title
    bra.w 1b
8:  bsr.w start_menu
9:  movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| Back to the game: the screens are cleared (the HUD only draws what it has under its own rows), the second playfield too (the scroll counts on its
| margins being black), the HUD is drawn again, both screens get the window and the hero, the package's palette comes back.
sp_leave:
    movem.l %d0-%d2/%a0-%a1/%a6, -(%sp)
    bsr.w sp_black_palette
    movea.l buf_a(%pc), %a6
    bsr.w sp_clear
    movea.l buf_b(%pc), %a6
    bsr.w sp_clear
    movea.l next_ptr(%pc), %a0
    move.w #(REGION_BYTES/4)-1, %d0
1:  clr.l (%a0)+
    dbra %d0, 1b
    lea hud_shown(%pc), %a0
    moveq #(3*128/4)-1, %d2
2:  move.l #-1, (%a0)+
    dbra %d2, 2b
    lea hud_dirty(%pc), %a0
    st (%a0)
    bsr.w box_leave
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a0
    bsr.w sp_set_palette
    movem.l (%sp)+, %d0-%d2/%a0-%a1/%a6
    rts

| ------------------------------------------------------------------------------------------------------------------ the file
| a0 = the name, d0.l = the size of the packed file. Out: d0 = 0 it is read and unpacked at next_ptr (sp_base), -1 it is not there. The disk is read
| as load_package does: the song is silenced and TOS's own VBL runs meanwhile (it switches the drive off again; ours would not). The word LOADING
| is on the screen that is shown while it takes.
splash_load:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    move.l %d0, %d4                         | the size
    movea.l %a0, %a3                        | the name
    bsr.w loading_show
    bsr.w sound_silence
    move.l old_vbl(%pc), %d2
    beq.s 8f
    lea saved_vbl(%pc), %a1
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l VBL_VECTOR, (%a1)
    move.l %d2, VBL_VECTOR
    move.w (%sp)+, %sr
8:  moveq #-1, %d3                          | the result
    clr.w -(%sp)                            | Fopen(name, read)
    move.l %a3, -(%sp)
    move.w #0x3D, -(%sp)
    trap #1
    addq.l #8, %sp
    tst.l %d0
    bmi.s 9f
    move.w %d0, %d5                         | the handle (the traps keep d3-d7 and a3-a6)
    movea.l next_ptr(%pc), %a3
    adda.l #SPLASH_SPAN, %a3
    suba.l %d4, %a3
    move.l %a3, %d0
    bclr #0, %d0
    movea.l %d0, %a3                        | the packed file lies at the end of the room, on an even address
    move.l %a3, -(%sp)                      | Fread(handle, count, buffer)
    move.l %d4, -(%sp)
    move.w %d5, -(%sp)
    move.w #0x3F, -(%sp)
    trap #1
    lea 12(%sp), %sp
    move.l %d0, %d6
    move.w %d5, -(%sp)                      | Fclose
    move.w #0x3E, -(%sp)
    trap #1
    addq.l #4, %sp
    cmp.l %d4, %d6
    bne.s 9f
    movea.l %a3, %a0
    movea.l next_ptr(%pc), %a1
    bsr.w unpack
    lea sp_base(%pc), %a0
    move.l %a1, (%a0)
    moveq #0, %d3
9:  move.l old_vbl(%pc), %d2
    beq.s 10f
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l saved_vbl(%pc), VBL_VECTOR
    move.w (%sp)+, %sr
10: bsr.w loading_hide
    move.l %d3, %d0
    movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

| ------------------------------------------------------------------------------------------------------------------ the screen
| a6 = a screen: cleared.
sp_clear:
    movem.l %d0/%a0, -(%sp)
    movea.l %a6, %a0
    move.w #7999, %d0
1:  clr.l (%a0)+
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0
    rts

| a0 = 16 palette words.
sp_set_palette:
    movem.l %d0/%a0-%a1, -(%sp)
    movea.l #PALETTE, %a1
    moveq #15, %d0
1:  move.w (%a0)+, (%a1)+
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0-%a1
    rts

sp_black_palette:
    movem.l %d0/%a0, -(%sp)
    movea.l #PALETTE, %a0
    moveq #15, %d0
1:  clr.w (%a0)+
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0
    rts

| The background's cells: columns d2 to d3 - 1, rows d4 to d5 - 1 (clipped to the 32 x 25 of the picture) of the map sp_map, drawn from the tiles
| sp_tiles into the screen a6, a cell being 8 x 8 pixels at x = 32 + 8 * column. A blank cell ($FFFF) is cleared. Keeps every register.
sp_cells:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    tst.w %d2
    bpl.s 1f
    moveq #0, %d2
1:  cmpi.w #32, %d3
    ble.s 2f
    moveq #32, %d3
2:  tst.w %d4
    bpl.s 3f
    moveq #0, %d4
3:  cmpi.w #25, %d5
    ble.s 4f
    moveq #25, %d5
4:  cmp.w %d3, %d2
    bge.s 9f
    cmp.w %d5, %d4
    bge.s 9f
    movea.l sp_map(%pc), %a2
    movea.l sp_tiles(%pc), %a3
    move.w %d4, %d6
5:  move.w %d2, %d7
6:  bsr.s sp_cell
    addq.w #1, %d7
    cmp.w %d3, %d7
    blt.s 6b
    addq.w #1, %d6
    cmp.w %d5, %d6
    blt.s 5b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| One cell: d6 = row, d7 = column, a2 = the map, a3 = the tiles, a6 = the screen. Clobbers d0, d1, a0, a1.
sp_cell:
    move.w %d6, %d1
    lsl.w #5, %d1
    add.w %d7, %d1
    add.w %d1, %d1
    move.w (%a2,%d1.w), %d0                 | the map's word
    move.w %d6, %d1
    mulu.w #8*160, %d1
    lea 16(%a6), %a0                        | x = 32
    adda.l %d1, %a0
    move.w %d7, %d1
    lsr.w #1, %d1
    lsl.w #3, %d1
    adda.w %d1, %a0                         | the 16-pixel group
    btst #0, %d7
    beq.s 1f
    addq.l #1, %a0                          | the right half of the group: the low bytes of its plane words
1:  addq.w #1, %d0
    beq.w 2f
    subq.w #1, %d0
    mulu.w #32, %d0
    movea.l %a3, %a1
    adda.l %d0, %a1
    CELL_COPY
    rts
2:  CELL_CLEAR
    rts

| ------------------------------------------------------------------------------------------------------------------ sprites
| The sprites of the objects are drawn with blit_tile into the screen a4. What one buffer holds is remembered: sp_shown, the pose and place of the
| four objects (hero, sparkle 0, sparkle 1, waterfall; a frame of -1 is none), and sp_boxes, the box each covered. A buffer that already holds what
| sp_obj says is left alone; otherwise the boxes are made again from the background's cells and the objects are drawn, the last one first (the
| ROM's list has the hero first and the first is in front).

| d0 = the frame, d1 = X, d2 = Y (the object's NES place), a4 = the screen: draws the pose's sprites, leaving out those from the cutoff on, and
| makes sp_box the box they cover. Keeps every register.
sp_pose:
    movem.l %d0-%d7/%a0-%a3/%a5, -(%sp)
    lea sp_px(%pc), %a0
    move.w %d1, (%a0)+
    move.w %d2, (%a0)
    movea.l sp_poses(%pc), %a5
    add.w %d0, %d0
    move.w (%a5,%d0.w), %d0
    adda.w %d0, %a5                         | the pose's triples: x offset, line offset, image
    movea.l sp_images(%pc), %a3
1:  move.w (%a5)+, %d0
    bmi.w 9f
    move.w (%a5)+, %d1
    move.w (%a5)+, %d2
    add.w sp_px(%pc), %d0
    add.w sp_py(%pc), %d1
    cmpi.w #SPLASH_CUTOFF, %d1
    bge.s 1b
    lea sp_box(%pc), %a0                    | the box grows
    cmp.w (%a0), %d0
    bge.s 2f
    move.w %d0, (%a0)
2:  move.w %d0, %d3
    addq.w #8, %d3
    cmp.w 2(%a0), %d3
    ble.s 3f
    move.w %d3, 2(%a0)
3:  cmp.w 4(%a0), %d1
    bge.s 4f
    move.w %d1, 4(%a0)
4:  move.w %d1, %d3
    addq.w #8, %d3
    cmp.w 6(%a0), %d3
    ble.s 5f
    move.w %d3, 6(%a0)
5:  mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile
    bra.s 1b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5
    rts

| a0 = a box (x0, x1, y0, y1: ST pixels, the ends exclusive; x1 negative is none), a6 = the screen: the background's cells it touches are drawn again.
sp_erase_box:
    movem.l %d2-%d5, -(%sp)
    tst.w 2(%a0)
    bmi.s 9f
    move.w (%a0), %d2
    subi.w #32, %d2
    asr.w #3, %d2                           | the first column
    move.w 2(%a0), %d3
    subi.w #25, %d3                         | (x1 - 32 + 7) / 8: the end column
    asr.w #3, %d3
    move.w 4(%a0), %d4
    asr.w #3, %d4
    move.w 6(%a0), %d5
    addq.w #7, %d5
    asr.w #3, %d5
    bsr.w sp_cells
9:  movem.l (%sp)+, %d2-%d5
    rts

| a4 = the screen to draw into: gets the objects of sp_obj (see above) and sp_bufpass remembers which pass it holds.
sp_render:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    movea.l %a4, %a6
    moveq #0, %d7                           | 0 for the screen buf_a, 1 for buf_b
    cmpa.l buf_a(%pc), %a4
    beq.s 1f
    moveq #1, %d7
1:  lea sp_shown(%pc), %a2
    move.w %d7, %d0
    mulu.w #24, %d0
    adda.w %d0, %a2                         | what this screen holds
    lea sp_obj(%pc), %a0
    movea.l %a2, %a3
    moveq #5, %d0
2:  cmpm.l (%a0)+, (%a3)+
    bne.s 3f
    dbra %d0, 2b
    bra.s 8f                                | the same: nothing to do
3:  lea sp_boxes(%pc), %a5
    move.w %d7, %d0
    lsl.w #5, %d0
    adda.w %d0, %a5                         | the four boxes of this screen
    movea.l %a5, %a0
    moveq #3, %d6
4:  bsr.w sp_erase_box
    lea 8(%a0), %a0
    dbra %d6, 4b
    moveq #3, %d6                           | the objects, the last first
5:  move.w %d6, %d0
    mulu.w #6, %d0
    lea sp_obj(%pc), %a0
    adda.w %d0, %a0
    move.w %d6, %d1
    lsl.w #3, %d1
    lea (%a5,%d1.w), %a1                    | this object's box in the screen's list
    lea sp_box(%pc), %a3
    move.w #32767, (%a3)
    move.w #-1, 2(%a3)
    move.w #32767, 4(%a3)
    move.w #-1, 6(%a3)
    move.w (%a0), %d0
    bmi.s 6f
    move.w 2(%a0), %d1
    move.w 4(%a0), %d2
    bsr.w sp_pose
6:  move.l (%a3), (%a1)
    move.l 4(%a3), 4(%a1)
    subq.w #1, %d6
    bpl.s 5b
    lea sp_obj(%pc), %a0                    | this is what the screen holds now
    moveq #5, %d0
7:  move.l (%a0)+, (%a2)+
    dbra %d0, 7b
8:  lea sp_bufpass(%pc), %a0
    add.w %d7, %d7
    move.w sp_st+ST_N(%pc), (%a0,%d7.w)
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| The palette follows the fade step: after the screen is shown.
sp_fade_palette:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    lea sp_st(%pc), %a1
    move.w ST_FADES(%a1), %d0
    cmp.w ST_PALSTEP(%a1), %d0
    beq.s 9f
    move.w %d0, ST_PALSTEP(%a1)
    subq.w #1, %d0
    lsl.w #5, %d0
    movea.l sp_fade(%pc), %a0
    adda.w %d0, %a0
    bsr.w sp_set_palette
9:  movem.l (%sp)+, %d0-%d1/%a0-%a1
    rts

| The scene's pointers from the header of the unpacked file (the intro's and the ending's have the same layout): sp_pal, sp_fade, sp_tiles,
| sp_map, sp_images, sp_poses, sp_tables.
sp_scene_setup:
    movem.l %d0-%d1/%a0-%a2, -(%sp)
    movea.l sp_base(%pc), %a0
    movea.l %a0, %a2
    lea sp_pal(%pc), %a1
    moveq #6, %d1
1:  move.l (%a2)+, %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+
    dbra %d1, 1b
    movem.l (%sp)+, %d0-%d1/%a0-%a2
    rts

| Both screens get the background, black meanwhile; nothing is drawn on them; the palette is the scene's. a4 is the screen to draw next.
sp_scene_show:
    movem.l %d0-%d6/%a0-%a1/%a6, -(%sp)
    bsr.w sp_black_palette
    lea sp_shown(%pc), %a0                  | no objects on either screen
    moveq #(2*24/4)-1, %d0
1:  move.l #-1, (%a0)+
    dbra %d0, 1b
    lea sp_boxes(%pc), %a0
    moveq #7, %d0
2:  move.l #0xFFFF, (%a0)+                  | x0 = 0, x1 = -1: none
    clr.l (%a0)+
    dbra %d0, 2b
    lea sp_obj(%pc), %a0
    moveq #5, %d0
3:  move.l #-1, (%a0)+
    dbra %d0, 3b
    moveq #1, %d6
4:  movea.l %a4, %a6
    bsr.w sp_clear
    moveq #0, %d2
    moveq #32, %d3
    moveq #0, %d4
    moveq #25, %d5
    bsr.w sp_cells
    bsr.w present_swap
    dbra %d6, 4b
    movea.l sp_pal(%pc), %a0
    bsr.w sp_set_palette
    movem.l (%sp)+, %d0-%d6/%a0-%a1/%a6
    rts

| The hero's start: x, y, vx, vy from the table (the intro's and the ending's table both begin with them).
sp_state_init:
    movem.l %d0/%a0-%a2, -(%sp)
    lea sp_st(%pc), %a0
    moveq #(ST_BYTES/2)-1, %d0
1:  clr.w (%a0)+
    dbra %d0, 1b
    lea sp_st(%pc), %a0
    movea.l sp_tables(%pc), %a1
    moveq #0, %d0
    move.b (%a1), %d0
    lsl.w #8, %d0
    move.w %d0, ST_X(%a0)
    moveq #0, %d0
    move.b 1(%a1), %d0
    lsl.w #8, %d0
    move.w %d0, ST_Y(%a0)
    move.b 2(%a1), %d0
    ext.w %d0
    move.w %d0, ST_VX(%a0)
    move.b 3(%a1), %d0
    ext.w %d0
    move.w %d0, ST_VY(%a0)
    move.w #1, ST_LOOP(%a0)
    movem.l (%sp)+, %d0/%a0-%a2
    rts

| ------------------------------------------------------------------------------------------------------------------ the title
| d0 = 0 START, 1 CONTINUE (the choice is made with Start, fire or Return), -1 TITLE.DAT is not there, 2 Esc.
title_screen:
    movem.l %d1-%d7/%a0-%a6, -(%sp)
    lea str_title(%pc), %a0
    move.l #TITLE_PACKED, %d0
    bsr.w splash_load
    tst.l %d0
    bne.w 90f
    movea.l sp_base(%pc), %a0               | the pointers: sp_pal, tiles, map; the arrow is "the images", its places "the poses"
    lea sp_pal(%pc), %a1
    move.l TITLE_PART_PALETTE(%a0), %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+                      | sp_pal
    addq.l #4, %a1                          | (sp_fade: not used)
    move.l TITLE_PART_TILES(%a0), %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+                      | sp_tiles
    move.l TITLE_PART_MAP(%a0), %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+                      | sp_map
    move.l TITLE_PART_ARROW(%a0), %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+                      | sp_images
    move.l TITLE_PART_CURSOR(%a0), %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+                      | sp_poses
    lea sp_phase(%pc), %a0
    move.w #1, (%a0)
    lea sp_cursor(%pc), %a0
    clr.w (%a0)
    bsr.w sp_black_palette
    movea.l %a4, %a6
    bsr.w sp_clear
    moveq #0, %d2
    moveq #32, %d3
    moveq #0, %d4
    moveq #25, %d5
    bsr.w sp_cells
    bsr.w sp_arrow
    bsr.w present_swap
    movea.l sp_pal(%pc), %a0
    bsr.w sp_set_palette
    moveq #1, %d0                           | the title song, which plays once
    bsr.w sound_play_music
10: bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 80f
    moveq #0, %d0
    move.b IN_PAD_NEW(%a0), %d0
    move.w %d0, %d1
    andi.w #NES_UP+NES_DOWN+NES_SELECT, %d1
    beq.s 11f
    lea sp_cursor(%pc), %a0                 | Select, or up or down: the other choice, sound $0B
    eori.w #1, (%a0)
    moveq #0x0B, %d0
    bsr.w sound_play_sfx
    bsr.w shown_screen
    movea.l %a3, %a6                        | the screen on show is changed (the arrow is far from the beam)
    bsr.w sp_arrow
    bra.s 10b
11: andi.w #NES_START+NES_A+NES_B, %d0
    beq.s 10b
    move.w sp_cursor(%pc), %d0
    bra.s 99f
80: moveq #2, %d0
    bra.s 99f
90: moveq #-1, %d0
99: movem.l (%sp)+, %d1-%d7/%a0-%a6
    rts

| a6 = the screen: the arrow at the cursor, after the background where either arrow can be is drawn again.
sp_arrow:
    movem.l %d0-%d7/%a0-%a5, -(%sp)
    moveq #6, %d2
    moveq #8, %d3
    moveq #16, %d4
    moveq #18, %d5
    bsr.w sp_cells
    moveq #14, %d2
    moveq #16, %d3
    bsr.w sp_cells
    movea.l sp_poses(%pc), %a0
    move.w sp_cursor(%pc), %d0
    lsl.w #2, %d0
    move.w (%a0,%d0.w), %d1
    move.w 2(%a0,%d0.w), %d2
    move.w %d1, %d0
    move.w %d2, %d1
    movea.l sp_images(%pc), %a1
    movea.l %a6, %a4
    bsr.w blit_tile
    movem.l (%sp)+, %d0-%d7/%a0-%a5
    rts

| ------------------------------------------------------------------------------------------------------------------ the intro
intro_play:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    lea str_intro(%pc), %a0
    move.l #INTRO_PACKED, %d0
    bsr.w splash_load
    tst.l %d0
    bne.w 99f                               | no INTRO.DAT: no intro
    moveq #0, %d0                           | the ROM plays no song in the intro
    bsr.w sound_play_music
    lea sp_phase(%pc), %a0
    move.w #2, (%a0)
    bsr.w sp_scene_setup
    bsr.w sp_state_init
    bsr.w sp_scene_show
    lea sp_late0(%pc), %a0
    move.l late_frames(%pc), (%a0)
1:  bsr.w intro_tick
    tst.w %d0
    beq.s 2f
    bsr.w sound_play_sfx                    | a footstep
2:  bsr.w sp_render
    bsr.w present_swap
    bsr.w sp_fade_palette
    bsr.w input_poll                        | (the ROM does not let the intro be skipped: only Esc leaves)
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 99f
    move.w sp_st+ST_DONE(%pc), %d0
    beq.s 1b
99: movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| One pass of SplashAnimation_RunIntro ($A7F9; tools/splash_model.py `Intro.tick` is the reference): the hero moves, grows when he is high enough
| up the road, the walk frame follows the count; sp_obj gets the hero. Out: d0 = the sound effect of this pass (0 none).
intro_tick:
    movem.l %d1-%d5/%a0-%a2, -(%sp)
    lea sp_st(%pc), %a0
    movea.l sp_tables(%pc), %a1
    addq.w #1, ST_N(%a0)
    move.w ST_VX(%a0), %d1
    add.w %d1, %d1                          | 8.8 fixed point: the velocity byte is in 1/128 pixels
    add.w %d1, ST_X(%a0)
    move.w ST_VY(%a0), %d1
    add.w %d1, %d1
    add.w %d1, ST_Y(%a0)
    move.w ST_SIZE(%a0), %d2
    move.w ST_Y(%a0), %d1
    lsr.w #8, %d1
    cmp.b INTRO_T_THRESHOLD(%a1,%d2.w), %d1
    bcc.s 1f                                | not yet up the road far enough for the next size
    move.b INTRO_T_VX(%a1,%d2.w), %d3
    ext.w %d3
    move.w %d3, ST_VX(%a0)
    move.b INTRO_T_VY(%a1,%d2.w), %d3
    ext.w %d3
    move.w %d3, ST_VY(%a0)
    addq.w #1, %d2
    move.w %d2, ST_SIZE(%a0)
1:  move.w ST_COUNT(%a0), %d3
    move.w %d3, %d4
    addq.w #1, %d4
    andi.w #255, %d4
    move.w %d4, ST_COUNT(%a0)               | the new count in d4, the old in d3
    lsr.w #4, %d3
    andi.w #3, %d3
    move.w %d2, %d5
    lsl.w #2, %d5
    add.w %d3, %d5                          | the frame table's index: size * 4 + the pose of the walk
    moveq #0, %d0
    cmpi.w #3, %d2
    bge.s 2f
    btst #0, %d5
    bne.s 2f
    andi.w #15, %d4
    bne.s 2f
    moveq #INTRO_FOOTSTEP_SFX, %d0          | a foot comes down
2:  moveq #0, %d3
    move.b INTRO_T_FRAME(%a1,%d5.w), %d3
    lea sp_obj(%pc), %a2
    move.w %d3, (%a2)
    move.w ST_X(%a0), %d3
    lsr.w #8, %d3
    move.w %d3, 2(%a2)
    move.w ST_Y(%a0), %d3
    lsr.w #8, %d3
    move.w %d3, 4(%a2)
    cmpi.w #4, %d2
    bne.s 9f
    addq.w #1, ST_STAGE(%a0)                | the smallest: the palette fades, every 8th pass a step, and after 32 the loop ends
    move.w ST_STAGE(%a0), %d3
    andi.w #7, %d3
    bne.s 3f
    addq.w #1, ST_FADES(%a0)
3:  cmpi.w #INTRO_END_STAGE, ST_STAGE(%a0)
    bne.s 9f
    move.w #1, ST_DONE(%a0)
9:  movem.l (%sp)+, %d1-%d5/%a0-%a2
    rts

| ------------------------------------------------------------------------------------------------------------------ the ending
ending_play:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    lea str_outro(%pc), %a0
    move.l #OUTRO_PACKED, %d0
    bsr.w splash_load
    tst.l %d0
    bne.w 99f
    lea sp_phase(%pc), %a0
    move.w #3, (%a0)
    bsr.w sp_scene_setup
    bsr.w sp_state_init
    lea sp_st+ST_SPK(%pc), %a2              | the sparkles' start
    movea.l sp_tables(%pc), %a1
    moveq #0, %d1
5:  moveq #0, %d0
    move.b OUTRO_T_SPARKLE_START(%a1,%d1.w), %d0
    lsl.w #8, %d0
    move.w %d0, (%a2)                       | x
    moveq #0, %d0
    move.b OUTRO_T_SPARKLE_START+2(%a1,%d1.w), %d0
    lsl.w #8, %d0
    move.w %d0, 2(%a2)                      | y
    move.b OUTRO_T_SPARKLE_START+4(%a1,%d1.w), %d0
    ext.w %d0
    move.w %d0, 4(%a2)                      | vx
    move.b OUTRO_T_SPARKLE_START+6(%a1,%d1.w), %d0
    ext.w %d0
    move.w %d0, 6(%a2)                      | vy
    lea 12(%a2), %a2
    addq.w #1, %d1
    cmpi.w #2, %d1
    blt.s 5b
    bsr.w sp_scene_show
    lea sp_late0(%pc), %a0
    move.l late_frames(%pc), (%a0)
    moveq #12, %d0                          | the ending's song
    bsr.w sound_play_music
1:  bsr.w outro_tick
    bsr.w sp_render
    bsr.w present_swap
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 99f
    move.w sp_st+ST_DONE(%pc), %d0
    beq.s 1b
99: movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| One pass of SplashAnimation_RunOutro (`Outro.tick` is the reference): the free-running counter (the waterfall), the hero in loop 1, the two sparkles
| (8 passes a phase, 10 phases, then they start again; shown in the first 3), the waterfall; then the loop changes: 1 to 2 when the hero's y reaches
| $FA, 2 to 3 when the song has ended (the sound player's frames left are 0; without sound after OUTRO_MUSIC_TICKS passes), 3 ends 240 passes later
| (the counter is set to $10 and runs round).
outro_tick:
    movem.l %d0-%d6/%a0-%a3, -(%sp)
    lea sp_st(%pc), %a0
    movea.l sp_tables(%pc), %a1
    lea sp_obj(%pc), %a2
    moveq #-1, %d0
    moveq #5, %d1
1:  move.l %d0, (%a2)+                      | no objects yet
    dbra %d1, 1b
    addq.w #1, ST_N(%a0)
    move.w ST_COUNT(%a0), %d0
    addq.w #1, %d0
    andi.w #255, %d0
    move.w %d0, ST_COUNT(%a0)
    cmpi.w #1, ST_LOOP(%a0)
    bne.w 20f
    move.w ST_VX(%a0), %d1                  | the hero
    add.w %d1, %d1
    add.w %d1, ST_X(%a0)
    move.w ST_VY(%a0), %d1
    add.w %d1, ST_Y(%a0)
    add.w %d1, ST_Y(%a0)
    move.w ST_SIZE(%a0), %d2
    cmpi.w #4, %d2
    bge.s 11f
    move.w ST_Y(%a0), %d1
    lsr.w #8, %d1
    cmp.b OUTRO_T_THRESHOLD(%a1,%d2.w), %d1
    bcs.s 11f                               | not down the road far enough for the next size
    move.b OUTRO_T_VX(%a1,%d2.w), %d3
    ext.w %d3
    move.w %d3, ST_VX(%a0)
    move.b OUTRO_T_VY(%a1,%d2.w), %d3
    ext.w %d3
    move.w %d3, ST_VY(%a0)
    addq.w #1, %d2
    move.w %d2, ST_SIZE(%a0)
11: move.w ST_HCOUNT(%a0), %d3
    move.w %d3, %d4
    addq.w #1, %d4
    andi.w #255, %d4
    move.w %d4, ST_HCOUNT(%a0)
    lsr.w #4, %d3
    andi.w #3, %d3
    lsl.w #2, %d2
    add.w %d3, %d2
    moveq #0, %d3
    move.b OUTRO_T_FRAME(%a1,%d2.w), %d3
    lea sp_obj(%pc), %a2
    move.w %d3, (%a2)
    move.w ST_X(%a0), %d3
    lsr.w #8, %d3
    move.w %d3, 2(%a2)
    move.w ST_Y(%a0), %d3
    lsr.w #8, %d3
    move.w %d3, 4(%a2)
20: lea ST_SPK(%a0), %a3                    | the sparkles move and count
    moveq #0, %d6
21: move.w 4(%a3), %d1
    lsl.w #7, %d1                           | (the velocity byte is in 1/2 pixels a pass)
    add.w %d1, (%a3)
    move.w 6(%a3), %d1
    lsl.w #7, %d1
    add.w %d1, 2(%a3)
    move.w 10(%a3), %d1
    addq.w #1, %d1
    cmpi.w #8, %d1
    bne.s 23f
    addq.w #1, 8(%a3)
    cmpi.w #10, 8(%a3)
    bne.s 22f
    clr.w 8(%a3)                            | the last phase: from the start again
    clr.w 10(%a3)
    moveq #0, %d2
    move.b OUTRO_T_SPARKLE_START(%a1,%d6.w), %d2
    lsl.w #8, %d2
    move.w %d2, (%a3)
    moveq #0, %d2
    move.b OUTRO_T_SPARKLE_START+2(%a1,%d6.w), %d2
    lsl.w #8, %d2
    move.w %d2, 2(%a3)
    move.b OUTRO_T_SPARKLE_START+4(%a1,%d6.w), %d2
    ext.w %d2
    move.w %d2, 4(%a3)
    move.b OUTRO_T_SPARKLE_START+6(%a1,%d6.w), %d2
    ext.w %d2
    move.w %d2, 6(%a3)
    bra.s 24f
22: moveq #0, %d1
23: move.w %d1, 10(%a3)
24: lea 12(%a3), %a3
    addq.w #1, %d6
    cmpi.w #2, %d6
    blt.s 21b
    lea ST_SPK(%a0), %a3                    | the first three phases are shown
    moveq #0, %d6
25: move.w 8(%a3), %d1
    cmpi.w #3, %d1
    bge.s 26f
    move.w %d6, %d2
    lsl.w #2, %d2
    add.w %d1, %d2
    moveq #0, %d3
    move.b OUTRO_T_SPARKLE_FRAME(%a1,%d2.w), %d3
    lea sp_obj+6(%pc), %a2
    move.w %d6, %d2
    mulu.w #6, %d2
    adda.w %d2, %a2
    move.w %d3, (%a2)
    move.w (%a3), %d3
    lsr.w #8, %d3
    move.w %d3, 2(%a2)
    move.w 2(%a3), %d3
    lsr.w #8, %d3
    move.w %d3, 4(%a2)
26: lea 12(%a3), %a3
    addq.w #1, %d6
    cmpi.w #2, %d6
    blt.s 25b
    move.w ST_COUNT(%a0), %d1               | the waterfall: two pictures, swapped every 16 passes
    andi.w #0x10, %d1
    lsr.w #4, %d1
    moveq #0, %d2
    move.b OUTRO_T_WATERFALL(%a1), %d2
    add.w %d1, %d2
    lea sp_obj+18(%pc), %a2
    move.w %d2, (%a2)
    moveq #0, %d2
    move.b OUTRO_T_WATERFALL+1(%a1), %d2
    move.w %d2, 2(%a2)
    moveq #0, %d2
    move.b OUTRO_T_WATERFALL+2(%a1), %d2
    move.w %d2, 4(%a2)
    move.w ST_LOOP(%a0), %d0                | the loops
    cmpi.w #1, %d0
    bne.s 31f
    move.w ST_Y(%a0), %d1
    lsr.w #8, %d1
    cmpi.w #OUTRO_END_Y, %d1
    blt.s 39f
    move.w #2, ST_LOOP(%a0)
    bra.s 39f
31: cmpi.w #2, %d0
    bne.s 32f
    move.w ST_N(%a0), %d1
    move.l snd_state+SND_BIN(%pc), %d0
    bne.s 311f
    cmpi.w #OUTRO_MUSIC_TICKS, %d1          | no sound: the ROM's count
    blt.s 39f
    bra.s 312f
311: cmpi.w #OUTRO_END_Y+SND_MIN_PASSES, %d1 | (the song must have had time to start)
    blt.s 39f
    move.w snd_state+SND_MLEFT(%pc), %d0
    bne.s 39f
312: move.w #3, ST_LOOP(%a0)
    move.w #OUTRO_LOOP3_COUNT, ST_COUNT(%a0)
    move.w ST_N(%a0), ST_L3AT(%a0)
    bra.s 39f
32: tst.w ST_COUNT(%a0)
    bne.s 39f
    move.w #1, ST_DONE(%a0)
39: movem.l (%sp)+, %d0-%d6/%a0-%a3
    rts

    .equ SND_MIN_PASSES, 1                  | (OUTRO_END_Y + 1 = 251 passes: the hero's loop is over by then)

    .even                                   | the variables stay in this section, in front of the data: more data would push the code away from it
sp_base:
    .long 0                                 | where the file is unpacked
sp_pal:
    .long 0                                 | the scene's parts (INTRO_PART_x order): palette, fade palettes, tiles, map, images, poses, tables
sp_fade:
    .long 0
sp_tiles:
    .long 0
sp_map:
    .long 0
sp_images:
    .long 0                                 | (the title: the arrow)
sp_poses:
    .long 0                                 | (the title: the arrow's two places)
sp_tables:
    .long 0
sp_late0:
    .long 0                                 | late_frames when the passes began (the tests look at how many came late)
sp_phase:
    .word 0                                 | 1 title, 2 intro, 3 ending
sp_cursor:
    .word 0                                 | the title's choice
sp_px:
    .word 0                                 | the object being drawn: X, Y
sp_py:
    .word 0
sp_st:
    .space ST_BYTES
sp_obj:
    .space 24                               | hero, sparkle 0, sparkle 1, waterfall: frame, X, Y (the frame is -1 for none, then X and Y are too)
sp_shown:
    .space 48                               | the same for each screen (buf_a, buf_b)
sp_boxes:
    .space 64                               | the four boxes of each screen: x0, x1, y0, y1
sp_box:
    .space 8
sp_bufpass:
    .word -1, -1                            | the pass each screen holds
str_title:
    .asciz "TITLE.DAT"
str_intro:
    .asciz "INTRO.DAT"
str_outro:
    .asciz "OUTRO.DAT"
    .even
    .text
