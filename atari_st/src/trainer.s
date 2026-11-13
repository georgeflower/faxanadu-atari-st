| The trainer (the author, 12 Nov 2026; in every build, the disk's too). T turns it on and off (sound $0B). While it is on nothing takes power off him
| (en_reduce_hp leaves the power as it is: enemies, their magic, a fall into nothing does not exist in this game) and the area and the screen are shown in
| the black margin left of the HUD, for debugging: "A1" and "S21" (cur_area; cur_screen, which with the whole areas is the ROM's own screen number, and in a
| building the building's). The flag is input_state's byte IN_TRAINER, which en_reduce_hp in .text reaches. Everything here is in .text.early.

    .section .text.early,"ax"

| Once a frame in the main loop: T newly pressed turns the trainer on or off.
trainer_key:
    movem.l %d0-%d1/%a0, -(%sp)
    lea input_state(%pc), %a0
    move.b IN_KEYS+0x14(%a0), %d1           | T
    lea trainer_down(%pc), %a0
    move.b (%a0), %d0
    move.b %d1, (%a0)
    tst.b %d0
    bne.s 9f
    tst.b %d1
    beq.s 9f
    lea input_state(%pc), %a0
    not.b IN_TRAINER(%a0)
    lea trainer_blank(%pc), %a0
    move.b #2, (%a0)                        | (turned off: blanks into both screens, then nothing)
    moveq #0x0B, %d0
    bsr.w sound_play_sfx
9:  movem.l (%sp)+, %d0-%d1/%a0
    rts

| a4 = the screen being drawn (before present_swap): the area and the screen in the margin left of the HUD, in white, or blanks when the trainer is off
| (so the words go when it is turned off). Two lines of four 8-pixel cells: x 0 to 31, lines 8 and 20.
trainer_draw:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea input_state(%pc), %a0
    tst.b IN_TRAINER(%a0)
    bne.s 4f
    lea trainer_blank(%pc), %a0             | off: blanks in the two frames after T, else nothing at all (no cycles in play)
    tst.b (%a0)
    beq.w 9f
    subq.b #1, (%a0)
4:  lea trainer_text(%pc), %a2
    move.l #0x20202020, (%a2)
    move.l #0x20202020, 4(%a2)
    lea input_state(%pc), %a0
    tst.b IN_TRAINER(%a0)
    beq.s 1f
    bsr.w text_color
    move.b #'A', (%a2)
    move.w cur_area(%pc), %d0
    andi.w #7, %d0
    addi.b #'0', %d0
    move.b %d0, 1(%a2)
    move.b #'S', 4(%a2)
    move.w cur_screen(%pc), %d0
    andi.l #0xFF, %d0
    divu #10, %d0
    addi.b #'0', %d0
    move.b %d0, 5(%a2)
    swap %d0
    addi.b #'0', %d0
    move.b %d0, 6(%a2)
1:  moveq #0, %d6
    moveq #0, %d5                           | the cell: 0 to 7
2:  move.b (%a2,%d5.w), %d0
    move.w %d5, %d1
    andi.w #3, %d1                          | column: cells 0, 1 in group 0 (bytes 0, 1), 2, 3 in group 1 (bytes 8, 9)
    move.w %d1, %d2
    andi.w #1, %d2
    lsr.w #1, %d1
    lsl.w #3, %d1
    add.w %d2, %d1
    move.w #8*160, %d2                      | line 8
    cmpi.w #4, %d5
    bcs.s 3f
    move.w #20*160, %d2                     | line 20
3:  add.w %d2, %d1
    lea (%a4,%d1.w), %a1
    bsr.w text_glyph
    addq.w #1, %d5
    cmpi.w #8, %d5
    bne.s 2b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

trainer_down:
    .byte 0
trainer_blank:
    .byte 0
    .even
trainer_text:
    .space 8
