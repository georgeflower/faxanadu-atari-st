| Drawing a sprite tile of the enemies and of the hero (en_tiles, en_blit). In .text.late, behind all the other code: it reaches no variable, so it costs
| the code in front of it nothing of its reach to .data (AGENTS.md, 5i).

    .section .text.late,"ax"
late_base:                                  | (tools/check_reach.py checks this section's branches from here)
| The tiles of the pose a6 points at (x, line and image offset, ended by -1) into screen a4; a3 = the table of en_blit. On the stack (above the return
| address): the x the pose's offsets are from (a word), the line (a word), the address the images' offsets are from (a long). Clobbers everything but a4.
en_tiles:
    moveq #-1, %d6                          | (the constants d4-d7 that en_blit keeps from tile to tile are not made yet)
1:  move.w (%a6)+, %d0
    bmi.s 9f
    add.w 4(%sp), %d0
    move.w (%a6)+, %d1
    add.w 6(%sp), %d1
    moveq #0, %d2
    move.w (%a6)+, %d2
    movea.l 8(%sp), %a1
    adda.l %d2, %a1
    bsr.s en_blit
    bra.s 1b
9:  rts

| One enemy tile over the picture: d0 = x, d1 = line (signed), a1 = the image (8 mask bytes, then 8 longs of the four plane bytes), a3 = the table
| (en_nm_table), a4 = screen. The same pixels as blit_tile (a tile that starts outside the playfield is not drawn, the top of the window and the bottom
| of the screen cut it) but a tile is two byte columns, and `movep.l` reads and writes the four planes of one byte column at once: a column's mask and data
| are the tile's, shifted by the pixel in the byte (p, d6; k = 8 - p, d7) in each of four byte lanes of a long, the bits that come in from the next lane
| cleared by the lane masks lm1 (d4: the low 8 - p bits) and hi1 (d5, the top p bits); the mask is looked up (a byte to the long that has it, inverted, in
| every lane) and rotated, which is a shift of every lane because all four are the same. Column 1 is (L >> p) & lm1 with the mask (R | hi1), column 2
| (L << k) & hi1 with (R | lm1). The constants stay in d4-d7 for the next tile while its p is the same (d6 = -1: none yet; a tile that is cut leaves -1).
| Clobbers d0-d3, a0-a2, a5 (and d4-d7 when p changes).
    .macro EN_LINE n
    moveq #0, %d2
    move.l (%a2)+, %d3                      | the line's four plane bytes (the flags come from the mask byte)
    move.b (%a1)+, %d2
    beq.s 6f                                | nothing of this line is drawn
    add.w %d2, %d2
    add.w %d2, %d2
    move.l (%a3,%d2.w), %d2
    movep.l \n*STRIDE(%a0), %d0
    ror.l %d6, %d2
    move.l %d2, %d1
    or.l %d5, %d1
    and.l %d1, %d0
    move.l %d3, %d1
    lsr.l %d6, %d1
    and.l %d4, %d1
    or.l %d1, %d0
    movep.l %d0, \n*STRIDE(%a0)
    movep.l \n*STRIDE(%a5), %d0
    or.l %d4, %d2
    and.l %d2, %d0
    lsl.l %d7, %d3
    and.l %d5, %d3
    or.l %d3, %d0
    movep.l %d0, \n*STRIDE(%a5)
6:
    .endm
    .macro EN_LINE0 n
    moveq #0, %d2
    move.l (%a2)+, %d3
    move.b (%a1)+, %d2
    beq.s 6f
    add.w %d2, %d2
    add.w %d2, %d2
    movep.l \n*STRIDE(%a0), %d0
    and.l (%a3,%d2.w), %d0
    or.l %d3, %d0
    movep.l %d0, \n*STRIDE(%a0)
6:
    .endm
    .macro EN_COLUMN                        | a0 = the line's first byte (a4 + line * STRIDE), d0 = x: a0 to the byte column, d3 = p (0 to 7), d2 = the column's parity
    move.w %d0, %d3
    andi.w #7, %d3
    lsr.w #3, %d0                           | the byte column c: the group is c >> 1 (8 bytes), the byte in its words c & 1
    move.w %d0, %d2
    andi.w #1, %d2
    andi.w #0xFE, %d0
    lsl.w #2, %d0
    add.w %d2, %d0
    adda.w %d0, %a0
    .endm
    .macro EN_MASKS                         | d6 = p (not 0): d7 = 8 - p, d4 = lm1, d5 = hi1
    moveq #8, %d7
    sub.w %d6, %d7
    move.w #0xFF, %d5
    lsr.w %d6, %d5
    add.w %d5, %d5
    add.w %d5, %d5
    move.l (%a3,%d5.w), %d5                 | the inverted mask of the top p bits: hi1
    move.l %d5, %d4
    not.l %d4
    .endm
    .macro EN_SECOND                        | a5 = the second byte column (the next byte, or the next group's first)
    lea 1(%a0), %a5
    tst.w %d2
    beq.s 5f
    lea 7(%a0), %a5
5:
    .endm
en_blit:
    cmpi.w #LEFT_BYTES*2, %d0
    blt.w 98f
    cmpi.w #288, %d0
    bge.w 98f
    lea 8(%a1), %a2
    cmpi.w #HUD_LINES, %d1
    blt.w en_clip
    cmpi.w #SCREEN_LINES-8, %d1
    bgt.w en_clip
    mulu.w #STRIDE, %d1
    lea (%a4,%d1.l), %a0
    EN_COLUMN
    tst.w %d3
    beq.w en_aligned
    cmp.w %d6, %d3
    beq.s 1f
    move.w %d3, %d6
    EN_MASKS
1:  EN_SECOND
    EN_LINE 0
    EN_LINE 1
    EN_LINE 2
    EN_LINE 3
    EN_LINE 4
    EN_LINE 5
    EN_LINE 6
    EN_LINE 7
98: rts
en_aligned:
    EN_LINE0 0
    EN_LINE0 1
    EN_LINE0 2
    EN_LINE0 3
    EN_LINE0 4
    EN_LINE0 5
    EN_LINE0 6
    EN_LINE0 7
    rts
en_clip:                                    | a tile that is cut: n lines from the line s of its image, drawn in a loop
    move.w %d0, -(%sp)                      | (every register but d0-d3 holds something)
    moveq #8, %d3
    moveq #0, %d2
    cmpi.w #HUD_LINES, %d1
    bge.s 1f
    move.w #HUD_LINES, %d2
    sub.w %d1, %d2                          | lines above the window
    sub.w %d2, %d3
    ble.w 97f
    move.w #HUD_LINES, %d1
1:  move.w #SCREEN_LINES, %d0
    sub.w %d1, %d0                          | lines left to the bottom of the screen
    ble.w 97f
    cmp.w %d0, %d3
    ble.s 2f
    move.w %d0, %d3
2:  adda.w %d2, %a1
    lsl.w #2, %d2
    adda.w %d2, %a2
    move.w %d3, -(%sp)                      | the line count
    mulu.w #STRIDE, %d1
    lea (%a4,%d1.l), %a0
    move.w 2(%sp), %d0
    EN_COLUMN
    move.w %d3, %d6
    bne.s 3f
    moveq #-1, %d4                          | (p = 0: lm1 is all ones and hi1 none; the second column stays as it was)
    moveq #0, %d5
    moveq #8, %d7
    bra.s 4f
3:  EN_MASKS
4:  EN_SECOND
5:  EN_LINE 0
    lea STRIDE(%a0), %a0
    lea STRIDE(%a5), %a5
    subq.w #1, (%sp)
    bne.w 5b
    addq.l #2, %sp
    moveq #-1, %d6
97: addq.l #2, %sp
    rts

    .section .herodata
en_nm_table:                                | for a mask byte m: the long with ~m in each of its four bytes (en_blit)
    .set en_m, 0
    .rept 256
    .long (~(en_m * 0x01010101)) & 0xFFFFFFFF
    .set en_m, en_m + 1
    .endr
    .text
