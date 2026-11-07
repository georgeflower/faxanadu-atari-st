"""The package packer (tools/lz.py)."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import lz  # noqa: E402


class PackTest(unittest.TestCase):
    def test_round_trip(self):
        rng = random.Random(5)
        samples = [b"", b"a", b"abc", b"abcd", bytes(100000), bytes(range(256)) * 40, bytes(rng.randrange(256) for _ in range(3000)),
                   bytes(rng.choice(b"ab") for _ in range(5000)), (b"0123456789" * 50 + bytes(rng.randrange(256) for _ in range(20))) * 30]
        for data in samples:
            self.assertEqual(lz.unpack(lz.pack(data)), data, len(data))

    def test_repeats_get_smaller(self):
        self.assertLess(len(lz.pack(b"faxanadu" * 500)), 100)


if __name__ == "__main__":
    unittest.main()
