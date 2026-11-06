"""The Python password model against the Europe ROM in jsnes (needs node, the harness's packages and your ROM): random game states written into the ROM's
RAM give the same bytes and characters from Password_GenerateStateAndReset and Password_GetNext6Bits, and typed passwords (right ones, a character
changed, one short, one too long) are accepted and loaded or refused by Password_Maybe_CheckPasswordLength and Password_Load as the model says."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


@unittest.skipUnless(ROM.exists() and shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs the ROM and the jsnes harness")
class PasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "password.json"
            subprocess.run(["node", "passwordgolden.mjs", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            cls.golden = json.loads(out.read_text())

    def test_the_bytes_and_characters_are_the_roms(self) -> None:
        import password_model as pm

        for n, case in enumerate(self.golden["cases"]):
            data, count = pm.encode(pm.State(**case["state"]))
            self.assertEqual((count, list(data)), (case["count"], case["data"][:len(data)]), f"state {n}")
            self.assertEqual([pm.CHARS.index(c) for c in pm.characters(data, count)], case["chars"], f"state {n}")

    def test_what_the_entry_screen_accepts_and_loads_is_the_roms(self) -> None:
        import password_model as pm

        accepted = 0
        for n, entry in enumerate(self.golden["entries"]):
            got = pm.decode("".join(pm.CHARS[c] for c in entry["chars"]))
            self.assertEqual(got, pm.State(**entry["state"]) if entry["ok"] else None, f"entry {n}: {entry['chars']}")
            accepted += entry["ok"]
        self.assertGreater(accepted, 30)
        self.assertGreater(len(self.golden["entries"]) - accepted, 15)

    def test_a_password_that_was_shown_gives_the_state_back(self) -> None:
        import password_model as pm

        for case in self.golden["cases"]:
            state = pm.State(**case["state"])
            if pm.decode(pm.password(state)) is not None:
                self.assertEqual(pm.decode(pm.password(state)), state)


if __name__ == "__main__":
    unittest.main()
