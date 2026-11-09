| The game's flow (F3). Included by viewer.s when FLOW is defined (NEWGAME=1, the disk build, brings it).
|
| new_game        START on the title: the ROM's new game (Player_SetStartGameState, Game_Start, Game_LoadFirstLevel): Eolis screen 0 at x 16, y 144
| temple_enter    a death or a mantra: Game_SpawnInTemple, he stands in the temple of the last Guru's town (hero_spawn) and leaves by its door
| flow_tick       once a frame, after the keys: the ending's walk, the screen's special event (a boss room, the final boss)
| end_start       the final boss is gone: 120 frozen frames, the fade, 120 black frames, the King's room, the walk to the King, his message, the outro, the title
| flow_fade_out   Screen_FadeToBlack: four steps of the palette, about 20 frames
|
| Like town.s and splash68.s the code and its variables are in .text.early (the main code has no room left): what it calls in the main code it reaches
| with bsr.w while that is near enough (check_reach.py says when not) and with FAR_CALL otherwise.

    .macro FAR_CALL sym
    pea 1f(%pc)
    FAR_JMP \sym
1:
    .endm

    .section .text.early,"ax"

| ------------------------------------------------------------------------------------------------------------------ a new game
| Player_SetStartGameState: the first spawn point, rank 0, leather armour, no weapon, shield, spell or item, nothing in the lists, no gold, no experience;
| Game_Start: the timed items cleared; Game_LoadFirstLevel: Eolis screen 0, power 16, magic 0, Eolis's song, the start position $91 (x 16, y 144), facing right.
new_game:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea hero_dead(%pc), %a0
    clr.w (%a0)
    lea hero_title(%pc), %a0
    clr.w (%a0)
    lea hero_next(%pc), %a0
    clr.w (%a0)
    lea hero_spawn(%pc), %a0
    clr.w (%a0)
    lea hero_invinc(%pc), %a0
    clr.w (%a0)
    lea hero_weapon(%pc), %a0
    move.w #0xFF, (%a0)                     | no weapon
    lea hero_magic(%pc), %a0
    move.w #-1, (%a0)                       | no spell
    lea inv(%pc), %a0                       | no lists, no special items, no quests
    moveq #(INV_BYTES/2)-1, %d0
1:  clr.w (%a0)+
    dbra %d0, 1b
    lea inv(%pc), %a0
    move.b #0xFF, INV_GLOVE(%a0)
    move.b #0xFF, INV_OINTMENT(%a0)
    move.b #0xFF, INV_SHIELD(%a0)
    move.b #0xFF, INV_ITEM(%a0)             | (the armour, 0, is the leather one)
    lea hero_hpl(%pc), %a0
    clr.b (%a0)
    lea hud_state(%pc), %a0                 | power 16, magic 0, experience 0, gold 0, no time
    move.b #16, (%a0)+
    clr.b (%a0)+
    clr.w (%a0)+
    clr.l (%a0)+
    clr.w (%a0)
    .ifdef NPCS
    lea npc_intro_done(%pc), %a0
    clr.w (%a0)                             | the first message of the game comes again
    .endif
    lea flow_event(%pc), %a0
    move.w #-1, (%a0)
    lea flow_exit(%pc), %a0
    clr.w (%a0)
    lea end_state(%pc), %a0
    clr.w (%a0)
    FAR_CALL timers_clear                   | Game_ClearTimedItems
    lea hero_flip(%pc), %a0
    move.w #1, (%a0)                        | facing right (Player_Flags $40)
    movea.l #PALETTE, %a0                   | (nothing to fade: the intro's fade and the title have left the screen black)
    moveq #15, %d0
2:  clr.w (%a0)+
    dbra %d0, 2b
    .if EOLIS_START_SCREEN >= 0
    move.w #EOLIS_START_SCREEN, %d0
    .else
    move.w #START_SCREEN, %d0
    .endif
    move.w #0x91, %d1
    moveq #0, %d2                           | area 0, Eolis's palette set 0
    moveq #0, %d3
    bsr.w enter_world
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

