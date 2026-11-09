// The hero's death in the ROM, frame by frame: he stands in Eolis (screen 1, armour and shield as given (default leather, none), no weapon), he is marked dead (PlayerIsDead, as Player_ReduceHP does) and the game's death loop (`Player_HandleDeath`)
// runs. After every frame the death animation's counters (phase, counter, the screen transition counter) and the sprite pattern tiles $00-$07 (the body's eight, which the loop dissolves
// in CHR RAM) are recorded, and the picture's hero area at the end of some frames.
//   node deathprobe.mjs OUT.json [facing 0|1] [armour] [shield]
import {newTown} from "./faxanadu.mjs";
import fs from "fs";

const [out = "/tmp/deathprobe.json", facing = "0", armor = "0", shield = "255"] = process.argv.slice(2);
const g = newTown();
g.wr("SelectedArmor", +armor); g.wr("SelectedShield", +shield); g.wr("SelectedWeapon", 255); g.wr("Player_CurWeapon", 255);
g.wr("Player_Flags", (g.rd("Player_Flags") & ~0x40) | (+facing ? 0x40 : 0));
g.run(30);
const chr = () => Array.from(g.nes.ppu.vramMem.slice(0, 0x80));
const rec = [{f: -1, chr: chr(), x: g.rd("Player_PosX_Block"), y: g.rd("Player_PosY"), flags: g.rd("Player_Flags")}];
g.wr("Player_HP_U", 0); g.wr("Player_HP_L", 0); g.wr("PlayerIsDead", 1);      // (what `Player_ReduceHP` does when the power is gone)
for (let f = 0; f < 275; f++) {
  g.run(1);
  rec.push({f, chr: chr(), phase: g.rd("Player_DeathAnimationPhase"), counter: g.rd("Player_DeathAnimationCounter"), tc: g.rd("Screen_TransitionCounter"), ic: g.rd("InterruptCounter"), dead: g.rd("PlayerIsDead"),
    oam: g.oam().filter((e, i) => e[0] < 0xef && e[1] < 0x80)});
}
fs.writeFileSync(out, JSON.stringify(rec));
