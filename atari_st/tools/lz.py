"""A small LZ77 packer for the area packages (the 68000 side is `unpack` in src/viewer.s).

The packed block is the length of the data (a big-endian long) and then sequences. A sequence is a token byte (literal count in the high
nibble, match length minus 4 in the low nibble; 15 means more bytes follow, each added, until one is not 255), the literals, and, unless the
data is complete, a big-endian word with how far back the match starts (1-32767) and the match length bytes. The last sequence has only literals.
"""
from __future__ import annotations

MIN_MATCH, MAX_BACK, CHAIN = 4, 32767, 600


def _length(out: bytearray, n: int) -> None:
    """The bytes after a nibble of 15 that say the rest of a length n >= 15."""
    n -= 15
    while n >= 255:
        out.append(255)
        n -= 255
    out.append(n)


def _sequence(out: bytearray, literals: bytes, match: tuple[int, int] | None) -> None:
    lit, length = len(literals), (match[1] - MIN_MATCH) if match else 0
    out.append(min(lit, 15) << 4 | min(length, 15))
    if lit >= 15:
        _length(out, lit)
    out += literals
    if match:
        out += match[0].to_bytes(2, "big")
        if length >= 15:
            _length(out, length)


def _longest(data: bytes, heads: dict, pos: int, end: int) -> tuple[int, int]:
    """The longest earlier match for the bytes at pos: (length, how far back), (0, 0) for none."""
    best, back = 0, 0
    for cand in reversed(heads.get(data[pos:pos + MIN_MATCH], ())[-CHAIN:]):
        if pos - cand > MAX_BACK:
            break
        n = MIN_MATCH
        while pos + n < end - 1 and data[cand + n] == data[pos + n]:
            n += 1
        if n > best:
            best, back = n, pos - cand
    return best, back


def pack(data: bytes) -> bytes:
    """Greedy with one step of lazy matching: a match is passed up (as a literal) when the next position has a longer one."""
    out, heads, start, pos, end = bytearray(len(data).to_bytes(4, "big")), {}, 0, 0, len(data)
    last = end - MIN_MATCH                           # the final bytes stay literals, so the last sequence has no match
    done = 0                                         # positions before this one are in `heads`

    def index(upto: int) -> None:
        nonlocal done
        while done < min(upto, last):
            heads.setdefault(data[done:done + MIN_MATCH], []).append(done)
            done += 1
        done = max(done, upto)

    while pos < last:
        index(pos)
        best, back = _longest(data, heads, pos, end)
        while best >= MIN_MATCH and pos + 1 < last:
            index(pos + 1)
            longer, farther = _longest(data, heads, pos + 1, end)
            if longer <= best:
                break
            pos, best, back = pos + 1, longer, farther
        if best >= MIN_MATCH:
            _sequence(out, data[start:pos], (back, best))
            pos += best
            start = pos
        else:
            pos += 1
    _sequence(out, data[start:], None)
    return bytes(out)


def unpack(blob: bytes) -> bytes:
    size, i, out = int.from_bytes(blob[:4], "big"), 4, bytearray()
    while True:
        token = blob[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = blob[i]
                i += 1
                lit += b
                if b != 255:
                    break
        out += blob[i:i + lit]
        i += lit
        if len(out) >= size:
            return bytes(out)
        back = int.from_bytes(blob[i:i + 2], "big")
        i += 2
        length = token & 15
        if length == 15:
            while True:
                b = blob[i]
                i += 1
                length += b
                if b != 255:
                    break
        for _ in range(length + MIN_MATCH):
            out.append(out[-back])


def overrun(blob: bytes) -> int:
    """How far the unpacked data runs ahead of the packed bytes read so far, at worst: the packed block may start this many bytes before the
    end of the data when it is unpacked where it lies (the writes must stay behind the reads)."""
    i, out, worst = 4, 0, 0
    size = int.from_bytes(blob[:4], "big")
    while True:
        token = blob[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = blob[i]
                i += 1
                lit += b
                if b != 255:
                    break
        i += lit
        out += lit
        worst = max(worst, out - i)
        if out >= size:
            return worst
        i += 2
        length = token & 15
        if length == 15:
            while True:
                b = blob[i]
                i += 1
                length += b
                if b != 255:
                    break
        out += length + MIN_MATCH
        worst = max(worst, out - i)
