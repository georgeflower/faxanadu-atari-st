| Text and the mantra's screens (included by viewer.s): the ROM's font, framed boxes of text, the message after a death, the mantra shown, the
| mantra entered (a grid of characters, as the ROM's password screen has) and the start menu.
|
| The font is the ROM's, 96 glyphs of 8 bytes (the characters 32 to 127, one bit a pixel); text_data holds it and then the texts (build_assets.py).
| A glyph is drawn in the brightest colour of the area's palette (the ROM draws white) on black; its x is a multiple of 8 (a byte of a plane).
| Boxes and text are drawn straight into the screen that is on show, while the game stands still; when a box goes the screens are made again
| (refresh_screens), so a box can lie over anything in the window of the playfield, but not the HUD.

    .equ BOX_PITCH, 10                      | lines between two lines of text
    .equ PAD_A, 0x80
    .equ PAD_B, 0x40
    .equ PAD_START, 0x10
    .equ PAD_UP, 0x08
    .equ PAD_DOWN, 0x04
    .equ PAD_LEFT, 0x02
    .equ PAD_RIGHT, 0x01
    .equ ENT_CELLS, 66                      | 64 characters, DEL and END

    .text
| text_planes: for each of the four planes a word, $FFFF when the text colour has that plane's bit. The text colour is the palette's brightest.
text_color:
    movem.l %d0-%d5/%a0-%a1, -(%sp)
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a0
    lea 2(%a0), %a0
    moveq #1, %d1                           | the colour looked at
    moveq #0, %d2                           | the brightest sum so far
    moveq #1, %d3                           | and its number
1:  move.w (%a0)+, %d0
    move.w %d0, %d4
    andi.w #7, %d4
    move.w %d0, %d5
    lsr.w #4, %d5
    andi.w #7, %d5
    add.w %d5, %d4
    lsr.w #8, %d0
    andi.w #7, %d0
    add.w %d0, %d4
    cmp.w %d2, %d4
    bls.s 2f
    move.w %d4, %d2
    move.w %d1, %d3
2:  addq.w #1, %d1
    cmpi.w #16, %d1
    bne.s 1b
    lea text_planes(%pc), %a0
    moveq #3, %d1
3:  moveq #0, %d0
    btst %d1, %d3
    beq.s 4f
    moveq #-1, %d0
4:  move.w %d0, (%a0)+
    dbra %d1, 3b
    movem.l (%sp)+, %d0-%d5/%a0-%a1
    rts

| One glyph: d0.b = the character, a1 = the cell's first line (the byte of plane 0), d6.b = $00, or $FF for light on dark turned round.
text_glyph:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    andi.w #0xFF, %d0
    subi.w #32, %d0
    cmpi.w #96, %d0
    bcs.s 1f
    moveq #0, %d0
1:  lsl.w #3, %d0
    lea text_data(%pc), %a2
    adda.w %d0, %a2
    lea text_planes(%pc), %a0
    moveq #7, %d4
2:  move.b (%a2)+, %d2
    eor.b %d6, %d2
    move.b %d2, %d3
    and.b 1(%a0), %d3
    move.b %d3, (%a1)
    move.b %d2, %d3
    and.b 3(%a0), %d3
    move.b %d3, 2(%a1)
    move.b %d2, %d3
    and.b 5(%a0), %d3
    move.b %d3, 4(%a1)
    move.b %d2, %d3
    and.b 7(%a0), %d3
    move.b %d3, 6(%a1)
    lea STRIDE(%a1), %a1
    dbra %d4, 2b
    movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts

| A text ended by a 0 byte (a line feed starts a line BOX_PITCH lines lower, under the first character): a0 = the text, a3 = the screen,
| d0 = x (a multiple of 8), d1 = y, d6 = 0 or $FF as in text_glyph. Keeps every register.
text_string:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    mulu.w #STRIDE, %d1
    move.w %d0, %d2
    lsr.w #4, %d2
    lsl.w #3, %d2
    move.w %d0, %d3
    lsr.w #3, %d3
    andi.w #1, %d3                          | 0: the left byte of a group of 16 pixels, 1: the right
    movea.l %a3, %a1
    adda.l %d1, %a1
    adda.w %d2, %a1
    adda.w %d3, %a1
    movea.l %a1, %a2                        | where this line began
    move.w %d3, %d4
1:  moveq #0, %d0
    move.b (%a0)+, %d0
    beq.s 9f
    cmpi.b #10, %d0
    bne.s 2f
    lea BOX_PITCH*STRIDE(%a2), %a2
    movea.l %a2, %a1
    move.w %d4, %d3
    bra.s 1b
2:  bsr.w text_glyph
    tst.w %d3
    bne.s 3f
    addq.l #1, %a1
    moveq #1, %d3
    bra.s 1b
3:  lea 7(%a1), %a1
    moveq #0, %d3
    bra.s 1b
9:  movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts

| A frame round black: a3 = the screen, d0 = the first group of 16 pixels, d1 = y, d2 = groups, d3 = lines. The frame is two pixels thick.
draw_box:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    mulu.w #STRIDE, %d1
    lsl.w #3, %d0
    lea (%a3,%d1.l), %a0
    adda.w %d0, %a0
    lea text_planes(%pc), %a2
    subq.w #1, %d2                          | the last group
    moveq #0, %d4                           | the line
1:  moveq #0, %d7                           | 1 on the top two and the bottom two lines
    cmpi.w #2, %d4
    bcs.s 2f
    move.w %d3, %d6
    subq.w #2, %d6
    cmp.w %d6, %d4
    bcs.s 3f
2:  moveq #1, %d7
3:  movea.l %a0, %a1
    moveq #0, %d5                           | the group
4:  moveq #0, %d0
    tst.w %d7
    beq.s 5f
    moveq #-1, %d0
    bra.s 7f
5:  tst.w %d5
    bne.s 6f
    move.w #0xC000, %d0
    bra.s 7f
6:  cmp.w %d2, %d5
    bne.s 7f
    move.w #0x0003, %d0
7:  move.w %d0, %d6
    and.w (%a2), %d6
    move.w %d6, (%a1)+
    move.w %d0, %d6
    and.w 2(%a2), %d6
    move.w %d6, (%a1)+
    move.w %d0, %d6
    and.w 4(%a2), %d6
    move.w %d6, (%a1)+
    move.w %d0, %d6
    and.w 6(%a2), %d6
    move.w %d6, (%a1)+
    addq.w #1, %d5
    cmp.w %d2, %d5
    ble.s 4b
    lea STRIDE(%a0), %a0
    addq.w #1, %d4
    cmp.w %d3, %d4
    bne.s 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| a3 = the screen that is on show (the one not being drawn into).
shown_screen:
    movea.l buf_a(%pc), %a3
    cmpa.l %a3, %a4
    bne.s 1f
    movea.l buf_b(%pc), %a3
1:  rts

| Waits for the A, B or Start button to be pressed (after all of them were let go), or for Esc.
wait_key:
    movem.l %d0/%a0, -(%sp)
    lea input_state(%pc), %a0
0:  bsr.w wait_vbl                         | a button that is down when the box comes does not count: it has to be let go first
    bsr.w input_poll
    tst.b IN_QUIT(%a0)
    bne.s 9f
    move.b IN_PAD(%a0), %d0
    andi.b #0xD0, %d0
    bne.s 0b
1:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 9f
    move.b IN_PAD_NEW(%a0), %d0
    andi.b #0xD0, %d0
    beq.s 1b
9:  movem.l (%sp)+, %d0/%a0
    rts

| The box goes: both screens are made again from the playfield.
box_leave:
    bsr.w refresh_screens
    bra.w refresh_screens

| A box of text in the middle of the window, until a button is pressed: a0 = the text (lines end with a line feed, up to 16 characters each).
message_box:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    bsr.w text_color
    bsr.w shown_screen
    bsr.w draw_text_box
    bsr.w wait_key
    bsr.w box_leave
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| Draws a0's text in a box 160 wide in the middle of the window, a3 = the screen.
draw_text_box:
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    moveq #1, %d4                           | the lines
    movea.l %a0, %a1
1:  move.b (%a1)+, %d0
    beq.s 3f
    cmpi.b #10, %d0
    bne.s 1b
    addq.w #1, %d4
    bra.s 1b
3:  move.w %d4, %d3
    mulu.w #BOX_PITCH, %d3
    addi.w #8, %d3                          | the height of the box: 4 above, 4 below the lines
    move.w #WINDOW_LINES, %d1
    sub.w %d3, %d1
    lsr.w #1, %d1
    addi.w #HUD_LINES, %d1                  | its y
    move.w %d1, %d4
    moveq #5, %d0
    moveq #10, %d2
    bsr.w draw_box
    moveq #0, %d6
    moveq #96, %d0
    move.w %d4, %d1
    addq.w #4, %d1
    bsr.w text_string
    movem.l (%sp)+, %d0-%d4/%a0-%a1
    rts

| The mantra on a box: the characters, 16 to a line, as the ROM shows it. Builds it from the game's state.
mantra_show:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    lea pw_block(%pc), %a1
    bsr.w pw_build
    movea.l %a1, %a0
    lea pw_text(%pc), %a1
    bsr.w pw_encode
    lea pw_lines(%pc), %a2                  | the characters, 16 to a line
    movea.l %a1, %a0
    moveq #0, %d1
1:  move.b (%a0)+, %d0
    beq.s 3f
    cmpi.w #16, %d1
    bne.s 2f
    move.b #10, (%a2)+
2:  move.b %d0, (%a2)+
    addq.w #1, %d1
    bra.s 1b
3:  clr.b (%a2)
    lea pw_lines(%pc), %a0
    bsr.w message_box
    movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| a1 = a state block: what the game has, as the ROM's password holds it: the rank, the spawn point, the special items and quests, what he wears
| and the spell and item chosen, and the lists of what he carries (items.s: inv).
pw_build:
    movem.l %d0-%d2/%a0-%a3, -(%sp)
    moveq #PW_STATE_BYTES-1, %d0
    movea.l %a1, %a0
1:  clr.b (%a0)+
    dbra %d0, 1b
    lea inv(%pc), %a2
    move.w hero_spawn(%pc), %d0
    move.b %d0, PW_SPAWN(%a1)
    move.w hero_title(%pc), %d0
    move.b %d0, PW_RANK(%a1)
    move.b INV_SPECIAL(%a2), PW_SPECIAL(%a1)
    move.b INV_QUESTS(%a2), PW_QUESTS(%a1)
    move.w hero_weapon(%pc), %d0
    move.b %d0, PW_WEAPON(%a1)
    move.b INV_ARMOUR(%a2), PW_ARMOUR(%a1)
    move.b INV_SHIELD(%a2), PW_SHIELD(%a1)
    move.b INV_ITEM(%a2), PW_ITEM(%a1)
    move.w hero_magic(%pc), %d0
    bmi.s 2f
    move.b %d0, PW_SPELL(%a1)
    bra.s 3f
2:  move.b #0xFF, PW_SPELL(%a1)
3:  moveq #0, %d2                           | the lists: weapons, armours, shields, spells, items
4:  moveq #0, %d1
    move.b INV_NWEAPONS(%a2,%d2.w), %d1
    move.w %d2, %d0
    mulu.w #5, %d0
    lea PW_WEAPONS(%a1,%d0.w), %a0
    move.b %d1, (%a0)+
    move.w %d2, %d0
    lsl.w #2, %d0
    lea (%a2,%d0.w), %a3
    subq.w #1, %d1
    bmi.s 6f
5:  move.b (%a3)+, %d0
    andi.b #31, %d0                         | (the category is in the item's byte, not in the mantra)
    move.b %d0, (%a0)+
    dbra %d1, 5b
6:  addq.w #1, %d2
    cmpi.w #5, %d2
    bcs.s 4b
    movem.l (%sp)+, %d0-%d2/%a0-%a3
    rts

| a1 = a state block that was read from a mantra: the game takes what the ROM does from a password (the rank, the spawn point, the special items
| and quests, what he wears, the spell and item chosen, the lists), and starts again as after a death (full power and magic, the gold and
| experience of the rank, the start screen).
mantra_apply:
    movem.l %d0-%d3/%a0-%a3, -(%sp)
    moveq #0, %d0
    move.b PW_RANK(%a1), %d0
    lea hero_title(%pc), %a0
    move.w %d0, (%a0)
    lea hero_next(%pc), %a0
    move.w %d0, (%a0)
    moveq #0, %d0
    move.b PW_SPAWN(%a1), %d0
    lea hero_spawn(%pc), %a0
    move.w %d0, (%a0)
    moveq #-1, %d0
    cmpi.b #0xFF, PW_SPELL(%a1)
    beq.s 1f
    moveq #0, %d0
    move.b PW_SPELL(%a1), %d0
1:  lea hero_magic(%pc), %a0
    move.w %d0, (%a0)
    moveq #0, %d0
    move.b PW_WEAPON(%a1), %d0
    lea hero_weapon(%pc), %a0
    move.w %d0, (%a0)
    lea inv(%pc), %a2
    move.b PW_SPECIAL(%a1), INV_SPECIAL(%a2)
    move.b PW_QUESTS(%a1), INV_QUESTS(%a2)
    move.b PW_ARMOUR(%a1), INV_ARMOUR(%a2)
    move.b PW_SHIELD(%a1), INV_SHIELD(%a2)
    move.b PW_ITEM(%a1), INV_ITEM(%a2)
    moveq #0, %d2
2:  moveq #0, %d1
    move.w %d2, %d0
    mulu.w #5, %d0
    lea PW_WEAPONS(%a1,%d0.w), %a0
    move.b (%a0)+, %d1
    move.b %d1, INV_NWEAPONS(%a2,%d2.w)
    move.w %d2, %d0
    lsl.w #2, %d0
    lea (%a2,%d0.w), %a3
    move.w %d2, %d3
    lsl.w #5, %d3                           | the category * 32 is the high part of an item's byte
    subq.w #1, %d1
    bmi.s 4f
3:  move.b (%a0)+, %d0
    or.b %d3, %d0
    move.b %d0, (%a3)+
    dbra %d1, 3b
4:  addq.w #1, %d2
    cmpi.w #5, %d2
    bcs.s 2b
    bsr.w hero_respawn
    movem.l (%sp)+, %d0-%d3/%a0-%a3
    rts

| The P key shows the mantra (the ROM shows it when a Guru of a temple meditates with him; there are no Gurus yet).
mantra_key:
    movem.l %d0-%d1/%a0, -(%sp)
    moveq #0, %d1
    lea input_state+IN_KEYS+0x19(%pc), %a0 | P
    tst.b (%a0)
    beq.s 1f
    moveq #1, %d1
1:  lea mantra_down(%pc), %a0
    move.w (%a0), %d0
    move.w %d1, (%a0)
    tst.w %d0
    bne.s 9f
    tst.w %d1
    beq.s 9f
    move.w hero_dead(%pc), %d0
    bne.s 9f
    bsr.w mantra_show
9:  movem.l (%sp)+, %d0-%d1/%a0
    rts

| ------------------------------------------------------------------------------------------------------------------ entering a mantra
    .equ ENT_X, 96                          | the left of the grid and of the text
    .equ ENT_INPUT_Y, 62
    .equ ENT_STATUS_Y, 84
    .equ ENT_GRID_Y, 98
    .equ ENT_LAST_Y, 178                    | DEL and END

| The screen that is on show gets the mantra's entry (a grid of the 64 characters, DEL and END; the stick moves, A or B (the stick's one fire button)
| takes the cell, Start is END). On return d0 = 1 when a mantra was accepted (pw_block holds its state) or 0 when it was given up (END with nothing
| written, or Esc). The box stays on show: the caller takes it away (box_leave).
mantra_entry:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    bsr.w text_color
    bsr.w shown_screen
    lea ent_len(%pc), %a0
    clr.w (%a0)
    clr.w 2(%a0)                            | the cell
    clr.w 4(%a0)                            | 1 after a wrong mantra
    lea ent_text(%pc), %a0
    clr.b (%a0)
    moveq #2, %d0                           | the box: groups 2 to 17, lines 36 to 196
    moveq #36, %d1
    moveq #16, %d2
    move.w #160, %d3
    bsr.w draw_box
    moveq #0, %d6
    lea text_data+TEXT_ASK(%pc), %a0
    move.w #88, %d0
    moveq #44, %d1
    bsr.w text_string
    moveq #0, %d4
