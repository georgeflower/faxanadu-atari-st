// Headless NES reference: boots the Faxanadu ROM in jsnes, drives the controller, reads and writes RAM by the
// disassembly's own label names.
//
//   ROM     the ROM to run (default ext/Faxanadu_Europe.nes, never committed). ROM=../../../build/faxanadu.nes runs the US build.
//   labels  atari_st/build/refnes/ram_labels.json, made by `python3 tools/ram_labels.py` from the disassembly.
//
// jsnes runs NTSC timing. Faxanadu's logic is driven by the NMI, so a jsnes frame is one game tick whatever the region;
// only the wall-clock length of a tick differs (60 or 50 a second).
import {NES, Controller} from "jsnes";
import fs from "fs";
import path from "path";
import {fileURLToPath} from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const ROM = process.env.ROM ? path.resolve(process.env.ROM) : path.resolve(here, "../../../ext/Faxanadu_Europe.nes");
export const LABELS = path.resolve(here, "../../build/refnes/ram_labels.json");
export const BTN = {A: Controller.BUTTON_A, B: Controller.BUTTON_B, SELECT: Controller.BUTTON_SELECT,
  START: Controller.BUTTON_START, UP: Controller.BUTTON_UP, DOWN: Controller.BUTTON_DOWN,
  LEFT: Controller.BUTTON_LEFT, RIGHT: Controller.BUTTON_RIGHT};

export class Faxanadu {
  constructor() {
    this.pixels = null;
    this.nes = new NES({onFrame: (buf) => { this.pixels = buf; }, onAudioSample() {}});
    this.nes.loadROM(fs.readFileSync(ROM).toString("binary"));
    this.frames = 0;
    this.labels = fs.existsSync(LABELS) ? JSON.parse(fs.readFileSync(LABELS, "utf8")) : {};
    // ROM labels [cpu address, bank, file offset] from tools/faxanadu_rom.py (made when that module first runs)
    const romLabels = path.resolve(here, "../../build/refnes/rom_labels.json");
    this.romLabels = fs.existsSync(romLabels) ? JSON.parse(fs.readFileSync(romLabels, "utf8")) : {};
  }
  // an address, or a label name from the disassembly
  addr(a) {
    if (typeof a === "number") return a;
    if (!(a in this.labels)) throw new Error(`no RAM label ${a} (run tools/ram_labels.py)`);
    return this.labels[a];
  }
  rd(a) { return this.nes.cpu.mem[this.addr(a)]; }
  rd16(a) { const x = this.addr(a); return this.nes.cpu.mem[x] | (this.nes.cpu.mem[x + 1] << 8); }
  wr(a, v) { this.nes.cpu.mem[this.addr(a)] = v & 0xff; }
  get pc() { return this.nes.cpu.REG_PC; }
  run(n = 1) { for (let i = 0; i < n; i++) { this.nes.frame(); this.frames++; } }
  hold(btn, n = 2) { this.nes.buttonDown(1, btn); this.run(n); this.nes.buttonUp(1, btn); }
  tap(btn, gap = 6) { this.hold(btn, 3); this.run(gap); }
  runUntil(pred, max = 6000) { for (let i = 0; i < max; i++) { if (pred()) return true; this.run(1); } return false; }
  // the PPU's picture of the last frame as 256x240 0xBBGGRR pixels, written as a PPM
  ppm(file) {
    const out = [`P6\n256 240\n255\n`];
    const buf = Buffer.alloc(256 * 240 * 3);
    for (let i = 0; i < 256 * 240; i++) {
      const p = this.pixels[i];
      buf[i * 3] = p & 0xff; buf[i * 3 + 1] = (p >> 8) & 0xff; buf[i * 3 + 2] = (p >> 16) & 0xff;
    }
    fs.writeFileSync(file, Buffer.concat([Buffer.from(out[0], "latin1"), buf]));
  }
  state() {
    return `area=${this.rd("Area_CurrentArea")} screen=${this.rd("Area_CurrentScreen")} ` +
      `x=${this.rd("Player_PosX_Block")} y=${this.rd("Player_PosY")} scrollDir=${this.rd("Screen_ScrollDirection")} ` +
      `scrollX=${this.rd("PPU_ScrollX")} bank=${this.rd("CurrentROMBank")}`;
  }
  // in play: the main loop runs and the player is on the screen (the scroll direction is $FF when nothing scrolls)
  inPlay() { return this.rd("Screen_ScrollDirection") === 0xff && this.rd("Player_PosY") !== 0; }
}

// A game in play: Start at the title, then Start again where the game asks, until the hero stands in Eolis.
export function newGame() {
  const g = new Faxanadu();
  g.run(360);
  for (let i = 0; i < 6 && !g.inPlay(); i++) {
    g.tap(BTN.START, 30);
    g.runUntil(() => g.inPlay(), 400);
  }
  if (!g.inPlay()) throw new Error("did not reach play: " + g.state());
  g.run(30);
  return g;
}

// The same, then through the castle door at the right of the first screen, into Eolis (screen 1 of area 0, with a
// screen to each side), where walking, scrolling and doors can be tried. (The first screen has no neighbours.)
export function newTown() {
  const g = newGame();
  g.wr("Player_PosX_Block", 192);
  g.run(3);
  g.nes.buttonDown(1, BTN.UP);
  const ok = g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
  g.nes.buttonUp(1, BTN.UP);
  if (!ok) throw new Error("did not get into Eolis: " + g.state());
  g.run(20);
  return g;
}

// The sprites jsnes has on screen: [y, tile, attributes, x] for each of the 64 OAM entries (y is the line above the sprite).
Faxanadu.prototype.oam = function () {
  const m = this.nes.ppu.spriteMem, out = [];
  for (let i = 0; i < 64; i++) out.push([m[i * 4], m[i * 4 + 1], m[i * 4 + 2], m[i * 4 + 3]]);
  return out;
};

// Run one of the game's own routines (by label in the disassembly, from `labels` of ROM addresses) from where the main loop
// waits, with the registers given, and let `frames` frames pass so the NMI writes what it queued to the PPU.
// jsnes keeps PC one byte before the next instruction, which is what a JSR pushes, so pushing PC and jumping to addr - 1 is a call.
Faxanadu.prototype.call = function (target, regs = {}, frames = 3) {
  const cpu = this.nes.cpu;
  const addr = typeof target === "number" ? target : this.romLabels[target][0];
  cpu.push((cpu.REG_PC >> 8) & 255);
  cpu.push(cpu.REG_PC & 255);
  if (regs.a !== undefined) cpu.REG_ACC = regs.a;
  if (regs.x !== undefined) cpu.REG_X = regs.x;
  if (regs.y !== undefined) cpu.REG_Y = regs.y;
  cpu.REG_PC = addr - 1;
  this.run(frames);
};

// Start a new life in a temple of any area (Player_Spawn with row 0 of the temple tables changed): area (Area_CurrentArea), region (Area_Region), the
// screen outside and the hero's x and y there. The hero is inside the temple; `leaveBuilding()` walks him out.
Faxanadu.prototype.warp = function (area, region, screen, x = 64, y = 144) {
  const rows = {START_SCREEN_FOR_TEMPLE_SPAWN: screen, START_MAYBE_NEXT_AREA_FOR_TEMPLE_SPAWN: region, START_PLAYERPOSX_FULL_FOR_TEMPLE_SPAWN: x,
    MAYBE_START_PLAYERPOSY_FOR_TEMPLE_SPAWN: y, DEST_SCREEN_FOR_TEMPLE_SPAWN: 0, CURRENT_REGION_FOR_TEMPLE_SPAWN: area};
  for (const [label, v] of Object.entries(rows)) this.nes.cpu.mem[this.romLabels[label][0]] = v;
  this.wr("TempleSpawnPoint", 0);
  this.nes.cpu.REG_PC = this.romLabels["Player_Spawn"][0] - 1;
  this.run(150);
};

// A game in play outside, on a screen of any area (through a temple, see `warp`): the hero stands at x, y on `screen` and the sprites of the screen are loaded.
export function newOutside(area, region, screen, x = 64, y = 144) {
  const g = newGame();
  g.warp(area, region, screen, x, y);
  g.nes.buttonDown(1, BTN.RIGHT);
  const ok = g.runUntil(() => g.rd("Area_CurrentArea") === area && g.rd("Area_CurrentScreen") === screen && g.inPlay(), 600);
  g.nes.buttonUp(1, BTN.RIGHT);
  if (!ok) throw new Error("did not get out of the temple: " + g.state());
  g.run(20);
  return g;
}
