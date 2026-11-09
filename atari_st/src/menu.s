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
    andi.w #0x1F, %d0                       | (a list entry is the number; the category bits some code leaves on it are not)
    add.w %d4, %d0                          | the name (and the picture: the same number)
    moveq #80, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #44, %d2
    bsr.w item_draw                         | the picture, 16 by 16, centred on the line of the name
    moveq #96, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #48, %d2
    bsr.w menu_text
    cmp.w %d6, %d3
    bne.s 2f
    moveq #72, %d1
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
    move.w cur_area(%pc), %d0               | GameLoop_CheckShowPlayerMenu: not on Eolis's first screen (the ROM's screen 0 of area 0, outside the walls)
    bne.s 1f
    move.w cur_screen(%pc), %d0
    cmpi.w #EOLIS_START_SCREEN, %d0
    beq.s 9f
1:  bsr.w player_menu
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
5:  cmpi.w #5, %d4                          | the last entry, the player's status: B closes the whole menu
    bne.s 6f
    bsr.w menu_status
    bra.s 9f
6:  move.w %d4, %d5
    bsr.w menu_category
9:  bsr.w hud_mark                          | what he holds may have changed: the HUD's picture
    bsr.w box_leave
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

| ---------------------------------------------------------------------------------------------------------------------- item pictures
    .equ ITEMS_PICTURES, 112                | items.bin (tools/itempics.py): 28 palette sets x 4 slots, then 39 pictures x 4 tile numbers, the Mattock's table (32 bytes),
    .equ ITEMS_MATTOCK, 268                 | then the tiles (16 bytes each)
    .equ ITEMS_TILES, 300

| d0.w = a tile of items.bin, a1 = where its 32 bytes go (8 lines of four plane bytes). The tile's colours 0-3 take the slots of the HUD's palette in the palette set
| in use (the same as the HUD's own tiles). Keeps every register (a1 as it was).
item_tile:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea items_data(%pc), %a0
    move.w cur_pal(%pc), %d1
    bpl.s 1f
    moveq #0, %d1
1:  lsl.w #2, %d1
    lea (%a0,%d1.w), %a2                    | the slots of the four colours
    lsl.w #4, %d0
    lea ITEMS_TILES(%a0), %a0
    adda.w %d0, %a0                         | the tile: 8 bytes of plane 0, then 8 of plane 1
    moveq #7, %d1                           | the lines
2:  moveq #0, %d2
    move.b (%a0), %d2                       | plane 0
    moveq #0, %d3
    move.b 8(%a0), %d3                      | plane 1
    addq.l #1, %a0
    move.b %d2, %d4
    or.b %d3, %d4
    not.b %d4                               | the pixels of colour 0
    move.b %d3, %d5
    not.b %d5
    and.b %d2, %d5                          | colour 1
    move.b %d2, %d6
    not.b %d6
    and.b %d3, %d6                          | colour 2
    and.b %d3, %d2                          | colour 3
    moveq #0, %d7                           | the plane made
3:  moveq #0, %d0
    btst %d7, (%a2)
    beq.s 4f
    or.b %d4, %d0
4:  btst %d7, 1(%a2)
    beq.s 5f
    or.b %d5, %d0
5:  btst %d7, 2(%a2)
    beq.s 6f
    or.b %d6, %d0
6:  btst %d7, 3(%a2)
    beq.s 7f
    or.b %d2, %d0
7:  move.b %d0, (%a1)+
    addq.w #1, %d7
    cmpi.w #4, %d7
    bne.s 3b
    dbra %d1, 2b
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| a0 = a tile of 32 bytes (8 lines of four plane bytes), d1 = x (a multiple of 8), d2 = y, a3 = the screen: the tile is put there. Keeps every register.
tile_put:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    mulu.w #STRIDE, %d2
    movea.l %a3, %a1
    adda.l %d2, %a1
    move.w %d1, %d0
    lsr.w #4, %d0
    lsl.w #3, %d0
    adda.w %d0, %a1                         | the group of 16 pixels
    move.w %d1, %d0
    lsr.w #3, %d0
    andi.w #1, %d0
    adda.w %d0, %a1                         | its left or right byte
    moveq #7, %d0
1:  move.b (%a0)+, (%a1)
    move.b (%a0)+, 2(%a1)
    move.b (%a0)+, 4(%a1)
    move.b (%a0)+, 6(%a1)
    lea STRIDE(%a1), %a1
    dbra %d0, 1b
    movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

| The picture of an item (2x2 tiles): d0.w = its number (0 weapons, 4 armours, 8 shields, 12 spells, 17 items, as the names are numbered), d1 = x (a multiple of 8),
| d2 = y, a3 = the screen. Keeps every register.
item_draw:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    lea -128(%sp), %sp
    lea items_data+ITEMS_PICTURES(%pc), %a0
    lsl.w #2, %d0
    lea (%a0,%d0.w), %a0                    | the four tile numbers
    movea.l %sp, %a1
    moveq #3, %d3
1:  moveq #0, %d0
    move.b (%a0)+, %d0
    bsr.w item_tile
    lea 32(%a1), %a1
    dbra %d3, 1b
    movea.l %sp, %a0
    move.w %d1, %d4
    move.w %d2, %d5
    moveq #0, %d3
2:  move.w %d4, %d1
    btst #0, %d3
    beq.s 3f
    addq.w #8, %d1
3:  move.w %d5, %d2
    btst #1, %d3
    beq.s 4f
    addq.w #8, %d2
4:  bsr.w tile_put
    lea 32(%a0), %a0
    addq.w #1, %d3
    cmpi.w #4, %d3
    bne.s 2b
    lea 128(%sp), %sp
    movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| The HUD's item box: the picture of the item in hand (inv INV_ITEM, the ROM's SelectedItem: 0-21, bit 7 set none) is made into the HUD's tiles $3C-$3F (blank for none).
