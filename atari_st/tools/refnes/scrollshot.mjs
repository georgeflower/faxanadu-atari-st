// The ROM's scroll between screens, recorded: walk to the edge of Eolis screen 1 and scroll to the screen on the side, and write for every
// frame of the scroll the sprites, the scroll registers and the hero's state (JSON), and a picture (PPM) of every fourth frame.
//   node scrollshot.mjs RIGHT|LEFT OUTDIR
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const dir = (process.argv[2] || "RIGHT").toUpperCase();
const out = process.argv[3] || "/tmp/scroll";
fs.mkdirSync(out, {recursive: true});
const g = newTown();
g.wr("Player_PosX_Block", dir === "RIGHT" ? 226 : 20);
g.run(5);
g.nes.buttonDown(1, BTN[dir]);
let begun = false;
for (let t = 0; t < 900 && !begun; t++) { g.run(1); begun = g.rd("Screen_ScrollDirection") !== 0xff; }
g.nes.buttonUp(1, BTN[dir]);
if (!begun) throw new Error("no scroll");
const frames = [];
const from = g.rd("Area_CurrentScreen");
for (let n = 0; n < 200 && g.rd("Screen_ScrollDirection") !== 0xff; n++) {
  g.run(1);
  const row = {n, scrollX: g.rd("PPU_ScrollX"), scrollScreen: g.rd("PPU_ScrollScreen"), x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"),
    screen: g.rd("Area_CurrentScreen"), flags: g.rd("Player_Flags"), oam: g.oam().filter((e, i) => e[0] < 0xef)};
  frames.push(row);
  if (n % 4 === 3) g.ppm(`${out}/frame${String(n + 1).padStart(3, "0")}.ppm`);
}
g.run(2);
fs.writeFileSync(`${out}/scroll.json`, JSON.stringify({dir, from, to: g.rd("Area_CurrentScreen"), frames}));
console.log(dir, "from", from, "to", g.rd("Area_CurrentScreen"), frames.length, "frames");
