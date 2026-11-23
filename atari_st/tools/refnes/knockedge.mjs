// A knock-back at the left and right edge of a screen (Player_HandleKnockback -> Player_TryMoveLeft/Right): the hit is written into the RAM
// between two frames (as walkgolden.mjs does), the screen's enemies are taken away, and the hero's place, the area and the screen are recorded
// every frame until the game is in play again and has stood for a while.
//   node knockedge.mjs CASES.json OUT.json
// CASES: [{area, region, screen, x, y, from: "left"|"right"}, ...]; "from" is the side the enemy hits him from (from the left he goes right).
// A case with "walk": "left"|"right"|"up"|"down" instead holds that way on the stick for `hold` frames (default 160) and hits him not (the same edges
// walked to; up and down climb the ladders of the up-and-down ways, AREA_SCREEN_COMPARATORS). "frames" (default 160) is how long it records.
// Each frame also has the music, the palette set, the first colours of the PPU's palette and how many pixels of the picture are not the backdrop.
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = process.argv[3] ?? "/tmp/knockedge.json";
const results = [];
for (const c of cases) {
  const g = newOutside(c.area, c.region, c.screen, c.x, c.y);
  const clear = () => { for (let i = 0; i < 8; i++) g.wr(g.addr("CurrentSprites_Entities") + i, 0xff); };
  clear();
  g.run(2);
  for (const n of ["Player_PosX_Frac", "Player_MovementTick", "Player_InvincibilityPhase", "Player_StatusFlag", "Player_MoveAcceleration",
    "Player_MoveAcceleration_U", "Player_JumpCurveIndex"]) g.wr(n, 0);
  g.wr("Player_PosX_Block", c.x); g.wr("Player_PosY", c.y); g.wr("Player_Flags", c.from === "left" ? 0 : 0x40);
  clear();
  g.run(1);
  const snap = () => ({x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), area: g.rd("Area_CurrentArea"), screen: g.rd("Area_CurrentScreen"),
    scroll: g.rd("Screen_ScrollDirection"), flags: g.rd("Player_Flags"), status: g.rd("Player_StatusFlag"), invinc: g.rd("Player_InvincibilityPhase"),
    music: g.rd("Music_Current"), palette: g.rd("Screen_PaletteIndex"), ppal: Array.from(g.nes.ppu.vramMem.slice(0x3F00, 0x3F04)),
    lit: g.pixels ? g.pixels.reduce((n, p) => n + (p !== g.pixels[0] ? 1 : 0), 0) : 0});
  const frames = [snap()];
  // Player_SetDamagedBySprite: 60 frames, he faces the enemy (from the left: he faces left, the flip bit clear), the knock-back bit
  const pad = c.walk ? {left: BTN.LEFT, right: BTN.RIGHT, up: BTN.UP, down: BTN.DOWN}[c.walk] : null;
  if (pad === null) {
    g.wr("Player_InvincibilityPhase", 0x3C); g.wr("Player_StatusFlag", g.rd("Player_StatusFlag") | 2);
    g.wr("Player_Flags", (g.rd("Player_Flags") & 0xBF) | (c.from === "left" ? 0 : 0x40));
  } else g.nes.buttonDown(1, pad);
  for (let i = 0; i < (c.frames ?? 160); i++) { if (pad !== null && i === (c.hold ?? 160)) g.nes.buttonUp(1, pad); g.run(1); clear(); frames.push(snap()); }
  if (pad !== null) g.nes.buttonUp(1, pad);
  results.push({case: c, frames});
  const last = frames[frames.length - 1];
  console.log(JSON.stringify(c), "->", JSON.stringify(frames.slice(0, 6).map(f => [f.area, f.screen, f.x, f.y])), "end", last.area, last.screen, last.x, last.y);
}
fs.writeFileSync(out, JSON.stringify(results));
