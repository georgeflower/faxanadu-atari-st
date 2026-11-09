// What the ROM does with the sprite slots when the hero leaves a screen and comes back: every placement of the list is loaded again.
//   node respawnprobe.mjs [SCREEN]      (Eolis: SCREEN, then the next one to the left of the map, then back)
import {newTown, BTN} from "./faxanadu.mjs";

const screen = +(process.argv[2] ?? 4);
const g = newTown();
const names = ["Entities", "Flags", "Phases", "HP", "HitCounter", "BehaviorArg1", "BehaviorData2", "BehaviorData3", "Behaviors", "Values"];
const snap = () => {
  const o = [];
  for (let i = 0; i < 8; i++) {
    const s = {i, x: g.rd(g.addr("CurrentSprites_XPos_Full") + i), y: g.rd(g.addr("CurrentSprites_YPos") + i), xf: g.rd(g.addr("CurrentSprites_XPos_Frac") + i), yf: g.rd(g.addr("CurrentSprites_YPos_Frac") + i)};
    for (const n of names) s[n] = g.rd(g.addr("CurrentSprites_" + n) + i);
    o.push(s);
  }
  return o;
};
const show = (t, s) => { console.log(t); for (const e of s) if (e.Entities !== 255) console.log("  ", JSON.stringify(e)); };
const go = (btn, scr) => {
  g.nes.buttonDown(1, btn);
  if (!g.runUntil(() => g.rd("Area_CurrentScreen") === scr && g.inPlay(), 4000)) throw new Error("not there " + scr + " " + g.state());
  g.nes.buttonUp(1, btn);
};
go(BTN.LEFT, screen);
g.run(3);
const s0 = snap(); show("first entry (frame 3 after load)", s0);
// the hero kills every enemy but the first (slot freed) and the first one is hurt and moved
const ent = g.addr("CurrentSprites_Entities");
const live = s0.filter((e) => e.Entities !== 255);
live.slice(1).forEach((e) => g.nes.cpu.mem[ent + e.i] = 255);
if (live.length) { g.nes.cpu.mem[g.addr("CurrentSprites_HP") + live[0].i] = 1; g.nes.cpu.mem[g.addr("CurrentSprites_XPos_Full") + live[0].i] = 100; g.nes.cpu.mem[g.addr("CurrentSprites_Phases") + live[0].i] = 3; }
g.run(2);
show("after the kills and the damage", snap());
const visits0 = g.rd("Screen_TrackedVisitCount");
g.nes.buttonUp(1, BTN.RIGHT);
go(BTN.LEFT, screen + 1); g.run(3);
show("screen " + (screen + 1), snap());
go(BTN.RIGHT, screen); g.run(3);
const s2 = snap(); show("back on screen " + screen + " (frame 3 after load)", s2);
const key = (e) => [e.Entities, e.y, e.HP, e.Phases, e.Values, e.Behaviors];
const same = JSON.stringify(s0.map(key)) === JSON.stringify(s2.map(key));
console.log("placement list loaded again (entity, row, hit points, phase, value, behaviour as on the first entry):", same);
console.log("Screen_TrackedVisitCount:", visits0, "->", g.rd("Screen_TrackedVisitCount"));
console.log("RESULT " + JSON.stringify({first: s0.map(key), back: s2.map(key), same}));
