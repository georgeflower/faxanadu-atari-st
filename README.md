Faxanadu for Atari ST
============================

This is a work-in-progress port of
[Faxanadu](https://www.mobygames.com/game/7331/faxanadu/) (NES) to the
**Atari ST** (520 STFM, 512 KB, 68000, PAL 50 Hz), written in 68000 assembly
with a Python asset pipeline. It builds a stock TOS `.PRG` (320x200, 16
colours, YM2149 sound).

All game data is read at build time from a ROM you supply
(`ext/Faxanadu_Europe.nes`); no ROM data is included in this repository. The
port lives in [atari_st](atari_st) (see `atari_st/AGENTS.md` and
`atari_st/PLAN.md`). Built with AI help.

# Credits

The disassembly of the NES game, which is the rest of this repository and the
spec for the game's behaviour, is by chipx86 (Christian Hammond):

* [github.com/chipx86/faxanadu](https://github.com/chipx86/faxanadu)
* [Faxanadu Disassembly Notes](https://notes.chipx86.com/Projects/Reverse-Engineering+Projects/Faxanadu+Disassembly/-Overview-)
* [chipx86.com](https://chipx86.com)
