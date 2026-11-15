// Jumping to a ladder whose bottom is above the hero's head, on real screens (golden runs for tests/test_ladderjump.py): the hero is put on the
// floor under the ladder at several x, and A is pressed with Up held from the press, Up pressed during the jump, Up never, or Right with A then
// Up (the diagonal jump). The screen's sprites are taken away (nothing knocks him about). After every frame the state is recorded.
//   node ladderjump.mjs SPOTS.json OUT.json
// SPOTS: [{area, region, screen, y, xs: [...], cases: [[name, [[buttons, frames], ...]], ...]}, ...]; buttons are names of BTN.
import {newOutside, BTN} from "./faxanadu.mjs";
import fs from "fs";

const [spotsFile, out = "/tmp/ladderjump.json"] = process.argv.slice(2);
const spots = JSON.parse(fs.readFileSync(spotsFile, "utf8"));
const result = [];
for (const spot of spots) {
  const g = newOutside(spot.area, spot.region, spot.screen, spot.xs[0], spot.y);
  g.wr("Player_InvincibilityPhase", 0);
  for (let i = 0; i < 8; i++) g.wr(g.addr("CurrentSprites_Entities") + i, 0xff);
  g.run(2);
  const saved = g.nes.toJSON();
  for (const x of spot.xs) {
    for (const [name, seq] of spot.cases) {
      g.nes.fromJSON(saved);
      for (const b of Object.values(BTN)) g.nes.buttonUp(1, b);
      g.wr("Player_PosX_Block", x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", spot.y); g.wr("Player_Flags", 0x40);
      g.wr("Player_JumpCurveIndex", 0); g.wr("Player_ClimbFlySpeedModifier", 0); g.wr("Player_MoveAcceleration", 0); g.wr("Player_MoveAcceleration_U", 0);
      g.wr("Player_StatusFlag", g.rd("Player_StatusFlag") & 0x7f);
      const frames = [];
      const snap = () => frames.push({x: g.rd("Player_PosX_Block"), frac: g.rd("Player_PosX_Frac"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"),
        tick: g.rd("Player_MovementTick"), jump: g.rd("Player_JumpCurveIndex"), climb: g.rd("Player_ClimbFlySpeedModifier"), joy: g.rd("Joy1_ButtonMask"),
        changed: g.rd("Joy1_ChangedButtonMask"), acc: g.rd("Player_MoveAcceleration") | g.rd("Player_MoveAcceleration_U") << 8, status: g.rd("Player_StatusFlag"),
        title: g.rd("PlayerTitle"), screen: g.rd("Area_CurrentScreen"), invinc: g.rd("Player_InvincibilityPhase")});
      g.run(4); snap();
      for (const [buttons, n] of seq) {
        for (const b of buttons) g.nes.buttonDown(1, BTN[b]);
        for (let i = 0; i < n; i++) { g.run(1); snap(); }
        for (const b of buttons) g.nes.buttonUp(1, BTN[b]);
      }
      result.push({area: spot.area, screen: spot.screen, x, y: spot.y, name, frames});
    }
  }
}
fs.writeFileSync(out, JSON.stringify(result));
console.log(result.length, "runs");