| Called by hud_build. Keeps every register.
hud_item_picture:
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    movea.l pkg_ptr+PKG_HUD_TILES(%pc), %a1
    lea 0x3C*32(%a1), %a1
    moveq #0, %d0
    move.b inv+INV_ITEM(%pc), %d0
    cmpi.b #22, %d0
    bcc.s 8f
    addi.w #17, %d0                         | the items start at 17
    lea items_data+ITEMS_PICTURES(%pc), %a0
    lsl.w #2, %d0
    lea (%a0,%d0.w), %a0
    moveq #3, %d3
1:  moveq #0, %d0
    move.b (%a0)+, %d0
    bsr.w item_tile
    lea 32(%a1), %a1
    dbra %d3, 1b
    bra.s 9f
8:  moveq #31, %d0                          | none: four blank tiles
2:  clr.l (%a1)+
    dbra %d0, 2b
9:  movem.l (%sp)+, %d0-%d3/%a0-%a1
    rts

| ---------------------------------------------------------------------------------------------------------------------- the PLAYER entry
| PlayerMenu_ShowStatusMenu (the box x4 y8, 26 by 16 tiles, over the menu): the rank, the experience the next one needs, what he wears and the special items he
| has. Only B ends it (A and Start do nothing), and that closes the whole menu. a3 = the screen.
menu_status:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    lea -8(%sp), %sp                        | room for the five digits of the experience
    moveq #4, %d0
    moveq #64, %d1
    moveq #13, %d2
    move.w #128, %d3
    bsr.w draw_box
    lea status_label_texts(%pc), %a0        | the labels: from y 80, a tile row of text and a blank one between
    moveq #0, %d3
1:  move.w %d3, %d0
    moveq #80, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #80, %d2
    bsr.w menu_text
    addq.w #1, %d3
    cmpi.w #7, %d3
    bne.s 1b
    move.w hero_title(%pc), %d0             | RANK: the rank in force
    andi.w #15, %d0
    lea status_title_texts(%pc), %a0
    move.w #152, %d1
    moveq #80, %d2
    bsr.w menu_text
    move.w hero_next(%pc), %d0              | NEXT EXP: what the next rank needs, five digits (nothing at the last rank)
    cmpi.w #15, %d0
    bcc.s 4f
    add.w %d0, %d0
    lea title_table(%pc), %a0
    moveq #0, %d1
    move.w (%a0,%d0.w), %d0
    clr.b 5(%sp)
    moveq #4, %d3
2:  andi.l #0xFFFF, %d0
    divu.w #10, %d0
    move.l %d0, %d1
    swap %d1
    addi.b #'0', %d1
    move.b %d1, (%sp,%d3.w)
    dbra %d3, 2b
    movea.l %sp, %a0
    move.w #152, %d0
    moveq #96, %d1
    moveq #0, %d6
    bsr.w text_string
4:  moveq #0, %d3                           | WEAPON, ARMOR, SHIELD, MAGIC: the picture at x 136 (the row above and the row of the name), the name at x 152
5:  move.w %d3, %d1
    bsr.w inv_selected                      | d0 = what he wears (bit 7: nothing)
    tst.b %d0
    bmi.s 6f
    andi.w #0x1F, %d0
    lea name_base(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d3.w), %d1
    add.w %d1, %d0                          | its number among the names
    move.w %d0, %d4
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #104, %d2
    move.w #136, %d1
    bsr.w item_draw
    move.w %d4, %d0
    lea menu_name_texts(%pc), %a0
    move.w #152, %d1
    move.w %d3, %d2
    lsl.w #4, %d2
    addi.w #112, %d2
    bsr.w menu_text
6:  addq.w #1, %d3
    cmpi.w #4, %d3
    bne.s 5b
    moveq #0, %d3                           | ITEM: a picture for each special item he has, in a place of its own (8 places, 16 pixels apart)
7:  lea special_masks(%pc), %a0
    move.b (%a0,%d3.w), %d0
    and.b inv+INV_SPECIAL(%pc), %d0
    beq.s 8f
    lea special_ids(%pc), %a0
    moveq #0, %d0
    move.b (%a0,%d3.w), %d0
    andi.w #0x1F, %d0
    addi.w #17, %d0
    move.w %d3, %d1
    lsl.w #4, %d1
    addi.w #136, %d1
    move.w #168, %d2
    bsr.w item_draw
8:  addq.w #1, %d3
    cmpi.w #8, %d3
    bne.s 7b
9:  bsr.w menu_input                         | only B (or Esc) leaves
    btst #8, %d0
    bne.s 10f
    btst #6, %d0
    beq.s 9b
10: lea 8(%sp), %sp
    movem.l (%sp)+, %d0-%d7/%a0-%a2
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
status_label_texts:                         | RANK:, NEXT EXP:, WEAPON:, ARMOR:, SHIELD:, MAGIC:, ITEM: (9 characters each, with their blanks)
    .word TEXT_STATUS_0, TEXT_STATUS_1, TEXT_STATUS_2, TEXT_STATUS_3, TEXT_STATUS_4, TEXT_STATUS_5, TEXT_STATUS_6
status_title_texts:                         | the 16 ranks in capitals
    .word TEXT_TITLE_0, TEXT_TITLE_1, TEXT_TITLE_2, TEXT_TITLE_3, TEXT_TITLE_4, TEXT_TITLE_5, TEXT_TITLE_6, TEXT_TITLE_7
    .word TEXT_TITLE_8, TEXT_TITLE_9, TEXT_TITLE_10, TEXT_TITLE_11, TEXT_TITLE_12, TEXT_TITLE_13, TEXT_TITLE_14, TEXT_TITLE_15
menu_name_texts:
    .word TEXT_NAME_0, TEXT_NAME_1, TEXT_NAME_2, TEXT_NAME_3, TEXT_NAME_4, TEXT_NAME_5, TEXT_NAME_6, TEXT_NAME_7, TEXT_NAME_8, TEXT_NAME_9, TEXT_NAME_10, TEXT_NAME_11, TEXT_NAME_12, TEXT_NAME_13, TEXT_NAME_14, TEXT_NAME_15, TEXT_NAME_16, TEXT_NAME_17, TEXT_NAME_18, TEXT_NAME_19, TEXT_NAME_20, TEXT_NAME_21, TEXT_NAME_22, TEXT_NAME_23, TEXT_NAME_24, TEXT_NAME_25, TEXT_NAME_26, TEXT_NAME_27, TEXT_NAME_28, TEXT_NAME_29, TEXT_NAME_30, TEXT_NAME_31, TEXT_NAME_32, TEXT_NAME_33, TEXT_NAME_34, TEXT_NAME_35, TEXT_NAME_36, TEXT_NAME_37, TEXT_NAME_38
    .even
    .text

    .section .herodata
items_data:                                 | tools/itempics.py: the slots of the HUD's colours by palette set, the item pictures' tile numbers, the tiles
    .incbin "items.bin"
    .even
    .text
