"""src/password.s on machine68k against tools/password_model.py: the 68000 code makes the same characters and accepts and rejects the same texts."""
from __future__ import annotations

import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import password_model as pm  # noqa: E402

AS, LD, OBJCOPY = "m68k-linux-gnu-as", "m68k-linux-gnu-ld", "m68k-linux-gnu-objcopy"
LOAD = 0x10000
STACK = 0x7F000
INPUT, OUTPUT, RESULT, MODE = 0x2100, 0x2200, 0x2010, 0x2000
STATE_BYTES = 38
OFFSETS = {"weapons": 9, "armors": 14, "shields": 19, "spells": 24, "items": 29}

WRAPPER = """
    .section .text.boot,"ax"
_start:
    bra.w run
    .text
run:
    lea 0x2100, %a0
    lea 0x2200, %a1
    tst.w 0x2000
    bne.s 1f
    bsr.w pw_encode
    bra.s 2f
1:  bsr.w pw_decode
    move.l %d0, 0x2010
2:
done:
    bra.s done
    .include "password.s"
"""


def block(s: pm.State) -> bytes:
    out = bytearray(STATE_BYTES)
    out[0:9] = bytes([s.spawn, s.title, s.special_items, s.quests, s.weapon, s.armor, s.shield, s.magic, s.item])
    for name, at in OFFSETS.items():
        values = getattr(s, name)
        out[at] = len(values)
        out[at + 1:at + 1 + len(values)] = bytes(values)
    return bytes(out)


def unblock(b: bytes) -> pm.State:
    s = pm.State(*b[0:9])
    for name, at in OFFSETS.items():
        setattr(s, name, list(b[at + 1:at + 1 + b[at]]))
    return s


def toolchain_ok() -> bool:
    if not all(shutil.which(t) for t in (AS, LD, OBJCOPY)):
        return False
    try:
        import machine68k  # noqa: F401
    except ImportError:
        return False
    return True


def random_state(rng: random.Random) -> pm.State:
    """Mostly states the game would make, now and then one with a value or a count it would refuse."""
    bad = rng.random() < 0.2
    valid_items = [i for i in range(21) if pm.VALID_ITEM[i]]

    def spell() -> int:
        return rng.randrange(8) if bad and rng.random() < 0.3 else rng.randrange(5)

    def item() -> int:
        return rng.randrange(32) if bad and rng.random() < 0.3 else rng.choice(valid_items)

    s = pm.State(rng.randrange(8), rng.randrange(16), rng.randrange(256), rng.randrange(256))
    s.weapon, s.shield = (pm.UNSET if rng.random() < 0.3 else rng.randrange(4) for _ in range(2))
    s.armor = pm.UNSET if bad and rng.random() < 0.3 else rng.randrange(4)
    s.magic = pm.UNSET if rng.random() < 0.3 else spell()
    s.item = pm.UNSET if rng.random() < 0.5 else item()
    for name, _, entry_bits, most in pm.LISTS:
        n = rng.randrange(most + (4 if bad and rng.random() < 0.3 else 1))
        setattr(s, name, [spell() if name == "spells" else item() if name == "items" else rng.randrange(1 << entry_bits) for _ in range(n)])
    return s


@unittest.skipUnless(toolchain_ok(), "needs the m68k binutils and machine68k")
class PasswordAsmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import machine68k as m

        cls.m = m
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "wrapper.s").write_text(WRAPPER, encoding="utf-8")
        subprocess.run([AS, "-m68000", "-I", str(ROOT / "src"), "-o", str(tmp / "w.o"), str(tmp / "wrapper.s")], check=True, capture_output=True)
        subprocess.run([LD, "-T", str(ROOT / "link.ld"), "-nostdlib", "-e", "0", "-o", str(tmp / "w.elf"), str(tmp / "w.o")], check=True, capture_output=True)
        subprocess.run([OBJCOPY, "-O", "binary", str(tmp / "w.elf"), str(tmp / "w.bin")], check=True)
        cls.image = (tmp / "w.bin").read_bytes()
        cls.machine = m.Machine(m.CPUType.M68000, 1024)
        mem = cls.machine.mem
        mem.w_block(LOAD, cls.image)
        cls.machine.cpu.set_instr_hook_callback(lambda pc: cls.machine.abort_execute() if mem.r16(pc) == 0x60FE else None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def call(self, mode: int, data: bytes) -> tuple[bytes, int]:
        machine = self.machine
        mem, cpu = machine.mem, machine.cpu
        mem.w_block(INPUT, data + bytes(64))
        mem.w_block(OUTPUT, bytes(64))
        mem.w16(MODE, mode)
        mem.w32(RESULT, 0)
        cpu.w_sr(0x2700)
        cpu.w_sp(STACK)
        cpu.w_pc(LOAD)
        machine.execute(2_000_000)
        return bytes(mem.r_block(OUTPUT, 64)), mem.r32(RESULT)

    def encode(self, s: pm.State) -> str:
        out, _ = self.call(0, block(s))
        return out.split(b"\0")[0].decode("ascii")

    def decode(self, text: str):
        out, result = self.call(1, text.encode("ascii") + b"\0")
        return (unblock(out), result)

    def test_the_characters_are_the_models(self) -> None:
        rng = random.Random(1)
        for _ in range(300):
            s = random_state(rng)
            for name, _, _, most in pm.LISTS:
                setattr(s, name, getattr(s, name)[:most])
            with self.subTest(state=s):
                self.assertEqual(self.encode(s), pm.password(s))

    def test_a_mantra_the_model_accepts_gives_the_same_state_and_a_wrong_one_is_refused(self) -> None:
        rng = random.Random(2)
        accepted = refused = 0
        for _ in range(400):
            s = random_state(rng)
            text = pm.password(s)
            if rng.random() < 0.3:                       # a mistake: another character, a shorter or a longer text
                at = rng.randrange(len(text))
                text = text[:at] + rng.choice(pm.CHARS) + text[at + 1:] if rng.random() < 0.6 else (text[:at] if rng.random() < 0.5 else text + rng.choice(pm.CHARS))
            if rng.random() < 0.05:
                text = text + "!"
            want = pm.decode(text)
            got, result = self.decode(text)
            with self.subTest(text=text):
                if want is None:
                    refused += 1
                    self.assertEqual(result & 0xFFFFFFFF, 0xFFFFFFFF)
                else:
                    accepted += 1
                    self.assertEqual(result, 0)
                    self.assertEqual(got, want)
        self.assertGreater(accepted, 100)
        self.assertGreater(refused, 40)

    def test_texts_that_are_empty_or_too_long_are_refused(self) -> None:
        for text in ("", "A", "A" * 33, "A" * 40):
            with self.subTest(text=text):
                self.assertIsNone(pm.decode(text))
                self.assertEqual(self.decode(text)[1] & 0xFFFFFFFF, 0xFFFFFFFF)


if __name__ == "__main__":
    unittest.main()
