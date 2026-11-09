"""The script interpreter (src/town.s) against the ROM's, in Hatari: many scripts in one run. The build (BATCH=n) takes n jobs from build/generated/batch.bin: each is a script,
a player state and what the buttons do (`auto_pad`: A for 4 frames of every 8, or B and then A); the program runs them one after the other and leaves the state after each
and the actions it ran (and the byte after each: a message's number) in `batch_out`. The expected result of a job is the Python model of the ROM's interpreter
(tools/iscript_model.py), which tests/test_iscript_model.py checks against the ROM in jsnes.

The jobs: the quest scripts (the springs, the Ruby ring), the seller of Elixir, the marks, the doctors, the Battle Suit branch of $55, Fraternal's Demon's Ring, the final
temple and the shops, each on states that take its branches. The item messages $80-$97 are not scripts of the people: the pickup and use code shows them."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_viewer as tv  # noqa: E402

INV_BYTES, BJ_STATE, BO_SIZE, TRACE = 38, 58, 92, 16
POLICY = {"A": 1, "BA": 2}
FRAMES = 100000                         # the frames the whole list takes (257 jobs: 89,000), the capture waits for them

# (script, state, buttons). A state is the name of one of iscript_model.PRESETS or a dict: {base: a preset, and the changes}.
JOBS: list[tuple[int, object, str]] = []
for ident in (0x25, 0x26, 0x27, 0x24, 0x20, 0x22, 0x23, 0x21):                               # springs, the Ruby ring and the other quest scripts
    JOBS += [(ident, "fresh", "A"), (ident, dict(base="rich", quests=1), "A"), (ident, dict(base="rich", quests=3), "A"), (ident, "full", "A")]
JOBS += [(0x26, "elixir", "A"), (0x26, dict(base="elixir", quests=1), "A"), (0x26, "elixir", "BA")]                  # the spring that takes the Elixir
for ident in (0x04, 0x03, 0x4B, 0x46, 0x43, 0x74):                                          # items given or asked for (Fraternal $74 wants the Demon's Ring)
    JOBS += [(ident, "fresh", "A"), (ident, "full", "A"), (ident, "mid", "A")]
for ident in (0x02, 0x7B, 0x7C, 0x7D, 0x7E):                                                 # the marks
    JOBS += [(ident, "rich", "A")]
for ident in (0x2A, 0x7A, 0x0B, 0x0E, 0x0F, 0x15, 0x38, 0x3A, 0x47, 0x49, 0x56, 0x58, 0x67, 0x76):  # doctors and meat
    JOBS += [(ident, "fresh", "A"), (ident, "rich", "A"), (ident, "mid", "BA")]
for ident in (0x55, 0x54, 0x53, 0x52, 0x51, 0x50):                                           # the Battle Suit branch of $55
    JOBS += [(ident, "fresh", "A"), (ident, "full", "A"), (ident, dict(base="full", special=0), "A"), (ident, dict(base="rich", lists=[[0], [3], [0, 1], [0, 1], [0x10]]), "A")]
for ident in (0x78, 0x1C, 0x29, 0x3D, 0x4C, 0x69):                                           # the final temple and the temples (gurus: rank, spawn point, password)
    JOBS += [(ident, "fresh", "A"), (ident, "rich", "A"), (ident, "full", "A")]
for ident in (0x0C, 0x0D, 0x19, 0x1A, 0x1D, 0x28, 0x2B, 0x39, 0x3B, 0x3C, 0x48, 0x4A, 0x57, 0x66, 0x68, 0x75, 0x77):  # shops: buy the first, sell the first
    JOBS += [(ident, "rich", "A"), (ident, "full", "A"), (ident, "fresh", "A"), (ident, "mid", "A"), (ident, "rich", "BA")]
for ident in (0x01, 0x05, 0x08, 0x13, 0x17, 0x1B, 0x30, 0x40, 0x60, 0x70):                  # others: the King (gold), ranks, the keys' people
    JOBS += [(ident, "fresh", "A"), (ident, "rich", "A"), (ident, "full", "A")]


def state_of(spec):
    import iscript_model as im

    if isinstance(spec, str):
        return im.PRESETS[spec].copy()
    spec = dict(spec)
    s = im.PRESETS[spec.pop("base")].copy()
    for key, value in spec.items():
        setattr(s, key, value)
    return s


def port_bytes(s) -> bytes:
    """A model state as the port holds it: the inventory block (lists, counts, special items, quests, glove and ointment off, what is worn), hud_state, five words."""
    inv = bytearray(INV_BYTES)
    for c, items in enumerate(s.lists):
        for i, item in enumerate(items):
            inv[4 * c + i] = item
        inv[24 + c] = len(items)
    inv[29], inv[30], inv[31], inv[32], inv[33] = s.special, s.quests, 0xFF, 0xFF, 0
    inv[34], inv[35], inv[36] = s.selected[1], s.selected[2], s.selected[4]
    hud = bytes([s.power, s.magic, 0, 0]) + s.gold.to_bytes(4, "big") + bytes([0, 0])
    spell = -1 if s.selected[3] == 0xFF else s.selected[3]                 # (no spell is -1, no weapon 255)
    words = b"".join(w.to_bytes(2, "big", signed=w < 0) for w in (s.title, s.next_title, s.spawn, s.selected[0], spell))
    return bytes(inv) + hud + words


def model_key(raw: bytes) -> dict:
    """The port's state bytes as the model's key (no spell is the word -1, no weapon 255)."""
    inv, hud, words = raw[:INV_BYTES], raw[INV_BYTES:INV_BYTES + 10], raw[INV_BYTES + 10:]
    w = [int.from_bytes(words[i:i + 2], "big") if i < 6 else words[i + 1] for i in range(0, 10, 2)]    # (the low byte of the weapon and the spell: $FF is none)
    lists = [list(inv[4 * c:4 * c + inv[24 + c]]) for c in range(4)] + [list(inv[16:16 + inv[28]])]
    return {"gold": int.from_bytes(hud[4:8], "big"), "power": hud[0], "magic": hud[1], "title": w[0], "next_title": w[1], "spawn": w[2], "special": inv[29], "quests": inv[30],
            "lists": lists, "selected": [w[3], inv[34], inv[35], w[4], inv[36]]}


@unittest.skipUnless(ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file(),
                     "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class IScriptBatchTests(unittest.TestCase):
    run_scenario = tv.ViewerTests.run_scenario

    def batch(self, jobs, name: str, frames: int | None = None):
        """Runs the jobs [(script, state spec, buttons)] in the 68000 interpreter; returns (the program's results, the model's): each (actions, state)."""
        import faxanadu_rom as fr
        import iscript_model as im

        script = im.Script(fr.Rom(ROM))
        blob = len(jobs).to_bytes(2, "big")
        expected = []
        for ident, spec, buttons in jobs:
            state = state_of(spec)
            blob += ident.to_bytes(2, "big") + POLICY[buttons].to_bytes(2, "big") + port_bytes(state)
            actions, messages, after = im.run(script, ident, state, buttons)
            ops = []
            for a in actions:
                op = script.byte(a)
                ops.append((op, script.byte(a + 1) if op in (1, 2, 3) else None))
            expected.append((ops, after.key(), messages))
        generated = ROOT / "build" / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        (generated / "batch.bin").write_bytes(blob)
        frames = frames or FRAMES
        args = [f"VIEWER_DEFS=--defsym SCRIPT=0 --defsym BATCH={len(jobs)}"]
        ram, word, log = self.run_scenario(args, [], frames, name)
        out = word.raw("batch_out", BO_SIZE * len(jobs))
        done = word("batch_done")
        self.frames_used = int.from_bytes(word.raw("batch_frames", 4), "big")
        got = []
        for i in range(done):
            rec = out[i * BO_SIZE:(i + 1) * BO_SIZE]
            n = int.from_bytes(rec[BJ_STATE:BJ_STATE + 2], "big")
            trace = rec[BJ_STATE + 2:BJ_STATE + 2 + 2 * TRACE]
            got.append(([(trace[2 * k], trace[2 * k + 1]) for k in range(min(n, TRACE))], model_key(rec[:BJ_STATE])))
        return got, expected, done

    @staticmethod
    def compare(jobs, got, expected) -> list[str]:
        bad = []
        for (ident, spec, buttons), (ops, state), (want_ops, want_state, _messages) in zip(jobs, got, expected):
            tag = f"script {ident:#x} {spec} {buttons}"
            seen = [(op, arg if op in (1, 2, 3) else None) for op, arg in ops]
            if seen != want_ops:
                bad.append(f"{tag}: actions {[(hex(o), a) for o, a in seen][:14]} want {[(hex(o), a) for o, a in want_ops][:14]}")
            elif state != want_state:
                bad.append(f"{tag}: state {state} want {want_state}")
        return bad

    def test_the_interpreter_does_what_the_model_of_the_roms_does_on_many_scripts(self) -> None:
        got, expected, done = self.batch(JOBS, "shots_iscript_batch")
        self.assertEqual(done, len(JOBS), "not every job has finished")
        bad = self.compare(JOBS, got, expected)
        self.assertEqual(bad, [], f"{len(bad)} of {len(JOBS)} jobs differ")


if __name__ == "__main__":
    unittest.main()
