// The HUD as the game draws it for chosen values: the harness sets the values and runs the game's own drawing routines.
//   node hudshot.mjs HP MP EXPERIENCE GOLD SECONDS     -> JSON {rows: [2 rows of 32 tile ids], power: [16 bytes], magic: [16 bytes]}
import {newTown} from "./faxanadu.mjs";

const [hp, mp, exp, gold, secs] = process.argv.slice(2, 7).map(Number);
const g = newTown();
g.wr("Experience", exp & 255); g.wr("Experience_U", (exp >> 8) & 255);
g.wr("Gold", gold & 255); g.wr("Gold_M", (gold >> 8) & 255); g.wr("Gold_U", (gold >> 16) & 255);
g.call("UI_DrawPlayerHPValue", {a: hp});
g.call("Player_SetMP", {a: mp});
g.call("UI_DrawPlayerExperience");
g.call("UI_DrawGoldValue");
g.call("UI_DrawTimeValue", {a: secs});
g.run(3);
const v = g.nes.ppu.vramMem;
const row = (r) => Array.from(v.slice(0x2000 + r * 32, 0x2000 + r * 32 + 32));
console.log(JSON.stringify({rows: [row(2), row(3)], power: Array.from(v.slice(0x10c0, 0x10d0)), magic: Array.from(v.slice(0x10d0, 0x10e0))}));
