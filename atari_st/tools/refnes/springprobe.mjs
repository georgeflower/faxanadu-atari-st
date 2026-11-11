// The springs ($61 to $63) and the fountain ($52) of Trunk, and the stone on the way to Mascon (screen 40), frame by frame.
//   node springprobe.mjs SPEC.json OUT.json
// SPEC: {"screen": n, "x": .., "y": .., "right": 0|1, "quests": q, "special": s, "frames": n, "pokes": [[frame, "Quests", value], ...], "hold": [[from, to, "RIGHT"|"LEFT"], ...]}
// The hero comes out of a temple onto Trunk's screen with the quests and special items given (Player_Spawn clears quest bit $10 only), stands at x, y, and from
// then on every frame records: the update counter, the eight slots (entity, phase, flags, data 2 and 3, x, y), the sprites in OAM, the quests, the push counter,
// the blocks of the fountain and the ladder's column, the hero and the sound effect asked for.
import fs from "fs";
import {newGame, BTN} from "./faxanadu.mjs";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = process.argv[3];
const g = newGame();
g.wr("Quests", spec.quests ?? 0);
g.wr("SpecialItems", spec.special ?? 0);
g.warp(1, 1, spec.screen, spec.x ?? 64, spec.y ?? 144);
// out of the temple: walk right until the screen is the one asked for (its sprites and event are loaded with the quests set above); from then on every frame is recorded
g.nes.buttonDown(1, BTN.RIGHT);
if (!g.runUntil(() => g.rd("Area_CurrentArea") === 1 && g.rd("Area_CurrentScreen") === spec.screen, 600)) throw new Error("did not get out: " + g.state());
let released = false;
const rows = [];
const pokes = spec.pokes ?? [];
const holds = spec.hold ?? [];
const blocks = [0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x82, 0x92, 0x55, 0x56, 0x57, 0x65, 0x66, 0x67];
for (let f = 0; f < spec.frames; f++) {
  for (const [at, label, v] of pokes) if (at === f) g.wr(label, v);
  for (const [a, b, btn] of holds) {
    if (f === a) g.nes.buttonDown(1, BTN[btn]);
    if (f === b) g.nes.buttonUp(1, BTN[btn]);
  }
  if (!released && g.inPlay()) {
    g.nes.buttonUp(1, BTN.RIGHT); released = true;
    for (const [a, b, btn] of holds) if (a <= f && f < b) g.nes.buttonDown(1, BTN[btn]);     // (a hold that began while he came out goes on)
    if (spec.place !== false) { g.wr("Player_PosX_Block", spec.x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", spec.y); g.wr("Player_Flags", spec.right ? 0x40 : 0); }
  }
  g.run(1);
  const slots = [];
  const F = ["Entities", "Phases", "Flags", "BehaviorData2", "BehaviorData3", "Behaviors", "PPUOffsets", "InternalBehaviorStates", "HitCounter", "BehaviorAddrs_L", "BehaviorAddrs_U", "BehaviorArg1"];
  for (let i = 0; i < 8; i++) {
    const o = {x: g.rd(0xba + i), y: g.rd(0xc2 + i)};
    for (const n of F) o[n] = g.rd(g.addr("CurrentSprites_" + n) + i);
    slots.push(o);
  }
  rows.push({f, counter: g.rd("SpriteUpdateCounter"), slots, oam: g.oam().filter((o) => o[0] < 240),
    quests: g.rd("Quests"), push: g.rd("BlockPushCounter"), opening: g.rd("PathToMascon_Opening"),
    blocks: blocks.map((b) => g.rd(0x600 + b)), hero: [g.rd("Player_PosX_Block"), g.rd("Player_PosY")], pf: g.rd("Player_Flags"), sfx: g.rd("SoundEffect_Current"),
    screen: g.rd("Area_CurrentScreen"), ic: g.rd("InterruptCounter")});
}
fs.writeFileSync(out, JSON.stringify(rows));
