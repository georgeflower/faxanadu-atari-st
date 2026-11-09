| Music and sound effects on the YM2149, played from the VBL (50 Hz, as the PAL NES runs its sound engine).
|
| Included by frame.s. The data is sound.bin (tools/build_sound.py): the program gives its address to sound_init. A song is a stream of changes
| from one frame to the next, a sound effect plain frames that take over the channels they name from the music (see build_sound.py).
|
| sound_init      a0 = sound.bin (or 0: no sound), a1 = a buffer of SND_SONG_MAX bytes for the song being played (the songs are packed), clears the state
| sound_play_music d0 = song 1 up, 0 stops it; the song loops if it has a loop point
| sound_play_sfx  d0 = sound effect 1 up: asked for, as the ROM's SoundEffect_SetCurrent does; the next sound_tick decides (see there)
| sound_tick      once a VBL (vbl_isr calls it): next frame of the song and the effect, mixed, into the YM's registers 0-10
| sound_silence   (supervisor mode) the YM quiet
| sound_keys      (debug) F1-F10 play songs 1-10, Ctrl+F 11-20, the digit keys 1-0 sound effects 1-10, Ctrl 11-20, Shift 21-30, Backspace stops

    .equ YM_SELECT, 0xFFFF8800
    .equ YM_DATA, 0xFFFF8802

    .equ SND_BIN, 0                         | the address of sound.bin
    .equ SND_MPTR, 4                        | the song: where the next frame is
    .equ SND_MLOOP, 8                       | where it loops back to (0: it ends)
    .equ SND_SPTR, 12                       | the sound effect: where the next frame is
    .equ SND_MLEFT, 16                      | frames of the song left
    .equ SND_MLLEFT, 18                     | frames left at the loop point
    .equ SND_SLEFT, 20                      | frames of the sound effect left
    .equ SND_MREGS, 22                      | the song's registers 0-10 as they are now (12 bytes)
    .equ SND_OUT, 34                        | what was written to the YM last (12 bytes)
    .equ SND_LASTKEY, 46                    | sound_keys: the key that started the last sound, until it is released
    .equ SND_SONG, 48                       | the buffer the song is unpacked into
    .equ SND_PEND, 52                       | the sound effect asked for since the last tick (0 none)
    .equ SND_PRIO, 54                       | the handler index of the effect that runs: the ROM's priority, lower is more important
    .equ SND_BUSY, 55                       | ticks left that the engine counts that effect as running (0: a new effect is always taken)
    .equ SND_SIZE, 56
    .equ SND_SONG_MAX, 15360                | what a song may be unpacked (build_sound.SONG_MAX; the biggest is 15,304)

    .section .data
    .even
snd_state:
    .space SND_SIZE

    .text

| The mixer register of the output (a1): the bits in the mask come from the sound effect's (a2), the others stay the music's (a macro).
    .macro MIXER_MERGE mask
    move.b 7(%a2), %d3                      | the effect's mixer
    move.b 7(%a1), %d2                      | the music's
    eor.b %d2, %d3
    andi.b #\mask, %d3
    eor.b %d3, %d2
    move.b %d2, 7(%a1)
    .endm

sound_init:
    lea snd_state(%pc), %a2
    moveq #(SND_SIZE/2)-1, %d0
1:  clr.w (%a2)+
    dbra %d0, 1b
    lea snd_state(%pc), %a2
    move.l %a0, SND_BIN(%a2)
    move.l %a1, SND_SONG(%a2)
    move.b #0xFF, SND_MREGS+7(%a2)          | all tones and noises off, the two port bits high
    move.b #0xFF, SND_OUT+7(%a2)
    rts

| d0 = the song (0 stops it)
sound_play_music:
    movem.l %d1/%a0-%a2, -(%sp)
    lea snd_state(%pc), %a0
    clr.w SND_MLEFT(%a0)
    move.b #0xFF, SND_MREGS+7(%a0)
    clr.b SND_MREGS+8(%a0)
    clr.b SND_MREGS+9(%a0)
    clr.b SND_MREGS+10(%a0)
    movea.l SND_BIN(%a0), %a1
    move.l %a1, %d1
    beq.s 9f
    tst.w %d0
    beq.s 9f
    cmp.w (%a1), %d0                        | n_music
    bhi.s 9f
    move.w %d0, %d1
    lsl.w #2, %d1
    move.l 0(%a1,%d1.w), %d1                | the offset of song d0 (the table starts at 4, entry d0 is at 4 + 4 * (d0 - 1))
    lea 0(%a1,%d1.l), %a2                   | the packed record
    movea.l SND_SONG(%a0), %a1              | unpacked into the buffer (the song is silent meanwhile: SND_MLEFT is 0)
    exg %a0, %a2
    bsr.w unpack
    exg %a0, %a2
    movea.l SND_SONG(%a0), %a2              | the record
    lea 8(%a2), %a1                         | the stream
    move.l %a1, SND_MPTR(%a0)
    move.w 2(%a2), SND_MLLEFT(%a0)
    clr.l SND_MLOOP(%a0)
    tst.w 2(%a2)
    beq.s 1f
    adda.l 4(%a2), %a1                      | the loop point
    move.l %a1, SND_MLOOP(%a0)
