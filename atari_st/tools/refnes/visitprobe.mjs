// Screen_TrackedVisitCount against a random item (entity $50, $55, $56 or $5D to $60: behaviours 50 to 56): each entry to the screen counts one and the item is there on
// every fourth, hidden by the hero's own entries on other screens. Trunk (area 1) screen 14 has entity $50 at (208, 80); its neighbours are 13 and 15.
//   node visitprobe.mjs [ENTRIES] [ENTITY]   prints, per entry: the count after 20 frames and whether the item's slot (and with it the item) is there
import {newOutside, BTN} from "./faxanadu.mjs";

const entries = +(process.argv[2] ?? 9), entity = +(process.argv[3] ?? 0x50);
const g = newOutside(1, 0, 14, 64);
g.run(30);
const walk = (btn, scr, max = 3000) => {
  g.nes.buttonDown(1, btn);
  const ok = g.runUntil(() => g.rd("Area_CurrentScreen") === scr && g.inPlay(), max);
  g.nes.buttonUp(1, btn);
  return ok;
};
const slotOf = () => { for (let i = 0; i < 8; i++) if (g.rd(g.addr("CurrentSprites_Entities") + i) === entity) return i; return -1; };
const out = [];
let next = BTN.LEFT;
for (let n = 1; n <= entries; n++) {
  g.run(20);
  const i = slotOf();
  out.push({entry: n, count: g.rd("Screen_TrackedVisitCount"), there: i >= 0, flags: i >= 0 ? g.rd(g.addr("CurrentSprites_Flags") + i) : null});
  console.log(JSON.stringify(out[out.length - 1]));
  // away to a neighbour and back
  const away = walk(BTN.LEFT, 13) ? BTN.RIGHT : (walk(BTN.RIGHT, 15), BTN.LEFT);
  if (!walk(away, 14)) throw new Error("not back " + g.state());
}
