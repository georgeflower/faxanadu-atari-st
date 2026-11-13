| The frame loop and the input: a 50 Hz VBL counter and the IKBD (joystick in port 1, keyboard) made into an NES pad.
|
| Included by the program (viewer.s now, the game later); position independent like the rest: our own labels are reached
| with PC-relative addressing only, the hardware with absolute addresses.
|
| frame_init (supervisor mode) takes over the VBL and the keyboard interrupt; frame_exit gives both back to TOS.
| Every frame: wait_vbl, then input_poll. `pad` then holds the NES pad (A=$80 B=$40 Select=$20 Start=$10 Up=$08 Down=$04
| Left=$02 Right=$01), `pad_new` the buttons that went down since the last poll, `quit` is set by Esc.
|
| Buttons: stick left, right, up and down are the pad's; the stick's fire button is B (the sword; there is only one
| button on an Atari stick). Keyboard: arrow keys as the pad, Space = A (jump), Alternate = B, Return = Start, Tab = Select.
| The mouse port (joystick 0) is ignored.
| With JOYPAD (the disk) the stick is the centre and what a button means depends on where it is pressed: input_poll (menus, boxes, the
| title: everything but the running game) has fire and Space = A (choose), Alternate = B (back); input_poll_game (the main loop, and the
| waits of a screen change) has fire and Alternate = B (the sword, also with Up held: never the spell), Space = Up and B together (the
| spell), and the press of Up is a jump (joy_jump, viewer.s). The notes on JOYPAD are in AGENTS.md.

    .equ VBL_VECTOR, 0x70
    .equ IKBD_VECTOR, 0x118
    .equ IKBD_STATUS, 0xFFFFFC00
    .equ IKBD_DATA, 0xFFFFFC02
    .equ MIDI_STATUS, 0xFFFFFC04
    .equ MIDI_DATA, 0xFFFFFC06
    .equ MFP_IPRB, 0xFFFFFA0D
    .equ MFP_ISRB, 0xFFFFFA11
    .equ MFP_IMRB, 0xFFFFFA15

    .equ NES_A, 0x80
    .equ NES_B, 0x40
    .equ NES_SELECT, 0x20
    .equ NES_START, 0x10
    .equ NES_UP, 0x08
    .equ NES_DOWN, 0x04
    .equ NES_LEFT, 0x02
    .equ NES_RIGHT, 0x01

    .equ SCAN_ESC, 0x01

    | the input block (input_state): the ring of bytes the interrupt queued, then what the parser made of them
    .equ IN_HEAD, 0                         | the interrupt writes at the head
    .equ IN_TAIL, 1                         | the parser reads at the tail
    .equ IN_RING, 2                         | 256 bytes
    .equ IN_PACKET, 258                     | what the next byte belongs to
    .equ IN_JOY, 259                        | joystick 1: bits 0-3 up, down, left, right; bit 7 fire
    .equ IN_PAD, 260
    .equ IN_PAD_NEW, 261
    .equ IN_QUIT, 262
    .equ IN_KEYS, 264                       | 128 bytes, non-zero while a key is down
    .ifdef JOYPAD
    .equ IN_MODE, 392                       | the mode of the last poll: 0 menu, 1 game (a change of mode makes no button new)
    .equ IN_REQ, 393                        | the mode the poll in progress runs in
    .equ IN_UPCNT, 394                      | polls (game mode) with Up held on the stick or the arrow key, up to 4; 1 is the press, 3 starts a jump
    .endif
    .equ IN_TRAINER, 395                    | the trainer (T, src/trainer.s): nonzero while it is on (every build)

    .equ PKT_NONE, 0
    .equ PKT_JOY0, 1
    .equ PKT_JOY1, 2
    .equ PKT_SKIP2, 3
    .equ PKT_SKIP1, 4

    .section .data
    .even
frame_count:
    .long 0                                 | VBLs since frame_init
late_frames:
    .long 0                                 | VBLs wait_vbl found already passed
last_wait:
    .long 0
old_vbl:
    .long 0
old_ikbd:
    .long 0
input_state:
    .space 396                              | (392 to 395: the JOYPAD bytes and the trainer)

    .text

