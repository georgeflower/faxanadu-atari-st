// Fights, frame by frame: into Eolis, to a screen with enemies, and the hero walks to the nearest one and attacks it with the sword. For every frame the
// slots, the experience, the gold, the power, and the hero as `Sprites_UpdateAll` sees him (his state is read when the routine is entered, so what the
// sprites do to him in the same frame is not in it) are recorded.
//   node combatprobe.mjs SCREEN FRAMES OUT.json [WEAPON] [ARMOUR]
import {newTown, newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const screen = +(process.argv[2] ?? 4), frames = +(process.argv[3] ?? 600), out = process.argv[4], weapon = +(process.argv[5] ?? 1), armour = +(process.argv[6] ?? 0);
// AREA=n (and REGION, HEROX) puts the hero on the screen of another area through a temple; without it he walks there from the first screen of Eolis.
const area = +(process.env.AREA ?? 0);
let g;
if (area) g = newOutside(area, +(process.env.REGION ?? 0), screen, +(process.env.HEROX ?? 64));
else {
  g = newTown();
  const walk = screen === 8 ? BTN.RIGHT : BTN.LEFT;
  g.nes.buttonDown(1, walk);
  if (!g.runUntil(() => g.rd("Area_CurrentScreen") === screen && g.inPlay(), 3000)) throw new Error("not there: " + g.state());
  g.nes.buttonUp(1, walk);
}
g.wr("Player_CurWeapon", weapon); g.wr("SelectedWeapon", weapon); g.wr("SelectedArmor", armour); g.wr("Player_ArmorLookupIndex", armour);
g.wr("Player_HP_U", 80); g.wr("Player_HP_L", 0);

const names = ["Entities", "Behaviors", "Flags", "Phases", "BehaviorData2", "BehaviorData3", "BehaviorArg1", "HP", "HitCounter", "HitBoxTypes", "InternalBehaviorStates",
  "HitByMagicBehavior", "Values", "BehaviorState_XFull", "BehaviorState_YFull", "BehaviorState_XFrac", "BehaviorState_YFrac", "BehaviorAddrs_L", "BehaviorAddrs_U", "PPUOffsets"];
const hero = () => ({x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), atk: g.rd("Player_AttackPhaseAnimFrame"),
  wx: g.rd("PlayerPosXPlus10"), wy: g.rd("Maybe_Something_WeaponPosY"), rx: g.rd("Maybe_WeaponRange_X"), ry: g.rd("Maybe_WeaponRange_Y"),
  inv: g.rd("Player_InvincibilityPhase"), status: g.rd("Player_StatusFlag"), hpU: g.rd("Player_HP_U"), hpL: g.rd("Player_HP_L"), weapon: g.rd("Player_CurWeapon")});
