"""The PRG packer and the disk image maker."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_disk  # noqa: E402
import make_prg  # noqa: E402


class PrgTests(unittest.TestCase):
    def test_header_is_a_tos_executable_with_no_relocation(self) -> None:
        payload = bytes(range(256)) * 3
        prg = make_prg.build_prg(payload)
        self.assertEqual(prg[:2], b"\x60\x1a")
        self.assertEqual(int.from_bytes(prg[2:6], "big"), len(payload))
        self.assertEqual(len(prg), make_prg.HEADER_SIZE + len(payload))
        self.assertEqual(prg[make_prg.HEADER_SIZE:], payload)

    def test_check_accepts_what_build_makes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T.PRG"
            path.write_bytes(make_prg.build_prg(b"\x4e\x75" * 10))
            make_prg.check_prg(path)


class DiskTests(unittest.TestCase):
    def test_files_survive_a_round_trip(self) -> None:
        files = [("FAXANADU.PRG", bytes(range(256)) * 40), ("A.DAT", b"x"), ("EMPTY.DAT", b"")]
        image = make_disk.build_disk(files)
        self.assertEqual(len(image), 720 * 1024)
        back = make_disk.read_disk(image)
        self.assertEqual(back["FAXANADU.PRG"], files[0][1])
        self.assertEqual(back["A.DAT"], b"x")

    def test_a_file_too_big_for_the_disk_is_refused(self) -> None:
        with self.assertRaises(make_disk.DiskFull):
            make_disk.build_disk([("BIG.DAT", bytes(800 * 1024))])


if __name__ == "__main__":
    unittest.main()
