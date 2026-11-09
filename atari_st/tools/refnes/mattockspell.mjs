// The Mattock used while a spell is in flight (Up+B casts, then Down+B): does the ROM take the item, and what does the spell do during the crumble?
//   node mattockspell.mjs AREA SCREEN X Y RIGHT SPELL DELAY
// The hero stands at (X, Y) facing right (RIGHT = 1) or left with the Mattock in hand and SPELL selected. Up+B at frame 0, nothing for DELAY frames, then Down+B.
// Prints the spell's state, the number of its sprites (tiles $40-$8F) and of all sprites in jsnes' OAM, the item in hand and the interrupt counter: every frame until the use,
// then only the frames in which something changed (the message takes about 135 frames, the crumble 16; A is pressed every 20 frames to dismiss the message). ITEM=255 runs it without the Mattock.
import {newOutside, BTN} from "./faxanadu.mjs";

const [area, screen, x, y, right, spell, delay] = process.argv.slice(2, 9).map(Number);
const g = newOutside(area, 0, screen, 100, 144);
g.wr("Player_PosX_Block", x); g.wr("Player_PosX_Frac", 0); g.wr("Player_PosY", y); g.wr("Player_Flags", right ? 0x40 : 0);
g.wr("SelectedMagic", spell); g.wr("Player_MP", 80); g.wr("SelectedItem", +(process.env.ITEM ?? 9)); g.wr("CastMagic_Type", 0xff);
g.run(40);
const oam = () => g.oam().filter((o) => o[0] >= 32 && o[0] < 240 && o[1] >= 0x40 && o[1] < 0x90).length;
let prev = '';
const line = (f, what) => { const t = `spell=${g.rd("CastMagic_Type")} x=${g.rd("CastMagic_XPos_Full")} item=${g.rd("SelectedItem")} spellSprites=${oam()} ic=${g.rd("InterruptCounter")} hero=${g.rd("Player_PosX_Block")},${g.rd("Player_PosY")} sprites=${g.oam().filter((o) => o[0] < 240).length}`; if (what !== 'after' || t.replace(/ic=\d+/, '') !== prev) console.log(f, what, t); prev = t.replace(/ic=\d+/, ''); };
g.nes.buttonDown(1, BTN.UP); g.run(1); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.UP);
line(0, "cast");
let f = 1;
for (; f <= delay; f++) { g.run(1); line(f, "wait"); }
g.nes.buttonDown(1, BTN.DOWN); g.run(1); g.nes.buttonDown(1, BTN.B); g.run(1); g.nes.buttonUp(1, BTN.B); g.nes.buttonUp(1, BTN.DOWN);
line(f++, "down+b");
for (let i = 0; i < 260; i++, f++) {
  if (i % 20 === 10) g.nes.buttonDown(1, BTN.A);
  if (i % 20 === 13) g.nes.buttonUp(1, BTN.A);
  g.run(1); line(f, "after");
}