1:  move.w %d4, %d0                         | the grid
    bsr.w ent_cell
    addq.w #1, %d4
    cmpi.w #ENT_CELLS, %d4
    bne.s 1b
    moveq #0, %d0
    moveq #-1, %d6
    bsr.w ent_cell                          | (the cursor in the first cell)
    bsr.w ent_input
    bsr.w ent_status
2:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.w 8f
    moveq #0, %d5
    move.b IN_PAD_NEW(%a0), %d5
    beq.s 2b
    move.w ent_cell_no(%pc), %d4
    btst #6, %d5                            | B or A (the stick has the one fire button): the cell
    bne.s 21f
    btst #7, %d5
    bne.s 21f
    btst #4, %d5                            | Start: END
    bne.s 22f
    btst #3, %d5                            | up
    beq.s 3f
    subq.w #8, %d4
    bpl.s 9f
    addi.w #64, %d4
    cmpi.w #ENT_CELLS, %d4
    bcs.s 9f
    subq.w #8, %d4                          | (the last row has two cells only)
    bra.s 9f
3:  btst #2, %d5                            | down
    beq.s 4f
    addq.w #8, %d4
    cmpi.w #ENT_CELLS, %d4
    bcs.s 9f
    andi.w #7, %d4
    bra.s 9f
