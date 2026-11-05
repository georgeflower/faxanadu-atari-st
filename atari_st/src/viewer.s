| Viewer: one Faxanadu screen on the ST, made from the ROM's data by tools/build_assets.py.
|
| 320x200, low resolution. The 256-pixel-wide playfield sits in the middle (32 pixels free on each side); the first 32 lines are
| the HUD's (as at the start of a game); below it a window of 168 lines of the 208-line playfield, starting at line CAMERA.
|
| Position independent, like main.s: only PC-relative addressing names our own labels.

    .include "assets.inc"

    .equ PALETTE, 0xFF8240
    .equ STRIDE, 160
    .equ HUD_LINES, 32
    .equ WINDOW_LINES, 168
    .equ LEFT_BYTES, 16                     | 32 pixels
    .equ SPRITE_IMAGE_BYTES, 40
    .equ SCREEN_LINES, 200
    .equ SCREEN_BYTES, 32000
    .equ BUFFER_BYTES, 3*SCREEN_BYTES+256   | two screens and the clean background, the first on a 256-byte boundary
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
    .even

    .text
start:
    movea.l 4(%sp), %a3
    lea stack_end(%pc), %sp

    move.l #image_size, %d0
    addi.l #0x100+BUFFER_BYTES, %d0         | the image, the basepage and room for three screens behind the image
    move.l %d0, -(%sp)
    move.l %a3, -(%sp)
    clr.w -(%sp)
    move.w #0x4A, -(%sp)
    trap #1                                 | Mshrink
    lea 12(%sp), %sp

    clr.l -(%sp)
    move.w #32, -(%sp)
    trap #1                                 | Super(0)
    addq.l #6, %sp
    lea old_ssp(%pc), %a0
    move.l %d0, (%a0)
    lea stack_end(%pc), %sp

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

    movea.l #PALETTE, %a2                   | keep TOS's palette, set the screen's
    lea saved_palette(%pc), %a1
    moveq #15, %d1
1:  move.w (%a2)+, (%a1)+
    dbra %d1, 1b
    movea.l #PALETTE, %a2
    lea palette_data(%pc), %a1
    moveq #15, %d1
2:  move.w (%a1)+, (%a2)+
    dbra %d1, 2b

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
    move.l %d0, (%a0)                       | buf_bg: the picture without sprites
    movea.l buf_a(%pc), %a4

    | Clear the screen (32,000 bytes), then draw.
    movea.l %a4, %a0
    move.w #7999, %d1
3:  clr.l (%a0)+
    dbra %d1, 3b

    lea screen_data(%pc), %a5               | the screen's block ids, 16 to a row
    lea block_index(%pc), %a2
    lea block_images(%pc), %a3
    moveq #0, %d6                           | window line
4:  move.w %d6, %d0
    addi.w #CAMERA, %d0                     | line of the playfield
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
    addi.w #HUD_LINES, %d3
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
    cmpi.w #WINDOW_LINES, %d6
    blt 4b

    | The HUD: first the state of the start screen, then the second state (to see that an update clears what was there).
    lea hud_states(%pc), %a0
    bsr.w hud_load_state
    bsr.w hud_update
    lea hud_states+10(%pc), %a0
    bsr.w hud_load_state
    bsr.w hud_update

    | Both screens and the background get the same picture (without sprites).
    movea.l %a4, %a0
    movea.l buf_b(%pc), %a1
    bsr.w copy_screen
    movea.l %a4, %a0
    movea.l buf_bg(%pc), %a1
    bsr.w copy_screen

    .ifdef BENCH
    | Time the hero: draw it BENCH times over itself and count the VBLs that took (frame_init starts the counter at 0).
    lea hero_list(%pc), %a5
    lea hero_images(%pc), %a3
    bsr.w frame_init
    move.w #BENCH-1, %d6
15: movem.l %d6, -(%sp)
    lea hero_list(%pc), %a5
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
    bsr.w frame_init
12: bsr.w input_poll
    bsr.w hero_step
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #3, %d0
    adda.w %d0, %a0                         | this screen's slot: where the hero was drawn in it
    bsr.w restore_rect
    bsr.w draw_hero
    bsr.w wait_vbl
    movea.l %a4, %a0
    bsr.w show_screen
    movea.l buf_a(%pc), %a0                 | the other screen is the next one to draw into
    cmpa.l %a0, %a4
    bne.s 13f
    movea.l buf_b(%pc), %a0
13: movea.l %a0, %a4
    lea slot_index(%pc), %a0
    eori.w #1, (%a0)
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    beq.s 12b
    bsr.w frame_exit
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
    movea.l buf_bg(%pc), %a0
    adda.l %d2, %a0
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
hero_step:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    lea input_state(%pc), %a0
    move.b IN_PAD(%a0), %d0
    lea hero_x(%pc), %a1                    | hero_x, hero_y, hero_left, hero_frame, hero_tick
    moveq #0, %d2                           | 1 when he moves
    btst #1, %d0                            | left
    beq.s 1f
    subq.w #2, (%a1)
    move.w #1, 4(%a1)
    moveq #1, %d2
1:  btst #0, %d0                            | right
    beq.s 2f
    addq.w #2, (%a1)
    clr.w 4(%a1)
    moveq #1, %d2
2:  btst #3, %d0                            | up
    beq.s 3f
    subq.w #2, 2(%a1)
    moveq #1, %d2
3:  btst #2, %d0                            | down
    beq.s 4f
    addq.w #2, 2(%a1)
    moveq #1, %d2
4:  tst.w %d2                               | the limits only apply to a hero who moves (the start position may lie outside)
    beq.s 8f
    cmpi.w #16, (%a1)
    bge.s 5f
    move.w #16, (%a1)
5:  cmpi.w #224, (%a1)
    ble.s 6f
    move.w #224, (%a1)
6:  cmpi.w #56, 2(%a1)
    bge.s 7f
    move.w #56, 2(%a1)
7:  cmpi.w #168, 2(%a1)
    ble.s 8f
    move.w #168, 2(%a1)
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
10: movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

| Draws the hero in the pose his state says, into screen a4, and notes the rectangle in this screen's slot.
draw_hero:
    movem.l %d0-%d7/%a0-%a3/%a5, -(%sp)
    lea hero_anim(%pc), %a5
    move.w hero_left(%pc), %d0
    add.w %d0, %d0
    add.w hero_left(%pc), %d0               | * 3
    add.w hero_frame(%pc), %d0              | the pose
    add.w %d0, %d0
    move.w (%a5,%d0.w), %d0
    adda.w %d0, %a5                         | the pose's record
    lea rect_slots(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #3, %d0
    adda.w %d0, %a0
    move.w hero_x(%pc), %d4                 | where he is: ST x and the line
    move.w hero_y(%pc), %d5
    subi.w #CAMERA, %d5
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a0)+                      | the box
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a0)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a0)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a0)+
    lea hero_anim_images(%pc), %a3
1:  move.w (%a5)+, %d0
    bmi.s 2f
    add.w hero_x(%pc), %d0
    move.w hero_y(%pc), %d1                 | blit_tile clobbers d0-d7: the position comes from memory each time
    subi.w #CAMERA, %d1
    add.w (%a5)+, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile
    bra.s 1b
2:  movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5
    rts

hud_load_state:
    lea hud_state(%pc), %a1
    move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    move.w (%a0)+, (%a1)+
    rts

    .include "hud.s"
    .include "frame.s"

    .section .rodata
hero_list:
    .incbin "hero_list.bin"
    .even
hero_images:
    .incbin "hero_images.bin"
hero_anim:
    .incbin "hero_anim.bin"
hero_anim_images:
    .incbin "hero_anim_images.bin"
hud_layout:
    .incbin "hud_layout.bin"
hud_partial:
    .incbin "hud_partial.bin"
hud_states:
    .incbin "hud_states.bin"
palette_data:
    .incbin "palette.bin"
screen_data:
    .incbin "screen.bin"
    .even
block_index:
    .incbin "block_index.bin"
block_images:
    .incbin "blocks.bin"

    .section .data
orig_screen:
    .long 0
buf_a:
    .long 0
buf_b:
    .long 0
buf_bg:
    .long 0
slot_index:
    .word 0
rect_slots:
    .space 16                               | per screen: x0, x1, y0, y1 of where the hero was drawn in it (all zero: nothing)
hero_x:
    .word HERO_X
hero_y:
    .word HERO_Y
hero_left:
    .word HERO_LEFT
hero_frame:
    .word HERO_FRAME
hero_tick:
    .word -1
hud_tiles:
    .incbin "hud_tiles.bin"
bench_result:
    .long 0

    .section .stack,"aw",@progbits
    .space 4096
stack_end:
