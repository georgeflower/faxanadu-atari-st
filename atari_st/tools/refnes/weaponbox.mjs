// The weapon's place and reach for every weapon, with and without a shield (golden run for tools/hero_physics.body_frame and
// tools/faxanadu_sprites.weapon_offset): in Eolis screen 1 the hero stands, walks, jumps and attacks, and after every frame the harness records the weapon
// position the game computed (Player_DrawWeapon: PlayerPosXPlus10, Maybe_Something_WeaponPosY, Maybe_WeaponRange_X and _Y) with his state.
//   node weaponbox.mjs OUT.json
import {newGame, BTN} from "./faxanadu.mjs";
import fs from "fs";

const out = process.argv[2] ?? "/tmp/weaponbox.json";
const g = newGame();
g.wr("Player_PosX_Block", 192);
g.run(3);
g.nes.buttonDown(1, BTN.UP);
g.runUntil(() => g.rd("Area_CurrentScreen") === 1 && g.inPlay(), 300);
g.nes.buttonUp(1, BTN.UP);
g.run(40);

const frames = [];
const snap = (pad, weapon, shield) => frames.push({
  pad, weapon, shield, x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags"), tick: g.rd("Player_MovementTick"),
  joy: g.rd("Joy1_ButtonMask"), status: g.rd("Player_StatusFlag"), atkFrame: g.rd("Player_AttackPhaseAnimFrame"), armorIndex: g.rd("Player_ArmorLookupIndex"),
  weaponX: g.rd("PlayerPosXPlus10"), weaponY: g.rd("Maybe_Something_WeaponPosY"), rangeX: g.rd("Maybe_WeaponRange_X"), rangeY: g.rd("Maybe_WeaponRange_Y"),
});
for (const weapon of [0, 1, 2, 3]) {
  for (const shield of [0, 255]) {
    g.wr("Player_CurWeapon", weapon); g.wr("SelectedWeapon", weapon); g.wr("SelectedShield", shield);
    g.wr("Player_ArmorLookupIndex", shield === 255 ? 0 : 1);
    const act = (buttons, n) => { for (const b of buttons) g.nes.buttonDown(1, b);
      for (let i = 0; i < n; i++) { g.run(1); snap(0, weapon, shield); }
      for (const b of buttons) g.nes.buttonUp(1, b); };
    g.wr("Player_PosX_Block", 0x40); g.wr("Player_PosY", 144); g.wr("Player_Flags", 0x40); g.wr("Player_StatusFlag", 0);
    act([], 4); act([BTN.RIGHT], 30); act([], 4); act([BTN.LEFT], 30); act([], 4);
    act([BTN.B], 1); act([], 25);                                        // standing attack
    act([BTN.RIGHT], 4); act([BTN.RIGHT, BTN.B], 1); act([BTN.RIGHT], 25); act([], 4);
    act([BTN.A], 1); act([], 12); act([BTN.B], 1); act([], 30);          // jumping, an attack in the air
    g.wr("Player_PosX_Block", 0x40); g.wr("Player_Flags", 0x00); act([BTN.RIGHT], 20); act([], 4);   // facing left, walking right turns him
  }
}
fs.writeFileSync(out, JSON.stringify(frames));
console.log(frames.length, "frames");
