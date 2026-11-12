| REPLAY=n (tests and tools/sidebyside.py only, never the disk): the program plays a stream of NES pads instead of the keys and the stick, and
| writes a trace of the game's state at every poll, so that a run of the ROM (tools/refnes/botplay.mjs) and a run of the port with the same
| buttons can be put side by side. n is the number of polls the stream and the trace hold.
|
| replay.bin (build/generated, written by sidebyside.py): one byte a poll, the NES layout (A $80, B $40, Select $20, Start $10, Up 8, Down 4,
| Left 2, Right 1). At poll k the trace gets record k (REPLAY_REC bytes; the state before the pad of poll k is used, that is after k passes of
| the loop), then the pad of byte k replaces what the keys made. Past the end of the stream the pad is 0 and nothing is recorded.
|
| A record (big endian): hero x.w, y.w, facing.b (1: right), area.b, screen.b, power.b, magic.b, power fraction.b, experience.w, gold.l;
| then the 8 enemy slots: entity, x, y, hit points (bytes); then the music.b, the spell's type.b ($FF: none), spell x.b, y.b, the VBL count of the poll.l (frame_count), the hero's x fraction.b, his acceleration.w, 5 bytes of 0.
| replay_count (a word) is the number of polls so far.

    .equ REPLAY_REC, 64
    .equ REPLAY_RING, 256                   | records kept: record k is at k mod 256

| Only a poll of the main loop while he lives is a pass (replay_main): the ROM's side counts the passes of Game_MainLoop in play the same way (no
| scroll, no box, no death: those run loops of their own there). Any other poll (a box, a menu, the frames of a scroll, a death) presses A every
| eighth VBL while the stream lasts, which takes messages away; the ROM's side does the same when its loop has not passed for a while.
replay_main_on:
    move.l %a0, -(%sp)
    lea replay_main(%pc), %a0
    st (%a0)
    movea.l (%sp)+, %a0
    rts
replay_main_off:
    move.l %a0, -(%sp)
    lea replay_main(%pc), %a0
    sf (%a0)
    movea.l (%sp)+, %a0
    rts

| d0 = the pad the keys made; out: d0 = the stream's. Every register but d0 is kept.
replay_step:
    movem.l %d1-%d2/%a0-%a3, -(%sp)
    lea game_start(%pc), %a3
    lea replay_count(%pc), %a0
    moveq #0, %d1
    move.w (%a0), %d1
    cmpi.w #REPLAY, %d1
    bcs.w 1f
    moveq #0, %d0                           | the stream has ended
    bra.w 9f
1:  move.b replay_main(%pc), %d2
    beq.s 4f
    move.w hero_dead(%pc), %d2
    beq.s 5f
4:  moveq #0, %d0                           | not a pass: A every eighth VBL
    move.l frame_count(%pc), %d2
    btst #2, %d2
    beq.w 9f
    btst #3, %d2
    beq.w 9f
    move.b #0x80, %d0
    bra.w 9f
5:  addq.w #1, (%a0)
    movea.l %a3, %a1
    adda.l #replay_pads, %a1
    move.b (%a1,%d1.l), -(%sp)              | the pad of this poll (taken after the record)
    andi.l #REPLAY_RING-1, %d1              | (a ring: the driver reads it every 200 VBLs, a long stream takes no more memory)
    lsl.l #6, %d1                           | * REPLAY_REC
    movea.l %a3, %a1
    adda.l #replay_trace, %a1
    adda.l %d1, %a1
    move.w hero_x(%pc), (%a1)+
    move.w hero_y(%pc), (%a1)+
    move.w hero_flip(%pc), %d1
    sne %d1
    andi.b #1, %d1
    move.b %d1, (%a1)+
    move.b cur_area+1(%pc), (%a1)+
    move.b cur_screen+1(%pc), (%a1)+
    lea hud_state(%pc), %a0
    move.b (%a0)+, (%a1)+                   | power
    move.b (%a0)+, (%a1)+                   | magic
    move.b hero_hpl(%pc), (%a1)+
    move.b (%a0)+, (%a1)+                   | experience
    move.b (%a0)+, (%a1)+
    move.b (%a0)+, (%a1)+                   | gold
    move.b (%a0)+, (%a1)+
    move.b (%a0)+, (%a1)+
    move.b (%a0)+, (%a1)+
    lea enemies(%pc), %a0
    moveq #7, %d2
2:  move.b E_ENT(%a0), (%a1)+
    move.b E_X(%a0), (%a1)+
    move.b E_Y(%a0), (%a1)+
    move.b E_HP(%a0), (%a1)+
    lea E_BYTES(%a0), %a0
    dbra %d2, 2b
    move.b cur_music+1(%pc), (%a1)+
    lea spell_state(%pc), %a0
    move.b 1(%a0), %d2                      | (the spell's type, x and y: see spell_state; Thunder and Fire after their hit are the ROM's types 6 and 7,
    cmpi.b #1, %d2                          | which the port keeps as spell_hit's count)
    beq.s 4f
    cmpi.b #2, %d2
    bne.s 6f
4:  move.w spell_hit(%pc), %d1
    beq.s 6f
    addq.b #5, %d2
6:  move.b %d2, (%a1)+
    move.b 5(%a0), (%a1)+
    move.b 9(%a0), (%a1)+
    move.l frame_count(%pc), %d2            | the VBL count (frame.s) of this poll: where its picture is in Hatari's video
    move.b %d2, 3(%a1)
    lsr.l #8, %d2
    move.b %d2, 2(%a1)
    lsr.l #8, %d2
    move.b %d2, 1(%a1)
    lsr.l #8, %d2
    move.b %d2, (%a1)
    addq.l #4, %a1
    move.b hero_x+11(%pc), (%a1)+           | the hero's x fraction (the hero block: frac at 10, a word, acceleration at 12)
    move.w hero_x+12(%pc), %d2
    move.b %d2, 1(%a1)
    lsr.w #8, %d2
    move.b %d2, (%a1)
    addq.l #2, %a1
    lea enemies(%pc), %a0
    move.b 6*E_BYTES+E_XF(%a0), (%a1)+     | the x fractions of slots 6 and 7 (the slots a screen fills first)
    move.b 7*E_BYTES+E_XF(%a0), (%a1)+
    moveq #2, %d2
3:  clr.b (%a1)+
    dbra %d2, 3b
    .ifdef REPLAY_HEAL
    lea hud_state(%pc), %a0                 | (a segment's "heal": power under 40 is made 80 after the record, as botplay.mjs does it in the ROM)
    cmpi.b #40, (%a0)
    bcc.s 7f
    move.b #80, (%a0)
    lea hud_dirty(%pc), %a0
    st (%a0)
7:
    .endif
    move.b (%sp)+, %d0
9:  movem.l (%sp)+, %d1-%d2/%a0-%a3
    rts

replay_count:
    .word 0
replay_main:
    .byte 0
    .even

    .section .batchdata
    .even
replay_pads:
    .incbin "replay.bin"
    .even
replay_trace:
    .space REPLAY_RING*REPLAY_REC
    .section .text.early,"ax"
