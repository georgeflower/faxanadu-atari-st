"""The Europe ROM's password (the mantra): the game state as a bit string, shown as characters, and read back (PRG12: `Password_GenerateState`,
`Password_EncodeGameState`, `Password_EncodeValue`, `Password_DecodeValue`, `Password_Maybe_CheckPasswordLength`, `Password_Load`).

The bits, most significant first: 8 for the checksum, 5 for the number of characters, then the state, padded with zeros to a whole byte, and a last byte of 0.
The checksum makes the sum of all the bytes 0 (mod 256). Six bits make a character of `CHARS`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789,?"      # PASSWORD_ENTERED_CHARS
MAX_CHARS = 32                                                                  # the entry field
UNSET = 0xFF


@dataclass
class State:
    spawn: int = 0                  # TempleSpawnPoint (3 bits)
    title: int = 0                  # PlayerTitle (4)
    special_items: int = 0          # SpecialItems bitmask (8)
    quests: int = 0                 # Quests bitmask (8)
    weapon: int = UNSET             # the selected ones: 0-3 (2 bits), magic 0-7 (3), item 0-31 (5), UNSET for none
    armor: int = UNSET
    shield: int = UNSET
    magic: int = UNSET
    item: int = UNSET
    weapons: list[int] = field(default_factory=list)       # the inventories: up to 4 (2 bits each), 4 (2), 4 (2), 4 spells (3), 8 items (4)
    armors: list[int] = field(default_factory=list)
    shields: list[int] = field(default_factory=list)
    spells: list[int] = field(default_factory=list)
    items: list[int] = field(default_factory=list)


# (field, bits of the count, bits of an entry, most entries): Password_EncodeValueList
LISTS = (("weapons", 3, 2, 4), ("armors", 3, 2, 4), ("shields", 3, 2, 4), ("spells", 3, 3, 4), ("items", 4, 5, 8))
# Password_Load of the Europe ROM: the selected item and the items must be one of these ids (a table of 21: 0 for 11, 14 and 17); the selected armor must be set
VALID_ITEM = tuple(int(i not in (11, 14, 17)) for i in range(21))
SELECTED = (("weapon", 2), ("armor", 2), ("shield", 2), ("magic", 3), ("item", 5))


class Bits:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def put(self, value: int, count: int) -> None:
        self.bits += [(value >> (count - 1 - i)) & 1 for i in range(count)]


def _game_state_bits(b: Bits, s: State) -> None:
    b.put(s.spawn, 3)
    b.put(s.title, 4)
    b.put(s.special_items, 8)
    b.put(s.quests, 8)
    for name, bits in SELECTED:
        value = getattr(s, name)
        if value == UNSET:
            b.put(0, 1)
        else:
            b.put(1, 1)
            b.put(value, bits)
    for name, count_bits, entry_bits, _ in LISTS:
        values = getattr(s, name)
        b.put(len(values), count_bits)
        for v in values:
            b.put(v, entry_bits)


def encode(s: State) -> bytes:
    """The 34 bytes of Password_EncodedState (the checksum first, a byte of 0 after the data) and the number of characters."""
    first = Bits()
    first.put(0, 8)
    first.put(0, 5)
    _game_state_bits(first, s)
    total = len(first.bits)
    count = -(-total // 6)
    b = Bits()
    b.put(0, 8)
    b.put(count, 5)
    _game_state_bits(b, s)
    while len(b.bits) % 8:
        b.bits.append(0)
    data = bytearray(sum(bit << (7 - i) for i, bit in enumerate(b.bits[n:n + 8])) for n in range(0, len(b.bits), 8))
    data.append(0)
    data[0] = (-sum(data)) & 0xFF
    return bytes(data), count


def characters(data: bytes, count: int) -> str:
    """The password as shown: `count` groups of 6 bits."""
    bits = [(data[i // 8] >> (7 - i % 8)) & 1 if i // 8 < len(data) else 0 for i in range(count * 6)]
    return "".join(CHARS[sum(bit << (5 - j) for j, bit in enumerate(bits[n:n + 6]))] for n in range(0, count * 6, 6))


def password(s: State) -> str:
    data, count = encode(s)
    return characters(data, count)


def decode(text: str) -> State | None:
    """What the password screen does with what was typed: None for a wrong one (Password_Maybe_CheckPasswordLength, Password_Load)."""
    if not text or len(text) > MAX_CHARS or any(c not in CHARS for c in text):
        return None
    bits = Bits()
    for c in text:
        bits.put(CHARS.index(c), 6)
    while len(bits.bits) % 8:
        bits.bits.append(0)
    data = bytearray(sum(bit << (7 - i) for i, bit in enumerate(bits.bits[n:n + 8])) for n in range(0, len(bits.bits), 8))
    if len(data) < 2 or data[1] >> 3 != len(text) or sum(data) & 0xFF:
        return None
    pos = 13

    def take(n: int) -> int:
        nonlocal pos
        value = 0
        for _ in range(n):
            byte = pos // 8
            value = value << 1 | ((data[byte] >> (7 - pos % 8)) & 1 if byte < len(data) else 0)
            pos += 1
        return value

    s = State(spawn=take(3), title=take(4), special_items=take(8), quests=take(8))
    for name, bits_ in SELECTED:
        setattr(s, name, take(bits_) if take(1) else UNSET)
    if s.armor == UNSET or (s.magic != UNSET and s.magic >= 5) or (s.item != UNSET and (s.item >= 21 or not VALID_ITEM[s.item])):
        return None
    for name, count_bits, entry_bits, most in LISTS:
        n = take(count_bits)
        if n > most:
            return None
        setattr(s, name, [take(entry_bits) for _ in range(n)])
    if any(v >= 5 for v in s.spells) or any(v >= 21 or not VALID_ITEM[v] for v in s.items):
        return None
    return s
