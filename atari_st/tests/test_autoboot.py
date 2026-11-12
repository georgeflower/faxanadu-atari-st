"""The game's disk boots: Hatari starts from the floppy image `make disk` writes (no hard drive, nothing started by hand), TOS runs
A:\\AUTO\\FAXANADU.PRG, and the program finds its data files in the root of the disk (the current folder of a program in AUTO is the root):
the first package and TOWN.DAT are loaded and the program's own VBL counts."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402  (the TOS image)

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class AutoBootTests(unittest.TestCase):
    def test_the_disk_boots_into_the_game_from_its_auto_folder(self) -> None:
        import make_disk

        work = ROOT / "build" / "shots_autoboot"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        image = work / "BOOT.st"
        subprocess.run(["make", "-C", str(ROOT), "disk", f"DISK={image}"], check=True, capture_output=True)
        files = make_disk.read_disk(image.read_bytes())
        self.assertIn("AUTO/FAXANADU.PRG", files)
        self.assertNotIn("FAXANADU.PRG", files, "the program is only in AUTO")
        self.assertIn("TOWN.DAT", files, "the data stays in the root")

        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        program = (ROOT / "build" / "viewer.bin").read_bytes()
        script = work / "dbg.ini"
        caps = (2400, 2500)
        for n, vbl in enumerate(caps):
            (work / f"c{n}.ini").write_text(f"savebin {work / f'ram{n}.bin'} 0 $80000\ncont\n", encoding="utf-8")
        script.write_text("".join(f"b VBL = {vbl} :once :file {work / f'c{n}.ini'}\n" for n, vbl in enumerate(caps)), encoding="utf-8")
        command = [shutil.which("hatari"), "--tos", str(tv.TOS), "--machine", "st", "--memsize", "0", "--fast-forward", "true", "--fastfdc", "true",
                   "--sound", "off", "--disable-video", "true", "--disk-a", str(image), "--parse", str(script), "--run-vbls", str(caps[-1] + 50)]
        subprocess.run(command, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL,
                       env=dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy"))
        rams = [(work / f"ram{n}.bin").read_bytes() for n in range(len(caps))]
        start = program[sym["start"]:sym["start"] + 48]
        base = rams[0].find(start) - sym["start"]
        self.assertGreater(base, 0, "the program is in memory: TOS ran it from AUTO")

        def long(ram: bytes, name: str) -> int:
            return int.from_bytes(ram[base + sym[name]:base + sym[name] + 4], "big")

        self.assertNotEqual(long(rams[1], "town_ptr"), 0, "TOWN.DAT was found in the root and loaded")
        self.assertGreater(long(rams[1], "frame_count"), long(rams[0], "frame_count"), "the program runs (its VBL counts)")


if __name__ == "__main__":
    unittest.main()
