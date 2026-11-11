// The HUD's T: (UI_DrawTimeValue at $2058, the Wing Boots' seconds) in the ROM: the boots put on with Down and B, the seconds counted, a door taken while they
// are on (Screen_SetupNew draws the HUD with 0), and their end.
//   node timeprobe.mjs OUT.json
// Each record: the frame, the two digit tiles of the name table at $2058, DurationWingBoots, InterruptCounter, the screen and area.
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const g = newOutside(0, 0, 0, 120, 144);                         // Eolis screen 0, the castle door at x 192
const nt = () => [g.nes.ppu.vramMem[0x2058], g.nes.ppu.vramMem[0x2059]];
const rec = [];
const log = (tag) => rec.push({f: g.frames, tag, t: nt(), wb: g.rd("DurationWingBoots"), ic: g.rd("InterruptCounter"), screen: g.rd("Area_CurrentScreen"), area: g.rd("Area_CurrentArea"), status: g.rd("Player_StatusFlag")});
log("start");
g.wr("DurationWingBoots", 5);                                    // the boots on with 5 seconds left, as Player_UseWingBoots leaves them
for (let i = 0; i < 200; i++) { g.run(1); log("count"); }
g.wr("DurationWingBoots", 30);
for (let i = 0; i < 70; i++) { g.run(1); log("count2"); }
g.nes.buttonDown(1, BTN.UP);
let inside = false;
for (let f = 0; f < 120 && !inside; f++) {
  g.wr("Player_PosX_Block", 192); g.wr("Player_PosY", 144);
  g.run(1); log("door");
  inside = g.rd("Area_CurrentScreen") !== 0;
}
g.nes.buttonUp(1, BTN.UP);
for (let i = 0; i < 200; i++) { g.run(1); log("after"); }
fs.writeFileSync(process.argv[2], JSON.stringify(rec));