4:  btst #1, %d5                            | left
    beq.s 5f
    subq.w #1, %d4
    bpl.s 9f
    moveq #ENT_CELLS-1, %d4
    bra.s 9f
5:  btst #0, %d5                            | right
    beq.s 2b
    addq.w #1, %d4
    cmpi.w #ENT_CELLS, %d4
    bcs.s 9f
    moveq #0, %d4
9:  move.w ent_cell_no(%pc), %d0            | the cursor moves
    moveq #0, %d6
    bsr.w ent_cell
    lea ent_cell_no(%pc), %a0
    move.w %d4, (%a0)
    move.w %d4, %d0
    moveq #-1, %d6
    bsr.w ent_cell
    bra.w 2b
20: bsr.w ent_back
    bra.w 2b
21: cmpi.w #64, %d4
    bcs.s 23f
    beq.s 20b
22: bsr.w ent_end                           | d0 = 1 accepted, 0 given up, -1 a wrong one
    tst.w %d0
    bpl.s 90f
    bra.w 2b
23: bsr.w ent_add
    bra.w 2b
8:  moveq #0, %d0
90: movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

| One cell of the grid: d0 = its number (0-63 a character, 64 DEL, 65 END), d6 = 0, or $FF for the one the cursor is on. a3 = the screen.
ent_cell:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    cmpi.w #64, %d0
    bcc.s 2f
    lea pw_chars(%pc), %a0
    lea ent_one(%pc), %a1
    move.b (%a0,%d0.w), (%a1)
    clr.b 1(%a1)
    movea.l %a1, %a0
    move.w %d0, %d1
    andi.w #7, %d1
    lsl.w #4, %d1
    addi.w #ENT_X, %d1                      | x
    lsr.w #3, %d0
    mulu.w #BOX_PITCH, %d0
    addi.w #ENT_GRID_Y, %d0                 | y
    move.w %d0, %d2
    move.w %d1, %d0
    move.w %d2, %d1
    bsr.w text_string
    bra.s 9f
