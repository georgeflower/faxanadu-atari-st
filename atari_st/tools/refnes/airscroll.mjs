// A jump to the right off the edge of Eolis screen 1 (and to the left off screen 2's edge): what the ROM has when the scroll is done
// (screen, x, y, jump index, flags), so the ST's scroll in the air can be compared.
//   node airscroll.mjs
import {newTown, BTN} from "./faxanadu.mjs";

function run(startX, dir, label) {
  const g = newTown();
  g.wr("Player_PosX_Block", startX); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", 144);
  g.run(3);
  const screen0 = g.rd("Area_CurrentScreen");
  g.nes.buttonDown(1, dir);
  g.run(3);
  g.nes.buttonDown(1, BTN.A);
  g.run(1);
  g.nes.buttonUp(1, BTN.A);
  let scrolling = false, done = null;
  for (let i = 0; i < 400 && !done; i++) {
    g.run(1);
    const dirNow = g.rd("Screen_ScrollDirection");
    if (dirNow < 4) scrolling = true;
    else if (scrolling) done = {frames: i, screen0, screen: g.rd("Area_CurrentScreen"), x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"),
      jump: g.rd("Player_JumpCurveIndex"), flags: g.rd("Player_Flags")};
  }
  g.nes.buttonUp(1, dir);
  g.run(60);
  console.log(label, JSON.stringify(done), "landed", g.rd("Player_PosX_Block"), g.rd("Player_PosY"), g.rd("Player_Flags"));
}
run(0xE0, BTN.RIGHT, "right");
run(0x18, BTN.LEFT, "left");