const slotsNow = () => {
  const slots = [];
  for (let i = 0; i < 8; i++) {
    const s = {x: g.rd(g.addr("CurrentSprites_XPos_Full") + i), xf: g.rd(g.addr("CurrentSprites_XPos_Frac") + i), y: g.rd(g.addr("CurrentSprites_YPos") + i), yf: g.rd(g.addr("CurrentSprites_YPos_Frac") + i)};
    for (const n of names) s[n] = g.rd(g.addr("CurrentSprites_" + n) + i);
    slots.push(s);
  }
  return slots;
};
// the hero as the sprites see him: read when Sprites_UpdateAll is entered
const ENEMIES = [0x47, 0x2A, 0x0C, 0x06, 0x26, 0x1B, 0x15, 0x04, 0x19, 0x28, 0x1E, 0x20, 0x17, 0x08, 0x1F, 0x21, 0x1C, 0x22, 0x1A, 0x18, 0x05, 0x0D, 0x23, 0x2C, 0x10, 0x0E, 0x11, 0x2F, 0x2D, 0x32];        // Zozura ... Geributa, Bihoruda, Sir Gawaine, Wolfman, Naga, Yareeka: what the hero fights
const JUMP = !!process.env.JUMP;
const REACH = +(process.env.REACH ?? 30);      // (how near the hero must be to swing: 30, a boss needs less)
let pre = null, preSlots = null, preState = null;
const entry = g.romLabels["Sprites_UpdateAll"][0] - 1, cpu = g.nes.cpu, emulate = cpu.emulate.bind(cpu);
cpu.emulate = function () {
  if (cpu.REG_PC === entry && g.rd("CurrentROMBank") === 14) {
    pre = hero(); preSlots = slotsNow();
    preState = {rnd: g.rd("Random_Offset"), mask: g.rd("Joy1_ButtonMask"), counter: g.rd("SpriteUpdateCounter")};
  }
  return emulate();
};
const rec = [];
let blocks = null;
for (let f = 0; f < frames; f++) {
  // the pad: walk to the nearest enemy, attack when near (B pressed for two frames out of 24)
  const h = hero(), live = slotsNow().filter((s) => ENEMIES.includes(s.Entities));
  g.nes.buttonUp(1, BTN.LEFT); g.nes.buttonUp(1, BTN.RIGHT); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.A);
  const items = slotsNow().filter((s) => s.Entities === 1 || s.Entities === 2);
  if (!live.length && items.length) {                       // nothing to fight: pick up what was dropped
    const dx = items[0].x - h.x;
    if (Math.abs(dx) > 3) g.nes.buttonDown(1, dx > 0 ? BTN.RIGHT : BTN.LEFT);
  } else if (live.length) {
    const t = live.reduce((a, b) => (Math.abs(a.x - h.x) <= Math.abs(b.x - h.x) ? a : b));
    const dx = t.x - h.x;
    if (Math.abs(dx) > REACH - 8) g.nes.buttonDown(1, dx > 0 ? BTN.RIGHT : BTN.LEFT);
    else if (Math.abs(dx) > 6 && f % 24 === 0) g.nes.buttonDown(1, dx > 0 ? BTN.RIGHT : BTN.LEFT);
    if (JUMP) {                                              // (a tall enemy is hit from the air: jump, swing at the top of the jump)
      if (Math.abs(dx) <= REACH && f % 40 < 2) g.nes.buttonDown(1, BTN.A);
      if (Math.abs(dx) <= REACH && f % 40 >= 12 && f % 40 < 14) g.nes.buttonDown(1, BTN.B);
    } else if (Math.abs(dx) <= REACH && f % 24 < 2) g.nes.buttonDown(1, BTN.B);
  }
  if (process.env.HEAL && g.rd("Player_HP_U") < 40) { g.wr("Player_HP_U", 80); g.wr("Player_HP_L", 0); }      // (a boss hits hard: the run goes on while he is cured now and then)
  pre = null;
  g.run(1);
  if (!blocks) blocks = Array.from({length: 256}, (_, i) => g.rd(g.addr("ScreenBuffer") + i));
  rec.push({f, pre, preSlots, ...preState, hero: hero(), exp: g.rd("Experience_U") << 8 | g.rd("Experience"), gold: g.rd("Gold_U") << 16 | g.rd("Gold_M") << 8 | g.rd("Gold"),
    ic: g.rd("InterruptCounter"), counter: g.rd("SpriteUpdateCounter"), slots: slotsNow(), scroll: g.rd("Screen_ScrollDirection"), dead: g.rd("PlayerIsDead"),
    oam: g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x40)});
}
const start = {screen, weapon, armour, special: g.rd("SpecialItems"), glove: g.rd("DurationGlove"), ointment: g.rd("DurationOintment"), blocks};
if (out) fs.writeFileSync(out, JSON.stringify({start, frames: rec}));
for (const r of rec.slice(0, 400)) {
  const live = r.slots.map((s, i) => [i, s]).filter(([, s]) => s.Entities !== 255);
  console.log(r.f, `hero ${r.hero.x},${r.hero.y} f${r.hero.flags.toString(16)} a${r.hero.atk} hp${r.hero.hpU} exp${r.exp} gold${r.gold} inv${r.hero.inv}`, live.map(([i, s]) => `#${i} e${s.Entities} (${s.x},${s.y}) hp${s.HP} h${s.HitCounter}`).join(" | "));
}
