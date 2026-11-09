// Two sound effects started one after the other, as the game's own code does it (SoundEffect_SetCurrent), frame by frame: what the ROM's sound engine
// writes to the sound chip (the same per-frame channel state as soundrec.mjs) and the engine's own bookkeeping: the handler index of the effect it is running
// (SoundEffect_HandlerIndex, 0 when nothing runs: the engine refuses a new effect whose handler index is higher than that of the one that is running).
//   node soundpair.mjs single OUT.json FRAMES        every effect alone
//   node soundpair.mjs pairs OUT.json FRAMES D1,D2,.. [A1,A2,.. [B1,B2,..]]    effect A, D frames later effect B (all effects when the lists are left out);
//     the result is keyed "A,D,B": `pre` is the handler index after each of the D frames of A, `rec` the handler index and channels after each of FRAMES frames
//     from the one in which B is asked for (the game asks after the frame's interrupt, so the engine takes B at rec[1]).
// The game is in play (Eolis) with the music off.
import {newGame} from "./faxanadu.mjs";
import fs from "fs";

const [mode, out, framesArg, delaysArg] = process.argv.slice(2, 6);
const frames = Number(framesArg);
const g = newGame();
g.wr("Music_Current", 0); g.wr("SoundEffect_Current", 0); g.run(6);
const base = g.nes.toJSON();
const sq = (c) => (c.isEnabled && (c.lengthCounter > 0 || !c.lengthCounterEnable) && c.progTimerMax >= 8 ? [c.progTimerMax, c.masterVolume, c.dutyMode] : [0, 0, 0]);
const chan = () => {
  const papu = g.nes.papu, t = papu.triangle, n = papu.noise;
  return [sq(papu.square1), sq(papu.square2),
    [t.progTimerMax, t.isEnabled && (t.lengthCounter > 0 || !t.lengthCounterEnable) && t.linearCounter > 0 ? 1 : 0],
    [n.progTimerMax, n.isEnabled && (n.lengthCounter > 0 || !n.lengthCounterEnable) ? n.masterVolume : 0, n.randomMode]];
};
const start = (id) => g.call("SoundEffect_SetCurrent", {a: id}, 0);
const step = (n, rec) => { for (let i = 0; i < n; i++) { g.run(1); if (rec) rec.push([g.rd("SoundEffect_HandlerIndex"), chan()]); } };
if (mode === "single") {
  const res = {};
  for (let id = 1; id <= 28; id++) {
    g.nes.fromJSON(base);
    const rec = [];
    start(id); step(frames, rec);
    res[id] = rec;
  }
  fs.writeFileSync(out, JSON.stringify(res));
} else {
  const delays = delaysArg.split(",").map(Number);
  const list = (arg) => arg ? arg.split(",").map(Number) : Array.from({length: 28}, (_, i) => i + 1);
  const as = list(process.argv[6]), bs = list(process.argv[7]);
  const res = {};
  for (const a of as) for (const d of delays) {
    g.nes.fromJSON(base);
    start(a); const pre = []; step(d, pre);
    const mid = g.nes.toJSON();
    for (const b of bs) {
      g.nes.fromJSON(mid);
      const rec = [];
      start(b); step(frames, rec);
      res[`${a},${d},${b}`] = {pre: pre.map((p) => p[0]), rec};
    }
  }
  fs.writeFileSync(out, JSON.stringify(res));
}
console.log("done", mode);
