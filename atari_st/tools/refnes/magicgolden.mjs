// Cast magic, frame by frame (golden run for tools/magic_model.py): the hero stands on the first screen of Eolis (the start screen, no
// neighbours), the harness selects a spell, gives him the magic power, presses Up and B, and records after every frame the game's cast magic state
// (CastMagic_*), the magic power, the interrupt counter, the sound effect asked for and the sprites of the spell in jsnes's OAM, with the buttons.
//   node magicgolden.mjs OUT.json
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2] ?? "/tmp/magicgolden.json";
const g = newGame();
const SB = g.addr("ScreenBuffer");
const ground = g.nes.cpu.mem[SB + 11 * 16];
const original = Array.from(g.nes.cpu.mem.slice(SB, SB + 208));
const scenarios = [];

const snap = (extra = {}) => ({
  type: g.rd("CastMagic_Type"), flags: g.rd("CastMagic_Flags"), x: g.rd("CastMagic_XPos_Full"), xfrac: g.rd("CastMagic_XPos_Frac"),
  y: g.rd("CastMagic_YPos_Full"), yfrac: g.rd("CastMagic_YPos_Frac"), counter: g.rd("CastMagic_Counter"), phase: g.rd("CastMagic_Phase"),
  mp: g.rd("Player_MP"), ic: g.rd("InterruptCounter"), snd: g.rd("SoundEffect_Current"), joy: g.rd("Joy1_ButtonMask"), changed: g.rd("Joy1_ChangedButtonMask"),
  climbing: g.rd("Player_Flags") & 0x10, hx: g.rd("Player_PosX_Block"), hy: g.rd("Player_PosY"), hflags: g.rd("Player_Flags"), oam: g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x40 && o[1] < 0x90), ...extra,
});

// One scenario: the hero at (x, y) facing right or left, the spell, the magic power, the walls (block columns/rows made as solid as the floor), the
// buttons. The game sometimes misses a button press when its main loop runs long (the changed-buttons byte is overwritten by the next frame's), so a
// scenario in which the press was not acted on (no attack and no spell began) is started again; the hero's attack always begins with B.
function run({spell, x, y, right, mp, walls = [], buttons = [BTN.UP, BTN.B], frames = 90, name = "", jump = 0}) {
  const press = buttons.filter((b) => b === BTN.B), first = buttons.filter((b) => b !== BTN.B);
  for (let attempt = 0; attempt < 8; attempt++) {
    g.wr("CastMagic_Type", 0xff);
    for (let i = 0; i < 208; i++) g.nes.cpu.mem[SB + i] = original[i];
    for (const [r, c] of walls) g.nes.cpu.mem[SB + r * 16 + c] = ground;
    g.wr("SelectedMagic", spell); g.wr("Player_MP", mp);
    g.wr("Player_PosX_Block", x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", y); g.wr("Player_Flags", right ? 0x40 : 0);
    g.wr("Player_MoveAcceleration", 0); g.wr("Player_MoveAcceleration_U", 0); g.wr("Player_StatusFlag", 0);
    g.run(40);                                              // (he settles: from the air he falls to the floor)
    if (jump) { g.nes.buttonDown(1, BTN.A); g.run(1); g.nes.buttonUp(1, BTN.A); g.run(jump); }    // in a jump: not on a block row
    const rec = {spell, x, y, right, mp, walls, name, start: snap(), frames: []};
    for (const b of first) g.nes.buttonDown(1, b);
    g.run(2); rec.frames.push(snap()); rec.frames.push(snap());   // Up (or nothing) first,
    for (const b of press) g.nes.buttonDown(1, b);
    g.run(1); rec.frames.push(snap());                      // then B as a new press
    for (const b of buttons) g.nes.buttonUp(1, b);
    const acted = !press.length || g.rd("CastMagic_Type") !== 0xff || (g.rd("Player_Flags") & 0x80);
    if (!acted) { g.run(30); continue; }
    let after = 0;
    for (let i = 1; i < frames; i++) {
      g.run(1); rec.frames.push(snap());
      if (g.rd("CastMagic_Type") === 0xff && ++after > 4) break;
    }
    g.run(30);
    scenarios.push(rec);
    return;
  }
  throw new Error("the press was never acted on: " + name);
}

for (const spell of [0, 1, 2, 3, 4]) {
  for (const right of [true, false]) {
    run({spell, x: right ? 40 : 150, y: 144, right, mp: 80, name: "free flight"});
    run({spell, x: right ? 40 : 150, y: 144, right, mp: 80, walls: [[9, right ? 9 : 4], [10, right ? 9 : 4]], name: "a wall two blocks high"});
    run({spell, x: right ? 40 : 150, y: 130, right, mp: 80, walls: [[8, right ? 8 : 5], [9, right ? 8 : 5], [10, right ? 8 : 5]], name: "between block rows, a wall three high"});
    run({spell, x: right ? 100 : 130, y: 100, right, mp: 80, name: "high up"});
  }
  run({spell, x: 100, y: 144, right: true, mp: [2, 4, 6, 10, 16][spell], name: "just enough power"});
  run({spell, x: 100, y: 144, right: true, mp: [2, 4, 6, 10, 16][spell] - 1, name: "too little power"});
  run({spell, x: 100, y: 144, right: true, mp: 80, buttons: [BTN.B], name: "B without Up"});
  run({spell, x: 100, y: 144, right: true, mp: 80, buttons: [BTN.UP], name: "Up without B"});
}
for (const spell of [0, 1, 2, 3, 4]) {
  for (const jump of [3, 6, 10, 14]) {
    run({spell, x: 40, y: 144, right: true, mp: 80, jump, walls: [[8, 9], [9, 9], [10, 9], [7, 9]], name: "cast in a jump " + jump});
    run({spell, x: 150, y: 144, right: false, mp: 80, jump, walls: [[8, 4], [9, 4], [10, 4], [7, 4]], name: "cast in a jump " + jump});
  }
}
run({spell: 5, x: 100, y: 144, right: true, mp: 80, name: "no such spell"});
run({spell: 255, x: 100, y: 144, right: true, mp: 80, name: "no spell selected"});
fs.writeFileSync(out, JSON.stringify(scenarios));
console.log(scenarios.length, "scenarios");
