// The death box in the ROM: the hero dies in Eolis (as deathprobe.mjs), the game's death loop runs and then script $1F (`IScripts_Begin` maps the $FF that
// `Player_HandleDeath` passes to $1F: the message "Don't have negative thoughts. Remember your mantra."). Prints, as JSON, the sprites on the screen while each
// page of the box is up (only the cursor's: the script's entity byte is $00, so no portrait opens) and writes the pictures if a prefix is given.
//   node deathboxprobe.mjs [PREFIX]
import {newTown, BTN} from "./faxanadu.mjs";

const [prefix] = process.argv.slice(2);
const g = newTown();
g.run(30);
g.wr("Player_HP_U", 0); g.wr("Player_HP_L", 0); g.wr("PlayerIsDead", 1);
const visible = () => g.oam().filter(e => e[0] < 0xef).map(e => Array.from(e));
const pages = [];
g.run(400); pages.push(visible()); if (prefix) g.ppm(`${prefix}_1.ppm`);
g.run(160); pages.push(visible());
g.tap(BTN.A); g.run(200); pages.push(visible()); if (prefix) g.ppm(`${prefix}_2.ppm`);
console.log(JSON.stringify({pages}));
