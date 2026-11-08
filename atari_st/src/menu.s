| The player menu (the ROM's PlayerMenu_Show, Select/Tab): a box of six entries; the first five open a box of what he owns in that category (weapons, armours,
| shields, spells, items) and choosing one wears it (Player_Equip: what was worn goes back into the list); inside a building nothing can be changed, and with
| the Dragon Slayer on, nothing but the spells and items. The inventory is the block `inv` (items.s); the lists hold what is not worn. tools/enemy_model.py
| (`menu_choose`, `equip`) is the reference and tests/test_menu.py checks it against the game.
|
| An item is a byte: the category (0 weapon, 1 armour, 2 shield, 3 spell, 4 item) times 32 and its number. The worn weapon is hero_weapon and the worn
| spell hero_magic (words, so that the other code can use them), the rest are bytes of `inv`.

| d0.b = the item. d1 = its place among the special items (they are not in a list, they are a bit of INV_SPECIAL), -1 if it is not one. Keeps d0.
inv_special_index:
    movem.l %a0, -(%sp)
    lea special_ids(%pc), %a0
    moveq #7, %d1
1:  cmp.b (%a0,%d1.w), %d0
    beq.s 2f
    dbra %d1, 1b
2:  movem.l (%sp)+, %a0
    rts

| d1.w = the category: d0.b = what is worn of it ($FF nothing).
inv_selected:
    tst.w %d1
    bne.s 1f
    move.w hero_weapon(%pc), %d0
    rts
1:  cmpi.w #1, %d1
    bne.s 2f
    move.b inv+INV_ARMOUR(%pc), %d0
    rts
2:  cmpi.w #2, %d1
    bne.s 3f
    move.b inv+INV_SHIELD(%pc), %d0
    rts
3:  cmpi.w #3, %d1
    bne.s 4f
    move.w hero_magic(%pc), %d0
    rts
4:  move.b inv+INV_ITEM(%pc), %d0
    rts

| d1.w = the category, d2.b = the number: it is worn from now on.
inv_set_selected:
    movem.l %d0/%a0, -(%sp)
    moveq #0, %d0
    move.b %d2, %d0
    tst.w %d1
    bne.s 1f
    lea hero_weapon(%pc), %a0
    move.w %d0, (%a0)
    bra.s 9f
1:  cmpi.w #3, %d1
    bne.s 2f
    lea hero_magic(%pc), %a0
    move.w %d0, (%a0)
    bra.s 9f
2:  lea inv(%pc), %a0
    cmpi.w #1, %d1
    bne.s 3f
    move.b %d0, INV_ARMOUR(%a0)
    bra.s 9f
3:  cmpi.w #2, %d1
    bne.s 4f
    move.b %d0, INV_SHIELD(%a0)
    bra.s 9f
4:  move.b %d0, INV_ITEM(%a0)
9:  movem.l (%sp)+, %d0/%a0
    rts

| Player_RemoveItem: d0.b = the item, it goes out of its list (or its special bit is cleared).
inv_remove:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    lea inv(%pc), %a2
    bsr.w inv_special_index
    tst.w %d1
    bmi.s 1f
    lea special_masks(%pc), %a0
    move.b (%a0,%d1.w), %d1
    not.b %d1
    and.b %d1, INV_SPECIAL(%a2)
    bra.s 9f
1:  moveq #0, %d1
    move.b %d0, %d1
    lsr.b #5, %d1                           | the category
    andi.b #0x1F, %d0
    moveq #0, %d2
    move.b INV_NWEAPONS(%a2,%d1.w), %d2     | how many
    beq.s 9f
    move.w %d1, %d3
    lsl.w #2, %d3
    lea (%a2,%d3.w), %a1                    | the list
    moveq #0, %d4
2:  cmp.b (%a1,%d4.w), %d0
    beq.s 3f
    addq.w #1, %d4
    cmp.w %d2, %d4
    bne.s 2b
    bra.s 9f
3:  addq.w #1, %d4                          | the ones after it move up
    cmp.w %d2, %d4
    beq.s 4f
    move.b (%a1,%d4.w), -1(%a1,%d4.w)
    bra.s 3b
4:  subq.b #1, INV_NWEAPONS(%a2,%d1.w)
9:  movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts

| Player_AddToInventory: d0.b = the item; in a full list the last place goes.
inv_add:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea inv(%pc), %a2
    bsr.w inv_special_index
    tst.w %d1
    bmi.s 1f
    lea special_masks(%pc), %a0
    move.b (%a0,%d1.w), %d1
    or.b %d1, INV_SPECIAL(%a2)
    bra.s 9f