2:  lea str_del(%pc), %a0
    move.w #ENT_X, %d1
    cmpi.w #64, %d0
    beq.s 4f
    lea str_end(%pc), %a0
    move.w #ENT_X+40, %d1
4:  move.w %d1, %d0
    move.w #ENT_LAST_Y, %d1
    bsr.w text_string
9:  movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

| The 32 places of the mantra written so far (two lines of 16), and a line under the next one to take a character.
ent_input:
    movem.l %d0-%d4/%a0/%a2, -(%sp)
    moveq #0, %d6
    lea ent_text(%pc), %a2
    lea ent_one(%pc), %a0
    clr.b 1(%a0)
    move.w ent_len(%pc), %d3
    moveq #0, %d4
1:  moveq #' ', %d0
    cmp.w %d3, %d4
    bge.s 2f
    move.b (%a2,%d4.w), %d0
    bra.s 3f
2:  bne.s 3f
    moveq #'_', %d0
3:  move.b %d0, (%a0)
    move.w %d4, %d0
    andi.w #15, %d0
    lsl.w #3, %d0
    addi.w #ENT_X, %d0                      | x
    moveq #ENT_INPUT_Y, %d1
    btst #4, %d4
    beq.s 4f
    addi.w #BOX_PITCH, %d1
4:  bsr.w text_string
    addq.w #1, %d4
    cmpi.w #PW_MAX_CHARS, %d4
    bne.s 1b
    movem.l (%sp)+, %d0-%d4/%a0/%a2
    rts