| ------------------------------------------------------------------------------------------------------------------ the temple
| Game_SpawnInTemple, then Game_SetupEnterBuilding: the temple (building 1 of area 4: palette set 18, start $9E = x 224, y 144, song 14, facing left) of the
| spawn point hero_spawn, with the people of that town's temple (the placement is by the screen the ROM puts in Area_DestScreen). What he leaves it for is the
| temple table: the outside area, screen and place, in the area's palette set. The song after leaving is AREA_TO_MUSIC_TABLE[area] (flow_exit), not the
| town's own: that is what the ROM does (Area_Music_Outside), checked in jsnes. The outside screens are the ROM's numbers, so the area must be built whole (ALL, WORLD).
temple_enter:
    movem.l %d0-%d4/%a0-%a2, -(%sp)
    move.w hero_spawn(%pc), %d4
    andi.w #7, %d4
    moveq #0, %d2
    lea tt_dest(%pc), %a1
    move.b (%a1,%d4.w), %d2                 | the id the temple's people are placed by
    move.w #0x9E, %d1
    moveq #18, %d3
    moveq #0, %d0
    bsr.w enter_building                    | (it remembers where he is: the way out is put right below)
    lea saved_area(%pc), %a0
    moveq #0, %d0
    lea tt_area(%pc), %a1
    move.b (%a1,%d4.w), %d0
    move.w %d0, (%a0)+                      | the area
    lea tt_palette(%pc), %a1
    moveq #0, %d1
    move.b (%a1,%d0.w), %d1
    move.w %d1, (%a0)+                      | its palette set
    lea tt_screen(%pc), %a1
    moveq #0, %d1
    move.b (%a1,%d4.w), %d1
    move.w %d1, (%a0)+                      | the screen
    lea tt_x(%pc), %a1
    moveq #0, %d1
    move.b (%a1,%d4.w), %d1
    lsr.w #4, %d1
    lea tt_y(%pc), %a1
    moveq #0, %d2
    move.b (%a1,%d4.w), %d2
    andi.w #0xF0, %d2
    or.w %d2, %d1
    move.w %d1, (%a0)                       | where he stands there (Y/16 << 4 | X/16)
    lea tt_music(%pc), %a1
    moveq #0, %d1
    move.b (%a1,%d0.w), %d1
    lea flow_exit(%pc), %a0
    move.w %d1, (%a0)
    movem.l (%sp)+, %d0-%d4/%a0-%a2
    rts

| Called when he has walked out of a building and the outside is drawn (exit_building): after a respawn the song is the area's.
flow_exit_music:
    movem.l %d0/%a0, -(%sp)
    move.w flow_exit(%pc), %d0
    beq.s 1f
    lea flow_exit(%pc), %a0
    clr.w (%a0)
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
1:  movem.l (%sp)+, %d0/%a0
    rts

tt_area:                                    | CURRENT_REGION_FOR_TEMPLE_SPAWN (the ROM calls it a region, it is the area)
    .byte 0, 3, 3, 2, 3, 3, 3, 3
tt_screen:                                  | START_SCREEN_FOR_TEMPLE_SPAWN
    .byte 2, 1, 3, 6, 6, 8, 11, 12
tt_x:                                       | START_PLAYERPOSX_FULL_FOR_TEMPLE_SPAWN
    .byte 80, 80, 48, 144, 48, 144, 96, 48
tt_y:                                       | MAYBE_START_PLAYERPOSY_FOR_TEMPLE_SPAWN
    .byte 144, 144, 144, 128, 144, 144, 144, 144
tt_dest:                                    | DEST_SCREEN_FOR_TEMPLE_SPAWN
    .byte 2, 11, 16, 30, 35, 43, 51, 60
tt_palette:                                 | AREA_PALETTE_INDEXES
    .byte 0, 6, 10, 27, 27, 8, 12, 15
tt_music:                                   | AREA_TO_MUSIC_TABLE
    .byte 7, 3, 5, 9, 9, 4, 2, 16
    .even

