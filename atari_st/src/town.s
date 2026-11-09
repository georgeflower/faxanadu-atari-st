| The interaction scripts (the ROM's IScripts): talking to people, the King, the Gurus, the shops' prices and what a visit does to the hero. A script is a few
| bytes of actions that the ROM's bank 12 runs (tools/iscripts.py writes them, the messages, the portraits and the people into TOWN.DAT, which the program reads once at
| the start into town_ptr). `iscript_run` (d0 = the script's number) is a blocking routine like `message_box`: the game stands still, the text box is drawn over the
| window, the script runs to its END, and the screens are made again (box_leave).
|
| What is here: the message printer (the ROM's raw message bytes, one character every four frames, the rank's name, the pauses) and every action of the language,
| the shops (OPEN_SHOP, BUY_SELL_MENU, SELL_MENU: the shop box with the pictures, names and prices, buying and selling as the ROM does it) and, with NPCS=1, the
| people of the screens (drawn, and a script when Up is pressed in front of one or a trigger is touched) and the portraits of the people in the buildings.
|
| The code is in .text.early (see link.ld); the tables and variables are in .data.
|
| The box. Where the NES has it (X = 10, W = 20, H = 8 tiles: 80 pixels in from the left of the 256-pixel playfield, 160 wide) it is group 7 here (x = 112, the
| playfield starts 32 pixels in); it is 48 high (four lines of text, BOX_PITCH apart) and sits in the window near the top (y = 40) when the hero stands at y $40 or
| more, else at the bottom (y = 144), as the ROM moves it out of his way (its Y = 6 or 16 tiles; at camera 40 line 16 of the playfield would be half under the HUD,
| so the window's own top and bottom are used); with a portrait it is always at the bottom (the ROM's Y = 16). The text area is 16 columns by 4 lines at the box's
| x + 16, y + 4. A blinking arrow (down: more after a button, up: the end, a question mark: yes or no) is in the last column's place right of the text, in the bottom line.
|
| The text. One byte of the message every four frames (`TextBox_ShowNextChar`: the timer is counted each frame, a byte is read when it is a multiple of 4), sound 1 for a
| character (not for a space, a new line or a pause). A line holds 16 characters; the 17th goes to the next line unless the message ends (or waits) there; a new line byte
| at the start of a line is nothing. A fifth line makes the text scroll up one line (the ROM's `TextBox_ShowMessage_Fill4Lines`), a pause ($FC) waits for A and goes on in the
| line below. A message starts in an empty text area (the ROM keeps the position of the one before; the messages are written so that this is what it looks like).
| The buttons: MSG_UNSKIPPABLE takes A at a pause and at the end; MSG and MSG_QUESTION also take B at any moment (the script ends); at the end of a question A is yes.

    .equ TB_GROUP, 7                        | the box's first group of 16 pixels (x = 112)
    .equ TB_GROUPS, 10                      | its width: 160 pixels
    .equ TB_HEIGHT, 4*BOX_PITCH+8           | and height
    .equ TB_TOP, HUD_LINES+8                | its y near the top of the window,
    .equ TB_BOTTOM, HUD_LINES+WINDOW_LINES-TB_HEIGHT-8 | and at the bottom
    .equ TB_COLS, 16
    .equ TB_ROWS, 4
    .equ TB_TEXT_X, 16*TB_GROUP+16          | where the text starts (a group of 16 pixels)
    .equ TB_ARROW_GROUP, TB_GROUP+TB_GROUPS-1 | the arrow's cell: the last group (right of the text), left byte
    .equ ISCRIPT_LAST_OP, 0x17
    .ifndef SCRIPT_AT
    .equ SCRIPT_AT, 20                      | (SCRIPT=n) the frame in which the script is started
    .endif

| the message printer's variables (tb_vars): offsets
    .equ TB_MSG, 0                          | long: the next byte of the message
    .equ TB_COL, 4                          | the column and the line the next character goes to
    .equ TB_LINE, 6
    .equ TB_TIMER, 8                        | counted each frame; a byte is read when it is a multiple of 4
    .equ TB_PAUSED, 10                      | 1: a pause waits for A
    .equ TB_DONE, 12                        | 1: the message has ended
    .equ TB_TITLE, 14                       | the rank's name is being written: its place + $81 (0: not)
    .equ TB_MODE, 16                        | 0 MSG_UNSKIPPABLE, 1 MSG_QUESTION, 2 MSG
    .equ TB_Y, 18                           | the box's y
    .equ TB_QUIET, 20                       | 1: a message is typed at once and without the character sound (BUY_SELL_MENU's)
    .equ TB_VARS_BYTES, 22

    .section .text.early,"ax"               | in front of the variables, like splash68.s: the main code has no room left behind them (link.ld)
| ------------------------------------------------------------------------------------------------------------------ loading
| TOWN.DAT (packed) is read into town_buf (TOS's screen memory, see viewer.s) once, after the first package (whose LOADING word is drawn there); town_ptr is its address, or 0 when the file could not be read (the
| scripts do nothing then). Keeps every register.
town_load:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    clr.w -(%sp)                            | Fopen(name, read)
    pea town_name(%pc)
    move.w #0x3D, -(%sp)
    trap #1
    addq.l #8, %sp
    tst.l %d0
    bmi.s 9f
    move.w %d0, %d2                         | the handle
    movea.l town_buf(%pc), %a0
    lea TOWN_SPAN-TOWN_COMP(%a0), %a0       | the packed file (tools/lz.py) is read to the end of the room and unpacked where it lies
    move.l %a0, -(%sp)                      | Fread(handle, count, buffer)
    move.l #TOWN_FILE, -(%sp)
    move.w %d2, -(%sp)
    move.w #0x3F, -(%sp)
    trap #1
    lea 12(%sp), %sp
    move.l %d0, %d1
    move.w %d2, -(%sp)                      | Fclose
    move.w #0x3E, -(%sp)
    trap #1
    addq.l #4, %sp
    cmpi.l #TOWN_FILE, %d1
    bne.s 9f
    movea.l town_buf(%pc), %a1
    lea TOWN_SPAN-TOWN_COMP(%a1), %a0       | the packed file lies at the end of the room
    bsr.w unpack
    lea town_ptr(%pc), %a0
    move.l town_buf(%pc), (%a0)
9:  movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| ------------------------------------------------------------------------------------------------------------------ the interpreter
| d0.w = the script's number ($FF is script $1F, "remember your mantra"). Runs it to its END (or Esc). Keeps every register. a5 is the script's next byte, d7 is set
| to 1 by an action that ends the script.
iscript_run:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    lea town_sp(%pc), %a0
    move.l %sp, (%a0)                       | where an abort (Esc) goes back to
    move.l town_ptr(%pc), %d1
    beq.w 9f                                | no TOWN.DAT
    andi.w #0xFF, %d0
    cmpi.w #0xFF, %d0
    bne.s 1f
    moveq #0x1F, %d0
1:  cmpi.w #ISCRIPT_COUNT, %d0
    bcc.w 9f
    movea.l %d1, %a0
    adda.l #ISCRIPT_OFFSETS, %a0
    add.w %d0, %d0
    move.w (%a0,%d0.w), %d1                 | its offset in the blob
    movea.l town_ptr(%pc), %a5
    adda.l #ISCRIPT_BLOB, %a5
    adda.w %d1, %a5
    moveq #0, %d0
    move.b (%a5)+, %d0                      | the entity byte: $00 no portrait, $80 + k the portrait k (not drawn yet)
    move.w #TB_BOTTOM, %d1
    tst.b %d0
    bmi.s 2f
    move.w hero_y(%pc), %d2
    cmpi.w #0x40, %d2
    bcs.s 2f
    move.w #TB_TOP, %d1
2:  lea tb_vars(%pc), %a0
    move.w %d1, TB_Y(%a0)
    move.w #1, TB_DONE(%a0)                 | (no message is being typed yet)
    .ifdef NPCS
    tst.b %d0
    bpl.s 4f
    andi.w #0x7F, %d0
    bsr.w portrait_open                     | the portrait and its box first, the text box over its edge
    .endif
4:  bsr.w tb_open
3:  moveq #0, %d7
    moveq #0, %d0
    move.b (%a5)+, %d0
    .ifdef BATCH
    bsr.w batch_trace
    .endif
    cmpi.b #ISCRIPT_LAST_OP, %d0
    bhi.s 8f
    add.w %d0, %d0
    lea iscript_ops(%pc), %a0
    move.w (%a0,%d0.w), %d0
    jsr (%a0,%d0.w)
    tst.w %d7
    beq.s 3b
8:  bsr.w box_leave                         | END: the box goes
    .ifdef NPCS
    bsr.w portrait_close                    | (and the portrait, with its colours)
    .endif
9:  movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| Esc in a wait: back to where iscript_run was called (the main loop sees the key too).
town_abort:
    movea.l town_sp(%pc), %sp
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| One frame in which the game stands still: the VBL, the keys, and the HUD if it changed. Esc leaves the script.
town_tick:
    movem.l %d0/%a0, -(%sp)
    bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.w town_abort
    lea hud_dirty(%pc), %a0
    tst.b (%a0)
    beq.s 1f
    clr.b (%a0)
    bsr.w hud_update_all
1:
    .ifdef NPCS
    move.w portrait_k(%pc), %d0
    bmi.s 2f
    bsr.w portrait_update                   | the eyes and the mouth while the text is typed
    .endif
2:
    movem.l (%sp)+, %d0/%a0
    rts

| d3 frames of town_tick.
town_wait:
    bsr.s town_tick
    subq.w #1, %d3
    bne.s town_wait
    rts

| ---- the actions: each reads its operands from a5 and comes back with rts; d7 = 1 ends the script.
op_end:                                     | $00
    moveq #1, %d7
    rts

iop_finish:                                  | $15 FINISH_GAME: the script ends; with FLOW the main loop then plays the ending (IScriptAction_FinishGame: RunOutro, then Game_Init)
    .ifdef FLOW
    lea end_state(%pc), %a0
    move.w #END_FINISH, (%a0)
    .endif
    moveq #1, %d7
    rts

op_msg_unskippable:                         | $01
    moveq #0, %d1
    bra.s op_msg_any
op_msg_question:                            | $02
    moveq #1, %d1
    bra.s op_msg_any
op_msg:                                     | $03
    moveq #2, %d1
op_msg_any:
    moveq #0, %d0
    move.b (%a5)+, %d0
    bsr.w tb_message
    move.w %d0, %d7                         | 1: the message was dismissed: the script ends
    rts

op_msg_question_jump:                       | $16 (no script has it): yes goes to the address, B goes on
    moveq #0, %d0
    move.b (%a5)+, %d0
    moveq #1, %d1
    bsr.w tb_message
    tst.w %d0
    bne.s 1f
    bra.w ip_jump
1:  addq.l #2, %a5
    rts

op_check_title:                             | $04: a new rank is his now: its address, else the next action
    move.w hero_next(%pc), %d0
    cmp.w hero_title(%pc), %d0
    beq.s ip_skip
    lea hero_title(%pc), %a0
    move.w %d0, (%a0)
    bra.s ip_jump

op_set_spawn:                               | $06: the temple he starts from, unless it is an earlier one
    moveq #0, %d0
    move.b (%a5)+, %d0
    cmp.w hero_spawn(%pc), %d0
    bcs.s 1f
    lea hero_spawn(%pc), %a0
    move.w %d0, (%a0)
1:  rts

op_if_quest:                                | $0B n, a: a quest done (n = 1 to 3)
    bsr.w ip_quest_bit
    and.b inv+INV_QUESTS(%pc), %d0
    bne.s ip_jump
    bra.s ip_skip

op_set_quest:                               | $0E n
    bsr.w ip_quest_bit
    lea inv+INV_QUESTS(%pc), %a0
    or.b %d0, (%a0)
    rts

op_if_rank:                                 | $0C n, a: a rank of n or more
    moveq #0, %d0
    move.b (%a5)+, %d0
    cmp.w hero_title(%pc), %d0
    bls.s ip_jump
    bra.s ip_skip

op_if_gold:                                 | $0D a: he has gold (the game's own "has he been to the King")
    move.l hud_state+4(%pc), %d0
    bne.s ip_jump
    bra.s ip_skip

op_if_item:                                 | $12 i, a: he has the item
    moveq #0, %d0
    move.b (%a5)+, %d0
    bsr.w far_inv_lacks                         | d0.w = 1: he lacks it
    tst.w %d0
    beq.w ip_jump
    bra.w ip_skip

    .section .text.early,"ax"

op_jump:                                    | $17 a
ip_jump:                                    | a5 = a (lo, hi): the script goes on there (the ROM's address minus ISCRIPT_BASE in the blob)
    moveq #0, %d0
    move.b 1(%a5), %d0
    lsl.w #8, %d0
    move.b (%a5), %d0
    subi.w #ISCRIPT_BASE, %d0
    movea.l town_ptr(%pc), %a5
    adda.l #ISCRIPT_BLOB, %a5
    andi.l #0xFFFF, %d0
    adda.l %d0, %a5
    rts
ip_skip:                                    | the address is not wanted
    addq.l #2, %a5
    rts

| d0 = the bit of the quest number in the next byte (1 to 3).
ip_quest_bit:
    moveq #0, %d1
    move.b (%a5)+, %d1
    subq.w #1, %d1
    moveq #1, %d0
    lsl.b %d1, %d0
    rts

| d0.w = the word (lo, hi) at a5, which moves on.
ip_word:
    moveq #0, %d0
    move.b 1(%a5), %d0
    lsl.w #8, %d0
    move.b (%a5), %d0
    addq.l #2, %a5
    rts

| $05 PAY_GOLD w: not enough: "This is not enough Golds." and the script ends. Else 10 gold a frame (the HUD each frame), then 60 frames.
op_pay_gold:
    bsr.s ip_word
    moveq #0, %d4
    move.w %d0, %d4                         | the price
    cmp.l hud_state+4(%pc), %d4
    bls.s 1f
    moveq #3, %d0                           | the message
    moveq #2, %d1
    bsr.w tb_message
    moveq #1, %d7
    rts
pay_gold_d4:                                | (d4 = the price: 10 gold a frame, then 60 frames; the shops come here too)
1:  cmpi.l #10, %d4
    bcs.s 3f
2:  bsr.w town_tick
    lea hud_state+4(%pc), %a0
    subi.l #10, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    subi.l #10, %d4
    cmpi.l #10, %d4
    bcc.s 2b
3:  moveq #60, %d3
    bra.w town_wait

| $09 ADD_GOLD w: 10 gold a frame, sound $19 every fourth frame (the HUD each frame), then 60 frames.
op_add_gold:
    bsr.s ip_word
    moveq #0, %d4
    move.w %d0, %d4
add_gold_d4:                                | (d4 = the gold: 10 a frame with the sound, then 60 frames; selling comes here too)
    cmpi.l #10, %d4
    bcs.s 3f
2:  bsr.w town_tick
    move.l frame_count(%pc), %d0
    andi.w #3, %d0
    bne.s 4f
    moveq #0x19, %d0
    bsr.w sound_play_sfx
4:  lea hud_state+4(%pc), %a0
    move.l (%a0), %d0
    addi.l #10, %d0
    cmpi.l #0xFFFFFF, %d0                   | (the HUD shows seven digits: the most is 16,777,215)
    bls.s 5f
    move.l #0xFFFFFF, %d0
5:  move.l %d0, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    subi.l #10, %d4
    cmpi.l #10, %d4
    bcc.s 2b
3:  moveq #60, %d3
    bra.w town_wait

| $0A ADD_MP n and $13 ADD_HP n: nothing when it is full; else n frames (0 is 256) of one more, up to 80, sound $13 every fourth frame.
op_add_mp:
    lea hud_state+1(%pc), %a1
    bra.s fill_by_one
op_add_hp:
    lea hud_state(%pc), %a1
fill_by_one:
    moveq #0, %d4
    move.b (%a5)+, %d4
    bne.s 1f
    move.w #256, %d4
1:  cmpi.b #80, (%a1)
    bcc.s 9f
2:  bsr.w town_tick
    move.l frame_count(%pc), %d0
    andi.w #3, %d0
    bne.s 3f
    moveq #0x13, %d0
    bsr.w sound_play_sfx
3:  move.b (%a1), %d0
    addq.b #1, %d0
    cmpi.b #80, %d0
    bls.s 4f
    moveq #80, %d0
4:  move.b %d0, (%a1)
    lea hud_dirty(%pc), %a0
    st (%a0)
    subq.w #1, %d4
    bne.s 2b
9:  rts

| $10 CONSUME_ITEM i: it goes out of his list (or its special bit goes); when it is what he wears or holds, nothing is chosen then.
op_consume:
    moveq #0, %d0
    move.b (%a5)+, %d0
    bra.w inv_consume

| $07 ADD_ITEM i: he gets it (a special item sets its bit; a full list loses its last place); the text area shows its name until A.
op_add_item:
    moveq #0, %d0
    move.b (%a5)+, %d0
    move.w %d0, %d4
    bsr.w far_inv_add
    move.w %d4, %d0
    move.w %d4, %d1
    lsr.w #5, %d1                           | the category
    andi.w #0x1F, %d0
    lea game_start(%pc), %a0
    adda.l #name_base, %a0
    moveq #0, %d2
    move.b (%a0,%d1.w), %d2
    add.w %d2, %d0                          | the item's place among the names
    add.w %d0, %d0
    lea game_start(%pc), %a0
    adda.l #menu_name_texts, %a0
    move.w (%a0,%d0.w), %d0
    lea game_start(%pc), %a0
    adda.l #text_data, %a0
    adda.w %d0, %a0                         | its name
    bsr.w tb_blank
    moveq #1, %d1                           | (the picture of the item comes later: the name stands on the second line)
    bsr.w tb_text
    moveq #2, %d0
    bra.w tb_wait_a

| $14 SHOW_PASSWORD: a small box asks Save to disk or Show mantra (save.s: the game is saved in SAVE.SAV, or the disk would not take it); the mantra goes in the text
| area (16 characters to a line) until A. The box took the place of the text box and the portrait: they are drawn again.
op_password:
    bsr.w far_save_guru
    move.w %d0, -(%sp)
    bsr.w town_reopen
    tst.w (%sp)+
    bne.s 1f
    rts                                     | saved: the script goes on
1:  lea pw_block(%pc), %a1
    bsr.w pw_build
    movea.l %a1, %a0
    lea pw_text(%pc), %a1
    bsr.w pw_encode
    bsr.w tb_blank
    lea pw_text(%pc), %a0
    moveq #0, %d1
    bsr.w tb_text
    moveq #2, %d0
    bra.w tb_wait_a

| ------------------------------------------------------------------------------------------------------------------ routines of menu.s
| menu.s and the names are out of the early section's reach: a jump that keeps every register goes to the routine's address (the program starts at 0, the link
| address is the offset from game_start; the return address stays on the stack).
    .macro FAR_JMP sym
    subq.l #4, %sp
    move.l %a0, -(%sp)
    lea game_start(%pc), %a0
    adda.l #\sym, %a0
    move.l %a0, 4(%sp)
    movea.l (%sp)+, %a0
    rts
    .endm
far_inv_lacks:
    FAR_JMP inv_lacks
far_inv_special_index:
    FAR_JMP inv_special_index
far_inv_add:
    FAR_JMP inv_add
far_inv_remove:
    FAR_JMP inv_remove
far_tile_put:
    FAR_JMP tile_put
far_inv_selected:
    FAR_JMP inv_selected
far_inv_set_selected:
    FAR_JMP inv_set_selected
far_item_draw:
    FAR_JMP item_draw
far_menu_text:
    FAR_JMP menu_text
far_save_guru:
    FAR_JMP save_guru

| d0.b = an item, d2 = y, a3 = the screen: its picture at x 128 and its name at x 152. Keeps every register.
far_item_row:
    movem.l %d0-%d4/%a0, -(%sp)
    move.w %d0, %d3
    lsr.w #5, %d3
    andi.w #0x1F, %d0
    lea game_start(%pc), %a0
    adda.l #name_base, %a0
    moveq #0, %d4
    move.b (%a0,%d3.w), %d4
    add.w %d4, %d0                          | its number among the pictures and names
    move.w %d0, %d4
    move.w #128, %d1
    bsr.w far_item_draw
    move.w %d4, %d0
    lea game_start(%pc), %a0
    adda.l #menu_name_texts, %a0
    move.w #152, %d1
    bsr.w far_menu_text
    movem.l (%sp)+, %d0-%d4/%a0
    rts

| ------------------------------------------------------------------------------------------------------------------ the portraits
| A portrait is 48 by 64 pixels in a frame of 64 by 80 (the ROM's X 2, Y 14, 8 by 10 tiles; here group 3, y 112, so that it ends where the text box starts and the
| frames' bottoms are level). portraits.bin: the base picture, then the eyes and the mouth: cells that fill holes in it. The cells are converted when they are
| drawn (`tile_convert`, 32 bytes of plane data on the stack, `tile_put`) with the portrait's colours for the building's palette set; while the portrait is up the
| palette is the one made for it (the building's with the spare slots given the portrait's colours), and `portrait_close` puts the package's back.
    .ifdef NPCS
    .equ PORTRAIT_GROUP, 3
    .equ PORTRAIT_Y, 112
    .equ PORTRAIT_X, 56                     | where the picture's left is (the frame's x + 8)
    .equ PORTRAIT_TOP, 120                  | and its top (the frame's y + 8)

| d0 = the portrait k (0 to 10): its colours are on the hardware, its base picture is drawn on the screen on show (the frame and the base; the eyes and the mouth
| come with the first portrait_update). No portrait when the palette set is not a building's. Keeps every register.
portrait_open:
    movem.l %d0-%d2/%a0-%a3, -(%sp)
    lea portrait_k(%pc), %a0
    move.w %d0, (%a0)
    lea portrait_f(%pc), %a0
    move.w #-1, (%a0)
    move.w cur_pal(%pc), %d1
    subi.w #17, %d1                         | the building palette sets are $11 to $1A
    cmpi.w #10, %d1
    bcc.s 8f
    move.l town_ptr(%pc), %d2
    beq.s 8f
    movea.l %d2, %a0
    adda.l #TOWN_PORTRAITS, %a0
    adda.l 4(%a0), %a0                      | the colours: 10 sets of 16 slot bytes, then 10 of 16 palette words
    move.w %d1, %d2
    lsl.w #4, %d2
    lea (%a0,%d2.w), %a1
    lea conv_slots(%pc), %a2
    move.l %a1, (%a2)
    lea 160(%a0), %a0
    move.w %d1, %d2
    lsl.w #5, %d2
    adda.w %d2, %a0                         | this set's palette words
    movea.l #PALETTE, %a2
    moveq #15, %d2
1:  move.w (%a0)+, (%a2)+
    dbra %d2, 1b
    bsr.w shown_screen
    bsr.s portrait_draw
    bra.s 9f
8:  lea portrait_k(%pc), %a0
    move.w #-1, (%a0)
9:  movem.l (%sp)+, %d0-%d2/%a0-%a3
    rts

| a3 = the screen: the frame (black inside) and the base picture. Keeps every register.
portrait_draw:
    movem.l %d0-%d3, -(%sp)
    moveq #PORTRAIT_GROUP, %d0
    moveq #PORTRAIT_Y, %d1
    moveq #4, %d2
    moveq #80, %d3
    bsr.w draw_box
    moveq #0, %d0
    bsr.s portrait_cells
    movem.l (%sp)+, %d0-%d3
    rts

| The frame of the portrait d0 (0 base, 1 and 2 the eyes, 3 and 4 the mouth) drawn on the screen a3: every cell but the empty ones (the holes of the base). Keeps every
| register.
portrait_cells:
    movem.l %d0-%d7/%a0-%a2/%a5-%a6, -(%sp)
    lea -40(%sp), %sp                       | 32 bytes for the converted tile, then the frame's columns, rows, x and y
    movea.l %sp, %a6
    move.w %d0, %d7
    move.w portrait_k(%pc), %d1
    move.l town_ptr(%pc), %d2
    beq.w 9f
    movea.l %d2, %a0
    adda.l #TOWN_PORTRAITS, %a0             | portraits.bin
    lsl.w #2, %d1
    move.l 8(%a0,%d1.w), %d2
    adda.l %d2, %a0                         | the portrait's record
    moveq #0, %d2
    move.w (%a0)+, %d2                      | its tiles
    movea.l %a0, %a2
    lsl.w #4, %d2
    adda.l %d2, %a0                         | the first frame
1:  tst.w %d7
    beq.s 2f
    moveq #0, %d2
    move.b (%a0), %d2
    moveq #0, %d3
    move.b 1(%a0), %d3
    mulu.w %d3, %d2
    add.w %d2, %d2
    addq.w #4, %d2
    adda.w %d2, %a0                         | the next frame
    subq.w #1, %d7
    bra.s 1b
2:  moveq #0, %d4
    move.b (%a0), %d4
    move.w %d4, 32(%a6)                     | columns
    moveq #0, %d5
    move.b 1(%a0), %d5
    move.w %d5, 34(%a6)                     | rows
    move.b 2(%a0), %d0
    ext.w %d0
    move.w %d0, 36(%a6)                     | x
    move.b 3(%a0), %d0
    ext.w %d0
    move.w %d0, 38(%a6)                     | y
    mulu.w %d4, %d5                         | the cells
    lea 4(%a0), %a5
    moveq #0, %d7
3:  cmp.w %d5, %d7
    bcc.s 9f
    moveq #0, %d0
    move.b (%a5)+, %d0                      | the tile
    moveq #0, %d1
    move.b (%a5)+, %d1                      | its attribute
    cmpi.b #0xFF, %d0
    beq.s 8f
    lsl.w #4, %d0
    lea (%a2,%d0.w), %a0
    movea.l %a6, %a1
    moveq #0, %d0                           | four plane bytes a line, no mask
    bsr.w tile_convert
    moveq #0, %d0
    move.w %d7, %d0
    divu.w 32(%a6), %d0                     | the row (low word) and the column (high word)
    move.w %d0, %d2
    lsl.w #3, %d2
    add.w 38(%a6), %d2
    addi.w #PORTRAIT_TOP, %d2
    swap %d0
    lsl.w #3, %d0
    add.w 36(%a6), %d0
    addi.w #PORTRAIT_X, %d0
    move.w %d0, %d1
    movea.l %a6, %a0
    bsr.w far_tile_put
8:  addq.w #1, %d7
    bra.s 3b
9:  lea 40(%sp), %sp
    movem.l (%sp)+, %d0-%d7/%a0-%a2/%a5-%a6
    rts

| While a script runs: the eyes and the mouth. f = (the frame count >> 3) & 3 while a message is typed, else 0; the eyes are frame 1 + (f & 1), the mouth 3 + (f >> 1 & 1);
| they are drawn when f has changed. Keeps every register.
portrait_update:
    movem.l %d0-%d2/%a0/%a3, -(%sp)
    moveq #0, %d1
    lea tb_vars(%pc), %a0
    tst.w TB_DONE(%a0)
    bne.s 1f
    move.l frame_count(%pc), %d1
    lsr.w #3, %d1
    andi.w #3, %d1
1:  move.w portrait_f(%pc), %d0
    cmp.w %d1, %d0
    beq.s 9f
    lea portrait_f(%pc), %a0
    move.w %d1, (%a0)
    move.w %d1, %d2
    bsr.w shown_screen
    move.w %d2, %d0
    andi.w #1, %d0
    addq.w #1, %d0
    bsr.w portrait_cells
    move.w %d2, %d0
    lsr.w #1, %d0
    andi.w #1, %d0
    addq.w #3, %d0
    bsr.w portrait_cells
9:  movem.l (%sp)+, %d0-%d2/%a0/%a3
    rts

| The portrait is drawn again after the screens were made again (the frame, the base; the eyes and the mouth with the next portrait_update).
portrait_again:
    movem.l %d0/%a0/%a3, -(%sp)
    move.w portrait_k(%pc), %d0
    bmi.s 9f
    lea portrait_f(%pc), %a0
    move.w #-1, (%a0)
    bsr.w shown_screen
    bsr.w portrait_draw
9:  movem.l (%sp)+, %d0/%a0/%a3
    rts

| The end of a script: the package's palette is on the hardware again.
portrait_close:
    movem.l %d0/%a0-%a1, -(%sp)
    move.w portrait_k(%pc), %d0
    bmi.s 9f
    lea portrait_k(%pc), %a0
    move.w #-1, (%a0)
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a0
    movea.l #PALETTE, %a1
    moveq #15, %d0
1:  move.w (%a0)+, (%a1)+
    dbra %d0, 1b
9:  movem.l (%sp)+, %d0/%a0-%a1
    rts
    .endif

| ------------------------------------------------------------------------------------------------------------------ the shops
| The shop box (the ROM's Shop_Draw: x 10, y 8, 20 by 20 tiles; here group 7, y 40, as high as its entries): for each entry (shop_items, shop_costs, shop_count of them)
| a picture of 16 by 16, the name beside its top half and the price, five digits without leading zeros, under it; the cursor (shop_cursor) is an arrow before the picture.
shop_draw:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea -8(%sp), %sp                        | the price's digits and a 0 byte
    bsr.w text_color
    bsr.w shown_screen
    moveq #7, %d0
    moveq #40, %d1
    moveq #10, %d2
    move.w shop_count(%pc), %d3
    lsl.w #4, %d3
    addi.w #16, %d3
    bsr.w draw_box
    moveq #0, %d7                           | the entry
1:  cmp.w shop_count(%pc), %d7
    bcc.w 9f
    lea shop_items(%pc), %a0
    moveq #0, %d0
    move.b (%a0,%d7.w), %d0                 | the item
    move.w %d7, %d5
    lsl.w #4, %d5
    addi.w #48, %d5                         | the entry's y
    move.w %d5, %d2
    bsr.w far_item_row                      | its picture and its name
    lea shop_costs(%pc), %a0
    move.w %d7, %d0
    add.w %d0, %d0
    move.w (%a0,%d0.w), %d0                 | the price
    clr.b 5(%sp)
    moveq #4, %d3
2:  andi.l #0xFFFF, %d0
    divu.w #10, %d0
    move.l %d0, %d1
    swap %d1
    addi.b #'0', %d1
    move.b %d1, (%sp,%d3.w)
    dbra %d3, 2b
    moveq #0, %d3
3:  cmpi.w #4, %d3
    beq.s 4f
    cmpi.b #'0', (%sp,%d3.w)
    bne.s 4f
    move.b #' ', (%sp,%d3.w)                | no leading zeros
    addq.w #1, %d3
    bra.s 3b
4:  movea.l %sp, %a0
    move.w #216, %d0
    move.w %d5, %d1
    addq.w #8, %d1
    moveq #0, %d6
    bsr.w text_string
    cmp.w shop_cursor(%pc), %d7
    bne.s 5f
    moveq #120, %d1
    move.w %d5, %d2
    addq.w #4, %d2
    bsr.w town_arrow
5:  addq.w #1, %d7
    bra.w 1b
9:  lea 8(%sp), %sp
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| The shop box and its menu (Menu_UpdateAndDraw with IScripts_WaitForMenuInput): Up and Down move the cursor round (sound $0B), A chooses: d0.w = the entry, B: d0.w = -1.
shop_choose:
    movem.l %d1/%a0, -(%sp)
    lea shop_cursor(%pc), %a0
    clr.w (%a0)
    bsr.w shop_draw
1:  bsr.w town_tick
    lea input_state(%pc), %a0
    moveq #0, %d1
    move.b IN_PAD_NEW(%a0), %d1
    btst #7, %d1
    bne.s 8f
    btst #6, %d1
    bne.s 7f
    btst #3, %d1
    bne.s 3f
    btst #2, %d1
    beq.s 1b
    move.w shop_cursor(%pc), %d0            | Down
    addq.w #1, %d0
    cmp.w shop_count(%pc), %d0
    bcs.s 4f
    moveq #0, %d0
    bra.s 4f
3:  move.w shop_cursor(%pc), %d0            | Up
    subq.w #1, %d0
    bpl.s 4f
    move.w shop_count(%pc), %d0
    subq.w #1, %d0
4:  lea shop_cursor(%pc), %a0
    move.w %d0, (%a0)
    moveq #0x0B, %d0
    bsr.w town_sfx
    bsr.w shop_draw
    bra.s 1b
7:  moveq #-1, %d0
    bra.s 9f
8:  move.w shop_cursor(%pc), %d0
9:  movem.l (%sp)+, %d1/%a0
    rts

| The text box (and the portrait) are drawn anew after the shop box: the screens are made again (Maybe_Shop_DrawTextBox).
town_reopen:
    bsr.w box_leave
    .ifdef NPCS
    bsr.w portrait_again
    .endif
    bra.w tb_open

shop_end:                                   | the script ends
    moveq #1, %d7
    rts

| a5 = an address (lo, hi) in the script, a shop list there: a2 = the list in the blob.
shop_list_at:
    bsr.w ip_word
    subi.w #ISCRIPT_BASE, %d0
    andi.l #0xFFFF, %d0
    movea.l town_ptr(%pc), %a2
    adda.l #ISCRIPT_BLOB, %a2
    adda.l %d0, %a2
    rts

| $08 OPEN_SHOP a: "What would you like?" is typed (B ends the script), the shop box is drawn and a choice made. B ends the script. The ROM's checks, in this order:
| he has the item already (an equipment item worn or in a list, or a special item that he has; the other items of the pack are sold again and again) or his list of that
| kind is full: message $06 and the script ends; not enough gold:
| message $03 and the script ends; else the item is his, the price goes 10 gold a frame (then 60 frames) and the text box is back; the script goes on.
op_open_shop:
    bsr.s shop_list_at
    moveq #0x14, %d0
    moveq #3, %d1
    bsr.w tb_message
    tst.w %d0
    bne.w shop_end
    lea shop_items(%pc), %a0
    lea shop_costs(%pc), %a1
    moveq #0, %d2
1:  move.b (%a2)+, %d0
    cmpi.b #0xFF, %d0
    beq.s 2f
    cmpi.w #8, %d2
    bcc.s 2f
    move.b %d0, (%a0,%d2.w)
    moveq #0, %d1
    move.b (%a2)+, %d1
    moveq #0, %d3
    move.b (%a2)+, %d3
    lsl.w #8, %d3
    or.w %d1, %d3
    move.w %d2, %d4
    add.w %d4, %d4
    move.w %d3, (%a1,%d4.w)
    addq.w #1, %d2
    bra.s 1b
2:  lea shop_count(%pc), %a0
    move.w %d2, (%a0)
    bsr.w shop_choose
    tst.w %d0
    bmi.w shop_end
    move.w %d0, %d1
    lea shop_items(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d1.w), %d2                 | the item
    add.w %d1, %d1
    lea shop_costs(%pc), %a0
    moveq #0, %d4
    move.w (%a0,%d1.w), %d4                 | its price
    move.w %d2, %d0
    bsr.w far_inv_special_index
    move.w %d1, %d5
    bpl.s 8f                                | a special item: has he it?
    cmpi.w #0x80, %d2
    bcc.s 9f                                | an item of the pack that is not special (a potion, a key): sold again and again (Shop_GetPlayerHasSelectedItem)
8:  move.w %d2, %d0
    bsr.w far_inv_lacks
    tst.w %d0
    beq.s 6f                                | he has it
9:  tst.w %d5
    bpl.s 4f                                | a special item: no limit
    move.w %d2, %d1
    lsr.w #5, %d1                           | the category
    moveq #4, %d0
    cmpi.w #4, %d1
    bne.s 3f
    moveq #8, %d0                           | (eight items, four of the others)
3:  lea inv+INV_NWEAPONS(%pc), %a0
    cmp.b (%a0,%d1.w), %d0
    beq.s 6f                                | the list is full
4:  cmp.l hud_state+4(%pc), %d4
    bls.s 5f
    bsr.w town_reopen
    moveq #3, %d0                           | not enough gold
    bra.s 7f
5:  move.w %d2, %d0
    bsr.w far_inv_add
    bsr.w pay_gold_d4
    bra.w town_reopen                       | (the script goes on)
6:  bsr.w town_reopen
    moveq #6, %d0                           | he cannot carry any more
7:  moveq #2, %d1
    bsr.w tb_message
    bra.w shop_end

| $11 SELL_MENU a: the items in his pack (the last first, as the ROM) that the shop list names, at half the list's price (the worn item is not in the pack). None: message $12 and the script ends; else
| "Which one would you like to sell?", the shop box, a choice (B ends the script): the item goes and the price is added 10 gold a frame (then 60 frames).
op_sell_menu:
    bsr.w shop_list_at
    lea inv+INV_ITEMS(%pc), %a3
    moveq #0, %d3
    move.b inv+INV_NITEMS(%pc), %d3
    lea shop_items(%pc), %a0
    lea shop_costs(%pc), %a1
    moveq #0, %d2                           | the entries found
    move.w %d3, %d5                         | the pack from its last entry to its first (the ROM lists them so: tools/iscript_model.py, checked in jsnes)
1:  subq.w #1, %d5
    bmi.s 5f
    moveq #0, %d0
    move.b (%a3,%d5.w), %d0
    ori.b #0x80, %d0                        | the item in the pack
    movea.l %a2, %a6
2:  cmpi.b #0xFF, (%a6)
    beq.s 4f
    cmp.b (%a6), %d0
    beq.s 3f
    addq.l #3, %a6
    bra.s 2b
3:  move.b %d0, (%a0,%d2.w)
    moveq #0, %d1
    move.b 2(%a6), %d1
    lsl.w #8, %d1
    move.b 1(%a6), %d1
    lsr.w #1, %d1                           | half the price
    move.w %d2, %d6
    add.w %d6, %d6
    move.w %d1, (%a1,%d6.w)
    addq.w #1, %d2
    cmpi.w #8, %d2
    bcc.s 5f
4:  bra.s 1b
5:  lea shop_count(%pc), %a0
    move.w %d2, (%a0)
    tst.w %d2
    bne.s 6f
    moveq #0x12, %d0                        | nothing to sell
    moveq #2, %d1
    bsr.w tb_message
    bra.w shop_end
6:  moveq #0x13, %d0
    moveq #3, %d1
    bsr.w tb_message
    tst.w %d0
    bne.w shop_end
    bsr.w shop_choose
    tst.w %d0
    bmi.w shop_end
    move.w %d0, %d1
    lea shop_items(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d1.w), %d2                 | the item
    add.w %d1, %d1
    lea shop_costs(%pc), %a0
    moveq #0, %d4
    move.w (%a0,%d1.w), %d4                 | what it brings
    move.w %d2, %d0
    bsr.w far_inv_remove
    bsr.w add_gold_d4
    bra.w town_reopen

| $0F BUY_SELL_MENU a: "Come here to buy. Come here to sell." is written at once (no sound) and an arrow chooses between the two (Up and Down, sound $0B): A on the
| first goes to the address, A on the second goes on with the next action; B ends the script.
op_buy_sell:
    moveq #0x10, %d0
    bsr.w tb_instant
    lea shop_cursor(%pc), %a0
    clr.w (%a0)                             | the arrow's line: 0 buy, 1 sell
    .ifdef BATCH
    move.w auto_pad(%pc), %d0
    cmpi.w #3, %d0                          | (tests) the buttons "SA": Sell is chosen, so the arrow starts on the second line and A takes it
    bne.s 5f
    move.w #1, (%a0)
5:
    .endif
    bsr.s bs_arrow
1:  bsr.w town_tick
    lea input_state(%pc), %a0
    moveq #0, %d1
    move.b IN_PAD_NEW(%a0), %d1
    btst #7, %d1
    bne.s 8f
    btst #6, %d1
    bne.w shop_end
    andi.b #0x0C, %d1                       | Up or Down
    beq.s 1b
    move.w shop_cursor(%pc), %d0
    eori.w #1, %d0
    lea shop_cursor(%pc), %a0
    move.w %d0, (%a0)
    moveq #0x0B, %d0
    bsr.w town_sfx
    bsr.s bs_arrow
    bra.s 1b
8:  move.w shop_cursor(%pc), %d0
    beq.w ip_jump
    bra.w ip_skip

| The arrow before line pair shop_cursor of the text area (the other pair's place is blanked). Keeps every register.
bs_arrow:
    movem.l %d0-%d2/%d6/%a0/%a3, -(%sp)
    bsr.w shown_screen
    lea tb_vars(%pc), %a0
    move.w TB_Y(%a0), %d1
    addq.w #4, %d1                          | the text area's first line
    lea blank_arrow(%pc), %a0
    moveq #0, %d6
    move.w #TB_TEXT_X-8, %d0
    bsr.w text_string                       | (both places blank)
    addi.w #2*BOX_PITCH, %d1
    bsr.w text_string
    move.w %d1, %d2
    move.w shop_cursor(%pc), %d0
    bne.s 1f
    subi.w #2*BOX_PITCH, %d2
1:  move.w #TB_TEXT_X-8, %d1
    bsr.w town_arrow
    movem.l (%sp)+, %d0-%d2/%d6/%a0/%a3
    rts
blank_arrow:
    .asciz " "
shop_arrow_text:
    .asciz ">"
    .even

| a sound d0: the registers are kept.
town_sfx:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    bsr.w sound_play_sfx
    movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| The arrow ">" at x = d1, y = d2 (a3 = the screen). Keeps every register.
town_arrow:
    movem.l %d0-%d1/%d6/%a0, -(%sp)
    lea shop_arrow_text(%pc), %a0
    move.w %d1, %d0
    move.w %d2, %d1
    moveq #0, %d6
    bsr.w text_string
    movem.l (%sp)+, %d0-%d1/%d6/%a0
    rts

| ------------------------------------------------------------------------------------------------------------------ the inventory
| d0.b = an item: Player_RemoveItem, and when it is the one he wears or holds nothing is chosen of its kind any more (the ROM leaves a worn item that is gone: the
| port does not).
inv_consume:
    movem.l %d0-%d3/%a0, -(%sp)
    move.b %d0, %d2
    bsr.w far_inv_remove
    move.b %d2, %d0
    bsr.w far_inv_special_index
    tst.w %d1
    bpl.s 9f                                | a special item has no place to choose
    moveq #0, %d1
    move.b %d2, %d1
    lsr.b #5, %d1                           | the category
    bsr.w far_inv_selected                  | d0 = what is chosen of it
    move.b %d2, %d3
    andi.b #0x1F, %d3
    cmp.b %d3, %d0
    bne.s 9f
    tst.w %d1
    bne.s 1f
    lea hero_weapon(%pc), %a0
    move.w #255, (%a0)
    bra.s 9f
1:  cmpi.w #3, %d1
    bne.s 2f
    lea hero_magic(%pc), %a0
    move.w #-1, (%a0)
    bra.s 9f
2:  move.b #0xFF, %d2                       | the armour, the shield and the item: $FF
    bsr.w far_inv_set_selected
9:  movem.l (%sp)+, %d0-%d3/%a0
    rts

| ------------------------------------------------------------------------------------------------------------------ the message printer
| The box with an empty text area on the screen that is on show.
tb_open:
    movem.l %d0-%d4/%a3, -(%sp)
    bsr.w text_color
    bsr.w shown_screen
    moveq #TB_GROUP, %d0
    lea tb_vars(%pc), %a0
    move.w TB_Y(%a0), %d1
    moveq #TB_GROUPS, %d2
    moveq #TB_HEIGHT, %d3
    bsr.w draw_box
    bsr.w tb_blank
    movem.l (%sp)+, %d0-%d4/%a3
    rts

| The text area is blank (and the printer starts at its top left).
tb_blank:
    movem.l %d0-%d1/%a0, -(%sp)
    lea tb_rows(%pc), %a0
    moveq #TB_COLS*TB_ROWS-1, %d0
    moveq #' ', %d1
1:  move.b %d1, (%a0)+
    dbra %d0, 1b
    lea tb_vars(%pc), %a0
    clr.w TB_COL(%a0)
    clr.w TB_LINE(%a0)
    bsr.w tb_redraw
    movem.l (%sp)+, %d0-%d1/%a0
    rts

| Every cell of the text area from tb_rows.
tb_redraw:
    movem.l %d0-%d2/%a0, -(%sp)
    lea tb_rows(%pc), %a0
    moveq #0, %d2
1:  moveq #0, %d1
2:  move.b (%a0)+, %d0
    bsr.w tb_cell_char
    addq.w #1, %d1
    cmpi.w #TB_COLS, %d1
    bcs.s 2b
    addq.w #1, %d2
    cmpi.w #TB_ROWS, %d2
    bcs.s 1b
    movem.l (%sp)+, %d0-%d2/%a0
    rts

| a0 = a text ended by a 0 byte, d1 = the line: its characters (up to 16) go in the text area from the left.
tb_text:
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    move.w %d1, %d2
    moveq #0, %d1
    lea tb_rows(%pc), %a1
    move.w %d2, %d3
    lsl.w #4, %d3
    adda.w %d3, %a1
1:  move.b (%a0)+, %d0
    beq.s 9f
    cmpi.w #TB_COLS, %d1
    bcc.s 9f
    move.b %d0, (%a1)+
    bsr.w tb_cell_char
    addq.w #1, %d1
    bra.s 1b
9:  movem.l (%sp)+, %d0-%d3/%a0-%a1
    rts

| d0.b = a character, d1 = its column, d2 = its line: drawn in the text area (the screen on show). Keeps every register.
tb_cell_char:
    movem.l %d0-%d3/%d6/%a1/%a3, -(%sp)
    bsr.w shown_screen
    bsr.s tb_cell
    moveq #0, %d6
    bsr.w text_glyph
    movem.l (%sp)+, %d0-%d3/%d6/%a1/%a3
    rts

| d1 = a column, d2 = a line, a3 = the screen: a1 = the cell's first line (the byte of plane 0). Clobbers d3 (and nothing else).
tb_cell:
    lea tb_vars(%pc), %a1
    move.w %d2, %d3
    mulu.w #BOX_PITCH, %d3
    add.w TB_Y(%a1), %d3
    addq.w #4, %d3                          | the line's y
    mulu.w #STRIDE, %d3
    movea.l %a3, %a1
    adda.l %d3, %a1
    move.w %d1, %d3
    lsr.w #1, %d3
    lsl.w #3, %d3
    adda.w %d3, %a1                         | the group
    adda.w #(TB_GROUP+1)*8, %a1             | (the text starts one group in)
    btst #0, %d1
    beq.s 1f
    addq.l #1, %a1                          | the right byte of a group
1:  rts

| The text area goes up a line (the first line is lost, the last is blank).
tb_scroll:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    lea tb_rows(%pc), %a0
    lea TB_COLS(%a0), %a1
    moveq #TB_COLS*(TB_ROWS-1)/4-1, %d0
1:  move.l (%a1)+, (%a0)+
    dbra %d0, 1b
    moveq #TB_COLS-1, %d0
    moveq #' ', %d1
2:  move.b %d1, (%a0)+
    dbra %d0, 2b
    bsr.w tb_redraw
    movem.l (%sp)+, %d0-%d1/%a0-%a1
    rts

| IncLineAndReset: the next line starts at its left; after the fourth the text scrolls.
tb_next_line:
    movem.l %d0/%a0, -(%sp)
    lea tb_vars(%pc), %a0
    clr.w TB_COL(%a0)
    move.w TB_LINE(%a0), %d0
    addq.w #1, %d0
    cmpi.w #TB_ROWS, %d0
    bcc.s 1f
    move.w %d0, TB_LINE(%a0)
    bra.s 9f
1:  bsr.s tb_scroll
9:  movem.l (%sp)+, %d0/%a0
    rts

| d0 = a symbol drawn in the arrow's cell, blinking (it shows while bit 4 of the frame count is set): 0 none, 1 down arrow, 2 up arrow, 3 question mark.
tb_arrow:
    movem.l %d0-%d3/%d6/%a0-%a3, -(%sp)
    move.w %d0, %d2
    move.l frame_count(%pc), %d0
    btst #4, %d0
    bne.s 1f
    moveq #0, %d2                           | the blink: blank for 16 frames
1:  bsr.w shown_screen
    lea tb_vars(%pc), %a1
    move.w TB_Y(%a1), %d3
    addi.w #4+3*BOX_PITCH, %d3
    mulu.w #STRIDE, %d3
    movea.l %a3, %a1
    adda.l %d3, %a1
    adda.w #TB_ARROW_GROUP*8, %a1
    moveq #0, %d6
    lea arrow_images(%pc), %a0
    cmpi.w #3, %d2
    bne.s 2f
    moveq #'?', %d0
    bsr.w text_glyph
    bra.s 9f
2:  lsl.w #3, %d2
    adda.w %d2, %a0                         | (image 0 is blank)
    bsr.w tb_bitmap
9:  movem.l (%sp)+, %d0-%d3/%d6/%a0-%a3
    rts

| a0 = 8 bytes (one bit a pixel, the left pixel is the high bit), a1 = a cell's first line: drawn in the text colour on black.
tb_bitmap:
    movem.l %d2-%d4/%a0-%a2, -(%sp)
    lea text_planes(%pc), %a2
    moveq #7, %d4
1:  move.b (%a0)+, %d2
    move.b %d2, %d3
    and.b 1(%a2), %d3
    move.b %d3, (%a1)
    move.b %d2, %d3
    and.b 3(%a2), %d3
    move.b %d3, 2(%a1)
    move.b %d2, %d3
    and.b 5(%a2), %d3
    move.b %d3, 4(%a1)
    move.b %d2, %d3
    and.b 7(%a2), %d3
    move.b %d3, 6(%a1)
    lea STRIDE(%a1), %a1
    dbra %d4, 1b
    movem.l (%sp)+, %d2-%d4/%a0-%a2
    rts

| d0 = a symbol for tb_arrow: waits for A (the text stays), the arrow blinking.
tb_wait_a:
    movem.l %d0-%d1, -(%sp)
    move.w %d0, %d1
1:  bsr.w town_tick
    move.w %d1, %d0
    bsr.w tb_arrow
    lea input_state(%pc), %a0
    btst #7, IN_PAD_NEW(%a0)
    beq.s 1b
    moveq #0, %d0
    bsr.w tb_arrow_off
    movem.l (%sp)+, %d0-%d1
    rts

| The arrow's cell is blank.
tb_arrow_off:
    movem.l %d0-%d3/%d6/%a0-%a3, -(%sp)
    bsr.w shown_screen
    lea tb_vars(%pc), %a1
    move.w TB_Y(%a1), %d3
    addi.w #4+3*BOX_PITCH, %d3
    mulu.w #STRIDE, %d3
    movea.l %a3, %a1
    adda.l %d3, %a1
    adda.w #TB_ARROW_GROUP*8, %a1
    lea arrow_images(%pc), %a0
    bsr.w tb_bitmap
    movem.l (%sp)+, %d0-%d3/%d6/%a0-%a3
    rts

| d0 = a message's number (1 to 193), d1 = 0 MSG_UNSKIPPABLE, 1 MSG_QUESTION, 2 MSG. Types it and waits as the mode says. d0.w = 0 when the script goes on, 1 when the
| message was dismissed (B, or at the end of a question: no). Keeps the other registers.
tb_message:
    movem.l %d1-%d4/%a0-%a2, -(%sp)
    lea tb_vars(%pc), %a2
    move.w %d1, TB_MODE(%a2)
    subq.w #1, %d0
    bmi.w 90f
    cmpi.w #MESSAGE_COUNT, %d0
    bcc.w 90f
    add.w %d0, %d0
    movea.l town_ptr(%pc), %a0
    adda.l #ISCRIPT_MSG_OFFSETS, %a0
    move.w (%a0,%d0.w), %d1                 | the message's place in the block of messages
    movea.l town_ptr(%pc), %a0
    adda.l #ISCRIPT_MESSAGES, %a0
    adda.w %d1, %a0
    move.l %a0, TB_MSG(%a2)
    clr.w TB_TIMER(%a2)
    clr.w TB_PAUSED(%a2)
    clr.w TB_DONE(%a2)
    clr.w TB_TITLE(%a2)
    bsr.w tb_blank
1:  bsr.w town_tick                         | one frame: the text moves on, then the buttons are looked at
    lea tb_vars(%pc), %a2
    lea input_state(%pc), %a1
    moveq #0, %d3
    move.b IN_PAD_NEW(%a1), %d3             | the buttons pressed in this frame
    addq.w #1, TB_TIMER(%a2)
    tst.w TB_DONE(%a2)
    bne.w 5f
    tst.w TB_PAUSED(%a2)
    bne.w 3f
    move.w TB_TIMER(%a2), %d0
    andi.w #3, %d0
    bne.w 2f
    bsr.w tb_step
    tst.w TB_DONE(%a2)
    bne.w 5f
    tst.w TB_PAUSED(%a2)
    bne.w 3f
2:  cmpi.w #0, TB_MODE(%a2)                 | typing: B ends a MSG or a question
    beq.w 1b
    btst #6, %d3
    beq.w 1b
    bra.w 80f
3:  moveq #1, %d0                           | a pause: the down arrow, A goes on in the line below
    bsr.w tb_arrow
    btst #7, %d3
    bne.w 4f
    tst.w TB_MODE(%a2)
    beq.w 1b
    btst #6, %d3
    beq.w 1b
    bra.w 80f
4:  clr.w TB_PAUSED(%a2)
    moveq #0, %d0
    bsr.w tb_arrow_off
    tst.w TB_COL(%a2)
    beq.w 1b
    bsr.w tb_next_line                      | (the line that was being written is finished)
    bra.w 1b
5:  cmpi.w #3, TB_MODE(%a2)                 | mode 3 (the shop's): the end is the end, nothing waits
    beq.w 91f
    moveq #2, %d0                           | the end: the up arrow (a question mark for a question), A goes on
    cmpi.w #1, TB_MODE(%a2)
    bne.w 6f
    moveq #3, %d0
6:  bsr.w tb_arrow
    btst #7, %d3
    bne.w 7f
    tst.w TB_MODE(%a2)
    beq.w 1b
    btst #6, %d3
    beq.w 1b
    bra.w 80f
7:  moveq #0, %d0                           | yes (or on): a question's text is blanked
    bsr.w tb_arrow_off
    cmpi.w #1, TB_MODE(%a2)
    bne.w 91f
    bsr.w tb_blank
    bra.w 91f
80: moveq #0, %d0
    bsr.w tb_arrow_off
90: moveq #1, %d0
    bra.w 99f
91: moveq #0, %d0
99: movem.l (%sp)+, %d1-%d4/%a0-%a2
    rts

| d0 = a message's number: it is written at once, without the character sound, in an empty text area (BUY_SELL_MENU's; the ROM's IScripts_LoadAndShowMessage).
tb_instant:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    lea tb_vars(%pc), %a2
    subq.w #1, %d0
    bmi.s 9f
    cmpi.w #MESSAGE_COUNT, %d0
    bcc.s 9f
    move.w #1, TB_QUIET(%a2)
    add.w %d0, %d0
    movea.l town_ptr(%pc), %a0
    adda.l #ISCRIPT_MSG_OFFSETS, %a0
    move.w (%a0,%d0.w), %d1
    movea.l town_ptr(%pc), %a0
    adda.l #ISCRIPT_MESSAGES, %a0
    adda.w %d1, %a0
    move.l %a0, TB_MSG(%a2)
    clr.w TB_TIMER(%a2)
    clr.w TB_PAUSED(%a2)
    clr.w TB_DONE(%a2)
    clr.w TB_TITLE(%a2)
    bsr.w tb_blank
1:  bsr.w tb_step
    tst.w TB_DONE(%a2)
    beq.s 1b
    clr.w TB_QUIET(%a2)
9:  movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts

| One byte of the message (TextBox_ShowNextChar_IfReady): a character is drawn with sound 1 and the column moves on; the end of a line goes to the next; a
| pause or the end of the message is noted in tb_vars.
tb_step:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea tb_vars(%pc), %a0
1:  move.w TB_TITLE(%a0), %d1
    beq.w 4f
    cmpi.w #0x90, %d1
    beq.w 3f
    bsr.w tb_rank_char                      | the next character of the rank's name (d1 = its place)
    addq.w #1, TB_TITLE(%a0)
    tst.b %d0
    bne.w 7f
3:  clr.w TB_TITLE(%a0)                     | the name is done: the message goes on in this step
4:  movea.l TB_MSG(%a0), %a1
    moveq #0, %d0
    move.b (%a1)+, %d0
    move.l %a1, TB_MSG(%a0)
    cmpi.b #0xFF, %d0
    beq.w 12f
    cmpi.b #0xFE, %d0
    beq.w 10f
    cmpi.b #0xFD, %d0
    beq.w 8f
    cmpi.b #0xFB, %d0
    beq.w 6f
    cmpi.b #0xFC, %d0
    beq.w 11f
7:  move.b %d0, %d3                         | a character: sound 1, then it is drawn
    tst.w TB_QUIET(%a0)
    bne.s 13f
    moveq #1, %d0
    bsr.w sound_play_sfx
13:     move.b %d3, %d0
    move.w TB_COL(%a0), %d1
    move.w TB_LINE(%a0), %d2
    lea tb_rows(%pc), %a2
    lsl.w #4, %d2
    add.w %d1, %d2
    move.b %d0, (%a2,%d2.w)
    move.w TB_LINE(%a0), %d2
    bsr.w tb_cell_char
8:  addq.w #1, TB_COL(%a0)                  | (a space moves on only)
    cmpi.w #TB_COLS, TB_COL(%a0)
    bcs.w 9f
    movea.l TB_MSG(%a0), %a1
    cmpi.b #0xFF, (%a1)                     | a full line: the message ends, or waits, here
    beq.w 12f
    cmpi.b #0xFC, (%a1)
    beq.w 9f
10: tst.w TB_COL(%a0)                       | a new line
    beq.w 1b                                | (at the start of a line it is nothing: the next byte is read now)
    bsr.w tb_next_line
    bra.w 9f
6:  move.w #0x81, TB_TITLE(%a0)             | $FB: the rank's name
    moveq #0, %d1
    bsr.w tb_rank_char
    bra.w 7b
11: movea.l TB_MSG(%a0), %a1                | $FC: a pause (at the end of a message nothing)
    cmpi.b #0xFF, (%a1)
    beq.w 12f
    move.w #1, TB_PAUSED(%a0)
    bra.w 9f
12: move.w #1, TB_DONE(%a0)
9:  movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

| d1 = the place in the rank's name (low four bits are used): d0.b = its character, 0 at its end. Keeps the rest.
tb_rank_char:
    movem.l %d1-%d2/%a1, -(%sp)
    move.w hero_title(%pc), %d2
    add.w %d2, %d2
    lea rank_texts(%pc), %a1
    move.w (%a1,%d2.w), %d2
    lea game_start(%pc), %a1
    adda.l #text_data, %a1
    adda.w %d2, %a1
    andi.w #15, %d1
    move.b (%a1,%d1.w), %d0
    movem.l (%sp)+, %d1-%d2/%a1
    rts

    .ifdef SCRIPT
| (SCRIPT=n, for the tests) the script n runs once, in the frame SCRIPT_AT.
script_test:
    movem.l %d0/%a0, -(%sp)
    lea script_wait(%pc), %a0
    move.w (%a0), %d0
    bmi.s 9f
    addq.w #1, %d0
    move.w %d0, (%a0)
    cmpi.w #SCRIPT_AT, %d0
    bne.s 9f
    move.w #-1, (%a0)
    .ifdef BATCH
    bsr.w batch_run
    .else
    moveq #SCRIPT, %d0
    bsr.w iscript_run
    .endif
9:  movem.l (%sp)+, %d0/%a0
    rts

    .ifdef BATCH
| (BATCH=n, for the tests/test_iscript_batch.py) runs the n jobs of batch.bin one after the other. A job: the script's number, the buttons (auto_pad: 1 A, 2 B then A, 3 A with Sell chosen in the buy-or-sell menu) and the
| hero's state (the inventory block, hud_state, the five words hero_title, hero_next, hero_spawn, hero_weapon, hero_magic). After it the state, the number of actions
| run, each with the byte after it (a message's number), are in batch_out (the first 16; BO_SIZE bytes a job); batch_done counts the jobs that are through (batch_frames: when the last was).
    .equ BJ_STATE, INV_BYTES+10+10
    .equ BJ_SIZE, 4+BJ_STATE
    .equ BO_COUNT, BJ_STATE
    .equ BO_TRACE, BO_COUNT+2
    .equ BO_SIZE, BO_TRACE+32
batch_run:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    lea game_start(%pc), %a3                | (the tables are behind everything, out of the PC-relative reach: link.ld)
    adda.l #batch_jobs, %a3
    lea game_start(%pc), %a2
    adda.l #batch_out, %a2
    move.w (%a3)+, %d6                      | how many jobs
1:  lea batch_cur(%pc), %a0
    move.l %a2, (%a0)
    clr.w BO_COUNT(%a2)
    lea auto_pad(%pc), %a0
    move.w 2(%a3), (%a0)
    bsr.w batch_state_in
    lea hud_dirty(%pc), %a0
    st (%a0)
    move.w (%a3), %d0
    bsr.w iscript_run
    lea auto_pad(%pc), %a0
    clr.w (%a0)
    bsr.w batch_state_out
    lea batch_done(%pc), %a0
    addq.w #1, (%a0)
    move.l frame_count(%pc), 2(%a0)         | (the frame in which the last job was through)
    lea BJ_SIZE(%a3), %a3
    lea BO_SIZE(%a2), %a2
    subq.w #1, %d6
    bne.s 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

batch_state_in:                             | the job's state (at 4(a3)) becomes the hero's
    lea 4(%a3), %a0
    lea inv(%pc), %a1
    moveq #INV_BYTES-1, %d0
2:  move.b (%a0)+, (%a1)+
    dbra %d0, 2b
    lea hud_state(%pc), %a1
    moveq #9, %d0
3:  move.b (%a0)+, (%a1)+
    dbra %d0, 3b
    lea hero_title(%pc), %a1
    move.w (%a0)+, (%a1)
    lea hero_next(%pc), %a1
    move.w (%a0)+, (%a1)
    lea hero_spawn(%pc), %a1
    move.w (%a0)+, (%a1)
    lea hero_weapon(%pc), %a1
    move.w (%a0)+, (%a1)
    lea hero_magic(%pc), %a1
    move.w (%a0)+, (%a1)
    rts

batch_state_out:                            | the hero's state goes to the job's record in batch_out (a4)
    movea.l %a2, %a0
    lea inv(%pc), %a1
    moveq #INV_BYTES-1, %d0
2:  move.b (%a1)+, (%a0)+
    dbra %d0, 2b
    lea hud_state(%pc), %a1
    moveq #9, %d0
3:  move.b (%a1)+, (%a0)+
    dbra %d0, 3b
    move.w hero_title(%pc), (%a0)+
    move.w hero_next(%pc), (%a0)+
    move.w hero_spawn(%pc), (%a0)+
    move.w hero_weapon(%pc), (%a0)+
    move.w hero_magic(%pc), (%a0)+
    rts

batch_trace:                                | d0.b = the action about to run
    movem.l %d1/%a0, -(%sp)
    move.l batch_cur(%pc), %d1
    beq.s 9f
    movea.l %d1, %a0
    move.w BO_COUNT(%a0), %d1
    addq.w #1, BO_COUNT(%a0)
    cmpi.w #16, %d1
    bcc.s 9f
    add.w %d1, %d1
    move.b %d0, BO_TRACE(%a0,%d1.w)
    move.b (%a5), BO_TRACE+1(%a0,%d1.w)
9:  movem.l (%sp)+, %d1/%a0
    rts
    .endif
    .endif

| ------------------------------------------------------------------------------------------------------------------ the people
| The people of a screen (TOWN.DAT's npc.bin, tools/iscripts.py describes it): standing where the ROM puts them, behaving as the ROM's scripts say, and drawn like the
| enemies are (each frame the box of the last drawing in this screen is put back from the playfield, then they are drawn; the hero comes last, over them). They are not
| drawn during a scroll (the ROM does not draw its sprites then either): `npc_clear` is called with `enemies_clear`, `npc_load` at the end of `enemies_load`, so every way into
| a screen has it.
|
| A screen's people: the records of npc.bin's places with this area and screen (area 4: the building's id from the door; elsewhere the ROM's number of the screen,
| from the package's screen_ids). Up alone, newly pressed, with the hero's box over a person's (`Player_CheckHandlePressUpOnNPC`; the box is where the person is now: he
| walks) runs the script of the record ($FF: nothing), unless the same Up opens a door (the door comes first, as in the ROM: the main loop calls `door_check` before
| `npc_check`, and `npc_load` sets `npc_fresh` so that the pass that loaded a screen does not look); the intro trigger (entity $4F, no picture) runs its script when the hero touches it, once in a game.
|
| Behaviour. A person is a slot of the enemies' layout (E_xxx, enemy.s) with a few fields more, and the enemies' engine runs him: `npc_update` (once a frame, after the boxes
| of the last drawing are put back) is `Sprites_UpdateAll` for a person: the ops of his script (`en_ops`, and op 6, which adds a value to his x: the priest and the doctor
| stand 4 and 8 pixels on, the King 8 when the hero is near) and then the behaviour (Move toward 0, Walk 4, Hop 9, Fall 21, which here is waiting: a countdown; they turn
| at a wall, fall off a ledge, as the enemies do). The scripts are the ROM's bytes (npcwalk.bin: tools/iscripts.py `walk_file`; the program's own data, TOWN.DAT has no room),
| tools/npc_model.py is the same in Python and tests/test_npc.py checks that against the game: every kind, every frame. Nothing hurts a person or touches him.
|
| The pictures are made when the screen is entered: every (tile, attribute) a person's poses use becomes an image of the blitter's form (a mask and four planes a line)
| in the palette set's slots (`tile_convert`), the poses become lists of (dx, dy, image) in the person's slot of npc_ram (behind TOWN.DAT). Which pose, as the kind's update
| handler does (`npc_draw`): the frame comes from the kind's rule (0: two frames by the counter, 1: walking: 0, 1, 0, 2 by the counter, 0 while the phase is 2, 2 the King's: two
| frames by the counter, two more from the second phase), the mirror rule (0 never, 1 always, 2 when he faces right), the pose is 2 * frame + mirrored.
    .ifdef NPCS
    .equ NPC_SLOTS, 2
    .equ NPC_REC, 40                        | a slot: the enemies' (E_BYTES, enemy.s: 30 bytes) and at the end the fields of a person
    .equ N_RAM, NPC_REC-8                   | long: the slot's room in npc_ram
    .equ N_SCRIPT, NPC_REC-4                | the script's number ($FF: none)
    .equ N_POSE, NPC_REC-3                  | the pose last drawn (2 * frame + mirrored)
    .equ NPC_WALK_TABLE, 18*4               | npcwalk.bin: a record of four bytes a kind (the hit box type, 0, the script's offset), then the scripts
    .equ NPC_FIRST, 0x34                    | the first kind
    .equ NPC_SLOT_RAM, 2560                 | a slot's room: the table and lists of poses (up to 640 bytes), the 44 keys (words), the images (40 bytes each)
    .equ NPC_KEYS, 640
    .equ NPC_IMAGES, 720
    .equ NPC_TRIGGER, 0x4F
    .equ NPC_END, 0x7FFF                    | ends a pose's cells

| All slots empty, their boxes forgotten.
npc_clear:
    movem.l %d0/%a0, -(%sp)
    lea npc_slots(%pc), %a0
    moveq #NPC_SLOTS-1, %d0
1:  move.b #0xFF, E_ENT(%a0)
    clr.l E_KIND(%a0)
    lea NPC_REC(%a0), %a0
    dbra %d0, 1b
    lea npc_rects(%pc), %a0
    moveq #(2*NPC_SLOTS*8/4)-1, %d0
2:  clr.l (%a0)+
    dbra %d0, 2b
    movem.l (%sp)+, %d0/%a0
    rts

| The people of the screen cur_screen (see above); in a building also the palette that has their colours. Keeps every register.
npc_load:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    bsr.s npc_clear
    lea npc_fresh(%pc), %a0
    move.w #1, (%a0)
    move.l town_ptr(%pc), %d0
    beq.w 9f
    movea.l %d0, %a3
    adda.l #TOWN_NPC, %a3                   | npc.bin
    lea npc_base(%pc), %a0
    move.l %a3, (%a0)
    move.w cur_pal(%pc), %d0
    cmp.w 2(%a3), %d0
    bcc.w 9f                                | (not one of the palette sets)
    lsl.w #4, %d0
    move.l 8(%a3), %d1
    lea (%a3,%d1.l), %a0
    adda.w %d0, %a0                         | the sprite palettes' slots in this palette set
    lea conv_slots(%pc), %a1
    move.l %a0, (%a1)
    move.w cur_area(%pc), %d6
    cmpi.w #BUILDING_AREA, %d6
    bne.s 1f
    move.w building_id(%pc), %d7            | the building's id
    bra.s 2f
1:  movea.l pkg_ptr+PKG_SCREEN_IDS(%pc), %a0
    move.w cur_screen(%pc), %d0
    moveq #0, %d7
    move.b (%a0,%d0.w), %d7                 | the ROM's number of the screen
2:  move.l 16(%a3), %d0
    lea (%a3,%d0.l), %a2                    | the places
    moveq #0, %d5                           | the next slot
3:  cmpi.b #0xFF, (%a2)
    beq.s 8f
    cmp.b (%a2), %d6
    bne.s 7f
    cmp.b 1(%a2), %d7
    bne.s 7f
    cmpi.w #NPC_SLOTS, %d5
    bcc.s 8f
    bsr.w npc_place
7:  addq.l #6, %a2
    bra.s 3b
8:  cmpi.w #BUILDING_AREA, %d6
    bne.s 9f
    bsr.w scene_palette                     | the palette with the people's colours
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| a2 = a place (area, screen, entity, script, x, y), d5 = the slot for it: the slot is filled as `enemies_load` fills an enemy's (behaviour ready, the script at its start,
| the hit box type the wall tests use) and d5 goes up by one (a person that is not known is skipped). Keeps the rest.
npc_place:
    movem.l %d0-%d4/%a0-%a3, -(%sp)
    move.l %a2, %d4
    moveq #0, %d0
    move.b 2(%a2), %d0                      | the entity
    lea npc_slots(%pc), %a3
    move.w %d5, %d1
    mulu.w #NPC_REC, %d1
    adda.w %d1, %a3
    movea.l %a3, %a0
    moveq #NPC_REC/4-1, %d1
1:  clr.l (%a0)+                            | (E_KIND 0: a trigger, no picture)
    dbra %d1, 1b
    cmpi.w #NPC_TRIGGER, %d0
    bne.s 2f
    move.w npc_intro_done(%pc), %d1
    bne.w 9f
    bra.s 5f                                | the trigger: no picture
2:  movea.l npc_base(%pc), %a0
    move.l 4(%a0), %d1
    lea (%a0,%d1.l), %a1                    | the table of the kinds
    move.w (%a0), %d2
    subq.w #1, %d2
3:  move.l (%a1)+, %d1
    lea (%a0,%d1.l), %a2
    cmp.b (%a2), %d0
    beq.s 4f
    dbra %d2, 3b
    bra.w 9f                                | no such kind
4:  move.l %a2, E_KIND(%a3)
5:  movea.l %d4, %a2
    move.b %d0, E_ENT(%a3)
    move.b 3(%a2), N_SCRIPT(%a3)
    move.b 4(%a2), E_X(%a3)                 | (the flags, the fractions, the phase, the countdown are 0)
    move.b 5(%a2), E_Y(%a3)
    move.b #0xFF, E_BEH(%a3)
    move.l E_KIND(%a3), %d1
    beq.s 6f
    lea game_start(%pc), %a0                | npcwalk.bin, the program's own data: a record a kind
    adda.l #npc_walk, %a0
    subi.w #NPC_FIRST, %d0
    lsl.w #2, %d0
    move.b (%a0,%d0.w), E_HBOX(%a3)
    move.w 2(%a0,%d0.w), E_SCRIPT(%a3)
    movea.l %d1, %a2
    move.w %d5, %d1
    mulu.w #NPC_SLOT_RAM, %d1
    move.l npc_buf(%pc), %d3
    add.l %d1, %d3                          | the slot's room
    move.l %d3, N_RAM(%a3)
    movea.l %d3, %a0
    bsr.w npc_convert
6:  addq.w #1, %d5
9:  movem.l (%sp)+, %d0-%d4/%a0-%a3
    rts

| a2 = a kind's record, a0 = the room for its pictures: the table of the poses (words: where the list of each is, from the room's start; 8 at most), the lists
| (a box x0, x1, y0, y1 relative to the person, then dx, dy and an image number as words, NPC_END), the keys of the images made and the images. Keeps every register.
npc_convert:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    movea.l %a0, %a1                        | the room
    moveq #0, %d7
    move.b 1(%a2), %d7
    add.w %d7, %d7                          | the poses: each frame both ways round
    lea conv_poses(%pc), %a6
    move.w %d7, (%a6)
    clr.w 2(%a6)                            | (conv_pose)
    move.w 8(%a2), %d0
    lsl.w #4, %d0
    lea 10(%a2,%d0.w), %a3                  | the kind's table of poses (offsets from the kind's start)
    lea 16(%a1), %a5                        | where the lists go
    moveq #0, %d5                           | the images made
1:  lea conv_poses(%pc), %a6
    move.w 2(%a6), %d6
    add.w %d6, %d6
    move.w (%a3,%d6.w), %d0
    lea (%a2,%d0.w), %a0                    | the pose's cells
    move.l %a5, %d0
    sub.l %a1, %d0
    move.w %d0, (%a1,%d6.w)                 | where its list is
    movea.l %a5, %a4                        | the box goes here
    lea 8(%a5), %a5
    move.w #0x7FFF, %d0                     | x0
    move.w #-0x7FFF, %d1                    | x1
    move.w #0x7FFF, %d2                     | y0
    move.w #-0x7FFF, %d3                    | y1
2:  move.b (%a0), %d4
    cmpi.b #0x80, %d4
    beq.w 5f
    ext.w %d4
    cmp.w %d0, %d4
    bge.s 21f
    move.w %d4, %d0
21: addq.w #8, %d4
    cmp.w %d1, %d4
    ble.s 22f
    move.w %d4, %d1
22: move.b 1(%a0), %d4
    ext.w %d4
    cmp.w %d2, %d4
    bge.s 23f
    move.w %d4, %d2
23: addq.w #8, %d4
    cmp.w %d3, %d4
    ble.s 24f
    move.w %d4, %d3
24: moveq #0, %d4
    move.b 2(%a0), %d4
    lsl.w #8, %d4
    move.b 3(%a0), %d4                      | the key: tile << 8 | attribute
    lea NPC_KEYS(%a1), %a6
    moveq #0, %d6
25: cmp.w %d5, %d6
    beq.s 26f                               | not made yet
    cmp.w (%a6)+, %d4
    beq.s 28f
    addq.w #1, %d6
    bra.s 25b
26: move.w %d4, (%a6)
    move.w %d5, %d6
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    moveq #0, %d0
    move.b 2(%a0), %d0
    lsl.w #4, %d0
    lea 10(%a2,%d0.w), %a0                  | the tile
    move.w %d5, %d0
    mulu.w #SPRITE_IMAGE_BYTES, %d0
    lea NPC_IMAGES(%a1), %a1
    adda.w %d0, %a1                         | where the image goes
    move.w %d4, %d1
    moveq #1, %d0                           | with a mask
    bsr.w tile_convert
    movem.l (%sp)+, %d0-%d3/%a0-%a1
    addq.w #1, %d5
28: move.b (%a0), %d4
    ext.w %d4
    move.w %d4, (%a5)+
    move.b 1(%a0), %d4
    ext.w %d4
    move.w %d4, (%a5)+
    move.w %d6, (%a5)+
    addq.l #4, %a0
    bra.w 2b
5:  move.w #NPC_END, (%a5)+
    move.w %d0, (%a4)+
    move.w %d1, (%a4)+
    move.w %d2, (%a4)+
    move.w %d3, (%a4)
    lea conv_poses(%pc), %a6
    addq.w #1, 2(%a6)
    move.w 2(%a6), %d6
    cmp.w (%a6), %d6
    bne.w 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| a0 = a tile (16 bytes: 8 of plane 0, 8 of plane 1, the leftmost pixel in bit 7), d1.b = its attribute (bit 6 mirrored, bits 0-1 the palette), d0.w = 1 to begin each
| line with a mask byte (the blitter's image: mask and four planes), 0 for four plane bytes; a1 = where the 8 lines go. The colours 1-3 take the slots of conv_slots
| (4 bytes a palette); colour 0 is slot 0 (black, and the mask's hole). Keeps every register.
tile_convert:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    movea.l conv_slots(%pc), %a3
    move.w %d1, %d2
    andi.w #3, %d2
    lsl.w #2, %d2
    adda.w %d2, %a3                         | the four slots of this palette
    move.w %d0, %d6                         | the mask flag
    moveq #7, %d7
1:  moveq #0, %d2
    move.b (%a0), %d2                       | plane 0
    moveq #0, %d3
    move.b 8(%a0), %d3                      | plane 1
    addq.l #1, %a0
    btst #6, %d1
    beq.s 3f
    moveq #7, %d4                           | mirrored: the bits turned round
    moveq #0, %d5
    moveq #0, %d0
2:  lsr.b #1, %d2
    roxl.b #1, %d5
    lsr.b #1, %d3
    roxl.b #1, %d0
    dbra %d4, 2b
    move.b %d5, %d2
    move.b %d0, %d3
3:  tst.w %d6
    beq.s 4f
    move.b %d2, %d4
    or.b %d3, %d4
    move.b %d4, (%a1)+                      | the mask
4:  move.b %d3, %d4
    not.b %d4
    and.b %d2, %d4                          | the pixels of colour 1
    move.b %d2, %d5
    not.b %d5
    and.b %d3, %d5                          | colour 2
    and.b %d3, %d2                          | colour 3
    moveq #0, %d0                           | the plane
5:  moveq #0, %d3
    btst %d0, 1(%a3)
    beq.s 6f
    or.b %d4, %d3
6:  btst %d0, 2(%a3)
    beq.s 7f
    or.b %d5, %d3
7:  btst %d0, 3(%a3)
    beq.s 8f
    or.b %d2, %d3
8:  move.b %d3, (%a1)+
    addq.w #1, %d0
    cmpi.w #4, %d0
    bne.s 5b
    dbra %d7, 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| The boxes of the last drawing in the screen being drawn into (a4) are put back from the playfield.
npc_erase:
    movem.l %d0/%a0, -(%sp)
    lea npc_rects(%pc), %a0
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0
    moveq #NPC_SLOTS-1, %d0
1:  tst.w 2(%a0)
    beq.s 2f
    bsr.w restore_rect
    clr.l (%a0)
    clr.l 4(%a0)
2:  addq.l #8, %a0
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0
    bra.w npc_update                        | (then the people move: once a frame, here, between the box going and the next drawing)

| Sprites_UpdateAll for the people: the slots in order (the first of the screen is the ROM's slot 7), each its script's ops and its behaviour. The behaviours look at the
| screen's blocks as the enemies' do (en_blocks: enemies_update sets it later in the frame; the people go first). Nothing is done on a screen without people.
npc_update:
    movem.l %d0-%d7/%a0-%a5, -(%sp)
    lea npc_slots(%pc), %a3
    moveq #NPC_SLOTS-1, %d7
    moveq #0, %d5
1:  tst.l E_KIND(%a3)
    beq.s 2f
    cmpi.b #0xFF, E_ENT(%a3)
    beq.s 2f
    moveq #1, %d5                           | (someone is there)
2:  lea NPC_REC(%a3), %a3
    dbra %d7, 1b
    tst.w %d5
    beq.s 9f
    move.w cur_screen(%pc), %d0
    bsr.w screen_flags                      | (as enemies_update: the screen's flags, its block ids)
    lea en_blocks(%pc), %a1
    move.l %a2, (%a1)+
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a0
    adda.l %d0, %a0
    move.l %a0, (%a1)
    lea game_start(%pc), %a5
    adda.l #npc_walk+NPC_WALK_TABLE, %a5    | the scripts
    lea npc_slots(%pc), %a3
    moveq #NPC_SLOTS-1, %d7
3:  tst.l E_KIND(%a3)
    beq.s 4f
    cmpi.b #0xFF, E_ENT(%a3)
    beq.s 4f
    bsr.s npc_behave
4:  lea NPC_REC(%a3), %a3
    dbra %d7, 3b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a5
    rts

| Sprites_UpdateBehavior for the person in a3 (a5 = the scripts): the ops (op 6, add to x, is here; the others are the enemies', which stop at it), then the behaviour.
| The behaviours end by storing the script's offset (en_behaviour_end).
npc_behave:
    moveq #0, %d6
    move.w E_SCRIPT(%a3), %d6
1:  cmpi.b #6, (%a5,%d6.w)
    bne.s 2f
    move.b 3(%a5,%d6.w), %d0                | BScript_Op_AddToSpriteData (the address is CurrentSprites_XPos_Full: it is the only one used)
    add.b %d0, E_X(%a3)
    addq.w #4, %d6
    bra.s 1b
2:  bsr.w en_ops
    cmpi.b #6, (%a5,%d6.w)
    beq.s 1b
    moveq #0, %d0
    move.b E_BEH(%a3), %d0
    andi.w #0x7F, %d0
    beq.w beh_move_toward
    cmpi.w #4, %d0
    beq.w beh_walk
    cmpi.w #9, %d0
    beq.w beh_hop
    cmpi.w #21, %d0
    beq.w beh_fall
    bra.w en_behaviour_end

| The people drawn into the screen a4, their boxes noted for npc_erase.
npc_draw:
    movem.l %d0-%d7/%a0-%a3/%a5-%a6, -(%sp)
    lea npc_slots(%pc), %a3
    moveq #0, %d7                           | the slot
1:  cmpi.b #0xFF, E_ENT(%a3)
    beq.w 8f
    movea.l E_KIND(%a3), %a2
    move.l %a2, %d0
    beq.w 8f                                | (a trigger has no picture)
    moveq #0, %d0                           | the frame: the kind's update handler
    move.w en_counter(%pc), %d1
    move.b 2(%a2), %d2                      | the rule: 0 two frames by the counter, 1 the walkers', 2 the King's
    cmpi.b #1, %d2
    bne.s 31f
    cmpi.b #2, E_PHASE(%a3)                 | (frame 0 while the phase is 2)
    beq.s 3f
    lsr.w #3, %d1
    andi.w #3, %d1
    lea npc_walk_frames(%pc), %a0
    move.b (%a0,%d1.w), %d0
    bra.s 3f
31: cmpi.b #2, %d2
    bne.s 32f
    cmpi.b #2, E_PHASE(%a3)                 | the King: two more frames from the second phase on
    bne.s 32f
    moveq #2, %d0
32: lsr.w #4, %d1
    andi.w #1, %d1
    add.w %d1, %d0
3:  moveq #0, %d2
    move.b 3(%a2), %d2                      | the mirror rule: 0 never, 1 always, 2 when it faces right
    cmpi.b #2, %d2
    bne.s 4f
    move.b E_FLAGS(%a3), %d2
    andi.w #1, %d2
4:  add.w %d0, %d0
    add.w %d2, %d0                          | the pose
    move.b %d0, N_POSE(%a3)
    add.w %d0, %d0
    movea.l N_RAM(%a3), %a6
    move.w (%a6,%d0.w), %d0
    lea (%a6,%d0.w), %a5                    | the pose's list
    lea NPC_IMAGES(%a6), %a6
    lea npc_rects(%pc), %a2
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a2
    move.w %d7, %d0
    lsl.w #3, %d0
    adda.w %d0, %a2                         | this person's box in this screen
    moveq #0, %d4
    move.b E_X(%a3), %d4
    moveq #0, %d5
    move.b E_Y(%a3), %d5
    sub.w camera(%pc), %d5
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d4, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a2)+
    move.w (%a5)+, %d0
    add.w %d5, %d0
    move.w %d0, (%a2)
    move.w %d7, -(%sp)
5:  move.w (%a5)+, %d0
    cmpi.w #NPC_END, %d0
    beq.s 7f
    moveq #0, %d4                           | (blit_tile clobbers d0-d7)
    move.b E_X(%a3), %d4
    moveq #0, %d5
    move.b E_Y(%a3), %d5
    sub.w camera(%pc), %d5
    add.w %d4, %d0
    move.w (%a5)+, %d1
    add.w %d5, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a6,%d2.l), %a1
    bsr.w blit_tile                         | (clobbers d0-d7, a0-a2)
    bra.s 5b
7:  move.w (%sp)+, %d7
    lea npc_rects(%pc), %a0                 | what reached into a side margin is cleared again
    move.w slot_index(%pc), %d0
    lsl.w #4, %d0
    adda.w %d0, %a0
    move.w %d7, %d0
    lsl.w #3, %d0
    adda.w %d0, %a0
    movem.w (%a0), %d0-%d3
    bsr.w clear_box
8:  lea NPC_REC(%a3), %a3
    addq.w #1, %d7
    cmpi.w #NPC_SLOTS, %d7
    blt.w 1b
    movem.l (%sp)+, %d0-%d7/%a0-%a3/%a5-%a6
    rts

| Player_CheckHandlePressUpOnNPC and Player_HandleTouchNPC: the hero's box against each person's (bounds from the kind: left, top, width, height; the trigger's are
| 0, 0, 16, 192): (hero x + 11 - (x + left)) < width + 11 and (hero y + 27 - (y + top)) < height + 27, unsigned. Up alone and newly pressed runs the person's script
| (not $FF); touching the trigger runs its script (once in a game).
npc_check:
    movem.l %d0-%d7/%a0-%a3, -(%sp)
    lea npc_fresh(%pc), %a0
    tst.w (%a0)
    beq.s 0f
    clr.w (%a0)                             | (the people were loaded in this pass: a door, a scroll: Up was for that)
    bra.w 9f
0:  move.w hero_dead(%pc), %d0
    bne.w 9f
    lea input_state(%pc), %a0
    moveq #0, %d6
    move.b IN_PAD_NEW(%a0), %d6
    lea npc_slots(%pc), %a3
    moveq #NPC_SLOTS-1, %d4
1:  cmpi.b #0xFF, E_ENT(%a3)
    beq.w 8f
    movea.l E_KIND(%a3), %a0
    move.l %a0, %d0
    bne.s 2f
    moveq #0, %d1                           | the trigger
    moveq #0, %d2
    moveq #16, %d3
    move.w #192, %d0
    bra.s 3f
2:  move.b 4(%a0), %d1
    ext.w %d1                               | left (signed)
    moveq #0, %d2
    move.b 5(%a0), %d2                      | top
    moveq #0, %d3
    move.b 6(%a0), %d3                      | width
    moveq #0, %d0
    move.b 7(%a0), %d0                      | height
3:  move.w hero_x(%pc), %d5
    addi.w #11, %d5
    moveq #0, %d7
    move.b E_X(%a3), %d7                    | (where he is now: a person walks)
    sub.w %d7, %d5
    sub.w %d1, %d5
    addi.w #11, %d3
    cmp.w %d3, %d5
    bcc.s 8f
    move.w hero_y(%pc), %d5
    addi.w #27, %d5
    moveq #0, %d7
    move.b E_Y(%a3), %d7
    sub.w %d7, %d5
    sub.w %d2, %d5
    addi.w #27, %d0
    cmp.w %d0, %d5
    bcc.s 8f
    move.l E_KIND(%a3), %d0                 | his box is over this one
    bne.s 5f
    lea npc_intro_done(%pc), %a0            | the trigger: once
    move.w #1, (%a0)
    moveq #0, %d0
    move.b N_SCRIPT(%a3), %d0
    move.b #0xFF, E_ENT(%a3)
    bra.s 6f
5:  cmpi.w #0x08, %d6                       | Up and nothing else
    bne.s 8f
    moveq #0, %d0
    move.b N_SCRIPT(%a3), %d0
    cmpi.b #0xFF, %d0
    beq.s 8f
6:  bsr.w iscript_run
    bra.s 9f
8:  lea NPC_REC(%a3), %a3
    dbra %d4, 1b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a3
    rts

| In a building: the building palette with the people's colours added (npc.bin) replaces the package's palette (the package is in memory: every later load of its
| palette, the death fade, the text colour, has the people's colours too) and is put on the hardware at once. Keeps every register.
scene_palette:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    move.w cur_pal(%pc), %d0
    subi.w #17, %d0                         | the building palette sets are $11 to $1A
    cmpi.w #10, %d0
    bcc.s 9f
    move.l town_ptr(%pc), %d1
    beq.s 9f
    movea.l %d1, %a1
    adda.l #TOWN_NPC, %a1
    move.l 12(%a1), %d1
    lea (%a1,%d1.l), %a0
    lsl.w #5, %d0
    adda.w %d0, %a0                         | the 16 words of this building
    movea.l pkg_ptr+PKG_PALETTE(%pc), %a1
    movea.l #PALETTE, %a2
    moveq #15, %d0
1:  move.w (%a0), (%a1)+
    move.w (%a0)+, (%a2)+
    dbra %d0, 1b
9:  movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| The variables (in .text.early: the room in .data is used up).
    .even
npc_slots:                                  | NPC_SLOTS records of NPC_REC bytes
    .rept NPC_SLOTS
    .byte 0xFF
    .space NPC_REC-1
    .endr
npc_rects:                                  | per screen, per slot: x0, x1, y0, y1 of the last drawing
    .space 2*NPC_SLOTS*8
npc_base:
    .long 0                                 | npc.bin in memory
conv_slots:
    .long 0                                 | the 16 slot bytes tile_convert reads (4 a palette)
conv_poses:
    .word 0, 0                              | npc_convert: how many poses, the one being made
npc_intro_done:
    .word 0                                 | the intro trigger has run (once in a game)
npc_fresh:
    .word 0                                 | `npc_load` ran since the last `npc_check`
npc_walk_frames:
    .byte 0, 1, 0, 2                        | the walkers' frames by the counter (SpriteUpdateHandler_NPC_Walking)
building_id:
    .word 0                                 | the building he is in: its id from the door (src/viewer.s enter_building)
portrait_k:
    .word -1                                | the portrait up (-1: none)
portrait_f:
    .word -1                                | the eyes and mouth frame drawn last (f = 0 to 3; -1: none yet)
    .endif
shop_count:
    .word 0                                 | the shop box: the entries, the cursor, the items and the prices
shop_cursor:
    .word 0
shop_items:
    .space 8
shop_costs:
    .space 16

    .section .data
    .even
iscript_ops:                                | the actions by their number
    .word op_end-iscript_ops, op_msg_unskippable-iscript_ops, op_msg_question-iscript_ops, op_msg-iscript_ops
    .word op_check_title-iscript_ops, op_pay_gold-iscript_ops, op_set_spawn-iscript_ops, op_add_item-iscript_ops
    .word op_open_shop-iscript_ops, op_add_gold-iscript_ops, op_add_mp-iscript_ops, op_if_quest-iscript_ops
    .word op_if_rank-iscript_ops, op_if_gold-iscript_ops, op_set_quest-iscript_ops, op_buy_sell-iscript_ops
    .word op_consume-iscript_ops, op_sell_menu-iscript_ops, op_if_item-iscript_ops, op_add_hp-iscript_ops
    .word op_password-iscript_ops, iop_finish-iscript_ops, op_msg_question_jump-iscript_ops, op_jump-iscript_ops
rank_texts:
    .word TEXT_RANK_0, TEXT_RANK_1, TEXT_RANK_2, TEXT_RANK_3, TEXT_RANK_4, TEXT_RANK_5, TEXT_RANK_6, TEXT_RANK_7
    .word TEXT_RANK_8, TEXT_RANK_9, TEXT_RANK_10, TEXT_RANK_11, TEXT_RANK_12, TEXT_RANK_13, TEXT_RANK_14, TEXT_RANK_15
arrow_images:                               | blank, down arrow, up arrow
    .byte 0, 0, 0, 0, 0, 0, 0, 0
    .byte 0x18, 0x18, 0x18, 0x18, 0xDB, 0x7E, 0x3C, 0x18
    .byte 0x18, 0x3C, 0x7E, 0xDB, 0x18, 0x18, 0x18, 0x18
town_name:
    .asciz "TOWN.DAT"
    .even
town_ptr:
    .long 0                                 | TOWN.DAT in memory (0: it was not read)
town_buf:
    .long 0                                 | where it is read to: TOS's own screen (32 KB at the top of memory, not used while the program shows its own screens)
npc_buf:
    .long 0                                 | the room for the pictures of the people (NPC_RAM_BYTES), behind the room of the packages
town_sp:
    .long 0
tb_vars:
    .space TB_VARS_BYTES
tb_rows:
    .space TB_COLS*TB_ROWS
    .ifdef SCRIPT
script_wait:
    .word 0
    .endif
    .ifdef BATCH
auto_pad:
    .word 0
batch_done:
    .word 0
batch_frames:
    .long 0
batch_cur:
    .long 0
    .section .batchdata
batch_jobs:
    .incbin "batch.bin"
batch_out:
    .space BO_SIZE*BATCH
    .section .data
    .endif
    .even
    .ifdef NPCS
    .section .herodata
    .even
npc_walk:                                   | npcwalk.bin (tools/iscripts.py `walk_file`): the people's behaviour scripts; reached as game_start + npc_walk (it is out of the early code's reach)
    .incbin "npcwalk.bin"
    .even
    .endif
    .text
