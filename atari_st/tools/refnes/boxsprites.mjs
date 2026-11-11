// Are the enemies in the OAM while the game stands for a box? The player menu (Select ... B) on a screen with enemies.
//   node boxsprites.mjs AREA SCREEN X
// Prints, every frame from Select on, the number of sprites in jsnes' OAM that are not the hero's (tiles below $40 are the hero's pattern tiles; the enemies' are $40 and up
// is not true for every kind, so the count is of all sprites on the screen, with the hero's count at the start for reference) and the enemies' x positions.
import {newTown, BTN} from "./faxanadu.mjs";

// Eolis screen SCREEN (left of the town, as combatprobe.mjs walks there); KIND = menu (Select, B) or item (Down+B with ITEM in hand, A to dismiss).
const screen = +(process.argv[2] ?? 4), kind = process.argv[3] ?? "menu", item = +(process.argv[4] ?? 0);
const g = newTown();
g.nes.buttonDown(1, BTN.LEFT);
if (!g.runUntil(() => g.rd("Area_CurrentScreen") === screen && g.inPlay(), 3000)) throw new Error("not there");
g.nes.buttonUp(1, BTN.LEFT);
g.run(10);
g.wr("Player_HP_U", 80);
const shown = () => g.oam().filter((o) => o[0] < 239).length;
const xs = () => [0, 1, 2, 3, 4, 5, 6, 7].map((i) => g.rd(g.addr("CurrentSprites_Entities") + i)).join(",");
const line = (f, what) => console.log(`${f} ${what} sprites=${shown()} entities=${xs()}`);
line(0, "before");
let f = 1;
if (kind === "menu") {
  g.nes.buttonDown(1, BTN.SELECT); g.run(1); g.nes.buttonUp(1, BTN.SELECT);
  for (; f < 60; f++) { g.run(1); if (f % 5 === 0 || f < 6) line(f, "menu"); }
  g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B);
} else {
  g.wr("SelectedItem", item);
  g.nes.buttonDown(1, BTN.DOWN); g.run(1); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.DOWN);
  for (; f < 200; f++) { if (f % 40 === 30) g.nes.buttonDown(1, BTN.A); if (f % 40 === 33) g.nes.buttonUp(1, BTN.A); g.run(1); if (f % 5 === 0 || f < 6) line(f, "box"); }
}
for (let i = 0; i < 20; i++, f++) { g.run(1); line(f, "after"); }
