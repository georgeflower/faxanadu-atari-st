| Overscan test: a 240-line screen on a PAL STF/STFM by opening the bottom border.
|
| The shifter stops the picture at the last line of the 50 Hz display. If the frequency is 60 Hz at that moment and back to
| 50 Hz a few cycles later, it carries on, and the picture runs on into the bottom border (to about line 310): 63..310 is
| about 248 lines, and 240 are what Faxanadu needs. A timer B interrupt (event count mode: it fires at the end of a display line)
| does the two timed writes; the vertical blank re-arms it every frame.
|
| The line and the delays are parameters (--defsym TB_LINE=n, TB_NOPS=n, TB_WAIT=n) so the working values can be found in Hatari's
| cycle-exact mode (`hatari_shot.py --trace video_border_v` says when a border opened) and then checked on a real machine.
|
| Position independent, like main.s: only PC-relative addressing names our own labels.

    .ifndef TB_LINE
    .equ TB_LINE, 199
    .endif
    .ifndef TB_NOPS
    .equ TB_NOPS, 0
    .endif
    .ifndef TB_WAIT
    .equ TB_WAIT, 50
    .endif

    .equ LINES, 240
    .equ BUFFER_LINES, 248                  | the shifter will fetch about 248 lines once the border is open
    .equ BUFFER_BYTES, (BUFFER_LINES * 160)

    .equ PALETTE, 0xFF8240
    .equ VBASE_HI, 0xFF8201
    .equ VBASE_MID, 0xFF8203
    .equ SYNCMODE, 0xFF820A
    .equ MFP_IERA, 0xFFFA07
    .equ MFP_IPRA, 0xFFFA0B
    .equ MFP_ISRA, 0xFFFA0F
    .equ MFP_IMRA, 0xFFFA13
    .equ MFP_TBCR, 0xFFFA1B
    .equ MFP_TBDR, 0xFFFA21

    .text
    .globl _start
    .section .text.boot,"ax"
_start:
game_start:
    bra.w start

    .section .data
test_palette:
    .word 0x000, 0x777, 0x700, 0x070, 0x007, 0x770, 0x707, 0x077
    .word 0x333, 0x555, 0x720, 0x270, 0x027, 0x702, 0x072, 0x742
saved_palette:
    .space 32
old_ssp:
    .long 0
old_vbase_hi:
    .byte 0
old_vbase_mid:
    .byte 0
old_iera:
    .byte 0
old_imra:
    .byte 0
    .even
old_vbl:
    .long 0
old_timer_b:
    .long 0
screen:
    .long 0
frames:
    .long 0
hide_cursor:
    .asciz "\033f"
show_cursor:
    .asciz "\033e"
    .even

    .text
start:
    movea.l 4(%sp), %a3                     | our basepage
    lea stack_end(%pc), %sp

    | Mshrink(0, basepage, size)
    move.l #image_size, %d0
    addi.l #0x100, %d0
    move.l %d0, -(%sp)
    move.l %a3, -(%sp)
    clr.w -(%sp)
    move.w #0x4A, -(%sp)
    trap #1
    lea 12(%sp), %sp

    | Malloc(buffer): our own screen, 256-byte aligned for the video base.
    move.l #(BUFFER_BYTES + 256), -(%sp)
    move.w #0x48, -(%sp)
    trap #1
    addq.l #6, %sp
    tst.l %d0
    beq no_memory
    addi.l #255, %d0
    andi.l #0xFFFFFF00, %d0
    lea screen(%pc), %a0
    move.l %d0, (%a0)

    | Super(0)
    clr.l -(%sp)
    move.w #32, -(%sp)
    trap #1
    addq.l #6, %sp
    lea old_ssp(%pc), %a0
    move.l %d0, (%a0)
    lea stack_end(%pc), %sp

    pea hide_cursor(%pc)
    move.w #9, -(%sp)
    trap #1
    addq.l #6, %sp

    | The picture: 240 lines of 20 groups of 16 pixels. Line 0 and line 239 are white (colour 1), so the first and last lines
    | can be told; otherwise group g of line y is colour (g + y/16) & 15. The lines after 239 are black.
    movea.l screen(%pc), %a0
    moveq #0, %d6                           | y
1:  cmpi.w #LINES, %d6
    bge 9f
    moveq #0, %d2                           | group
2:  move.w %d2, %d3
    move.w %d6, %d4
    lsr.w #4, %d4
    add.w %d4, %d3                          | colour = g + y/16 (the low four bits are used)
    tst.w %d6
    beq.s 3f
    cmpi.w #(LINES - 1), %d6
    bne.s 4f
