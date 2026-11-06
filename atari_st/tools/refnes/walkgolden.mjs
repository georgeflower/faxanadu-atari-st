// The hero's horizontal walking, frame by frame (golden run for tools/hero_physics.py): in Eolis screen 1 the harness stands still,
// walks right, stands, walks left, stands, and records the position, the acceleration, the flags and the buttons after every frame.
//   node walkgolden.mjs OUT.json
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2] ?? "/tmp/walkgolden.json";
const g = newGame();
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
g.nes.buttonUp(1, BTN.UP);
g.run(40);

const frames = [];
const snap = (pad) => frames.push({
  pad, x: g.rd("Player_PosX_Block"), frac: g.rd("Player_PosX_Frac"), y: g.rd("Player_PosY"),
  acc: g.rd("Player_MoveAcceleration"), accU: g.rd("Player_MoveAcceleration_U"),
  flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"), joy: g.rd("Joy1_ButtonMask"),
  title: g.rd("PlayerTitle"), status: g.rd("Player_StatusFlag"),
});
const act = (buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b);
  for (let i = 0; i < n; i++) { g.run(1); snap(buttons.reduce((a, b) => a | b, 0)); }
  for (const b of buttons) g.nes.buttonUp(1, b); };
act([], 8);
act([BTN.RIGHT], 45);
act([], 8);
act([BTN.LEFT], 70);
act([], 5);
act([BTN.RIGHT], 12);
act([BTN.LEFT], 12);
act([], 5);
fs.writeFileSync(out, JSON.stringify(frames));
console.log(frames.length, "frames; start", JSON.stringify(frames[0]));
