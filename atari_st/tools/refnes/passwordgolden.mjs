// The password (the mantra) from the ROM: random game states are written into the ROM's RAM and the routines of bank 12 are called with the CPU
// itself (Password_GenerateStateAndReset, Password_GetNext6Bits for the characters; then the entry screen's Password_Maybe_CheckPasswordLength and
// Password_Load on characters, right and wrong ones). Writes a JSON list of cases to the file named on the command line.
import fs from "fs";
import {newGame, BTN} from "./faxanadu.mjs";

const g = newGame();
g.wr("Player_HP_U", 0); g.wr("PlayerIsDead", 1);
g.run(900);                                              // the death messages: bank 12 is in
const cpu = g.nes.cpu;
const SENTINEL = 0xFFF0;

// the routines in the Europe ROM's bank 12 (the labels of the disassembly are the US ROM's, which has other addresses from here on)
const ADDR = {Password_GenerateStateAndReset: 0x9729, Password_GetNext6Bits: 0x9735, Password_Maybe_CheckPasswordLength: 0x9894, Password_Load: 0x95E9};
function call(label, a = 0, x = 0, y = 0) {
  const addr = ADDR[label];
  const saved = [cpu.REG_PC, cpu.REG_SP, cpu.REG_ACC, cpu.REG_X, cpu.REG_Y, cpu.F_CARRY, cpu.F_ZERO, cpu.F_SIGN, cpu.F_OVERFLOW, cpu.F_DECIMAL, cpu.F_INTERRUPT];
  cpu.push((SENTINEL - 1) >> 8); cpu.push((SENTINEL - 1) & 0xFF);
  cpu.REG_PC = addr - 1; cpu.REG_ACC = a; cpu.REG_X = x; cpu.REG_Y = y;
  for (let n = 0; cpu.REG_PC + 1 !== SENTINEL; n++) { if (n > 200000) throw new Error("runaway " + label); cpu.emulate(); }
  const out = {a: cpu.REG_ACC, carry: cpu.F_CARRY};
  [cpu.REG_PC, cpu.REG_SP, cpu.REG_ACC, cpu.REG_X, cpu.REG_Y, cpu.F_CARRY, cpu.F_ZERO, cpu.F_SIGN, cpu.F_OVERFLOW, cpu.F_DECIMAL, cpu.F_INTERRUPT] = saved;
  return out;
}

const LISTS = [["weapons", "WeaponInventory", "NumberOfWeapons", 4, 4], ["armors", "ArmorInventory", "NumberOfArmors", 4, 4], ["shields", "ShieldInventory", "NumberOfShields", 4, 4],
               ["spells", "MagicInventory", "NumberOfMagicSpells", 4, 5], ["items", "ItemInventory", "NumberOfItems", 8, 21]];
const SELECTED = [["weapon", "SelectedWeapon", 4], ["armor", "SelectedArmor", 4], ["shield", "SelectedShield", 4], ["magic", "SelectedMagic", 8], ["item", "SelectedItem", 32]];
let seed = 12345;
const rnd = (n) => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return (seed >> 8) % n; };

function setState(s) {
  g.wr("TempleSpawnPoint", s.spawn); g.wr("PlayerTitle", s.title); g.wr("SpecialItems", s.special_items); g.wr("Quests", s.quests);
  for (const [n, label] of SELECTED.map(([a, b]) => [a, b])) g.wr(label, s[n] === 255 ? 255 : s[n]);
  for (const [n, inv, num] of LISTS) { g.wr(num, s[n].length); s[n].forEach((v, i) => g.wr(g.addr(inv) + i, v)); }
}
function getState() {
  const s = {spawn: g.rd("TempleSpawnPoint"), title: g.rd("PlayerTitle"), special_items: g.rd("SpecialItems"), quests: g.rd("Quests")};
  for (const [n, label] of SELECTED.map(([a, b]) => [a, b])) s[n] = g.rd(label);
  for (const [n, inv, num] of LISTS) { s[n] = Array.from({length: g.rd(num)}, (_, i) => g.rd(g.addr(inv) + i)); }
  return s;
}
const BAD_ITEMS = [11, 14, 17];
const goodItem = () => { let v; do { v = rnd(21); } while (BAD_ITEMS.includes(v)); return v; };
function randomState() {
  const s = {spawn: rnd(8), title: rnd(16), special_items: rnd(256), quests: rnd(256)};
  for (const [n, , lim] of SELECTED) s[n] = rnd(3) === 0 ? 255 : rnd(n === "item" ? 21 : n === "magic" ? 5 : lim);
  for (const [n, , , most, lim] of LISTS) s[n] = Array.from({length: rnd(most + 1)}, () => n === "items" ? goodItem() : rnd(lim));
  if (rnd(8) !== 0 && s.armor === 255) s.armor = rnd(4);
  if (rnd(8) !== 0 && BAD_ITEMS.includes(s.item)) s.item = 0;
  return s;
}

const cases = [];
for (let i = 0; i < 60; i++) {
  const s = i === 0 ? {spawn: 0, title: 0, special_items: 0, quests: 0, weapon: 255, armor: 255, shield: 255, magic: 255, item: 255, weapons: [], armors: [], shields: [], spells: [], items: []}
    : randomState();
  setState(s);
  call("Password_GenerateStateAndReset");
  const base = g.addr("Password_EncodedState");
  const count = g.rd("Password_6BitCount");
  const data = Array.from({length: 34}, (_, k) => g.nes.cpu.mem[base + k]);
  const chars = [];
  for (let k = 0; k < count; k++) chars.push(call("Password_GetNext6Bits").a);
  cases.push({state: s, count, data, chars});
}
// the entry screen: characters (as indices 0-63 in ScreenBuffer) checked and loaded; the right ones, and some with a character changed, cut or added
const entries = [];
for (let i = 0; i < cases.length; i++) {
  const c = cases[i];
  const variants = [c.chars];
  if (i % 3 === 0) { const v = [...c.chars]; v[rnd(v.length)] ^= 1 << rnd(6); variants.push(v); }
  if (i % 5 === 0) variants.push(c.chars.slice(0, -1));
  if (i % 7 === 0) variants.push([...c.chars, rnd(64)]);
  for (const v of variants) {
    for (let k = 0; k < 32; k++) g.wr(g.addr("ScreenBuffer") + k, 0xFF);
    v.forEach((x, k) => g.wr(g.addr("ScreenBuffer") + k, x));
    g.wr("Password_EnteredCharsLength", v.length);
    for (const [, inv] of LISTS) for (let k = 0; k < 8; k++) g.wr(g.addr(inv) + k, 0xEE);
    setState({spawn: 7, title: 15, special_items: 0xAA, quests: 0x55, weapon: 1, armor: 1, shield: 1, magic: 1, item: 1, weapons: [], armors: [], shields: [], spells: [], items: []});
    const check = call("Password_Maybe_CheckPasswordLength");
    let ok = check.carry === 0, state = null;
    if (ok) {
      const load = call("Password_Load");
      ok = load.carry === 0;
      if (ok) state = getState();
    }
    entries.push({chars: v, ok, state});
  }
}
fs.writeFileSync(process.argv[2], JSON.stringify({cases, entries}));
console.log(cases.length, "states", entries.length, "entries", entries.filter((e) => e.ok).length, "accepted");
