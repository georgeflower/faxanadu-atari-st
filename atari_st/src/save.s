| The save file (included by viewer.s, last of the code in .text). A saved game is the mantra: SAVE.SAV holds the mantra's characters and a line end (13, 10), the
| text pw_encode makes from the state pw_build takes from the game. Loading reads the characters back through pw_decode and the caller runs mantra_apply, so a file
| that was edited, cut or damaged is refused as a typed mantra would be. The file lies next to the program, like the .DAT files (a name without a path).
|
| save_guru       the Guru's SHOW_PASSWORD: a box of two lines, Save to disk or Show mantra; d0.w = 1: show the mantra (chosen, or the disk would not take it)
| save_title      CONTINUE on the title: with a SAVE.SAV, a box of Load game or Enter mantra; d0.w = 1: a game was read (pw_block holds it), 0: enter a mantra
| sv_choose       a1 and a2 = two lines of text: a small box in the middle of the window; Up and Down choose, A or Start takes the line (d0.w = 0 or 1), B or Esc -1
| sv_write        d0.w = 0 saved, -1 not (the disk is write protected or full)
| sv_read         d0.w = 0 read (pw_block holds the state), -1 refused, -2 there is no file
|
| The disk is used as load_package does: the YM is silenced and TOS's own VBL runs meanwhile (it switches the drive off again; ours would not), and TOS's critical-error
| handler is ours meanwhile (a write protected disk would otherwise make the desktop's alert box, on a screen that is not ours, and wait for a click that cannot come).
| The song starts again afterwards.

    .equ ETV_CRITIC, 0x404
    .equ SV_READ, 35                        | 32 characters, the line end and one more: a longer file is refused for its length

    .text
| a1, a2 = the two lines; d7.w = the one the cursor is on (drawn light on dark turned round). Keeps every register.
sv_draw:
    movem.l %d0-%d4/%d6/%a0-%a3, -(%sp)
    bsr.w text_color
    bsr.w shown_screen
    moveq #5, %d0                           | the box of the start menu: groups 5 to 14, lines 88 to 143
    moveq #88, %d1
    moveq #10, %d2
    moveq #56, %d3
    bsr.w draw_box
    moveq #0, %d6
    tst.w %d7
    bne.s 1f
    moveq #-1, %d6
1:  movea.l %a1, %a0
    moveq #104, %d0
    moveq #96, %d1
    bsr.w text_string
    moveq #0, %d6
    tst.w %d7
    beq.s 2f
    moveq #-1, %d6
2:  movea.l %a2, %a0
    moveq #104, %d0
    moveq #114, %d1
    bsr.w text_string
    movem.l (%sp)+, %d0-%d4/%d6/%a0-%a3
    rts

sv_choose:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    moveq #0, %d7
    bsr.s sv_draw
1:  bsr.w wait_vbl
    bsr.w input_poll
    lea input_state(%pc), %a0
    tst.b IN_QUIT(%a0)
    bne.s 8f
    moveq #0, %d0
    move.b IN_PAD_NEW(%a0), %d0
    beq.s 1b
    btst #6, %d0                            | B
    bne.s 8f
    btst #7, %d0                            | A
    bne.s 9f
    btst #4, %d0                            | Start
    bne.s 9f
    andi.b #0x0C, %d0                       | Up or Down
    beq.s 1b
    eori.w #1, %d7
    moveq #0x0B, %d0
    bsr.w sound_play_sfx
    bsr.w sv_draw
    bra.w 1b
8:  moveq #-1, %d7
9:  move.w %d7, %d0
    movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

| The disk is about to be used / is done with. Keep every register.
sv_disk_on:
    movem.l %d0/%a0-%a1, -(%sp)
    bsr.w sound_silence
    lea sv_crit_old(%pc), %a0
    move.l ETV_CRITIC, (%a0)
    lea sv_crit(%pc), %a1
    move.l %a1, ETV_CRITIC
    move.l old_vbl(%pc), %d0
    beq.s 1f
    lea saved_vbl(%pc), %a1
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l VBL_VECTOR, (%a1)
    move.l %d0, VBL_VECTOR
    move.w (%sp)+, %sr
1:  movem.l (%sp)+, %d0/%a0-%a1
    rts

sv_disk_off:
    movem.l %d0/%a0, -(%sp)
    move.l old_vbl(%pc), %d0
    beq.s 1f
    move.w %sr, -(%sp)
    ori.w #0x0700, %sr
    move.l saved_vbl(%pc), VBL_VECTOR
    move.w (%sp)+, %sr
1:  move.l sv_crit_old(%pc), ETV_CRITIC
    move.w sv_song(%pc), %d0
    beq.s 2f
    bsr.w sound_play_music
2:  movem.l (%sp)+, %d0/%a0
    rts

sv_crit:                                    | TOS's own default: the error code, negative, so the BIOS gives up and the call answers with it
    move.w 4(%sp), %d0
    ext.l %d0
    rts

| The mantra of the game goes to SAVE.SAV (Fcreate, Fwrite, Fclose; every answer is looked at). A file that was made but not written whole is deleted again.
sv_write:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    lea pw_block(%pc), %a1
    bsr.w pw_build
    movea.l %a1, %a0
    lea pw_text(%pc), %a1
    bsr.w pw_encode
    movea.l %a1, %a0
    moveq #0, %d4
1:  tst.b (%a0)+                            | the length
    beq.s 2f
    addq.w #1, %d4
    bra.s 1b
2:  subq.l #1, %a0
    move.b #13, (%a0)+
    move.b #10, (%a0)
    addq.w #2, %d4
    bsr.w sv_disk_on
    moveq #-1, %d3                          | the answer
    clr.w -(%sp)                            | Fcreate(name, 0)
    pea sv_name(%pc)
    move.w #0x3C, -(%sp)
    trap #1
    addq.l #8, %sp
    tst.l %d0
    bmi.s 9f
    move.w %d0, %d5                         | the handle (the traps keep d3-d7 and a3-a6)
    pea pw_text(%pc)                        | Fwrite(handle, count, buffer)
    move.l %d4, -(%sp)
    move.w %d5, -(%sp)
    move.w #0x40, -(%sp)
    trap #1
    lea 12(%sp), %sp
    move.l %d0, %d6
    move.w %d5, -(%sp)                      | Fclose
    move.w #0x3E, -(%sp)
    trap #1
    addq.l #4, %sp
    tst.l %d0
    bmi.s 3f
    cmp.l %d4, %d6
    bne.s 3f
    moveq #0, %d3                           | all of it is on the disk
    bra.s 9f
3:  pea sv_name(%pc)                        | Fdelete: no half file
    move.w #0x41, -(%sp)
    trap #1
    addq.l #6, %sp
9:  bsr.w sv_disk_off
    move.w %d3, %d0
    lea sv_status(%pc), %a0
    move.w %d0, (%a0)
    movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

| SAVE.SAV is read into pw_text and decoded: the characters up to the first byte of 32 or less (the line end, a space, the end of the text).
sv_read:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    bsr.w sv_disk_on
    moveq #-2, %d3                          | no file
    clr.w -(%sp)                            | Fopen(name, read)
    pea sv_name(%pc)
    move.w #0x3D, -(%sp)
    trap #1
    addq.l #8, %sp
    tst.l %d0
    bmi.s 9f
    move.w %d0, %d5
    moveq #-1, %d3                          | there is one: from here on a bad one is refused
    pea pw_text(%pc)                        | Fread(handle, count, buffer)
    move.l #SV_READ, -(%sp)
    move.w %d5, -(%sp)
    move.w #0x3F, -(%sp)
    trap #1
    lea 12(%sp), %sp
    move.l %d0, %d6
    move.w %d5, -(%sp)                      | Fclose
    move.w #0x3E, -(%sp)
    trap #1
    addq.l #4, %sp
    tst.l %d6
    ble.s 9f                                | an error, or nothing in it
    lea pw_text(%pc), %a0
    clr.b (%a0,%d6.w)
    movea.l %a0, %a1
3:  move.b (%a1), %d0
    beq.s 4f
    cmpi.b #' ', %d0
    bhi.s 5f
    clr.b (%a1)
    bra.s 4f
5:  addq.l #1, %a1
    bra.s 3b
4:  lea pw_block(%pc), %a1
    bsr.w pw_decode
    move.w %d0, %d3
9:  bsr.w sv_disk_off
    move.w %d3, %d0
    lea sv_status(%pc), %a0
    move.w %d0, (%a0)
    movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

save_guru:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    lea sv_song(%pc), %a0
    move.w cur_music(%pc), (%a0)            | the song that goes on afterwards
    lea sv_t_save(%pc), %a1
    lea sv_t_show(%pc), %a2
    bsr.w sv_choose
    tst.w %d0
    bne.s 8f                                | Show mantra, or B
    bsr.w sv_write
    lea sv_t_saved(%pc), %a0
    tst.w %d0
    beq.s 1f
    lea sv_t_failed(%pc), %a0
1:  bsr.w message_box
    neg.w %d0                               | saved: 0, not: 1 (the mantra is shown instead)
    bra.s 9f
8:  moveq #1, %d0
9:  movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

save_title:
    movem.l %d1-%d7/%a0-%a3, -(%sp)
    lea sv_song(%pc), %a0
    move.w #8, (%a0)                        | the title's song (CONTINUE leaves it on)
    bsr.w sv_read
    moveq #0, %d6
    move.w %d0, %d6
    cmpi.w #-2, %d6
    beq.s 7f                                | no file: the entry
1:  lea sv_t_load(%pc), %a1
    lea str_enter(%pc), %a2
    bsr.w sv_choose
    tst.w %d0
    bne.s 7f                                | Enter mantra, or B
    tst.w %d6
    beq.s 6f
    lea sv_t_wrong(%pc), %a0                | the file is refused as a typed mantra is
    bsr.w message_box
    bra.s 1b
6:  moveq #1, %d0
    bra.s 9f
7:  moveq #0, %d0
9:  movem.l (%sp)+, %d1-%d7/%a0-%a3
    rts

sv_name:
    .asciz "SAVE.SAV"
sv_t_save:
    .asciz "Save to disk"
sv_t_show:
    .asciz "Show mantra"
sv_t_saved:
    .asciz "Game saved."
sv_t_failed:
    .asciz "Could not save."
sv_t_load:
    .asciz "Load game"
sv_t_wrong:
    .ascii "Mantra is in\n"
    .asciz "the wrong."
    .even
sv_crit_old:
    .long 0
sv_song:
    .word 0
sv_status:
    .word 0                                 | what sv_write or sv_read answered last (tests)