| ------------------------------------------------------------------------------------------------------------------ every frame
| Run in the main loop after the keys are read.
flow_tick:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    move.w end_state(%pc), %d0
    beq.s 4f
    lea input_state(%pc), %a0
    cmpi.w #END_FINISH, %d0
    beq.w 80f
    cmpi.w #END_WALK, %d0
    beq.s 2f
    clr.b IN_PAD(%a0)                       | the 120 frozen frames: nothing is pressed
    clr.b IN_PAD_NEW(%a0)
    lea end_count(%pc), %a1
    subq.w #1, (%a1)
    bne.w 9f
    bsr.w end_fade_room
    bra.w 9f
2:  lea end_count(%pc), %a1                 | the walk has a time limit: a hero who does not get there (stuck on the step) is taken to the King's message
    subq.w #1, (%a1)
    bne.s 21f
    bsr.w end_walk_timeout
    bra.w 9f
21: move.w hero_x(%pc), %d1                 | EndGame_MovePlayerTowardKing: pressing Left, Left and A between x $50 and $60, Up in front of the King
    moveq #NES_UP, %d2
    cmpi.w #0x44, %d1
    bcs.s 3f
    moveq #NES_LEFT, %d2
    cmpi.w #0x61, %d1
    bcc.s 3f
    cmpi.w #0x50, %d1
    bcs.s 3f
    move.w #NES_LEFT+NES_A, %d2
3:  move.b %d2, IN_PAD(%a0)                 | (both the held and the newly pressed buttons: the ROM sets both masks)
    move.b %d2, IN_PAD_NEW(%a0)
    bra.w 9f
4:  move.w hero_dead(%pc), %d0
    bne.w 9f
    lea flow_last(%pc), %a0                 | a new screen: its special event id
    move.w cur_area(%pc), %d0
    cmp.w (%a0), %d0
    bne.s 5f
    move.w cur_pal(%pc), %d0
    cmp.w 2(%a0), %d0
    bne.s 5f
    move.w cur_screen(%pc), %d0
    cmp.w 4(%a0), %d0
    beq.s 6f
5:  move.w cur_area(%pc), (%a0)
    move.w cur_pal(%pc), 2(%a0)
    move.w cur_screen(%pc), 4(%a0)
    move.w flow_event(%pc), %d1
    andi.w #0x7F, %d1
    cmpi.w #1, %d1
    bne.s 51f
    bsr.w flow_default_music                | Area_ScrollTo: out of a boss room the area's song comes back
51: movea.l pkg_ptr+PKG_SCREEN_EVENTS(%pc), %a1
    move.w cur_screen(%pc), %d1
    moveq #0, %d2
    move.b (%a1,%d1.w), %d2
    lea flow_event(%pc), %a1
    move.w %d2, (%a1)
6:  move.w flow_event(%pc), %d0
    cmpi.w #0xFF, %d0
    beq.w 9f
    move.w %d0, %d1
    andi.w #0x7F, %d1
    cmpi.w #1, %d1
    beq.s 7f
    cmpi.w #2, %d1
    bne.w 9f
    bsr.w flow_any_enemy                    | ScreenEvents_HandleFinalBossKilled: with no sprite left on the screen the ending begins
    tst.w %d0
    bne.w 9f
    bsr.w end_start
    bra.w 9f
7:  btst #7, %d0                            | ScreenEvents_HandleBoss
    bne.s 71f
    ori.w #0x80, %d0                        | the first tick of the screen: the Ointment and the Hour Glass are cut short (LimitItemDurations), the boss song
    lea flow_event(%pc), %a1
    move.w %d0, (%a1)
    lea inv+INV_OINTMENT(%pc), %a1
    tst.b (%a1)
    bmi.s 70f
    clr.b (%a1)
70: lea hourglass(%pc), %a1
    tst.w (%a1)
    bmi.s 72f
    clr.w (%a1)
72: moveq #10, %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a1
    move.w %d0, (%a1)
71: bsr.w flow_has_boss                     | the boss is gone: the area's song and no more events here
    tst.w %d0
    bne.s 9f
    bsr.w flow_default_music
    lea flow_event(%pc), %a1
    move.w #0xFF, (%a1)
    bra.s 9f
