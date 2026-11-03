| Faxanadu for the Atari ST: the start of the program.
|
| For now it only proves the toolchain and the start-up: it gives the memory back to GEMDOS, takes the screen, shows
| sixteen colour bars, waits for a key and puts TOS back as it was. It uses TOS for everything (no interrupts of
| its own yet), so leaving it needs nothing more than the palette.
|
| Position independent: a .PRG made here has no relocation table, so only PC-relative addressing may name our own
| labels. Hardware addresses are fixed numbers and are fine.

    .equ PALETTE, 0xFF8240

    .text
    .globl _start
    .section .text.boot,"ax"
_start:
game_start:
    bra.w start

    .section .data
| The test card's colours, $0RGB with three bits a channel.
test_palette:
    .word 0x000, 0x777, 0x700, 0x070, 0x007, 0x770, 0x707, 0x077
    .word 0x333, 0x555, 0x720, 0x270, 0x027, 0x702, 0x072, 0x742
saved_palette:
    .space 32
old_ssp:
    .long 0
hide_cursor:
    .asciz "\033f"
show_cursor:
    .asciz "\033e"
    .even

    .text
start:
    movea.l 4(%sp), %a3                     | our basepage
    lea stack_end(%pc), %sp

    | Mshrink(0, basepage, size): GEMDOS gave us all memory; keep only what the image needs.
    move.l #image_size, %d0
    addi.l #0x100, %d0
    move.l %d0, -(%sp)
    move.l %a3, -(%sp)
    clr.w -(%sp)
    move.w #0x4A, -(%sp)
    trap #1
    lea 12(%sp), %sp

    | Super(0): ST hardware registers can only be reached in supervisor mode.
    clr.l -(%sp)
    move.w #32, -(%sp)
    trap #1
    addq.l #6, %sp
    lea old_ssp(%pc), %a0                   | (PC-relative cannot be a destination)
    move.l %d0, (%a0)
    lea stack_end(%pc), %sp                 | whatever stack Super left us on, use our own

    | Low resolution, whatever the desktop was in. (A monochrome monitor ignores this.)
    clr.w -(%sp)
    move.l #-1, -(%sp)
    move.l #-1, -(%sp)
    move.w #5, -(%sp)                       | Setscreen
    trap #14
    lea 12(%sp), %sp

    pea hide_cursor(%pc)
    move.w #9, -(%sp)                       | Cconws
    trap #1
    addq.l #6, %sp

    | Keep TOS's palette, set ours.
    movea.l #PALETTE, %a2
    lea saved_palette(%pc), %a1
    moveq #15, %d1
1:  move.w (%a2)+, (%a1)+
    dbra %d1, 1b
    movea.l #PALETTE, %a2
    lea test_palette(%pc), %a1
    moveq #15, %d1
2:  move.w (%a1)+, (%a2)+
    dbra %d1, 2b

    | Physbase: the screen TOS gave us.
    move.w #2, -(%sp)
    trap #14
    addq.l #2, %sp
    movea.l %d0, %a0

    | 200 lines of 20 groups of 16 pixels; group n is colour n (mod 16). A group is four plane words, all ones for
    | each set bit of the colour.
    move.w #199, %d6
3:  moveq #0, %d2
4:  move.w %d2, %d3
    moveq #3, %d4
5:  lsr.w #1, %d3                           | the next colour bit goes to the carry
    scs %d5
    ext.w %d5                               | $FFFF if it was set
    move.w %d5, (%a0)+
    dbra %d4, 5b
    addq.w #1, %d2
    cmpi.w #20, %d2
    blt.s 4b
    dbra %d6, 3b

    | Crawcin: wait for a key.
    move.w #7, -(%sp)
    trap #1
    addq.l #2, %sp

    | Put back what we changed.
    movea.l #PALETTE, %a2
    lea saved_palette(%pc), %a1
    moveq #15, %d1
6:  move.w (%a1)+, (%a2)+
    dbra %d1, 6b
    pea show_cursor(%pc)
    move.w #9, -(%sp)
    trap #1
    addq.l #6, %sp

    | Super(old), then Pterm0.
    move.l old_ssp(%pc), -(%sp)
    move.w #32, -(%sp)
    trap #1
    addq.l #6, %sp
    clr.w -(%sp)
    trap #1

    .section .stack,"aw",@progbits
    .space 4096
stack_end:
