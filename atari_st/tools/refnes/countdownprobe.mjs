// The glove's and the ointment's time running out, as the game does it: a quiet screen, DurationGlove and DurationOintment preset, A pressed now and then
// to dismiss the "is gone" messages; every change of the two is recorded with the frame and the interrupt counter (the ROM counts every 64th interrupt).
//   node countdownprobe.mjs GLOVE OINTMENT FRAMES OUT.json
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [glove, ointment, frames] = process.argv.slice(2, 5).map(Number), out = process.argv[5];
const g = newOutside(0, 0, 1, 100, 144);
g.wr("DurationGlove", glove); g.wr("DurationOintment", ointment);
const log = [], iscripts = [], cpu = g.nes.cpu, emulate = cpu.emulate.bind(cpu);
const begin = g.romLabels["IScripts_Begin"] ? g.romLabels["IScripts_Begin"][0] - 1 : -1;
cpu.emulate = function () { if (cpu.REG_PC === begin) iscripts.push([g.frames, cpu.REG_ACC, g.rd("InterruptCounter")]); return emulate(); };
let last = [glove, ointment];
for (let f = 0; f < frames; f++) {
  g.nes.buttonUp(1, BTN.A);
  if (f % 30 === 20) g.nes.buttonDown(1, BTN.A);
  g.run(1);
  const now = [g.rd("DurationGlove"), g.rd("DurationOintment")];
  if (now[0] !== last[0] || now[1] !== last[1]) { log.push([f, g.rd("InterruptCounter"), ...now]); last = now; }
}
fs.writeFileSync(out, JSON.stringify({log, iscripts}));
