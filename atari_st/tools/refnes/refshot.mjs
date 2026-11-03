// A reference picture of a screen for the ROM-data checks: the harness plays to the screen, then writes PREFIX.ppm (256x240),
// PREFIX.oam.json (the sprites on screen) and prints the state as JSON.
//   node refshot.mjs [town|right] PREFIX
import {newTown, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [where = "town", prefix = "/tmp/refshot"] = process.argv.slice(2);
const g = newTown();
if (where === "right") {
  g.wr("Player_PosX_Block", 226);
  g.nes.buttonDown(1, BTN.RIGHT);
  g.runUntil(() => g.rd("Screen_ScrollDirection") !== 0xff, 600);
  g.runUntil(() => g.rd("Screen_ScrollDirection") === 0xff, 600);
  g.nes.buttonUp(1, BTN.RIGHT);
  g.run(30);
}
g.ppm(prefix + ".ppm");
fs.writeFileSync(prefix + ".oam.json", JSON.stringify(g.oam()));
console.log(JSON.stringify({area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen"), palette: g.rd("Screen_PaletteIndex")}));
