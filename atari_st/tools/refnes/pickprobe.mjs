// Picking up an item, as the game does it: the hero is put on the item, the game runs, A is pressed now and then to dismiss the message, and the
// inventory, the special items, the quests, the durations, the experience, the gold, the power and the sound effects played are recorded before and after.
//   node pickprobe.mjs AREA SCREEN ITEM_X ITEM_Y OUT.json [PRESET]     (ITEM_X, ITEM_Y: where the item stands; PRESET: a JSON of RAM labels to set first)
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [area, screen, ix, iy] = process.argv.slice(2, 6).map(Number), out = process.argv[6], preset = process.argv[7] ? JSON.parse(process.argv[7]) : {};
const g = newOutside(area, 0, screen, Math.max(0, ix - 40), 144);
const ARR = {WeaponInventory: 4, ArmorInventory: 4, ShieldInventory: 4, MagicInventory: 4, ItemInventory: 8};
const ONE = ["SelectedWeapon", "SelectedArmor", "SelectedShield", "SelectedMagic", "SelectedItem", "NumberOfWeapons", "NumberOfArmors", "NumberOfShields", "NumberOfMagicSpells", "NumberOfItems",
  "SpecialItems", "Quests", "DurationOintment", "DurationGlove", "DurationWingBoots", "DurationHourGlass", "Experience", "Experience_U", "Gold", "Gold_M", "Gold_U", "Player_HP_U", "Player_HP_L",
  "Player_InvincibilityPhase", "Player_CurWeapon", "Screen_TrackedVisitCount"];
const snap = () => {
  const o = {};
  for (const n of ONE) o[n] = g.rd(n);
  for (const [n, c] of Object.entries(ARR)) o[n] = Array.from({length: c}, (_, i) => g.rd(g.addr(n) + i));
  return o;
};
for (const [k, v] of Object.entries(preset)) { if (Array.isArray(v)) v.forEach((b, i) => g.wr(g.addr(k) + i, b)); else g.wr(k, v); }
const sounds = [], cpu = g.nes.cpu, emulate = cpu.emulate.bind(cpu), entry = g.romLabels["Sound_PlayEffect"][0] - 1;
const pick = g.romLabels["Player_PickUp"][0] - 1;
let picked = -1;
let doneAt = -1;
cpu.emulate = function () { if (cpu.REG_PC === entry) { sounds.push([g.frames, cpu.REG_ACC]); if (picked >= 0 && doneAt < 0 && (cpu.REG_ACC === 8 || cpu.REG_ACC === 4)) doneAt = frame; } if (cpu.REG_PC === pick && picked < 0) picked = frame; return emulate(); };
let frame = 0;
const slotOf = () => { for (let i = 0; i < 8; i++) if (g.rd(g.addr("CurrentSprites_Entities") + i) !== 255 && g.rd(g.addr("CurrentSprites_XPos_Full") + i) === ix && g.rd(g.addr("CurrentSprites_YPos") + i) >= iy) return i; return -1; };
// INJECT=ent turns the glove of screen 24 of area 1 into that kind (one that is only there some of the time), with the Magical Rod's script that does nothing
if (process.env.INJECT) {
  const e = +process.env.INJECT, i = 5, at = (n) => g.addr("CurrentSprites_" + n) + i;
  g.wr(at("Entities"), e); g.wr(at("Behaviors"), 0x3D); g.wr(at("BehaviorAddrs_L"), 45647 & 255); g.wr(at("BehaviorAddrs_U"), 45647 >> 8);
}
const before = snap(), entsBefore = [];
const ent = [];
for (let i = 0; i < 8; i++) ent.push(g.rd(g.addr("CurrentSprites_Entities") + i));
// stand on it: x at the item, y so that the boxes overlap; the game decides when it is touched
g.wr("Player_PosX_Block", ix); g.wr("Player_PosY", iy - 16);
for (let f = 0; f < 900; f++) {
  frame = f;
  g.nes.buttonUp(1, BTN.A); g.nes.buttonUp(1, BTN.B);
  if (picked >= 0 && (f - picked) % 30 === 20) g.nes.buttonDown(1, BTN.A);
  if (doneAt >= 0 && f > doneAt) break;
  g.run(1);
}
fs.writeFileSync(out, JSON.stringify({area, screen, before, after: snap(), picked, sounds, frames: g.frames}));
