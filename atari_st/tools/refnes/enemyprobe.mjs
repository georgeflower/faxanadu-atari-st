// What the sprite slots do, frame by frame: into Eolis, right to a screen with enemies, the hero stands still (or walks), and every frame the 8 slots are recorded.
//   node enemyprobe.mjs SCREEN FRAMES [OUT.json] [right|left]
import {newTown, newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const screen = +(process.argv[2] ?? 4), frames = +(process.argv[3] ?? 200), out = process.argv[4], dir = process.argv[5] ?? "right";
// AREA=n (and REGION, HEROX) puts the hero on the screen of another area through a temple; without it he walks there from the first screen of Eolis.
const area = +(process.env.AREA ?? 0);
let g;
if (area) g = newOutside(area, +(process.env.REGION ?? 0), screen, +(process.env.HEROX ?? 64));
else {
  g = newTown();
  const walk = dir === "left" ? BTN.LEFT : BTN.RIGHT;
  g.nes.buttonDown(1, walk);
  if (!g.runUntil(() => g.rd("Area_CurrentScreen") === screen && g.inPlay(), 3000)) throw new Error("not there: " + g.state());
  g.nes.buttonUp(1, walk);
}
const names = ["Entities", "Behaviors", "Flags", "Phases", "BehaviorData2", "BehaviorData3", "BehaviorArg1", "HP", "HitCounter", "HitBoxTypes", "InternalBehaviorStates",
  "HitByMagicBehavior", "Values", "BehaviorState_XFull", "BehaviorState_YFull", "BehaviorState_XFrac", "BehaviorState_YFrac", "BehaviorAddrs_L", "BehaviorAddrs_U", "PPUOffsets"];
const rec = [];
for (let f = 0; f < frames; f++) {
  g.run(1);
  const slots = [];
  for (let i = 0; i < 8; i++) {
    const s = {x: g.rd(g.addr("CurrentSprites_XPos_Full") + i), xf: g.rd(g.addr("CurrentSprites_XPos_Frac") + i), y: g.rd(g.addr("CurrentSprites_YPos") + i), yf: g.rd(g.addr("CurrentSprites_YPos_Frac") + i)};
    for (const n of names) s[n] = g.rd(g.addr("CurrentSprites_" + n) + i);
    slots.push(s);
  }
  const blocks = f === 0 ? Array.from({length: 256}, (_, i) => g.rd(g.addr("ScreenBuffer") + i)) : undefined;
  rec.push({f, chr: f === 0 ? Array.from(g.nes.ppu.vramMem.slice(0x900, 0xD00)) : undefined, ic: g.rd("InterruptCounter"), oam: g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x90), rnd: g.rd("Random_Offset"), mask: g.rd("Joy1_ButtonMask"), blocks, px: g.rd("Player_PosX_Block"), py: g.rd("Player_PosY"), counter: g.rd("SpriteUpdateCounter"), slots});
}
if (out) fs.writeFileSync(out, JSON.stringify(rec));
for (const r of rec.slice(0, 40)) {
  const live = r.slots.map((s, i) => [i, s]).filter(([, s]) => s.Entities !== 255);
  console.log(r.f, `hero ${r.px},${r.py} ctr ${r.counter}`, live.map(([i, s]) => `#${i} e${s.Entities} (${s.x}.${s.xf},${s.y}.${s.yf}) fl${s.Flags} ph${s.Phases} b${s.Behaviors} a${s.BehaviorArg1} d${s.BehaviorData2}/${s.BehaviorData3} hp${s.HP} h${s.HitCounter}`).join(" | "));
}
