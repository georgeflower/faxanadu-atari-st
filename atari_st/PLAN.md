# Plan

The order follows the Zelda port. Each step is one or a few commits straight to `main` that build and are tested (in Hatari once there is something to see) and, when worth playing, get a disk image.

## Done

- [x] 1. Set-up: `atari_st/` with the build, the tools, a start-up check that runs in Hatari on a 512 KB machine, tests, this briefing.
- [x] 2. ROM harness: jsnes plays the Europe ROM from RAM labels; scroll measured (64 frames of 4 px); labels checked.

- [x] 3a. The map data: areas, screens, blocks, tilesets and palettes read from the ROM; a screen drawn from them equals jsnes, pixel for pixel.

- [x] 3a'. Block properties, screen neighbours, doors and the HUD and letter tiles, checked against the game's RAM.

## Next

3b. **The rest of the data.** The HUD layout, the sprite tiles and their info and palettes (banks 6-8, 11) and per-screen sprite placements, doors into buildings, text (banks 12 and 13 differ in Europe: read the Europe ROM). Then convert tiles, blocks and maps to ST planar form and map the NES colours to 16 (see the Zelda port).
4. **Display and scroll.** Decided: 240 lines with the HUD on top by overscan (see `AGENTS.md`). In order:
   - 4a. A 240-line screen of 320 pixels on a PAL STFM. Bottom border: works in Hatari (`src/overscan_test.s`, one removal every frame). To do: try it on the real 520 STFM (Göran), then show a screen of the game on it.
   - 4b. Scroll between screens (256 px in 64 frames at 4 px, measured; nothing else runs): measure a 16-pixel step every four frames from a pre-composed wider buffer, the 8-line vertical steps through the video base, and what the hero does during it (`Game_UpdatePlayerOnScroll`, and the two other `Screen_HandleScroll` callers).
   - 4c. Left and right borders (about 416 pixels wide): try it and measure what it costs per frame; decide what fills the sides.
   - Colour: how many colours one screen needs against 16 (the Zelda shared-palette technique, with swaps per area). Data volume: tilesets 16 KB and maps about 54 KB, so a whole area fits.
5. **Hero, collision, physics**, matched against the disassembly with harness comparisons (jump arc, speeds, ladders, stairs).
6. **Enemies and bosses**, in groups by area, each with a golden scene.
7. **Towns, buildings, shops, NPCs**: a small interpreter for the ROM's interaction scripts, and the scripts themselves read from the ROM.
8. **HUD, items, magic, inventory.**
9. **Title, start screen, intro, ending.**
10. **Music and sound** from the ROM's own sound engine (bank 5; the Europe bank differs, so rip from the Europe ROM). Independent of the rest; can start any time after 3.
11. **Password** (the ROM's format) and a save file as a convenience.
12. **Disk layout**, the final image, checks on the real 520 STFM after each step.

## Known risks

- Scrolling and the display size (step 4).
- Colour: Faxanadu's per-area palettes against 16 colours.
- Data volume: 272 screens in eight areas and a lot of text. The maps are about 54 KB in the ROM's compressed form (about 200 bytes a screen; the biggest area, Mist, 17 KB); all tilesets together are 16 KB. Small enough to keep a whole area in memory.
- The script interpreter: all NPC behaviour depends on it being exact.
- Bank 5 (music) and bank 12 (texts) differ between the US and Europe ROMs: the disassembly does not describe those bytes exactly.
