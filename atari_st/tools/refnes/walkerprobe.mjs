// The walking man of Eolis ($34) in the ROM, frame by frame: his x (full and fraction), his flags (bit 0: facing right), the behaviour he runs ($04 walk, $15 wait) and its
// countdown, and the hero's x, for the frames of a walk; the Python test (tests/test_iscript_model.py) reads the pattern from it.
//   node walkerprobe.mjs OUT.json [FRAMES]
import {newTown} from "./faxanadu.mjs";
import fs from "fs";

const g = newTown();
const slot = 7;
const A = (n) => g.addr("CurrentSprites_" + n) + slot;
const rows = [];
for (let f = 0; f < Number(process.argv[3] ?? 700); f++) {
  g.run(1);
  rows.push({x: g.rd(A("XPos_Full")), frac: g.rd(A("XPos_Frac")), flags: g.rd(A("Flags")), beh: g.rd(A("Behaviors")), arg: g.rd(A("BehaviorArg1")), phase: g.rd(A("Phases")),
             entity: g.rd(A("Entities")), hero: g.rd("Player_PosX_Block")});
}
fs.writeFileSync(process.argv[2], JSON.stringify(rows));
