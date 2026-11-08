| The hero's pictures follow what he wears. The data for every armour, weapon and shield is in the program (hero_equip.bin, tools/st_convert.py
| hero_equip_assets): the tiles as the NES has them, and the places of the pictures in every pose. The images the screen is drawn with (40 bytes a
| tile, in the colours of the package in use) are made here when the worn equipment or the colours change: hero_sync checks it before the hero is
| drawn, and keeps every register.
|
| hero_ram: the 64 tiles of the NES pattern table the hero uses (16 bytes), then the images, 256 of them: tile * 4 + palette * 2 + mirrored.
| The poses: hero_poses holds the pose tables of the body, the piece of the arm in an attack, the weapon and the shield (0: none).

    .text
    .equ HD_ARMOUR_TILES, 0                 | the directory of hero_equip: long offsets from its start (the order is HERO_DIRECTORY in st_convert.py)
    .equ HD_WEAPON_TILES, 8
    .equ HD_SHIELD_TILES, 12
    .equ HD_BODY, 15
    .equ HD_ARM, 23
    .equ HD_WEAPON, 31
    .equ HD_SHIELD, 39
    .equ HD_RANGE, 42                       | 8 for (weapon, shield), the ninth for no weapon
    .equ HD_REVERSE, 51

hero_sync:
    movem.l %d0-%d6/%a0-%a3, -(%sp)
    lea inv(%pc), %a0
    moveq #0, %d0
    move.b INV_ARMOUR(%a0), %d0
    lsl.w #8, %d0
    move.b INV_SHIELD(%a0), %d0
    swap %d0                                | armour and shield in the top word
    move.w hero_weapon(%pc), %d1
    cmpi.w #4, %d1
    bcs.s 1f
    move.w #0xFF, %d1                       | none
1:  move.l %d0, %d2
    move.w %d1, %d3
    lsl.w #8, %d3
    move.w %d3, %d2                         | the key of the images: armour, shield, weapon
    move.w cur_area(%pc), %d3
    cmpi.w #BUILDING_AREA, %d3
    bne.s 2f
    move.w #0xFF, %d1                       | in a building the weapon is put away
2:  lsl.w #8, %d1
    move.w %d1, %d0                         | the key of the poses: armour, shield, the weapon to be seen

    movea.l pkg_ptr+PKG_HERO_COLOURS(%pc), %a1
    lea hero_img_key(%pc), %a0
    cmp.l (%a0), %d2
    bne.s 3f
    move.l (%a1), %d3
    cmp.l 4(%a0), %d3
    bne.s 3f
    move.l 4(%a1), %d3
    cmp.l 8(%a0), %d3
    beq.s 4f
3:  move.l %d2, (%a0)
    move.l (%a1), 4(%a0)
    move.l 4(%a1), 8(%a0)
    bsr.w hero_build_images
4:  lea hero_pose_key(%pc), %a0
    cmp.l (%a0), %d0
    beq.w 9f
    move.l %d0, (%a0)
    movea.l hero_blob(%pc), %a2
    move.l %d0, %d1
    swap %d1
    moveq #0, %d2
    move.b %d1, %d2                         | the shield
    lsr.w #8, %d1                           | the armour
    moveq #0, %d3
    cmpi.b #3, %d2
    bcc.s 5f
    moveq #1, %d3                           | with a shield
5:  moveq #0, %d4
    move.w %d0, %d4
    lsr.w #8, %d4                           | the weapon (255: none)
    add.w %d1, %d1
    add.w %d3, %d1                          | the body: armour * 2 + 1 with a shield
    lsl.w #2, %d1
    lea hero_poses(%pc), %a0
    lea HD_BODY*4(%a2), %a3
    move.l (%a3,%d1.w), %d5
    add.l %a2, %d5
    move.l %d5, (%a0)+
    lea HD_ARM*4(%a2), %a3
    move.l (%a3,%d1.w), %d5
    add.l %a2, %d5
    move.l %d5, (%a0)+
    lea HD_RANGE*4(%a2), %a3
    moveq #0, %d5
    moveq #0, %d6                           | no weapon: no pictures, the last place and reach (all zero)
    cmpi.b #4, %d4
    bcc.s 6f
    add.w %d4, %d4
    add.w %d3, %d4                          | weapon * 2 + 1 with a shield
    lea HD_WEAPON*4(%a2), %a1
    lsl.w #2, %d4
    move.l (%a1,%d4.w), %d5
    add.l %a2, %d5
    move.l (%a3,%d4.w), %d6
    add.l %a2, %d6
    bra.s 7f