| In supervisor mode. Our VBL and our keyboard interrupt replace TOS's; the joystick is switched to event reporting.
frame_init:
    move.w %sr, %d0
    ori.w #0x0700, %sr
    lea old_vbl(%pc), %a0
    move.l VBL_VECTOR, (%a0)
    lea vbl_isr(%pc), %a1
    move.l %a1, VBL_VECTOR
    lea old_ikbd(%pc), %a0
    move.l IKBD_VECTOR, (%a0)
    lea ikbd_isr(%pc), %a1
    move.l %a1, IKBD_VECTOR
    lea frame_count(%pc), %a0
    clr.l (%a0)+                            | frame_count
    clr.l (%a0)+                            | late_frames
    clr.l (%a0)                             | last_wait
    movea.l #IKBD_STATUS, %a0
1:  btst #0, (%a0)                          | whatever the ACIA holds is stale
    beq.s 2f
    tst.b 2(%a0)
    bra.s 1b
2:  lea input_state(%pc), %a0
    .ifdef JOYPAD
    moveq #(396/4)-1, %d1
    .else
    moveq #(392/4)-1, %d1
    .endif
3:  clr.l (%a0)+
    dbra %d1, 3b
    movea.l #IKBD_STATUS, %a0
4:  btst #1, (%a0)
    beq.s 4b
    move.b #0x14, 2(%a0)                    | joysticks send events
    move.w %d0, %sr
    rts

| In supervisor mode. Hands the keyboard back to TOS: both ACIAs share one interrupt line to the MFP, which only notices it
| going low, so a byte left in either one would keep the line low and the desktop would come back without keyboard and mouse.
frame_exit:
    move.w %sr, %d0
    ori.w #0x0700, %sr
    bclr #6, MFP_IMRB
    lea old_vbl(%pc), %a0
    move.l (%a0), VBL_VECTOR
    lea old_ikbd(%pc), %a0
    move.l (%a0), IKBD_VECTOR
    bsr.w sound_silence
    movea.l #IKBD_STATUS, %a0
    move.w #255, %d1
1:  btst #0, (%a0)
    beq.s 2f
    tst.b 2(%a0)
    dbra %d1, 1b
2:  movea.l #MIDI_STATUS, %a0
    move.w #255, %d1
3:  btst #0, (%a0)
    beq.s 4f
    tst.b 2(%a0)
    dbra %d1, 3b
4:  movea.l #IKBD_STATUS, %a0
    move.w #0x7FFF, %d1
5:  btst #1, (%a0)
    dbne %d1, 5b
    move.b #0x08, 2(%a0)                    | the mouse reports its moves again
    move.b #0xBF, MFP_IPRB                  | a zero clears a mark, a one leaves it: only the keyboard's goes
    move.b #0xBF, MFP_ISRB
    bset #6, MFP_IMRB
    move.w %d0, %sr
    rts

vbl_isr:
    move.l %a0, -(%sp)
    lea frame_count(%pc), %a0
    addq.l #1, (%a0)
    movea.l (%sp)+, %a0
    bsr.w sound_tick
    rte

| Waits for the next VBL. A VBL that passed before the call (the frame took longer than 20 ms) is counted in late_frames.
wait_vbl:
    movem.l %d0-%d1/%a0, -(%sp)
    lea frame_count(%pc), %a0
    move.l 8(%a0), %d1
    addq.l #1, %d1                          | the VBL we are waiting for
1:  cmp.l (%a0), %d1
    bhi.s 1b                                | it has not come yet
    move.l (%a0), %d0
    move.l %d0, 8(%a0)                      | last_wait
    sub.l %d1, %d0                          | VBLs that passed before the call
    add.l %d0, 4(%a0)                       | late_frames
    movem.l (%sp)+, %d0-%d1/%a0
    rts

| The keyboard interrupt: every byte goes into the ring (a single ACIA holds one byte, and a frame can bring several:
| a missed key release would leave the hero walking by himself).
ikbd_isr:
    movem.l %d0-%d1/%a0, -(%sp)
    lea input_state(%pc), %a0
