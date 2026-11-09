FAXANADU FOR THE ATARI ST
=========================

A port of the NES game (Europe, PAL)
for the 520 STFM, written in 68000
assembly. Claude helped with the code.
The game data on this disk was made
from the author's own ROM: keep the
disk to yourself.

WHAT YOU NEED
-------------
 - an Atari ST with 512 KB, colour
   monitor, low resolution, PAL (50 Hz)
 - this disk in the drive the whole
   time: the areas load from it

START
-----
Open the disk and run FAXANADU.PRG.
The title screen comes first. Up, Down
or Tab pick START or CONTINUE, fire or
Return confirm. START plays the intro
and begins a new game in Eolis.
CONTINUE asks for a mantra (the
password a Guru shows you).

CONTROLS
--------
Joystick in port 1:
  stick     walk, climb, Up at a door
            or a person
  fire      sword (B)

Keyboard:
  arrows    walk, climb
  Space     jump (A), and OK in text
            boxes and menus
  Alt       sword (B)
  Return    Start
  Tab       Select: the player menu
  Esc       leave the game

A stick has one button, so the jump
(and OK in text boxes) is only on the
keyboard for now.

Up + sword        cast the chosen spell
Down + sword      use the item in hand
Up at a door      go in
Walk off an edge  next screen

WHAT TO EXPECT
--------------
A screen change scrolls in steps of 16
pixels, four frames each. A door fades
out and the next place loads from the
disk: the word LOADING shows, and on a
real drive it takes a second or two.
Music and sound effects play from the
YM2149.

Still missing or not as in the game:
the walking people in the towns stand
still, there are no credits, and the
timing of the intro, the ending and the
fades is an approximation.

TEST KEYS STILL IN
------------------
F1-F10 and the number keys play songs
and sounds, Backspace stops them.
H and G hurt you. M picks the next
spell and refills magic. P shows the
mantra.

If it does not start: the program
needs about 380 KB free. Take out
desk accessories and AUTO programs.