| The line for a wrong mantra (the ROM's message), or a blank one.
ent_status:
    movem.l %d0-%d1/%a0, -(%sp)
    moveq #0, %d6
    lea str_blank(%pc), %a0
    move.w ent_bad(%pc), %d0
    beq.s 1f
    lea text_data+TEXT_WRONG(%pc), %a0
1:  move.w #64, %d0
    moveq #ENT_STATUS_Y, %d1
    bsr.w text_string
    movem.l (%sp)+, %d0-%d1/%a0
    rts

| A: the cell's character is added (d4 = the cell).
ent_add:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    move.w ent_len(%pc), %d0
    cmpi.w #PW_MAX_CHARS, %d0
    bcc.s 9f
    lea pw_chars(%pc), %a0
    lea ent_text(%pc), %a1
    move.b (%a0,%d4.w), %d1
    move.b %d1, (%a1,%d0.w)
    clr.b 1(%a1,%d0.w)
    addq.w #1, %d0
    lea ent_len(%pc), %a0
    move.w %d0, (%a0)
    clr.w 4(%a0)
    bsr.w ent_input
    bsr.w ent_status
9:  movem.l (%sp)+, %d0-%d1/%a0-%a1
    rts

| DEL: the last character goes.
ent_back:
    movem.l %d0/%a0-%a1, -(%sp)
    move.w ent_len(%pc), %d0
    beq.s 9f
    subq.w #1, %d0
    lea ent_text(%pc), %a1
    clr.b (%a1,%d0.w)
    lea ent_len(%pc), %a0
    move.w %d0, (%a0)
    clr.w 4(%a0)
    bsr.w ent_input
    bsr.w ent_status
9:  movem.l (%sp)+, %d0/%a0-%a1
    rts

| END: d0 = 0 with nothing written, 1 when the game accepts the mantra (its state is in pw_block), -1 when it does not (the message appears).
ent_end:
    movem.l %d1/%a0-%a1, -(%sp)
    moveq #0, %d0
    move.w ent_len(%pc), %d1
    beq.s 9f
    lea ent_text(%pc), %a0
    lea pw_block(%pc), %a1
    bsr.w pw_decode
    tst.w %d0
    bne.s 1f
    moveq #1, %d0
    bra.s 9f
1:  lea ent_bad(%pc), %a0
    move.w #1, (%a0)
    bsr.w ent_status
    moveq #-1, %d0
9:  movem.l (%sp)+, %d1/%a0-%a1
    rts

| ------------------------------------------------------------------------------------------------------------------ the start menu
| (MENU) Before the game: start, or enter a mantra. Up and down choose, A, B or Start takes it.
start_menu:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea menu_sel(%pc), %a0
    clr.w (%a0)
    bsr.w menu_draw
1:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.w 9f
    moveq #0, %d0
    move.b IN_PAD_NEW(%a0), %d0
    beq.s 1b
    btst #3, %d0
    bne.s 2f
    btst #2, %d0
    bne.s 2f
    andi.b #0xD0, %d0
    beq.s 1b
    move.w menu_sel(%pc), %d1
    beq.s 8f                                | Start
    bsr.w mantra_entry
    tst.w %d0
    beq.s 3f
    bsr.w box_leave                         | accepted: the game begins as after a death, with what the mantra holds
    lea pw_block(%pc), %a1
    bsr.w mantra_apply
    bra.s 9f
3:  bsr.w box_leave                         | given up: back to the menu
    bsr.w menu_draw
    bra.s 1b
2:  lea menu_sel(%pc), %a0
    eori.w #1, (%a0)
    bsr.w menu_draw
    bra.s 1b
8:  bsr.w box_leave
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

menu_draw:
    movem.l %d0-%d4/%a0-%a3, -(%sp)
    bsr.w text_color
    bsr.w shown_screen
    moveq #5, %d0
    moveq #88, %d1
    moveq #10, %d2
    moveq #56, %d3
    bsr.w draw_box
    moveq #0, %d6
    move.w menu_sel(%pc), %d1
    bne.s 1f
    moveq #-1, %d6
1:  lea str_start(%pc), %a0
    moveq #104, %d0
    moveq #96, %d1
    bsr.w text_string
    moveq #0, %d6
    move.w menu_sel(%pc), %d1
    beq.s 2f
    moveq #-1, %d6
2:  lea str_enter(%pc), %a0
    moveq #104, %d0
    moveq #114, %d1
    bsr.w text_string
    movem.l (%sp)+, %d0-%d4/%a0-%a3
    rts

    .section .rodata
text_data:
    .incbin "text.bin"
str_del:
    .asciz "DEL"
str_end:
    .asciz "END"
str_start:
    .asciz "Start"
str_enter:
    .asciz "Enter mantra"
str_blank:
    .asciz "                       "
    .even

    .section .data
text_planes:
    .space 8
hero_spawn:
    .word 0                                 | TempleSpawnPoint: which temple he starts from (there are no temples yet; the mantra keeps it)
mantra_down:
    .word 0
menu_sel:
    .word 0
ent_len:
    .word 0
ent_cell_no:
    .word 0
ent_bad:
    .word 0
ent_text:
    .space 36
ent_one:
    .space 2
pw_block:
    .space PW_STATE_BYTES
pw_text:
    .space 36
pw_lines:
    .space 40
    .even
    .text
