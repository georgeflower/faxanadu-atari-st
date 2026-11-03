# Plan

The order follows the Zelda port. Each step is a pull request (or a few) that builds, is tested in Hatari and gets a disk image `F-PR##.st`.

## Done

- [x] 1. Set-up: `atari_st/` with the build, the tools, a start-up check that runs in Hatari on a 512 KB machine, tests, this briefing.
- [x] 2. ROM harness: jsnes plays the Europe ROM from RAM labels; scroll measured (64 frames of 4 px); labels checked.

## Next

3. **Read the data.** Pull out of the ROM, by searching (not by US offsets): the CHR RAM tiles (bank 10: find the upload routines, run them in the harness), sprite tiles (banks 6-8), palettes (bank 11 and the per-area ones), the area maps (banks 0-3, compressed: write the decoder in Python first). Render a screen to a PNG and compare it with a jsnes screenshot of the same place.
4. **Decide the display and the scroll, then measure.** This is the main risk. Open questions to answer by reading first:
   - The playfield is 256x208 under a 32-line HUD (seen in a screenshot). 208 lines do not fit 200 with a HUD on top. Options: crop, a HUD at the sides (the screen has 64 spare pixels across), a smaller window, or overscan (top and bottom border, timing-critical, a real-hardware project of its own). Look at real screens and decide with Göran.
   - Scroll between screens: 256 px in 64 frames at 4 px a frame (measured), nothing else runs. Cheap candidates: 16-pixel steps every four frames from a pre-composed wider buffer, and the ST's 8-line vertical steps through the video base for up and down.
   - What the hero does during a scroll (`Game_UpdatePlayerOnScroll`), and the two other `Screen_HandleScroll` callers.
   - Colour: how many colours one screen needs against 16 (the Zelda shared-palette technique, with swaps per area).
   - Data volume: size of all graphics and maps after conversion decides resident data against one file per area.
   Prototype one scrolling area on the 520 STFM with an empty hero, measure late frames, then choose.
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
- Data volume: eight areas and a lot of text.
- The script interpreter: all NPC behaviour depends on it being exact.
- Bank 5 (music) and bank 12 (texts) differ between the US and Europe ROMs: the disassembly does not describe those bytes exactly.
