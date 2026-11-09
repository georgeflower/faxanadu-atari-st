// Records what the ROM's sound engine writes to the NES sound chip ($4000-$4017), frame by frame, for one music id or sound effect.
//   node soundrec.mjs music ID FRAMES OUT.json
//   node soundrec.mjs sfx   ID FRAMES OUT.json
// The game is in play (Eolis); the id is put in Music_Current / passed to SoundEffect_SetCurrent as the game's own code would.
// `handler` is the sound effect engine's own note of what it runs after each frame (SoundEffect_HandlerIndex: 0 nothing; otherwise the effect's
// handler index, which is its priority: the engine refuses a new effect whose index is higher), see soundpair.mjs and AGENTS.md 5f.
import {newGame} from "./faxanadu.mjs";
import fs from "fs";

const [kind, idArg, framesArg, out] = process.argv.slice(2);
const id = Number(idArg), frames = Number(framesArg);
const g = newGame();
const papu = g.nes.papu, orig = papu.writeReg.bind(papu);
let cur = 0; const log = [];
papu.writeReg = (a, v) => { if (a >= 0x4000 && a <= 0x4017) log.push([cur, a, v]); return orig(a, v); };
// silence first: whatever the area music is doing is stopped
g.wr("Music_Current", 0); g.wr("SoundEffect_Current", 0); g.run(4);
log.length = 0;
if (kind === "music") g.wr("Music_Current", id);
else g.call("SoundEffect_SetCurrent", {a: id}, 0);
// What each channel sounds like at the end of every frame (jsnes has already applied length counters, sweep and envelopes):
// [period, volume, duty] for the two pulse channels, [period, on] for the triangle, [period, volume, mode] for the noise.
const mc = [], st = [], hi = [];
const sq = (c) => (c.isEnabled && (c.lengthCounter > 0 || !c.lengthCounterEnable) && c.progTimerMax >= 8 ? [c.progTimerMax, c.masterVolume, c.dutyMode] : [0, 0, 0]);
for (cur = 0; cur < frames; cur++) {
  g.run(1); mc.push(g.rd("Music_Current")); hi.push(g.rd("SoundEffect_HandlerIndex"));
  const p = papu, t = p.triangle, n = p.noise;
  st.push([sq(p.square1), sq(p.square2),
    [t.progTimerMax, t.isEnabled && (t.lengthCounter > 0 || !t.lengthCounterEnable) && t.linearCounter > 0 ? 1 : 0],
    [n.progTimerMax, n.isEnabled && (n.lengthCounter > 0 || !n.lengthCounterEnable) ? n.masterVolume : 0, n.randomMode]]);
}
fs.writeFileSync(out, JSON.stringify({kind, id, frames, writes: log, musicCurrent: mc, state: st, handler: hi}));
console.log(kind, id, "writes", log.length, "last Music_Current", mc[mc.length - 1].toString(16));
