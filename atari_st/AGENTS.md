# AGENTS.md - the briefing for anyone working on the port

Read this before researching anything. When you learn something durable, add it here. `CLAUDE.md` in the repository root only points here.

## 1. What this is

A native **Atari ST (520 STFM, 512 KB, 68000, PAL 50 Hz)** port of **Faxanadu (NES)**, in 68000 assembly (GNU as syntax) with a Python asset pipeline that reads graphics, maps, palettes, text and music from **a ROM you supply** (`ext/Faxanadu_Europe.nes`, gitignored, never committed). The result is a stock TOS `.PRG`: 320x200, 16 colours, YM2149 sound.

It follows the Zelda 1 port (`georgeflower/zelda1-atarist`): same method, same tools, same rules.

The rest of the repository is chipx86's labelled disassembly of the **US** version (`src/*.asm`, builds with `make` in the root). It is the **spec for every behaviour**: when you need a number (speed, timer, damage, tile id, table), read it there, never guess.

Status: set-up and the ROM harness. `src/main.s` is a start-up check that shows 16 colour bars. What comes next is in `PLAN.md`.

## 2. Rules

1. **The ROM is the reference for behaviour.** Read values from the disassembly, then check them in the ROM. The port "improving" on the ROM is a bug report later; match first, change only when asked, and write deliberate differences down here.
2. **All game data comes from the user's ROM.** Nothing from the ROM (images, tables, music) is committed. Tests keep sizes and hashes. If the ROM is missing the build stops; no stand-in art.
3. **Build and test headlessly, always.** Assemble, run in Hatari, compare frames with golden hashes, run the unit tests. A disk image the user has not seen built and run is not delivered.
4. **The 16-bit branch limit wraps silently** in GNU as and ld. `tools/check_reach.py` runs on every link; do not disable it.
5. **Budget first.** An STFM has no blitter and no hardware scroll; a frame is about 160,000 cycles at 50 Hz. Estimate the cycles of anything per-frame before writing it and measure afterwards.
6. **No version numbers** anywhere (no VERSION, no CHANGELOG, no version line in docs). Göran tags releases himself.
7. Pull requests go to `master`; Göran merges them himself, so treat a created pull request as merged. Disk images are named `F-PR##.st` (## = the pull request number). Commits end with the `Co-Authored-By` line and no session link; pull request bodies end with the "Generated with Claude Code" line and no session link.
8. Docs are short and plain, in Göran's voice. One line on the AI help, no details of what was tested by hand.

## 3. Which ROM

The ROM the port reads is **Faxanadu (Europe)**, PAL, because Göran's ST is PAL and runs at 50 Hz like the PAL NES: one game tick per VBL, no pacing tricks. (At 60 Hz, hold one VBL in six.)

The disassembly is the US ROM. They match closely (`tools/rom_diff.py US-ROM EU-ROM`, counts only; the US ROM is what `make` in the root builds, `ext/` is not needed for it):

| bank | what | Europe versus US |
| --- | --- | --- |
| 0-4, 6-11, 14 | area data, area metadata, sprites, CHR RAM tiles, sprite info and palettes, game logic | identical |
| 5 | audio logic and music data | 13,371 bytes differ (not looked at yet) |
| 12 | game logic, interaction scripts, start screen, password | 5,774 bytes differ (texts and the start screen's code) |
| 13 | strings and font | 397 bytes differ (the font is redrawn) |
| 15 | fixed bank | 12 bytes differ: the bank-call code's zero-page variables move by four, three far-call pointers change (the start screen's code moved in bank 12), and a stray padding byte and two bytes at the end of the ROM |

So the disassembly is a valid spec for nearly all logic. For data, **search the Europe ROM for what is needed; do not trust US offsets** (the Zelda port learned this with Rev 1). Where bank 5, 12 or 13 are involved, check the Europe ROM itself.

The iNES header of the Europe ROM: NES 2.0, mapper 1 (MMC1), 16 PRG banks (256 KB), no CHR (CHR RAM), PAL timing, horizontal-mirroring flag set (the disassembly's header says vertical; MMC1 sets mirroring at run time, so which one the game uses is [to check]).

## 4. The disassembly

- Build: `make` in the root needs `cc65` (`ca65`, `ld65`); it writes `build/faxanadu.nes`. The file `src/HEADER.asm` is named in capitals because `faxanadu.asm` includes it that way (a lower-case name broke the build on Linux).
- Banks (`DEFS.asm`): 0-2 area data (maps), 3 area metadata, 5 audio logic, 6-8 sprites, 9 unused, 10 CHR RAM (tile data), 11 sprite info and palettes, 12 logic, 13 strings, 14 logic, 15 the fixed bank at `$C000`, the biggest (about 30,000 lines).
- Areas (chipx86's notes, "Levels"): Eolis, Forepaw, Mascon in bank 0; Apolune, Conflate in bank 1; Daybreak, Victim, Evil Fortress in bank 2. The current screen's block data is at `$0600-$06FF`. Blocks have 16 kinds (air, solid, ladder, door, transition up/down/left/right ...). Block data is compressed [format to read in the disassembly].
- Notes by chipx86: <https://notes.chipx86.com/Projects/Reverse-Engineering+Projects/Faxanadu+Disassembly/-Overview-> (Levels, Sprites, Palettes, Music Scripts, Interaction Scripts, Passwords, Strings, Memory). Tools: <https://github.com/chipx86/faxanatools/>, level editor and format doc <https://github.com/kaimitai/faxedit/>, interaction script tools <https://github.com/kaimitai/FaxIScripts>. Not all of these could be fetched from the cloud session; ask Göran to attach what is needed.

## 5. Facts read from the disassembly (US)

- **Scrolling is between screens** [verified in the ROM, `tools/refnes/scroll_probe.mjs`]. In normal play the camera is still. Leaving a screen costs 14 frames of preparation and then exactly 64 frames of 4 pixels (`Game_MainLoop` runs `Screen_HandleScroll` four times a frame, one pixel each), 256 pixels in all, with nothing else going on. The Europe ROM and the US build do the same. Vertical scrolls wrap at `$D0` = 208 lines (read in the code, not yet measured). `Screen_HandleScroll` has two more callers that are not read yet.
- **The picture is a 32-line HUD on top of a 256x208 playfield** (NES screen 256x240) [verified in a jsnes screenshot; the HUD is split from the playfield with a sprite-0 hit]. 208 lines do not fit 200, and the HUD would come on top: the main design question for the display (see `PLAN.md`, step 4).
- The hero starts on a first screen with no neighbouring screens (`Area_ScreenToTheLeft/Right/Above/Below` all `$FF`); the castle door at x 192 (Up) leads to Eolis, screen 1, which has screens on both sides. Eolis is area 0.
- Interaction scripts: a script language runs all NPC and item interactions (`IScripts_*`, `IScriptAction_*`). The port should run the ROM's own scripts through a small interpreter, not hand-code each dialogue.
- Passwords: `IScriptAction_ShowPassword`; the format is in chipx86's notes.

## 6. Tools and layout

```
../src/*.asm            the US disassembly (spec)
../ext/                 your ROM (gitignored)
Makefile, link.ld       build: as -> ld -> objcopy -> PRG; `make check`, `make disk`
src/main.s              the start-up check (will become the game)
tools/make_prg.py       the .PRG header (a flat image, no relocation: PC-relative code only)
tools/make_disk.py      a 720 KB .st image for the Gotek
tools/check_reach.py    the 16-bit reach check
tools/hatari_shot.py    runs a PRG headless in Hatari and renders the screen to a PNG; prints a frame hash
tools/rom_diff.py       Europe ROM against the US build, counts only
tools/ram_labels.py     the disassembly's RAM labels as JSON (names and addresses only)
tools/refnes/           the jsnes ROM harness: read RAM by label, press buttons, take pictures, probes (see its README)
tests/                  unit tests; test_start.py runs main.s on machine68k with GEMDOS stubs
build/                  output (gitignored)
```

ROM harness: `cd tools/refnes && npm install`, `python3 tools/ram_labels.py`, then `node scroll_probe.mjs RIGHT`. The labels were checked against the running ROM: player position and screen, area, scroll direction, scroll X and the neighbour screens all read right. In the Europe ROM the bank-call variables in zero page sit four bytes higher than in the disassembly (`BankedCallSetup_Saved*`); nothing else in zero page or RAM was seen to differ.

Toolchain: `binutils-m68k-linux-gnu` (`m68k-linux-gnu-as -m68000`), `cc65`, Hatari (2.4 and up), `pip install machine68k`, Python 3. A TOS image is needed for Hatari: EmuTOS 512k works (`--tos etos512us.img`, or the `TOS` environment variable). **Never commit a TOS image.**

Run: `make`, `make check`, `python3 tools/hatari_shot.py --tos etos512us.img` (captures at VBL 600; TOS takes about 300 to boot). Hatari is run with `--memsize 0` = 512 KB, like Göran's 520 STFM.

## 7. 68000 and GNU as pitfalls (from the Zelda port)

- A `bsr`/`bra`/`Bcc` or `(label,pc)` that does not reach wraps silently: `check_reach.py`.
- `(label,pc)` cannot be a destination: load the address with `lea label(%pc),%aN` and store through it.
- Odd addresses fault on word and long accesses.
- A routine that clobbers `a0`/`a1` inside the caller's loop: save what the callee uses.
- Hardware registers and `$0-$7FF` need supervisor mode (`Super(0)`); restore everything TOS had (palette, video base, the keyboard vector) before `Pterm0`.
- `|` starts a comment in GNU as for m68k. Register names are `%d0`, `%a0`.
- More in the Zelda port's `AGENTS.md`; copy what applies.

## 8. Deliberate differences from the ROM

None yet.
