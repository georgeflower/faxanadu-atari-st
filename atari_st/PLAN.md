# Plan

The order follows the Zelda port. Each step is one or a few commits straight to `main` that build and are tested (in Hatari once there is something to see) and, when worth playing, get a disk image. The ROM harness (jsnes) is the reference: every behaviour is first written down from the disassembly, then compared with the harness, then built on the ST.

## Done

- [x] 1. Set-up: `atari_st/` with the build, the tools, a start-up check that runs in Hatari on a 512 KB machine, tests, this briefing.
- [x] 2. ROM harness: jsnes plays the Europe ROM from RAM labels; scroll measured (64 frames of 4 px); labels checked.
- [x] 3a. Map data: areas, screens, blocks, tilesets and palettes read from the ROM; a screen drawn from them equals jsnes, pixel for pixel.
- [x] 3a'. Block properties, screen neighbours, doors and the HUD and letter tiles, checked against the game's RAM.
- [x] 4a. A screen on the ST: playfield, HUD (as at the start of a game) and the hero, pixel-exact in Hatari (`make viewer`). 16 colours are enough for all 28 palette sets.
- [x] 3b-hero. The hero's tiles, frames, offsets and colours decoded and checked against jsnes (`tools/faxanadu_sprites.py`).

## Order of work

The numbers are the order I intend to work in. A step is done when its tests pass and `AGENTS.md` says what was learned. **Unattended** means it can be done without Göran: the harness gives the answer. **Needs Göran** means a real machine, a choice or a file.

### A. Frame loop and the HUD (next)

- A1. **HUD that updates** (DONE, `src/hud.s`): HP, MP, experience, gold, time and the item box drawn from a state block by a routine, not from a fixed picture. The bars' partial tiles (8 values each, the magic bar with its halves swapped) come from the ROM. Test: Hatari picture equals `st_convert.hud_pixels` for several states (the five states of `hudshot.mjs`).
- A2. **The frame loop** (DONE for the VBL counter and the input, `src/frame.s`; the screen buffer scheme is decided in A3 after measuring): VBL interrupt (50 Hz), one game tick per VBL, a double screen buffer or a drawn-under-the-beam scheme (decide after measuring), joystick and keyboard read through the IKBD (joystick port 1 as the NES pad; keyboard keys as an option), a frame counter. Test in Hatari with injected key events; measure cycles per frame with Hatari's profiler or a timer-B border colour.
- A3. **Sprite engine** (STARTED: double buffer, erase from the clean copy, hero poses, fast one-group blit, measured; HUD on both screens done; open: composed poses, many sprites with priority and limits, behind-background): draw and erase sprites over a still background (save-under or redraw of the touched blocks), the hero composed once per pose and shifted (see `AGENTS.md` 5e for the budget), a sprite list with the NES's priority rules and the per-frame limits the game has (`Sprites_SlotsFull`), "behind the background" for the hero. Measure: hero + 8 sprites inside 60,000 cycles.

### B. Moving between screens (the display risk)

