# AGENTS.md - the briefing for anyone working on the port

Read this before researching anything. When you learn something durable, add it here. `CLAUDE.md` in the repository root only points here.

## 1. What this is

A native **Atari ST (520 STFM, 512 KB, 68000, PAL 50 Hz)** port of **Faxanadu (NES)**, in 68000 assembly (GNU as syntax) with a Python asset pipeline that reads graphics, maps, palettes, text and music from **a ROM you supply** (`ext/Faxanadu_Europe.nes`, gitignored, never committed). The result is a stock TOS `.PRG`: 320x200, 16 colours, YM2149 sound.

It follows the Zelda 1 port (`georgeflower/zelda1-atarist`): same method, same tools, same rules.

The rest of the repository is chipx86's labelled disassembly of the **US** version (`src/*.asm`, builds with `make` in the root). It is the **spec for every behaviour**: when you need a number (speed, timer, damage, tile id, table), read it there, never guess.

Status: set-up, the ROM harness and the map data decoder. `src/main.s` is a start-up check that shows 16 colour bars. What comes next is in `PLAN.md`.

## 2. Rules

1. **The ROM is the reference for behaviour.** Read values from the disassembly, then check them in the ROM. The port "improving" on the ROM is a bug report later; match first, change only when asked, and write deliberate differences down here.
2. **All game data comes from the user's ROM.** Nothing from the ROM (images, tables, music) is committed. Tests keep sizes and hashes. If the ROM is missing the build stops; no stand-in art.
3. **Build and test headlessly, always.** Assemble, run in Hatari, compare frames with golden hashes, run the unit tests. A disk image the user has not seen built and run is not delivered.
4. **The 16-bit branch limit wraps silently** in GNU as and ld. `tools/check_reach.py` runs on every link; do not disable it.
5. **Budget first.** An STFM has no blitter and no hardware scroll; a frame is about 160,000 cycles at 50 Hz. Estimate the cycles of anything per-frame before writing it and measure afterwards.
6. **No version numbers** anywhere (no VERSION, no CHANGELOG, no version line in docs). Göran tags releases himself.
7. **Commit straight to `main` and push; no pull requests** (Göran's decision, Nov 2026; stacked pull requests had merged into their base branches and never reached `main`). Run `make check` first. Disk images used to be named `F-PR##.st` after the pull request; without pull requests the naming needs a new rule (ask Göran when the first image is delivered). Commits end with the `Co-Authored-By` line and no session link.
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

## 5b. The map data, decoded [verified: pixel-exact against jsnes on two Eolis screens]

`tools/faxanadu_rom.py` finds tables by the disassembly's label names (names, addresses and file offsets only are cached, never ROM data) and reads the bytes from your ROM; `tools/faxanadu_maps.py` decodes areas and screens; `tools/render_screen.py` draws a screen from them with no emulator. `tools/refnes/refshot.mjs` makes the reference picture (and the sprites on it) from the harness.

- There are **8 areas** with 272 screens: 9, 64, 83, 14, 10, 40, 32 and 20. Their tilesets are 0 Eolis, 2 Trunk, 3 Mist, 5 Towns, 6 King's room/guru/hospital (buildings), 1 Branch, 4 Dartmoor and 4 again for the last area (the names of the areas themselves are not read yet).
- A screen is **16x13 blocks of 16x16 pixels**. Its block ids are compressed: two control bits per block, most significant first: 0 copy the block to the left, 1 the one above, 2 the one above and to the left, 3 read the next 8 bits. Offsets wrap in a 256-byte buffer; the last three rows are zeros (`Area_LoadBlocks`).
- An area's tables are in bank 3 (`AREAS_TABLE_PTR` then per area: five pointers to the block attributes and four block lists, block properties, scrolling data, door locations, door destinations). The block data is in banks 0-2 (`AREA_TO_SCREEN_DATA_BANKS`, `AREA_TO_BANK_OFFSET`). Pointers in a bank are the CPU address minus `$8000`.
- A block is four tiles (lists 1 to 4: top left, top right, bottom left, bottom right) and one attribute byte holding a palette number for each corner of a 2x2 group of blocks; the block's own corner is picked by the parity of its column and row.
- The tileset of an area is plain NES 2-bit tiles in bank 4 (`TILE_INDEX_TO_ADDR`, 4 to 8 pages of 256 bytes; all nine tilesets are 16 KB) loaded at `$1800`, which is tile `$80` of the background pattern table at `$1000`. Buildings load theirs at `$1A00`. Tile 0 is blank.
- Background palettes: `PALETTE_TILES_*` in bank 11, 16 bytes (four palettes of four NES colours); the area's default is `AREA_PALETTE_INDEXES`. Whether single screens use another one is [to check]. The harness' colour table is in `tools/nes_palette.py`.
- The jsnes picture differs from the data in three places that are not data: sprites (the hero and NPCs), the outer 8 pixels on each side, and the last 8 lines of the playfield (jsnes shows the NTSC window and blanks them; on a PAL TV they are visible). `render_screen.compare` leaves these out.
- **Screen neighbours** [verified against the game's RAM]: four bytes a screen in the area's scrolling data: left, right, above, below, `$FF` for none (`Area_LoadScrollData`). Seven of the links are one-way (area 1 screen 27, area 2 screen 38, area 7 screens 1, 12, 17); all others are mirrored.
- **Block properties** [verified against the game's RAM]: 256 bytes a area (one per block id, value 0-15; the game packs them two to a byte). Eolis uses 0, 1, 3 and 4. From chipx86's notes (not checked here): 0 air, 1 solid, 2 ladder, 3 door, 10-13 the screen transitions (up, down, left, right).
- **Doors**: records of four bytes ended by `$FF` in the area's door locations: screen, block position (row*16+column), destination index, start position (high nibble Y/16, low nibble X/16: where the hero stands on arrival). The destination (four bytes at index*4 in the door destinations; area 3 is 32 too high): new screen, palette, key requirement, and a byte not read yet. Verified for the castle door of Eolis (screen 0, block 156 -> screen 1, hero at 144,144); indices of 32 and up (doors into buildings) are decoded the same way but not checked. A new screen's **palette** comes from the door; scrolling between screens keeps it.
- **HUD and letter tiles**: 60 tiles at `HUD_TILES_START` in bank 10 are written to the background pattern table's first 60 tiles. They equal the game's CHR RAM except tiles 12 and 13, the bar tiles, which the game draws into CHR RAM as the bars fill.
- Still to find: the HUD's layout and palette, the sprite tiles (banks 6-8, with the sprite info and palettes in bank 11) and the per-screen sprite placements, what the other property values mean, doors into buildings, text (banks 12 and 13 differ in Europe).

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
tools/faxanadu_rom.py   tables by label name from your ROM (labels cached, no ROM data)
tools/faxanadu_maps.py  areas, screens, blocks, neighbours, block properties, doors from the ROM
tools/faxanadu_gfx.py   the HUD and letter tiles
tools/render_screen.py  draw a screen from the ROM's data; compare with a jsnes picture
tools/nes_palette.py    the 64 NES colours as jsnes shows them
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

## 7b. Display decision (Göran, Nov 2026)

The whole NES picture on screen: **240 lines, HUD on top**, by opening the ST's borders (overscan), not by cropping. On a PAL STF/STFM the top and bottom borders give about 270 lines, so 240 fit. Opening them is cheap for the CPU (a few timed writes per frame, from timer interrupts). **Opening the left and right borders too** (lines about 416 pixels / 230 bytes wide) costs timed writes on every scanline and 230-byte lines (240 lines = 55 KB a screen), which eats much of the frame budget; Göran wants the sides filled as well, so it stays a goal, to be measured after top and bottom work. What would fill the side areas is not decided. A 320-wide screen is the safe base; overscan must be tried on the real 520 STFM and on Hatari's cycle-exact mode (`--trace video_border_v,video_border_h` logs when a border is opened).

## 8. Deliberate differences from the ROM

None yet.
