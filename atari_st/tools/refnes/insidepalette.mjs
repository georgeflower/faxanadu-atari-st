// The palettes the PPU holds outside and inside a building, and a picture inside: the hero walks through a door of Eolis (screen 1, x 48), and the PPU's four background and four
// sprite palettes (NES colour numbers) are written out for each place (the sprite palettes are loaded from bank 11: $1C0 outside, $1D0 inside).
//   node insidepalette.mjs PREFIX [screen x]      writes PREFIX.json, PREFIX_in.ppm and PREFIX_in.chr.bin (the CHR RAM)
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [prefix = "/tmp/inside", screen = "1", doorX = "48"] = process.argv.slice(2);
const g = newOutside(0, 0, +screen, 100, 144);
const pal = () => ({bg: Array.from({length: 16}, (_, i) => g.nes.ppu.vramMem[0x3f00 + i]), sprite: Array.from({length: 16}, (_, i) => g.nes.ppu.vramMem[0x3f10 + i]), index: g.rd("Screen_PaletteIndex")});
const out = {outside: pal()};
g.wr("SpecialItems", 0xf0);
g.nes.buttonDown(1, BTN.UP);
let ok = false;
for (let f = 0; f < 90 && !ok; f++) {
  g.wr("Player_PosX_Block", +doorX);
  g.wr("Player_PosY", 144);
  g.run(1);
  ok = g.rd("Area_CurrentArea") === 4;
}
g.nes.buttonUp(1, BTN.UP);
if (!ok) throw new Error("did not get in");
g.runUntil(() => g.inPlay(), 300);
g.run(150);
out.inside = pal();
out.area = g.rd("Area_CurrentArea"); out.screen = g.rd("Area_CurrentScreen");
out.hero = {x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), armor: g.rd("SelectedArmor"), shield: g.rd("SelectedShield"), weapon: g.rd("SelectedWeapon")};
out.oam = g.oam();
fs.writeFileSync(prefix + ".json", JSON.stringify(out));
g.ppm(prefix + "_in.ppm");
fs.writeFileSync(prefix + "_in.chr.bin", Buffer.from(g.nes.ppu.vramMem.slice(0, 0x2000)));
