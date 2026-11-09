// Which song the ROM plays when: the music state (Music_Current, Areas_DefaultMusic = D, Area_Music_Outside = O) frame by frame while a situation is played through.
//   node musicprobe.mjs door AREA REGION SCREEN BLOCK [KEY [D]]   stand at a door of the screen (block = row * 16 + column), press Up, go through it. KEY: the key the door
//     needs (its requirement number, 1-5; the rings are all on), D: the song the area has been playing (Areas_DefaultMusic) when he gets there
//   node musicprobe.mjs start     the title, then Start: per frame from the press, Music_Current and what the four channels sound (the Start blip: song 8 for a few frames)
// Prints one line each time one of the three changes, and a RESULT line with the same as JSON: [[frame, Music_Current, D, O], ...] (frames from the press).
import {Faxanadu, newOutside, BTN} from "./faxanadu.mjs";

const [kind, ...args] = process.argv.slice(2);
const log = [];
const state = (g) => [g.rd("Music_Current"), g.rd("Areas_DefaultMusic"), g.rd("Area_Music_Outside")];
let g, t0, last = null;
const watch = () => { const s = state(g); if (!last || s.some((v, i) => v !== last[i])) { log.push([g.frames - t0, ...s]); last = s; } };
if (kind === "door") {
  const [area, region, screen, block, key = 0, preD = 0] = args.map(Number);
  const x = (block & 15) * 16, y = (block >> 4) * 16;
  g = newOutside(area, region, screen, x < 100 ? x + 80 : x - 40, 144);
  g.wr("SpecialItems", 0xf0);
  if (key) g.wr("SelectedItem", key + 3);
  if (preD) { g.wr("Areas_DefaultMusic", preD); g.wr("Music_Current", preD | 0x80); g.run(2); }
  t0 = g.frames; watch();
  g.nes.buttonDown(1, BTN.UP);
  const a0 = g.rd("Area_CurrentArea"), pal0 = g.rd("Screen_PaletteIndex"), s0 = g.rd("Area_CurrentScreen");
  for (let f = 0; f < 300; f++) {
    if (f < 120 && g.rd("Area_CurrentScreen") === screen) { g.wr("Player_PosX_Block", x); g.wr("Player_PosY", y); }
    g.run(1); watch();
  }
  g.nes.buttonUp(1, BTN.UP);
  console.log(`from area ${a0} palette ${pal0} screen ${s0} to area ${g.rd("Area_CurrentArea")} palette ${g.rd("Screen_PaletteIndex")} screen ${g.rd("Area_CurrentScreen")}`);
}
if (kind === "start") {
  g = new Faxanadu();
  g.run(360);
  // what the sound chip is sounding: [square 1 period, volume], [square 2 ...], triangle on or off, noise volume
  const sq = (c) => (c.isEnabled && (c.lengthCounter > 0 || !c.lengthCounterEnable) && c.progTimerMax >= 8 ? [c.progTimerMax, c.masterVolume] : [0, 0]);
  const chan = () => { const p = g.nes.papu, t = p.triangle; return [sq(p.square1), sq(p.square2), t.isEnabled && (t.lengthCounter > 0 || !t.lengthCounterEnable) && t.linearCounter > 0 ? 1 : 0, p.noise.masterVolume]; };
  g.nes.buttonDown(1, BTN.START);
  const rows = [];
  for (let i = 0; i < 16; i++) { g.run(1); if (i === 2) g.nes.buttonUp(1, BTN.START); rows.push([i, g.rd("Music_Current"), chan()]); }
  for (const [i, m, c] of rows) console.log(`  f${i}: Music_Current=${m.toString(16)} ${JSON.stringify(c)}`);
  console.log("RESULT " + JSON.stringify(rows));
  process.exit(0);
}
for (const [f, m, d, o] of log) console.log(`  f${f}: Music_Current=${m.toString(16)} D=${d.toString(16)} O=${o.toString(16)}`);
console.log("RESULT " + JSON.stringify(log));
