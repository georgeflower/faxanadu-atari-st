"""The sound: tools/build_sound.py turns the recorded NES sound channels into YM2149 frames, src/sound.s plays them.

The converter is tried on invented recordings (the real ones come from the ROM and are not in the repository); the 68000 player runs on
machine68k with a sound.bin made from them and has to give, tick by tick, what a plain Python player gives.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_sound as bs  # noqa: E402

ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
TOS = Path(os.environ.get("TOS") or os.environ.get("TOS_PAL") or "")
AS, LD, NM = "m68k-linux-gnu-as", "m68k-linux-gnu-ld", "m68k-linux-gnu-nm"
LOAD = 0x10000
BIN_AT = 0x100000
STACK = 0x7F000
CALL = 0x400
SND_MPTR, SND_SPTR, SND_MLEFT, SND_SLEFT, SND_MREGS, SND_OUT = 4, 12, 16, 20, 22, 34


def silent():
    return [[0, 0, 0], [0, 0, 0], [0, 0], [4, 0, 0]]


def song_states(n_loops: int = 10) -> list:
    """An intro of 40 frames and a pattern of 20 that repeats: pulse 1 holds notes, pulse 2 has an envelope, the triangle a bass, a
    drum of noise now and then."""
    out = []
    for i in range(40):
        s = silent()
        s[0] = [200 + i, 10, 2]
        out.append(s)
    for _ in range(n_loops):
        for i in range(20):
            s = silent()
            s[0] = [232 if i < 10 else 207, 12 - (i % 10) // 2, 2] if i % 10 < 8 else [0, 0, 0]
            s[1] = [116, 6, 1] if i < 15 else [0, 0, 0]
            s[2] = [155, 1] if i < 12 else [0, 0]
            s[3] = [32, 9 - i // 3, 0] if i in (0, 1, 2, 10, 11) else [4, 0, 0]
            out.append(s)
    return out


def sfx_states() -> list:
    out = []
    for i in range(10):
        s = silent()
        s[1] = [100 + 5 * i, 12, 2] if i < 6 else [0, 0, 0]
        s[3] = [16, 8, 0] if 3 <= i <= 8 else [4, 0, 0]
        out.append(s)
    return out


def noise_only_sfx_states() -> list:
    out = []
    for i in range(5):
        s = silent()
        s[3] = [64, 10 - i, 0]
        out.append(s)
    return out


def write_recordings(directory: Path) -> None:
    states = song_states()
    (directory / "m1.json").write_text(json.dumps({"musicCurrent": [0x81] * len(states), "state": states}))
    ending = song_states(1)[:30]
    (directory / "m2.json").write_text(json.dumps({"musicCurrent": [0x82] * 28 + [0, 0], "state": ending}))
    (directory / "s1.json").write_text(json.dumps({"state": sfx_states() + [silent()] * 5}))
    (directory / "s2.json").write_text(json.dumps({"state": noise_only_sfx_states() + [silent()] * 3}))


class ConverterTests(unittest.TestCase):
    def test_the_nes_registers_become_ym_registers(self) -> None:
        # 232 on a pulse is 446 Hz on a PAL NES: the YM's period is 2 MHz / (16 * 446) = 280
        regs, bits = bs.ym_frame([[232, 10, 2], [0, 0, 0], [116, 1], [4, 0, 0]])
        self.assertEqual(bits, 1 | 4)
        self.assertEqual(regs[0] | regs[1] << 8, 280)
        self.assertEqual(regs[4] | regs[5] << 8, round(2 * 117 * 2e6 / 1662607))      # the triangle: an octave down
        self.assertEqual(regs[7], 0xFF & ~1 & ~4)                                       # tone A and C on, the port bits high
        self.assertEqual((regs[8], regs[9], regs[10]), (bs.ym_volume(10), 0, bs.TRIANGLE_LEVEL))
        self.assertEqual(bs.ym_volume(15), 15)
        self.assertEqual(bs.ym_volume(0), 0)
        self.assertTrue(all(bs.ym_volume(v) <= bs.ym_volume(v + 1) for v in range(1, 15)))

    def test_noise_shares_channel_c_with_the_triangle(self) -> None:
        regs, bits = bs.ym_frame([[0, 0, 0], [0, 0, 0], [0, 0], [64, 10, 0]])
        self.assertEqual(bits, 8)
        self.assertEqual(regs[7], 0xFF & ~0x20)                                         # noise on C, no tone
        self.assertEqual(regs[10], bs.ym_volume(10))
        self.assertEqual(regs[6], round(64 * 2e6 / (16 * 1662607)))
        regs, bits = bs.ym_frame([[0, 0, 0], [0, 0, 0], [155, 1], [64, 10, 0]])
        self.assertEqual(regs[7], 0xFF & ~0x20 & ~4)                                    # both
        self.assertEqual(regs[10], max(bs.TRIANGLE_LEVEL, bs.ym_volume(10)))

    def test_the_loop_is_found_in_the_middle_of_jitter(self) -> None:
        frames = [bs.ym_frame(s)[0] + b"\0" for s in song_states()]
        self.assertEqual(bs.find_loop(frames), (40, 20))
        frames[40 + 20 * 3 + 5] = frames[0]                                              # a note that ended a frame early
        self.assertEqual(bs.find_loop(frames), (40, 20))

    def test_a_song_survives_the_packing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            write_recordings(Path(d))
            data, info = bs.build(Path(d), 2, 2)
        self.assertEqual(struct.unpack_from(">HH", data, 0), (2, 2))
        offsets = [struct.unpack_from(">L", data, 4 + 4 * i)[0] for i in range(4)]
        self.assertTrue(all(o % 2 == 0 for o in offsets))
        frames, loop_left, loop_offset = struct.unpack_from(">HHL", data, offsets[0])
        self.assertEqual((frames, loop_left), (60, 20))
        self.assertEqual(info["m1"][:2], (60, 40))
        expected = [bs.ym_frame(s)[0] for s in song_states()[:60]]
        self.assertEqual(bs.parse_song(data, offsets[0]), expected)
        # the loop point is stored whole: the 68000 jumps there without having seen the frames before
        self.assertEqual(data[offsets[0] + 8 + loop_offset], 0xFF)
        # a song that ends: no loop; the silence at its end is cut and one silent frame stays
        frames, loop_left, _ = struct.unpack_from(">HHL", data, offsets[1])
        self.assertEqual(loop_left, 0)
        parsed = bs.parse_song(data, offsets[1])
        self.assertEqual(len(parsed), frames)
        self.assertNotEqual(parsed[-2][8:11], b"\0\0\0")
        self.assertEqual(parsed[-1][7:11], b"\xFF\0\0\0")

    def test_a_sound_effect_takes_the_channels_it_uses_from_its_first_sound_to_its_last(self) -> None:
        frames = bs.sfx_frames({"state": sfx_states() + [silent()] * 5})
        self.assertEqual(len(frames), 9)                                                # trailing silence cut
        masks = [f[11] for f in frames]
        self.assertEqual(masks, [2, 2, 2, 2 | 8, 2 | 8, 2 | 8, 8, 8, 8])
        self.assertEqual(bs.sfx_frames({"state": [silent()] * 4}), [])


def toolchain_ok() -> bool:
    if not all(shutil.which(t) for t in (AS, LD, NM)):
        return False
    try:
        import machine68k  # noqa: F401
    except ImportError:
        return False
    return True


def reference(data: bytes, song: int, sfx: int | None, sfx_at: int, ticks: int) -> list[bytes]:
    """What the YM is given each tick: the song (looping), with the sound effect started at tick sfx_at over it."""
    n_music, n_sfx = struct.unpack_from(">HH", data, 0)
    offsets = [struct.unpack_from(">L", data, 4 + 4 * i)[0] for i in range(n_music + n_sfx)]
    frames = bs.parse_song(data, offsets[song - 1])
    total, loop_left, _ = struct.unpack_from(">HHL", data, offsets[song - 1])
    sfx_frames = []
    if sfx is not None:
        o = offsets[n_music + sfx - 1]
        count = struct.unpack_from(">H", data, o)[0]
        sfx_frames = [data[o + 2 + 12 * i:o + 14 + 12 * i] for i in range(count)]
    out = []
    for t in range(ticks):
        if t < total:
            regs = bytearray(frames[t])
        elif loop_left:
            regs = bytearray(frames[total - loop_left + (t - total) % loop_left])
        else:
            regs = bytearray(frames[-1])                                            # the last tones stay, the mixer and the volumes go
            regs[7:11] = b"\xFF\0\0\0"
        i = t - sfx_at
        if 0 <= i < len(sfx_frames):
            f, mask = sfx_frames[i], sfx_frames[i][11]
            for bit, idx, vol, mix in ((0, (0, 1), 8, 0x09), (1, (2, 3), 9, 0x12), (2, (4, 5), 10, 0x04)):
                if mask >> bit & 1:
                    for k in idx:
                        regs[k] = f[k]
                    regs[vol] = f[vol]
                    regs[7] = regs[7] ^ ((regs[7] ^ f[7]) & mix)
            if mask & 8:
                regs[6] = f[6]
                regs[7] = regs[7] ^ ((regs[7] ^ f[7]) & 0x20)
                if not mask & 4:
                    regs[10] = max(regs[10], f[10])
        out.append(bytes(regs))
    return out


@unittest.skipUnless(toolchain_ok(), "needs the m68k binutils and machine68k")
class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import machine68k as m

        cls.m = m
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "rec").mkdir()
        write_recordings(tmp / "rec")
        cls.data, _ = bs.build(tmp / "rec", 2, 2)
        source = tmp / "sound_test.s"
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

    def machine(self, data: bytes | None = None):
        m = self.m
        machine = m.Machine(m.CPUType.M68000, 16384)
        machine.mem.w_block(LOAD, self.image)
        machine.mem.w_block(BIN_AT, self.data if data is None else data)
        return machine

    def call(self, machine, name: str, d0: int = 0, a0: int = 0) -> None:
        m = self.m
        mem, cpu = machine.mem, machine.cpu
        mem.w16(CALL, 0x4EB9)
        mem.w32(CALL + 2, self.sym[name])
        mem.w16(CALL + 6, 0x60FE)

        def on_instr(pc):
            if mem.r16(pc) == 0x60FE:
                machine.abort_execute()

        cpu.set_instr_hook_callback(on_instr)
        cpu.w_sr(0x2700)
        cpu.w_sp(STACK)
        cpu.w_reg(m.Register.D0, d0)
        cpu.w_reg(m.Register.A0, a0)
        cpu.w_pc(CALL)
        machine.execute(200_000)

    def out(self, machine) -> bytes:
        return bytes(machine.mem.r8(self.sym["snd_state"] + SND_OUT + i) for i in range(11))

    def play(self, song: int, sfx: int | None, sfx_at: int, ticks: int, data: bytes | None = None) -> list[bytes]:
        mc = self.machine(data)
        self.call(mc, "sound_init", a0=BIN_AT)
        self.call(mc, "sound_play_music", d0=song)
        got = []
        for t in range(ticks):
            if sfx is not None and t == sfx_at:
                self.call(mc, "sound_play_sfx", d0=sfx)
            self.call(mc, "sound_tick")
            got.append(self.out(mc))
        return got

    def test_a_song_plays_frame_by_frame_and_loops(self) -> None:
        got = self.play(1, None, 0, 60 + 3 * 20 + 9)
        self.assertEqual(got, [r[:11] for r in reference(self.data, 1, None, 0, len(got))])

    def test_a_song_that_ends_goes_quiet(self) -> None:
        got = self.play(2, None, 0, 40)
        self.assertEqual(got, [r[:11] for r in reference(self.data, 2, None, 0, 40)])
        self.assertEqual(got[-1][8:11], b"\0\0\0")
        self.assertEqual(got[-1][7], 0xFF)

    def test_a_sound_effect_takes_over_its_channels_and_gives_them_back(self) -> None:
        for sfx in (1, 2):
            with self.subTest(sfx=sfx):
                got = self.play(1, sfx, 12, 40)
                self.assertEqual(got, [r[:11] for r in reference(self.data, 1, sfx, 12, 40)])
        plain = self.play(1, None, 0, 40)
        loud = self.play(1, 1, 12, 40)
        self.assertNotEqual(plain[14], loud[14])
        self.assertEqual(plain[30], loud[30])

    def test_no_sound_data_means_no_sound(self) -> None:
        mc = self.machine()
        self.call(mc, "sound_init", a0=0)
        self.call(mc, "sound_play_music", d0=1)
        self.call(mc, "sound_tick")
        self.assertEqual(self.out(mc), b"\0" * 7 + b"\xFF" + b"\0\0\0")
        self.assertEqual(mc.mem.r8(0xFF8802), 0)                                      # nothing was sent to the chip

    def test_the_chip_is_given_registers_0_to_10_and_not_the_floppy_lines(self) -> None:
        mc = self.machine()
        self.call(mc, "sound_init", a0=BIN_AT)
        self.call(mc, "sound_play_music", d0=1)
        mem = mc.mem
        self.call(mc, "sound_tick")
        self.assertEqual(mem.r8(0xFF8800), 10)                                        # the last register selected
        self.assertEqual(mem.r8(0xFF8802), self.out(mc)[10])


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class ViewerSoundTests(unittest.TestCase):
    def test_the_viewer_plays_the_songs_of_the_rom(self) -> None:
        """Eolis's song (7) from the start: after about 300 of its own VBLs the registers the chip was given are those of the song's frame
        for that tick (the program's frame counter says which; the dump may land a tick either side)."""
        import hatari_shot as hs

        subprocess.run(["make", "-C", str(ROOT), "viewer"], check=True, capture_output=True)
        data = (ROOT / "build" / "generated" / "sound.bin").read_bytes()
        n_music = struct.unpack_from(">H", data, 0)[0]
        if n_music < 7:
            self.skipTest("the viewer was built without sound (node and the ROM harness are needed to record it)")
        nm = subprocess.run([NM, str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        image = (ROOT / "build" / "viewer.bin").read_bytes()
        work = ROOT / "build" / "shots_sound"
        work.mkdir(parents=True, exist_ok=True)
        prg = ROOT / "build" / "VIEWER.PRG"
        hatari = shutil.which("hatari")
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        script = f"b VBL > 499 :once :file {work / 'c0.ini'}\n"
        hs.run_hatari(hatari, TOS, prg, work, 500, "0", script, None)
        ram = (work / "ram0.bin").read_bytes()
        base = ram.find(image[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0)
        frame_count = int.from_bytes(ram[base + sym["frame_count"]:base + sym["frame_count"] + 4], "big")
        out = ram[base + sym["snd_state"] + SND_OUT:base + sym["snd_state"] + SND_OUT + 11]
        self.assertGreater(frame_count, 250)
        offsets = [struct.unpack_from(">L", data, 4 + 4 * i)[0] for i in range(n_music)]
        frames = bs.parse_song(data, offsets[6])
        total, loop_left, _ = struct.unpack_from(">HHL", data, offsets[6])
        plausible = []
        for t in range(frame_count - 3, frame_count + 2):
            plausible.append(frames[t] if t < total else frames[total - loop_left + (t - total) % loop_left])
        self.assertIn(out, plausible, f"frame {frame_count}: {out.hex()} is not near {plausible[2].hex()}")


if __name__ == "__main__":
    unittest.main()
