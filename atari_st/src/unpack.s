| The unpacker for the data tools/lz.py packs: the area packages and the songs.

    .text

| a0 = a packed block (tools/lz.py: the length as a long, then sequences), a1 = where the data goes (may be just before the packed block: the
| writes stay behind the reads, `lz.overrun`). Keeps every register.
unpack:
    movem.l %d0-%d3/%a0-%a3, -(%sp)
    move.l (%a0)+, %d0
    lea (%a1,%d0.l), %a2                    | the end of the data
1:  moveq #0, %d1
    move.b (%a0)+, %d1                      | the token
    move.w %d1, %d2
    lsr.w #4, %d1                           | literals
    cmpi.w #15, %d1
    bne.s 3f
2:  moveq #0, %d3
    move.b (%a0)+, %d3
    add.w %d3, %d1
    cmpi.b #255, %d3
    beq.s 2b
3:  tst.w %d1
    beq.s 5f
    subq.w #1, %d1
4:  move.b (%a0)+, (%a1)+
    dbra %d1, 4b
5:  cmpa.l %a2, %a1
    bcc.s 9f                                | the last sequence has only literals
    moveq #0, %d3
    move.b (%a0)+, %d3
    lsl.w #8, %d3
    move.b (%a0)+, %d3                      | how far back
    movea.l %a1, %a3
    suba.l %d3, %a3
    andi.w #15, %d2                         | the match length - 4
    cmpi.w #15, %d2
    bne.s 7f
6:  moveq #0, %d3
    move.b (%a0)+, %d3
    add.w %d3, %d2
    cmpi.b #255, %d3
    beq.s 6b
7:  addq.w #3, %d2                          | + 4, - 1 for dbra
8:  move.b (%a3)+, (%a1)+
    dbra %d2, 8b
    bra.s 1b
9:  movem.l (%sp)+, %d0-%d3/%a0-%a3
    rts
