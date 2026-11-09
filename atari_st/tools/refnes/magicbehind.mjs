// Spells behind the background (CastMagic_CalculateVisibility): Eolis screen 4 has a pillar (x 176 to 207, rows 4 to 10, property 4). The hero casts each spell from
// several places on both sides of it, facing either way; every frame records the spell's x, y and flags (CastMagic_*), MovingSpriteVisibility and the spell's sprites in OAM
// (y, tile, attribute, x; tiles $40 to $8F; attribute bit 5 = behind the background).
//   node magicbehind.mjs [OUT.json]
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2];
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 4 && g.inPlay(), 3000)) throw new Error("not there " + g.state());
g.nes.buttonUp(1, BTN.LEFT);
g.run(10);
const rec = [];
for (const spell of [0, 1, 2, 3, 4]) for (const flags of [0x00, 0x40]) for (const x of [120, 150, 170, 196, 215, 236]) {
  g.wr("CastMagic_Type", 0xff);
  g.wr("SelectedMagic", spell); g.wr("Player_MP", 80);
  g.wr("Player_PosX_Block", x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", 144); g.wr("Player_Flags", flags);
  g.wr("Player_MoveAcceleration", 0); g.wr("Player_MoveAcceleration_U", 0); g.wr("Player_StatusFlag", 0);
  g.run(30);
  g.nes.buttonDown(1, BTN.UP); g.run(2); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.UP);
  for (let i = 0; i < 70; i++) {
    g.run(1);
    if (g.rd("CastMagic_Type") === 0xff) { if (i > 6) break; continue; }
    rec.push({spell, hx: x, type: g.rd("CastMagic_Type"), cflags: g.rd("CastMagic_Flags"), x: g.rd("CastMagic_XPos_Full"), y: g.rd("CastMagic_YPos_Full"),
      vis: g.rd("MovingSpriteVisibility"), oam: g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x40 && o[1] < 0x90)});
  }
  g.run(40);
}
if (out) fs.writeFileSync(out, JSON.stringify(rec));
console.log(rec.length, "frames");
