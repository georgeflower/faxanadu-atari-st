"""The start-up code (src/main.s) on machine68k, with GEMDOS and XBIOS replaced by small stubs that log their calls.

It checks what a real TOS would care about: the order of the calls, the size handed to Mshrink, that the screen is
filled and the palette set while the program waits for a key, and that the palette is put back before Pterm0.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AS = "m68k-linux-gnu-as"
LD = "m68k-linux-gnu-ld"
OBJCOPY = "m68k-linux-gnu-objcopy"

STUB_BASE = 0x400
LOAD = 0x10000          # where the image is loaded; the real one sits behind a 256-byte basepage
BASEPAGE = LOAD - 0x100
SCREEN = 0x40000
STACK = 0x7F000
LOG = 0x3000            # the call log: one word per call, GEMDOS 0x0000 + n, XBIOS 0x0E00 + n
LOG_PTR = 0x2FF0
MSHRINK_SIZE = 0x2FF4
PALETTE_AT_KEY = 0x3100  # the palette as it is when the program asks for a key
PALETTE = 0xFF8240
ORIGINAL_PALETTE = [0x0123, 0x0234, 0x0345, 0x0456, 0x0567, 0x0671, 0x0712, 0x0123,
                    0x0777, 0x0666, 0x0555, 0x0444, 0x0333, 0x0222, 0x0111, 0x0001]

STUBS = f"""
    .text
    bra.w trap1                 | the vector for trap #1 points at STUB_BASE
    bra.w trap14                | and the one for trap #14 at STUB_BASE + 4
trap1:
    move.w 6(%sp), %d1
    bsr log_call
    cmpi.w #0, %d1
    beq done
    cmpi.w #0x4A, %d1
    bne 1f
    move.l 14(%sp), {MSHRINK_SIZE}
    moveq #0, %d0
    rte
1:  cmpi.w #32, %d1
    bne 2f
    move.l #0x5000, %d0
    rte
2:  cmpi.w #7, %d1
    bne 3f
    lea {PALETTE}, %a0
    lea {PALETTE_AT_KEY}, %a1
    moveq #15, %d2
4:  move.w (%a0)+, (%a1)+
    dbra %d2, 4b
    move.l #0x00390020, %d0
    rte
3:  moveq #0, %d0
    rte
trap14:
    move.w 6(%sp), %d1
    ori.w #0x0E00, %d1
    bsr log_call
    cmpi.w #0x0E02, %d1
    bne 1f
    move.l #{SCREEN}, %d0
    rte
1:  moveq #0, %d0
    rte
log_call:
    movea.l {LOG_PTR}, %a0
    move.w %d1, (%a0)+
    move.l %a0, {LOG_PTR}
    rts
done:
    bra.s done
"""


def toolchain_ok() -> bool:
    if not all(shutil.which(t) for t in (AS, LD, OBJCOPY)):
        return False
    try:
        import machine68k  # noqa: F401
    except ImportError:
        return False
    return True


def assemble(directory: Path, name: str, source: Path, link_args: list[str]) -> bytes:
    subprocess.run([AS, "-m68000", "-I", str(source.parent), "-o", str(directory / f"{name}.o"), str(source)],
                   check=True, capture_output=True)
    subprocess.run([LD, *link_args, "-nostdlib", "-e", "0", "-o", str(directory / f"{name}.elf"),
                    str(directory / f"{name}.o")], check=True, capture_output=True)
    subprocess.run([OBJCOPY, "-O", "binary", str(directory / f"{name}.elf"), str(directory / f"{name}.bin")], check=True)
    return (directory / f"{name}.bin").read_bytes()


@unittest.skipUnless(toolchain_ok(), "needs the m68k binutils and machine68k")
class StartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import machine68k as m

        cls.m = m
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stub_source = tmp / "stubs.s"
        stub_source.write_text(STUBS, encoding="utf-8")
        cls.stubs = assemble(tmp, "stubs", stub_source, [f"-Ttext={STUB_BASE:#x}"])
        # The real image, linked as the build does (the code is position independent, so any load address will do).
        cls.image = assemble(tmp, "main", ROOT / "src" / "main.s", ["-T", str(ROOT / "link.ld")])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_program(self):
        m = self.m
        machine = m.Machine(m.CPUType.M68000, 16384)        # 16 MB, so the hardware registers are plain memory
        mem, cpu = machine.mem, machine.cpu
        mem.w_block(STUB_BASE, self.stubs)
        mem.w_block(LOAD, self.image)
        mem.w32(0x84, STUB_BASE)                             # trap #1
        mem.w32(0xB8, STUB_BASE + 4)                         # trap #14
        mem.w32(LOG_PTR, LOG)
        for i, word in enumerate(ORIGINAL_PALETTE):
            mem.w16(PALETTE + 2 * i, word)
        mem.w32(STACK + 4, BASEPAGE)                         # a program starts with its basepage at 4(sp)
        cpu.set_instr_hook_callback(lambda pc: machine.abort_execute() if mem.r16(pc) == 0x60FE else None)
        cpu.w_sr(0x2700)
        cpu.w_sp(STACK)
        cpu.w_pc(LOAD)
        machine.execute(50_000_000)
        return mem

    def test_calls_come_in_the_order_a_tos_program_needs(self) -> None:
        mem = self.run_program()
        end = mem.r32(LOG_PTR)
        calls = [mem.r16(a) for a in range(LOG, end, 2)]
        # Mshrink, Super(0), Setscreen, Cconws (hide the cursor), Physbase, Crawcin, Cconws, Super(old), Pterm0
        self.assertEqual(calls, [0x4A, 32, 0x0E05, 9, 0x0E02, 7, 9, 32, 0])

    def test_mshrink_keeps_the_image_and_the_basepage(self) -> None:
        mem = self.run_program()
        self.assertEqual(mem.r32(MSHRINK_SIZE), len(self.image) + 0x100)

    def test_the_test_card_is_drawn_and_the_palette_set_while_waiting(self) -> None:
        mem = self.run_program()
        # Group n of every line is colour n (mod 16): each plane word is all ones when its colour bit is set.
        for line in (0, 99, 199):
            for group in (0, 1, 5, 15, 16, 19):
                words = [mem.r16(SCREEN + line * 160 + group * 8 + 2 * p) for p in range(4)]
                expected = [0xFFFF if (group & 15) >> p & 1 else 0 for p in range(4)]
                self.assertEqual(words, expected, f"line {line}, group {group}")
        shown = [mem.r16(PALETTE_AT_KEY + 2 * i) for i in range(16)]
        self.assertEqual(shown[:3], [0x000, 0x777, 0x700])
        self.assertNotEqual(shown, ORIGINAL_PALETTE)

    def test_the_palette_is_put_back_before_leaving(self) -> None:
        mem = self.run_program()
        self.assertEqual([mem.r16(PALETTE + 2 * i) for i in range(16)], ORIGINAL_PALETTE)


if __name__ == "__main__":
    unittest.main()
