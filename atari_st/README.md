# Faxanadu for the Atari ST

A native port of Faxanadu (NES) for the Atari 520 STFM, written in 68000 assembly. It reads everything from a ROM you supply yourself; no game data is in this repository. Claude helps me write the code.

Status: just started. The program only shows 16 colour bars so far. The plan is in `PLAN.md`, and `AGENTS.md` has everything else.

## Build

You need `binutils-m68k-linux-gnu`, Python 3 and `make`.

    cd atari_st
    make            # build/FAXANADU.PRG
    make check      # unit tests
    make disk       # build/FAXANADU.st, a 720 KB image for a Gotek

The game will read the Europe ROM from `ext/Faxanadu_Europe.nes` (not in the repository). To run it in Hatari you also need a TOS image, for example EmuTOS 512k:

    python3 tools/hatari_shot.py --tos etos512us.img

That writes `build/screen.png` from the running program.

The disassembly in the rest of the repository is chipx86's, and builds with `make` in the root (needs `cc65`).
