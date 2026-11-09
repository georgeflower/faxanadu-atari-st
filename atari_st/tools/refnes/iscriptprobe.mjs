// The ROM's own interaction-script interpreter in jsnes, for the Python model (tools/iscript_model.py) to be checked against: for each job (a script id, the player's
// state, and what the buttons do) the hero talks to a person of Eolis whose script is set to that id; every action the interpreter runs is logged (its address in bank
// 12), and the state is read when the game has the hero again.
//   node iscriptprobe.mjs JOBS.json OUT.json
// A job: {id, state: {label: number | [bytes]}, policy: "A" | "BA" | "B" | "SA"}. policy A holds A for 4 frames of every 8; BA presses B in the first half of every 16 frames, A in the
// second; B only B; SA is A, but in the buy-or-sell menu (the loop of IScriptAction_ShowBuySellMenu) Down is pressed first and then A: Sell. The state is set before the script starts; STATE lists what is read after it.
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const ARR = {WeaponInventory: 4, ArmorInventory: 4, ShieldInventory: 4, MagicInventory: 4, ItemInventory: 8};
const ONE = ["Gold", "Gold_M", "Gold_U", "Player_HP_U", "Player_HP_L", "Player_MP", "Experience", "Experience_U", "PlayerTitle", "NextPlayerTitle", "TempleSpawnPoint", "SpecialItems", "Quests",
  "NumberOfWeapons", "NumberOfArmors", "NumberOfShields", "NumberOfMagicSpells", "NumberOfItems", "SelectedWeapon", "SelectedArmor", "SelectedShield", "SelectedMagic", "SelectedItem"];

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8")), out = [];
const g = newTown();
const slot = 7;
const base = JSON.stringify(g.nes.toJSON());                  // every job starts from this game: the hero in Eolis, the walker on the screen
let cpu = g.nes.cpu;
const next = g.romLabels["IScripts_InvokeNextAction"][0] - 1;
const begin = g.romLabels["IScripts_Begin"][0] - 1;
let trace = null, started = false, done = false, last = -1;
const waitPC = cpu.REG_PC;                                     // where the main loop spins in WaitForNextFrame (ca28/ca2a); the script waits at the same place, deeper in the stack
const mainSP = cpu.REG_SP;
const menuLoop = g.romLabels["IScriptAction_ShowBuySellMenu"][0] + 15 - 1;   // after its message, the string count and the cursor are set (15 bytes): the loop that waits for a button
let menuStart = -1;
const install = () => {                                         // (a restored game has a new CPU object)
  cpu = g.nes.cpu;
  const emulate = cpu.emulate.bind(cpu);
  cpu.emulate = function () {
    const pc = cpu.REG_PC;
    if (trace && pc !== last) {                                 // (jsnes calls emulate more than once at a PC while it waits)
      if (pc === next && g.rd("CurrentROMBank") === 12) { trace.push(g.rd16("IScriptOrCHRAddr") + g.rd("IScriptOffset")); started = true; }
      else if (started && (pc === waitPC || pc === waitPC + 2) && cpu.REG_SP === mainSP) done = true;
    }
    if (trace && pc === menuLoop && menuStart === -2) menuStart = -3;       // (the loop is entered: the main loop below takes the frame number)
    last = pc;
    return emulate();
  };
};
const snap = () => {
  const o = {};
  for (const n of ONE) o[n] = g.rd(n);
  for (const [n, c] of Object.entries(ARR)) o[n] = Array.from({length: c}, (_, i) => g.rd(g.addr(n) + i));
  return o;
};
const press = (policy, f) => {
  let a = false, b = false, d = false;
  if (policy === "A") a = (f & 7) >= 4;
  else if (policy === "SA") {
    if (menuStart === -3) menuStart = f;
    if (menuStart >= 0 && f < menuStart + 12) { d = f >= menuStart + 1 && f < menuStart + 4; a = f >= menuStart + 8 && f < menuStart + 11; }
    else a = (f & 7) >= 4;
  }
  else if (policy === "B") b = (f & 7) >= 4;
  else if (policy === "BA") { const p = f & 15; b = p >= 4 && p < 8; a = p >= 12; }
  a ? g.nes.buttonDown(1, BTN.A) : g.nes.buttonUp(1, BTN.A);
  b ? g.nes.buttonDown(1, BTN.B) : g.nes.buttonUp(1, BTN.B);
  d ? g.nes.buttonDown(1, BTN.DOWN) : g.nes.buttonUp(1, BTN.DOWN);
};
for (const job of jobs) {
  g.nes.fromJSON(JSON.parse(base));
  install();
  last = -1;
  for (const n of ONE) g.wr(n, 0);
  for (const [n, c] of Object.entries(ARR)) for (let i = 0; i < c; i++) g.wr(g.addr(n) + i, 0);
  g.wr("SelectedWeapon", 0xff); g.wr("SelectedArmor", 0xff); g.wr("SelectedShield", 0xff); g.wr("SelectedMagic", 0xff); g.wr("SelectedItem", 0xff);
  for (const [k, v] of Object.entries(job.state)) { if (Array.isArray(v)) v.forEach((b, i) => g.wr(g.addr(k) + i, b)); else g.wr(k, v); }
  g.run(2);
  const before = snap();
  trace = [];
  started = done = false;
  menuStart = job.policy === "SA" ? -2 : -1;
  const sprite = (n) => g.rd(g.addr("CurrentSprites_" + n) + slot);
  g.wr(g.addr("CurrentSprites_Values") + slot, job.id);
  let f = 0;
  for (; f < 30 && !started; f++) {                             // Up, newly pressed, in front of the person
    g.wr("Player_PosX_Block", sprite("XPos_Full")); g.wr("Player_PosY", sprite("YPos"));
    if (f % 4 === 1) g.nes.buttonDown(1, BTN.UP); else g.nes.buttonUp(1, BTN.UP);
    g.run(1);
  }
  g.nes.buttonUp(1, BTN.UP);
  const first = f;
  for (f = 0; f < (job.frames ?? 4000) && !done; f++) { press(job.policy, f); g.run(1); }
  g.nes.buttonUp(1, BTN.A); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.DOWN);
  trace.push(-1);
  out.push({id: job.id, policy: job.policy, started, done, frames: f, first, trace, before, after: snap()});
  trace = null;
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
