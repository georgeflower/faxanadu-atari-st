"""The frame loop and the input (src/frame.s).

The IKBD parser and the pad run on machine68k with bytes put in the ring by the test, as the interrupt would; the VBL counter
runs in Hatari (the viewer's frame loop): it has to count every VBL, 100 of them in 100 frames, with none late.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
AS, LD, NM = "m68k-linux-gnu-as", "m68k-linux-gnu-ld", "m68k-linux-gnu-nm"
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")

LOAD = 0x10000
STACK = 0x7F000
CALL = 0x400                      # jsr to the routine under test, then a stop

NES_A, NES_B, NES_START, NES_UP, NES_DOWN, NES_LEFT, NES_RIGHT = 0x80, 0x40, 0x10, 0x08, 0x04, 0x02, 0x01
IN_HEAD, IN_TAIL, IN_RING, IN_PACKET, IN_JOY, IN_PAD, IN_PAD_NEW, IN_QUIT, IN_KEYS = 0, 1, 2, 258, 259, 260, 261, 262, 264


def toolchain_ok() -> bool:
    if not all(shutil.which(t) for t in (AS, LD, NM)):
        return False
    try:
        import machine68k  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(toolchain_ok(), "needs the m68k binutils and machine68k")
class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import machine68k as m

        cls.m = m
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        source = tmp / "frame_test.s"
        source.write_text('    .text\n    .include "frame.s"\n', encoding="utf-8")
        subprocess.run([AS, "-m68000", "-I", str(ROOT / "src"), "-o", str(tmp / "t.o"), str(source)], check=True, capture_output=True)
        subprocess.run([LD, "-T", str(ROOT / "link.ld"), "-nostdlib", "-e", "0", "-o", str(tmp / "t.elf"), str(tmp / "t.o")],
                       check=True, capture_output=True)
        subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", str(tmp / "t.elf"), str(tmp / "t.bin")], check=True)
        cls.image = (tmp / "t.bin").read_bytes()
        names = subprocess.run([NM, str(tmp / "t.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        cls.sym = {line.split()[2]: int(line.split()[0], 16) + LOAD for line in names if len(line.split()) == 3}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def machine(self):
        m = self.m
        machine = m.Machine(m.CPUType.M68000, 16384)
        machine.mem.w_block(LOAD, self.image)
        return machine

    def call(self, machine, name: str, hook=None, limit: int = 2_000_000) -> None:
        mem, cpu = machine.mem, machine.cpu
        mem.w16(CALL, 0x4EB9)                                # jsr name
        mem.w32(CALL + 2, self.sym[name])
        mem.w16(CALL + 6, 0x60FE)                            # bra *: the stop
        steps = [0]

        def on_instr(pc):
            steps[0] += 1
            if mem.r16(pc) == 0x60FE:
                machine.abort_execute()
            elif hook:
                hook(steps[0])

        cpu.set_instr_hook_callback(on_instr)
        cpu.w_sr(0x2700)
        cpu.w_sp(STACK)
        cpu.w_pc(CALL)
        machine.execute(limit)

    def feed(self, machine, data: list[int]) -> None:
        mem, base = machine.mem, self.sym["input_state"]
        head = mem.r8(base + IN_HEAD)
        for b in data:
            mem.w8(base + IN_RING + head, b)
            head = (head + 1) & 255
        mem.w8(base + IN_HEAD, head)

    def poll(self, machine, data: list[int]) -> tuple[int, int]:
        self.feed(machine, data)
        self.call(machine, "input_poll")
        base = self.sym["input_state"]
        return machine.mem.r8(base + IN_PAD), machine.mem.r8(base + IN_PAD_NEW)

    def test_joystick_one_makes_the_pad(self) -> None:
        mc = self.machine()
        self.assertEqual(self.poll(mc, [0xFF, 0x08])[0], NES_RIGHT)
        self.assertEqual(self.poll(mc, [0xFF, 0x81])[0], NES_UP | NES_B)    # up and fire
        self.assertEqual(self.poll(mc, [0xFF, 0x06])[0], NES_DOWN | NES_LEFT)
        self.assertEqual(self.poll(mc, [0xFF, 0x00])[0], 0)

    def test_the_mouse_port_and_mouse_moves_are_ignored(self) -> None:
        mc = self.machine()
        self.assertEqual(self.poll(mc, [0xFE, 0x0F])[0], 0)                  # joystick 0
        # a mouse move whose data bytes look like a joystick header and a scan code
        self.assertEqual(self.poll(mc, [0xF8, 0xFF, 0x39, 0xFF, 0x02]), (NES_DOWN, NES_DOWN))
        base = self.sym["input_state"]
        self.assertEqual(mc.mem.r8(base + IN_KEYS + 0x39), 0)

    def test_keys_make_the_pad_and_a_release_ends_it(self) -> None:
        mc = self.machine()
        self.assertEqual(self.poll(mc, [0x39]), (NES_A, NES_A))              # Space down
        self.assertEqual(self.poll(mc, []), (NES_A, 0))                      # held: no new press
        self.assertEqual(self.poll(mc, [0x4B, 0x1C]), (NES_A | NES_LEFT | NES_START, NES_LEFT | NES_START))
        self.assertEqual(self.poll(mc, [0xB9, 0xCB, 0x9C]), (0, 0))          # all released within one frame
        # pressed and released within one frame: a missed release would leave the hero walking by himself
        self.assertEqual(self.poll(mc, [0x4D, 0xCD]), (0, 0))

    def test_stick_and_keys_together(self) -> None:
        mc = self.machine()
        self.assertEqual(self.poll(mc, [0xFF, 0x80, 0x48])[0], NES_B | NES_UP)

    def test_esc_asks_to_quit(self) -> None:
        mc = self.machine()
        self.poll(mc, [0x01])
        self.assertNotEqual(mc.mem.r8(self.sym["input_state"] + IN_QUIT), 0)

    def test_the_ring_wraps(self) -> None:
        mc = self.machine()
        for i in range(200):                                                  # 600 bytes through a ring of 256
            self.assertEqual(self.poll(mc, [0xFF, i & 0x0F])[0] & 0x0F, _pad_of(i & 0x0F))

    def test_wait_vbl_waits_for_the_next_vbl_and_counts_late_ones(self) -> None:
        mc = self.machine()
        mem = mc.mem
        count, late, last = self.sym["frame_count"], self.sym["late_frames"], self.sym["last_wait"]
        mem.w32(count, 7)
        mem.w32(last, 7)

        def vbl(step):                                       # the interrupt: one VBL after 100 instructions
            if step == 100:
                mem.w32(count, 8)

        self.call(mc, "wait_vbl", vbl)
        self.assertEqual((mem.r32(last), mem.r32(late)), (8, 0))
        mem.w32(count, 12)                                   # three more VBLs passed behind our back
        self.call(mc, "wait_vbl")
        self.assertEqual((mem.r32(last), mem.r32(late)), (12, 3))


def _pad_of(joy: int) -> int:
    """The pad for a stick state: bit 0 up, 1 down, 2 left, 3 right."""
    return sum(nes for bit, nes in ((0, NES_UP), (1, NES_DOWN), (2, NES_LEFT), (3, NES_RIGHT)) if joy >> bit & 1)


ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which(AS) and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class VblTests(unittest.TestCase):
    def test_every_vbl_is_counted_and_none_is_late(self) -> None:
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer"], check=True, capture_output=True)
        elf = ROOT / "build" / "viewer.elf"
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        nm = subprocess.run([NM, str(elf)], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        work = ROOT / "build" / "shots_frame"
        work.mkdir(parents=True, exist_ok=True)
        first, second = 600, 700
        for n, vbl in ((1, first), (2, second)):
            (work / f"cap{n}.ini").write_text(f"savebin {work / f'ram{n}.bin'} 0 $80000\ncont\n", encoding="utf-8")
        script = "".join(f"b VBL > {v - 1} :once :file {work / f'cap{n}.ini'}\n" for n, v in ((1, first), (2, second)))
        hatari = shutil.which("hatari")
        hs.run_hatari(hatari, TOS, ROOT / "build" / "VIEWER.PRG", work, second, "0", script, None)
        probe = image[sym["start"]:sym["start"] + 48]
        values = []
        for n in (1, 2):
            ram = (work / f"ram{n}.bin").read_bytes()
            base = ram.find(probe) - sym["start"]
            self.assertGreater(base, 0, "the program was not found in RAM")
            values.append((int.from_bytes(ram[base + sym["frame_count"]:base + sym["frame_count"] + 4], "big"),
                           int.from_bytes(ram[base + sym["late_frames"]:base + sym["late_frames"] + 4], "big")))
        self.assertEqual(values[1][0] - values[0][0], second - first)
        self.assertEqual(values[1][1], values[0][1])


if __name__ == "__main__":
    unittest.main()
