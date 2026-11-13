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


    def test_the_program_started_in_its_auto_folder_finds_its_data_in_the_root(self) -> None:
        """Double clicked on the desktop the program starts with A:\\AUTO as the current folder (the author saw "The package file ... is missing");
        the start-up sets the root (Dsetpath). Here a small launcher in AUTO does what the desktop does: Dsetpath to the program's folder, then Pexec
        of FAXANADU.PRG, on a floppy with the disk's files and the program in a folder of its own (Hatari's own hard drive does not follow Dsetpath)."""
        import make_disk

        work = ROOT / "build" / "shots_autodesk"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        image = work / "DESK.st"
        subprocess.run(["make", "-C", str(ROOT), "disk", f"DISK={image}"], check=True, capture_output=True)
        launcher = work / "launch.s"
        launcher.write_text("""
    .text
start:
    movea.l 4(%sp), %a0
    move.l #0x400, -(%sp)
    move.l %a0, -(%sp)
    clr.w -(%sp)
    move.w #0x4A, -(%sp)
    trap #1                         | Mshrink: room for the game
    lea 12(%sp), %sp
    pea path(%pc)
    move.w #0x3B, -(%sp)
    trap #1                         | Dsetpath("\\AUTO"), as the desktop does for a program in that folder
    addq.l #6, %sp
    pea env(%pc)
    pea env(%pc)
    pea name(%pc)
    clr.w -(%sp)
    move.w #0x4B, -(%sp)
    trap #1                         | Pexec(0, "FAXANADU.PRG")
    lea 16(%sp), %sp
    clr.w -(%sp)
    trap #1
path: .asciz "\\\\GAME"
name: .asciz "FAXANADU.PRG"
env:  .byte 0, 0
    .even
""", encoding="utf-8")
        subprocess.run(["m68k-linux-gnu-as", "-m68000", "-o", str(work / "launch.o"), str(launcher)], check=True)
        subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", str(work / "launch.o"), str(work / "launch.bin")], check=True)
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_prg.py"), str(work / "launch.bin"), str(work / "LAUNCH.PRG")], check=True)
        files = make_disk.read_disk(image.read_bytes())
        files["GAME/FAXANADU.PRG"] = files.pop("AUTO/FAXANADU.PRG")
        files["AUTO/LAUNCH.PRG"] = (work / "LAUNCH.PRG").read_bytes()
        floppy = work / "LAUNCH.st"
        floppy.write_bytes(make_disk.build_disk(list(files.items())))
        nm = subprocess.run(["m68k-linux-gnu-nm", str(ROOT / "build" / "viewer.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        sym = {line.split()[2]: int(line.split()[0], 16) for line in nm if len(line.split()) == 3}
        program = (ROOT / "build" / "viewer.bin").read_bytes()
        (work / "c0.ini").write_text(f"savebin {work / 'ram0.bin'} 0 $80000\ncont\n", encoding="utf-8")
        script = work / "dbg.ini"
        script.write_text(f"b VBL = 2500 :once :file {work / 'c0.ini'}\n", encoding="utf-8")
        command = [shutil.which("hatari"), "--tos", str(tv.TOS), "--machine", "st", "--memsize", "0", "--fast-forward", "true", "--sound", "off",
                   "--fastfdc", "true", "--disable-video", "true", "--disk-a", str(floppy), "--parse", str(script), "--run-vbls", "2550"]
        subprocess.run(command, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL,
                       env=dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy"))
        ram = (work / "ram0.bin").read_bytes()
        base = ram.find(program[sym["start"]:sym["start"] + 48]) - sym["start"]
        self.assertGreater(base, 0, "the program is running")
        self.assertNotEqual(int.from_bytes(ram[base + sym["town_ptr"]:base + sym["town_ptr"] + 4], "big"), 0, "TOWN.DAT was found in the root and loaded")

if __name__ == "__main__":
    unittest.main()
