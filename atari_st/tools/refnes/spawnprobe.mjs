// Where the hero comes back after a death, for each temple spawn point (Game_SpawnInTemple): TempleSpawnPoint is set, Player_Spawn runs (as after the
// death message or a mantra), and the hero walks out of the temple to the right. Prints JSON: for each spawn point the temple (area, Area_DestScreen,
// x, y, facing) and the outside he comes to (area, Area_Region, screen, x, y, palette, Music_Current, Quests).
//   node spawnprobe.mjs
import {newGame, BTN} from "./faxanadu.mjs";

const out = [];
for (let k = 0; k < 8; k++) {
  const g = newGame();
  g.wr("TempleSpawnPoint", k);
  g.wr("Quests", 0x17);                       // (Player_Spawn clears bit 4, the Mattock's)
  g.nes.cpu.REG_PC = g.romLabels["Player_Spawn"][0] - 1;
  g.run(150);
  const temple = {area: g.rd("Area_CurrentArea"), dest: g.rd("Area_DestScreen"), x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"),
    quests: g.rd("Quests"), hp: g.rd("Player_HP_U"), mp: g.rd("Player_MP")};
  g.nes.buttonDown(1, BTN.RIGHT);
  g.runUntil(() => g.rd("Area_CurrentArea") !== temple.area && g.rd("Screen_PaletteIndex") !== 18 && g.inPlay(), 900);
  g.nes.buttonUp(1, BTN.RIGHT);
  out.push({k, temple, outside: {area: g.rd("Area_CurrentArea"), region: g.rd("Area_Region"), screen: g.rd("Area_CurrentScreen"), x: g.rd("Player_PosX_Block"),
    y: g.rd("Player_PosY"), palette: g.rd("Screen_PaletteIndex"), music: g.rd("Music_Current")}});
}
console.log(JSON.stringify(out));