6:  move.l 8*4(%a3), %d6
    add.l %a2, %d6
7:  move.l %d5, (%a0)+                      | the weapon
    moveq #0, %d5
    cmpi.b #3, %d2
    bcc.s 8f
    lea HD_SHIELD*4(%a2), %a1
    add.w %d2, %d2
    add.w %d2, %d2
    move.l (%a1,%d2.w), %d5
    add.l %a2, %d5
8:  move.l %d5, (%a0)+                      | the shield
    move.l %d6, (%a0)                       | hero_wtab: where the weapon is and how far it reaches
9:  movem.l (%sp)+, %d0-%d6/%a0-%a3
    rts

| Makes the tiles of the equipment in hero_img_key (d2: armour, shield, weapon in the bytes of the top word and the next byte) and the images from them
| in the colours hero_img_key+4 holds. Keeps every register. About 15 frames: it runs when he changes what he wears.
hero_build_images:
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    movea.l hero_ram(%pc), %a5
    movea.l hero_blob(%pc), %a2
    movea.l %a5, %a0
    move.w #(HERO_RAM_BYTES/4)-1, %d0
1:  clr.l (%a0)+
    dbra %d0, 1b
    move.l %d2, %d0
    swap %d0
    moveq #0, %d3
    move.b %d0, %d3                         | the shield
    lsr.w #8, %d0                           | the armour
    moveq #0, %d4
    cmpi.b #3, %d3
    bcc.s 2f
    moveq #1, %d4
2:  add.w %d0, %d0
    add.w %d4, %d0
    lsl.w #2, %d0
    move.l (%a2,%d0.w), %d0                 | the armour's tiles
    lea (%a2,%d0.l), %a0
    bsr.w hero_put_tiles
    move.w %d2, %d1
    lsr.w #8, %d1                           | the weapon
    cmpi.b #4, %d1
    bcc.s 3f
    lsl.w #2, %d1
    move.l HD_WEAPON_TILES*4(%a2,%d1.w), %d0
    lea (%a2,%d0.l), %a0
    bsr.w hero_put_tiles
3:  cmpi.b #3, %d3
    bcc.s 4f
    lsl.w #2, %d3
    move.l HD_SHIELD_TILES*4(%a2,%d3.w), %d0
    lea (%a2,%d0.l), %a0
    bsr.w hero_put_tiles
4:  lea HD_REVERSE*4(%a2), %a0
    move.l (%a0), %d0
    lea (%a2,%d0.l), %a6                    | the table that reverses the bits of a byte
    lea HERO_IMAGES_AT(%a5), %a3
    movea.l %a5, %a4
    moveq #63, %d6
5:  move.l (%a4), %d0                       | a tile that is empty has an empty image (the memory is cleared)
    or.l 4(%a4), %d0
    or.l 8(%a4), %d0
    or.l 12(%a4), %d0
    beq.s 6f
    movea.l %a3, %a1
    lea hero_img_key+4(%pc), %a2
    movea.l %a4, %a0
    bsr.s hero_convert                      | the first palette; a1 is at the next image
    movea.l %a3, %a0
    bsr.s hero_reverse                      | ... mirrored
    addq.l #4, %a2
    movea.l %a4, %a0
    bsr.s hero_convert                      | the second palette
    lea 2*SPRITE_IMAGE_BYTES(%a3), %a0
    bsr.s hero_reverse
6:  lea 4*SPRITE_IMAGE_BYTES(%a3), %a3
    lea 16(%a4), %a4
    dbra %d6, 5b
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    rts

| a0 = a tile record (the first tile, the count, the tiles); a5 = the tiles of hero_ram. Clobbers d5, d6, a0, a1.
hero_put_tiles:
    move.w (%a0)+, %d5
    move.w (%a0)+, %d6
    lsl.w #4, %d5
    lea (%a5,%d5.w), %a1
    lsl.w #2, %d6
    subq.w #1, %d6
7:  move.l (%a0)+, (%a1)+
    dbra %d6, 7b
    rts

| a0 = an image, a1 = where its mirror goes (a6: the table that reverses the bits of a byte); a1 moves 40 bytes on.
hero_reverse:
    movem.l %d0-%d1, -(%sp)
    moveq #SPRITE_IMAGE_BYTES-1, %d1
    moveq #0, %d0
1:  move.b (%a0)+, %d0
    move.b (%a6,%d0.w), (%a1)+
    dbra %d1, 1b
    movem.l (%sp)+, %d0-%d1
    rts

