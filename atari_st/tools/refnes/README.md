# refnes: ROM reference harness

Headless NES emulation (jsnes) that plays the original ROM, to find out what the real game does and to compare it with the port.
Needs Node, `npm install` in this folder, the ROM in `ext/Faxanadu_Europe.nes` (never committed) and the RAM labels:

    python3 ../ram_labels.py        # writes atari_st/build/refnes/ram_labels.json from the disassembly (needs cc65)

`faxanadu.mjs` is the harness: `new Faxanadu()`, `rd`/`wr` by address or by the disassembly's label (`g.rd("Player_PosX_Block")`),
`run(n)` frames, `hold`/`tap` buttons, `ppm(file)` for a picture, `newGame()` (in play on the first screen) and `newTown()` (through
the castle door into Eolis, which has screens to both sides). `ROM=../../../build/faxanadu.nes` runs the US build instead.

jsnes runs NTSC timing. The game's logic runs once per NMI, so a jsnes frame is one game tick in either region.

- `scroll_probe.mjs [RIGHT|LEFT|UP|DOWN] [frames]`: puts the hero at the screen's edge and records the scroll frame by frame.
  Result for RIGHT, Europe and US alike: 14 frames of preparation, then exactly 64 frames of 4 pixels (256 pixels). LEFT is the same
  with a short start.

- `npcprobe.mjs SPEC.json OUT.json`: the town people frame by frame: the hero in a street or a building (through its door), his x written from a schedule, and every frame
  the eight sprite slots, the sprites on show and the counters. `tests/test_npc.py` writes the specs and compares `tools/npc_model.py` (`NPC_CACHE=dir` keeps the runs while working on it).

## Notes on getting into the game

- Start at the title, wait about 360 frames, press Start; the hero stands on the first screen and is in play at once.
- The first screen has no neighbouring screens. Walking right, a text box ("I've been on a long journey.") appears and waits for A.
  The castle door (stand at x 192 and press Up) leads on to screen 1 of Eolis.
- A is jump, so tapping A to get past text also makes the hero jump.
- `Screen_ScrollDirection` is `$FF` when nothing scrolls; the main loop waits for the next frame at `$CA28`/`$CA2A`.
- `soundrec.mjs music|sfx ID FRAMES OUT.json`: records what the ROM's sound engine does to the NES sound channels, frame by frame, for one song or sound effect (`tools/record_sounds.py` runs it for all of them; `tools/build_sound.py` converts them for the ST).
- `magickill.mjs SPELL OUT.json`, `tiltehit.mjs MODE OUT.json`: a kill by a spell (entity $14, its five pieces) and Tilte's hit and miss (the explosion), frame by frame.
- `soundpair.mjs single|pairs OUT FRAMES ...`: two sound effects asked for one after the other (effect A, D frames later effect B): the engine's handler index and the channels after every frame (priorities, `tests/test_sound.py`).
- `musicprobe.mjs door AREA REGION SCREEN BLOCK [KEY [D]]` and `start`: `Music_Current`, `Areas_DefaultMusic` and `Area_Music_Outside` while a door is taken, and the Start press on the title with what the channels sound (`tests/test_music.py`).
- `respawnprobe.mjs [SCREEN]`: Eolis, kills and hurts the enemies of a screen, goes to the next one and back, and prints what the slots hold each time (the whole list is loaded again).
- `visitprobe.mjs [ENTRIES] [ENTITY]`: Trunk screen 14, enters it again and again and prints `Screen_TrackedVisitCount` and whether the random item is there (every 4th time).
- `behindprobe.mjs [SCREEN] [OUT.json]`: Eolis screen 4, walks left through the pillar and back and records the hero's and the enemies' slots and the OAM sprites with their attributes (bit 5: behind the background).
- `mattockspell.mjs AREA SCREEN X Y RIGHT SPELL DELAY`: Trunk screen 12 with the Mattock in hand: Up and B cast a spell, DELAY frames later Down and B use the Mattock; prints the spell's state, its sprites in jsnes' OAM and the item frame by frame (the ROM takes the Mattock with the spell in flight, the spell stands still and its sprites are off the screen from the message to the end of the crumble; `ITEM=255` runs it without the Mattock).
