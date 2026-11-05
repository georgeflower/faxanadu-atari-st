// The hero in motion, frame by frame: with the given equipment the harness walks right and left, crouches, attacks and jumps in Eolis,
// and records after every frame the sprites jsnes holds and the state the game draws them from.
//   node herowalk.mjs ARMOR SHIELD WEAPON OUT.json
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [armor, shield, weapon, out = "/tmp/herowalk.json"] = process.argv.slice(2, 6);
const g = newGame();
g.wr("SelectedArmor", Number(armor)); g.wr("SelectedShield", Number(shield));
g.wr("SelectedWeapon", Number(weapon)); g.wr("Player_CurWeapon", Number(weapon));
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
g.nes.buttonUp(1, BTN.UP);
g.run(40);

const frames = [];
const snap = () => frames.push({
  oam: g.oam().filter((e, i) => i > 0 && e[0] < 0xef),
  x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"),
  attack: g.rd("Player_AttackPhaseAnimFrame"), scrollX: g.rd("PPU_ScrollX"), status: g.rd("Player_StatusFlag"), joy: g.rd("Joy1_ButtonMask"),
});
const act = (buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b); for (let i = 0; i < n; i++) { g.run(1); snap(); } for (const b of buttons) g.nes.buttonUp(1, b); };
act([], 10);
act([BTN.RIGHT], 50);
act([], 10);
act([BTN.LEFT], 40);
act([BTN.DOWN], 15);
act([], 10);
act([BTN.B], 3); act([], 30);
act([BTN.A], 3); act([], 50);
act([BTN.RIGHT, BTN.A], 40);
act([BTN.DOWN, BTN.B], 10); act([], 30);
fs.writeFileSync(out, JSON.stringify(frames));
console.log(frames.length, "frames");