3:  moveq #1, %d3                           | the first and the last line: white
4:  moveq #3, %d4
5:  lsr.w #1, %d3
    scs %d5
    ext.w %d5
    move.w %d5, (%a0)+
    dbra %d4, 5b
    addq.w #1, %d2
    cmpi.w #20, %d2
    blt.s 2b
    addq.w #1, %d6
    bra.s 1b
9:  cmpi.w #BUFFER_LINES, %d6               | black lines after the picture
    bge.s 10f
    moveq #39, %d4
11: clr.l (%a0)+
    dbra %d4, 11b
    addq.w #1, %d6
    bra.s 9b
10:

    | The palette and the screen.
    move.w #0x2700, %sr
    movea.l #PALETTE, %a2
    lea saved_palette(%pc), %a1
    moveq #15, %d1
6:  move.w (%a2)+, (%a1)+
    dbra %d1, 6b
    movea.l #PALETTE, %a2
    lea test_palette(%pc), %a1
    moveq #15, %d1
7:  move.w (%a1)+, (%a2)+
    dbra %d1, 7b

    lea old_vbase_hi(%pc), %a0
    move.b VBASE_HI, (%a0)
    lea old_vbase_mid(%pc), %a0
    move.b VBASE_MID, (%a0)
    move.l screen(%pc), %d0
    lsr.l #8, %d0
    move.b %d0, VBASE_MID
    lsr.l #8, %d0
    move.b %d0, VBASE_HI

    | Our vertical blank and timer B.
    lea old_vbl(%pc), %a0
    move.l 0x70, (%a0)
    lea old_timer_b(%pc), %a0
    move.l 0x120, (%a0)
    lea old_iera(%pc), %a0
    move.b MFP_IERA, (%a0)
    lea old_imra(%pc), %a0
    move.b MFP_IMRA, (%a0)
    lea vbl(%pc), %a0
    move.l %a0, 0x70
    lea timer_b(%pc), %a0
    move.l %a0, 0x120
    clr.b MFP_TBCR
    bset #0, MFP_IERA
    bset #0, MFP_IMRA
    move.w #0x2300, %sr

    .ifdef AUTOEXIT
    | (a test build: leave by itself after AUTOEXIT frames, so a harness can check the way out)
wait_frames:
    move.l frames(%pc), %d0
    cmpi.l #AUTOEXIT, %d0
    blt.s wait_frames
    .else
    | Crawcin: wait for a key.
    move.w #7, -(%sp)
    trap #1
    addq.l #2, %sp
    .endif

    | Put everything back.
    move.w #0x2700, %sr
    clr.b MFP_TBCR
    lea old_iera(%pc), %a0
    move.b (%a0), MFP_IERA
    lea old_imra(%pc), %a0
    move.b (%a0), MFP_IMRA
    move.l old_vbl(%pc), 0x70
    move.l old_timer_b(%pc), 0x120
    move.b #2, SYNCMODE
    lea old_vbase_hi(%pc), %a0
    move.b (%a0), VBASE_HI
    lea old_vbase_mid(%pc), %a0
    move.b (%a0), VBASE_MID
    movea.l #PALETTE, %a2
    lea saved_palette(%pc), %a1
    moveq #15, %d1
8:  move.w (%a1)+, (%a2)+
    dbra %d1, 8b
    move.w #0x2300, %sr
    pea show_cursor(%pc)
    move.w #9, -(%sp)
    trap #1
    addq.l #6, %sp

no_memory:
    move.l old_ssp(%pc), -(%sp)
    move.w #32, -(%sp)
    trap #1
    addq.l #6, %sp
    clr.w -(%sp)
    trap #1

| Vertical blank: count the frame and arm timer B for the last display line. (The frame counter is the mark that the
| program runs: a harness can read it.)
vbl:
    movem.l %a0, -(%sp)
    clr.b MFP_TBCR
    move.b #TB_LINE, MFP_TBDR
    move.b #8, MFP_TBCR                     | event count: counts display lines
    lea frames(%pc), %a0
    addq.l #1, (%a0)
    movem.l (%sp)+, %a0
    rte

| Timer B: the two timed writes that keep the shifter going past the end of the 50 Hz picture.
timer_b:
    movem.l %d0/%a0, -(%sp)
    moveq #0, %d0
    movea.l #SYNCMODE, %a0
    .rept TB_NOPS
    nop
    .endr
    move.b %d0, (%a0)                       | 60 Hz, on the last display line, before cycle 502 ...
    move.w #TB_WAIT, %d0
1:  dbra %d0, 1b                            | ... and 50 Hz again only after it (Hatari: LINE_REMOVE_BOTTOM_CYCLE)
    move.b #2, (%a0)
    bclr #0, MFP_ISRA                       | software end of interrupt
    movem.l (%sp)+, %d0/%a0
    rte

    .section .stack,"aw",@progbits
    .space 4096
stack_end:
