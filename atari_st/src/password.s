| The mantra (the ROM's password) as the Europe ROM makes and reads it: tools/password_model.py is the reference, tests/test_password.py checks this code against
| it (and the model against the ROM). The state is a block of PW_STATE_BYTES bytes:
|   0 spawn, 1 rank, 2 special items, 3 quests, 4 weapon, 5 armour, 6 shield, 7 spell, 8 item (the selected ones; $FF none),
|   then five lists, each a count and four entries (eight for the items): weapons at 9, armours 14, shields 19, spells 24, items 29.
| Position independent. No hardware.

    .equ PW_SPAWN, 0
    .equ PW_RANK, 1
    .equ PW_SPECIAL, 2
    .equ PW_QUESTS, 3
    .equ PW_WEAPON, 4
    .equ PW_ARMOUR, 5
    .equ PW_SHIELD, 6
    .equ PW_SPELL, 7
    .equ PW_ITEM, 8
    .equ PW_WEAPONS, 9
    .equ PW_ARMOURS, 14
    .equ PW_SHIELDS, 19
    .equ PW_SPELLS, 24
    .equ PW_ITEMS, 29
    .equ PW_STATE_BYTES, 38
    .equ PW_MAX_CHARS, 32
    .equ PW_DATA_BYTES, 40

    .text
| Puts the d1.w low bits of d0 into the bit string at a2, at the bit d7 (most significant first), and moves d7 on.
pw_put:
    movem.l %d1-%d3, -(%sp)
    subq.w #1, %d1
1:  move.w %d0, %d2
    lsr.w %d1, %d2
    btst #0, %d2
    beq.s 2f
    move.w %d7, %d3
    lsr.w #3, %d3
    move.w %d7, %d2
    not.w %d2
    andi.w #7, %d2
    bset %d2, (%a2,%d3.w)
2:  addq.w #1, %d7
    dbra %d1, 1b
    movem.l (%sp)+, %d1-%d3
    rts

| Reads d1.w bits from the bit string at a2 from the bit d7 into d0, and moves d7 on.
pw_get:
    movem.l %d1-%d3, -(%sp)
    moveq #0, %d0
    subq.w #1, %d1
1:  move.w %d7, %d3
    lsr.w #3, %d3
    moveq #0, %d2
    move.b (%a2,%d3.w), %d2
    move.w %d7, %d3
    not.w %d3
    andi.w #7, %d3
    lsr.w %d3, %d2
    andi.w #1, %d2
    add.w %d0, %d0
    or.w %d2, %d0
    addq.w #1, %d7
    dbra %d1, 1b
    movem.l (%sp)+, %d1-%d3
    rts

| Clears the bit string (a2).
pw_clear:
    moveq #PW_DATA_BYTES/4-1, %d0
    movea.l %a2, %a3
1:  clr.l (%a3)+
    dbra %d0, 1b
    rts

| a0 = a state block, a1 = where to put the characters (a text ended by a 0 byte, up to PW_MAX_CHARS + 1 bytes). Clobbers nothing else.
pw_encode:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea pw_data(%pc), %a2
    bsr.w pw_clear
    moveq #13, %d7                          | the checksum (8 bits) and the number of characters (5) come last
    moveq #0, %d0
    move.b PW_SPAWN(%a0), %d0
    moveq #3, %d1
    bsr.w pw_put
    move.b PW_RANK(%a0), %d0
    moveq #4, %d1
    bsr.w pw_put
    move.b PW_SPECIAL(%a0), %d0
    moveq #8, %d1
    bsr.w pw_put
    move.b PW_QUESTS(%a0), %d0
    moveq #8, %d1
    bsr.w pw_put
    lea pw_selected_bits(%pc), %a3
    moveq #0, %d3
1:  moveq #0, %d0
    move.b PW_WEAPON(%a0,%d3.w), %d0
    cmpi.b #0xFF, %d0
    bne.s 2f
    moveq #0, %d0                           | none: a 0 bit
    moveq #1, %d1
    bsr.w pw_put
    bra.s 3f
2:  move.w %d0, %d4
    moveq #1, %d0
    moveq #1, %d1
    bsr.w pw_put                            | a 1 bit and the value
    move.w %d4, %d0
    moveq #0, %d1
    move.b (%a3,%d3.w), %d1
    bsr.w pw_put
3:  addq.w #1, %d3
    cmpi.w #5, %d3
    bne.s 1b
    lea pw_list_table(%pc), %a3
    moveq #4, %d3
4:  moveq #0, %d4
    move.b (%a3)+, %d4                      | where the count is
    moveq #0, %d0
    move.b (%a0,%d4.w), %d0
    move.w %d0, %d5                         | the number of entries
    moveq #0, %d1
    move.b (%a3)+, %d1
    bsr.w pw_put
    move.b (%a3)+, %d6                      | bits of an entry
    addq.l #1, %a3
    addq.w #1, %d4
    bra.s 6f
5:  moveq #0, %d0
    move.b (%a0,%d4.w), %d0
    moveq #0, %d1
    move.b %d6, %d1
    bsr.w pw_put
    addq.w #1, %d4
6:  dbra %d5, 5b
    dbra %d3, 4b
    move.w %d7, %d6                         | the bits in all
    addq.w #5, %d7
    divu.w #6, %d7                          | the characters: (bits + 5) / 6
    moveq #0, %d5
    move.w %d7, %d5                         | (the quotient is in the low word)
    moveq #8, %d7
    move.w %d5, %d0
    moveq #5, %d1
    bsr.w pw_put
    move.w %d6, %d4
    addq.w #7, %d4
    lsr.w #3, %d4                           | the bytes of the data; one 0 byte follows
    moveq #0, %d0
    moveq #0, %d1
    move.w %d4, %d2
7:  add.b (%a2,%d2.w), %d0                  | the sum of all but the first byte
    dbra %d2, 7b
    neg.b %d0
    move.b %d0, (%a2)                       | ... made 0 by the first
    moveq #0, %d7
    lea pw_chars(%pc), %a3
    subq.w #1, %d5
8:  moveq #6, %d1
    bsr.w pw_get
    move.b (%a3,%d0.w), (%a1)+
    dbra %d5, 8b
    clr.b (%a1)
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| a0 = a text ended by a 0 byte, a1 = a state block. On return d0 = 0 for a mantra the game accepts (the block holds it), -1 for a wrong one
| (Password_Maybe_CheckPasswordLength and Password_Load of the Europe ROM). Clobbers nothing else.
pw_decode:
    movem.l %d1-%d7/%a0-%a4, -(%sp)
    lea pw_data(%pc), %a2
    bsr.w pw_clear
    moveq #PW_STATE_BYTES-1, %d0
    movea.l %a1, %a3
9:  clr.b (%a3)+
    dbra %d0, 9b
    lea pw_chars(%pc), %a3
    moveq #0, %d7
    moveq #0, %d5                           | the characters
10: moveq #0, %d0
    move.b (%a0)+, %d0
    beq.s 14f
    cmpi.w #PW_MAX_CHARS, %d5
    beq.w 90f                               | too long
    moveq #63, %d2
11: cmp.b (%a3,%d2.w), %d0
    beq.s 12f
    dbra %d2, 11b
    bra.w 90f                               | not one of the characters
12: move.w %d2, %d0
    moveq #6, %d1
    bsr.w pw_put
    addq.w #1, %d5
    bra.s 10b
14: cmpi.w #2, %d5                          | fewer than two characters have no checksum and no count
    bcs.w 90f
    move.w %d5, %d4
    mulu.w #6, %d4
    addq.w #7, %d4
    lsr.w #3, %d4                           | the bytes of data
    moveq #0, %d0
    move.w %d4, %d2
    subq.w #1, %d2
15: add.b (%a2,%d2.w), %d0
    dbra %d2, 15b
    tst.b %d0
    bne.w 90f                               | the checksum
    moveq #0, %d0
    move.b 1(%a2), %d0
    lsr.b #3, %d0
    cmp.b %d5, %d0
    bne.w 90f                               | the number of characters
    moveq #13, %d7
    moveq #3, %d1
    bsr.w pw_get
    move.b %d0, PW_SPAWN(%a1)
    moveq #4, %d1
    bsr.w pw_get
    move.b %d0, PW_RANK(%a1)
    moveq #8, %d1
    bsr.w pw_get
    move.b %d0, PW_SPECIAL(%a1)
    moveq #8, %d1
    bsr.w pw_get
    move.b %d0, PW_QUESTS(%a1)
    lea pw_selected_bits(%pc), %a3
    moveq #0, %d3
16: moveq #1, %d1
    bsr.w pw_get
    tst.w %d0
    beq.s 17f
    moveq #0, %d1
    move.b (%a3,%d3.w), %d1
    bsr.w pw_get
    bra.s 18f
17: move.w #0xFF, %d0
18: move.b %d0, PW_WEAPON(%a1,%d3.w)
    addq.w #1, %d3
    cmpi.w #5, %d3
    bne.s 16b
    cmpi.b #0xFF, PW_ARMOUR(%a1)
    beq.w 90f                               | the armour must be one
    move.b PW_SPELL(%a1), %d0
    cmpi.b #0xFF, %d0
    beq.s 19f
    cmpi.b #5, %d0
    bcc.w 90f
19: move.b PW_ITEM(%a1), %d0
    cmpi.b #0xFF, %d0
    beq.s 20f
    bsr.w pw_item_ok
    bne.w 90f
20: lea pw_list_table(%pc), %a3
    moveq #4, %d3
21: moveq #0, %d4
    move.b (%a3)+, %d4                      | where the count is
    moveq #0, %d1
    move.b (%a3)+, %d1
    bsr.w pw_get
    move.b (%a3)+, %d6                      | bits of an entry
    moveq #0, %d1
    move.b (%a3)+, %d1                      | the most entries
    cmp.w %d1, %d0
    bhi.w 90f
    move.b %d0, (%a1,%d4.w)
    move.w %d0, %d5
    addq.w #1, %d4
    bra.s 23f
22: moveq #0, %d1
    move.b %d6, %d1
    bsr.w pw_get
    move.b %d0, (%a1,%d4.w)
    cmpi.w #PW_ITEMS, %d4
    bcs.s 24f
    bsr.w pw_item_ok                        | (an item)
    bne.w 90f
    bra.s 25f
24: cmpi.w #PW_SPELLS, %d4
    bcs.s 25f
    cmpi.b #5, %d0                          | (a spell)
    bcc.w 90f
25: addq.w #1, %d4
23: dbra %d5, 22b
    dbra %d3, 21b
    moveq #0, %d0
    bra.s 91f
90: moveq #-1, %d0
91: movem.l (%sp)+, %d1-%d7/%a0-%a4
    rts

| d0.b = an item number: the zero flag is set when it is one the game knows (below 21, and not 11, 14 or 17).
pw_item_ok:
    cmpi.b #21, %d0
    bcc.s 2f
    cmpi.b #11, %d0
    beq.s 2f
    cmpi.b #14, %d0
    beq.s 2f
    cmpi.b #17, %d0
    beq.s 2f
    moveq #0, %d0                           | (Z set) -- d0 is not kept
    rts
2:  moveq #1, %d0
    rts

    .section .rodata
pw_chars:
    .ascii "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789,?"
pw_selected_bits:
    .byte 2, 2, 2, 3, 5
pw_list_table:                              | the count's place, the bits of the count, the bits of an entry, the most entries
    .byte PW_WEAPONS, 3, 2, 4
    .byte PW_ARMOURS, 3, 2, 4
    .byte PW_SHIELDS, 3, 2, 4
    .byte PW_SPELLS, 3, 3, 4
    .byte PW_ITEMS, 4, 5, 8
    .even

    .section .data
pw_data:
    .space PW_DATA_BYTES
    .text