1:  move.b IKBD_STATUS, %d0
    btst #0, %d0
    beq.s 3f
    move.b IKBD_DATA, %d0
    moveq #0, %d1
    move.b IN_HEAD(%a0), %d1
    move.b %d0, IN_RING(%a0,%d1.w)
    addq.b #1, %d1
    move.b %d1, IN_HEAD(%a0)
    bra.s 1b
3:  btst #0, MIDI_STATUS                    | the MIDI port shares the line: empty it too
    beq.s 4f
    tst.b MIDI_DATA
4:  bclr #6, MFP_ISRB
    movem.l (%sp)+, %d0-%d1/%a0
    rte

| Once a frame: parses what the interrupt queued and makes the pad. Clobbers nothing.
input_poll:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea input_state(%pc), %a1
    .ifdef JOYPAD
    clr.b IN_REQ(%a1)                       | menu mode
    bra.s ip_go
input_poll_game:                            | the running game: once a frame, from the main loop
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    lea input_state(%pc), %a1
    move.b #1, IN_REQ(%a1)
ip_go:
    .endif
    lea IN_KEYS(%a1), %a2
1:  moveq #0, %d2
    move.b IN_TAIL(%a1), %d2
    cmp.b IN_HEAD(%a1), %d2
    beq.w 9f
    moveq #0, %d0
    move.b IN_RING(%a1,%d2.w), %d0
    addq.b #1, %d2
    move.b %d2, IN_TAIL(%a1)

    move.b IN_PACKET(%a1), %d1
    beq.s 4f
    clr.b IN_PACKET(%a1)
    cmpi.b #PKT_JOY1, %d1
    bne.s 2f
    move.b %d0, IN_JOY(%a1)
    bra.s 1b
2:  cmpi.b #PKT_SKIP2, %d1                  | the first of two bytes of a mouse move: the second follows
    bne.s 1b
    move.b #PKT_SKIP1, IN_PACKET(%a1)
    bra.s 1b                                | (PKT_JOY0 and PKT_SKIP1: this byte is the packet's last)

4:  cmpi.b #0xFF, %d0
    bne.s 5f
    move.b #PKT_JOY1, IN_PACKET(%a1)
    bra.s 1b
5:  cmpi.b #0xFE, %d0
    bne.s 6f
    move.b #PKT_JOY0, IN_PACKET(%a1)
    bra.s 1b
6:  cmpi.b #0xF8, %d0
    bcs.s 7f
    cmpi.b #0xFB, %d0
    bhi.s 7f
    move.b #PKT_SKIP2, IN_PACKET(%a1)
    bra.s 1b
7:  move.w %d0, %d3
    andi.w #0x7F, %d3
    tst.b %d0
    bmi.s 8f
    st (%a2,%d3.w)                          | key down
    cmpi.b #SCAN_ESC, %d0
    bne.w 1b
    st IN_QUIT(%a1)
    bra.w 1b
8:  clr.b (%a2,%d3.w)                       | key up
    bra.w 1b

9:  moveq #0, %d0                           | the pad from the stick ...
    move.b IN_JOY(%a1), %d1
    btst #0, %d1
    beq.s 10f
    ori.b #NES_UP, %d0
10: btst #1, %d1
    beq.s 11f
    ori.b #NES_DOWN, %d0
11: btst #2, %d1
    beq.s 12f
    ori.b #NES_LEFT, %d0
12: btst #3, %d1
    beq.s 13f
    ori.b #NES_RIGHT, %d0
13: tst.b %d1
    bpl.s 14f
    .ifdef JOYPAD
    tst.b IN_REQ(%a1)
    bne.s 19f
    ori.b #NES_A, %d0                       | menus: fire chooses
    bra.s 14f
19:
    .endif
    ori.b #NES_B, %d0
14: lea key_map(%pc), %a0                   | ... and from the keys
15: moveq #0, %d2
    move.b (%a0)+, %d2                      | scan code, 0 ends the table
    beq.s 18f
    move.b (%a0)+, %d1
    tst.b (%a2,%d2.w)
    beq.s 15b
    or.b %d1, %d0
    bra.s 15b
18:
    .ifdef JOYPAD
    move.b IN_REQ(%a1), %d3                 | the mode of this poll
    tst.b 0x39(%a2)                         | Space (it is not in key_map: it means something else in each mode)
    sne %d2
    tst.b %d3
    bne.s 20f
    tst.b %d2                               | menus: Space chooses, as fire does
    beq.s 22f
    ori.b #NES_A, %d0
    bra.s 22f
20: move.b IN_UPCNT(%a1), %d1               | the game: how long Up (the stick or the arrow key, not Space) has been held
    btst #3, %d0
    bne.s 21f
    moveq #0, %d1                           | Up is up: no count
    bra.s 23f
21: cmpi.b #4, %d1
    bcc.s 23f
    addq.b #1, %d1
23: move.b %d1, IN_UPCNT(%a1)
    tst.b %d2
    beq.s 26f
    ori.b #NES_UP+NES_B, %d0                | Space: Up held and B (new when Space goes down): the spell
    bra.s 28f
26: btst #6, %d0                            | fire or Alternate pressed just now (B new) with Up held: the sword, never the spell (the ROM's Up
    beq.s 28f                               | and B): Up is left out of the pad in this poll (the count goes on, so it is no new Up after it)
    btst #6, IN_PAD(%a1)
    bne.s 28f
    btst #3, %d0
    beq.s 28f
    bclr #3, %d0
    ori.b #NES_A, %d0                       | (the A of the Up that is held stays: the wing boots)
