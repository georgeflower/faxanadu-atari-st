// The town people in the ROM, frame by frame: the hero stands on a screen of an area (through a temple, see `newOutside`) or in a building (walked in through a door of
// that screen), his x is set from a schedule, and every frame the 8 sprite slots, the sprites on show (OAM) and the counters are recorded.
//   node npcprobe.mjs SPEC.json OUT.json
// SPEC: {area, region, screen, x, door: {x, y} | null, frames, hero: [[frame, x], ...], hourglass: [[from, to], ...], inject: [{slot, entity, x, y, hbox, script}, ...]} (the hero's x from the first frame of each pair on;
// it is written every frame; a kind the game never places is put into a slot as the loader would: behaviour ready, the rest 0)
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let g;
if (spec.door) {
  const d = spec.door;
  let ok = false;
  for (const from of [d.x < 100 ? d.x + 80 : d.x - 40, d.x - 16, d.x + 16, d.x - 64, d.x + 48]) {      // where he is put before he is held at the door
    if (from < 8 || from > 232) continue;
    g = newOutside(spec.area, spec.region, spec.screen, from, 144);
    g.wr("SpecialItems", 0xf0);                                // the rings: the doors of key 6 and the others open
    g.nes.buttonDown(1, BTN.UP);
    for (let f = 0; f < 90 && !ok; f++) {                      // held at the door every frame until the game takes him in
      g.wr("Player_PosX_Block", d.x);
      g.wr("Player_PosY", d.y);
      g.run(1);
      ok = g.rd("Area_CurrentArea") === 4;
    }
    g.nes.buttonUp(1, BTN.UP);
    if (ok) break;
  }
  if (!ok) throw new Error("did not get into the building");
  g.runUntil(() => g.inPlay(), 300);
  g.run(150);                                                  // (the building's screen number and its people come a while after the door)
} else {
  g = newOutside(spec.area, spec.region, spec.screen, spec.x ?? 64);
}
const names = ["Entities", "Behaviors", "Flags", "Phases", "BehaviorData2", "BehaviorData3", "BehaviorArg1", "HP", "HitCounter", "HitBoxTypes", "InternalBehaviorStates",
  "HitByMagicBehavior", "Values", "BehaviorState_XFull", "BehaviorState_YFull", "BehaviorState_XFrac", "BehaviorState_YFrac", "BehaviorAddrs_L", "BehaviorAddrs_U", "PPUOffsets"];
for (const j of spec.inject ?? []) {
  const w = (n, v) => g.wr(g.addr("CurrentSprites_" + n) + j.slot, v);
  w("Entities", j.entity); w("XPos_Full", j.x); w("XPos_Frac", 0); w("YPos", j.y); w("YPos_Frac", 0); w("Flags", 0); w("Phases", 0); w("Behaviors", 0xff); w("BehaviorArg1", 0);
  w("HitBoxTypes", j.hbox); w("BehaviorAddrs_L", j.script & 255); w("BehaviorAddrs_U", j.script >> 8); w("HitCounter", 0); w("HP", 0); w("HitByMagicBehavior", 0xff);
}
const startX = g.rd("Player_PosX_Block");
const schedule = spec.hero ?? [];
let heroX = g.rd("Player_PosX_Block");
const rec = [];
for (let f = 0; f < spec.frames; f++) {
  for (const [from, x] of schedule) if (f >= from) heroX = x;
  if (spec.hourglass) g.wr("DurationHourGlass", spec.hourglass.some(([a, b]) => f >= a && f < b) ? 15 : 0xff);      // the Hour Glass in force in these windows of frames (15 seconds, kept up every frame)
  if (schedule.length) g.wr("Player_PosX_Block", heroX);
  g.run(1);
  const slots = [];
  for (let i = 0; i < 8; i++) {
    const s = {x: g.rd(g.addr("CurrentSprites_XPos_Full") + i), xf: g.rd(g.addr("CurrentSprites_XPos_Frac") + i), y: g.rd(g.addr("CurrentSprites_YPos") + i), yf: g.rd(g.addr("CurrentSprites_YPos_Frac") + i)};
    for (const n of names) s[n] = g.rd(g.addr("CurrentSprites_" + n) + i);
    slots.push(s);
  }
  const blocks = f === 0 ? Array.from({length: 256}, (_, i) => g.rd(g.addr("ScreenBuffer") + i)) : undefined;
  rec.push({f, hg: g.rd("DurationHourGlass") !== 0xff, start_x: startX, ic: g.rd("InterruptCounter"), oam: g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x90), rnd: g.rd("Random_Offset"), mask: g.rd("Joy1_ButtonMask"), blocks,
    pf: g.rd("Player_Flags"), px: g.rd("Player_PosX_Block"), py: g.rd("Player_PosY"), counter: g.rd("SpriteUpdateCounter"), area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen"), slots});
}
fs.writeFileSync(process.argv[3], JSON.stringify(rec));
