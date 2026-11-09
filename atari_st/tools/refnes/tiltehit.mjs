// The Tilte spell hitting an enemy (the explosion), and not hitting one (it ends where it leaves the screen: no explosion at a wall or at the end of its flight).
// Eolis screen 4: the hero at x 85 facing right (or left), the Zozura in front of him given HP 200 (so it lives) or none at all. Records every frame the cast magic
// state (CastMagic_*), the interrupt counter and the sprites in OAM.
//   node tiltehit.mjs OUT.json hit|miss|wall|left [spell]
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2], mode = process.argv[3] ?? "hit", spell = +(process.argv[4] ?? 4);
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 4 && g.inPlay(), 3000)) throw new Error("not there");
g.nes.buttonUp(1, BTN.LEFT);
g.run(5);
g.wr("Player_HP_U", 80); g.wr("Player_InvincibilityPhase", 255);
g.wr("SelectedMagic", spell); g.wr("Player_MP", 80);
const left = mode === "left";
g.wr("Player_PosX_Block", left ? 200 : 85); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", 144); g.wr("Player_Flags", left ? 0 : 0x40);
const slotAddr = (n, i) => g.addr("CurrentSprites_" + n) + i;
g.run(2);
const SB = g.addr("ScreenBuffer");
if (mode === "wall") {                                         // a wall two blocks high 8 blocks in front of him (rows 9 and 10, column 12)
  const ground = g.nes.cpu.mem[SB + 11 * 16];
  for (const r of [8, 9, 10]) g.nes.cpu.mem[SB + r * 16 + 12] = ground;
}
for (let i = 0; i < 8; i++) {
  if (g.rd(slotAddr("Entities", i)) !== 0x47) continue;
  if (mode === "hit") { g.wr(slotAddr("XPos_Full", i), 101); g.wr(slotAddr("HP", i), 200); }
  else g.wr(slotAddr("Entities", i), 0xFF);                    // taken away: nothing to hit
}
const rec = [];
const snap = (f) => ({f, type: g.rd("CastMagic_Type"), flags: g.rd("CastMagic_Flags"), x: g.rd("CastMagic_XPos_Full"), y: g.rd("CastMagic_YPos_Full"),
  counter: g.rd("CastMagic_Counter"), phase: g.rd("CastMagic_Phase"), ic: g.rd("InterruptCounter"), snd: g.rd("SoundEffect_Current"),
  slots: Array.from({length: 8}, (_, i) => [g.rd(slotAddr("Entities", i)), g.rd(slotAddr("XPos_Full", i)), g.rd(slotAddr("HP", i))]),
  oam: g.oam().map((o, i) => [i, ...o]).filter((o) => o[1] >= 8 && o[1] < 240 && o[4] < 250)});
g.nes.buttonDown(1, BTN.UP); g.run(2); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.UP);
rec.push(snap(0));
let ended = 0;
for (let f = 1; f < 400 && ended < 6; f++) { g.run(1); rec.push(snap(f)); if (g.rd("CastMagic_Type") === 0xFF) ended++; }
if (out) fs.writeFileSync(out, JSON.stringify(rec));
for (const r of rec) console.log(r.f, "type", r.type, "x", r.x, "y", r.y, "counter", r.counter, "phase", r.phase, "ic", r.ic);