1:  moveq #0, %d1
    move.b %d0, %d1
    lsr.b #5, %d1
    andi.b #0x1F, %d0
    moveq #4, %d2                           | the most it holds
    cmpi.w #4, %d1
    bne.s 2f
    moveq #8, %d2
2:  moveq #0, %d3
    move.b INV_NWEAPONS(%a2,%d1.w), %d3
    cmp.w %d2, %d3
    bne.s 3f
    subq.w #1, %d3
3:  move.w %d1, %d2
    lsl.w #2, %d2
    lea (%a2,%d2.w), %a1
    move.b %d0, (%a1,%d3.w)
    addq.b #1, %d3
    move.b %d3, INV_NWEAPONS(%a2,%d1.w)
9:  movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

| Player_LacksItem: d0.b = the item; d0.w = 1 when he neither wears it nor has it in a list.
inv_lacks:
    movem.l %d1-%d4/%a0-%a2, -(%sp)
    lea inv(%pc), %a2
    bsr.w inv_special_index
    tst.w %d1
    bmi.s 1f
    lea special_masks(%pc), %a0
    move.b (%a0,%d1.w), %d1
    and.b INV_SPECIAL(%a2), %d1
    seq %d0
    andi.w #1, %d0
    bra.s 9f
1:  move.b %d0, %d4
    andi.b #0x1F, %d4                       | the number
    moveq #0, %d1
    move.b %d0, %d1
    lsr.b #5, %d1
    bsr.w inv_selected
    cmp.b %d4, %d0
    beq.s 8f                                | worn
    moveq #0, %d2
    move.b INV_NWEAPONS(%a2,%d1.w), %d2
    move.w %d1, %d3
    lsl.w #2, %d3
    lea (%a2,%d3.w), %a1
    bra.s 3f
2:  cmp.b (%a1)+, %d4
    beq.s 8f
3:  dbra %d2, 2b
    moveq #1, %d0
    bra.s 9f
8:  moveq #0, %d0
9:  movem.l (%sp)+, %d1-%d4/%a0-%a2
    rts

| Player_Equip: d0.b = the item. It is taken out of its list, what was worn goes in, and it is worn.
inv_equip:
    movem.l %d0-%d2/%d5-%d6, -(%sp)
    move.b %d0, %d5
    moveq #0, %d1
    move.b %d0, %d1
    lsr.b #5, %d1
    bsr.w inv_selected
    move.b %d0, %d6                         | what was worn
    move.b %d5, %d0
    bsr.w inv_remove
    tst.b %d6
    bmi.s 1f
    move.b %d5, %d0
    andi.b #0xE0, %d0
    or.b %d6, %d0
    bsr.w inv_add
1:  move.b %d5, %d2
    andi.b #0x1F, %d2
    bsr.w inv_set_selected
    movem.l (%sp)+, %d0-%d2/%d5-%d6
    rts

| A to choose the entry d6 of the category d5: d0.w = 1 when it is worn now (sound 8), 0 for an invalid choice (sound 13).
menu_choose:
    movem.l %d1-%d4/%a1-%a2, -(%sp)
    move.w cur_area(%pc), %d0
    cmpi.w #4, %d0                          | inside a building nothing can be changed
    beq.s 8f
    lea inv(%pc), %a2
    move.w %d5, %d1
    lsl.w #2, %d1
    lea (%a2,%d1.w), %a1
    moveq #0, %d4
    move.b (%a1,%d6.w), %d4                 | its number
    cmpi.w #3, %d5
    bcc.s 5f
    move.w hero_weapon(%pc), %d0
    cmpi.w #3, %d0                          | with the Dragon Slayer in his hand
    beq.s 8f
    cmpi.b #3, %d4
    bne.s 5f
    moveq #0x03, %d0                        | the Dragon Slayer, the Battle Suit and the Battle Helmet go on together, and only when he has all three
    bsr.w inv_lacks
    tst.w %d0
    bne.s 8f
    moveq #0x23, %d0
    bsr.w inv_lacks
    tst.w %d0
    bne.s 8f
    moveq #0x43, %d0
    bsr.w inv_lacks
    tst.w %d0
    bne.s 8f
    moveq #8, %d0
    bsr.w menu_sound
    moveq #0x03, %d0
    bsr.w inv_equip
    moveq #0x23, %d0
    bsr.w inv_equip
    moveq #0x43, %d0
    bsr.w inv_equip
    bra.s 7f
