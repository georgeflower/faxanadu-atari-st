// Sprites behind the background (Player_CalculateVisibility): Eolis screen 4 has a pillar of blocks 92/93 (property 4, x 176 to 207, rows 4 to 10). The hero walks left through it
// and back right; every frame records his x, y and flags and the sprites in OAM that are near him (y, tile, attribute, x; attribute bit 5 = behind the background).
//   node behindprobe.mjs [SCREEN] [OUT.json]
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const screen = +(process.argv[2] ?? 4), out = process.argv[3];
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === screen && g.inPlay(), 3000)) throw new Error("not there " + g.state());
g.nes.buttonUp(1, BTN.LEFT);
g.run(10);
const rec = [];
const snap = () => {
  const x = g.rd("Player_PosX_Block"), y = g.rd("Player_PosY");
  const slots = [];
  for (let i = 0; i < 8; i++) slots.push({e: g.rd(g.addr("CurrentSprites_Entities") + i), x: g.rd(g.addr("CurrentSprites_XPos_Full") + i), y: g.rd(g.addr("CurrentSprites_YPos") + i), fl: g.rd(g.addr("CurrentSprites_Flags") + i)});
  rec.push({x, y, slots, flags: g.rd("Player_Flags"), counter: g.rd("SpriteUpdateCounter"), vis: g.rd("MovingSpriteVisibility"), sx: g.rd("PPU_ScrollX"),
    oam: g.oam().filter((o) => o[0] < 0xef && true)});
};
const act = (buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b); for (let i = 0; i < n; i++) { g.run(1); snap(); } for (const b of buttons) g.nes.buttonUp(1, b); };
act([BTN.LEFT], 130);
act([], 10);
act([BTN.RIGHT], 130);
if (out) fs.writeFileSync(out, JSON.stringify(rec));
for (const r of rec.filter((_, i) => i % 6 === 0)) console.log(r.x, r.y, r.flags.toString(16), "vis", r.vis, r.oam.map((o) => `${o[3]},${o[0]}:${o[1].toString(16)}/${o[2].toString(16)}`).slice(0, 12).join(" "));
