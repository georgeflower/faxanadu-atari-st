// What the ROM shows on the title screen, in the intro and in the ending, recorded in jsnes for tests/test_splash.py.
//
//   node splashgolden.mjs OUT.json
//
// title:  the picture (256x240 RGB, base64), the name table, the pattern tables, the palette, the sprites with the cursor on START and on CONTINUE.
// intro:  from Start on the title to the first frame of play: the sprites of every frame, the palette whenever it changes, the picture, name table and
//         pattern tables at one frame, the hero's place when play starts.
// outro:  RunOutro called from the title (Game_Init follows it in the game): the sprites and the interrupt counter of every frame, palette changes,
//         pictures, name table and pattern tables at one frame.
// A record i is the state before the i-th frame is run (the OAM is what the PPU got at the last NMI).
import {Faxanadu, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2];
if (!out) throw new Error("usage: node splashgolden.mjs OUT.json");
const hex = (a) => Buffer.from(a).toString("hex");
const grab = (g) => {
  const v = g.nes.ppu.vramMem, buf = Buffer.alloc(256 * 240 * 3);
  for (let i = 0; i < 256 * 240; i++) {
    const p = g.pixels[i];
    buf[i * 3] = p & 0xff; buf[i * 3 + 1] = (p >> 8) & 0xff; buf[i * 3 + 2] = (p >> 16) & 0xff;
  }
  return {rgb: buf.toString("base64")};
};
const vram = (g) => {
  const v = g.nes.ppu.vramMem;
  return {chr: hex(v.slice(0, 0x2000)), nametable: hex(v.slice(0x2000, 0x2400)), palette: hex(v.slice(0x3f00, 0x3f20))};
};
const oam = (g) => g.oam().filter((s) => s[0] < 0xef);

const gold = {};

// ------------------------------------------------------------------------------------------------------------------ title
{
  const g = new Faxanadu();
  g.run(360);
  const t = {...grab(g), ...vram(g), oam_start: oam(g), cursor_start: g.rd(0x687)};
  g.tap(BTN.SELECT, 10);
  t.oam_continue = oam(g);
  t.cursor_continue = g.rd(0x687);
  gold.title = t;

  // ---------------------------------------------------------------------------------------------------------------- intro
  g.tap(BTN.SELECT, 10);
  g.hold(BTN.START, 2);
  const intro = {oam: [], palette_changes: [], pictures: {}};
  const shots = new Set([5, 100, 300, 500, 639, 640, 648, 656, 664]);
  let last = "";
  for (let i = 0; i < 760; i++) {
    const p = hex(g.nes.ppu.vramMem.slice(0x3f00, 0x3f20));
    if (p !== last) { intro.palette_changes.push([i, p]); last = p; }
    intro.oam.push(oam(g).flat());
    if (shots.has(i)) intro.pictures[i] = grab(g);
    if (i === 100) Object.assign(intro, {vram: vram(g)});
    g.run(1);
    if (g.inPlay() && i > 20) { intro.play_at = i; break; }
  }
  intro.start_state = {x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), screen: g.rd("Area_CurrentScreen"), area: g.rd("Area_CurrentArea"),
    music: g.rd("Music_Current"), hp: g.rd("Player_HP_U"), start_pos: g.rd("Screen_StartPosYX")};
  gold.intro = intro;
}

// ------------------------------------------------------------------------------------------------------------------ outro
{
  const g = new Faxanadu();
  g.run(360);
  g.call("MMC1_UpdateROMBank", {x: 12}, 1);
  g.call(0xA97D, {}, 1);
  const outro = {oam: [], ic: [], music: [], palette_changes: [], pictures: {}};
  const shots = new Set([10, 150, 300, 500, 700, 900, 2400, 2500]);
  let last = "";
  for (let i = 0; i < 2700; i++) {
    const p = hex(g.nes.ppu.vramMem.slice(0x3f00, 0x3f20));
    if (p !== last) { outro.palette_changes.push([i, p]); last = p; }
    outro.oam.push(oam(g).flat());
    outro.ic.push(g.rd("InterruptCounter"));
    outro.music.push(g.rd("Music_Current"));
    if (shots.has(i)) outro.pictures[i] = grab(g);
    if (i === 100) Object.assign(outro, {vram: vram(g)});
    g.run(1);
  }
  gold.outro = outro;
}
fs.writeFileSync(out, JSON.stringify(gold));
