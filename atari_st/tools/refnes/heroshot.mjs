// The hero as the game draws him, for the ROM-data checks: the harness sets the equipment, lets the game load the tiles and draw him,
// and writes what the PPU holds.
//   node heroshot.mjs ARMOR SHIELD WEAPON PREFIX [flags] [tick]
//   ARMOR 0-3 (leather, studded, full plate, battle suit), SHIELD 0-2 or 255 (none; 3 = battle helmet), WEAPON 0-3 or 255 (none)
//   flags: the value for Player_Flags (bit 0 jumping/crouching? bit 5 walking, bit 6 faces left, bit 7 attacking), tick: Player_MovementTick
// Writes PREFIX.oam.json (the 64 sprites [y, tile, attr, x]), PREFIX.chr.bin (the 4 KB sprite pattern table), PREFIX.state.json.
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [armor, shield, weapon, prefix = "/tmp/hero"] = process.argv.slice(2, 6);
const flags = process.argv[6] !== undefined ? Number(process.argv[6]) : null;
const tick = process.argv[7] !== undefined ? Number(process.argv[7]) : null;
const g = newGame();
g.wr("SelectedArmor", Number(armor));
g.wr("SelectedShield", Number(shield));
g.wr("SelectedWeapon", Number(weapon));
g.wr("Player_CurWeapon", Number(weapon));
// the game loads the hero's tiles when it sets up a screen (in vblank): go through the castle door to get that done with this equipment
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
g.nes.buttonUp(1, BTN.UP);
g.run(40);
if (process.env.HERO_X) { g.wr("Player_PosX_Block", Number(process.env.HERO_X)); }
if (flags !== null) g.wr("Player_Flags", flags);
if (tick !== null) g.wr("Player_MovementTick", tick);
g.run(3);
g.ppm(prefix + ".ppm");
fs.writeFileSync(prefix + ".chr.bin", Buffer.from(g.nes.ppu.vramMem.slice(0, 0x1000)));
fs.writeFileSync(prefix + ".oam.json", JSON.stringify(g.oam()));
fs.writeFileSync(prefix + ".state.json", JSON.stringify({
  x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"),
  armor: g.rd("SelectedArmor"), shield: g.rd("SelectedShield"), weapon: g.rd("Player_CurWeapon"), armorLookup: g.rd("Player_ArmorLookupIndex"),
  scrollX: g.rd("PPU_ScrollX"), attackFrame: g.rd("Player_AttackPhaseAnimFrame"), palette: g.rd("Screen_PaletteIndex"),
  sprPal: Array.from(g.nes.ppu.vramMem.slice(0x3f10, 0x3f20)),
}));
console.log("ok");
