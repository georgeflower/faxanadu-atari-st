| Viewer: one Faxanadu screen on the ST, made from the ROM's data by tools/build_assets.py.
|
| 320x200, low resolution. The 256-pixel-wide playfield sits in the middle (32 pixels free on each side); the first 32 lines are
| the HUD's (as at the start of a game); below it a window of 168 lines of the 208-line playfield, starting at line CAMERA.
|
| Position independent, like main.s: only PC-relative addressing names our own labels.

    .include "assets.inc"
    .include "iscript.inc"

    | MUSIC=n plays song n (0 none, 1-16 as the NES numbers them) everywhere; without it every package plays its own (PKG_MUSIC).
    .ifndef DAMAGE
    .equ DAMAGE, 8                          | the power an enemy's touch takes (debug keys H and G)
    .endif
    .ifndef WINGS
    .equ WINGS, -1                          | seconds of wing boots left at the start (-1: none)
    .endif
    .ifndef MAGIC
    .equ MAGIC, -1                          | the spell chosen at the start (0 Deluge, 1 Thunder, 2 Fire, 3 Death, 4 Tilte; -1 none); the M key chooses the next
    .endif
    .ifndef TITLE
    .equ TITLE, 0
    .endif
    .ifdef INTRO                            | INTRO=1 or ENDING=1 play the intro or the ending first (splash68.s), so they need the code too
    .ifndef SPLASH
    .equ SPLASH, 1
    .endif
    .endif
    .ifdef ENDING
    .ifndef SPLASH
    .equ SPLASH, 1
    .endif
    .endif
    .ifdef NEWGAME                          | NEWGAME=1 (the disk build): START begins the ROM's new game; it brings the whole game flow (FLOW, src/flow.s)
    .ifndef FLOW
    .equ FLOW, 1
    .endif
    .ifndef SPLASH
    .equ SPLASH, 1
    .endif
    .endif
    .equ END_FREEZE, 1                      | flow.s end_state: the final boss is dead (120 frozen frames), the hero walks to the King, the script's FINISH_GAME was run
    .equ END_WALK, 2
    .equ END_FINISH, 3
    .equ END_WALK_FRAMES, 600               | the walk to the King (about 150 frames in the ROM) times out after these; then 120 more for his message to end it
    .equ END_WALK_GRACE, 120
    .ifndef ITEM
    .equ ITEM, 0xFF                         | the item he holds at the start (a number of the ROM's item list: 7 is the J key; $FF none)
    .endif

    .equ PALETTE, 0xFF8240
    .equ STRIDE, 160
    .equ HUD_LINES, 32
    .equ WINDOW_LINES, 168
    .equ LEFT_BYTES, 16                     | 32 pixels
    .equ SPRITE_IMAGE_BYTES, 40
    .equ DOOR_BYTES, 8
    .equ SCREEN_LINES, 200
    .equ SCREEN_BYTES, 32000
    .equ FLAG_SLOTS, 6                      | screens whose block flags are kept at a time (the one he is on, the ones next to it)
    .if FLAG_SLOTS*416 > PACKAGE_EXPAND
    .error "build_assets.py: PACKAGE_EXPAND is too small for the flags of FLAG_SLOTS screens"
    .endif
    .if TOWN_SPAN > SCREEN_BYTES
    .error "TOWN.DAT no longer fits TOS's screen memory (town_buf): see the memory map in AGENTS.md"
    .endif
    .equ REGION_BYTES, 208*160              | a whole 208-line playfield (stride 160: the same layout as the screen)
    .equ HERO_IMAGES_AT, 64*16              | hero.s: the hero's 64 tiles, then his 256 images
    .equ HERO_RAM_BYTES, HERO_IMAGES_AT+256*SPRITE_IMAGE_BYTES
    .equ NPC_KEYS, NPC_LIST_BYTES           | town.s: a person's slot holds the table and lists of poses (NPC_LIST_BYTES), the keys of the images (a word each), the images (40 bytes each);
    .equ NPC_IMAGES, NPC_KEYS+2*NPC_IMAGE_SLOTS      | the numbers are the biggest of the 18 kinds (tools/iscripts.py equates, in iscript.inc)
    .equ NPC_SLOT_RAM, NPC_IMAGES+SPRITE_IMAGE_BYTES*NPC_IMAGE_SLOTS
    .equ NPC_RAM_BYTES, 2*NPC_SLOT_RAM     | town.s: the pictures of the people of a screen (NPC_SLOTS slots), behind the package room
    .equ BUFFER_BYTES, 2*SCREEN_BYTES+2*REGION_BYTES+HERO_RAM_BYTES+256 | two screens and two playfields, the first on a 256-byte boundary
    .equ HERO_X_MIN, 0                      | where he is at the left edge (he has walked off it): scrolls to the screen on the left
    .equ HERO_X_MAX, 241                    | and at the right edge
    .equ HERO_Y_MIN, 0                      | at the top of the playfield (the game's Player_PosY): scrolls to the screen above
    .equ BUILDING_AREA, 4
    .equ EDGE_BYTES, 5
    .equ DOOR_BUILDING, 2                   | door kinds (build_assets.py): 0 same package, 1 other palette set, 2 into a building, 3 out to another area
    .equ HERO_Y_MAX, 192                    | and at the bottom ($C1 and more: the screen below; the demo stops at $C0)
    .equ CAMERA_UP, 56                      | the camera is 0 while the hero's y is below this (he is at the top)
    .equ CAMERA_DOWN, 120                   | and 40 while it is above this; in between it stays
    .equ CAMERA_MAX, 40
    .equ VIDEO_BASE_HI, 0xFFFF8201
    .equ VIDEO_BASE_MID, 0xFFFF8203

    .text
    .globl _start
    .section .text.boot,"ax"
_start:
game_start:
    bra.w start

    .section .data
saved_palette:
    .space 32
old_ssp:
    .long 0
hide_cursor:
    .asciz "\033f"
show_cursor:
    .asciz "\033e"
loading_text:
    .asciz "LOADING"
no_memory:
    .asciz "\r\nNot enough memory: this program needs more than a 520 STFM has free.\r\nPress a key.\r\n"
no_package:
    .asciz "\r\nThe package file (A<area>P<palette>.DAT) is not next to the program.\r\nPress a key.\r\n"
    .even

    .text
start:
    movea.l 4(%sp), %a3
    lea game_start(%pc), %sp                | the stack is the last thing in the image, out of the way of the displacements (link.ld)
    adda.l #stack_end, %sp

    move.l #image_size, %d0
    addi.l #0x100+BUFFER_BYTES+PACKAGE_SPAN+NPC_RAM_BYTES, %d0 | the image, the basepage and room behind the image for the screens and the package in use with its flag tables (the packed file is read to the end of that room); TOWN.DAT lies in TOS's own screen (town_buf)
    move.l 4(%a3), %d1                      | p_hitpa: the end of the memory the program was given
    sub.l %a3, %d1
    cmp.l %d0, %d1
    bcc.s 20f
    pea no_memory(%pc)                      | not enough memory: say so and leave (Mshrink would not tell)
    move.w #9, -(%sp)
    trap #1                                 | Cconws
    addq.l #6, %sp
    move.w #8, -(%sp)
    trap #1                                 | Cnecin
    clr.w -(%sp)
    trap #1                                 | Pterm0
20: move.l %d0, -(%sp)
    move.l %a3, -(%sp)
    clr.w -(%sp)
    move.w #0x4A, -(%sp)
    trap #1                                 | Mshrink
    lea 12(%sp), %sp
.ifdef JUNK
    movea.l %a3, %a0                        | JUNK (test only): TOS 1.02 does not clear the memory behind the image
    adda.l #0x100+image_size, %a0
    movea.l 4(%a3), %a1
    move.l #JUNK, %d0
9:  move.l %d0, (%a0)+
    cmpa.l %a1, %a0
    bcs.s 9b
.endif

    clr.l -(%sp)
    move.w #32, -(%sp)
    trap #1                                 | Super(0)
    addq.l #6, %sp
    lea old_ssp(%pc), %a0
    move.l %d0, (%a0)
    lea game_start(%pc), %sp                | the stack is the last thing in the image, out of the way of the displacements (link.ld)
    adda.l #stack_end, %sp

    clr.w -(%sp)
    move.l #-1, -(%sp)
    move.l #-1, -(%sp)
    move.w #5, -(%sp)
    trap #14                                | Setscreen: low resolution
    lea 12(%sp), %sp

    pea hide_cursor(%pc)
    move.w #9, -(%sp)
    trap #1
    addq.l #6, %sp

    move.w #2, -(%sp)
    trap #14                                | Physbase
    addq.l #2, %sp
    lea orig_screen(%pc), %a0
    move.l %d0, (%a0)
    move.l %a3, %d0                         | the basepage; the image follows it, the screens follow the image
    addi.l #0x100+image_size+255, %d0
    andi.l #-256, %d0
    lea buf_a(%pc), %a0
    move.l %d0, (%a0)+                      | buf_a
    addi.l #SCREEN_BYTES, %d0
    move.l %d0, (%a0)+                      | buf_b
    addi.l #SCREEN_BYTES, %d0
    move.l %d0, (%a0)+                      | pf_ptr: the playfield (208 lines) of the screen, without sprites
    addi.l #REGION_BYTES, %d0
    move.l %d0, (%a0)                       | next_ptr: the playfield of the screen scrolled to
    addi.l #REGION_BYTES, %d0
    lea hero_ram(%pc), %a0
    move.l %d0, (%a0)                       | the hero's tiles and images (hero.s)
    addi.l #HERO_RAM_BYTES, %d0
    lea game_start(%pc), %a0
    adda.l #hero_equip, %a0
    lea hero_blob(%pc), %a1
    move.l %a0, (%a1)
    lea pkg_buf(%pc), %a0
    move.l %d0, (%a0)                       | where a package from disk is loaded
    addi.l #PACKAGE_SPAN, %d0
    lea npc_buf(%pc), %a0
    move.l %d0, (%a0)                       | and behind its room the pictures of the people of a screen (town.s)
    lea town_buf(%pc), %a0
    move.l orig_screen(%pc), (%a0)          | TOWN.DAT (town.s) lies in TOS's own screen memory, which nothing uses once the program shows its own screens: 32 KB the program need not have
    movea.l buf_a(%pc), %a4

    movea.l #PALETTE, %a2                   | keep TOS's palette, set the screen's
    lea saved_palette(%pc), %a1
    moveq #15, %d1
1:  move.w (%a2)+, (%a1)+
    dbra %d1, 1b
    moveq #PACKAGE_AREA, %d0                | the first package is read from the disk like the others (its LOADING word is drawn on TOS's screen, which TOWN.DAT then takes)
    moveq #PACKAGE_PALETTE, %d1
    bsr.w load_package
    bsr.w town_load                         | the scripts, messages and people (TOWN.DAT, once)
    move.l pkg_result(%pc), %d0
    bpl.s 5f
    pea no_package(%pc)
    move.w #9, -(%sp)
    trap #1                                 | Cconws
    addq.l #6, %sp
    move.w #8, -(%sp)
    trap #1                                 | Cnecin: a key press
    addq.l #2, %sp
    bra.w viewer_quit
5:  movea.l #PALETTE, %a2
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a1
    moveq #15, %d1
2:  move.w (%a1)+, (%a2)+
    dbra %d1, 2b

    | Clear the screen (32,000 bytes) and the two playfields (their margins are never drawn), then draw.
    movea.l %a4, %a0
    move.w #7999, %d1
3:  clr.l (%a0)+
    dbra %d1, 3b
    movea.l pf_ptr(%pc), %a0
    move.w #(2*REGION_BYTES/4)-1, %d1
13: clr.l (%a0)+
    dbra %d1, 13b

    movea.l pkg_ptr+PKG_SCREENS(%pc), %a5               | the start screen's block ids
    adda.l #START_SCREEN*208, %a5
    move.l %a4, -(%sp)
    movea.l pf_ptr(%pc), %a4
    bsr.w draw_playfield                    | into the playfield buffer ...
    movea.l (%sp)+, %a4
    bsr.w set_view
    moveq #0, %d0
    bsr.w copy_window_half                  | ... and its window into the first screen
    moveq #1, %d0
    bsr.w copy_window_half

    | The HUD: first the state of the start screen, then the second state (to see that an update clears what was there).
    lea hud_states(%pc), %a0
    bsr.w hud_load_state
    bsr.w hud_update
    lea hud_states+10(%pc), %a0
    bsr.w hud_load_state
    bsr.w hud_update

    | Both screens get the same picture (without sprites).
    movea.l %a4, %a0
    movea.l buf_b(%pc), %a1
    bsr.w copy_screen
    bsr.w hud_copy_shown

    .ifdef BENCH
    | Time the hero: draw it BENCH times over itself and count the VBLs that took (frame_init starts the counter at 0).
    movea.l pkg_ptr+PKG_HERO_LIST(%pc), %a5
    movea.l pkg_ptr+PKG_HERO_IMAGES(%pc), %a3
    bsr.w frame_init
    move.w #BENCH-1, %d6
15: movem.l %d6, -(%sp)
    movea.l pkg_ptr+PKG_HERO_LIST(%pc), %a5
    bsr.w draw_sprites
    movem.l (%sp)+, %d6
    dbra %d6, 15b
    lea frame_count(%pc), %a0
    lea bench_result(%pc), %a1
    move.l (%a0), (%a1)
    bsr.w frame_exit
    .endif

    | The frame loop. a4 is the screen drawn into; the other one is on show. One pass a VBL until Esc: erase what was drawn in this
    | screen two frames ago (copy back from the background), move the hero, draw him, wait for the VBL, show this screen.
    movea.l buf_a(%pc), %a0
    bsr.w show_screen                       | the picture without the hero
    movea.l buf_b(%pc), %a4
    lea game_start(%pc), %a0                | the songs are the last in the image (link.ld), and behind them the room for the one that plays
    lea game_start(%pc), %a1
    adda.l #sound_start, %a0
    adda.l #sound_song, %a1
    bsr.w sound_init
    .ifdef MUSIC
    moveq #MUSIC, %d0
    .else
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0      | the area's song (7 is Eolis's); the F keys and the digit keys try the others (sound.s)
    .endif
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    bsr.w hero_sync                         | the hero's images are made before the frame counter starts
    bsr.w frame_init
    bsr.w enemies_load
    .ifdef SPLASH
    .ifndef NO_TITLE                        | (tests: NO_TITLE=1 has the code but starts in the game)
    bsr.w splash_start                      | the title, the intro, CONTINUE (src/splash68.s)
    .endif
    .else
    .ifdef MENU
    bsr.w start_menu                        | start the game, or enter a mantra
    .endif
    .endif
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.w viewer_leave                      | Esc on the title (or in the intro): the program ends, as it always did
12: bsr.w input_poll
    bsr.w esc_key                           | Esc: the menu (Save, Continue, Exit to GEMDOS; src/save.s)
    .ifdef FLOW
    bsr.w flow_tick                         | the ending's walk, boss rooms, the final boss (src/flow.s)
    .endif
    .ifndef NEWGAME                         | the test keys (F keys, digits, Backspace: songs and sounds; P: the mantra; H, G: hurt; M: the next spell) are not in the disk build
    bsr.w sound_keys
    bsr.w mantra_key                        | P: shows the mantra
    .endif
    .ifdef SCRIPT
    bsr.w script_test                       | (tests) runs the script SCRIPT once
    .endif
    bsr.w menu_key                          | Tab (Select): the player menu
    bsr.w hero_step
    .ifndef NO_PHYSICS
    bsr.w use_item                          | Down and B: the item he holds is used
    .endif
    bsr.w scroll_check                      | at the edge of the screen: scrolls to the next one (and comes back when it is done)
    .ifndef NO_PHYSICS
    bsr.w door_check                        | up in front of a door: the screen on the other side
    .ifdef NPCS
    bsr.w npc_check                         | Up in front of a person, or a touch trigger: its script (src/town.s); after the door: a person who walks by does not keep him out
    .endif
    .endif
    bsr.w camera_follow                     | the window of the playfield follows him up and down
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0                         | this screen's slot: where the hero and the spell were drawn in it
    bsr.w restore_rect
    lea 8(%a0), %a0
    bsr.w restore_rect
    clr.l (%a0)+                            | (the spell's box: nothing, until it is drawn)
    clr.l (%a0)
    .ifndef NO_PHYSICS
    bsr.w enemies_erase
    .ifdef NPCS
    bsr.w npc_erase
    .endif
    lea hero_dead(%pc), %a0                 | Player_HandleDeath is a loop of its own in the ROM: the sprites are cleared, nothing moves and nothing touches him until the death is over
    tst.w (%a0)
    bne.s 13f                               | (an enemy on him would start the death again and again)
    bsr.w enemies_update
    bsr.w items_tick
13: bsr.w draw_spell
    .ifdef NPCS
    bsr.w npc_draw                          | the people of the screen (src/town.s), under the enemies and the hero
    .endif
    lea hero_dead(%pc), %a0
    tst.w (%a0)
    bne.s 14f
    bsr.w draw_enemies
14:
    .endif
    bsr.w draw_hero
    bsr.w present_swap
    bra.w 12b                               | (Esc is seen at the top: esc_key)
viewer_leave:                               | (also the way out of flow_fade_out: Esc in the middle of a door's fade, and of the Esc menu's Exit to GEMDOS)
    bsr.w frame_exit
viewer_quit:
    movea.l orig_screen(%pc), %a0
    bsr.w show_screen                       | TOS's screen again

    movea.l #PALETTE, %a2
    lea saved_palette(%pc), %a1
    moveq #15, %d1
6:  move.w (%a1)+, (%a2)+
    dbra %d1, 6b
    pea show_cursor(%pc)
    move.w #9, -(%sp)
    trap #1
    addq.l #6, %sp
    move.l old_ssp(%pc), -(%sp)
    move.w #32, -(%sp)
    trap #1
    addq.l #6, %sp
    clr.w -(%sp)
    trap #1

| One 8x8 sprite tile over the picture. In: d0 = x, d1 = line (signed), a1 = image (8 lines of mask and four plane bytes), a4 = screen.
| The tile is cut at the top of the window (under the HUD) and at the bottom of the screen. Keeps a3, a5, a4; clobbers d0-d7, a0-a2.
.macro PLANE off
    moveq #0, %d3
    move.b (%a1)+, %d3
    ror.l #8, %d3
    lsr.l %d0, %d3                          | the plane byte at its pixel position: high word the first group, low word the next
    move.w %d3, %d4
    swap %d3
    move.w \off(%a0), %d5
    and.w %d2, %d5
    or.w %d3, %d5
    move.w %d5, \off(%a0)
    move.w \off+8(%a0), %d5
    and.w %d6, %d5
    or.w %d4, %d5
    move.w %d5, \off+8(%a0)
.endm

blit_tile:
    cmpi.w #LEFT_BYTES*2, %d0               | a tile that starts outside the playfield (x 32 to 287) is not drawn, as the game skips cells that
    blt.w 9f                                | do not fit a byte; one that starts inside and reaches into the right margin is cut by clear_margins
    cmpi.w #288, %d0
    bge.w 9f
    moveq #8, %d7                           | lines to draw
    cmpi.w #HUD_LINES, %d1
    bge.s 1f
    move.w #HUD_LINES, %d2
    sub.w %d1, %d2                          | lines above the window
    sub.w %d2, %d7
    ble.w 9f
    move.w %d2, %d3
    lsl.w #2, %d3
    add.w %d2, %d3                          | * 5 bytes a line
    adda.w %d3, %a1
    move.w #HUD_LINES, %d1
1:  move.w #SCREEN_LINES, %d2
    sub.w %d1, %d2                          | lines left to the bottom of the screen
    ble.w 9f
    cmp.w %d2, %d7
    ble.s 2f
    move.w %d2, %d7
2:  subq.w #1, %d7
    mulu.w #STRIDE, %d1
    movea.l %a4, %a0
    adda.l %d1, %a0
    move.w %d0, %d1
    lsr.w #4, %d1
    lsl.w #3, %d1                           | 8 bytes a 16-pixel group
    adda.w %d1, %a0
    andi.w #15, %d0                         | the shift inside the group
    cmpi.w #8, %d0
    bgt.s 3f
    | The tile (8 pixels) fits in one group: a single word a plane.
    moveq #8, %d6
    sub.w %d0, %d6                          | shift left by 8 - x
.macro PLANE1 off
    moveq #0, %d3
    move.b (%a1)+, %d3
    lsl.w %d6, %d3
    move.w \off(%a0), %d5
    and.w %d2, %d5
    or.w %d3, %d5
    move.w %d5, \off(%a0)
.endm
4:  moveq #0, %d2
    move.b (%a1)+, %d2
    lsl.w %d6, %d2
    not.w %d2
    PLANE1 0
    PLANE1 2
    PLANE1 4
    PLANE1 6
    lea STRIDE(%a0), %a0
    dbra %d7, 4b
    rts
3:  moveq #0, %d2
    move.b (%a1)+, %d2
    ror.l #8, %d2
    lsr.l %d0, %d2                          | the mask, shifted
    not.l %d2
    move.w %d2, %d6                         | what to keep in the next group
    swap %d2                                | and in the first
    PLANE 0
    PLANE 2
    PLANE 4
    PLANE 6
    lea STRIDE(%a0), %a0
    dbra %d7, 3b
9:  rts

| Draws a sprite list: a5 = list (x, line, image number for each tile, ended by -1), a3 = images, a4 = screen.
draw_sprites:
10: move.w (%a5)+, %d0                      | x on the screen
    bmi.s 11f
    move.w (%a5)+, %d1                      | line (may be above or below the window)
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile
    bra.s 10b
11: rts

| a0 = a screen (256-byte aligned): the shifter shows it from the next frame.
show_screen:
    move.l %a0, %d0
    lsr.l #8, %d0
    move.b %d0, VIDEO_BASE_MID
    lsr.l #8, %d0
    move.b %d0, VIDEO_BASE_HI
    rts

| a0 = source, a1 = destination: 32,000 bytes.
copy_screen:
    move.w #(SCREEN_BYTES/16)-1, %d0
1:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    dbra %d0, 1b
    rts

| Puts back the background where a rectangle was drawn. a0 = the rectangle: x0, x1, y0, y1 as words (ST pixels, the end exclusive),
| a4 = the screen. Whole 16-pixel groups are copied; what is outside the screen's window (the HUD, below the last line) is not.
restore_rect:
    movem.l %d0-%d5/%a0-%a1, -(%sp)
    movem.w (%a0), %d0-%d3                  | x0, x1, y0, y1
    tst.w %d0
    bpl.s 1f
    moveq #0, %d0
1:  cmpi.w #320, %d1
    ble.s 2f
    move.w #320, %d1
2:  cmpi.w #HUD_LINES, %d2
    bge.s 3f
    move.w #HUD_LINES, %d2
3:  cmpi.w #SCREEN_LINES, %d3
    ble.s 4f
    move.w #SCREEN_LINES, %d3
4:  cmp.w %d0, %d1
    ble.s 9f
    sub.w %d2, %d3                          | lines
    ble.s 9f
    subq.w #1, %d3
    subq.w #1, %d1
    lsr.w #4, %d1                           | last group
    lsr.w #4, %d0                           | first group
    sub.w %d0, %d1                          | groups - 1
    move.w %d1, %d4
    addq.w #1, %d4
    lsl.w #3, %d4
    move.w #STRIDE, %d5
    sub.w %d4, %d5                          | what to add to get to the next line
    lsl.w #3, %d0
    mulu.w #STRIDE, %d2
    add.l %d0, %d2                          | offset of the first group of the first line
    lea (%a4,%d2.l), %a1
    movea.l pf_ptr(%pc), %a0
    adda.l %d2, %a0
    move.w camera(%pc), %d4                 | the screen's line y is the playfield's line y - 32 + camera
    subi.w #HUD_LINES, %d4
    muls.w #STRIDE, %d4
    adda.l %d4, %a0
5:  move.w %d1, %d0
6:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    dbra %d0, 6b
    adda.w %d5, %a0
    adda.w %d5, %a1
    dbra %d3, 5b
9:  movem.l (%sp)+, %d0-%d5/%a0-%a1
    rts

| The pad moves the hero (a demonstration, not the game's physics): two pixels a frame, the walk frame changes every six frames.
| The hero's walking as the ROM does it (tools/hero_physics.py is the reference, tests/test_hero_physics.py checks it against the game):
| x in 8.8 fixed point (hero_x and hero_frac), an acceleration (hero_acc) that starts at $C0 when he starts walking and grows by 2 a frame
| to $180 (rank group 0; 4, 6, 8 for the higher ranks: not here yet), a wall stops him on a block edge. Up and down are still the demo's.
| Fields at hero_x: x 0, y 2, flip 4, frame 6, tick 8, frac 10, acc 12, moving 14, jump 16, air 18 (the ROM's Player_Flags bits: 1 jumping,
| 2 holding to climb, 4 falling, 8 can climb, $10 climbing), climb 20, mtick 22, atk 24, atk timer 26, atk phase 28.
hero_step:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    lea step_clock(%pc), %a0
    addq.w #1, (%a0)
    lea input_state(%pc), %a0
    move.b IN_PAD(%a0), %d0
    moveq #0, %d4
    move.b %d0, %d4                         | the pad, kept (d0 becomes the horizontal choice)
    lea hero_x(%pc), %a1
    .ifndef NO_PHYSICS
    move.w hero_dead(%pc), %d1
    bne.w 70f
    .ifndef NEWGAME
    bsr.w hurt_keys
    .endif
    .endif
    moveq #0, %d2                           | 1 when he moves
    | The ROM's ladders, jump, fall and landing. (The picture tests, NO_PHYSICS: up or down held moves him 2 pixels, nothing else.)
    .ifdef NO_PHYSICS
    btst #3, %d0
    bne.s 50f
    btst #2, %d0
    bne.s 50f
    .endif
    .ifndef NO_PHYSICS
    bsr.w hero_attack
    .endif
    bsr.w hero_vertical
    bra.s 51f
50: clr.w 16(%a1)
    clr.w 18(%a1)
51: move.w %d4, %d0                         | (the pad again, and no move yet: hero_vertical used d0 and d2)
    moveq #0, %d2
    tst.w 38(%a1)
    beq.s 56f
    clr.w 18(%a1)                           | knocked back (Player_HandleKnockback): one move away from the enemy, 8 pixels; every flag but the
    move.w 4(%a1), -(%sp)                   | facing is gone (the jump and the attack end), the facing comes back after the move (hero_step 40)
    moveq #2, %d0
    tst.w 4(%a1)
    bne.s 54f
    moveq #1, %d0
    bra.s 54f
56: tst.w 36(%a1)
    bpl.s 57f                               | wing boots on: he steers in the air as on the ground
    move.w 18(%a1), %d1                     | in the air (jumping or falling) he cannot turn: he goes on the way he went
    andi.w #5, %d1
    beq.s 52f
    moveq #0, %d0
    tst.w 14(%a1)
    beq.s 52f
    moveq #2, %d0
    tst.w 4(%a1)
    beq.s 52f
    moveq #1, %d0
52: move.w 18(%a1), %d1                     | on the ground: walking counts the movement tick; up or down beside a ladder steps him to it
    andi.w #5, %d1
    bne.s 54f
57: btst #7, 19(%a1)                        | attacking on the ground: he stands still
    bne.s 55f
    move.w %d0, %d1
    andi.w #3, %d1
    beq.s 53f
    addq.w #1, 22(%a1)
    bra.s 54f
53: andi.w #0x0C, %d0
    beq.s 55f
    btst #3, 19(%a1)
    beq.s 55f
    move.w (%a1), %d1
    andi.w #15, %d1
    beq.s 55f
    addq.w #1, 22(%a1)
    moveq #2, %d0                           | left when x & 15 < 8, else right
    cmpi.w #8, %d1
    bcs.s 54f
    moveq #1, %d0
    bra.s 54f
55: moveq #0, %d0
54:
    btst #0, %d0                            | right
    bne.s 20f
    btst #1, %d0                            | left
    bne.s 30f
    clr.w 14(%a1)                           | not walking: the next step starts from $C0 again
    bra.w 40f
20: moveq #1, %d2
    bsr.w hero_accelerate
    move.w #1, 4(%a1)                       | facing right: flipped
    move.w (%a1), %d1
    lsl.w #8, %d1
    move.w 10(%a1), %d3
    or.w %d3, %d1
    add.w 12(%a1), %d1
    move.w %d1, %d3
    andi.w #0xFF, %d3
    move.w %d3, 10(%a1)
    lsr.w #8, %d1
    move.w %d1, (%a1)
    cmpi.w #240, %d1                        | the pixel 16 to the right lies on this screen
    blt.s 21f
    moveq #1, %d1                           | no: the next screen's first column
    bsr.w edge_blocked
    bra.s 22f
21: addi.w #16, %d1
    bsr.w column_blocked
22: beq.w 40f
    andi.w #0xF0, (%a1)                     | a wall: he stops on the block's edge
    bra.w 40f
30: moveq #1, %d2
    lea hero_wall(%pc), %a2
    clr.w (%a2)                             | (a wall in the next screen's last column sets it again)
    lea hero_off(%pc), %a2
    clr.w (%a2)
    bsr.w hero_accelerate
    clr.w 4(%a1)                            | facing left: the flip bit is clear
    move.w (%a1), %d1
    lsl.w #8, %d1
    move.w 10(%a1), %d3
    or.w %d3, %d1
    sub.w 12(%a1), %d1
    bcc.s 31f
    move.w %d1, %d3                         | off the left edge: x is 0 (scroll_check sees it)
    andi.w #0xFF, %d3
    move.w %d3, 10(%a1)
    clr.w (%a1)
    lea hero_off(%pc), %a2
    move.w #1, (%a2)                        | (the ROM scrolls on this step, not when x reaches 0)
    bra.w 32f
31: move.w %d1, %d3
    andi.w #0xFF, %d3
    move.w %d3, 10(%a1)
    lsr.w #8, %d1
    move.w %d1, (%a1)
    beq.w 32f
    subq.w #1, %d1                          | the pixel to the left
    bsr.w column_blocked
    beq.w 40f
    move.w (%a1), %d1
    move.w %d1, %d3
    andi.w #15, %d3
    beq.w 40f
    andi.w #0xF0, %d1                       | a wall: the next block edge to the right
    addi.w #16, %d1
    move.w %d1, (%a1)
    bra.w 40f
32: moveq #0, %d1                           | at x 0: the last column of the screen to the left
    bsr.w edge_blocked
    beq.w 40f
    lea hero_wall(%pc), %a2
    move.w #1, (%a2)                        | blocked: he stays, scroll_check does not scroll
40: tst.w 38(%a1)
    beq.s 41f
    move.w (%sp)+, 4(%a1)                   | knockback: the facing as it was
41: .ifdef NO_PHYSICS
    btst #3, %d4                            | up (the demo's)
    beq.s 43f
    subq.w #2, 2(%a1)
    moveq #1, %d2
43: btst #2, %d4                            | down
    beq.s 44f
    addq.w #2, 2(%a1)
    moveq #1, %d2
    .endif
44: bsr.w hero_iframes
    tst.w %d2                               | the limits only apply to a hero who moves (the start position may lie outside)
    beq.s 8f
    cmpi.w #HERO_Y_MIN, 2(%a1)
    bge.s 7f
    move.w #HERO_Y_MIN, 2(%a1)
7:  cmpi.w #HERO_Y_MAX, 2(%a1)
    ble.s 8f
    move.w #HERO_Y_MAX, 2(%a1)
8:  tst.w %d2
    bne.s 9f
    cmpi.w #-1, 8(%a1)                      | standing (tick -1): the start pose stays until he has moved
    beq.s 10f
    clr.w 6(%a1)                            | stopped: frame 0
    move.w #-1, 8(%a1)
    bra.s 10f
9:  addq.w #1, 8(%a1)
    bne.s 11f
    clr.w 8(%a1)                            | the first step: tick 0
11: cmpi.w #6, 8(%a1)
    blt.s 10f
    clr.w 8(%a1)
    addq.w #1, 6(%a1)
    cmpi.w #3, 6(%a1)
    blt.s 10f
    clr.w 6(%a1)
10: .ifndef NO_PHYSICS
    bsr.w hero_pose
    bsr.w magic_update
    .endif
    bsr.w weapon_update
    movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts
70: bsr.w death_step                        | dead: no input, no moves; the death goes on
    moveq #0, %d4
    bra.s 10b

| Player_HandleIFrames: the invincibility phase (hero_invinc, $3C when he is hit) counts down; the knockback lasts until it has reached $39.
| a1 = hero_x. Clobbers d0.
hero_iframes:
    move.w 40(%a1), %d0
    bne.s 1f
    clr.w 38(%a1)
    rts
1:  subq.w #1, %d0
    move.w %d0, 40(%a1)
    cmpi.w #0x39, %d0
    bhi.s 2f
    bne.s 3f
    move.w #0xC0, 12(%a1)                   | at $39 the speed is reset
3:  clr.w 38(%a1)
    rts
2:  move.w #0xC0, 12(%a1)
    rts

    .ifndef NEWGAME                         | a test key: not in the disk build
| Debug keys for the damage, until there are enemies: H = something hits him from the right (he turns to it and is knocked back to the left), G from
| the left. Player_HandleTouchEnemy: nothing happens during the 60 frames of invincibility; else he loses DAMAGE power and the HUD is told.
| a1 = hero_x. Clobbers nothing.
hurt_keys:
    movem.l %d0-%d1/%a0, -(%sp)
    lea input_state+IN_KEYS+0x23(%pc), %a0  | H
    moveq #1, %d1                           | he will face right
    tst.b (%a0)
    bne.s 1f
    lea input_state+IN_KEYS+0x22(%pc), %a0  | G
    moveq #0, %d1
    tst.b (%a0)
    beq.s 9f
1:  tst.w 40(%a1)
    bne.s 9f                                | invincible
    move.w #0x3C, 40(%a1)                   | Player_SetDamagedBySprite: 60 frames, facing the enemy, knocked back
    move.w %d1, 4(%a1)
    move.w #1, 38(%a1)
    lea hud_state(%pc), %a0                 | Player_ReduceHP
    moveq #0, %d0
    move.b (%a0), %d0
    subi.w #DAMAGE, %d0
    bpl.s 2f
    moveq #0, %d0
2:  move.b %d0, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    tst.w %d0
    bne.s 9f
    btst #3, inv+INV_SPECIAL(%pc)           | no power left: the Elixir, or dead
    beq.s 3f
    bsr.w use_elixir
    bra.s 9f
3:  bsr.w death_start
9:  movem.l (%sp)+, %d0-%d1/%a0
    rts
    .endif

| Player_ReduceHP found no power left: Player_HandleDeath starts. Every flag but the facing, the status and the invincibility are cleared, the music
| stops. a1 = hero_x. Clobbers nothing.
death_start:
    movem.l %d0/%a0, -(%sp)
    lea hero_dead(%pc), %a0
    move.w #1, (%a0)
    bsr.w spell_clear
    lea death_state(%pc), %a0
    clr.w (%a0)                             | the pass of the death loop
    move.w #0xFF, 2(%a0)                    | Player_DeathAnimationPhase $FF: not started
    move.w #-1, 4(%a0)                      | Player_DeathAnimationCounter $FF
    clr.w 6(%a0)                            | Screen_FadeOutCounter
    move.w #4, 8(%a0)                       | Screen_FadeOutStage 4: no fade yet
    clr.w 10(%a0)
    clr.w 18(%a1)
    clr.w 14(%a1)
    clr.w 22(%a1)
    clr.w 38(%a1)
    clr.w 40(%a1)
    move.w #-1, 36(%a1)
    moveq #0, %d0
    bsr.w sound_play_music
    moveq #0x16, %d0                        | the death sound effect
    bsr.w sound_play_sfx
    movem.l (%sp)+, %d0/%a0
    rts

| Player_HandleDeath's loop, a pass a frame (256 of them): he stands for 16, then dissolves in 8 phases of 8 tiles (Player_DrawDeathAnimation; the
| picture is made by dissolve_image), from pass 80 the screen fades to black in four steps (Screen_NextTransitionState), and at the end he is
| the screen is shown again and the death song plays, the ROM's message "Remember your mantra" is on a box until a button is pressed (A, B or Start),
| and then he is back at the start with all his power and magic, and the gold and experience of his rank.
| a1 = hero_x. Clobbers nothing.
death_step:
    movem.l %d0-%d3/%a0, -(%sp)
    lea input_state(%pc), %a0
    clr.b IN_PAD(%a0)
    clr.b IN_PAD_NEW(%a0)
    lea death_state(%pc), %a0
    move.w (%a0), %d0
    cmpi.w #80, %d0
    bcs.s 3f
    bne.s 2f
    clr.w 8(%a0)                            | pass 80: the fade begins
    bra.s 3f
2:  move.w 8(%a0), %d1
    cmpi.w #4, %d1
    bcc.s 3f
    addi.w #50, 6(%a0)
    cmpi.w #256, 6(%a0)
    bcs.s 3f
    subi.w #256, 6(%a0)
    addq.w #1, %d1
    move.w %d1, 8(%a0)
    bsr.w death_fade
3:  move.w 2(%a0), %d1
    cmpi.w #8, %d1
    bcc.s 6f
    move.w 4(%a0), %d2
    bpl.s 4f
    move.w %d0, %d3
    andi.w #3, %d3
    bne.s 6f
    moveq #0, %d2
4:  addq.w #1, %d2                          | the tile (d2 before this) is dissolved in this phase: dissolve_image reads the counts
    move.w %d2, 4(%a0)
    cmpi.w #8, %d2
    bcs.s 6f
    move.w #-1, 4(%a0)
    addq.w #1, 2(%a0)
6:  cmpi.w #0xFF, 2(%a0)
    bne.s 7f
    cmpi.w #16, %d0
    bcs.s 7f
    clr.w 2(%a0)
    clr.w 4(%a0)
7:  addq.w #1, %d0
    move.w %d0, (%a0)
    cmpi.w #256, %d0
    bne.s 9f
    lea hero_dead(%pc), %a0                 | the message: the palette comes back, the death song plays, the ROM's words in a box until a button
    move.w #2, (%a0)
    moveq #0, %d1
    bsr.w death_fade
    moveq #8, %d0
    bsr.w sound_play_music
    lea text_data+TEXT_DEATH(%pc), %a0
    bsr.w message_box
    bsr.w hero_respawn
9:  movem.l (%sp)+, %d0-%d3/%a0
    rts

| The screen's colours a quarter darker each step: d1 = the step (1 to 4; 4 is black).
death_fade:
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a0
    movea.l #PALETTE, %a1
    moveq #4, %d4
    sub.w %d1, %d4                          | the brightness in quarters
    moveq #15, %d3
1:  move.w (%a0)+, %d0
    move.w %d0, %d1
    andi.w #15, %d1
    mulu.w %d4, %d1
    lsr.w #2, %d1                           | blue
    move.w %d0, %d2
    lsr.w #4, %d2
    andi.w #15, %d2
    mulu.w %d4, %d2
    lsr.w #2, %d2
    lsl.w #4, %d2
    or.w %d2, %d1                           | green
    lsr.w #8, %d0
    andi.w #15, %d0
    mulu.w %d4, %d0
    lsr.w #2, %d0
    lsl.w #8, %d0
    or.w %d0, %d1                           | red
    move.w %d1, (%a1)+
    dbra %d3, 1b
    movem.l (%sp)+, %d0-%d4/%a0-%a1
    rts

| The start again (Player_SetInitialExpAndGold, Game_InitStateForSpawn, Player_Spawn): the gold and experience his rank starts with, full power
| and magic, the start screen of the start package, the start position, the song. (The ROM puts him in the temple of the last town he was in.)
hero_respawn:
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    lea hero_dead(%pc), %a0
    clr.w (%a0)
    moveq #0, %d0
    bsr.w sound_play_music                  | the death song ends
    lea hud_state(%pc), %a0
    clr.b hero_hpl-hud_state(%a0)
    move.b #80, (%a0)+                      | Player_Spawn: power and magic 80
    move.b #80, (%a0)+
    moveq #0, %d1                           | a Novice has none
    moveq #0, %d2
    move.w hero_title(%pc), %d0
    beq.s 1f
    subq.w #1, %d0
    add.w %d0, %d0
    lea title_table(%pc), %a1
    move.w (%a1,%d0.w), %d1                 | the experience the rank takes
    move.w 30(%a1,%d0.w), %d2               | the gold it starts with
1:  move.w %d1, (%a0)+
    clr.w (%a0)+
    move.w %d2, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    lea hero_next(%pc), %a0                 | Player_SetInitialExpAndGold: the rank earned is the rank he has
    move.w hero_title(%pc), (%a0)
    bsr.w timers_clear                      | Game_ClearTimedItems: wing boots, hour glass, glove and ointment are lost; the mattock quest bit too
    .ifdef FLOW
    bsr.w temple_enter                      | Game_SpawnInTemple: inside the temple of the last Guru he met (src/flow.s)
    movem.l (%sp)+, %d0-%d3/%a0-%a1
    rts
    .else
    lea hero_flip(%pc), %a0
    move.w #HERO_FLIP, (%a0)
    move.w #START_SCREEN, %d0
    move.w #(HERO_Y&0xF0)+(HERO_X/16), %d1
    moveq #PACKAGE_AREA, %d2
    moveq #PACKAGE_PALETTE, %d3
    bsr.w enter_world
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    movem.l (%sp)+, %d0-%d3/%a0-%a1
    rts
    .endif

| The dissolved hero: a1 = the image of the next tile of the hero (the 8 mask bytes, then the 8 lines' four plane bytes, as enemy_data.column_image); on return a1 is a copy with the pixels
| gone that Player_DrawDeathAnimation has removed so far: in each phase q a pixel a line, the one PPUBUFFER_DRAWCOMMAND_REMOVE_VERT_LINES_MASKS[(q - line) & 7]
| says, and in the phase going on only the tiles done so far (death_state count). The ROM dissolves the pattern tiles $00-$07 and no others: the
| standing body is the first eight sprites of the list (armour 1 without a shield has tiles $09-$0C among them, which stay whole); the weapon and
| the shield (the rest) are not drawn while he dies. The masks are mirrored when he faces right. d3 = the image number (tile * 4 + palette * 2 +
| mirrored). Keeps every register but a1.
dissolve_image:
    movem.l %d0-%d5/%a0/%a2, -(%sp)
    move.w hero_dead(%pc), %d0
    beq.w 9f
    lsr.w #2, %d3                           | the pattern tile
    lea death_state(%pc), %a0
    move.w 10(%a0), %d1                     | which sprite this is: the first eight are the body's
    addq.w #1, 10(%a0)
    cmpi.w #8, %d1
    blt.s 11f
    lea blank_image(%pc), %a1               | Player_DrawBody only: no sword, no shield
    bra.w 9f
11: cmpi.w #8, %d3
    bge.w 9f                                | not one of the tiles the ROM dissolves: whole
    move.w 2(%a0), %d4                      | the phases done
    cmpi.w #8, %d4
    bls.s 1f
    moveq #0, %d4                           | $FF: not started
1:  move.w 4(%a0), %d5                      | the tiles done in the phase going on
    bmi.s 2f
    cmp.w %d5, %d3
    bge.s 2f
    addq.w #1, %d4
2:  tst.w %d4
    beq.s 9f
    lea dissolve_masks(%pc), %a0
    lea dissolve_buf(%pc), %a2
    moveq #0, %d2                           | the line
3:  moveq #-1, %d0                          | what is left of the line's pixels
    moveq #0, %d1                           | the phase
4:  cmp.w %d4, %d1
    bge.s 5f
    move.w %d1, %d3
    sub.w %d2, %d3
    andi.w #7, %d3
    and.b (%a0,%d3.w), %d0
    addq.w #1, %d1
    bra.s 4b
5:  move.w hero_flip(%pc), %d3
    beq.s 7f
    moveq #7, %d3                           | facing right: the picture is mirrored
    moveq #0, %d5
6:  lsr.b #1, %d0
    roxl.b #1, %d5
    dbra %d3, 6b
    move.b %d5, %d0
7:  move.b (%a1,%d2.w), %d5                | the line's mask byte, then its four plane bytes
    and.b %d0, %d5
    move.b %d5, (%a2,%d2.w)
    move.w %d2, %d3
    lsl.w #2, %d3
    move.b 8(%a1,%d3.w), %d5
    and.b %d0, %d5
    move.b %d5, 8(%a2,%d3.w)
    move.b 9(%a1,%d3.w), %d5
    and.b %d0, %d5
    move.b %d5, 9(%a2,%d3.w)
    move.b 10(%a1,%d3.w), %d5
    and.b %d0, %d5
    move.b %d5, 10(%a2,%d3.w)
    move.b 11(%a1,%d3.w), %d5
    and.b %d0, %d5
    move.b %d5, 11(%a2,%d3.w)
    addq.w #1, %d2
    cmpi.w #8, %d2
    blt.s 3b
    lea dissolve_buf(%pc), %a1
9:  movem.l (%sp)+, %d0-%d5/%a0/%a2
    rts

| Player_DrawWeapon's numbers: where the weapon is (weapon_x, weapon_y: the hero's place and the package's offsets for the pose) and how far it
| reaches (weapon_rx, weapon_ry; 0 without a weapon). The enemies will be hit by them as Sprites_IsSpriteOutOfWeaponRange does. a1 = hero_x.
| Clobbers d0, a0.
weapon_update:
    bsr.w hero_sync
    movea.l hero_wtab(%pc), %a0
    move.w 4(%a1), %d0                      | the pose: the body frame + 8 for the flip bit
    lsl.w #3, %d0
    add.w 6(%a1), %d0
    lsl.w #3, %d0                           | 8 bytes a pose
    adda.w %d0, %a0
    move.w (%a1), %d0
    add.w (%a0)+, %d0
    move.w %d0, weapon_x-hero_x(%a1)
    move.w 2(%a1), %d0
    add.w (%a0)+, %d0
    move.w %d0, weapon_x+2-hero_x(%a1)
    move.w (%a0)+, weapon_x+4-hero_x(%a1)
    move.w (%a0)+, weapon_x+6-hero_x(%a1)
    rts

| ---------------------------------------------------------------------------------------------------------------------------- magic
| Player_CastMagic: one spell at a time (spell_state: type 0 Deluge, 1 Thunder, 2 Fire, 3 Death, 4 Tilte, -1 none; flags, x, x fraction, y, y fraction,
| counter, phase, the interrupt counter; see tools/magic_model.py, which this follows step for step and which is checked against the ROM). With
| Up held and B pressed (not on a ladder), a spell chosen (hero_magic) and the power (MP) for it, it starts at the hero and flies the way he faces.
| There are no enemies yet to hit it. The M key (until there is an inventory) chooses the next spell and fills the magic. a1 = hero_x. Clobbers nothing.
magic_update:
    movem.l %d0-%d6/%a0/%a2-%a3, -(%sp)
    move.w hero_dead(%pc), %d0
    bne.w 9f
    lea spell_state(%pc), %a3
    addq.w #1, 16(%a3)                      | InterruptCounter
    .ifndef NEWGAME                         | (a test key: not in the disk build)
    moveq #0, %d1                           | the M key: a new press chooses the next spell (none after the last) and fills the magic
    lea input_state+IN_KEYS+0x32(%pc), %a0
    tst.b (%a0)
    beq.s 1f
    moveq #1, %d1
1:  lea magic_key(%pc), %a0
    move.w (%a0), %d0
    move.w %d1, (%a0)
    tst.w %d0
    bne.s 2f
    tst.w %d1
    beq.s 2f
    lea hero_magic(%pc), %a0
    move.w (%a0), %d0
    addq.w #1, %d0
    cmpi.w #5, %d0
    blt.s 3f
    moveq #-1, %d0
3:  move.w %d0, (%a0)
    lea hud_state(%pc), %a0
    move.b #80, 1(%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    .endif
2:  tst.w (%a3)
    bpl.w 20f                               | one on the screen: it goes on
    btst #3, 19(%a1)                        | Player_IsClimbing: can climb, not falling off beside the ladder, climbing
    beq.s 4f
    btst #4, 19(%a1)
    beq.s 4f
    move.w (%a1), %d0
    andi.w #15, %d0
    beq.w 9f
    btst #2, 19(%a1)
    beq.w 9f
4:  lea input_state(%pc), %a0
    btst #3, IN_PAD(%a0)                    | Up held
    beq.w 9f
    btst #6, IN_PAD_NEW(%a0)                | B pressed just now
    beq.w 9f
    move.w hero_magic(%pc), %d0
    bmi.w 9f
    cmpi.w #5, %d0
    bcc.w 9f
    lea magic_costs(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    lea hud_state(%pc), %a0
    moveq #0, %d2
    move.b 1(%a0), %d2
    cmp.w %d1, %d2
    blt.w 9f                                | not enough power
    sub.w %d1, %d2
    move.b %d2, 1(%a0)                      | Player_ReduceMP
    lea hud_dirty(%pc), %a0
    st (%a0)
    move.w %d0, (%a3)                       | the type
    lea spell_hit(%pc), %a0
    clr.w (%a0)
    moveq #0, %d2
    tst.w 4(%a1)
    beq.s 5f
    moveq #0x40, %d2                        | it flies the way he faces
5:  lea magic_start_y(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    add.w 2(%a1), %d1
    andi.w #0xFF, %d1
    move.w %d1, 8(%a3)
    move.w (%a1), 4(%a3)
    clr.w 6(%a3)
    clr.w 10(%a3)
    clr.w 12(%a3)
    clr.w 14(%a3)
    moveq #5, %d3                           | the sound effect: the spell's, Tilte's own
    cmpi.w #4, %d0
    bne.s 6f
    ori.w #0x80, %d2                        | Tilte starts falling, 33 into its curve
    move.w #0x21, 12(%a3)
    moveq #0x14, %d3
6:  move.w %d2, 2(%a3)
    move.w %d3, %d0
    bsr.w sound_play_sfx
20: bsr.s magic_step
9:  movem.l (%sp)+, %d0-%d6/%a0/%a2-%a3
    rts

| The update handler of the spell on the screen. a3 = spell_state. Clobbers d0-d6, a0, a2.
magic_step:
    lea spell_hit(%pc), %a0                 | after a hit Thunder and Fire fly on for a time (24 and 255 updates) and hit nothing more
    move.w (%a0), %d0
    beq.s 0f
    cmpi.w #0x7FFF, %d0                     | Tilte hit an enemy last time (en_magic): CastMagic_HitHandler_Tilte made it type 11 with the counter 0, and now it is
    beq.w 45f                               | updated as that
    subq.w #1, %d0
    move.w %d0, (%a0)
    bne.s 0f
    move.w #-1, (%a3)
    rts
0:  move.w (%a3), %d5
    cmpi.w #11, %d5
    beq.w 46f
    cmpi.w #4, %d5
    beq.w 40f
    lea magic_speed(%pc), %a0               | Deluge 3, Thunder 2, Fire 4, Death 2 pixels a frame
    moveq #0, %d1
    move.b (%a0,%d5.w), %d1
    bsr.w spell_move_x                      | d0 = off the screen, d2 = a wall in its way
    tst.w %d0
    bne.s 31f
    tst.w %d2
    beq.s 39f
    btst #0, %d5                            | Deluge (0) and Fire (2) stop on a wall, Thunder (1) and Death (3) go through
    bne.s 39f
    moveq #0x0A, %d0
    bsr.w sound_play_sfx
31: move.w #-1, (%a3)
39: rts
40: btst #0, 15(%a3)
    beq.s 41f
    moveq #4, %d1                           | the missile: 4 pixels along and 4 up
    bsr.w spell_move_x
    tst.w %d0
    bne.s 31b
    moveq #4, %d1
    moveq #0, %d2
    bsr.w spell_move_y
    tst.w %d0
    bne.s 31b
    rts
41: moveq #1, %d1                           | the curve: one pixel along, and up or down by a fraction that follows the triangle of the counter
    bsr.w spell_move_x
    tst.w %d0
    bne.s 31b
    move.w 12(%a3), %d3
    move.w %d3, %d2
    andi.w #0x1F, %d2
    btst #5, %d3
    beq.s 42f
    moveq #0x1F, %d4
    sub.w %d2, %d4
    move.w %d4, %d2
42: lsl.w #3, %d2
    andi.w #0xFF, %d2
    moveq #0, %d1
    bsr.w spell_move_y
    tst.w %d0
    bne.s 31b
    move.w 12(%a3), %d3
    move.w %d3, %d0
    andi.w #0x1F, %d0
    beq.s 43f
    addq.w #1, %d3
    andi.w #0xFF, %d3
    move.w %d3, 12(%a3)
    rts
43: eori.w #0x80, 2(%a3)                    | every 32 ticks the curve turns
    btst #7, 3(%a3)
    bne.s 44f
    addq.w #1, %d3
    andi.w #0xFF, %d3
    move.w %d3, 12(%a3)
    rts
44: addq.w #1, 14(%a3)                      | the missile (odd phase) begins, flying up
    andi.w #0x7F, 2(%a3)
    rts
45: clr.w (%a0)                             | the explosion: type 11, its counter 0 at the hit and 1 after this update
    move.w #11, (%a3)
    move.w #1, 12(%a3)
    rts
46: addq.w #1, 12(%a3)                      | (CastMagic_UpdateTilteAfterFirstHit) it does not move; drawn for the counter 1 to 15, gone at 16
    cmpi.w #16, 12(%a3)
    bcs.s 47f
    move.w #-1, (%a3)
47: rts

| CastMagic_UpdateXPosition: d1 = pixels along its way (to the right when flag $40 is set). Out: d0 = 1 when it is off the screen (at the edge:
| $F0, Fire $E0 to the right), d2 = what the wall check found (non-zero: a wall). a3 = spell_state. Clobbers d1, d3-d4, a2.
spell_move_x:
    move.w 4(%a3), %d3
    move.w (%a3), %d4
    lea magic_widths(%pc), %a2
    btst #6, 3(%a3)
    beq.s 2f
    add.w %d1, %d3                          | to the right
    andi.w #0xFF, %d3
    move.w %d3, 4(%a3)
    moveq #0, %d1
    move.b (%a2,%d4.w), %d1
    add.w %d3, %d1                          | the column its right edge is in
    cmpi.w #0xFF, %d1
    bhi.s 3f
    move.w %d1, %d3
    bsr.w spell_wall
    bra.s 8f
3:  moveq #1, %d2                           | past the last column: a wall
8:  lea magic_max_x(%pc), %a2
    moveq #0, %d1
    move.b (%a2,%d4.w), %d1
    moveq #0, %d0
    cmp.w 4(%a3), %d1
    bhi.s 5f
    moveq #1, %d0
5:  rts
2:  sub.w %d1, %d3                          | to the left
    andi.w #0xFF, %d3
    move.w %d3, 4(%a3)
    cmpi.w #0xF0, %d3
    bcc.s 6f
    bsr.w spell_wall
    moveq #0, %d0
    rts
6:  moveq #1, %d2
    moveq #1, %d0
    rts

| CastMagic_CheckDirection_CheckImpassable: d3 = the pixel x to look at (0-255), d4 = the type. Out: d2 = non-zero when the block at the spell's y is
| one he cannot walk through, or the one below it (Thunder is two blocks high), or the one under that (its y is not on a block row).
| Keeps d3-d4, a3. Clobbers d0-d1, a2.
spell_wall:
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags
    move.w 8(%a3), %d0
    move.w %d0, %d1
    andi.w #0xF0, %d0
    move.w %d3, %d2
    lsr.w #4, %d2
    add.w %d2, %d0                          | the flag's index: row * 16 + column
    moveq #0, %d2
    cmpi.w #208, %d0
    bge.s 1f
    or.b (%a2,%d0.w), %d2
1:  cmpi.w #1, %d4                          | Thunder looks at the block below too
    bne.s 2f
    addi.w #0x10, %d0
    andi.w #0xFF, %d0
    cmpi.w #208, %d0
    bge.s 2f
    or.b (%a2,%d0.w), %d2
2:  andi.w #15, %d1
    beq.s 9f
    addi.w #0x10, %d0
    andi.w #0xFF, %d0
    cmpi.w #208, %d0
    bge.s 9f
    or.b (%a2,%d0.w), %d2
9:  rts

| CastMagic_UpdateYPosition: d1 = whole pixels, d2 = the fraction (of 256) it moves; down when flag $80 is set, else up. Out: d0 = 1 when it is off
| the screen. a3 = spell_state. Clobbers d1-d5.
spell_move_y:
    move.w 10(%a3), %d3
    move.w 8(%a3), %d4
    btst #7, 3(%a3)
    beq.s 2f
    add.w %d2, %d3                          | down
    move.w %d3, %d5
    lsr.w #8, %d5
    andi.w #0xFF, %d3
    move.w %d3, 10(%a3)
    add.w %d1, %d4
    add.w %d5, %d4
    moveq #0, %d0
    cmpi.w #0xFF, %d4
    bls.s 1f
    moveq #1, %d0
1:  andi.w #0xFF, %d4
    move.w %d4, 8(%a3)
    rts
2:  sub.w %d2, %d3                          | up
    move.w %d3, %d5
    asr.w #8, %d5
    andi.w #0xFF, %d3
    move.w %d3, 10(%a3)
    sub.w %d1, %d4
    add.w %d5, %d4
    andi.w #0xFF, %d4
    move.w %d4, 8(%a3)
    moveq #0, %d0
    cmpi.w #0xF0, %d4
    bcs.s 3f
    moveq #1, %d0
3:  rts

| The spell's picture (the finish handlers' choice by the interrupt counter: Thunder, Fire and the Tilte missile blink) drawn into screen a4, its
| box noted in this screen's slot (the box is cleared already). Mirrored when it flies right.
draw_spell:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    lea spell_state(%pc), %a2
    move.w (%a2), %d5
    bmi.w 9f
    cmpi.w #11, %d5
    beq.w draw_burst                        | Tilte after its hit: the explosion
    move.w 16(%a2), %d3                     | the interrupt counter
    moveq #0, %d6                           | the picture, counted from the first of the spells' (0x95)
    cmpi.w #1, %d5
    bhi.s 2f
    beq.s 1f
    move.w %d3, %d6                         | Deluge: four pictures, a change every 4 frames
    lsr.w #2, %d6
    andi.w #3, %d6
    bra.s 6f
1:  btst #1, %d3                            | Thunder: two, blinking
    bne.w 9f
    move.w %d3, %d6
    lsr.w #2, %d6
    andi.w #1, %d6
    addq.w #4, %d6
    bra.s 6f
2:  cmpi.w #3, %d5
    bhi.s 4f
    beq.s 3f
    btst #1, %d3                            | Fire
    beq.w 9f
    move.w %d3, %d6
    lsr.w #2, %d6
    andi.w #1, %d6
    addq.w #6, %d6
    bra.s 6f
3:  move.w %d3, %d6                         | Death: four, a change every 8 frames
    lsr.w #3, %d6
    andi.w #3, %d6
    addq.w #8, %d6
    bra.s 6f
4:  btst #0, 15(%a2)
    bne.s 5f
    moveq #12, %d6                          | Tilte on its curve: two pictures
    btst #3, %d3
    beq.s 6f
    moveq #13, %d6
    bra.s 6f
5:  btst #1, %d3                            | the missile: two, blinking
    bne.w 9f
    move.w %d3, %d6
    lsr.w #2, %d6
    andi.w #1, %d6
    addi.w #14, %d6
6:  btst #6, 3(%a2)
    beq.s 7f
    addi.w #16, %d6                         | the mirrored poses
7:  movea.l pkg_ptr+PKG_MAGIC_ANIM(%pc), %a5
    add.w %d6, %d6
    move.w (%a5,%d6.w), %d0
    adda.w %d0, %a5                         | the pose's record
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0
    lea 8(%a0), %a0
    move.w 4(%a2), %d4
    move.w 8(%a2), %d5
    sub.w camera(%pc), %d5
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a0)+
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a0)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a0)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a0)+
    movea.l pkg_ptr+PKG_MAGIC_IMAGES(%pc), %a3
    move.w %d4, %d0                         | the halves of it that are behind the background (CastMagic_CalculateVisibility, at the spell's place)
    move.w 8(%a2), %d1
    bsr.w behind_set
    move.w behind_v(%pc), %d0
    bne.s 10f
8:  move.w (%a5)+, %d0
    bmi.s 9f
    lea spell_state(%pc), %a2
    add.w 4(%a2), %d0
    move.w 8(%a2), %d1                      | blit_tile clobbers d0-d7: the position comes from memory each time
    sub.w camera(%pc), %d1
    add.w (%a5)+, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile
    bra.s 8b
10: movea.l %a5, %a6                        | behind a pillar: the tiles go through behind_tile like the hero's (en_blit's registers)
    movea.l en_nm(%pc), %a3
    moveq #-1, %d6
11: move.w (%a6)+, %d0
    bmi.s 9f
    lea spell_state(%pc), %a2
    add.w 4(%a2), %d0
    move.w 8(%a2), %d1
    sub.w camera(%pc), %d1
    add.w (%a6)+, %d1
    move.w (%a6)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    movea.l pkg_ptr+PKG_MAGIC_IMAGES(%pc), %a1
    adda.l %d2, %a1
    lea -40(%sp), %sp                       | the tile as en_blit has it (the 8 mask bytes, then 8 longs of plane bytes): the spells' images have a line's 5 bytes together
    movea.l %sp, %a0
    lea 8(%sp), %a2
    moveq #7, %d3
12: move.b (%a1)+, (%a0)+
    move.b (%a1)+, (%a2)+
    move.b (%a1)+, (%a2)+
    move.b (%a1)+, (%a2)+
    move.b (%a1)+, (%a2)+
    dbra %d3, 12b
    movea.l %sp, %a1
    bsr.w behind_tile
    lea 40(%sp), %sp
    bra.s 11b
draw_spell_end:
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

| The Tilte explosion (CastMagic_FinishHandler_TilteAfterFirstHit), entered from draw_spell with a2 = spell_state and the registers saved: four pieces (poses 32 to
| 35 of magic_anim: top left, bottom left, top right, bottom right), the counter (1 to 15) times 2 pixels from the spell's place in both directions. A piece's
| place is a byte, as the ROM adds it: one that passes the edge comes in at the other side. They are drawn bottom right first and the box noted for the erase
| holds all four.
draw_burst:
    move.w 12(%a2), %d6
    add.w %d6, %d6                          | 2 * counter
    move.w 4(%a2), %d0
    move.w %d0, %d1
    sub.w %d6, %d0
    add.w %d6, %d1
    andi.w #0xFF, %d0                       | the left pieces' x, the right pieces'
    andi.w #0xFF, %d1
    move.w 8(%a2), %d2
    move.w %d2, %d3
    sub.w %d6, %d2
    add.w %d6, %d3
    andi.w #0xFF, %d2                       | the top pieces' y, the bottom pieces'
    andi.w #0xFF, %d3
    movem.w %d0-%d3, -(%sp)                 | (sp): the four, then the piece counter, then each piece's place
    movea.l pkg_ptr+PKG_MAGIC_ANIM(%pc), %a5
    move.w 64(%a5), %d6
    lea (%a5,%d6.w), %a1                    | pose 32: the four pieces have the same box
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d6
    lsl.w #4, %d6
    adda.w %d6, %a0
    lea 8(%a0), %a0
    move.w %d0, %d4                         | x: the smallest and the largest of the two
    move.w %d1, %d5
    cmp.w %d5, %d4
    bls.s 1f
    exg %d4, %d5
1:  move.w (%a1)+, %d6
    add.w %d4, %d6
    move.w %d6, (%a0)+
    move.w (%a1)+, %d6
    add.w %d5, %d6
    move.w %d6, (%a0)+
    move.w %d2, %d4                         | y, less the camera
    move.w %d3, %d5
    cmp.w %d5, %d4
    bls.s 2f
    exg %d4, %d5
2:  move.w camera(%pc), %d7
    sub.w %d7, %d4
    sub.w %d7, %d5
    move.w (%a1)+, %d6
    add.w %d4, %d6
    move.w %d6, (%a0)+
    move.w (%a1)+, %d6
    add.w %d5, %d6
    move.w %d6, (%a0)+
    lea burst_buf(%pc), %a3                 | (the 16 images of burst_make: piece * 4 + the tile's place in the piece)
    moveq #3, %d7
    move.w %d7, -(%sp)
3:  move.w (%sp), %d7                       | the piece: bit 0 right, bit 1 bottom
    move.w 2(%sp), %d3
    btst #0, %d7
    beq.s 4f
    move.w 4(%sp), %d3
4:  move.w 6(%sp), %d4
    btst #1, %d7
    beq.s 5f
    move.w 8(%sp), %d4
5:  sub.w camera(%pc), %d4
    move.w %d3, -(%sp)                      | its place: x, y
    move.w %d4, -(%sp)
    move.w %d7, %d0
    lsr.w #1, %d0
    btst #0, %d7
    beq.s 6f
    addq.w #2, %d0
6:  addi.w #32, %d0                         | the pose: 32 + 2 * right + bottom
    add.w %d0, %d0
    movea.l pkg_ptr+PKG_MAGIC_ANIM(%pc), %a5
    move.w (%a5,%d0.w), %d0
    adda.w %d0, %a5
    addq.l #8, %a5                          | (past the box)
7:  move.w (%a5)+, %d0
    bmi.s 8f
    add.w 2(%sp), %d0
    move.w (%sp), %d1
    add.w (%a5)+, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile                         | (clobbers d0-d7: the place is on the stack)
    bra.s 7b
8:  addq.l #4, %sp
    move.w (%sp), %d7
    subq.w #1, %d7
    bmi.s 9f
    move.w %d7, (%sp)
    bra.s 3b
9:  lea 10(%sp), %sp
    bra.w draw_spell_end

| The Tilte explosion's pictures: one 16x16 picture (the tiles $6E to $71, the package holds its four images first in magic_images) drawn as four pieces, each the picture
| mirrored left-right (piece 2), upside down (piece 1) or both (piece 3). The package keeps only the four, so that it stays small: pkg_attach has this make the 16 images
| of burst_buf (piece p, place q in it: image p * 4 + q is image q ^ flags of the four, flags 0, 2, 1, 3 for p 0 to 3, mirrored as flags say). Keeps every register.
burst_make:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    movea.l pkg_ptr+PKG_MAGIC_IMAGES(%pc), %a2
    lea burst_buf(%pc), %a1
    moveq #0, %d6
1:  move.w %d6, %d0
    lsr.w #1, %d0
    btst #0, %d6
    beq.s 2f
    addq.w #2, %d0                          | the flags: p 0 to 3 give 0, 2, 1, 3
2:  moveq #0, %d7
3:  move.w %d7, %d1
    eor.w %d0, %d1
    mulu.w #SPRITE_IMAGE_BYTES, %d1
    lea (%a2,%d1.l), %a0
    bsr.s burst_flip
    lea SPRITE_IMAGE_BYTES(%a1), %a1
    addq.w #1, %d7
    cmpi.w #4, %d7
    blt.s 3b
    addq.w #1, %d6
    cmpi.w #4, %d6
    blt.s 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| a0 = an image of a sprite tile (blit_tile's: 8 lines of a mask byte and four plane bytes), a1 = where its copy goes, d0: bit 0 mirrors it left-right, bit 1 turns it upside down.
| Clobbers d1-d5 (not a0 and a1).
    .macro BREV                             | reverses the bits of each byte of d3 (d4 scratch)
    move.l %d3, %d4
    andi.l #0x55555555, %d4
    add.l %d4, %d4
    lsr.l #1, %d3
    andi.l #0x55555555, %d3
    or.l %d4, %d3
    move.l %d3, %d4
    andi.l #0x33333333, %d4
    lsl.l #2, %d4
    lsr.l #2, %d3
    andi.l #0x33333333, %d3
    or.l %d4, %d3
    move.l %d3, %d4
    andi.l #0x0F0F0F0F, %d4
    lsl.l #4, %d4
    lsr.l #4, %d3
    andi.l #0x0F0F0F0F, %d3
    or.l %d4, %d3
    .endm
burst_flip:
    movem.l %d6/%a3/%a5, -(%sp)
    moveq #0, %d1
1:  move.w %d1, %d2
    btst #1, %d0
    beq.s 2f
    moveq #7, %d2
    sub.w %d1, %d2                          | the line it goes to
2:  move.w %d1, %d5
    add.w %d5, %d5
    add.w %d5, %d5
    add.w %d1, %d5                          | 5 bytes a line: the mask byte, then the four plane bytes
    lea (%a0,%d5.w), %a3
    move.w %d2, %d5
    add.w %d5, %d5
    add.w %d5, %d5
    add.w %d2, %d5
    lea (%a1,%d5.w), %a5
    moveq #4, %d6
3:  moveq #0, %d3
    move.b (%a3)+, %d3
    btst #0, %d0
    beq.s 4f
    BREV
4:  move.b %d3, (%a5)+
    dbra %d6, 3b
    addq.w #1, %d1
    cmpi.w #8, %d1
    blt.w 1b
    movem.l (%sp)+, %d6/%a3/%a5
    rts

| Area_ScrollTo and a new screen: the spell is gone and the interrupt counter starts again. Clobbers nothing.
spell_clear:
    move.l %a0, -(%sp)
    lea spell_state(%pc), %a0
    move.w #-1, (%a0)
    clr.w 16(%a0)
    lea spell_hit(%pc), %a0
    clr.w (%a0)
    movea.l (%sp)+, %a0
    rts

| Player_GetBodySpriteFrameOffset: the pose from his state. 3 in the air (jumping), 4 (the ROM's frame 7) climbing, else the walk frames 0, 1, 2, 1
| by the movement tick (every 8 ticks the next) while he walks and 0 standing. a1 = hero_x. Clobbers d0-d2.
hero_pose:
    move.w 18(%a1), %d0
    btst #0, %d0
    beq.s 2f
    moveq #3, %d1                           | jumping: the frame in the air, or the attack frame
    btst #7, %d0
    beq.s 9f
    bra.s 3f
2:  move.w %d0, %d2
    andi.w #0x18, %d2
    cmpi.w #0x18, %d2
    bne.s 1f
    moveq #7, %d1
    move.w (%a1), %d2
    andi.w #15, %d2
    beq.s 9f                                | square on a ladder and climbing
    btst #2, %d0
    beq.s 9f                                | (falling off the ladder is not climbing)
1:  btst #7, %d0
    bne.s 3f
    tst.w 36(%a1)
    bmi.s 4f
    btst #7, %d4
    beq.s 4f
    moveq #3, %d1                           | wing boots and A held: the pose in the air
    bra.s 9f
4:  moveq #0, %d1
    tst.w 14(%a1)
    beq.s 9f                                | not walking
    move.w 22(%a1), %d2
    lsr.w #3, %d2
    andi.w #3, %d2
    move.w %d2, %d1
    cmpi.w #3, %d1
    bne.s 9f
    moveq #1, %d1
    bra.s 9f
3:  move.w 28(%a1), %d1                     | attacking: frame 4, 5 or 6 by the attack phase
    addq.w #4, %d1
9:  move.w %d1, 6(%a1)
    rts

| Player_CheckHandleAttack: B pressed (not held) starts an attack of 8 + 3 + 8 frames (PLAYER_ATTACK_ANIMATION_PHASES) unless he climbs.
| air bit $80 = attacking; fields: 24 B was down last frame (Player_StatusFlag bit 0), 26 phase timer, 28 phase. a1 = hero_x. Clobbers d0-d1, a0, a2.
hero_attack:
    btst #7, 19(%a1)
    bne.s 5f                                | already attacking
    btst #4, 19(%a1)                        | climbing: no attack
    beq.s 1f
    move.w (%a1), %d0
    andi.w #15, %d0
    beq.s 8f
    btst #2, 19(%a1)
    beq.s 8f
1:  lea input_state(%pc), %a0
    btst #6, IN_PAD_NEW(%a0)                | B pressed just now?
    beq.s 8f
    tst.w 24(%a1)
    bne.s 9f
    ori.w #0x80, 18(%a1)
    move.w #1, 24(%a1)
    clr.w 26(%a1)
    clr.w 28(%a1)
5:  addq.w #1, 26(%a1)
    move.w 28(%a1), %d0
    lea attack_phases(%pc), %a2
    moveq #0, %d1
    move.b (%a2,%d0.w), %d1
    cmp.w 26(%a1), %d1
    bhi.s 9f                                | the phase goes on
    clr.w 26(%a1)
    addq.w #1, %d0
    cmpi.w #3, %d0
    bcc.s 6f
    move.w %d0, 28(%a1)
    rts
6:  andi.w #0xFF7F, 18(%a1)                 | done
    rts
8:  clr.w 24(%a1)
9:  rts

| a1 = hero_x. $C0 when he starts walking, then 2 more a frame until $180.
hero_accelerate:
    tst.w 14(%a1)
    bne.s 1f
    move.w #0xC0, 12(%a1)
1:  move.w #1, 14(%a1)
    tst.w 38(%a1)
    beq.s 4f
    move.w #0x800, 12(%a1)                  | Player_UpdatePosFromKnockback: 8 pixels a frame
    rts
4:  move.w %d4, %d1
    andi.w #0x0C, %d1                       | up or down beside a ladder: the standard speed, no acceleration
    beq.s 3f
    btst #3, 19(%a1)
    beq.s 3f
    move.w #0xC0, 12(%a1)
    rts
3:  cmpi.w #0x180, 12(%a1)
    bcc.s 2f
    move.w hero_title(%pc), %d1
    lsr.w #2, %d1
    andi.w #3, %d1
    lea acc_delta(%pc), %a2
    moveq #0, %d0
    move.b (%a2,%d1.w), %d0                 | PLAYER_ACCELERATION_DELTA_BY_RANK_GROUP: 2, 4, 6, 8 by title >> 2
    add.w %d0, 12(%a1)
2:  rts

| d1 = a pixel x on the screen: is there a block he cannot walk through in that column, at his height (the rows his 32 lines touch)?
| Result in d0 and the Z flag (Z: free). Clobbers d1-d2, a2.
column_blocked:
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags                      | this screen's 13 rows of 16 flags
    lsr.w #4, %d1                           | the column
column_rows:                                | a2 = a screen's flags, d1 = a column of it
    move.w hero_y(%pc), %d2
    move.w %d2, -(%sp)
    lsr.w #4, %d2
    lsl.w #4, %d2
    add.w %d1, %d2                          | the flag's index: row * 16 + column
    moveq #0, %d0
    cmpi.w #208, %d2
    bge.s 1f
    or.b (%a2,%d2.w), %d0
1:  addi.w #16, %d2
    cmpi.w #208, %d2
    bge.s 2f
    or.b (%a2,%d2.w), %d0
2:  move.w (%sp)+, %d1
    andi.w #15, %d1
    beq.s 3f
    addi.w #16, %d2
    cmpi.w #208, %d2
    bge.s 3f
    or.b (%a2,%d2.w), %d0
3:  tst.b %d0
    rts

| d1 = 0 left, 1 right: is the neighbour screen's edge column (its last, its first) blocked at his height? (`LastColumnLeftScreen`,
| `FirstColumnInRightScreen`; with no neighbour the column is empty.) Out: d0 and Z (Z: free). Clobbers d1-d3, a2.
edge_blocked:
    move.w %d1, %d3
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    bne.s 1f
    moveq #0, %d0
    rts
1:  andi.w #0xFF, %d0
    bsr.w screen_flags
    moveq #15, %d1
    tst.w %d3
    beq.s 2f
    moveq #0, %d1
2:  bra.w column_rows

| d1 = 0 left, 1 right, 2 above, 3 below. Out: d0 = the neighbour's number in the table, $FF for none. Clobbers d0, a2.
neighbour_of:
    moveq #0, %d0
    move.w cur_screen(%pc), %d0
    lsl.w #2, %d0
    add.w %d1, %d0
    movea.l pkg_ptr+PKG_NEIGHBOURS(%pc), %a2
    move.b (%a2,%d0.w), %d0
    rts

| d1 = a pixel line below $D0 (relative to the screen's top): is there a block under the middle of the hero (x + 4), and under the next column
| when he stands over two (Area_CanMoveImmediatelyRight)? Out: d0 and Z (Z: free). Clobbers d1-d3, a2.
body_blocked:
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags
    lsr.w #4, %d1
    lsl.w #4, %d1                           | the row's first flag
    move.w hero_x(%pc), %d2
    move.w %d2, %d3
    addq.w #4, %d2
    lsr.w #4, %d2
    add.w %d2, %d1                          | the flag
    moveq #0, %d0
    or.b (%a2,%d1.w), %d0
    andi.w #15, %d3
    subq.w #4, %d3
    cmpi.w #8, %d3
    bcc.s 1f                                | x & 15 from 4 to 11: he stands over the next column too
    addq.w #1, %d1
    cmpi.w #208, %d1
    bge.s 1f
    or.b (%a2,%d1.w), %d0
1:  tst.b %d0
    rts

| a2 = 16 flags of a row of another screen: the one(s) under the hero's x (Player_CheckIfPassable beyond the screen). Out: d0 and Z.
edge_row:
    move.w hero_x(%pc), %d1
    move.w %d1, %d3
    lsr.w #4, %d1
    moveq #0, %d0
    or.b (%a2,%d1.w), %d0
    andi.w #15, %d3
    beq.s 1f
    addq.w #1, %d1
    cmpi.w #16, %d1
    bge.s 1f
    or.b (%a2,%d1.w), %d0
1:  tst.b %d0
    rts

| Is there something under his feet (the 32 lines of the hero down)? Out: d0 and Z (Z: free). Clobbers d1-d3, a2.
blocked_below:
    move.w hero_y(%pc), %d1
    addi.w #32, %d1
    andi.w #0xFF, %d1
    cmpi.w #0xD0, %d1
    bcs.w body_blocked
    moveq #3, %d1                           | below the screen: the first row of the screen below
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 1f
    andi.w #0xFF, %d0
    bsr.w screen_flags
    bra.w edge_row
1:  moveq #0, %d0
    rts

| Is there something just over his head (the line above his y)? Out: d0 and Z. Clobbers d1-d3, a2.
blocked_above:
    move.w hero_y(%pc), %d1
    subq.w #1, %d1
    andi.w #0xFF, %d1
    cmpi.w #0xF0, %d1
    bcs.w body_blocked
    moveq #2, %d1                           | above the screen: the last row of the screen above
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 1f
    andi.w #0xFF, %d0
    bsr.w screen_flags
    adda.w #192, %a2
    bra.w edge_row
1:  moveq #0, %d0
    rts

| Player_HandleVertLadderOrJump / Player_UpdateClimbOrJump for a hero who is not on a ladder (a1 = hero_x; tools/hero_physics.py is the reference):
| a new A press on the ground starts a jump (unless something is just over his head); the jump follows PLAYER_JUMP_CURVE; with nothing
| under his feet he falls 8 lines a frame; he lands on a block row. Over the top or the bottom of the screen he asks scroll_check for the
| neighbour (vscroll_req), or stops at the edge. Keeps a1, d4; clobbers d0-d3, a0, a2.
hero_vertical:
    .ifdef NO_PHYSICS
    rts                                     | (the tests that put him anywhere and want him to stay: make viewer VIEWER_DEFS='--defsym NO_PHYSICS=1')
    .endif
    bsr.w check_on_ladder
    tst.w 36(%a1)
    bmi.s 61f
    btst #7, %d4
    beq.s 61f
    btst #2, %d4                            | wing boots and A held: down and up fly, ladder or not
    bne.w climb_down
    btst #3, %d4
    bne.w climb_up
    bra.s 60f
61: btst #3, 19(%a1)                        | a ladder here, and up or down pressed: climbing
    beq.s 60f
    move.w %d4, %d0
    andi.w #0x0C, %d0
    beq.s 60f
    ori.w #0x10, 18(%a1)
    move.w (%a1), %d0
    andi.w #15, %d0
    bne.s 60f                               | not square on the ladder: hero_step steps him to it
    btst #2, %d4
    bne.w climb_down
    bra.w climb_up
60: cmpi.w #0x20, 16(%a1)
    bcs.s 1f
    andi.w #0xFFFE, 18(%a1)                 | the curve is over: not jumping
1:  btst #0, 19(%a1)
    bne.w 7f                                | jumping
    bsr.w blocked_below
    bne.s 3f
    btst #3, 19(%a1)                        | no floor, but a ladder: he hangs on it
    bne.s 3f
    ori.w #4, 18(%a1)                       | nothing under his feet: falling (gliding a pixel a frame on wings with A held)
    moveq #8, %d0
    tst.w 36(%a1)
    bmi.s 62f
    btst #7, %d4
    beq.s 62f
    moveq #1, %d0
62: add.w %d0, 2(%a1)
    cmpi.w #0xC1, 2(%a1)
    bcs.s 2f
    moveq #3, %d1                           | the bottom of the screen
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 8f
    lea vscroll_req(%pc), %a0
    move.w #3, (%a0)
    rts
8:  move.w #0xC0, 2(%a1)                    | no screen below: he stops at the edge
    andi.w #0xFFFB, 18(%a1)
    rts
2:  bsr.w blocked_below                     | landed on a block: on its top
    beq.s 9f
    andi.w #0xF0, 2(%a1)
9:  rts
3:  andi.w #0xFFFB, 18(%a1)                 | standing
    lea input_state(%pc), %a0
    btst #7, IN_PAD_NEW(%a0)                | A pressed just now?
    bne.s 4f
    andi.w #0xFFFC, 18(%a1)
    rts
4:  btst #4, 19(%a1)                        | climbing: no jump
    bne.s 9b
    bsr.w blocked_above
    bne.s 9b                                | no room to jump
    ori.w #3, 18(%a1)
    clr.w 16(%a1)
    bra.s 6f
7:  andi.w #0xFFFB, 18(%a1)
6:  move.w 16(%a1), %d0
    lea jump_curve(%pc), %a2
    moveq #0, %d1
    move.b (%a2,%d0.w), %d1                 | how far this frame
    cmpi.w #16, %d0
    bcc.s 20f
    move.w 2(%a1), %d2                      | rising
    sub.w %d1, %d2
    bpl.s 11f
    moveq #2, %d1                           | over the top of the screen
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 12f
    lea vscroll_req(%pc), %a0
    move.w #2, (%a0)
    andi.w #0xFFFE, 18(%a1)
    rts
12: clr.w 2(%a1)
    bra.s 14f
11: move.w %d2, 2(%a1)
    bsr.w blocked_above
    beq.s 15f
    move.w 2(%a1), %d0                      | the head hits a block: below its edge, and down
    move.w %d0, %d1
    andi.w #15, %d1
    beq.s 14f
    andi.w #0xF0, %d0
    addi.w #16, %d0
    move.w %d0, 2(%a1)
14: move.w #15, 16(%a1)
15: addq.w #1, 16(%a1)
    rts
20: add.w %d1, 2(%a1)                       | falling
    bsr.w blocked_below
    beq.s 15b
    andi.w #0xF0, 2(%a1)                    | landed
    andi.w #0xFFFE, 18(%a1)
    rts

| Player_CheckIfOnLadder: Can Climb (air bit 8) when a ladder block is at his head or his feet (x + 7; the next block too when x & 15 is 8);
| without one Climbing (bit $10) goes too. a1 = hero_x. Clobbers d0-d3, a2.
check_on_ladder:
    move.w (%a1), %d3
    addq.w #7, %d3
    andi.w #0xFF, %d3
    lsr.w #4, %d3                           | the column
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags
    adda.w #208, %a2                        | the ladder flags follow the blocking ones
    move.w 2(%a1), %d1
    bsr.s ladder_at
    tst.b %d0
    bne.s 1f
    move.w 2(%a1), %d1
    addi.w #31, %d1
    bsr.s ladder_at
1:  tst.b %d0
    beq.s 2f
    ori.w #8, 18(%a1)
    rts
2:  andi.w #0xFFE7, 18(%a1)                 | no ladder: not Can Climb, not Climbing
    rts

| d1 = a pixel line, d3 = the column, a2 = this screen's ladder flags: a ladder there (or in the next column when x & 15 is 8)? d0 = result.
ladder_at:
    andi.w #0xFF, %d1
    lsr.w #4, %d1
    lsl.w #4, %d1
    add.w %d3, %d1
    moveq #0, %d0
    cmpi.w #208, %d1
    bge.s 1f
    or.b (%a2,%d1.w), %d0
1:  tst.b %d0
    bne.s 3f
    move.w (%a1), %d2
    andi.w #15, %d2
    cmpi.w #8, %d2
    bne.s 3f
    addq.w #1, %d1
    cmpi.w #208, %d1
    bge.s 3f
    or.b (%a2,%d1.w), %d0
3:  rts

| Player_CheckHandleClimbUp (5/8 of a pixel a frame, with wing boots a whole one; the scroll to the screen above if he climbs over the top) and
| ClimbDown (3/4, with wing boots 1 1/2).
climb_up:
    andi.w #0xDA, 18(%a1)
    bsr.w blocked_above
    bne.s 9f
    addq.w #1, 22(%a1)
    st %d1                                  | wing boots on: a pixel every frame
    tst.w 36(%a1)
    bpl.s 5f
    move.w 20(%a1), %d0
    subi.w #0xA0, %d0
    smi %d1                                 | borrowed: he moves a pixel
    andi.w #0xFF, %d0
    move.w %d0, 20(%a1)
5:  tst.b %d1
    beq.s 9f
    tst.w 2(%a1)
    bne.s 8f
    moveq #2, %d1                           | over the top
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 9f
    lea vscroll_req(%pc), %a0
    move.w #2, (%a0)
    rts
8:  subq.w #1, 2(%a1)
9:  rts

climb_down:
    andi.w #0xDA, 18(%a1)
    bsr.w blocked_below
    bne.s 9f
    addq.w #1, 22(%a1)
    move.w 20(%a1), %d0
    addi.w #0xC0, %d0
    moveq #0, %d2
    tst.w 36(%a1)
    bmi.s 5f
    subi.w #0x40, %d0                       | wing boots on: 1 1/2 pixels a frame (a pixel and 1/2)
    moveq #1, %d2
5:  move.w %d0, %d1
    lsr.w #8, %d1                           | the carry: a pixel
    andi.w #0xFF, %d0
    move.w %d0, 20(%a1)
    add.w %d1, 2(%a1)
    add.w %d2, 2(%a1)
    cmpi.w #0xC1, 2(%a1)
    bcs.s 9f
    moveq #3, %d1
    bsr.w neighbour_of
    cmpi.b #0xFF, %d0
    beq.s 8f
    lea vscroll_req(%pc), %a0
    move.w #3, (%a0)
    rts
8:  move.w #0xC0, 2(%a1)
9:  rts

| Draws the hero in the pose his state says, into screen a4, and notes the rectangle in this screen's slot.
draw_hero:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    bsr.w hero_sync
    lea death_state(%pc), %a0
    clr.w 10(%a0)                           | (dissolving: the first tile again)
    move.w hero_flip(%pc), %d0
    move.w hero_frame(%pc), %d1
    cmpi.w #7, %d1
    bne.s 1f
    move.w hero_mtick(%pc), %d0             | climbing: the picture is mirrored every 16 ticks, by the tick alone (the ROM stores it over the facing)
    lsr.w #4, %d0
    andi.w #1, %d0
1:  lsl.w #3, %d0                           | * 8: a pose for each of the ROM's body frames, both ways round
    add.w hero_frame(%pc), %d0              | the pose
    add.w %d0, %d0
    lea hero_pose_off(%pc), %a0
    move.w %d0, (%a0)                       | (an offset in a pose table)
    move.w %d0, %d6
    move.w #0x7FFF, %d0                     | the box of all the parts: x0, x1, y0, y1
    move.w #-0x7FFF, %d1
    move.w #0x7FFF, %d2
    move.w #-0x7FFF, %d3
    lea hero_poses(%pc), %a2
    movea.l (%a2)+, %a5
    bsr.w hero_box_part
    movea.l (%a2)+, %a5
    bsr.w hero_box_part
    movea.l (%a2)+, %a5
    bsr.w hero_box_part
    movea.l (%a2)+, %a5
    bsr.w hero_box_part
    addq.w #8, %d1
    addq.w #8, %d3
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d4
    lsl.w #4, %d4
    adda.w %d4, %a0
    move.w hero_x(%pc), %d4                 | where he is: ST x and the line
    move.w hero_y(%pc), %d5
    sub.w camera(%pc), %d5
    add.w %d4, %d0
    add.w %d4, %d1
    add.w %d5, %d2
    add.w %d5, %d3
    movem.w %d0-%d3, (%a0)                  | the box
    movea.l hero_ram(%pc), %a3
    lea HERO_IMAGES_AT(%a3), %a3
    lea hero_poses(%pc), %a2                | each part is behind the background by what is under its own place (Player_CalculateVisibility):
    move.w hero_x(%pc), %d0                 | the body at his, the arm piece at x - 8 or + 16, the weapon where weapon_update says, the shield at the table's x and 8 down
    move.w hero_y(%pc), %d1
    bsr.s draw_hero_part
    move.w hero_x(%pc), %d0
    move.w hero_y(%pc), %d1
    moveq #-8, %d2
    move.w hero_flip(%pc), %d3
    beq.s 1f
    moveq #16, %d2
1:  add.w %d2, %d0
    bsr.s draw_hero_part
    move.w weapon_x(%pc), %d0
    move.w weapon_x+2(%pc), %d1
    bsr.s draw_hero_part
    move.w hero_frame(%pc), %d0
    add.w %d0, %d0
    add.w hero_flip(%pc), %d0
    lea shield_dx(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d0.w), %d2                 | SHIELD_SPRITE_OFFSETS_X
    move.w hero_x(%pc), %d0
    add.w %d2, %d0
    move.w hero_y(%pc), %d1
    addq.w #8, %d1
    bsr.s draw_hero_part
    bsr.s clear_margins
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

| One part of the hero (a2 = its pose table's pointer in hero_poses, moved on), the origin of the part d0 = x, d1 = y (the world's): the halves of it that are behind the
| background, then the part. Clobbers d0-d7, a0, a1, a3, a5, a6.
draw_hero_part:
    movea.l (%a2)+, %a5
    move.l %a5, %d2
    beq.s 9f
    move.w hero_pose_off(%pc), %d2
    move.w (%a5,%d2.w), %d2
    tst.w (%a5,%d2.w)
    bmi.s 9f                                | (nothing of it in this pose)
    movem.l %a2, -(%sp)
    bsr.w behind_set
    move.w hero_dead(%pc), %d2
    beq.s 1f
    lea behind_v(%pc), %a0
    clr.w (%a0)                             | (the dissolving body is drawn whole)
1:  bsr.w hero_draw_part
    movem.l (%sp)+, %a2
9:  rts

| The shield's x from the hero's: SHIELD_SPRITE_OFFSETS_X, 2 * the body frame + 1 when he faces left.
shield_dx:
    .byte 0, 8, 0, 8, 0, 8, 0, 8, 0, 8, 0, 8, 8, 0, 0, 0

| The hero (or his box) reaches into a side margin: the playfield is x 32 to 287, so what was drawn outside it is cleared again (the margins are
| black). Uses the box in this screen's slot; clobbers d0-d3, a0-a1.
clear_margins:
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0
    movem.w (%a0), %d0-%d3                  | x0, x1, y0, y1
clear_box:                                  | the same for the box d0-d3 (x0, x1, y0, y1); a4 = the screen drawn into
    cmpi.w #LEFT_BYTES*2, %d0
    blt.s 1f
    cmpi.w #320-LEFT_BYTES*2, %d1
    ble.s 9f
1:  cmpi.w #HUD_LINES, %d2
    bge.s 2f
    move.w #HUD_LINES, %d2
2:  cmpi.w #SCREEN_LINES, %d3
    ble.s 3f
    move.w #SCREEN_LINES, %d3
3:  sub.w %d2, %d3
    ble.s 9f
    subq.w #1, %d3
    mulu.w #STRIDE, %d2
    lea (%a4,%d2.l), %a1
    moveq #0, %d0
4:  move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    lea STRIDE-32(%a1), %a1
    move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    move.l %d0, (%a1)+
    dbra %d3, 4b
9:  rts

| Draws a screen's whole playfield (208 lines, stride 160, x from byte 16) into a buffer. a5 = the block ids (16 to a row), a4 = the buffer.
| Clobbers d0-d7, a0-a3, a6.
draw_playfield:
    bsr.w mattock_restore                   | what the Mattock broke in this screen is whole again (items.s)
    movea.l pkg_ptr+PKG_BLOCK_INDEX(%pc), %a2
    movea.l pkg_ptr+PKG_BLOCKS(%pc), %a3
    moveq #0, %d6                           | window line
4:  move.w %d6, %d0                         | line of the playfield
    move.w %d0, %d1
    lsr.w #4, %d1                           | block row
    andi.w #15, %d0                         | line inside the block
    lsl.w #3, %d0                           | * 8 bytes a line
    move.w %d1, %d2
    andi.w #1, %d2
    add.w %d2, %d2                          | the row's half of the corner (bit 1)
    lsl.w #4, %d1
    lea (%a5,%d1.w), %a1                    | the block ids of this row
    move.w %d6, %d3
    mulu.w #STRIDE, %d3
    lea LEFT_BYTES(%a4,%d3.l), %a0          | where the line goes
    moveq #0, %d4                           | block column
5:  moveq #0, %d5
    move.b (%a1,%d4.w), %d5                 | block id
    lsl.w #2, %d5
    move.w %d4, %d7
    andi.w #1, %d7
    or.w %d2, %d7                           | corner: column parity | row parity << 1
    add.w %d7, %d5
    add.w %d5, %d5
    move.w (%a2,%d5.w), %d5                 | image number
    moveq #0, %d7
    move.w %d5, %d7
    lsl.l #7, %d7                           | * 128 bytes
    add.w %d0, %d7
    lea (%a3,%d7.l), %a6
    move.l (%a6)+, (%a0)+
    move.l (%a6)+, (%a0)+
    addq.w #1, %d4
    cmpi.w #16, %d4
    blt.s 5b
    addq.w #1, %d6
    cmpi.w #208, %d6
    blt 4b
    rts


| What is on the screen a4 besides the blocks, as it stands (nothing moves while the game stands still, and the ROM's sprites stay on the screen): the boxes of the last drawing in
| this screen are put back, then the people, the enemies and the hero are drawn again (the frame loop's order, without the updates). The spell is not: the ROM's is off the
| screen from the message box on (jsnes, tools/refnes/mattockspell.mjs). Here and not in items.s: the people's routines are in .text.early, out of reach from the end of .text.
mattock_sprites:
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0
    bsr.w restore_rect
    lea 8(%a0), %a0
    bsr.w restore_rect
    clr.l (%a0)+
    clr.l (%a0)
    bsr.w enemies_erase
    .ifdef NPCS
    bsr.w npc_erase_boxes
    .endif
    .ifdef NPCS
    bsr.w npc_draw
    .endif
    bsr.w draw_enemies
    bra.w draw_hero

| a4 = the screen just drawn: waits for the VBL, shows it, makes the other screen the one to draw into (a4 and slot_index), and draws
| the HUD again if the game changed it (right after the VBL, before the beam gets to it). pending_offset becomes shown_offset.
present_swap:
    bsr.w wait_vbl
    movea.l %a4, %a0
    bsr.w show_screen
    lea shown_offset(%pc), %a0
    move.w pending_offset(%pc), (%a0)
    lea shown_vtop(%pc), %a0
    move.w pending_vtop(%pc), (%a0)
    lea hud_dirty(%pc), %a0
    tst.b (%a0)
    beq.s 1f
    clr.b (%a0)
    bsr.w hud_update_all
1:  movea.l buf_a(%pc), %a0                 | the other screen is the next one to draw into
    cmpa.l %a0, %a4
    bne.s 2f
    movea.l buf_b(%pc), %a0
2:  movea.l %a0, %a4
    lea slot_index(%pc), %a0
    eori.w #1, (%a0)
    rts

| Walked to the edge of the screen with the stick pushed that way, and there is a screen there: scroll to it.
scroll_check:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    move.w vscroll_req(%pc), %d1            | the hero went over the top or the bottom (jump, fall): 2 above, 3 below
    beq.s 8f
    lea vscroll_req(%pc), %a0
    clr.w (%a0)
    bra.w 7f
8:  lea input_state(%pc), %a0
    move.b IN_PAD(%a0), %d0
    move.w hero_x(%pc), %d1
    btst #0, %d0                            | right
    beq.s 1f
    cmpi.w #HERO_X_MAX, %d1
    blt.s 4f
    moveq #1, %d1                           | the neighbour to the right
    bra.s 2f
1:  btst #1, %d0                            | left
    beq.s 4f
    cmpi.w #HERO_X_MIN, %d1
    bgt.s 4f
    lea hero_wall(%pc), %a0
    tst.w (%a0)
    bne.s 4f
    lea hero_off(%pc), %a0
    tst.w (%a0)
    beq.s 4f
    moveq #0, %d1
2:  moveq #0, %d0
    move.w cur_screen(%pc), %d0
    lsl.w #2, %d0
    add.w %d1, %d0                          | screen * 4 + 0 (left) or 1 (right)
    movea.l pkg_ptr+PKG_NEIGHBOURS(%pc), %a0
    move.b (%a0,%d0.w), %d0                 | its number in the table, $FF for none
    cmpi.b #0xFF, %d0
    bne.s 3f
    bsr.w edge_leave                        | no neighbour: out of a building, or another area
    bra.s 5f
3:  andi.w #0xFF, %d0
    bsr.w do_scroll                         | d0 = the screen scrolled to, d1 = 1 right, 0 left
    bra.s 5f
4:  .ifndef NO_PHYSICS
    bra.s 5f                                | (up and down scroll through hero_vertical)
    .endif
    btst #3, %d0                            | up
    beq.s 6f
    move.w hero_y(%pc), %d1
    cmpi.w #HERO_Y_MIN, %d1
    bgt.s 5f
    moveq #2, %d1
    bra.s 7f
6:  btst #2, %d0                            | down
    beq.s 5f
    move.w hero_y(%pc), %d1
    cmpi.w #HERO_Y_MAX, %d1
    blt.s 5f
    moveq #3, %d1
7:  moveq #0, %d0
    move.w cur_screen(%pc), %d0
    lsl.w #2, %d0
    add.w %d1, %d0
    movea.l pkg_ptr+PKG_NEIGHBOURS(%pc), %a0
    move.b (%a0,%d0.w), %d0
    cmpi.b #0xFF, %d0
    beq.s 5f
    andi.w #0xFF, %d0
    subq.w #2, %d1                          | 0 up, 1 down
    bsr.w do_vscroll
5:  movem.l (%sp)+, %d0-%d1/%a0-%a1
    rts

| ---------------------------------------------------------------------------------------------------------------------------- scrolling
| d0 = the screen to scroll to (its number in the table), d1 = 1 for the right neighbour, 0 for the left. The ROM waits 14 frames and then
| moves the picture 4 pixels a frame for 64 frames, hero included, with nothing else going on. The ST moves it 16 pixels every 4 frames:
| the clean background shifts one group of 16 pixels (in place, one frame), the window is copied into the screen being drawn (two frames),
| the hero is drawn and the screen shown (one frame). a4 and slot_index come back as present_swap leaves them; everything else is kept.
do_scroll:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    bsr.w spell_clear
    bsr.w enemies_clear
    lea scroll_dir(%pc), %a0
    move.w %d1, (%a0)
    lea scroll_target(%pc), %a0
    move.w %d0, (%a0)
    move.l %a4, -(%sp)
    movea.l next_ptr(%pc), %a4              | the screen scrolled to, drawn once into its own buffer
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a5
    adda.l %d0, %a5
    bsr.w draw_playfield
    movea.l (%sp)+, %a4
    moveq #13, %d7
1:  bsr.w wait_vbl
    bsr.w input_poll
    dbra %d7, 1b
    moveq #1, %d7                           | the step: 1 to 16
2:  move.w %d7, %d0
    bsr.w scroll_bg_step
    bsr.w wait_vbl
    moveq #0, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    moveq #1, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    move.w %d7, %d0
    bsr.w scroll_hero
    move.w %d7, %d0
    lsl.w #4, %d0
    lea pending_offset(%pc), %a0
    move.w %d0, (%a0)
    bsr.w present_swap
    addq.w #1, %d7
    cmpi.w #17, %d7
    blt.s 2b
    | arrived: the new playfield is the one in next_ptr (the shifted old one is rubbish now)
    bsr.w swap_playfields
    lea cur_screen(%pc), %a0
    move.w scroll_target(%pc), (%a0)
    lea pending_offset(%pc), %a0
    clr.w (%a0)
    lea hero_x(%pc), %a0                    | he stands where the new screen puts him
    move.w #1, (%a0)
    move.w scroll_dir(%pc), %d0
    bne.s 3f
    move.w #HERO_X_MAX, (%a0)
3:  clr.w 6(%a0)
    clr.w 8(%a0)
    bsr.w refresh_screens
    bsr.w enemies_load
    lea scroll_dir(%pc), %a0
    clr.w (%a0)
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

| d0 = the screen to scroll to, d1 = 1 for the screen below, 0 for the one above. The ROM does nothing to the hero but put him at the
| bottom ($C0, going up) or the top (0, going down) of the new screen at once; the picture moves 208 lines at 4 a frame under him
| (after the same wait). Here the two playfields lie one after the other in memory (above: the new one first) and the window is
| copied from a line of them that moves 16 lines every 4 frames; the last step may be shorter.
do_vscroll:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    bsr.w spell_clear
    bsr.w enemies_clear
    move.w %d1, %d6                         | 1 down, 0 up
    lea vscroll_down(%pc), %a0
    move.w %d1, (%a0)
    lea scroll_target(%pc), %a0
    move.w %d0, (%a0)
    | The playfields in the order the scroll needs: up: the new one at the lower address, down: the old one.
    move.l pf_ptr(%pc), %d2
    move.l next_ptr(%pc), %d3
    tst.w %d6
    bne.s 1f
    cmp.l %d3, %d2
    bhi.s 2f                                | up: the old one (pf) is the higher: right
    bra.s 3f
1:  cmp.l %d3, %d2
    bcs.s 2f                                | down: the old one is the lower: right
3:  movea.l %d2, %a0                        | on the wrong side: the old one moves to the other region
    movea.l %d3, %a1
    bsr.w copy_region
    lea pf_ptr(%pc), %a0
    move.l %d3, (%a0)+
    move.l %d2, (%a0)
2:  move.l %a4, -(%sp)
    movea.l next_ptr(%pc), %a4
    move.w scroll_target(%pc), %d0
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a5
    adda.l %d0, %a5
    bsr.w draw_playfield
    movea.l (%sp)+, %a4
    moveq #13, %d7
4:  bsr.w wait_vbl
    bsr.w input_poll
    dbra %d7, 4b
    | the viewport: its top line T in the two playfields (416 lines): d4 now, d3 at the end; the camera and the hero of the end
    move.w vscroll_down(%pc), %d6           | (draw_playfield clobbers the registers)
    lea hero_x(%pc), %a0
    move.w camera(%pc), %d4
    tst.w %d6
    bne.s 5f
    addi.w #208, %d4                        | up: the old screen is the lower one
    move.w #192, 2(%a0)                     | he is at the bottom of the new screen
    moveq #CAMERA_MAX, %d5
    move.w %d5, %d3                         | the end: the camera's line in the upper playfield
    bra.s 6f
5:  clr.w 2(%a0)                            | down: at the top of the new screen
    moveq #0, %d5
    move.w #208, %d3
6:  lea camera(%pc), %a1
    move.w %d5, (%a1)                       | the camera of the new screen: the hero is drawn with it
    clr.w 6(%a0)
    clr.w 8(%a0)
    movea.l pf_ptr(%pc), %a2                | the lower playfield: up: next_ptr, down: pf_ptr
    tst.w %d6
    bne.s 7f
    movea.l next_ptr(%pc), %a2
7:  move.w %d3, %d0
    sub.w %d4, %d0                          | what is left (signed)
    beq.s 12f
    bpl.s 9f
    neg.w %d0
    moveq #16, %d1
    cmp.w %d1, %d0
    bcc.s 10f
    move.w %d0, %d1
10: sub.w %d1, %d4                          | up: T goes down
    bra.s 11f
9:  moveq #16, %d1
    cmp.w %d1, %d0
    bcc.s 13f
    move.w %d0, %d1
13: add.w %d1, %d4
11: move.w %d4, %d0
    mulu.w #STRIDE, %d0
    add.l %a2, %d0
    lea view_src(%pc), %a0
    move.l %d0, (%a0)
    bsr.w wait_vbl
    moveq #0, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    moveq #1, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    bsr.w draw_hero
    lea pending_vtop(%pc), %a0
    move.w %d4, (%a0)
    bsr.w present_swap
    bra.s 7b
12: bsr.w swap_playfields                   | the new playfield is the one on show now
    lea pending_vtop(%pc), %a0
    move.w #-1, (%a0)
    lea cur_screen(%pc), %a0
    move.w scroll_target(%pc), (%a0)
    bsr.w refresh_screens
    bsr.w enemies_load
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

| a0 = the playfield to copy, a1 = where to (a whole region of 208 lines). Clobbers d0, a0-a1.
copy_region:
    move.w #(REGION_BYTES/16)-1, %d0
1:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    dbra %d0, 1b
    rts

| d0 = the step (1-16): the clean background moves 16 pixels towards the screen it scrolls from, and the next group of the new screen
| comes in at the other end.
scroll_bg_step:
    movem.l %d0-%d2/%d7/%a0-%a3, -(%sp)
    move.w camera(%pc), %d2                 | the window's lines of the playfield: the others are not needed (the new playfield replaces it)
    mulu.w #STRIDE, %d2
    addi.l #LEFT_BYTES, %d2
    movea.l pf_ptr(%pc), %a0
    adda.l %d2, %a0
    movea.l next_ptr(%pc), %a1
    adda.l %d2, %a1
    move.w #WINDOW_LINES-1, %d7
    move.w scroll_dir(%pc), %d1
    beq.s 4f
    move.w %d0, %d2                         | to the right: group m-1 of the new screen comes in at the right
    subq.w #1, %d2
    lsl.w #3, %d2
1:  lea 8(%a0), %a2
    movea.l %a0, %a3
    .rept 30
    move.l (%a2)+, (%a3)+
    .endr
    lea (%a1,%d2.w), %a2
    move.l (%a2)+, (%a3)+
    move.l (%a2)+, (%a3)+
    lea STRIDE(%a0), %a0
    lea STRIDE(%a1), %a1
    dbra %d7, 1b
    bra.s 9f
4:  moveq #16, %d2                          | to the left: group 16-m of the new screen comes in at the left
    sub.w %d0, %d2
    lsl.w #3, %d2
5:  lea 120(%a0), %a2                       | the groups move one place to the right, from the right
    lea 128(%a0), %a3
    .rept 30
    move.l -(%a2), -(%a3)
    .endr
    lea (%a1,%d2.w), %a2
    move.l (%a2)+, (%a0)
    move.l (%a2)+, 4(%a0)
    lea STRIDE(%a0), %a0
    lea STRIDE(%a1), %a1
    dbra %d7, 5b
9:  movem.l (%sp)+, %d0-%d2/%d7/%a0-%a3
    rts

| d0 = 0: the top half of the window (84 lines), 1: the bottom half: copied from view_src (the window's first line in the playfield, or
| in two playfields one after the other while scrolling up and down) to the screen a4.
copy_window_half:
    movem.l %d0/%a0-%a1, -(%sp)
    movea.l view_src(%pc), %a0
    lea HUD_LINES*STRIDE(%a4), %a1
    tst.w %d0
    beq.s 1f
    adda.l #(WINDOW_LINES/2)*STRIDE, %a0
    adda.l #(WINDOW_LINES/2)*STRIDE, %a1
1:  move.w #((WINDOW_LINES/2)*STRIDE/16)-1, %d0
2:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    dbra %d0, 2b
    movem.l (%sp)+, %d0/%a0-%a1
    rts

| d0 = the step (1-16): the hero where the picture has moved him to (he stays where he was in the world and the picture moves under
| him: x = 261 - 16 m for a scroll to the right and 16 m - 20 to the left: where the ROM's sprites are in the pictures it shows, found from jsnes), in the next walk frame.
scroll_hero:
    movem.l %d0-%d1/%a0, -(%sp)
    lea hero_x(%pc), %a0
    move.w %d0, %d1
    andi.w #1, %d1
    move.w %d1, 6(%a0)                      | hero_frame: 0 and 1 in turn
    lsl.w #4, %d0
    move.w scroll_dir(%pc), %d1
    beq.s 1f
    neg.w %d0
    addi.w #261, %d0                        | right
    move.w %d0, (%a0)
    move.w #1, 4(%a0)                       | facing right: flipped
    bra.s 2f
1:  subi.w #20, %d0                         | left
    move.w %d0, (%a0)
    clr.w 4(%a0)
2:  movem.l (%sp)+, %d0-%d1/%a0
    bra.w draw_hero

| The two playfields change places (the screen scrolled to is the one on show now).
swap_playfields:
    movem.l %d0-%d1, -(%sp)
    lea pf_ptr(%pc), %a0
    move.l (%a0), %d0
    move.l 4(%a0), %d1
    move.l %d1, (%a0)
    move.l %d0, 4(%a0)
    movem.l (%sp)+, %d0-%d1
    rts

| The screen being drawn into (a4) gets the window of the playfield, the people and the hero (the enemies too while box_keep is set), and is shown (three frames). Does not touch the other one.
refresh_screens:
    bsr.w set_view
    moveq #0, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    moveq #1, %d0
    bsr.w copy_window_half
    bsr.w wait_vbl
    .ifdef NPCS
    bsr.w npc_draw
    .endif
    move.w box_keep(%pc), %d0
    beq.s 1f
    bsr.w draw_enemies                      | (the Mattock's box: the ROM keeps its enemies on the screen, and so do we, in every one of the frames the box goes in)
1:  bsr.w draw_hero
    bra.w present_swap

| view_src = the window's first line in the playfield: pf_ptr + camera * 160.
set_view:
    move.l %a0, -(%sp)
    move.l %d0, -(%sp)
    move.w camera(%pc), %d0
    mulu.w #STRIDE, %d0
    add.l pf_ptr(%pc), %d0
    lea view_src(%pc), %a0
    move.l %d0, (%a0)
    move.l (%sp)+, %d0
    movea.l (%sp)+, %a0
    rts

| The window of the playfield follows the hero up and down: camera 0 while he is high (y below CAMERA_UP), 40 while he is low (above
| CAMERA_DOWN), unchanged in between. Only once he has moved (the start position decides the start camera). A change needs both screens
| redrawn (a copy of the window each, six frames): the hero stands still for a moment.
camera_follow:
    movem.l %d0-%d1/%a0, -(%sp)
    move.w hero_tick(%pc), %d0
    cmpi.w #-1, %d0
    beq.s 9f
    move.w hero_y(%pc), %d0
    move.w camera(%pc), %d1
    cmpi.w #CAMERA_UP, %d0
    bge.s 1f
    moveq #0, %d0
    bra.s 3f
1:  cmpi.w #CAMERA_DOWN, %d0
    ble.s 9f
    moveq #CAMERA_MAX, %d0
3:  cmp.w %d1, %d0
    beq.s 9f
    lea camera(%pc), %a0
    move.w %d0, (%a0)
    bsr.w refresh_screens
    bsr.w refresh_screens
9:  movem.l (%sp)+, %d0-%d1/%a0
    rts


| ---------------------------------------------------------------------------------------------------------------------------- doors
| Up pressed just now with a door block under him (the block at his x + 7 and the row of his y; the next one to the right when x & 15 is 8:
| `Area_SetStateFromDoorDestination`): the screen on the other side, as the ROM's Game_SetupEnterScreen. The doors are 8 bytes each
| (build_assets.door_table): screen, block, kind, destination screen, start position (Y/16 << 4 | X/16), palette, key, pad. Only kind 0
| (this screen set, this palette) and doors that need no key are followed here.
door_check:
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    lea input_state(%pc), %a0
    btst #3, IN_PAD_NEW(%a0)
    beq.w 9f
    move.w hero_x(%pc), %d1
    move.w hero_y(%pc), %d2
    andi.w #0xF0, %d2
    move.w %d1, %d3
    addq.w #7, %d3
    lsr.w #4, %d3
    or.w %d3, %d2                           | the block: row * 16 + column
    andi.w #15, %d1
    moveq #0, %d3
    cmpi.w #8, %d1
    bne.s 1f
    moveq #1, %d3                           | on a block boundary the next block is a candidate too
1:  move.w cur_screen(%pc), %d4
    movea.l pkg_ptr+PKG_DOORS(%pc), %a1
    move.w pkg_ptr+PKG_DOOR_COUNT(%pc), %d0
    beq.s 9f
    subq.w #1, %d0
2:  cmp.b (%a1), %d4
    bne.s 4f
    moveq #0, %d1
    move.b 1(%a1), %d1
    cmp.w %d2, %d1
    beq.s 5f
    tst.w %d3
    beq.s 4f
    addq.w #1, %d1
    cmp.w %d2, %d1
    beq.s 5f
4:  lea DOOR_BYTES(%a1), %a1
    dbra %d0, 2b
    bra.s 9f
5:  moveq #0, %d2
    move.b 6(%a1), %d2                      | the key he needs
    beq.s 6f
    bsr.w door_unlock                       | the item he holds (used up), a ring he has: the door opens; else a message, and it stays shut
    tst.w %d0
    beq.w 9f
6:  moveq #0, %d0
    move.b 3(%a1), %d0                      | the screen there
    moveq #0, %d1
    move.b 4(%a1), %d1                      | where he stands
    moveq #0, %d2
    move.b 7(%a1), %d2                      | the area there (for a building: its number)
    moveq #0, %d3
    move.b 5(%a1), %d3                      | the palette set there
    move.b 2(%a1), %d4
    beq.s 7f                                | kind 0: another screen of this package
    cmpi.b #DOOR_BUILDING, %d4
    beq.s 8f
    bsr.w enter_world                       | kind 1 (same area, other palette set) and 3 (out to another area)
    bra.s 9f
7:  bsr.w enter_screen
    bra.s 9f
8:  bsr.w enter_building
9:  movem.l (%sp)+, %d0-%d4/%a0-%a1
    rts

| d0 = the screen to go to (its number in the table), d1 = where the hero stands there (Y/16 << 4 | X/16). The picture fades out (black
| palette), the new screen is drawn, the hero put at the door's other end, and the picture fades in (six frames each, the ROM's fade is
| about as long). a4 and slot_index come back as present_swap leaves them.
enter_screen:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    bsr.w spell_clear
    bsr.w enemies_clear
    lea hero_x(%pc), %a0
    move.w %d1, %d2
    andi.w #15, %d2
    lsl.w #4, %d2
    move.w %d2, (%a0)                       | x
    lsr.w #4, %d1
    lsl.w #4, %d1
    move.w %d1, 2(%a0)                      | y
    clr.w 6(%a0)                            | frame, tick, fraction, acceleration, moving
    move.w #-1, 8(%a0)
    clr.w 10(%a0)
    clr.w 12(%a0)
    clr.w 14(%a0)
    clr.w 16(%a0)                           | jump index
    andi.w #0x40, 18(%a0)                   | flags: only the way he faces stays
    clr.w 20(%a0)
    clr.w 24(%a0)
    clr.w 26(%a0)
    clr.w 28(%a0)
    move.w %d0, %d3
    .ifdef FLOW
    bsr.w flow_fade_out                     | Screen_FadeToBlack: four steps, about 20 frames (src/flow.s)
    .else
    moveq #6, %d7
1:  bsr.w wait_vbl
    dbra %d7, 1b
    .endif
    movea.l #PALETTE, %a1                   | black
    moveq #15, %d7
2:  clr.w (%a1)+
    dbra %d7, 2b
    lea cur_screen(%pc), %a0
    move.w %d3, (%a0)
    move.l %a4, -(%sp)
    movea.l pf_ptr(%pc), %a4
    mulu.w #208, %d3
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a5
    adda.l %d3, %a5
    bsr.w draw_playfield
    movea.l (%sp)+, %a4
    lea camera(%pc), %a0                    | the camera for where he stands (the start camera's rule)
    move.w hero_y(%pc), %d1
    moveq #0, %d0
    cmpi.w #(CAMERA_UP+CAMERA_DOWN)/2, %d1
    blt.s 3f
    moveq #CAMERA_MAX, %d0
3:  move.w %d0, (%a0)
    bsr.w refresh_screens
    bsr.w refresh_screens
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a0
    movea.l #PALETTE, %a1
    moveq #15, %d7
4:  move.w (%a0)+, (%a1)+
    dbra %d7, 4b
    bsr.w enemies_load
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts


| d0 = the screen to go to, d1 = where the hero stands there (Y/16 << 4 | X/16), d2 = the area, d3 = the palette set: the package of that area
| and palette set is read from the disk (A<area>P<palette>.DAT, the biggest thing the viewer waits for; not when it is the one in use) and the
| screen is entered in it. The picture fades out first (FLOW) and goes black; the HUD is drawn again, its tiles are in the colours of the new package.
enter_world:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    .ifdef FLOW
    bsr.w flow_fade_out                     | Screen_FadeToBlack: a building, another area, the respawn after a death (the ROM has no fade in; a black screen is not faded)
    .endif
    lea black_palette(%pc), %a0
    movea.l #PALETTE, %a1
    moveq #15, %d0
1:  move.w (%a0)+, (%a1)+
    dbra %d0, 1b
    move.w %d2, %d0
    move.w %d3, %d1
    bsr.w load_package
    movem.l (%sp), %d0-%d3
    lea hud_shown(%pc), %a0
    moveq #(3*128/4)-1, %d2
2:  move.l #-1, (%a0)+
    dbra %d2, 2b
    lea hud_dirty(%pc), %a0
    move.b #1, (%a0)
    bsr.w enter_screen
    movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

black_palette:
    .space 32

| d0 = the screen there (not used: a building is the only screen of its package), d1 = where he stands, d2 = the building's id (Area_DestScreen), d3 = the building's palette set. Remembers
| the way back (Game_EnterBuilding: area, screen, palette set and the block he stood at) and goes in facing left; the sword is put away (the
| building's package has the hero without one).
enter_building:
    movem.l %d0-%d3/%a0, -(%sp)
    lea saved_area(%pc), %a0
    move.w cur_area(%pc), (%a0)+
    move.w cur_pal(%pc), (%a0)+
    move.w cur_screen(%pc), (%a0)+
    move.w hero_y(%pc), %d0
    andi.w #0xF0, %d0
    move.w hero_x(%pc), %d2
    lsr.w #4, %d2
    or.w %d2, %d0
    move.w %d0, (%a0)                       | saved_pos
    .ifdef NPCS
    lea building_id(%pc), %a0
    move.w 10(%sp), (%a0)                   | (d2, the door's byte 7: the building's id, the first byte of the ROM's destination record, which the people and scripts are placed by)
    .endif
    lea hero_flip(%pc), %a0
    clr.w (%a0)
    moveq #0, %d0
    moveq #BUILDING_AREA, %d2
    bsr.w enter_world
    movem.l (%sp)+, %d0-%d3/%a0
    rts

| Walking off a side of a building: back out where he went in (Game_BeginExitBuilding), facing right.
exit_building:
    movem.l %d0-%d3/%a0, -(%sp)
    lea saved_area(%pc), %a0
    move.w (%a0)+, %d2
    move.w (%a0)+, %d3
    move.w (%a0)+, %d0
    move.w (%a0), %d1
    lea hero_flip(%pc), %a0
    move.w #1, (%a0)
    bsr.w enter_world
    .ifdef FLOW
    bsr.w flow_exit_music                   | after a respawn the area's song, not the town's (a quirk of the ROM)
    .endif
    movem.l (%sp)+, %d0-%d3/%a0
    rts

| Off the side of a screen that has no neighbour: out of a building, or into another area where the ROM's table (AREA_TOWN_TRANSITIONS_DATA,
| the package's edges) has one for this screen.
edge_leave:
    movem.l %d0-%d4/%a0, -(%sp)
    move.w cur_area(%pc), %d0
    cmpi.w #BUILDING_AREA, %d0
    bne.s 1f
    bsr.w exit_building
    bra.s 9f
1:  movea.l pkg_ptr+PKG_EDGES(%pc), %a0
    move.w pkg_ptr+PKG_EDGE_COUNT(%pc), %d4
    beq.s 9f
    subq.w #1, %d4
    move.w cur_screen(%pc), %d0
2:  cmp.b (%a0), %d0
    beq.s 3f
    addq.l #EDGE_BYTES, %a0
    dbra %d4, 2b
    bra.s 9f
3:  moveq #0, %d2
    move.b 1(%a0), %d2                      | the area
    moveq #0, %d0
    move.b 2(%a0), %d0                      | the screen
    moveq #0, %d1
    move.b 3(%a0), %d1                      | where he stands
    moveq #0, %d3
    move.b 4(%a0), %d3                      | the palette set
    bsr.w enter_world
9:  movem.l (%sp)+, %d0-%d4/%a0
    rts

| d0.w = the area, d1.w = the palette set: loads A<area>P<palette>.DAT into pkg_buf and makes it the package in use (pkg_ptr), unless it is
| the one in use. Silences the YM, and TOS's own VBL runs while the disk is read (it switches the drive off again; ours would not); then the
| package's song is played if the frame loop is running.
load_package:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    cmp.w cur_area(%pc), %d0
    bne.s 5f
    cmp.w cur_pal(%pc), %d1
    beq.w 10f
5:  moveq #-1, %d2                          | a door to another palette set of the same area: the ROM changes the song only when the new palette's is another one
    cmp.w cur_area(%pc), %d0                | (Player_CheckHandleEnterDoor); keep_music is the song of the package he leaves then, else -1
    bne.s 51f
    cmpi.w #BUILDING_AREA, %d0
    beq.s 51f
    move.w pkg_ptr+PKG_MUSIC(%pc), %d2
51: lea keep_music(%pc), %a0
    move.w %d2, (%a0)
    lea cur_area(%pc), %a0
    move.w %d0, (%a0)+
    move.w %d1, (%a0)
    lea pkg_name(%pc), %a0
    addi.b #'0', %d0
    move.b %d0, 1(%a0)
    move.w %d1, %d0
    ext.l %d0
    divu.w #10, %d0
    addi.b #'0', %d0
    move.b %d0, 3(%a0)
    swap %d0
    addi.b #'0', %d0
    move.b %d0, 4(%a0)
    bsr.w loading_show
    bsr.w sound_silence
    move.l old_vbl(%pc), %d2                | 0 before frame_init: TOS's vector is still the one in use
    beq.s 8f
    lea saved_vbl(%pc), %a1
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l VBL_VECTOR, (%a1)
    move.l %d2, VBL_VECTOR
    move.w (%sp)+, %sr
8:
    clr.w -(%sp)                            | Fopen(name, read)
    move.l %a0, -(%sp)
    move.w #0x3D, -(%sp)
    trap #1
    addq.l #8, %sp
    lea pkg_result(%pc), %a1
    move.l %d0, (%a1)                       | what Fopen answered (a handle, or a negative error)
    tst.l %d0
    bmi.s 9f
    move.w %d0, %d2                         | the handle
    movea.l pkg_buf(%pc), %a0
    adda.l #PACKAGE_SPAN-PACKAGE_COMP, %a0  | the packed file goes to the end of the package's room
    move.l %a0, -(%sp)                      | Fread(handle, count, buffer)
    move.l #PACKAGE_COMP, -(%sp)
    move.w %d2, -(%sp)
    move.w #0x3F, -(%sp)
    trap #1
    lea 12(%sp), %sp
    move.w %d2, -(%sp)                      | Fclose
    move.w #0x3E, -(%sp)
    trap #1
    addq.l #4, %sp
    movea.l pkg_buf(%pc), %a1
    movea.l %a1, %a0
    adda.l #PACKAGE_SPAN-PACKAGE_COMP, %a0
    bsr.w unpack
    movea.l pkg_buf(%pc), %a0
    bsr.w pkg_attach
9:  bsr.w loading_hide
    move.l old_vbl(%pc), %d2
    beq.s 10f
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l saved_vbl(%pc), VBL_VECTOR
    move.w (%sp)+, %sr
    move.l old_vbl(%pc), %d2
    beq.s 10f                               | the frame loop is not running yet: it plays the song itself
    .ifndef MUSIC
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0
    cmp.w keep_music(%pc), %d0
    beq.s 10f                               | the same song goes on (no restart, the Hour Glass's song stays too)
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    .endif
10: movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| The word LOADING on black while a package is read from the disk (the screen on show; before the frame loop runs, TOS's own screen): colour 15 white,
| the other colours black. loading_hide clears it again (and gives TOS's colours back when the frame loop is not running: an error message follows).
| Keep every register.
loading_show:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    bsr.s loading_screen
    bsr.s loading_clear
    movea.l #PALETTE, %a0
    moveq #14, %d0
1:  clr.w (%a0)+
    dbra %d0, 1b
    move.w #0x777, (%a0)
    lea text_planes(%pc), %a0
    moveq #3, %d0
2:  move.w #-1, (%a0)+
    dbra %d0, 2b
    lea loading_text(%pc), %a0
    moveq #0, %d6
    move.w #128, %d0
    move.w #96, %d1
    bsr.w text_string
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

loading_hide:
    movem.l %d0-%d2/%a0-%a3, -(%sp)
    move.l old_vbl(%pc), %d0
    beq.s 2f                                | before the frame loop: TOS's screen is not cleared (the flag tables lie behind the package, in it)
    bsr.s loading_screen
    bsr.s loading_clear
    bra.s 9f
2:
    movea.l #PALETTE, %a0
    lea saved_palette(%pc), %a1
    moveq #15, %d1
1:  move.w (%a1)+, (%a0)+
    dbra %d1, 1b
9:  movem.l (%sp)+, %d0-%d2/%a0-%a3
    rts

loading_screen:                             | a3 = the screen on show
    move.l old_vbl(%pc), %d0
    bne.w shown_screen
    movea.l orig_screen(%pc), %a3
    rts

loading_clear:                              | clears the screen a3
    movea.l %a3, %a0
    move.w #7999, %d0
1:  clr.l (%a0)+
    dbra %d0, 1b
    rts

| a0 = a package (the block make_package writes): its parts' offsets become addresses in pkg_ptr.
pkg_attach:
    movem.l %d0-%d1/%a0-%a2, -(%sp)
    lea pkg_ptr(%pc), %a1
    movea.l %a0, %a2
    moveq #(PKG_DOOR_COUNT/4)-1, %d1
1:  move.l (%a2)+, %d0
    add.l %a0, %d0
    move.l %d0, (%a1)+
    dbra %d1, 1b
    move.l (%a2)+, (%a1)+                   | the numbers of doors and screens
    move.l (%a2), (%a1)                     | of edges, and the music
    bsr.w burst_make                        | (needs pkg_ptr: the four images of the Tilte explosion)
    bsr.w behind_expand                     | (the sprites behind the background: the masks the file leaves to the block images, src/enemy.s)
    lea flag_screens(%pc), %a1              | the flags of the screens are made as they are asked for (`screen_flags`): none yet
    moveq #FLAG_SLOTS-1, %d1
2:  move.w #-1, (%a1)+
    dbra %d1, 2b
    clr.w (%a1)
    movem.l (%sp)+, %d0-%d1/%a0-%a2
    rts

| d0.w = a screen's number in the package. Out: a2 = its flags, 208 bytes of impassable ones (bit 0 of the block's flags) and 208 of ladder ones (the
| flags shifted right once), made from the block ids of the screen and kept in FLAG_SLOTS places behind the package (the oldest is made anew). Keeps all else.
screen_flags:
    movem.l %d0-%d4/%a0-%a1/%a3, -(%sp)
    lea flag_screens(%pc), %a0
    moveq #0, %d2
    moveq #0, %d4
1:  cmp.w (%a0)+, %d0
    beq.s 3f
    addq.w #1, %d2
    cmpi.w #FLAG_SLOTS, %d2
    bcs.s 1b
    moveq #1, %d4                           | not kept: the oldest place is made anew
    move.w (%a0), %d2
    move.w %d2, %d1
    addq.w #1, %d1
    cmpi.w #FLAG_SLOTS, %d1
    bcs.s 2f
    moveq #0, %d1
2:  move.w %d1, (%a0)
    lea flag_screens(%pc), %a0
    move.w %d2, %d1
    add.w %d1, %d1
    move.w %d0, (%a0,%d1.w)
3:  mulu.w #416, %d2
    movea.l pkg_buf(%pc), %a2
    adda.l #PACKAGE_MAX, %a2
    adda.l %d2, %a2
    tst.w %d4
    beq.s 9f
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a0
    adda.l %d0, %a0
    movea.l pkg_ptr+PKG_BLOCK_FLAGS(%pc), %a1
    lea 208(%a2), %a3
    moveq #0, %d1
    move.w #207, %d3
4:  move.b (%a0)+, %d1
    move.b (%a1,%d1.w), %d2
    move.b %d2, %d4
    andi.b #1, %d4
    move.b %d4, (%a2)+
    lsr.b #1, %d2
    move.b %d2, (%a3)+
    dbra %d3, 4b
    suba.w #208, %a2
9:  movem.l (%sp)+, %d0-%d4/%a0-%a1/%a3
    rts

hud_load_state:
    lea hud_state(%pc), %a1
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.w (%a0)+, (%a1)+
    rts

    .section .text.early,"ax"
early_base:                                 | the start of .text.early (tools/check_reach.py), where town.s and splash68.s put their code
    .text
    .include "hud.s"
    .include "frame.s"
    .include "password.s"
    .include "text.s"
    .include "save.s"                       | (the save file)
    .include "town.s"
    .include "enemy.s"
    .include "items.s"
    .include "menu.s"
    .include "hero.s"
    .include "blit.s"                       | (its code is in .text.late)
    .ifdef SPLASH
    .include "splash68.s"                   | (its code is in .text.early, in front of the variables: see link.ld)
    .endif
    .ifdef FLOW
    .include "flow.s"                       | (also in .text.early)
    .endif

    .section .rodata
hud_layout:
    .incbin "hud_layout.bin"
    .even

    .section .data
orig_screen:
    .long 0
pkg_ptr:
    .space PKG_SIZE                         | the addresses of the package in use (PKG_xxx are the offsets), then its door and screen counts
pkg_buf:
    .long 0
pkg_result:
    .long 0
cur_area:
    .word -1                                | the package in use (-1: none yet)
cur_pal:
    .word -1
cur_music:
    .word 0
saved_area:
    .word 0                                 | the way back out of a building: area, palette set, screen, block (Y/16 << 4 | X/16)
saved_pal:
    .word 0
saved_screen:
    .word 0
saved_pos:
    .word 0
saved_vbl:
    .long 0
pkg_name:
    .asciz "A0P00.DAT"
    .even
flag_screens:
    .space 2*FLAG_SLOTS+2                   | the screens whose flags are kept (-1 for none), then the place to fill next
cur_screen:
    .word START_SCREEN                      | the screen shown: its number in the table
scroll_dir:
    .word 0                                 | 1 scrolling to the right, 0 to the left (or not scrolling)
scroll_target:
    .word 0
pending_offset:
    .word 0
vscroll_down:
    .word 0
pending_vtop:
    .word -1                                | the viewport's top line in the two playfields while scrolling up or down (-1: not)
shown_vtop:
    .word -1
shown_offset:
    .word 0                                 | the picture on show has moved this many pixels (0 when not scrolling)
buf_a:
    .long 0
buf_b:
    .long 0
pf_ptr:
    .long 0                                 | the playfield (208 lines) of the screen on show, without sprites or HUD
next_ptr:
    .long 0                                 | the one of the screen scrolled to
view_src:
    .long 0                                 | where the window's lines come from (copy_window_half)
camera:
    .word CAMERA                            | the playfield line shown on the window's first line
slot_index:
    .word 0
rect_slots:
    .space 32                               | per screen: x0, x1, y0, y1 of where the hero was drawn in it, and the same for the spell (all zero: nothing)
hero_x:
    .word HERO_X
hero_y:
    .word HERO_Y
hero_flip:
    .word HERO_FLIP
hero_frame:
    .word HERO_FRAME
hero_tick:
    .word -1
hero_frac:
    .word 0
hero_acc:
    .word 0
hero_moving:
    .word 0
hero_jump:
    .word 0                                 | Player_JumpCurveIndex
hero_air:
    .word 0                                 | Player_Flags: 1 jumping, 2 holding to climb, 4 falling, 8 can climb, $10 climbing
hero_climb:
    .word 0                                 | Player_ClimbFlySpeedModifier: the fractions of a pixel the climbing adds up
hero_mtick:
    .word 0                                 | Player_MovementTick (walking, climbing; the animation uses it)
hero_atk:
    .word 0                                 | Player_StatusFlag bit 0: B was down at the last look
hero_atk_timer:
    .word 0                                 | Player_AttackPhaseTimer
hero_atk_phase:
    .word 0                                 | Player_AttackPhaseAnimFrame
hero_off:
    .word 0                                 | the left step ran off x 0 (the ROM scrolls then)
hero_wall:
    .word 0                                 | a wall in the next screen's last column holds him at x 0
hero_title:
    .word TITLE                             | PlayerTitle (the rank): the walking acceleration steps by its group; TITLE=n sets it (no experience yet)
hero_wings:
    .word WINGS                             | seconds of wing boots left (Player_StatusFlag bit 7 is "this is 0 or more"); -1 none
hero_knock:
    .word 0                                 | Player_StatusFlag bit 1: knocked back
hero_invinc:
    .word 0                                 | Player_InvincibilityPhase: $3C when hit, counts down to 0
weapon_x:
    .word 0, 0, 0, 0                        | weapon_update: x, y, reach x, reach y
spell_state:
    .word -1, 0, 0, 0, 0, 0, 0, 0, 0       | the spell: type (-1 none), flags ($40 flies right, $80 falls), x, x fraction, y, y fraction, counter, phase, interrupt counter
hero_next:                                  | NextPlayerTitle: the rank earned (the experience reached its price); a guru makes it hero_title (not inside the hero block: it is addressed by offsets)
    .ifdef NEXT_TITLE
    .word NEXT_TITLE                        | (tests) the rank earned at the start
    .else
    .word TITLE
    .endif
spell_hit:
    .word 0                                 | the spell has hit an enemy: the updates it flies on (Thunder 24, Fire 255) without hitting
hero_magic:
    .word MAGIC                             | SelectedMagic
magic_key:
    .word 0                                 | the M key was down at the last frame
magic_costs:
    .byte 2, 4, 6, 10, 16                   | MAGIC_COSTS
magic_start_y:
    .byte 8, 0, 0, 8, 8                     | CAST_MAGIC_START_Y
magic_speed:
    .byte 3, 2, 4, 2, 1
magic_widths:
    .byte 0x0F, 0x0F, 0x1F, 0x0F, 0x0F      | CAST_MAGIC_WIDTHS
magic_max_x:
    .byte 0xF0, 0xF0, 0xE0, 0xF0, 0xF0      | CAST_MAGIC_MAX_SCREEN_WIDTHS
    .even
hero_dead:
    .word 0                                 | 1 while he dies (death_step)
death_state:
    .word 0, 0xFF, -1, 0, 4, 0              | the pass, Player_DeathAnimationPhase, ...Counter, Screen_FadeOutCounter, ...Stage, the tile being drawn
dissolve_masks:
    .byte 0xFE, 0xDF, 0xF7, 0xFD, 0xBF, 0xEF, 0x7F, 0xFB   | PPUBUFFER_DRAWCOMMAND_REMOVE_VERT_LINES_MASKS
dissolve_buf:
    .space 40
blank_image:
    .space 40
    .even
step_clock:
    .word 0                                 | frames the hero's step has run (for the tests)
hourglass:
    .word -1                                | DurationHourGlass: seconds left (-1: not in force); enemies of the category 0 stand still while it is
wings_time:
    .byte 40, 30, 20, 10                    | TITLE_TO_WINGBOOTS_DURATION
acc_delta:
    .byte 2, 4, 6, 8
attack_phases:
    .byte 8, 3, 8, 0                        | PLAYER_ATTACK_ANIMATION_PHASES: thrust out, wait, withdraw
vscroll_req:
    .word 0                                 | 2 or 3: scroll_check is to scroll to the screen above or below
jump_curve:
    .byte 8, 4, 4, 4, 4, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 0       | PLAYER_JUMP_CURVE: up, then down
    .byte 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 4, 4, 4, 4, 8
bench_result:
    .long 0
burst_buf:
    .space 16*SPRITE_IMAGE_BYTES            | the Tilte explosion's 16 images (burst_make)
en_nm:
    .long 0                                 | enemies_load: the table of inverted masks (src/blit.s) that draw_enemies and hero_draw_part give en_blit
keep_music:
    .word -1                                | load_package: the song of the package that was in use when the area stays the same, else -1
hud_states:                                 | last in .data, next to the code: the start-up code and the menus reach these from either end of .text
    .incbin "hud_states.bin"
title_table:                                | PLAYER_TITLE_EXP_NEEDED (15 words), PLAYER_TITLE_GOLD (15 words)
    .incbin "title_table.bin"
    .even

    .section .sounddata
sound_bin:
    .incbin "sound.bin"
    .even
sound_song:
    .space SND_SONG_MAX

    .section .stack,"aw",@progbits          | the stack, 4 KB, behind the song buffer: both are zeros and not in the file (make_prg.py --bss-from). It must stay 4 KB: GEMDOS's file calls (a door loads a package)
    .space 4096                             | run on this stack in supervisor mode and TOS 1.02 needs far more than the 638 bytes the game's own calls reach; at 2 KB a door crashed on the author's TOS
stack_end:
