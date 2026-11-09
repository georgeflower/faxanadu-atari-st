| Items: the things that lie on the screens (the ROM's category 5): potions, the glove, the ointment, the tools and the drops of the bosses. What the hero has
| picked up is the inventory block `inv`, laid out as the ROM's RAM is (the lists and their counts, the special items, the quests). tools/enemy_model.py
| (behaviour_* for the sprites, pickup for the hero) is the reference; tests/test_enemy.py and tests/test_items.py check it against the game.

    .equ INV_WEAPONS, 0                     | WeaponInventory, ArmorInventory, ShieldInventory, MagicInventory: four bytes each; ItemInventory: eight
    .equ INV_ARMOURS, 4
    .equ INV_SHIELDS, 8
    .equ INV_MAGIC, 12
    .equ INV_ITEMS, 16
    .equ INV_NWEAPONS, 24                   | how many of each the hero has (NumberOfWeapons, ...)
    .equ INV_NARMOURS, 25
    .equ INV_NSHIELDS, 26
    .equ INV_NMAGIC, 27
    .equ INV_NITEMS, 28
    .equ INV_SPECIAL, 29                    | SpecialItems: bit 0 Black Onyx, 1 Pendant, 2 Magical Rod, 3 Elixir, 4 Demon's Ring, 5 Ring of Dworf, 6 Ruby Ring, 7 Ring of Elf
    .equ INV_QUESTS, 30                     | Quests: bit 3 Wing Boots, bit 4 Mattock
    .equ INV_GLOVE, 31                      | DurationGlove and DurationOintment: seconds left, $FF: not in force
    .equ INV_OINTMENT, 32
    .equ INV_VISITS, 33                     | Screen_TrackedVisitCount: the items that come every fourth time count in it
    .equ INV_ARMOUR, 34                     | SelectedArmor and SelectedShield: what he wears ($FF: none)
    .equ INV_SHIELD, 35
    .equ INV_ITEM, 36                       | what he holds of the items ($FF: nothing); the worn weapon and spell are the words hero_weapon and hero_magic
    .equ INV_BYTES, 38

    .text
| The behaviours 41 to 56 and 61 of the ROM's table (d0): Ointment, Glove, what the bosses leave, the items that are there every fourth time, the Magical Rod.
beh_item:
    cmpi.w #41, %d0
    beq.w beh_ointment
    cmpi.w #42, %d0
    beq.w beh_glove
    cmpi.w #61, %d0
    beq.w beh_rod
    cmpi.w #50, %d0
    bcc.w beh_random_item
    bra.w beh_drop_item

item_gone:                                  | Sprites_Remove
    move.b #0xFF, E_ENT(%a3)
    bra.w en_behaviour_end

beh_ointment:                               | the ointment lies about while its effect is not in force, and falls to the ground
    lea inv+INV_OINTMENT(%pc), %a0
    bra.s item_timed
beh_glove:
    lea inv+INV_GLOVE(%pc), %a0
item_timed:
    btst #6, E_FLAGS(%a3)
    bne.s 1f
    tst.b (%a0)
    bpl.s item_gone                         | in force: it is not there
    bset #6, E_FLAGS(%a3)
1:  bsr.w en_can_move
    bsr.w en_fall_step
    bra.w en_behaviour_end

beh_rod:                                    | SpriteBehavior_ShowMagicalRod: gone when he has it
    btst #2, inv+INV_SPECIAL(%pc)
    bne.s item_gone
    bra.w en_behaviour_end

| SpriteBehavior_RandomlyShowItem_50 to _56: every fourth time (the count is one for all of them) the item is there; it is hidden while an enemy is on the screen.
beh_random_item:
    btst #6, E_FLAGS(%a3)
    bne.s 3f
    lea inv+INV_VISITS(%pc), %a0
    addq.b #1, (%a0)
    cmpi.b #4, (%a0)
    bcs.s item_gone
    clr.b (%a0)
    clr.b E_PHASE(%a3)
    bset #6, E_FLAGS(%a3)
3:  bsr.w en_any_enemy
    tst.w %d0
    bne.s 4f
    bclr #4, E_FLAGS(%a3)
    bra.w en_behaviour_end
4:  bset #4, E_FLAGS(%a3)
    bra.w en_behaviour_end

| d0 = 1 when a sprite of the category 0 (an enemy) is on the screen.
en_any_enemy:
    movem.l %d1/%a0-%a1, -(%sp)
    lea enemies(%pc), %a0
    moveq #8-1, %d1
1:  cmpi.b #0xFF, E_ENT(%a0)
    beq.s 2f
    movea.l E_KIND(%a0), %a1
    tst.b K_CAT+1(%a1)
    beq.s 8f
2:  lea E_BYTES(%a0), %a0
    dbra %d1, 1b
    moveq #0, %d0
    bra.s 9f
8:  moveq #1, %d0
9:  movem.l (%sp)+, %d1/%a0-%a1
    rts

| What the bosses leave (43 Battle Suit, 44 Battle Helmet, 45 Dragon Slayer, 46 Mattock, 47 Wing Boots, 48 Black Onyx, 49 Pendant): not there when he has it
| already (the first three wipe the whole screen's sprites); hidden while its boss is on the screen.
beh_drop_item:
    move.w %d0, %d4
    subi.w #43, %d4
    btst #6, E_FLAGS(%a3)
    bne.w 8f
    lea inv(%pc), %a2
    cmpi.w #3, %d4
    bcc.s 5f
    cmpi.w #2, %d4
    beq.s 1f
    lea drop_worn(%pc), %a0                 | the armour or the shield he wears
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
    cmpi.b #3, (%a2,%d1.w)
    beq.w item_clear_all
    bra.s 2f
1:  move.w hero_weapon(%pc), %d1             | the weapon in his hand
    cmpi.w #3, %d1
    beq.w item_clear_all
2:  lea drop_list(%pc), %a0                 | or one in the list (the game looks for the number 3)
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
    lea (%a2,%d1.w), %a1
    lea drop_count(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
    move.b (%a2,%d1.w), %d1
    bsr.w item_has
    tst.w %d0
    bne.w item_clear_all
    bra.s 6f
5:  lea drop_mask-3(%pc), %a0               | 46 to 49: a quest bit or a special item bit
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
    lea drop_where-3(%pc), %a0
    moveq #0, %d2
    move.b (%a0,%d4.w), %d2
    and.b (%a2,%d2.w), %d1
    bne.w item_gone
6:  clr.b E_PHASE(%a3)
    bset #6, E_FLAGS(%a3)
8:  lea drop_boss(%pc), %a0                 | hidden while its boss is on the screen
    moveq #0, %d1
    move.b (%a0,%d4.w), %d1
    lea enemies(%pc), %a0
    moveq #8-1, %d2
9:  cmp.b E_ENT(%a0), %d1
    beq.s 10f
    lea E_BYTES(%a0), %a0
    dbra %d2, 9b
    bclr #4, E_FLAGS(%a3)
    bra.w en_behaviour_end
10: bset #4, E_FLAGS(%a3)
    bra.w en_behaviour_end

item_clear_all:                             | Sprites_ClearAllEntities
    lea enemies(%pc), %a0
    moveq #8-1, %d0
1:  move.b #0xFF, E_ENT(%a0)
    lea E_BYTES(%a0), %a0
    dbra %d0, 1b
    bra.w en_behaviour_end

| d0 = 1 when the list a1 of d1.b entries holds the number 3.
item_has:
    moveq #0, %d0
    andi.w #0xFF, %d1
    bra.s 2f
1:  cmpi.b #3, (%a1)+
    bne.s 2f
    moveq #1, %d0
    rts
2:  dbra %d1, 1b
    rts

| Player_HandleTouchItem for the slot a3 (d5 = its kind): the ROM's message, then what the item does (Player_PickUp), and it is gone.
item_pickup:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    moveq #0, %d6
    move.b %d5, %d6
    subi.w #0x48, %d6
    move.w %d6, %d0
    add.w %d0, %d0
    lea item_texts(%pc), %a0
    move.w (%a0,%d0.w), %d0                 | the message (the text's place in text_data)
    beq.s 1f
    lea text_data(%pc), %a0
    adda.w %d0, %a0
    bsr.w message_box
1:  lea item_actions(%pc), %a0              | what it does: the action, a value, the quest bit it sets
    move.w %d6, %d0
    add.w %d6, %d0
    add.w %d6, %d0
    adda.w %d0, %a0
    lea inv(%pc), %a2
    move.b 2(%a0), %d0
    or.b %d0, INV_QUESTS(%a2)
    moveq #0, %d1
    move.b 1(%a0), %d1
    moveq #0, %d0
    move.b (%a0), %d0
    cmpi.w #2, %d0                          | (the poison makes its own sound)
    beq.s 2f
    movem.w %d0-%d1, -(%sp)
    moveq #8, %d0
    bsr.w sound_play_sfx
    movem.w (%sp)+, %d0-%d1
2:  add.w %d0, %d0
    lea item_jumps(%pc), %a0
    move.w (%a0,%d0.w), %d0
    jsr (%a0,%d0.w)
    move.b #0xFF, E_ENT(%a3)
    movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| GameLoop_CountdownItems for the glove and the ointment: every 64th frame each loses a second; at the end of its last one (it goes from 0 to $FF) a message
| says the power is gone. (Called once a frame.)
items_tick:
    movem.l %d0-%d1/%a0-%a2, -(%sp)
    lea item_ticks(%pc), %a0
    addq.w #1, (%a0)
    move.w (%a0), %d0
    andi.w #0x3F, %d0
    bne.w 9f
    lea hourglass(%pc), %a1                 | the hour glass first, then the wing boots
    tst.w (%a1)
    bmi.s 1f
    subq.w #1, (%a1)
    bpl.s 1f
    lea text_data+TEXT_HOURGLASS_GONE(%pc), %a0
    bsr.w message_box
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0      | Areas_DefaultMusic comes back
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
1:  lea hero_wings(%pc), %a1
    tst.w (%a1)
    bmi.s 2f
    subq.w #1, (%a1)
    bmi.s 3f
    move.b 1(%a1), %d0                      | the time on the HUD
    bsr.w hud_set_time
    bra.s 2f
3:  lea text_data+TEXT_WINGS_GONE(%pc), %a0
    bsr.w message_box
2:  lea inv(%pc), %a2
    lea INV_GLOVE(%a2), %a1
    lea text_data+TEXT_GLOVE_GONE(%pc), %a0
    bsr.s item_count
    lea INV_OINTMENT(%a2), %a1
    lea text_data+TEXT_OINTMENT_GONE(%pc), %a0
    bsr.s item_count
9:  movem.l (%sp)+, %d0-%d1/%a0-%a2
    rts

| UI_DrawTimeValue: d0.b = the seconds on the HUD (the ROM draws it only when the boots are put on and at each tick; it stays after they are gone).
hud_set_time:
    movem.l %a0, -(%sp)
    lea hud_state(%pc), %a0
    move.b %d0, 8(%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    movem.l (%sp)+, %a0
    rts

item_count:                                 | a1 = the time left, a0 = the message for its end
    tst.b (%a1)
    bmi.s 1f
    subq.b #1, (%a1)
    bpl.s 1f
    movem.l %a1-%a2, -(%sp)
    bsr.w message_box
    movem.l (%sp)+, %a1-%a2
1:  rts

item_jumps:
    .word item_none-item_jumps, item_add-item_jumps, item_poison-item_jumps, item_glove-item_jumps, item_ointment-item_jumps
    .word item_special-item_jumps, item_suit-item_jumps, item_helmet-item_jumps, item_slayer-item_jumps

item_none:
    rts

item_add:                                   | Player_PickUpItem: d1 = the item; nothing when he has eight
    moveq #0, %d0
    move.b INV_NITEMS(%a2), %d0
    cmpi.b #8, %d0
    bcc.s 1f
    move.b %d1, INV_ITEMS(%a2,%d0.w)
    addq.b #1, INV_NITEMS(%a2)
1:  rts

item_poison:                                | 16 power off, nothing taken away for armour; 60 frames of invincibility and the knock-back
    moveq #4, %d0
    bsr.w sound_play_sfx
    lea hero_invinc(%pc), %a0
    move.w #0x3C, (%a0)
    move.w #1, hero_knock-hero_invinc(%a0)
    move.w #0x1000, %d0
    bra.w en_reduce_hp

item_glove:                                 | 20 seconds of more strength, and 100 experience
    move.b #20, INV_GLOVE(%a2)
    bra.s item_100
item_ointment:                              | 30 seconds in which nothing hurts, and 100 experience
    move.b #30, INV_OINTMENT(%a2)
item_100:
    move.w #100, %d0
    bra.w exp_add

| Player_UpdateExperience: d0.w = the experience gained (the most is 65535). Player_CheckReachedNextTitle: when the experience has reached what the next rank
| needs (PLAYER_TITLE_EXP_NEEDED[NextPlayerTitle]) the rank earned goes up one (silently: a guru gives it, hero_title stays). Clobbers nothing.
exp_add:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    lea hud_state(%pc), %a0
    add.w %d0, 2(%a0)
    bcc.s 1f
    move.w #0xFFFF, 2(%a0)
1:  lea hud_dirty(%pc), %a1
    st (%a1)
    lea hero_next(%pc), %a1
    move.w (%a1), %d0
    cmpi.w #15, %d0
    bcc.s 9f
    add.w %d0, %d0
    lea title_table(%pc), %a0
    move.w (%a0,%d0.w), %d1                 | what the next rank needs
    lea hud_state+2(%pc), %a0
    move.w (%a0), %d2
    cmp.w %d1, %d2
    bcs.s 9f
    addq.w #1, (%a1)
9:  movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

item_special:                               | Black Onyx, Pendant, Elixir, Magical Rod
    or.b %d1, INV_SPECIAL(%a2)
    rts

| The Battle Suit, the Battle Helmet and the Dragon Slayer go in the next place of their list, the last one when it is full; the suit and the slayer look at
| the wrong list for how many there are, as the ROM does.
item_suit:
    lea INV_ARMOURS(%a2), %a0
    moveq #0, %d0
    move.b INV_NWEAPONS(%a2), %d0
    lea INV_NARMOURS(%a2), %a1
    bra.s item_put
item_helmet:
    lea INV_SHIELDS(%a2), %a0
    moveq #0, %d0
    move.b INV_NSHIELDS(%a2), %d0
    lea INV_NSHIELDS(%a2), %a1
    bra.s item_put
item_slayer:
    lea INV_WEAPONS(%a2), %a0
    moveq #0, %d0
    move.b INV_NARMOURS(%a2), %d0
    lea INV_NWEAPONS(%a2), %a1
item_put:
    cmpi.b #4, %d0
    bcs.s 1f
    moveq #3, %d0
1:  move.b #3, (%a0,%d0.w)
    addq.b #1, %d0
    move.b %d0, (%a1)
    rts

    .section .rodata
    .even
drop_worn:                                  | (43, 44) the offsets in inv of what he wears
    .byte INV_ARMOUR, INV_SHIELD
drop_list:                                  | (43 to 45) the list, and where its count is
    .byte INV_ARMOURS, INV_SHIELDS, INV_WEAPONS
drop_count:
    .byte INV_NARMOURS, INV_NSHIELDS, INV_NWEAPONS
drop_mask:                                  | (46 to 49) the bit that says he has it, and where: the quests (Mattock, Wing Boots) or the special items (Black Onyx, Pendant)
    .byte 0x10, 0x08, 0x01, 0x02
drop_where:
    .byte INV_QUESTS, INV_QUESTS, INV_SPECIAL, INV_SPECIAL
drop_boss:                                  | (43 to 49) the boss they wait for: Zoradohna, Zoradohna, King Grieve, Ripasheiku, Zorugeriru, Zoradohna, Ripasheiku
    .byte 0x2E, 0x2E, 0x32, 0x2D, 0x31, 0x2E, 0x2D
    .even
item_texts:                                 | the message of the items from entity $48 to $60 (a place in text_data, 0: none)
    .word ITEMTXT_48
    .word ITEMTXT_49
    .word ITEMTXT_4A
    .word ITEMTXT_4B
    .word ITEMTXT_4C
    .word ITEMTXT_4D
    .word ITEMTXT_4E
    .word ITEMTXT_4F
    .word ITEMTXT_50
    .word ITEMTXT_51
    .word ITEMTXT_52
    .word ITEMTXT_53
    .word ITEMTXT_54
    .word ITEMTXT_55
    .word ITEMTXT_56
    .word ITEMTXT_57
    .word ITEMTXT_58
    .word ITEMTXT_59
    .word ITEMTXT_5A
    .word ITEMTXT_5B
    .word ITEMTXT_5C
    .word ITEMTXT_5D
    .word ITEMTXT_5E
    .word ITEMTXT_5F
    .word ITEMTXT_60
item_actions:                               | by entity from $48: 0 nothing, 1 an item (the value), 2 poison, 3 glove, 4 ointment, 5 a special item (the bit), 6 suit, 7 helmet, 8 slayer; the quest bit it sets
    .byte 3, 0, 0                      | 0x48
    .byte 5, 1, 0                      | 0x49
    .byte 5, 2, 0                      | 0x4a
    .byte 1, 16, 0                      | 0x4b
    .byte 2, 0, 0                      | 0x4c
    .byte 5, 8, 0                      | 0x4d
    .byte 4, 0, 0                      | 0x4e
    .byte 0, 0, 0                      | 0x4f
    .byte 1, 9, 0                      | 0x50
    .byte 0, 0, 0                      | 0x51
    .byte 0, 0, 0                      | 0x52
    .byte 0, 0, 0                      | 0x53
    .byte 0, 0, 0                      | 0x54
    .byte 1, 15, 0                      | 0x55
    .byte 1, 13, 0                      | 0x56
    .byte 5, 4, 0                      | 0x57
    .byte 6, 0, 0                      | 0x58
    .byte 7, 0, 0                      | 0x59
    .byte 8, 0, 0                      | 0x5a
    .byte 1, 9, 16                      | 0x5b
    .byte 1, 15, 8                      | 0x5c
    .byte 1, 16, 0                      | 0x5d
    .byte 2, 0, 0                      | 0x5e
    .byte 3, 0, 0                      | 0x5f
    .byte 4, 0, 0                      | 0x60
    .even

    .text
| ---------------------------------------------------------------------------------------------------------------------------- using items
| GameLoop_CheckUseCurrentItem: Down held and B pressed just now, not jumping or falling: the item he holds (INV_ITEM, a number of the ROM's list) is used.
| Keys and rings do nothing here (a key is used at its door). Clobbers nothing.
use_item:
    movem.l %d0-%d2/%a0-%a2, -(%sp)
    move.w hero_dead(%pc), %d0
    bne.w 9f
    lea input_state(%pc), %a0
    btst #6, IN_PAD_NEW(%a0)
    beq.w 9f
    btst #2, IN_PAD(%a0)
    beq.w 9f
    move.b hero_x+19(%pc), %d0              | not jumping (bit 0), not falling (bit 2)
    andi.b #5, %d0
    bne.w 9f
    moveq #0, %d0
    move.b inv+INV_ITEM(%pc), %d0
    cmpi.b #13, %d0
    beq.s 1f
    cmpi.b #15, %d0
    beq.s 2f
    cmpi.b #9, %d0
    beq.s 3f
    cmpi.b #16, %d0
    bne.w 9f
    lea text_data+TEXT_USED_POTION(%pc), %a0    | the Red Potion: full power, a step at a time
    bsr.s use_spent
    moveq #2, %d1
    bsr.w fill_power
    bra.w 9f
1:  lea text_data+TEXT_USED_HOURGLASS(%pc), %a0 | the Hour Glass: half the power, 15 seconds in which the enemies stand still, its song
    bsr.s use_spent
    lea hud_state(%pc), %a0
    lea hero_hpl(%pc), %a1
    moveq #0, %d0
    move.b (%a0), %d0
    lsl.w #8, %d0
    move.b (%a1), %d0
    lsr.w #1, %d0
    move.b %d0, (%a1)
    lsr.w #8, %d0
    move.b %d0, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    lea hourglass(%pc), %a0
    move.w #15, (%a0)
    moveq #0x0B, %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    bra.w 9f
2:  lea text_data+TEXT_USED_WINGS(%pc), %a0     | the Wing Boots: seconds by his rank
    bsr.s use_spent
    move.w hero_title(%pc), %d0
    lsr.w #2, %d0
    andi.w #3, %d0
    lea wings_time(%pc), %a0
    moveq #0, %d1
    move.b (%a0,%d0.w), %d1
    lea hero_wings(%pc), %a0
    move.w %d1, (%a0)
    move.w %d1, %d0
    bsr.w hud_set_time
    bra.w 9f
3:  bsr.w use_mattock                       | the Mattock
9:  movem.l (%sp)+, %d0-%d2/%a0-%a2
    rts

| The message of an item used up (a0), then nothing is held, and sound $1A.
use_spent:
    bsr.w message_box
    lea inv+INV_ITEM(%pc), %a0
    move.b #0xFF, (%a0)
    lea hud_dirty(%pc), %a0                 | the item box is empty now
    st (%a0)
    moveq #0x1A, %d0
    bra.w sound_play_sfx

| ---------------------------------------------------------------------------------------------------------------------------- the Mattock
| Player_UseMattock (tools: spec in the ROM's PRG15 L3282). One block is looked at: the one in front of the top of the hero (his x + 16 facing right, x - 1 facing left,
| 8 bits; nothing at $F0 and more) at the row of his y. It is the one the Mattock breaks when it is the first of the area's four ids in USE_MATTOCK_BLOCK_TRANSITIONS
| (items.bin; only Trunk has a real entry: $63 becomes $85, $86, $42; in every other area the id is 0, air, and the ROM's quirk is kept: it matches there). Then:
| the message, the Mattock is gone, sound $1A, and four times (4 frames, the block and the one below it are made the next id of the four). The game stands still
| (the sprites stay where they were: the enemies, the people, the spell and the hero are drawn again over the new blocks). Nothing is kept: a screen is made from the package again each time it is entered,
| so what was changed is put back when the screen is drawn next (mattock_restore, from draw_playfield).
use_mattock:
    movem.l %d0-%d7/%a0-%a2, -(%sp)
    move.w hero_x(%pc), %d1
    move.w hero_flip(%pc), %d0
    beq.s 1f
    addi.w #16, %d1
    bra.s 2f
1:  subq.w #1, %d1
2:  andi.w #0xFF, %d1
    cmpi.w #0xF0, %d1
    bcc.w 9f
    lsr.w #4, %d1                           | the column
    move.w hero_y(%pc), %d2
    andi.w #0xFF, %d2
    lsr.w #4, %d2                           | the row
    move.w %d2, %d3
    lsl.w #4, %d3
    add.w %d1, %d3                          | its place in the screen's block ids (rows 13 to 15 of the ROM's buffer are zeros)
    moveq #0, %d5
    cmpi.w #13, %d2
    bcc.s 3f
    move.w cur_screen(%pc), %d0
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a0
    adda.l %d0, %a0
    move.b (%a0,%d3.w), %d5
3:  move.w cur_area(%pc), %d0
    andi.w #7, %d0
    lsl.w #2, %d0
    lea items_data+ITEMS_MATTOCK(%pc), %a1
    cmp.b (%a1,%d0.w), %d5
    bne.w 9f
    move.w %d3, -(%sp)
    lea text_data+TEXT_USED_MATTOCK(%pc), %a0
    bsr.w use_spent                         | "I've used Mattock.", nothing in hand, sound $1A
    move.w (%sp)+, %d3
    move.w cur_screen(%pc), %d0
    mulu.w #208, %d0
    movea.l pkg_ptr+PKG_SCREENS(%pc), %a2
    adda.l %d0, %a2                         | this screen's block ids
    bsr.w mattock_record
    moveq #1, %d7                           | the box has gone and the screens were made again from the playfield (the hero and the people only): the rest comes back
5:  bsr.w mattock_sprites
    bsr.w present_swap
    dbra %d7, 5b
    moveq #0, %d6                           | the step
4:  bsr.w wait_vbl
    bsr.w wait_vbl
    move.w cur_area(%pc), %d0
    andi.w #7, %d0
    lsl.w #2, %d0
    add.w %d6, %d0
    lea items_data+ITEMS_MATTOCK(%pc), %a1
    move.b (%a1,%d0.w), %d4                 | the id of this step
    move.w %d3, %d1
    andi.w #15, %d1
    move.w %d3, %d2
    lsr.w #4, %d2
    cmpi.w #13, %d2
    bcc.s 6f
    move.b %d4, (%a2,%d3.w)                 | the block ...
    bsr.w mattock_draw_block
    cmpi.w #12, %d2
    bcc.s 6f
    move.b %d4, 16(%a2,%d3.w)               | ... and the one under it (the same id, as the ROM's Area_SetBlocks leaves it)
    addq.w #1, %d2
    bsr.w mattock_draw_block
    subq.w #1, %d2
6:  bsr.w mattock_flags_reset
    moveq #1, %d7                           | both screens get the new blocks, the hero is drawn again over them
7:  bsr.w mattock_show
    bsr.w mattock_sprites
    bsr.w present_swap
    dbra %d7, 7b
    addq.w #1, %d6
    cmpi.w #4, %d6
    bne.s 4b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a2
    rts

| The block (d1 = column, d2 = row) of the screen's block ids a2 drawn into the playfield pf_ptr. Keeps every register.
mattock_draw_block:
    movem.l %d0-%d7/%a0-%a1, -(%sp)
    moveq #0, %d0
    move.w %d2, %d3
    lsl.w #4, %d3
    add.w %d1, %d3
    move.b (%a2,%d3.w), %d0                 | the id
    lsl.w #2, %d0
    move.w %d1, %d4
    andi.w #1, %d4
    move.w %d2, %d5
    andi.w #1, %d5
    add.w %d5, %d5
    or.w %d5, %d4                           | the corner: column parity | row parity << 1
    add.w %d4, %d0
    add.w %d0, %d0
    movea.l pkg_ptr+PKG_BLOCK_INDEX(%pc), %a0
    moveq #0, %d6
    move.w (%a0,%d0.w), %d6                 | its image
    cmpi.w #0xFFFF, %d6
    beq.s 9f
    lsl.l #7, %d6
    movea.l pkg_ptr+PKG_BLOCKS(%pc), %a0
    adda.l %d6, %a0
    move.w %d2, %d3
    lsl.w #4, %d3
    mulu.w #STRIDE, %d3
    movea.l pf_ptr(%pc), %a1
    adda.l %d3, %a1
    lea LEFT_BYTES(%a1), %a1
    move.w %d1, %d3
    lsl.w #3, %d3
    adda.w %d3, %a1
    moveq #15, %d7
1:  move.l (%a0)+, (%a1)+
    move.l (%a0)+, (%a1)+
    lea STRIDE-8(%a1), %a1
    dbra %d7, 1b
9:  movem.l (%sp)+, %d0-%d7/%a0-%a1
    rts

| The two blocks at column d1, row d2 are copied from the playfield into the screen a4 (restore_rect does it clipped to the window). Keeps every register.
mattock_show:
    movem.l %d0-%d3/%a0, -(%sp)
    move.w %d1, %d0
    lsl.w #4, %d0
    addi.w #32, %d0                         | x0
    move.w %d0, %d3
    addi.w #16, %d3                         | x1
    move.w %d2, %d1
    lsl.w #4, %d1
    addi.w #HUD_LINES, %d1
    sub.w camera(%pc), %d1                  | y0
    move.w %d1, %d2
    addi.w #32, %d2                         | y1 (two blocks)
    lea -8(%sp), %sp
    move.w %d0, (%sp)
    move.w %d3, 2(%sp)
    move.w %d1, 4(%sp)
    move.w %d2, 6(%sp)
    movea.l %sp, %a0
    bsr.w restore_rect
    lea 8(%sp), %sp
    movem.l (%sp)+, %d0-%d3/%a0
    rts

mattock_flags_reset:                        | the flags of the screens are made again from the block ids when they are asked for
    movem.l %d0/%a1, -(%sp)
    lea flag_screens(%pc), %a1
    moveq #FLAG_SLOTS-1, %d0
1:  move.w #-1, (%a1)+
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a1
    rts

| A change to remember: a2 = the screen's block ids, d3 = the place. The four last ones are kept (area, palette set, the ids at the place and the one under it).
mattock_record:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    lea mt_recs(%pc), %a0
    move.w mt_count(%pc), %d0
    cmpi.w #4, %d0
    bcs.s 2f
    lea 12(%a0), %a1                        | full: the oldest is forgotten
    moveq #8, %d1
1:  move.l (%a1)+, (%a0)+
    dbra %d1, 1b
    lea mt_recs(%pc), %a0
    moveq #3, %d0
2:  move.w %d0, %d2
    addq.w #1, %d2                          | the new count
    mulu.w #12, %d0
    adda.w %d0, %a0
    move.l %a2, (%a0)
    move.w cur_area(%pc), 4(%a0)
    move.w cur_pal(%pc), 6(%a0)
    move.w %d3, 8(%a0)
    clr.w 10(%a0)
    cmpi.w #208, %d3
    bcc.s 3f
    move.b (%a2,%d3.w), 10(%a0)
    cmpi.w #192, %d3
    bcc.s 3f
    move.b 16(%a2,%d3.w), 11(%a0)
3:  lea mt_count(%pc), %a1
    move.w %d2, (%a1)
    movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

| draw_playfield is about to draw the screen whose block ids are at a5: what the Mattock changed in it is put back (newest first). Records of another package are dropped.
| Keeps every register.
mattock_restore:
    movem.l %d0-%d6/%a0-%a1, -(%sp)
    move.w mt_count(%pc), %d5
    beq.w 9f
    move.w cur_area(%pc), %d1
    move.w cur_pal(%pc), %d2
    move.l %a5, %d3
    moveq #0, %d4                           | something was put back
    lea mt_recs(%pc), %a0
    move.w %d5, %d0
    mulu.w #12, %d0
    adda.w %d0, %a0                         | behind the last
    move.w %d5, %d0
    subq.w #1, %d0
1:  lea -12(%a0), %a0
    move.l (%a0), %d6
    beq.s 5f                                | (done already)
    cmp.w 4(%a0), %d1
    bne.s 4f                                | another package: stale
    cmp.w 6(%a0), %d2
    bne.s 4f
    cmp.l %d6, %d3
    bne.s 5f                                | another screen: it stays as it is
    movea.l %d6, %a1
    move.w 8(%a0), %d6
    cmpi.w #208, %d6
    bcc.s 3f
    move.b 10(%a0), (%a1,%d6.w)
    cmpi.w #192, %d6
    bcc.s 3f
    move.b 11(%a0), 16(%a1,%d6.w)
3:  moveq #1, %d4
4:  clr.l (%a0)
5:  dbra %d0, 1b
    lea mt_recs(%pc), %a0                   | the count shrinks past the done ones at the end
    move.w %d5, %d0
    mulu.w #12, %d0
    adda.w %d0, %a0
6:  tst.w %d5
    beq.s 7f
    tst.l -12(%a0)
    bne.s 7f
    lea -12(%a0), %a0
    subq.w #1, %d5
    bra.s 6b
7:  lea mt_count(%pc), %a1
    move.w %d5, (%a1)
    tst.w %d4
    beq.s 9f
    bsr.w mattock_flags_reset
9:  movem.l (%sp)+, %d0-%d6/%a0-%a1
    rts

| The HUD is drawn again at the next frame (hud_dirty is out of reach of the code at the end of the program: menu.s asks for it here). Keeps every register.
hud_mark:
    movem.l %a0, -(%sp)
    lea hud_dirty(%pc), %a0
    st (%a0)
    movem.l (%sp)+, %a0
    rts

| One frame in which the game stands still: the VBL, and the HUD if it changed.
frozen_wait:
    movem.l %d0/%a0, -(%sp)
    bsr.w wait_vbl
    lea hud_dirty(%pc), %a0
    tst.b (%a0)
    beq.s 1f
    clr.b (%a0)
    bsr.w hud_update_all
1:  movem.l (%sp)+, %d0/%a0
    rts

| Player_FillHPAndMP's loops: d1 = the step (Red Potion 2, Elixir 4) added to the power every four frames, with sound $13, until it is 80 (at least once);
| fill_magic does the same for the magic.
fill_power:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    lea hud_state(%pc), %a1
    bra.s fill_loop
fill_magic:
    movem.l %d0-%d2/%a0-%a1, -(%sp)
    lea hud_state+1(%pc), %a1
fill_loop:
1:  moveq #0x13, %d0
    bsr.w sound_play_sfx
    move.b (%a1), %d0
    add.b %d1, %d0
    cmpi.b #80, %d0
    bcs.s 2f
    moveq #80, %d0
2:  move.b %d0, (%a1)
    lea hud_dirty(%pc), %a0
    st (%a0)
    moveq #3, %d2
3:  bsr.s frozen_wait
    dbra %d2, 3b
    cmpi.b #80, (%a1)
    bcs.s 1b
    movem.l (%sp)+, %d0-%d2/%a0-%a1
    rts

| Game_ClearTimedItems (Game_Start, Player_Spawn): wing boots, hour glass, glove and ointment are not in force; the Mattock quest bit goes (Player_Spawn).
timers_clear:
    movem.l %a0, -(%sp)
    lea hero_wings(%pc), %a0
    move.w #-1, (%a0)
    lea hourglass(%pc), %a0
    move.w #-1, (%a0)
    lea inv(%pc), %a0
    move.b #0xFF, INV_GLOVE(%a0)
    move.b #0xFF, INV_OINTMENT(%a0)
    andi.b #0xEF, INV_QUESTS(%a0)
    movem.l (%sp)+, %a0
    rts

| Player_UseElixir (the damage left no power): the Elixir is used up, its message, power and magic filled to 80 a step of 4 at a time.
use_elixir:
    movem.l %d1/%a0, -(%sp)
    lea inv+INV_SPECIAL(%pc), %a0
    andi.b #0xF7, (%a0)
    lea text_data+TEXT_USED_ELIXIR(%pc), %a0
    bsr.w message_box
    moveq #4, %d1
    bsr.w fill_power
    bsr.w fill_magic
    movem.l (%sp)+, %d1/%a0
    rts

| Game_OpenDoorWithAKey and the rings' tests (Game_RunDoorRequirementHandler): d2 = the door's requirement (1 Ace, 2 King, 3 Queen, 4 Jack, 5 Joker keys, 6 Ring of
| Elf, 7 Ring of Dworf, 8 Demon's Ring). d0.w = 1 when the door opens: the key he holds is the one (it is used up: its message), or he has the ring (it stays);
| else the mark by the key hole (or the ring's question) is said and the door stays shut.
door_unlock:
    movem.l %d1-%d2/%a0, -(%sp)
    move.w %d2, %d1
    cmpi.w #6, %d2
    bcc.s 5f
    addq.w #3, %d2                          | the key's number in the ROM's item list: A 4 ... Joker 8
    cmp.b inv+INV_ITEM(%pc), %d2
    bne.s 6f
    lea text_data+TEXT_USED_KEY(%pc), %a0
    bsr.w message_box
    lea inv+INV_ITEM(%pc), %a0
    move.b #0xFF, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
    bra.s 8f
5:  lea ring_masks-6(%pc), %a0
    move.b (%a0,%d1.w), %d0
    and.b inv+INV_SPECIAL(%pc), %d0
    bne.s 8f
    lea text_data+TEXT_RING(%pc), %a0
    bsr.w message_box
    bra.s 7f
6:  add.w %d1, %d1
    lea key_hints-2(%pc), %a0
    move.w (%a0,%d1.w), %d1
    lea text_data(%pc), %a0
    adda.w %d1, %a0
    bsr.w message_box
7:  moveq #0, %d0
    bra.s 9f
8:  moveq #6, %d0
    bsr.w sound_play_sfx
    moveq #1, %d0
9:  movem.l (%sp)+, %d1-%d2/%a0
    rts

    .section .rodata
ring_masks:
    .byte 0x80, 0x20, 0x10
key_hints:
    .word TEXT_KEY_A, TEXT_KEY_K, TEXT_KEY_Q, TEXT_KEY_J, TEXT_KEY_JO
    .even

    .section .data
item_ticks:
    .word 0
mt_count:                                   | the Mattock's changes still in the package: how many, then 4 records of 12 bytes (the screen's ids, area, palette set, place, two old ids)
    .word 0
mt_recs:
    .space 48
inv:                                        | the inventory (a new game: nothing, no glove and no ointment in force, the equipment the build gave him)
    .space INV_GLOVE
    .byte 0xFF, 0xFF, 0, HERO_ARMOUR, HERO_SHIELD & 0xFF, ITEM & 0xFF, 0
    .even
    .text
