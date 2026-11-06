"""The Python magic model against a golden run recorded from the ROM in jsnes (needs node, the harness's packages and your ROM): the spell's state
every frame, the magic power, the sound effect, and the spell's sprites in the next frame's OAM."""
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
class MagicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr
        import hero_physics as hp

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "magic.json"
            subprocess.run(["node", "magicgolden.mjs", str(out)], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
            cls.scenarios = json.loads(out.read_text())
        cls.rom = fr.Rom(ROM)
        a = fm.area(cls.rom, 0)
        props = fm.block_properties(cls.rom, a)
        cls.impassable = [hp.IMPASSABLE[props[b] & 15] for b in fm.decode_screen(cls.rom, a, 0)]

    def replay(self, s: dict):
        """Yields (frame, the model's spell after the frame, the magic power, the sound effect it asked for)."""
        import magic_model as mm

        impassable = list(self.impassable)
        for r, c in s["walls"]:
            impassable[r * 16 + c] = 1
        spell, mp = mm.Spell(), s["mp"]
        for f in s["frames"]:
            sound = None
            if spell.type < 0:
                mp, sound = mm.cast(spell, f["hx"], f["hy"], f["hflags"], mp, s["spell"], f["joy"], f["changed"])
            if spell.type >= 0:
                sound = mm.step(spell, impassable) or sound
            yield f, spell, mp, sound

    def test_the_spells_move_and_stop_as_in_the_rom_frame_by_frame(self) -> None:
        self.assertGreater(len(self.scenarios), 20)
        for s in self.scenarios:
            for n, (f, spell, mp, _) in enumerate(self.replay(s)):
                got = (spell.type, spell.flags if spell.type >= 0 else f["flags"], spell.x, spell.xfrac, spell.y, spell.yfrac, spell.counter, spell.phase, mp)
                want = (f["type"], f["flags"], f["x"], f["xfrac"], f["y"], f["yfrac"], f["counter"], f["phase"], f["mp"])
                if spell.type < 0 and f["type"] == 255:
                    got = (255,) + want[1:8] + (mp,)                   # a cleared spell keeps what it had
                self.assertEqual(got, want, f"spell {s['spell']} right={s['right']} {s['name']}: frame {n}")

    def test_the_picture_follows_the_interrupt_counter_and_matches_the_roms_sprites(self) -> None:
        import faxanadu_sprites as fs
        import magic_model as mm

        checked = 0
        for s in self.scenarios:
            states = [(sp.type, sp.flags, sp.x, sp.y, sp.counter, sp.phase, f["ic"]) for f, sp, _, _ in self.replay(s)]
            for n in range(len(states) - 1):                           # the OAM lags the state by one frame
                t, flags, x, y, counter, phase, ic = states[n]
                idx = mm.appearance(mm.Spell(type=t, flags=flags, x=x, y=y, counter=counter, phase=phase), ic) if t >= 0 else None
                want = sorted(map(tuple, s["frames"][n + 1]["oam"]))
                got = []
                if idx is not None:
                    app = fs.appearance(self.rom, idx, "TILEINFO_ENTITY_ADDRS")
                    got = sorted((sp.y, sp.tile, sp.attr, sp.x) for sp in fs.place(app, x, y, flags & 0x40))
                self.assertEqual(got, want, f"spell {s['spell']} right={s['right']} {s['name']}: frame {n}, picture {idx}")
                checked += 1
        self.assertGreater(checked, 1000)

    def test_the_sounds_are_the_cast_sound_and_the_wall_hit(self) -> None:
        import magic_model as mm

        seen = set()
        for s in self.scenarios:
            for f, _, _, sound in self.replay(s):
                if sound is not None:
                    seen.add(sound)
                    self.assertEqual(f["snd"], sound, f"spell {s['spell']} {s['name']}")
        self.assertEqual(seen, {mm.SOUND_CAST, mm.SOUND_TILTE, mm.SOUND_HIT})


if __name__ == "__main__":
    unittest.main()