80: lea end_state(%pc), %a1                 | IScriptAction_FinishGame: RunOutro, then Game_Init (the title)
    clr.w (%a1)
    .ifdef SPLASH
    bsr.w ending_play
    bsr.w splash_start
    lea input_state(%pc), %a1
    tst.b IN_QUIT(%a1)
    beq.s 9f
    FAR_JMP viewer_leave                    | Esc in the outro or on the title after it: the program ends (the Esc menu is for the running game)
    .endif
9:  movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

| Areas_DefaultMusic: the song of the package (also what plays when the Hour Glass runs out).
flow_default_music:
    movem.l %d0/%a0, -(%sp)
    move.w pkg_ptr+PKG_MUSIC(%pc), %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    movem.l (%sp)+, %d0/%a0
    rts

| Sprites_HasBoss: d0 = 1 when a slot holds a boss (the ROM's category 7; its death effect has another one), else 0.
flow_has_boss:
    movem.l %d1/%a1-%a2, -(%sp)
    lea enemies(%pc), %a1
    moveq #8-1, %d1
1:  cmpi.b #0xFF, E_ENT(%a1)
    beq.s 2f
    movea.l E_KIND(%a1), %a2
    cmpi.b #7, K_CAT+1(%a2)
    beq.s 3f
2:  lea E_BYTES(%a1), %a1
    dbra %d1, 1b
    moveq #0, %d0
    bra.s 4f
3:  moveq #1, %d0
4:  movem.l (%sp)+, %d1/%a1-%a2
    rts

| Sprites_HasCurrentSprites: d0 = 1 when a slot is in use (the boss, its bolts, what it dropped), else 0.
flow_any_enemy:
    movem.l %d1/%a1, -(%sp)
    lea enemies(%pc), %a1
    moveq #8-1, %d1
    moveq #1, %d0
1:  cmpi.b #0xFF, E_ENT(%a1)
    bne.s 2f
    lea E_BYTES(%a1), %a1
    dbra %d1, 1b
    moveq #0, %d0
2:  movem.l (%sp)+, %d1/%a1
    rts

| ------------------------------------------------------------------------------------------------------------------ the ending
| ScreenEvents_HandleFinalBossKilled: Eolis's song, the hit sound, EndGame_Begin clears the sprites; the game then stands still for 120 frames (the main loop goes on
| with nothing pressed and nothing on the screen but him: end_state END_FREEZE counts them in flow_tick).
end_start:
    movem.l %d0/%a0, -(%sp)
    moveq #7, %d0
    bsr.w sound_play_music
    lea cur_music(%pc), %a0
    move.w %d0, (%a0)
    moveq #4, %d0
    bsr.w sound_play_sfx
    bsr.w spell_clear
    bsr.w enemies_clear
    lea end_count(%pc), %a0
    move.w #120, (%a0)
    lea end_state(%pc), %a0
    move.w #END_FREEZE, (%a0)
    lea end_times(%pc), %a0
    move.l frame_count(%pc), (%a0)          | (the tests read when the ending began and when the King's room came)
    movem.l (%sp)+, %d0/%a0
    rts

| The rest of EndGame_Begin: Screen_FadeToBlack (four steps at the passes 126, 131, 136, 141), 120 black frames, then EndGame_MoveToKingsRoom: the King's room (building 0
| of area 4: palette set 17, song 13), the start position $9D (x 208, y 144), facing left, the people placed by the id $44; the main loop goes on with the walk
| (end_state END_WALK; the King's message ends in FINISH_GAME).
end_fade_room:
    movem.l %d0-%d3/%a0, -(%sp)
    moveq #1, %d1
1:  moveq #4, %d0
    bsr.w end_wait
    bcs.s 9f
    bsr.w death_fade                        | (d1 = the step, 4 is black)
    addq.w #1, %d1
    cmpi.w #5, %d1
    bne.s 1b
    move.w #119, %d0
    bsr.w end_wait
    bcs.s 9f
    move.w #0x9D, %d1
    move.w #0x44, %d2
    moveq #17, %d3
    moveq #0, %d0
    bsr.w enter_building
    lea end_state(%pc), %a0
    move.w #END_WALK, (%a0)
    lea end_times+4(%pc), %a0
    move.l frame_count(%pc), (%a0)
    lea end_count(%pc), %a0
    move.w #END_WALK_FRAMES, (%a0)
    lea end_stage(%pc), %a0
    clr.w (%a0)
9:  movem.l (%sp)+, %d0-%d3/%a0
    rts

| d0+1 frames in which the game stands still, with the keys read: Esc ends the wait at once (carry set; the main loop then leaves the program).
end_wait:
    movem.l %d0/%a0, -(%sp)
1:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 2f
    dbra %d0, 1b
    movem.l (%sp)+, %d0/%a0                 | (the flags are those of the tst: carry clear)
    rts
2:  movem.l (%sp)+, %d0/%a0
    ori #1, %ccr
    rts

| The walk to the King has not got there in END_WALK_FRAMES (the ROM's takes about 150): his message is started from where he stands (the script of the room's
| person), and when that does not end the walk within END_WALK_GRACE frames, or there is no person, the ending goes on to the outro.
end_walk_timeout:
    movem.l %d0/%a0-%a1, -(%sp)
    lea end_stage(%pc), %a0
    tst.w (%a0)
    bne.s 3f
    move.w #1, (%a0)
    lea end_count(%pc), %a0
    move.w #END_WALK_GRACE, (%a0)
    .ifdef NPCS
    lea npc_slots(%pc), %a1
    moveq #NPC_SLOTS-1, %d0
1:  cmpi.b #0xFF, E_ENT(%a1)
    beq.s 2f
    cmpi.b #0xFF, N_SCRIPT(%a1)
    bne.s 4f
2:  lea NPC_REC(%a1), %a1
    dbra %d0, 1b
    .endif
3:  lea end_state(%pc), %a0
    move.w #END_FINISH, (%a0)
    .ifdef NPCS
    bra.s 9f
4:  moveq #0, %d0
    move.b N_SCRIPT(%a1), %d0
    bsr.w iscript_run
    .endif
9:  movem.l (%sp)+, %d0/%a0-%a1
    rts

| ------------------------------------------------------------------------------------------------------------------ the fade
| Screen_FadeToBlack: the palette a quarter darker every fifth frame, black after four steps (the ROM: counter + $32 a frame, steps at 5.12 frames). Nothing when the
| screen is black already.
flow_fade_out:
    movem.l %d0-%d2/%a0, -(%sp)
    movea.l #PALETTE, %a0
    moveq #15, %d0
    moveq #0, %d2
1:  or.w (%a0)+, %d2
    dbra %d0, 1b
    andi.w #0x777, %d2                      | (the unused bits of a palette register read as anything)
    beq.s 9f
    moveq #1, %d1
2:  moveq #4, %d0
3:  bsr.w wait_vbl
    bsr.w input_poll                        | Esc leaves at once (the frame loop would only see it after the next screen was made)
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 8f
    dbra %d0, 3b
    bsr.w death_fade
    addq.w #1, %d1
    cmpi.w #5, %d1
    bne.s 2b
9:  movem.l (%sp)+, %d0-%d2/%a0
    rts
8:  FAR_JMP viewer_leave                    | the program's way out (frame_exit, TOS's screen and palette, Pterm0): it never comes back

flow_last:
    .word -1, -1, -1                        | the area, palette set and screen the event below belongs to
flow_event:
    .word -1                                | its special event id ($FF none; bit 7 set once its first tick has run)
flow_exit:
    .word 0                                 | the song to play when he has walked out of the temple he respawned in (0: the package's own)
end_state:
    .word 0                                 | 0, END_FREEZE, END_WALK or END_FINISH
end_count:
    .word 0
end_stage:
    .word 0                                 | the walk: 0, 1 once the time ran out and the King's message was started (or there was none)
end_times:
    .long 0, 0                              | frame_count when the ending began and when the King's room was there
    .text