| a0 = a NES tile (two bit planes, 8 lines), a2 = the ST colours of the palette (four bytes, colour 0 is see-through), a1 = where the image goes:
| a line of the mask (a bit for a pixel that is drawn) and the four planes, 8 lines. a1 moves 40 bytes on.
hero_convert:
    movem.l %d0-%d7/%a0/%a5, -(%sp)
    lea 8(%a0), %a5
1:  move.b (%a0)+, %d0
    move.b 7(%a0), %d1
    moveq #0, %d2
    moveq #0, %d3
    moveq #0, %d4
    moveq #0, %d5
    moveq #0, %d6
    .rept 8
    moveq #0, %d7
    add.b %d1, %d1
    addx.b %d7, %d7
    add.b %d0, %d0
    addx.b %d7, %d7                         | the pixel's colour, 0-3
    add.b %d6, %d6
    tst.b %d7
    beq.s 2f
    addq.b #1, %d6
2:  move.b (%a2,%d7.w), %d7
    lsr.b #1, %d7
    addx.b %d2, %d2
    lsr.b #1, %d7
    addx.b %d3, %d3
    lsr.b #1, %d7
    addx.b %d4, %d4
    lsr.b #1, %d7
    addx.b %d5, %d5
    .endr
    move.b %d6, (%a1)+
    move.b %d2, (%a1)+
    move.b %d3, (%a1)+
    move.b %d4, (%a1)+
    move.b %d5, (%a1)+
    cmpa.l %a5, %a0
    bne.w 1b
    movem.l (%sp)+, %d0-%d7/%a0/%a5
    rts

| Draws the hero in the pose his state says, into screen a4, and notes the rectangle in this screen's slot.
| (The code is in viewer.s: draw_hero; these are its parts.)

| a5 = a pose table (0: none), d6 = the pose's offset in it; d0-d3 = the box so far (x0, x1, y0, y1, relative to the hero). Clobbers d4, a5.
hero_box_part:
    move.l %a5, %d4
    beq.s 9f
    move.w (%a5,%d6.w), %d4
    adda.w %d4, %a5
1:  move.w (%a5)+, %d4
    bmi.s 9f
    cmp.w %d0, %d4
    bge.s 2f
    move.w %d4, %d0
2:  cmp.w %d1, %d4
    ble.s 3f
    move.w %d4, %d1
3:  move.w (%a5)+, %d4
    cmp.w %d2, %d4
    bge.s 4f
    move.w %d4, %d2
4:  cmp.w %d3, %d4
    ble.s 5f
    move.w %d4, %d3
5:  addq.l #2, %a5
    bra.s 1b
9:  rts

| a5 = a pose table (0: none), a3 = the images, a4 = the screen; the pose is hero_pose_off. Clobbers d0-d7, a0, a1, a5.
hero_draw_part:
    move.l %a5, %d0
    beq.s 9f
    move.w hero_pose_off(%pc), %d0
    move.w (%a5,%d0.w), %d0
    adda.w %d0, %a5
1:  move.w (%a5)+, %d0
    bmi.s 9f
    add.w hero_x(%pc), %d0
    move.w hero_y(%pc), %d1                 | blit_tile clobbers d0-d7: the position comes from memory each time
    sub.w camera(%pc), %d1
    add.w (%a5)+, %d1
    move.w (%a5)+, %d2
    mulu.w #SPRITE_IMAGE_BYTES, %d2
    lea (%a3,%d2.l), %a1
    bsr.w dissolve_image
    bsr.w blit_tile
    bra.s 1b
9:  rts

    .section .data
hero_ram:
    .long 0                                 | HERO_RAM_BYTES, behind the playfields (viewer.s: start)
hero_blob:
    .long 0                                 | hero_equip, found from the first byte of the program (start)
hero_img_key:
    .long -1, 0, 0                          | what the images are made for: armour, shield, weapon; the 8 colour bytes
hero_pose_key:
    .long -1                                | what hero_poses and hero_wtab are made for: armour, shield, the weapon that is seen
hero_poses:
    .long 0, 0, 0, 0                        | the pose tables of the body, the arm piece, the weapon and the shield
hero_wtab:
    .long 0                                 | the weapon's places and reaches for the poses (8 bytes each: dx, dy, reach x, reach y)
hero_pose_off:
    .word 0                                 | the pose of the hero being drawn, as an offset in a pose table

    .section .herodata
hero_equip:
    .incbin "hero_equip.bin"
    .even
    .text
