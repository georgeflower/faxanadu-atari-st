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

## Notes on getting into the game

- Start at the title, wait about 360 frames, press Start; the hero stands on the first screen and is in play at once.
- The first screen has no neighbouring screens. Walking right, a text box ("I've been on a long journey.") appears and waits for A.
  The castle door (stand at x 192 and press Up) leads on to screen 1 of Eolis.
- A is jump, so tapping A to get past text also makes the hero jump.
- `Screen_ScrollDirection` is `$FF` when nothing scrolls; the main loop waits for the next frame at `$CA28`/`$CA2A`.