5:  moveq #8, %d0
    bsr.w menu_sound
    move.w %d5, %d0
    lsl.w #5, %d0
    or.b %d4, %d0
    bsr.w inv_equip
7:  moveq #1, %d0
    bra.s 9f
8:  moveq #13, %d0
    bsr.w menu_sound
    moveq #0, %d0
9:  movem.l (%sp)+, %d1-%d4/%a1-%a2
    rts

| ---------------------------------------------------------------------------------------------------------------------- the boxes
| The sound d0 (keeps everything).
menu_sound:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    bsr.w sound_play_sfx
    movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| Waits for a new press of Up, Down, A or B: d0 = the pad's bits ($08, $04, $80, $40), or $100 when Esc was pressed.
menu_input:
    movem.l %a0, -(%sp)
1:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 8f
    moveq #0, %d0
    move.b IN_PAD_NEW(%a0), %d0
    andi.b #0xCC, %d0
    beq.s 1b
    bra.s 9f
8:  move.w #0x100, %d0
9:  movem.l (%sp)+, %a0
    rts

| The text with its offset in text_data (a word of the table at a0, entry d0.w) at x = d1, y = d2 (a3 = the screen).
menu_text:
    movem.l %d0-%d2/%d6/%a0-%a1, -(%sp)
    add.w %d0, %d0
    move.w (%a0,%d0.w), %d0
    lea text_data(%pc), %a0
    adda.w %d0, %a0
    move.w %d1, %d0
    move.w %d2, %d1
    moveq #0, %d6
    bsr.w text_string
    movem.l (%sp)+, %d0-%d2/%d6/%a0-%a1
    rts

| The arrow at x = d1, y = d2.
menu_arrow:
    movem.l %d0-%d1/%d6/%a0, -(%sp)
    lea menu_arrow_text(%pc), %a0
    move.w %d1, %d0
    move.w %d2, %d1
    moveq #0, %d6
    bsr.w text_string
    movem.l (%sp)+, %d0-%d1/%d6/%a0
    rts

| The top menu with the cursor on d4.
menu_draw_top:
    movem.l %d0-%d3/%a0, -(%sp)
    moveq #3, %d0
    moveq #48, %d1
    moveq #5, %d2
    moveq #112, %d3
    bsr.w draw_box
    lea menu_top_texts(%pc), %a0
    moveq #0, %d3
1:  move.w %d3, %d0
    moveq #72, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #56, %d2
    bsr.w menu_text
    cmp.w %d4, %d3
    bne.s 2f
    moveq #56, %d1
    bsr.w menu_arrow
2:  addq.w #1, %d3
    cmpi.w #6, %d3
    bne.s 1b
    movem.l (%sp)+, %d0-%d3/%a0
    rts

| The box of the category d5 with its list: d6 = the cursor, d7 = how many, a1 = the list.
menu_draw_list:
    movem.l %d0-%d4/%a0/%a2, -(%sp)
    moveq #4, %d0
    moveq #40, %d1
    moveq #10, %d2
    move.w #144, %d3
    bsr.w draw_box
    lea menu_name_texts(%pc), %a0
    lea name_base(%pc), %a2
    moveq #0, %d4
    move.b (%a2,%d5.w), %d4                 | the first name of the category
    moveq #0, %d3
1:  cmp.w %d7, %d3
    bcc.s 9f
    moveq #0, %d0
    move.b (%a1,%d3.w), %d0
    add.w %d4, %d0                          | the name
    moveq #96, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #48, %d2
    bsr.w menu_text
    cmp.w %d6, %d3
    bne.s 2f
    moveq #80, %d1
    bsr.w menu_arrow
2:  addq.w #1, %d3
    bra.s 1b
9:  movem.l (%sp)+, %d0-%d4/%a0/%a2
    rts

| Tab (Select) opens the player menu, unless he is dead.
menu_key:
    movem.l %d0/%a0, -(%sp)
    lea input_state(%pc), %a0
    btst #5, IN_PAD_NEW(%a0)
    beq.s 9f
    move.w hero_dead(%pc), %d0
    bne.s 9f
    bsr.w player_menu
9:  movem.l (%sp)+, %d0/%a0
    rts

| The player menu: Select. Draws on the screen that is on show while the game stands still, as the message boxes do.
player_menu:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    moveq #0x18, %d0
    bsr.w menu_sound
    bsr.w text_color
    bsr.w shown_screen
    moveq #0, %d4
