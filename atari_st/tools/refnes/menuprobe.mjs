// The player menu (Select) as the game runs it: a preset of RAM labels, then the buttons of KEYS (comma separated, tapped one after the other; WAIT runs 40 frames, for a menu that is slow to draw), then the
// inventory, the selected things and the sounds played are written out. SHOTS=dir writes a PPM after every tap.
//   node menuprobe.mjs AREA SCREEN KEYS OUT.json [PRESET]
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [area, screen] = process.argv.slice(2, 4).map(Number), keys = process.argv[4].split(",").filter(Boolean), out = process.argv[5];
const preset = process.argv[6] ? JSON.parse(process.argv[6]) : {};
const g = newOutside(area, 0, screen, 100, 144);
const ARR = {WeaponInventory: 4, ArmorInventory: 4, ShieldInventory: 4, MagicInventory: 4, ItemInventory: 8};
const ONE = ["SelectedWeapon", "SelectedArmor", "SelectedShield", "SelectedMagic", "SelectedItem", "NumberOfWeapons", "NumberOfArmors", "NumberOfShields", "NumberOfMagicSpells", "NumberOfItems",
  "SpecialItems", "Player_CurWeapon"];
for (const [k, v] of Object.entries(preset)) { if (Array.isArray(v)) v.forEach((b, i) => g.wr(g.addr(k) + i, b)); else g.wr(k, v); }
const snap = () => {
  const o = {};
  for (const n of ONE) o[n] = g.rd(n);
  for (const [n, c] of Object.entries(ARR)) o[n] = Array.from({length: c}, (_, i) => g.rd(g.addr(n) + i));
  return o;
};
const sounds = [], cpu = g.nes.cpu, emulate = cpu.emulate.bind(cpu), entry = g.romLabels["Sound_PlayEffect"][0] - 1;
cpu.emulate = function () { if (cpu.REG_PC === entry) sounds.push([g.frames, cpu.REG_ACC]); return emulate(); };
g.run(30);
const before = snap(), shots = process.env.SHOTS;
if (shots) fs.mkdirSync(shots, {recursive: true});
keys.forEach((k, i) => {
  if (k === "WAIT") { g.run(40); return; }
  g.tap(BTN[k], 12);
  if (shots) g.ppm(`${shots}/${String(i).padStart(2, "0")}_${k}.ppm`);
});
g.run(30);
fs.writeFileSync(out, JSON.stringify({before, after: snap(), sounds}));