1:  move.w (%a2), SND_MLEFT(%a0)
9:  movem.l (%sp)+, %d1/%a0-%a2
    rts

| d0 = the sound effect. Like the ROM's SoundEffect_SetCurrent it only remembers the last one asked for; sound_tick (the ROM's next interrupt) decides.
sound_play_sfx:
    movem.l %d1/%a0-%a1, -(%sp)
    lea snd_state(%pc), %a0
    movea.l SND_BIN(%a0), %a1
    move.l %a1, %d1
    beq.s 9f
    tst.w %d0
    beq.s 9f
    cmp.w 2(%a1), %d0                       | n_sfx
    bhi.s 9f
    move.w %d0, SND_PEND(%a0)
9:  movem.l (%sp)+, %d1/%a0-%a1
    rts

sound_tick:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea snd_state(%pc), %a0
    tst.l SND_BIN(%a0)
    beq.w 9f

    | The sound effect asked for since the last tick (SoundEffects_HandleOnInterrupt): it is taken, and the effect that ran is gone for good, unless that
    | one has a lower handler index (the ROM's priority) and is still running; then the new one is forgotten. The record: word frames, byte index, byte busy.
    move.w SND_PEND(%a0), %d0
    beq.s 22f
    clr.w SND_PEND(%a0)
    movea.l SND_BIN(%a0), %a1
    move.w (%a1), %d1                       | n_music
    add.w %d0, %d1
    lsl.w #2, %d1
    move.l 0(%a1,%d1.w), %d1
    lea 0(%a1,%d1.l), %a2                   | the record
    move.b 2(%a2), %d1                      | its handler index
    tst.b SND_BUSY(%a0)
    beq.s 21f                               | nothing runs
    cmp.b SND_PRIO(%a0), %d1
    bhi.s 22f                               | refused: what runs goes on
21: move.b %d1, SND_PRIO(%a0)
    move.b 3(%a2), SND_BUSY(%a0)
    move.w (%a2), SND_SLEFT(%a0)
    addq.l #4, %a2
    move.l %a2, SND_SPTR(%a0)
    bra.s 23f
22: tst.b SND_BUSY(%a0)
    beq.s 23f
    subq.b #1, SND_BUSY(%a0)
23:

    | The song: apply the changes of its next frame to the registers.
    move.w SND_MLEFT(%a0), %d0
    beq.w 8f
    movea.l SND_MPTR(%a0), %a1
    lea SND_MREGS(%a0), %a2
    moveq #0, %d1
    move.b (%a1)+, %d1
    lsr.b #1, %d1
    bcc.s 1f
    move.b (%a1)+, (%a2)                    | period A
    move.b (%a1)+, 1(%a2)
1:  lsr.b #1, %d1
    bcc.s 2f
    move.b (%a1)+, 2(%a2)                   | period B
    move.b (%a1)+, 3(%a2)
2:  lsr.b #1, %d1
    bcc.s 3f
    move.b (%a1)+, 4(%a2)                   | period C
    move.b (%a1)+, 5(%a2)
3:  lsr.b #1, %d1
    bcc.s 4f
    move.b (%a1)+, 6(%a2)                   | noise period
4:  lsr.b #1, %d1
    bcc.s 5f
    move.b (%a1)+, 7(%a2)                   | mixer
5:  lsr.b #1, %d1
    bcc.s 6f
    move.b (%a1)+, 8(%a2)                   | volume A
6:  lsr.b #1, %d1
    bcc.s 7f
    move.b (%a1)+, 9(%a2)                   | volume B
7:  lsr.b #1, %d1
    bcc.s 71f
    move.b (%a1)+, 10(%a2)                  | volume C
71: subq.w #1, %d0
    bne.s 72f
    move.l SND_MLOOP(%a0), %d2              | the last frame: back to the loop point, or the end
    beq.s 73f
    movea.l %d2, %a1
    move.w SND_MLLEFT(%a0), %d0
    bra.s 72f
73: move.b #0xFF, 7(%a2)
    clr.b 8(%a2)
    clr.b 9(%a2)
    clr.b 10(%a2)
72: move.l %a1, SND_MPTR(%a0)
    move.w %d0, SND_MLEFT(%a0)

    | What goes to the YM: the song's registers, with the channels the sound effect takes over.
8:  lea SND_MREGS(%a0), %a2
    lea SND_OUT(%a0), %a1
    move.l (%a2)+, (%a1)+
    move.l (%a2)+, (%a1)+
    move.l (%a2)+, (%a1)+
    lea SND_OUT(%a0), %a1
    move.w SND_SLEFT(%a0), %d0
    beq.w snd_mixed
    movea.l SND_SPTR(%a0), %a2
    moveq #0, %d1
    move.b 11(%a2), %d1                     | the channels it takes: bit 0 A, 1 B, 2 C's tone, 3 the noise
    btst #0, %d1
    beq.s 81f
    move.b (%a2), (%a1)
    move.b 1(%a2), 1(%a1)
    move.b 8(%a2), 8(%a1)
    MIXER_MERGE 0x09
81: btst #1, %d1
    beq.s 82f
    move.b 2(%a2), 2(%a1)
    move.b 3(%a2), 3(%a1)
    move.b 9(%a2), 9(%a1)
    MIXER_MERGE 0x12
82: btst #2, %d1
    beq.s 83f
    move.b 4(%a2), 4(%a1)
    move.b 5(%a2), 5(%a1)
    move.b 10(%a2), 10(%a1)
    MIXER_MERGE 0x04
83: btst #3, %d1
    beq.s 84f
    move.b 6(%a2), 6(%a1)
    MIXER_MERGE 0x20
    btst #2, %d1
    bne.s 84f
    move.b 10(%a2), %d2                     | the noise alone: as loud as the louder of the two on channel C
    cmp.b 10(%a1), %d2
    bls.s 84f
    move.b %d2, 10(%a1)
84: lea 12(%a2), %a2
    move.l %a2, SND_SPTR(%a0)
    subq.w #1, %d0
    move.w %d0, SND_SLEFT(%a0)
snd_mixed:

    | Registers 0-10 into the YM (register 14 has the floppy select lines: not touched).
    lea SND_OUT(%a0), %a2
    movea.l #YM_SELECT, %a1
    moveq #0, %d0
    moveq #10, %d2
91: move.b %d0, (%a1)
    move.b (%a2)+, 2(%a1)
    addq.b #1, %d0
    dbra %d2, 91b
9:  movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

sound_silence:
    movem.l %d0/%a1, -(%sp)
    movea.l #YM_SELECT, %a1
    move.b #7, (%a1)
    move.b #0xFF, 2(%a1)
    moveq #8, %d0
1:  move.b %d0, (%a1)
    clr.b 2(%a1)
    addq.b #1, %d0
    cmp.b #11, %d0
    bne.s 1b
    movem.l (%sp)+, %d0/%a1
    rts

    .ifndef NEWGAME                         | a test key: not in the disk build
| Debug keys. A sound starts when its key goes down and the key is not the one that started the last (SND_LASTKEY).
sound_keys:
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    lea input_state+IN_KEYS(%pc), %a1
    lea snd_state(%pc), %a0
    moveq #0, %d3                           | what the modifiers add: Ctrl 10, Shift 20
    tst.b 0x1D(%a1)
    beq.s 1f
    moveq #10, %d3
1:  tst.b 0x2A(%a1)
    beq.s 2f
    moveq #20, %d3
2:  moveq #0, %d2
3:  tst.b 0x3B(%a1,%d2.w)                   | F1-F10
    bne.s 4f
    addq.w #1, %d2
    cmp.w #10, %d2
    bne.s 3b
    moveq #0, %d2
5:  tst.b 0x02(%a1,%d2.w)                   | 1 .. 0
    bne.s 6f
    addq.w #1, %d2
    cmp.w #10, %d2
    bne.s 5b
    tst.b 0x0E(%a1)                         | Backspace
    beq.s 8f
    moveq #0x0E, %d1
    cmp.b SND_LASTKEY(%a0), %d1
    beq.s 9f
    move.b %d1, SND_LASTKEY(%a0)
    moveq #0, %d0
    bsr.w sound_play_music
    bra.s 9f
8:  clr.b SND_LASTKEY(%a0)                  | nothing down
    bra.s 9f
4:  moveq #0x3B, %d1                        | a function key: song d2 + 1
    add.b %d2, %d1
    cmp.b SND_LASTKEY(%a0), %d1
    beq.s 9f
    move.b %d1, SND_LASTKEY(%a0)
    move.w %d2, %d0
    addq.w #1, %d0
    cmp.w #20, %d3
    bne.s 41f
    moveq #10, %d3                          | Shift on a function key is Ctrl's
41: add.w %d3, %d0
    bsr.w sound_play_music
    bra.s 9f
6:  moveq #2, %d1                           | a digit key: sound effect d2 + 1
    add.b %d2, %d1
    cmp.b SND_LASTKEY(%a0), %d1
    beq.s 9f
    move.b %d1, SND_LASTKEY(%a0)
    move.w %d2, %d0
    addq.w #1, %d0
    add.w %d3, %d0
    bsr.w sound_play_sfx
9:  movem.l (%sp)+, %d0-%d3/%a0-%a1
    rts
    .endif
