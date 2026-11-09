// Sprites behind the background for the hero's weapon, shield and sword arm: Eolis screen 4 (a pillar of blocks 92/93, property 4, x 176 to 207, rows 4 to 10).
// The harness puts the hero at every x from X0 to X1 on the ground, lets him strike (B), and records for every frame the sprites of his own
// (tiles below $40: body, arm, shield, weapon; y, tile, attribute, x) with the weapon's own place (PlayerPosXPlus10, Maybe_Something_WeaponPosY).
//   EQUIP=armor,shield,weapon  node behindspots.mjs [X0] [X1] [OUT.json]
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const x0 = +(process.argv[2] ?? 150), x1 = +(process.argv[3] ?? 236), out = process.argv[4];
const equip = (process.env.EQUIP ?? "1,0,1").split(",").map(Number);
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 4 && g.inPlay(), 3000)) throw new Error("not there " + g.state());
g.nes.buttonUp(1, BTN.LEFT);
g.wr("SelectedArmor", equip[0]); g.wr("SelectedShield", equip[1]); g.wr("SelectedWeapon", equip[2]); g.wr("Player_CurWeapon", equip[2]);
g.wr("Player_ArmorLookupIndex", equip[1] === 255 ? 0 : 1);
g.run(10);
const rec = [];
for (const left of [0, 1]) for (let x = x0; x <= x1; x++) {
  g.wr("Player_PosX_Block", x); g.wr("Player_Flags", left ? 0x40 : 0x00); g.wr("Player_StatusFlag", 0);
  g.run(2);
  g.nes.buttonDown(1, BTN.B);
  for (let i = 0; i < 14; i++) {
    g.run(1);
    if (i === 0) g.nes.buttonUp(1, BTN.B);
    rec.push({left, x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), wx: g.rd("PlayerPosXPlus10"), wy: g.rd("Maybe_Something_WeaponPosY"),
      sx: g.rd("PPU_ScrollX"), oam: g.oam().filter((o) => o[0] < 0xef && o[1] < 0x40 && o[3] > x - 40 && o[3] < x + 56 && o[0] > 150 && o[0] < 215)});
  }
  g.run(30);
}
if (out) fs.writeFileSync(out, JSON.stringify(rec));
console.log(rec.length, "frames; sample", JSON.stringify(rec[3]));
