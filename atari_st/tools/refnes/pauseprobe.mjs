// The Start pause (GameLoop_CheckPauseGame, Audio_HandlePaused): Eolis screen 1, the song playing; a sound effect ($08, a pickup) is asked for a few frames before Start.
// Per frame: Game_PausedState, Music_Current, the song's place (Music_* pointers, as a hash of the music RAM), the hero's x, and what the four channels sound.
//   node pauseprobe.mjs   prints RESULT [[frame, paused, x, channels, musicstate], ...] (frame 0 is the frame Start goes down)
import {newOutside, BTN} from "./faxanadu.mjs";
const g = newOutside(0, 0, 1, 64, 144);
g.run(120);
const sq = (c) => (c.isEnabled && (c.lengthCounter > 0 || !c.lengthCounterEnable) && c.progTimerMax >= 8 ? [c.progTimerMax, c.masterVolume] : [0, 0]);
const chan = () => { const p = g.nes.papu, t = p.triangle; return [sq(p.square1), sq(p.square2), t.isEnabled && (t.lengthCounter > 0 || !t.lengthCounterEnable) && t.linearCounter > 0 ? 1 : 0, p.noise.isEnabled ? p.noise.masterVolume : 0]; };
const mstate = () => { let h = 0; for (let a = 0xC0; a < 0x100; a++) h = (h * 31 + g.nes.cpu.mem[a]) >>> 0; return h; };
const rows = [];
const sfx = Number(process.argv[2] ?? 8);
g.nes.buttonDown(1, BTN.RIGHT);
g.run(20);
if (sfx) g.wr("SoundEffect_Current", sfx);
g.run(3);
for (let f = 0; f < 140; f++) {
  if (f === 0) g.nes.buttonDown(1, BTN.START);
  if (f === 3) g.nes.buttonUp(1, BTN.START);
  if (f === 100) g.nes.buttonDown(1, BTN.START);
  if (f === 103) g.nes.buttonUp(1, BTN.START);
  g.run(1);
  rows.push([f, g.rd("Game_PausedState"), g.rd("Player_PosX_Block"), chan(), g.rd("Music_Current")]);
}
for (const r of rows) console.log(JSON.stringify(r));
console.log("RESULT " + JSON.stringify(rows));
process.exit(0);
