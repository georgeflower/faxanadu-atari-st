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
    .equ INV_BYTES, 36

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
    tst.w K_CAT(%a1)
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
    addq.b #1, (%a0)
    move.b (%a0), %d0
    andi.b #0x3F, %d0
    bne.s 9f
    lea inv(%pc), %a2
    lea INV_GLOVE(%a2), %a1
    lea text_data+TEXT_GLOVE_GONE(%pc), %a0
    bsr.s item_count
    lea INV_OINTMENT(%a2), %a1
    lea text_data+TEXT_OINTMENT_GONE(%pc), %a0
    bsr.s item_count
9:  movem.l (%sp)+, %d0-%d1/%a0-%a2
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
    lea hud_state(%pc), %a0
    addi.w #100, 2(%a0)
    bcc.s 1f
    move.w #0xFFFF, 2(%a0)
1:  lea hud_dirty(%pc), %a0
    st (%a0)
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

    .section .data
item_ticks:
    .byte 0
inv:                                        | the inventory (a new game: nothing, no glove and no ointment in force, the equipment the build gave him)
    .space INV_GLOVE
    .byte 0xFF, 0xFF, 0, HERO_ARMOUR, HERO_SHIELD & 0xFF
    .even
    .text
