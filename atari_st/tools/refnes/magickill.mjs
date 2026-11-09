// A kill with a spell, frame by frame: Eolis screen 4, the hero at x 85 facing right next to the Zozura, the Zozura given HP 1, the spell cast with Up and B.
// Records, from the frame of the hit, the death effect's slot (entity, BehaviorData2, SpriteUpdateCounter, x, y) and the sprites in OAM near it.
//   node magickill.mjs SPELL OUT.json [sword]       (with `sword` the Zozura is killed with the sword instead, for the entity $13 reference)
// BOSS=1 turns the death effect into entity $64 in step 2 (what SpriteUpdateHandler_Effect_BossDeath does in its steps 2 and 7: the same drawing as $14).
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const spell = +(process.argv[2] ?? 1), out = process.argv[3], sword = process.argv[4] === "sword";
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 4 && g.inPlay(), 3000)) throw new Error("not there");
g.nes.buttonUp(1, BTN.LEFT);
g.run(5);
g.wr("Player_HP_U", 80); g.wr("Player_InvincibilityPhase", 255);
g.wr("Player_CurWeapon", 1); g.wr("SelectedWeapon", 1);
g.wr("SelectedMagic", spell); g.wr("Player_MP", 80);
g.wr("Player_PosX_Block", 85); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", 144); g.wr("Player_Flags", 0x40);
const slotAddr = (n, i) => g.addr("CurrentSprites_" + n) + i;
const slots = () => { const a = []; for (let i = 0; i < 8; i++) a.push({ent: g.rd(slotAddr("Entities", i)), x: g.rd(slotAddr("XPos_Full", i)), y: g.rd(slotAddr("YPos", i)), d2: g.rd(slotAddr("BehaviorData2", i)), hp: g.rd(slotAddr("HP", i)), flags: g.rd(slotAddr("Flags", i)), phase: g.rd(slotAddr("Phases", i)), internal: g.rd(slotAddr("InternalBehaviorStates", i))}); return a; };
// the Zozura nearest the hero in front of him
let target = -1;
g.run(2);
for (let i = 0; i < 8; i++) if (g.rd(slotAddr("Entities", i)) === 0x47) target = i;
if (target < 0) throw new Error("no zozura");
g.wr(slotAddr("XPos_Full", target), 101);
g.wr(slotAddr("HP", target), 1);
const rec = [];
if (sword) { g.nes.buttonDown(1, BTN.B); g.run(2); g.nes.buttonUp(1, BTN.B); }
else { g.nes.buttonDown(1, BTN.UP); g.run(2); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.UP); }
for (let f = 0; f < 40; f++) {
  if (process.env.BOSS && g.rd(slotAddr("Entities", target)) === 0x14) { g.wr(slotAddr("Entities", target), 0x64); g.wr(slotAddr("Phases", target), 2); }
  g.run(1);
  const s = slots()[target];
  rec.push({f, ic: g.rd("InterruptCounter"), counter: g.rd("SpriteUpdateCounter"), slot: s, all: slots().map((q) => q.ent), oam: g.oam().map((o, i) => [i, ...o]).filter((o) => o[1] >= 8 && o[1] < 240 && o[4] < 250)});
}
if (out) fs.writeFileSync(out, JSON.stringify(rec));
for (const r of rec) console.log(r.f, "counter", r.counter, "slots", r.all.map((e) => e.toString(16)).join(","), "target", JSON.stringify(r.slot));
