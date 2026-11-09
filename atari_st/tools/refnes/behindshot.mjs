// The hero in front of and behind the pillar of Eolis screen 4 (blocks 92 and 93, x 176 to 207), as jsnes draws him, for the picture check in tests/test_behind.py:
// the harness walks to the screen, takes the enemies away and puts him at each of the given places; for each it writes PREFIX<n>.ppm (256x240), PREFIX<n>.oam.json and
// PREFIX<n>.state.json (x, y, flags, equipment, the sprite palettes).
//   node behindshot.mjs PREFIX X:FLAGS ...     (FLAGS: Player_Flags, bit 6 faces left)
// EQUIP=armor,shield,weapon as behindprobe.mjs
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [prefix, ...places] = process.argv.slice(2);
const g = newGame();
const equip = process.env.EQUIP ? process.env.EQUIP.split(",").map(Number) : null;
if (equip) {                                // (before the castle door: the game loads the hero's tiles when it sets up a screen)
  g.wr("SelectedArmor", equip[0]); g.wr("SelectedShield", equip[1]); g.wr("SelectedWeapon", equip[2]); g.wr("Player_CurWeapon", equip[2]);
  g.wr("Player_ArmorLookupIndex", equip[1] === 255 ? 0 : 1);
}
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300)) throw new Error("did not get into Eolis: " + g.state());
g.nes.buttonUp(1, BTN.UP);
g.run(20);
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === 4 && g.inPlay(), 3000)) throw new Error("not there " + g.state());
g.nes.buttonUp(1, BTN.LEFT);
g.run(10);
places.forEach((p, n) => {
  const [x, flags] = p.split(":").map(Number);
  for (let i = 0; i < 8; i++) g.wr(g.addr("CurrentSprites_Entities") + i, 0xff);
  g.wr("Player_PosX_Block", x);
  g.wr("Player_Flags", flags);
  g.run(3);
  g.ppm(`${prefix}${n}.ppm`);
  fs.writeFileSync(`${prefix}${n}.oam.json`, JSON.stringify(g.oam()));
  fs.writeFileSync(`${prefix}${n}.state.json`, JSON.stringify({
    x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), armor: g.rd("SelectedArmor"), shield: g.rd("SelectedShield"), weapon: g.rd("Player_CurWeapon"),
    sprPal: Array.from(g.nes.ppu.vramMem.slice(0x3f10, 0x3f20)),
  }));
});
console.log("ok");
