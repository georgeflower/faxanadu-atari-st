// The hero on a real ladder, frame by frame: Mist screen 0 (area 2) has a ladder in column 2 (rows 10 to 12; the hero stands on it at x 32). With the given equipment and facing
// he stands, climbs up with Up held, stands on the ladder, climbs down with Down held, and after every frame the sprites jsnes holds and the state the game draws them from are recorded.
//   node ladderprobe.mjs ARMOR SHIELD WEAPON FACING(0 right|1 left) OUT.json [x y]
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [armor, shield, weapon, facing, out = "/tmp/ladderprobe.json", x0 = "32", y0 = "170"] = process.argv.slice(2);
const g = newOutside(2, 2, 0, +x0, +y0);
g.wr("SelectedArmor", +armor); g.wr("SelectedShield", +shield); g.wr("SelectedWeapon", +weapon); g.wr("Player_CurWeapon", +weapon);
g.run(5);
g.wr("Player_Flags", (g.rd("Player_Flags") & ~0x40) | (+facing ? 0x40 : 0));
g.run(3);
const frames = [];
const snap = (phase) => frames.push({
  phase, oam: g.oam().filter((e, i) => i > 0 && e[0] < 0xef),
  x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"),
  attack: g.rd("Player_AttackPhaseAnimFrame"), scrollX: g.rd("PPU_ScrollX"), status: g.rd("Player_StatusFlag"), joy: g.rd("Joy1_ButtonMask"),
});
const act = (name, buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b); for (let i = 0; i < n; i++) { g.run(1); snap(name); } for (const b of buttons) g.nes.buttonUp(1, b); };
act("stand", [], 8);
act("up", [BTN.UP], 70);
act("hang", [], 12);
act("down", [BTN.DOWN], 60);
act("end", [], 12);
fs.writeFileSync(out, JSON.stringify(frames));
console.log(frames.length, "frames");
