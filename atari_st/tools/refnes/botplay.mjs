// The ROM side of the side-by-side runs (tools/sidebyside.py): a game put in play, the start state of a segment written into the RAM (a cheat), the
// sprites of the screen loaded afresh (as the port has them at its first frame), then one pad a frame, from a bot or from a stream, and a trace of
// every frame in the record layout of src/replay.s.
//   node botplay.mjs SEGMENT.json OUTDIR
// SEGMENT: {lead ([[pad, frames], ...] pressed before the bot takes over), area, screen, region (for areas past Eolis), x, y, left (the sprite flip bit, $40 of Player_Flags), hp, mp, exp, gold, title, weapon, armour,
//   shield, magic, item, frames, policy ("fight" or "pads"), pads (a file of one pad a frame, for "pads"), png_every (0: none), heal (keep him alive), cast (Up and B every that many passes), jump}
// OUTDIR gets pads.bin (what was pressed, one byte a frame), trace.bin (REC bytes a frame, the state before the pad of that frame), and with png_every
// rom_NNNNN.ppm, the picture after frame NNNNN.
import {newTown, newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";
import path from "path";

const seg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outDir = process.argv[3];
fs.mkdirSync(outDir, {recursive: true});
const REC = 64;
const BITS = [[0x80, BTN.A], [0x40, BTN.B], [0x20, BTN.SELECT], [0x10, BTN.START], [0x08, BTN.UP], [0x04, BTN.DOWN], [0x02, BTN.LEFT], [0x01, BTN.RIGHT]];

let g;
if (seg.area) g = newOutside(seg.area, seg.region ?? 0, seg.screen, seg.x ?? 64, seg.y ?? 144);
else {
  g = newTown();
  if (seg.screen !== 1) {
    const walk = seg.screen >= 8 ? BTN.RIGHT : BTN.LEFT;
    g.nes.buttonDown(1, walk);
    if (!g.runUntil(() => g.rd("Area_CurrentScreen") === seg.screen && g.inPlay(), 4000)) throw new Error("not there: " + g.state());
    g.nes.buttonUp(1, walk);
  }
  g.run(4);
}
// the cheat: what he has and where he stands
const put = (label, v) => { if (v !== undefined) g.wr(label, v); };
put("Player_CurWeapon", seg.weapon); put("SelectedWeapon", seg.weapon); put("SelectedArmor", seg.armour); put("Player_ArmorLookupIndex", seg.armour);
put("SelectedShield", seg.shield); put("SelectedMagic", seg.magic); put("SelectedItem", seg.item); put("PlayerTitle", seg.title);
if (seg.exp !== undefined) { g.wr("Experience", seg.exp & 255); g.wr("Experience_U", seg.exp >> 8); }
if (seg.gold !== undefined) { g.wr("Gold", seg.gold & 255); g.wr("Gold_M", (seg.gold >> 8) & 255); g.wr("Gold_U", (seg.gold >> 16) & 255); }
g.call("UI_DrawPlayerHPValue", {a: seg.hp ?? 80});
g.call("Player_SetMP", {a: seg.mp ?? 80});
g.call("UI_DrawPlayerExperience");
g.call("UI_DrawGoldValue");
g.wr("Player_HP_L", 0);
// the hero at his place, standing, and the screen's sprites as a fresh load makes them: Screen_ClearSprites runs first, then Screen_LoadSpriteInfo (a call
// pushes its return address, so the routine called last runs first), in one frame with no buttons
g.wr("Player_PosX_Block", seg.x); g.wr("Player_PosY", seg.y);
g.wr("Player_Flags", seg.left ? 0x40 : 0);
const still = ["Player_PosX_Frac", "Player_MovementTick", "Player_InvincibilityPhase", "Player_StatusFlag", "Player_AttackPhaseAnimFrame", "Player_AttackPhaseTimer",
  "Player_MoveAcceleration", "Player_MoveAcceleration_U", "Player_JumpCurveIndex"];
for (const n of still) if (n in g.labels) g.wr(n, 0);
// run a routine now, from where the main loop waits, instruction by instruction until it has returned (no frame passes: the sprites are not updated)
function callNow(label) {
  const cpu = g.nes.cpu, back = cpu.REG_PC;
  cpu.push((back >> 8) & 255); cpu.push(back & 255);
  cpu.REG_PC = g.romLabels[label][0] - 1;
  for (let n = 0; n < 200000 && cpu.REG_PC !== back; n++) cpu.emulate();
  if (cpu.REG_PC !== back) throw new Error(label + " did not return");
}
// the fields Screen_LoadSpriteInfo leaves as they were (the fractions, the behaviour data): 0, as the port's enemies_load makes them (else the start
// differs by what the screen's enemies did before the cheat)
if (!seg.leftovers) for (const n of ["XPos_Frac", "YPos_Frac", "BehaviorArg1", "BehaviorData2", "BehaviorData3", "InternalBehaviorStates", "BehaviorState_XFrac",
  "BehaviorState_XFull", "BehaviorState_YFrac", "BehaviorState_YFull", "Values"])
  if (("CurrentSprites_" + n) in g.labels) for (let i = 0; i < 8; i++) g.wr(g.addr("CurrentSprites_" + n) + i, 0);
callNow("Screen_ClearSprites");
callNow("Screen_LoadSpriteInfo");
g.wr("Random_Offset", 0); g.wr("SpriteUpdateCounter", 0);

const slot = (i, n) => g.rd(g.addr("CurrentSprites_" + n) + i);
function record() {
  const b = Buffer.alloc(REC);
  b.writeUInt16BE(g.rd("Player_PosX_Block"), 0);
  b.writeUInt16BE(g.rd("Player_PosY"), 2);
  b[4] = (g.rd("Player_Flags") >> 6) & 1;
  b[5] = g.rd("Area_CurrentArea"); b[6] = g.rd("Area_CurrentScreen");
  b[7] = g.rd("Player_HP_U"); b[8] = g.rd("Player_MP"); b[9] = g.rd("Player_HP_L");
  b.writeUInt16BE(g.rd("Experience_U") << 8 | g.rd("Experience"), 10);
  b.writeUInt32BE(g.rd("Gold_U") << 16 | g.rd("Gold_M") << 8 | g.rd("Gold"), 12);
  for (let i = 0; i < 8; i++) {
    b[16 + i * 4] = slot(i, "Entities"); b[17 + i * 4] = slot(i, "XPos_Full"); b[18 + i * 4] = slot(i, "YPos"); b[19 + i * 4] = slot(i, "HP");
  }
  b[59] = g.rd(g.addr("CurrentSprites_XPos_Frac") + 6); b[60] = g.rd(g.addr("CurrentSprites_XPos_Frac") + 7);
  b[56] = g.rd("Player_PosX_Frac"); b[57] = g.rd("Player_MoveAcceleration_U"); b[58] = g.rd("Player_MoveAcceleration");
  b[48] = g.rd("Music_Current"); b[49] = g.rd("CastMagic_Type"); b[50] = g.rd("CastMagic_XPos_Full"); b[51] = g.rd("CastMagic_YPos_Full");
  return b;
}

// the bot: walk to the nearest enemy, swing when near, pick up what was dropped
const ITEMS = [1, 2];
function fight(f) {
  const hx = g.rd("Player_PosX_Block");
  let pad = 0;
  const live = [], drops = [];
  for (let i = 0; i < 8; i++) {
    const e = slot(i, "Entities"), x = slot(i, "XPos_Full");
    if (e === 255 || e === 0x13 || e === 0x14) continue;
    (ITEMS.includes(e) ? drops : live).push(x);
  }
  if (live.length) {
    const t = live.reduce((a, b) => (Math.abs(a - hx) <= Math.abs(b - hx) ? a : b));
    const dx = t - hx, reach = seg.reach ?? 30;
    if (Math.abs(dx) > reach - 8 || (Math.abs(dx) > 6 && f % 24 === 0)) pad |= dx > 0 ? 0x01 : 0x02;
    if (Math.abs(dx) <= reach && f % 24 < 2) pad |= 0x40;
    if (seg.jump && Math.abs(dx) <= reach && f % 48 === 30) pad |= 0x80;
    if (seg.cast && f % seg.cast === seg.cast - 1) pad = (dx > 0 ? 0x01 : 0x02) | 0x08 | 0x40;   // (cast: every `cast` passes Up and B, facing the enemy: the B before it is let go by f % 24)
  } else if (drops.length) {
    const dx = drops[0] - hx;
    if (Math.abs(dx) > 3) pad |= dx > 0 ? 0x01 : 0x02;
  }
  return pad;
}

// One pad a pass of the game loop, given where the loop has the buttons the NMI read (Game_MainLoop, after WaitForNextFrame): there the state is recorded
// (the state after the pass before), the pad is chosen, and Joy1_ButtonMask and Joy1_ChangedButtonMask are made from it as Input_HandleOnInterrupt does
// (the controller is set to it as well, so the next NMI reads it as the previous mask). A pass of the port's loop is one poll (src/replay.s): record k
// of both is the state after k passes. Frames in which the loop does not pass there (a scroll, a box, a door) take no pad.
const given = seg.policy === "pads" ? fs.readFileSync(seg.pads) : null;
const frames = given ? Math.min(seg.frames ?? given.length, given.length) : seg.frames;
const pads = Buffer.alloc(frames), trace = Buffer.alloc(frames * REC);
const hook = g.romLabels["Game_MainLoop"][0] + 11 - 1;               // (LDX, TXS, LDX, JSR MMC1_UpdateROMBank, JSR WaitForNextFrame: 11 bytes)
let passes = 0, idle = 0;
const cpu = g.nes.cpu, emulate = cpu.emulate.bind(cpu);
cpu.emulate = function () {
  if (cpu.REG_PC === hook && passes < frames && g.rd("Screen_ScrollDirection") === 0xff && !g.rd("PlayerIsDead")) {
    idle = 0;
    const f = passes++;
    record().copy(trace, f * REC);
    let pad = given ? given[f] : fight(f);
    let lead = 0;                                                    // (seg.lead: [[pad, frames], ...] pressed first, then the bot)
    for (const [p, n] of seg.lead ?? []) { if (f < lead + n) { pad = p; break; } lead += n; }
    pads[f] = pad;
    const prev = g.rd("Joy1_PrevButtonMask");
    g.wr("Joy1_ButtonMask", pad); g.wr("Joy1_ChangedButtonMask", pad & ~prev & 255);
    for (const [bit, btn] of BITS) (pad & bit ? g.nes.buttonDown : g.nes.buttonUp).call(g.nes, 1, btn);
    if (seg.heal && g.rd("Player_HP_U") < 40) g.wr("Player_HP_U", 80);
  }
  return emulate();
};
let shot = 0;
for (let n = 0; passes < frames && n < frames * 4 + 1000; n++) {
  // a frame that is no pass (a box, a scroll, a death): A every eighth frame takes messages away, as the port's replay does
  if (++idle > 2) for (const [bit, btn] of BITS) (bit === 0x80 && (n & 12) === 12 ? g.nes.buttonDown : g.nes.buttonUp).call(g.nes, 1, btn);
  g.run(1);
  if (seg.png_every && Math.floor(passes / seg.png_every) > shot) {
    shot = Math.floor(passes / seg.png_every);
    g.ppm(path.join(outDir, `rom_${String(shot * seg.png_every).padStart(5, "0")}.ppm`));
  }
}
fs.writeFileSync(path.join(outDir, "pads.bin"), pads.subarray(0, passes));
fs.writeFileSync(path.join(outDir, "trace.bin"), trace.subarray(0, passes * REC));
console.log(JSON.stringify({frames: passes, start: g.state()}));
