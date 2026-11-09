// Which screen of area 4 the game puts the hero on when he enters a building door: Area_CurrentScreen inside the building (the screen the people and scripts are
// placed by), Area_CurrentArea, the palette (the building's type) and the start position, for each door of a list.
//   node buildingprobe.mjs DOORS.json OUT.json     (DOORS: [{area, region, screen, x, y}, ...]; the hero is put at x, y with Up pressed)
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const doors = JSON.parse(fs.readFileSync(process.argv[2], "utf8")), out = [];
for (const d of doors) {
  const g = newOutside(d.area, d.region, d.screen, d.x < 100 ? d.x + 80 : d.x - 40, 144);
  g.wr("SpecialItems", 0xf0);                                  // the rings: the doors of key 6 and the others open
  g.nes.buttonDown(1, BTN.UP);
  let ok = false;
  for (let f = 0; f < 90 && !ok; f++) {                        // the hero is held at the door every frame (no fall, no walk) until the game takes him in
    g.wr("Player_PosX_Block", d.x);
    g.wr("Player_PosY", d.y);
    g.run(1);
    ok = g.rd("Area_CurrentArea") === 4;
  }
  g.nes.buttonUp(1, BTN.UP);
  g.runUntil(() => g.inPlay(), 300);
  g.run(150);
  out.push({...d, ok, area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen"), palette: g.rd("Screen_DestPaletteOrIndex"), loading: g.rd("Area_LoadingScreenIndex"),
    dest: g.rd("Area_DestScreen"), sprites: Array.from({length: 8}, (_, i) => g.rd(g.addr("CurrentSprites_Entities") + i)), values: Array.from({length: 8}, (_, i) => g.rd(g.addr("CurrentSprites_Values") + i)), xs: Array.from({length: 8}, (_, i) => g.rd(g.addr("CurrentSprites_XPos_Full") + i)),
    tiles: g.rd("Area_TilesIndex"), music: g.rd("Music_Current"), from: d.screen, door_area: d.area});
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