- B1. **Horizontal scroll between screens** (DONE, 16 px every 4 frames, tested in Hatari; still **needs Göran** to judge on the real machine; original text: **needs Göran** to judge on the real machine): 64 frames of 4 px = 16 px every 4 frames. Pre-compose the neighbour screen into a wider buffer and move the picture 16 px at a time with word-aligned copies; nothing else runs during the scroll (checked in the harness). Measure the copy cost (about 168 lines x 256 px x 4 planes = 21 KB a step, a few hundred thousand cycles if done naively: this is the main budget problem; options are a 4-step cache, or scrolling by redrawing only the new column of blocks and moving the rest with `movem`).
- B2. **Vertical scroll** (DONE, tested in Hatari for up and down; needs Göran's eyes): the two playfields lie one after the other in memory and the window is copied from a moving line of them, 16 lines every 4 frames (the ROM moves 208 lines at 4 a frame, the window is only 168 high, so the ST scrolls about 168). The camera follows the hero between scrolls in two positions (0 and 40) with hysteresis; a change redraws both screens (six frames of standing still). Open: the 14 waiting frames show a still hero, a smoother camera.
- B3. **Screen setup** [DONE: doors in the area and to other palette sets, buildings, out to other areas, edges between areas, keys (a fixed set until there is an inventory), music per package; the scroll callers are covered by the scroll tests] (decided by Göran, 6 Nov 2026: option 1, one area is loaded at a time, at the doors, with a pause at every area change): loading a screen from the area data on entry (block ids, tiles, palette from the door, neighbours), area changes, the other two `Screen_HandleScroll` callers, `Game_UpdatePlayerOnScroll`. Compare the first frame after every kind of move with jsnes.
- B4. **Palette per screen** [one palette per package, set from the door, DONE; enemy colours with D]: one 16-colour palette per palette set, set from the door's palette index; sprite palettes loaded on top by `Screen_LoadSpritePalette` (enemy colours) counted into the 16.

### C. The hero plays

- C1. **Input and walking** (DONE: acceleration by rank, wall stops, the neighbour screen's edge column, matched to the ROM frame by frame; the game has no crouch).
- C2. **Collision with blocks**: block properties (0 air, 1 solid, 2 ladder, 3 door, 4/9/13 pass-behind, 10-13 screen transitions, the rest to read), the hero's 16x32 box, ledges.
- C3. **Jump and fall**: done. The arc, the fall, landing and ceilings match the harness frame by frame; the in-air pose and the screen change in the air too.
- C4. **Ladders and wing boots**: done (model, golden runs, viewer tests); the game has no stairs.
- C5. **Attack and damage** (the swing with its three poses and the arm piece, being hit, knock-back, invincibility and the death animation are done, with debug keys until there are enemies; the weapon's place and reach are computed for the enemy code; the death sound, song, gold and experience reset are done; magic is done (the five spells fly, stop on walls and are drawn, with the M key to choose one until there is an inventory); open: what enemies do to a spell (D), the death message box and the temple spawn point, which need the text engine and buildings of E).
- Each of C1-C5 gets a "golden run": a recorded button sequence from the harness and the hero's x, y and frame per tick; the ST code (run under Hatari or an emulator in the tests) must reproduce it.

### D. Enemies, items, bosses

- D1. **Sprite data** (done for Zozura, Monodron, Snowman, Zombie, Ikeda, Myconid, Yuinaru, Hornet, Charron (with its fireball), Raiden, Grimlock, Lamprey, Giant Strider, Maskman and Geributa, the same path for the rest: add the kind to `enemy_data.py`): all enemy and NPC tiles, frames and palettes (banks 6-8, 11), converted as for the hero; per-screen sprite placements; the sprite entity tables (`SPRITE_ENTITY_*`: hit points, damage, drop values, ranges).
- D2. **Enemy behaviours** (done: Zozura, Monodron, Snowman, Zombie, Ikeda, Myconid, the death effect, drops, experience, touch damage; next the other Trunk kinds; about 60 kinds, `SpriteBehavior`): group them by movement pattern; one at a time, each with a golden scene from the harness. Spawning, respawn rules, drops, experience and gold.
- D3. **Items and magic**: pickups, the inventory, equipment changes (re-load the hero's tiles), magic spells and their sprites, keys and doors that need them.
- D4. **Bosses**: one each, after the normal enemies; their rooms and music cues.

### E. Towns, buildings, text

- E1. **Doors into buildings** and the building screens (tileset 6, palettes), moving in and out, the hero's start position.
- E2. **Text and the font**: banks 12 and 13 of the **Europe** ROM (they differ from the US). The font, the messages and a box of text are done (`src/text.s`, the death message uses them); to do: the portrait pictures (`TILEINFO_PORTRAITS_ADDRS`), a box that waits for a button every four lines, the $FB rank code.
- E3. **Interaction scripts**: a small interpreter for the ROM's script language (`IScripts_*`, `IScriptAction_*`) and the scripts read from the Europe ROM; shops, guru, the King, the hospital, the key sellers.
- E4. **Passwords**: the ROM's format, the coder, the entry screen and the start menu are done (the P key shows the mantra until the Gurus of E3 do it with `IScriptAction_ShowPassword`; the temple spawn point and the inventory go into it when they exist). To do: a save file as a convenience (floppy or the Gotek image).

### F. The rest of the game

- F1. **Title screen, start screen, intro, ending, credits** (bank 12 differs in Europe: the start screen's code).
- F2. **Music and sound** (DONE, see `AGENTS.md` 5f; needs Göran's ears on the real machine): the ROM's own engine plays every song and effect in jsnes, the channels are recorded and converted to YM2149 frames, a player runs from the VBL. Open: the song of each area and event, priorities between sound effects, duty cycle.
- F3. **Game flow**: death, continue, the time counter, area transitions that change music and palette, the final boss.

### G. Making it a product

- G1. **Memory map**: all areas, tiles, sprite images, music and text must fit 512 KB with the program, two screens and the buffers. Estimate now, verify at each step. Decided (Göran, 6 Nov 2026): one area is in memory at a time and the next is loaded from disk at the door, with a pause at every area change (that includes the area's song, 15 KB at most; all songs together are 150 KB, too much to keep).
- G2. **Disk layout**, the final image, naming of images (a rule for no-PR numbering is still to be agreed with Göran), loading screen, a README for the disk.
- G3. **Real hardware checks** after each of A, B, C: Göran runs the image on the 520 STFM and reports (speed, flicker, tearing, colours, sound). These are the real acceptance tests; Hatari timing is not exact.
- G4. **Polish**: ST-specific options (joystick or keyboard, colour palette tweak, speed option) written in `AGENTS.md` section 8 as deliberate differences.

## Cross-cutting work

- **Cycle budget** (rule 5): one table in `AGENTS.md` with the measured cost of each per-frame routine; a frame is about 160,000 cycles at 50 Hz and the scroll and the sprites are the two big spenders.
- **Tests**: golden pictures (frame hashes) per screen and state, golden runs per behaviour, unit tests for decoders; `make check` runs all of it in a few minutes. Needs `TOS` (an EmuTOS image) and the ROM.
- **Harness gaps**: climbing, a screen with a ladder, an enemy of each kind, a shop, the title screen; each needs a short "how to get there" script in `tools/refnes/`.
- **Europe versus US**: whenever a table from banks 5, 12 or 13 is used, read it from the Europe ROM, not from the US offsets.
- **Disk images**: only built and run images are delivered; names to be decided with Göran.

## Known risks

- Scrolling and the display size (step B): the biggest.
- Sprite cost on a machine with no blitter (A3).
- Colour: Faxanadu's per-area palettes against 16 colours, and enemy sprite palettes on top (B4).
- Data volume: 272 screens in eight areas and a lot of text. The maps are about 54 KB in the ROM's compressed form (about 200 bytes a screen; the biggest area, Mist, 17 KB); all tilesets together are 16 KB. Small enough to keep a whole area in memory, but sprite images (several variants each) and music add up: see G1.
- The script interpreter (E3): all NPC behaviour depends on it being exact.
- Bank 5 (music) and bank 12 (texts) differ between the US and Europe ROMs: the disassembly does not describe those bytes exactly.
- Only Göran can run the real machine: plan G3 checks so each one is a short, specific question.