1:  bsr.w menu_draw_top
    bsr.w menu_input
    btst #8, %d0
    bne.w 9f
    btst #6, %d0                            | B: out
    bne.w 9f
    btst #7, %d0
    bne.s 5f
    move.w %d0, -(%sp)
    moveq #11, %d0
    bsr.w menu_sound
    move.w (%sp)+, %d0
    btst #3, %d0                            | Up
    beq.s 2f
    subq.w #1, %d4
    bpl.s 1b
    moveq #5, %d4
    bra.s 1b
2:  addq.w #1, %d4
    cmpi.w #6, %d4
    bne.s 1b
    moveq #0, %d4
    bra.s 1b
5:  cmpi.w #5, %d4                          | (the last entry, the player's status, is not made yet)
    beq.s 1b
    move.w %d4, %d5
    bsr.w menu_category
9:  bsr.w box_leave
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| The box of the category d5 and its choice: A on an entry wears it (and the menu is done), B or Esc leave.
menu_category:
    movem.l %d3/%d6-%d7/%a1-%a2, -(%sp)
    lea inv(%pc), %a2
    moveq #0, %d7
    move.b INV_NWEAPONS(%a2,%d5.w), %d7
    move.w %d5, %d1
    lsl.w #2, %d1
    lea (%a2,%d1.w), %a1
    moveq #0, %d6
    tst.w %d7
    bne.s 1f
    moveq #4, %d0                           | nothing in this category: "NO WEAPON" and so on until B
    moveq #40, %d1
    moveq #10, %d2
    move.w #144, %d3
    bsr.w draw_box
    lea menu_none_texts(%pc), %a0
    move.w %d5, %d0
    moveq #96, %d1
    moveq #56, %d2
    bsr.w menu_text
2:  bsr.w menu_input
    btst #8, %d0
    bne.s 9f
    btst #6, %d0
    beq.s 2b
    bra.s 9f
1:  bsr.w menu_draw_list
    bsr.w menu_input
    btst #8, %d0
    bne.s 9f
    btst #6, %d0
    bne.s 9f
    btst #7, %d0
    bne.s 5f
    move.w %d0, -(%sp)
    moveq #11, %d0
    bsr.w menu_sound
    move.w (%sp)+, %d0
    btst #3, %d0
    beq.s 3f
    subq.w #1, %d6
    bpl.s 1b
    move.w %d7, %d6
    subq.w #1, %d6
    bra.s 1b
3:  addq.w #1, %d6
    cmp.w %d7, %d6
    bne.s 1b
    moveq #0, %d6
    bra.s 1b
5:  bsr.w menu_choose
    tst.w %d0
    beq.s 1b
9:  movem.l (%sp)+, %d3/%d6-%d7/%a1-%a2
    rts

    .section .rodata
    .even
special_ids:                                | Ring of Elf, Ruby Ring, Ring of Dworf, Demon's Ring, Elixir, Magical Rod, Pendant, Black Onyx
    .byte 0x80, 0x81, 0x82, 0x83, 0x92, 0x8A, 0x93, 0x94
special_masks:
    .byte 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
name_base:                                  | where the names of a category start in menu_name_texts
    .byte 0, 4, 8, 12, 17
menu_arrow_text:
    .asciz ">"
    .even
menu_top_texts:
    .word TEXT_TOP_0, TEXT_TOP_1, TEXT_TOP_2, TEXT_TOP_3, TEXT_TOP_4, TEXT_TOP_5
menu_none_texts:
    .word TEXT_NONE_0, TEXT_NONE_1, TEXT_NONE_2, TEXT_NONE_3, TEXT_NONE_4
menu_name_texts:
    .word TEXT_NAME_0, TEXT_NAME_1, TEXT_NAME_2, TEXT_NAME_3, TEXT_NAME_4, TEXT_NAME_5, TEXT_NAME_6, TEXT_NAME_7, TEXT_NAME_8, TEXT_NAME_9, TEXT_NAME_10, TEXT_NAME_11, TEXT_NAME_12, TEXT_NAME_13, TEXT_NAME_14, TEXT_NAME_15, TEXT_NAME_16, TEXT_NAME_17, TEXT_NAME_18, TEXT_NAME_19, TEXT_NAME_20, TEXT_NAME_21, TEXT_NAME_22, TEXT_NAME_23, TEXT_NAME_24, TEXT_NAME_25, TEXT_NAME_26, TEXT_NAME_27, TEXT_NAME_28, TEXT_NAME_29, TEXT_NAME_30, TEXT_NAME_31, TEXT_NAME_32, TEXT_NAME_33, TEXT_NAME_34, TEXT_NAME_35, TEXT_NAME_36, TEXT_NAME_37, TEXT_NAME_38
    .even
    .text