28: btst #3, %d0
    beq.s 22f
    ori.b #NES_A, %d0                       | Up held is A held for the wing boots (a jump is not A: joy_jump)
22:
    .endif
    .ifdef BATCH
    move.w auto_pad(%pc), %d1               | (tests) the buttons pressed by themselves: 4 frames down, 4 up; 1: A, 2: B and then A, 3: A (Sell is chosen by town.s)
    beq.s 16f
    move.l frame_count(%pc), %d3
    btst #2, %d3
    beq.s 16f
    cmpi.w #2, %d1
    bne.s 17f
    btst #3, %d3
    bne.s 17f
    ori.b #NES_B, %d0
    bra.s 16f
17: ori.b #NES_A, %d0
    .endif
16:
    .ifdef REPLAY
    bsr.w replay_step                       | (tests) the pad from the stream, src/replay.s
    .endif
    move.b IN_PAD(%a1), %d1
    move.b %d0, IN_PAD(%a1)
    not.b %d1
    and.b %d1, %d0
    .ifdef JOYPAD
    move.b IN_REQ(%a1), %d1
    cmp.b IN_MODE(%a1), %d1
    beq.s 27f
    move.b %d1, IN_MODE(%a1)                | the mode changed: no button is new, so that fire still down from a box or a menu is not an attack or a
    moveq #0, %d0                           | choice now; an Up still held is not a jump either
    tst.b %d1
    beq.s 29f
    tst.b IN_UPCNT(%a1)
    beq.s 29f
    move.b #4, IN_UPCNT(%a1)
    bra.s 29f
27: tst.b %d1
    beq.s 29f
    andi.b #0x77, %d0                       | the game: Up is new when the stick's Up (not Space's) was pressed in this poll; A is never new here
    cmpi.b #1, IN_UPCNT(%a1)
    bne.s 29f
    ori.b #NES_UP, %d0
29:
    .endif
    move.b %d0, IN_PAD_NEW(%a1)
    movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

key_map:
    .byte 0x48, NES_UP
    .byte 0x50, NES_DOWN
    .byte 0x4B, NES_LEFT
    .byte 0x4D, NES_RIGHT
    .ifndef JOYPAD
    .byte 0x39, NES_A                       | Space
    .endif
    .byte 0x38, NES_B                       | Alternate
    .byte 0x1C, NES_START                   | Return
    .byte 0x0F, NES_SELECT                  | Tab
    .byte 0
    .even

    .ifdef REPLAY
    .section .text.early,"ax"               | (in front of .data: the test build's replay code then takes nothing of .text's reach)
    .include "replay.s"
    .text
    .endif
    .include "unpack.s"
    .include "sound.s"
