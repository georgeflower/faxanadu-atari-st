| The HUD, drawn from a state block (rows 2 and 3 of the game's 32x4 tile HUD, screen lines 16 to 31).
|
| hud_state is what the game keeps: power (HP) and magic (MP) 0-80, experience 0-65535, gold 0-16777215, seconds 0-99. hud_update
| builds the 128 tile ids of the HUD from it, the way the game's own routines do (tools/faxanadu_gfx.py is the reference), and draws
| the tiles that are not already shown: the bars' partial tiles change their picture with the value, so they are always drawn.
|
| In: a4 = the screen. Keeps every register. Position independent: our own data only through (label,pc).
|
|   hud_tiles:    64 tile images of 32 bytes (8 lines of four plane bytes), tiles $0C and $0D are filled in from hud_partial
|   hud_partial:  2 bars x 8 values x 32 bytes: the partial tile of the power bar, then of the magic bar
|   hud_layout:   the 128 tile ids the game draws at the start (the static symbols; the bars and numbers are overwritten)

    .equ HUD_STRIDE, 160
    .equ HUD_LEFT, 16
    .equ HUD_FIRST, 64                      | the first tile drawn: row 2
    .equ HUD_END, 128                       | the tiles drawn are 64 to 127: rows 2 and 3

    .text
hud_update:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    bsr.s hud_build
    lea hud_shown(%pc), %a2
    bsr.w hud_draw
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| hud_update for the three pictures of the frame loop: both screens and the clean background (a4 is kept).
hud_update_all:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    bsr.s hud_build
    movea.l buf_a(%pc), %a4
    lea hud_shown(%pc), %a2
    bsr.w hud_draw
    movea.l buf_b(%pc), %a4
    lea hud_shown_b(%pc), %a2
    bsr.w hud_draw
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| After the first picture is copied to the other screen and the background: what they show is what the first one shows.
hud_copy_shown:
    movem.l %d0/%a0-%a1, -(%sp)
    lea hud_shown(%pc), %a0
    lea hud_shown_b(%pc), %a1
    moveq #31, %d0
1:  move.l (%a0)+, (%a1)+
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0-%a1
    rts

| Makes the tile ids (hud_buffer) and the partial tiles' pictures from hud_state. Clobbers d0-d5, a0-a3, a5, a6.
hud_build:
    lea hud_state(%pc), %a5
    lea hud_tiles(%pc), %a3
    lea hud_partial(%pc), %a0

    | The partial tiles' pictures for the two values.
    moveq #0, %d0
    move.b (%a5), %d0                       | power
    bsr.w hud_bar_value
    andi.w #7, %d0
    lsl.w #5, %d0
    lea (%a0,%d0.w), %a1
    lea 0x0C*32(%a3), %a2
    moveq #7, %d1
1:  move.l (%a1)+, (%a2)+
    dbra %d1, 1b
    moveq #0, %d0
    move.b 1(%a5), %d0                      | magic
    bsr.w hud_bar_value
    andi.w #7, %d0
    lsl.w #5, %d0
    lea (%a0,%d0.w), %a1
    lea 256(%a1), %a1
    lea 0x0D*32(%a3), %a2
    moveq #7, %d1
2:  move.l (%a1)+, (%a2)+
    dbra %d1, 2b

    | The tile ids: the layout of a new game, then the bars and the numbers over it.
    lea hud_layout(%pc), %a0
    lea hud_buffer(%pc), %a6
    movea.l %a6, %a1
    moveq #31, %d1
3:  move.l (%a0)+, (%a1)+
    dbra %d1, 3b

    moveq #0, %d0
    move.b (%a5), %d0                       | power: row 3, column 3
    lea 96+3(%a6), %a1
    moveq #0x08, %d2
    moveq #0x0C, %d3
    bsr.w hud_bar
    moveq #0, %d0
    move.b 1(%a5), %d0                      | magic: row 2, column 3
    lea 64+3(%a6), %a1
    moveq #0x09, %d2
    moveq #0x0D, %d3
    bsr.w hud_bar

    moveq #0, %d0
    move.w 2(%a5), %d0                      | experience: row 2, columns 16-20
    lea 64+16(%a6), %a1
    moveq #5, %d4
    bsr.w hud_digits
    move.l 4(%a5), %d0                      | gold: row 3, columns 16-22
    lea 96+16(%a6), %a1
    moveq #7, %d4
    bsr.w hud_digits
    moveq #0, %d0
    move.b 8(%a5), %d0                      | seconds: row 2, columns 24-25
    lea 64+24(%a6), %a1
    moveq #2, %d4
    bsr.w hud_digits

    rts

| Draws the tiles of hud_buffer that are not shown yet. a4 = the screen, a2 = what is shown on it (128 bytes). Clobbers d0-d4, a0-a3, a6.
hud_draw:
    lea hud_buffer(%pc), %a6
    lea hud_tiles(%pc), %a3
    moveq #HUD_FIRST, %d1
4:  moveq #0, %d0
    move.b (%a6,%d1.w), %d0
    cmpi.b #0x0C, %d0
    beq.s 5f
    cmpi.b #0x0D, %d0
    beq.s 5f
    cmp.b (%a2,%d1.w), %d0
    beq.s 6f
5:  move.b %d0, (%a2,%d1.w)
    lsl.w #5, %d0
    lea (%a3,%d0.w), %a1                    | the tile's 32 bytes
    move.w %d1, %d2
    lsr.w #5, %d2                           | tile row
    mulu.w #(8 * HUD_STRIDE), %d2
    move.w %d1, %d3
    andi.w #31, %d3                         | tile column
    move.w %d3, %d4
    lsr.w #1, %d4
    lsl.w #3, %d4                           | 8 bytes a 16-pixel group
    add.w %d4, %d2
    andi.w #1, %d3
    add.w %d3, %d2                          | left or right byte of the plane words
    lea HUD_LEFT(%a4,%d2.l), %a0
    moveq #7, %d3
7:  move.b (%a1)+, (%a0)                    | plane 0
    move.b (%a1)+, 2(%a0)
    move.b (%a1)+, 4(%a0)
    move.b (%a1)+, 6(%a0)
    lea HUD_STRIDE(%a0), %a0
    dbra %d3, 7b
6:  addq.w #1, %d1
    cmpi.w #HUD_END, %d1
    blt.s 4b
    rts

| d0 = a bar's value; returns it cut to 80.
hud_bar_value:
    cmpi.w #80, %d0
    bls.s 1f
    moveq #80, %d0
1:  rts

| The 11 tiles of a bar: d0 = value, a1 = where, d2 = full tile, d3 = partial tile (ten tiles, one of them partial unless the bar is
| full, then the end tile $0B).
hud_bar:
    bsr.s hud_bar_value
    lsr.w #3, %d0                           | full tiles
    moveq #0, %d4
1:  cmp.w %d0, %d4
    bcs.s 2f
    beq.s 3f
    move.b #0x07, (%a1)+                    | empty
    bra.s 4f
2:  move.b %d2, (%a1)+
    bra.s 4f
3:  move.b %d3, (%a1)+
4:  addq.w #1, %d4
    cmpi.w #10, %d4
    blt.s 1b
    move.b #0x0B, (%a1)
    rts

| d0 = a number (0 to 16,777,215), d4 = how many digits, a1 = the first digit's place: the digits as tiles $30-$39, low digit last.
hud_digits:
    adda.w %d4, %a1
    subq.w #1, %d4
1:  move.l %d0, %d1                         | d0 / 10: the high word first, so the quotient may be wider than 16 bits
    clr.w %d1
    swap %d1
    divu.w #10, %d1
    move.w %d1, %d5                         | quotient, high word
    clr.w %d1
    swap %d1                                | the remainder
    swap %d1
    move.w %d0, %d1
    divu.w #10, %d1                         | (remainder << 16 | low word) / 10
    swap %d5
    move.w %d1, %d5                         | quotient, low word
    swap %d1                                | the digit
    addi.b #0x30, %d1
    move.b %d1, -(%a1)
    move.l %d5, %d0
    dbra %d4, 1b
    rts

    .section .data
hud_dirty:                                  | set (non-zero) when hud_state changed: the loop calls hud_update_all
    .byte 0
    .even
hud_state:                                  | power, magic, experience, gold, seconds (+ a pad byte)
    .space 10
hud_buffer:
    .space 128
hud_shown:
    .space 128
hud_shown_b:
    .space 128
hud_shown_bg:
    .space 128
    .text
