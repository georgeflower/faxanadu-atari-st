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
    addi.l #0x100, %d0
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
    movea.l %d0, %a4

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

    | The hero (and later every other sprite): the list is x, line, image number for each tile, ended by a word of -1.
    lea hero_list(%pc), %a5
    lea hero_images(%pc), %a3
10: move.w (%a5)+, %d0                      | x on the screen
    bmi.s 11f
    move.w (%a5)+, %d1                      | line (may be above or below the window)
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w blit_tile
    bra.s 10b
11:
    | The frame loop: one pass a VBL until Esc.
    bsr.w frame_init
12: bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    beq.s 12b
    bsr.w frame_exit

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
hud_tiles:
    .incbin "hud_tiles.bin"

    .section .stack,"aw",@progbits
    .space 4096
stack_end:
