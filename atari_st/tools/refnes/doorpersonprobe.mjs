// A locked door and a person at once: the hero stands at a door that needs a key (no key in hand) with a person's box over his, and Up is pressed. Every start of an
// interaction script (`IScripts_Begin`: the script's number is in A) and the frame it started in are recorded, and what the hero's buttons do afterwards.
//   node doorpersonprobe.mjs SPEC.json OUT.json
// SPEC: {area, region, screen, x (the hero's, and the door's), entity, script (the person's `CurrentSprites_Values`), px (the person's x), ring (0 or 1), up: [frame, ...] (Up goes
//   down in these frames for 3), buttons: "A" | "B" | "none" (what presses after the first script has started: A for 4 of every 8 frames, B, nothing), frames}
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const g = newOutside(spec.area, spec.region, spec.screen, spec.x, 144);
g.wr("SpecialItems", spec.ring ? 0xf0 : 0);
g.wr("SelectedItem", 0xff);
const w = (n, v) => g.wr(g.addr("CurrentSprites_" + n) + 7, v);
if (spec.entity !== undefined) {                                  // the person in slot 7 (the screen's own people are cleared first)
  for (let i = 0; i < 8; i++) g.wr(g.addr("CurrentSprites_Entities") + i, 0xff);
  w("Entities", spec.entity); w("XPos_Full", spec.px ?? spec.x); w("XPos_Frac", 0); w("YPos", 144); w("YPos_Frac", 0); w("Flags", 0); w("Phases", 0); w("Behaviors", 0xff); w("BehaviorArg1", 0);
  w("HitBoxTypes", spec.hbox); w("BehaviorAddrs_L", spec.bscript & 255); w("BehaviorAddrs_U", spec.bscript >> 8); w("HitCounter", 0); w("HP", 0); w("HitByMagicBehavior", 0xff);
  w("Values", spec.script);
}
const begin = g.romLabels["IScripts_Begin"][0] - 1;
const starts = [];
let cpu = g.nes.cpu, frame = 0, last = -1;
const emulate = cpu.emulate.bind(cpu);
cpu.emulate = function () {
  const pc = cpu.REG_PC;
  if (pc === begin && pc !== last) starts.push({frame, script: cpu.REG_ACC, bank: g.rd("CurrentROMBank")});
  last = pc;
  return emulate();
};
const rec = [];
let first = -1;
for (frame = 0; frame < spec.frames; frame++) {
  const up = spec.up.some((u) => frame >= u && frame < u + 3);
  up ? g.nes.buttonDown(1, BTN.UP) : g.nes.buttonUp(1, BTN.UP);
  if (starts.length && first < 0) first = frame;
  let a = false, b = false;
  if (first >= 0 && !up) { if (spec.buttons === "A") a = ((frame - first) & 7) >= 4; else if (spec.buttons === "B") b = ((frame - first) & 7) >= 4; }
  a ? g.nes.buttonDown(1, BTN.A) : g.nes.buttonUp(1, BTN.A);
  b ? g.nes.buttonDown(1, BTN.B) : g.nes.buttonUp(1, BTN.B);
  g.run(1);
  rec.push({f: frame, area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen"), changed: g.rd("Joy1_ChangedButtonMask"), x: g.rd("Player_PosX_Block"), up});
}
g.nes.buttonUp(1, BTN.UP); g.nes.buttonUp(1, BTN.A); g.nes.buttonUp(1, BTN.B);
fs.writeFileSync(process.argv[3], JSON.stringify({starts, final: {area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen")}, rec}));
