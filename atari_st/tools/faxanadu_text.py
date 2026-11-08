"""The text of the Europe ROM: the font and the messages of the text boxes (bank 13), and the password screen's two lines (bank 12).

The font is 96 glyphs for the characters 32 to 127, 8 bytes each, one bit a pixel (the most significant bit is the left pixel);
`TextBox_WriteChar` draws a glyph in both planes of a tile, which makes its pixels colour 3. The messages follow the font from `$8300`, each ended by
`$FF`, numbered from 1: bytes 32 to 127 are the characters, `$FE` starts a new line, `$FD` is a space that may be the end of a line, `$FC` waits for a
button, `$FB` is the player's rank. Bank 13 and bank 12 differ from the US build, so the offsets here are the Europe ROM's.
"""
from __future__ import annotations

import re

import faxanadu_rom as fr

BANK = 0x4000
FONT_GLYPHS = 96
FIRST_MESSAGE = FONT_GLYPHS * 8            # $8300
MESSAGE_DEATH = 0x24                       # "Don't have negative thoughts. Remember your mantra."
MESSAGE_MEDITATE = 0x22                    # the Guru's, before the password
PASSWORD_LINE = 0x91BE - 0x8000            # bank 12: "Mantra is in the wrong." and "Enter your mantra."


def _bank(rom: fr.Rom, number: int) -> bytes:
    start = fr.HEADER + number * BANK
    return rom.data[start:start + BANK]


def font(rom: fr.Rom) -> bytes:
    """768 bytes: glyph c - 32 is bytes 8 * (c - 32) to 8 * (c - 32) + 7, top line first."""
    return _bank(rom, 13)[:FIRST_MESSAGE]


def message(rom: fr.Rom, number: int) -> str:
    """Message `number` (1-based) as text: lines end with a line feed; a wait for a button (`$FC`) is a line feed too, the player's rank (`$FB`) is `{rank}`."""
    bank, pos = _bank(rom, 13), FIRST_MESSAGE
    for _ in range(number - 1):
        pos = bank.index(b"\xff", pos) + 1
    out = []
    for b in bank[pos:bank.index(b"\xff", pos)]:
        out.append({0xFE: "\n", 0xFD: " ", 0xFC: "\n", 0xFB: "{rank}"}.get(b) or chr(b))
    return "".join(out)


def password_lines(rom: fr.Rom) -> tuple[str, str]:
    """The password screen's two lines: the message for a wrong password, and the request."""
    text = bytes(_bank(rom, 12)[PASSWORD_LINE:PASSWORD_LINE + 70]).split(b"\0")[0].decode("ascii")
    wrong, ask = (part.strip() for part in re.split(r" {2,}", text.strip())[:2])
    return wrong, ask


def _records(rom: fr.Rom, first: bytes, count: int) -> list[str]:
    """`count` strings of the 16-byte records (a length byte, then the text padded with blanks) from the one that starts with `first` (its length byte
    comes just before it): what the player menu and the item lists show."""
    at = rom.data.index(first) - 1
    return [rom.data[at + 16 * i + 1:at + 16 * i + 16].decode("ascii").strip() for i in range(count)]


def menu_strings(rom: fr.Rom) -> dict[str, list[str]]:
    """The player menu's texts: the six entries of the top menu, the names of every weapon, armour, shield, spell and item in one list (`ITEM_NAMES_*`: the
    weapons from 0, the armours from 4, the shields from 8, the spells from 12, the items from 17), and the five 'NO ...' lines."""
    return {"top": _records(rom, b"WEAPON ", 6), "names": _records(rom, b"HAND DAGGER", 39), "none": _records(rom, b"NO WEAPON", 5)}
