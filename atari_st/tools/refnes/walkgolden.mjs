// The hero's horizontal walking, frame by frame (golden run for tools/hero_physics.py): in Eolis screen 1 the harness stands still,
// walks right, stands, walks left, stands, and records the position, the acceleration, the flags and the buttons after every frame.
//   node walkgolden.mjs OUT.json
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2] ?? "/tmp/walkgolden.json";
const g = newGame();
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
g.nes.buttonUp(1, BTN.UP);
g.run(40);

const frames = [];
const snap = (pad) => frames.push({
  pad, x: g.rd("Player_PosX_Block"), frac: g.rd("Player_PosX_Frac"), y: g.rd("Player_PosY"),
  acc: g.rd("Player_MoveAcceleration"), accU: g.rd("Player_MoveAcceleration_U"),
  flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"), joy: g.rd("Joy1_ButtonMask"),
  title: g.rd("PlayerTitle"), status: g.rd("Player_StatusFlag"), changed: g.rd("Joy1_ChangedButtonMask"),
  jump: g.rd("Player_JumpCurveIndex"), climb: g.rd("Player_ClimbFlySpeedModifier"), atkTimer: g.rd("Player_AttackPhaseTimer"), atkFrame: g.rd("Player_AttackPhaseAnimFrame"),
});
const act = (buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b);
  for (let i = 0; i < n; i++) { g.run(1); snap(buttons.reduce((a, b) => a | b, 0)); }
  for (const b of buttons) g.nes.buttonUp(1, b); };
act([], 8);
act([BTN.RIGHT], 45);
act([], 8);
act([BTN.LEFT], 70);
act([], 5);
act([BTN.RIGHT], 12);
act([BTN.LEFT], 12);
act([], 5);
act([BTN.A], 1); act([], 45);                       // a standing jump
act([BTN.RIGHT], 5); act([BTN.RIGHT, BTN.A], 1); act([BTN.RIGHT], 40); act([], 10);   // a running jump
// The screen is changed by hand (the test makes the same changes): a ceiling over columns 3-4 (row 8) and 6-7 (row 7), a hole in the floor over
// columns 8-11 with a floor one row lower, so there is something to bump into and something to fall off.
const SB = g.addr("ScreenBuffer"), ground = g.nes.cpu.mem[SB + 11 * 16], air = g.nes.cpu.mem[SB];
for (const c of [3, 4]) g.nes.cpu.mem[SB + 8 * 16 + c] = ground;
for (const c of [6, 7]) g.nes.cpu.mem[SB + 7 * 16 + c] = ground;
for (const c of [8, 9, 10, 11]) { g.nes.cpu.mem[SB + 11 * 16 + c] = air; g.nes.cpu.mem[SB + 12 * 16 + c] = ground; }
const put = (x, y) => { g.wr("Player_PosX_Block", x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", y); g.wr("Player_Flags", 0x40); g.wr("Player_JumpCurveIndex", 0); g.wr("Player_ClimbFlySpeedModifier", 0);
  g.wr("Player_MoveAcceleration", 0); g.wr("Player_MoveAcceleration_U", 0); snap(0); frames[frames.length - 1].set = 1; };
put(0x30, 144); act([], 3); act([BTN.A], 1); act([], 40);        // a jump into the ceiling (the hit is not on a block row)
put(0x60, 144); act([], 3); act([BTN.A], 1); act([], 40);        // a jump into the ceiling (the hit is on a block row)
put(0x20, 48); act([], 20);                                     // falling from the air
put(0x70, 144); act([BTN.RIGHT], 30); act([], 5);               // walking off the ledge into the hole
put(0x70, 144); act([BTN.RIGHT], 3); act([BTN.RIGHT, BTN.A], 1); act([BTN.RIGHT], 40); act([], 5);   // jumping over it
// A ladder in column 13 from row 6 to row 10 (block 250 gets the ladder property in the game's copy of the block properties).
const BP = g.addr("BlockProperties");
g.nes.cpu.mem[BP + 125] = (g.nes.cpu.mem[BP + 125] & 0xF0) | 2;
for (let r = 6; r <= 10; r++) g.nes.cpu.mem[SB + r * 16 + 13] = 250;
put(0xD0, 144); frames[frames.length - 1].ladder = 1;
act([BTN.UP], 30); act([BTN.DOWN], 40); act([BTN.UP], 10); act([BTN.A], 1); act([], 5);        // on the ladder: up, down, up, A does nothing
act([BTN.RIGHT], 12); act([], 10);                                                              // off it to the side and falling the little there is
put(0xD4, 144); act([BTN.UP], 25);                                                              // not on the ladder: he steps to it (left), then climbs
put(0xDC, 144); act([BTN.UP], 25);                                                              // the same from the other side
put(0xD4, 144); act([BTN.DOWN], 12);                                                            // down at the floor does nothing but step to it
put(0xD0, 144); act([BTN.UP], 90); act([], 10);                                                 // up over the top of the ladder
put(0x04, 144); act([], 3);
act([BTN.B], 1); act([], 25);                       // an attack standing
act([BTN.RIGHT], 4); act([BTN.RIGHT, BTN.B], 1); act([BTN.RIGHT], 25); act([], 5);   // an attack while walking
act([BTN.A], 1); act([BTN.B], 1); act([], 45);      // an attack in the air
fs.writeFileSync(out, JSON.stringify(frames));
console.log(frames.length, "frames; start", JSON.stringify(frames[0]));
