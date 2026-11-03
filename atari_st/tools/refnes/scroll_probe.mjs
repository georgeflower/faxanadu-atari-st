// How the ROM scrolls between screens: walk to the edge of the first screen and record the scroll frame by frame.
//   node scroll_probe.mjs [RIGHT|LEFT|UP|DOWN] [max frames]
import {newTown, BTN} from "./faxanadu.mjs";

const dir = (process.argv[2] || "RIGHT").toUpperCase();
const max = +(process.argv[3] || 900);
const g = newTown();
console.log("start:", g.state());

// Put the hero near the edge he walks off (the walk itself is slow and has text boxes on the way), then hold the direction.
const EDGE = {RIGHT: ["Player_PosX_Block", 226], LEFT: ["Player_PosX_Block", 20], UP: ["Player_PosY", 40], DOWN: ["Player_PosY", 200]};
g.wr(EDGE[dir][0], EDGE[dir][1]);
g.run(5);
console.log("moved to:", g.state());
let begun = false;
g.nes.buttonDown(1, BTN[dir]);
for (let t = 0; t < max && !begun; t += 20) {
  g.run(17);
  g.nes.buttonDown(1, BTN.A); g.run(3); g.nes.buttonUp(1, BTN.A);
  begun = g.rd("Screen_ScrollDirection") !== 0xff;
}
if (!begun) {
  g.nes.buttonUp(1, BTN[dir]);
  console.log("no scroll within", max, "frames:", g.state());
  process.exit(1);
}
g.nes.buttonUp(1, BTN[dir]);
console.log("scroll begins:", g.state());

const rows = [];
let frames = 0;
let last = g.rd("PPU_ScrollX") + 256 * g.rd("PPU_ScrollScreen");
while (g.rd("Screen_ScrollDirection") !== 0xff && frames < 400) {
  g.run(1);
  frames++;
  const at = g.rd("PPU_ScrollX") + 256 * g.rd("PPU_ScrollScreen");
  rows.push({frame: frames, scrollX: g.rd("PPU_ScrollX"), screen: g.rd("PPU_ScrollScreen"), scrollY: g.rd("PPU_ScrollY"),
    dx: at - last, playerX: g.rd("Player_PosX_Block")});
  last = at;
}
console.log("scroll frames:", frames);
const deltas = new Map();
for (const r of rows) deltas.set(r.dx, (deltas.get(r.dx) || 0) + 1);
console.log("scrollX change per frame (change: frames):", [...deltas].map(([k, v]) => `${k}: ${v}`).join(", "));
console.log("first 6:", JSON.stringify(rows.slice(0, 6)));
console.log("last 4:", JSON.stringify(rows.slice(-4)));
g.run(10);
console.log("after:", g.state());
