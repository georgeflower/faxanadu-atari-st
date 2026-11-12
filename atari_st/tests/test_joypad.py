"""The joystick-centred controls (JOYPAD=1, the disk build): what the stick and the keys mean in the game and in the menus.

Two parts. The mapping itself (`input_poll` for menus, boxes and the title; `input_poll_game` for the running game, src/frame.s) runs on machine68k against a small Python
model: fire and Space, Up and the two-frame rule that tells a jump from a spell, a change of mode that makes no button new. Then the game in Hatari (the same tools as
tests/test_flow.py): the stick's Up jumps along the ROM's curve, enters a door, talks to a person and climbs a ladder without jumping, Up and fire cast a spell, Space casts
a spell, fire attacks, Down and fire use the item, the arrow keys are the stick, and in the player menu, the Esc menu and on the title fire and Space choose and Alternate
goes back. Needs the ROM, Hatari, the m68k binutils and a TOS image (TOS), like tests/test_viewer.py.
"""
from __future__ import annotations

import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import test_flow as tf  # noqa: E402  (the Run helper: a build, Hatari, pokes and captures)
import test_frame as tfr  # noqa: E402  (the input parser on machine68k)
import test_viewer as tv  # noqa: E402  (the TOS image)

NEEDS = ROM.is_file() and shutil.which("hatari") and shutil.which("m68k-linux-gnu-as") and shutil.which("ca65") and tv.TOS.is_file()
UP, DOWN, LEFT, RIGHT, FIRE = 1, 2, 4, 8, 0x80                      # the stick byte
N_A, N_B, N_SELECT, N_START, N_UP, N_DOWN, N_LEFT, N_RIGHT = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01     # the NES pad
K_UP, K_DOWN, K_LEFT, K_RIGHT, K_SPACE, K_ALT, K_RETURN, K_TAB, K_ESC = 0x48, 0x50, 0x4B, 0x4D, 0x39, 0x38, 0x1C, 0x0F, 0x01
CURVE = (8, 4, 4, 4, 4, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 4, 4, 4, 4, 8)         # PLAYER_JUMP_CURVE
IN_MODE, IN_UPCNT, IN_LATCH = 392, 394, 395


def key(scan: int, down: bool = True) -> int:
    return scan << 8 | (1 if down else 0)


class Model:
    """The mapping as the specification says it, one `poll` for each call of input_poll (game=False) or input_poll_game (game=True)."""

    def __init__(self) -> None:
        self.pad = self.new = 0
        self.mode = 0
        self.count = 0

    def poll(self, game: bool, joy: int, keys: set[int]) -> tuple[int, int]:
        pad = 0
        for bit, flag in ((UP, N_UP), (DOWN, N_DOWN), (LEFT, N_LEFT), (RIGHT, N_RIGHT)):
            if joy & bit:
                pad |= flag
        for scan, flag in ((K_UP, N_UP), (K_DOWN, N_DOWN), (K_LEFT, N_LEFT), (K_RIGHT, N_RIGHT), (K_RETURN, N_START), (K_TAB, N_SELECT)):
            if scan in keys:
                pad |= flag
        fire, space, alt = bool(joy & FIRE), K_SPACE in keys, K_ALT in keys
        if not game:
            if fire or space:
                pad |= N_A                                          # choose
            if alt:
                pad |= N_B                                          # back
        else:
            if fire or alt:
                pad |= N_B
            self.count = min(self.count + 1, 4) if pad & N_UP else 0
            if space:
                pad |= N_UP | N_B
            elif pad & N_B and not self.pad & N_B and pad & N_UP:
                pad = (pad & ~N_UP) | N_A                           # fire or Alternate with Up held: the sword, never the spell (Up left out in that poll)
            if pad & N_UP:
                pad |= N_A                                          # Up held is A held (the wing boots), never a new A
        new = pad & ~self.pad & 0xFF
        if int(game) != self.mode:
            self.mode = int(game)
            new = 0
            if game and self.count:
                self.count = 4
        elif game:
            new &= ~(N_UP | N_A) & 0xFF
            if self.count == 1:
                new |= N_UP
        self.pad, self.new = pad, new
        return pad, new


@unittest.skipUnless(tfr.toolchain_ok(), "needs the m68k binutils and machine68k")
class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import machine68k as m

        cls.m = m
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "t.s").write_text('    .text\n    .include "frame.s"\n', encoding="utf-8")
        subprocess.run(["m68k-linux-gnu-as", "-m68000", "--defsym", "JOYPAD=1", "-I", str(ROOT / "src"), "-o", str(tmp / "t.o"), str(tmp / "t.s")], check=True, capture_output=True)
        subprocess.run(["m68k-linux-gnu-ld", "-T", str(ROOT / "link.ld"), "-nostdlib", "-e", "0", "-o", str(tmp / "t.elf"), str(tmp / "t.o")], check=True, capture_output=True)
        subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", str(tmp / "t.elf"), str(tmp / "t.bin")], check=True)
        cls.image = (tmp / "t.bin").read_bytes()
        names = subprocess.run(["m68k-linux-gnu-nm", str(tmp / "t.elf")], check=True, capture_output=True, text=True).stdout.split("\n")
        cls.sym = {line.split()[2]: int(line.split()[0], 16) + tfr.LOAD for line in names if len(line.split()) == 3}
        cls.helper = tfr.InputTests("test_joystick_one_makes_the_pad")      # (borrowed: its machine, call and feed)
        cls.helper.m, cls.helper.image, cls.helper.sym = m, cls.image, cls.sym

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.mc = self.helper.machine()
        self.model = Model()
        self.joy = 0
        self.keys: set[int] = set()

    def poll(self, game: bool, joy: int | None = None, down: tuple[int, ...] = (), up: tuple[int, ...] = ()) -> tuple[int, int]:
        """Presses and releases, then one poll in the given mode; the assembler's (pad, new) must be the model's."""
        data: list[int] = []
        if joy is not None:
            self.joy = joy
            data += [0xFF, joy]
        for k in down:
            self.keys.add(k)
            data.append(k)
        for k in up:
            self.keys.discard(k)
            data.append(k | 0x80)
        self.helper.feed(self.mc, data)
        self.helper.call(self.mc, "input_poll_game" if game else "input_poll")
        base = self.sym["input_state"]
        got = (self.mc.mem.r8(base + tfr.IN_PAD), self.mc.mem.r8(base + tfr.IN_PAD_NEW))
        self.assertEqual(got, self.model.poll(game, self.joy, self.keys), f"game={game} joy={self.joy:#x} keys={sorted(self.keys)}")
        return got

    def count(self) -> int:
        return self.mc.mem.r8(self.sym["input_state"] + IN_UPCNT)

    def test_menus_fire_and_space_choose_and_alternate_goes_back(self) -> None:
        self.assertEqual(self.poll(False, FIRE), (N_A, N_A))
        self.assertEqual(self.poll(False, 0), (0, 0))
        self.assertEqual(self.poll(False, down=(K_SPACE,)), (N_A, N_A))
        self.assertEqual(self.poll(False, up=(K_SPACE,)), (0, 0))
        self.assertEqual(self.poll(False, down=(K_ALT,)), (N_B, N_B))
        self.assertEqual(self.poll(False, up=(K_ALT,), joy=DOWN | FIRE), (N_DOWN | N_A, N_DOWN | N_A))
        self.assertEqual(self.poll(False, joy=0, down=(K_UP, K_RETURN, K_TAB)), (N_UP | N_START | N_SELECT,) * 2)

    def test_in_the_game_fire_and_alternate_are_the_sword_and_the_arrow_keys_are_the_stick(self) -> None:
        self.poll(True)
        self.assertEqual(self.poll(True, FIRE), (N_B, N_B))
        self.assertEqual(self.poll(True, 0), (0, 0))
        self.assertEqual(self.poll(True, down=(K_ALT,)), (N_B, N_B))
        self.assertEqual(self.poll(True, up=(K_ALT,), joy=DOWN | FIRE), (N_DOWN | N_B, N_DOWN), "Alternate let go, fire pressed in the same poll: B stays down, not new")
        self.assertEqual(self.poll(True, joy=0, down=(K_DOWN, K_LEFT, K_RIGHT)), (N_DOWN | N_LEFT | N_RIGHT, N_LEFT | N_RIGHT), "(Down was already held)")

    def test_up_held_makes_up_new_once_and_the_press_is_the_jump(self) -> None:
        self.poll(True)
        self.assertEqual(self.poll(True, UP), (N_UP | N_A, N_UP))
        self.assertEqual(self.count(), 1, "the poll in which joy_jump starts the jump: the press")
        self.assertEqual(self.poll(True)[1], 0)
        self.assertEqual(self.count(), 2, "one Up, one jump: the count is 1 in one poll only")
        self.poll(True)
        self.poll(True)
        self.assertEqual(self.count(), 4)
        self.poll(True)
        self.assertEqual(self.count(), 4)
        self.poll(True, 0)
        self.assertEqual(self.count(), 0)

    def test_fire_with_up_held_is_the_sword_and_never_the_spell(self) -> None:
        self.poll(True)
        self.poll(True, UP)
        self.assertEqual(self.poll(True, UP | FIRE), (N_A | N_B, N_B), "B new without Up: the sword (Up's A stays, for the wing boots)")
        self.assertEqual(self.poll(True, UP | FIRE), (N_UP | N_A | N_B, 0), "Up back in the pad, not new: no door, no talk")
        self.assertEqual(self.count(), 3)
        self.poll(True, 0)
        self.assertEqual(self.poll(True, UP | FIRE), (N_A | N_B, N_B | N_UP), "pressed together: the sword, and the press of Up (new: a door, a person) is the jump")
        self.assertEqual(self.count(), 1)
        self.poll(True, 0)
        self.poll(True, UP)
        self.assertEqual(self.poll(True, down=(K_ALT,), joy=UP), (N_A | N_B, N_B), "Alternate the same")

    def test_space_is_up_and_b_held_and_makes_no_new_up(self) -> None:
        self.poll(True)
        self.assertEqual(self.poll(True, down=(K_SPACE,)), (N_UP | N_B | N_A, N_B), "B is new, Up is only held: no door, no talk, a spell")
        self.assertEqual(self.poll(True)[1], 0)
        self.assertEqual(self.count(), 0, "Space is not an Up that counts for a jump")
        self.assertEqual(self.poll(True, UP)[1], N_UP, "the stick's Up while Space is held is a press")
        self.assertEqual(self.poll(True, up=(K_SPACE,), joy=UP)[0], N_UP | N_A)

    def test_a_change_of_mode_makes_no_button_new(self) -> None:
        self.poll(True)
        self.poll(True, FIRE)                                       # fire held in the game, then a box opens and closes with it still down
        self.assertEqual(self.poll(False), (N_A, 0), "the box: it is A now, and held")
        self.assertEqual(self.poll(False, 0), (0, 0))
        self.poll(False, FIRE)
        self.assertEqual(self.poll(True), (N_B, 0), "back in the game with fire still down: no attack")
        self.poll(True, 0)
        self.assertEqual(self.poll(True, FIRE), (N_B, N_B), "let go and pressed again: an attack")
        self.poll(True, UP | FIRE)
        self.poll(True, UP)
        self.poll(False, UP)                                        # a door's fade or a box with Up held
        self.assertEqual(self.poll(True, UP), (N_UP | N_A, 0))
        self.assertEqual(self.count(), 4, "Up held across a menu is not a new Up: no jump afterwards")
        self.poll(True, 0)
        self.poll(False, 0)
        self.assertEqual(self.poll(False, FIRE), (N_A, N_A), "menu to menu: nothing is swallowed")

    def test_the_model_and_the_code_agree_on_random_play(self) -> None:
        rng = random.Random(1)
        self.poll(True)
        for _ in range(400):
            joy = rng.choice((0, 0, UP, UP, UP | FIRE, FIRE, DOWN, DOWN | FIRE, RIGHT | UP, LEFT, UP | FIRE | LEFT))
            toggles = [k for k in (K_UP, K_DOWN, K_LEFT, K_RIGHT, K_SPACE, K_ALT, K_RETURN, K_TAB) if rng.random() < 0.15]
            down = tuple(k for k in toggles if k not in self.keys)
            up = tuple(k for k in toggles if k in self.keys)
            self.poll(rng.random() < 0.75, joy if rng.random() < 0.5 else None, down, up)


def y_after(y0: int, n: int) -> int:
    """The hero's y n frames into a jump from the ground at y0 (the ROM's curve)."""
    return y0 - sum(CURVE[:min(n, 16)]) + sum(CURVE[16:n]) if n > 16 else y0 - sum(CURVE[:n])


@unittest.skipUnless(NEEDS, "needs the ROM, cc65, hatari, the m68k binutils and a TOS image (TOS or TOS_PAL)")
class GameTests(unittest.TestCase):
    DEFS = "--defsym JOYPAD=1 --defsym NO_ENEMIES=1"
    UP_AT = 603                                                     # the stick is poked at this VBL; the game polls it in the next frame: the press is the jump

    @staticmethod
    def args(screen: int = 1, hero: str = "144,144,0,255,0,0,1", hud: str = "16,0,0,0,0", defs: str = "", area: int = 0, world: bool = False) -> list[str]:
        return ["ALL=1", f"AREA={area}", f"SCREEN={screen}", f"HERO={hero}", f"HUD={hud}"] + (["WORLD=1"] if world else []) + [f"VIEWER_DEFS={GameTests.DEFS} {defs}".strip()]

    def ys(self, run: "tf.Run") -> list[int]:
        return [s.at("hero_y") for s in run.shots]

    def jumped(self, shot: "tf.Shot") -> bool:
        return shot.at("hero_x", 18) & 1 != 0 or shot.at("hero_y") != 144

    # ------------------------------------------------------------------------------------------------------ Up jumps
    def jump_run(self, pokes, name: str) -> "tf.Run":
        caps = list(range(604, 616)) + [660, 700]
        return tf.Run(self.args(), pokes, caps, name)

    def check_jump(self, run: "tf.Run") -> None:
        ys = self.ys(run)
        near, later = ys[:12], ys[12:]
        first = next(i for i, y in enumerate(near) if y != 144)
        self.assertEqual(604 + first, self.UP_AT + 1, f"the jump starts in the poll of Up's press: {near}")
        self.assertEqual(near[first:], [y_after(144, n + 1) for n in range(len(near) - first)], "up 8, 4, 4, 4, 4, 2, ...: the ROM's curve")
        self.assertEqual(later, [144, 144], "he landed and the Up still held does not jump again")
        self.assertEqual([s.at("hero_x", 18) & 1 for s in run.shots[12:]], [0, 0])

    def test_stick_up_jumps_along_the_roms_curve_once_for_each_press(self) -> None:
        self.check_jump(self.jump_run([(self.UP_AT, "joy", UP)], "shots_jp_jump"))

    def test_the_up_arrow_key_is_the_stick(self) -> None:
        self.check_jump(self.jump_run([(self.UP_AT, "key", key(K_UP))], "shots_jp_jump_key"))

    def test_up_pressed_again_after_landing_jumps_again(self) -> None:
        run = tf.Run(self.args(), [(self.UP_AT, "joy", UP), (640, "joy", 0), (650, "joy", UP)], [645, 655, 656, 657, 658, 659, 660, 700], "shots_jp_jump_twice")
        ys = self.ys(run)
        self.assertEqual(ys[0], 144)
        self.assertTrue(any(y < 144 for y in ys[1:6]), f"the second press jumps: {ys}")
        self.assertEqual(ys[-1], 144)

    # ------------------------------------------------------------------------------------------------------ Up and fire: a spell
    def spell_args(self, **kw) -> list[str]:
        return self.args(hud="80,80,0,0,0", defs="--defsym MAGIC=3", **kw)                  # Death, 10 magic points

    def check_spell(self, run: "tf.Run", spell_shot: int, whole: bool = True) -> None:
        self.assertEqual(run.shots[spell_shot].at("spell_state"), 3, "Death is in flight (-1: no spell)")
        self.assertEqual(run.shots[-1].raw("hud_state", 2), bytes([80, 70]), "10 magic points: one cast")
        if whole:
            for s in run.shots:
                self.assertEqual((s.at("hero_y"), s.at("hero_x", 18) & 1), (144, 0), "no jump")

    def no_spell(self, run: "tf.Run") -> None:
        for shot in run.shots:
            self.assertEqual(shot.at("spell_state"), -1, "no spell")
        self.assertEqual(run.shots[-1].raw("hud_state", 2), bytes([80, 80]), "no magic points used")

    def test_up_and_fire_together_jump_and_swing_the_sword_and_cast_nothing(self) -> None:
        run = tf.Run(self.spell_args(), [(self.UP_AT, "joy", UP | FIRE), (606, "joy", UP), (640, "joy", 0)], [605, 607, 610, 625, 660, 700], "shots_jp_upfire")
        self.assertNotEqual(run.shots[0].at("hero_y"), 144, "he jumped")
        self.assertNotEqual(run.shots[0].at("hero_x", 18) & 0x80, 0, "the sword is swung")
        self.no_spell(run)
        self.assertEqual(run.shots[-1].at("hero_y"), 144)

    def test_fire_with_up_held_on_the_ground_or_in_the_air_is_the_sword(self) -> None:
        for fire_at, name in ((self.UP_AT + 2, "air"), (650, "ground")):
            with self.subTest(name):
                run = tf.Run(self.spell_args(), [(self.UP_AT, "joy", UP), (fire_at, "joy", UP | FIRE), (fire_at + 4, "joy", UP), (690, "joy", 0)],
                             [fire_at + 2, fire_at + 4, 700], f"shots_jp_upheld_fire_{name}")
                self.assertNotEqual(run.shots[0].at("hero_x", 18) & 0x80, 0, "the sword is swung")
                self.no_spell(run)

    def test_space_casts_the_spell_and_is_no_jump_no_door(self) -> None:
        """Eolis screen 0, at the castle door: Up would enter it, Space does not (it is Up held and B new)."""
        run = tf.Run(self.spell_args(screen=0, hero="192,144,0,255,0,0,1"), [(self.UP_AT, "key", key(K_SPACE))], [606, 608, 612, 620, 660, 700], "shots_jp_space")
        self.check_spell(run, 0)
        self.assertEqual({s.at("cur_screen") for s in run.shots}, {0}, "the door stayed shut")
        run = tf.Run(self.spell_args(screen=0, hero="192,144,0,255,0,0,1"), [(self.UP_AT, "key", key(K_SPACE)), (620, "key", key(K_SPACE, False)), (630, "key", key(K_SPACE)), (640, "key", key(K_SPACE, False))],
                     [625, 645, 700], "shots_jp_space_twice")
        self.assertEqual(run.shots[0].raw("hud_state", 2), bytes([80, 70]))
        self.assertEqual(run.shots[1].raw("hud_state", 2), bytes([80, 60]), "pressed again after the first spell is over: a second one")

    # ------------------------------------------------------------------------------------------------------ fire: the sword, the item
    def test_fire_alone_attacks_and_does_not_jump_or_cast(self) -> None:
        run = tf.Run(self.spell_args(), [(self.UP_AT, "joy", FIRE), (640, "joy", 0)], [605, 607, 612, 625, 660, 700], "shots_jp_attack")
        self.assertNotEqual(run.shots[0].at("hero_x", 18) & 0x80, 0, "the attack is on")
        for s in run.shots:
            self.assertEqual((s.at("hero_y"), s.at("hero_x", 18) & 1, s.at("spell_state")), (144, 0, -1))
        self.assertEqual(run.shots[-1].raw("hud_state", 2), bytes([80, 80]))

    def test_alternate_attacks_too(self) -> None:
        run = tf.Run(self.spell_args(), [(self.UP_AT, "key", key(K_ALT)), (610, "key", key(K_ALT, False))], [605, 700], "shots_jp_alternate")
        self.assertNotEqual(run.shots[0].at("hero_x", 18) & 0x80, 0)
        self.assertEqual(run.shots[1].at("hero_y"), 144)

    def test_down_and_fire_use_the_item_fire_alone_does_not(self) -> None:
        """The Wing Boots in hand (item 15): fire alone is a sword stroke, Down and fire use them: the message opens, fire (A in the box) takes it away (it is still down when the game
        goes on: no new stroke, nothing is used again) and the boots run (hero_wings counts their seconds, -1 is none; 40 for the first rank)."""
        run = tf.Run(self.args(), [(380, "b:inv+36", 15), (600, "joy", FIRE), (606, "joy", 0), (640, "joy", DOWN | FIRE), (646, "joy", DOWN), (656, "joy", DOWN | FIRE), (659, "joy", DOWN), (660, "joy", 0)],
                     [620, 700], "shots_jp_item")
        self.assertEqual((run.shots[0].at("hero_wings"), run.shots[0].raw("inv", 37)[36]), (-1, 15), "fire alone: the sword, the item is still in hand")
        self.assertIn(run.shots[1].at("hero_wings"), (40, 39))
        self.assertEqual((run.shots[1].raw("inv", 37)[36], run.shots[1].at("hero_y")), (255, 144), "used up")

    def test_down_arrow_and_alternate_use_the_item(self) -> None:
        run = tf.Run(self.args(), [(380, "b:inv+36", 15), (600, "key", key(K_ALT)), (606, "key", key(K_ALT, False)), (640, "key", key(K_DOWN)), (641, "key", key(K_ALT)),
                                   (646, "key", key(K_ALT, False)), (656, "key", key(K_ALT)), (659, "key", key(K_ALT, False)), (660, "key", key(K_DOWN, False))], [620, 700], "shots_jp_item_keys")
        self.assertEqual(run.shots[0].at("hero_wings"), -1)
        self.assertIn(run.shots[1].at("hero_wings"), (40, 39))

    def test_the_arrow_keys_walk_like_the_stick(self) -> None:
        keyed = tf.Run(self.args(), [(self.UP_AT, "key", key(K_RIGHT)), (630, "key", key(K_RIGHT, False))], [640, 700], "shots_jp_walk_key")
        stick = tf.Run(self.args(), [(self.UP_AT, "joy", RIGHT), (630, "joy", 0)], [640, 700], "shots_jp_walk_stick")
        self.assertEqual([s.at("hero_x") for s in keyed.shots], [s.at("hero_x") for s in stick.shots])
        self.assertGreater(keyed.shots[0].at("hero_x"), 150)

    # ------------------------------------------------------------------------------------------------------ Up: doors, people, ladders
    def test_up_at_the_door_enters_it_and_up_held_while_walking_onto_a_door_does_not_enter(self) -> None:
        run = tf.Run(self.args(screen=0, hero="192,144,0,255,0,0,1"), [(self.UP_AT, "joy", UP), (606, "joy", 0)], [700], "shots_jp_door")
        (s,) = run.shots
        self.assertEqual((s.at("cur_screen"), s.at("hero_x"), s.at("hero_y")), (1, 144, 144), "the castle door leads to screen 1")
        # Up and Right held from x 184, next to the castle door (its block is the one at x + 7 = 192, so x 185 to 200): Up was pressed beside the door, so it is a jump (the press is the
        # jump), and the door is not entered when he comes over it with Up still held (not a new Up). The control, away from it: the same sticks jump.
        walk = tf.Run(self.args(screen=0, hero="184,144,0,255,0,0,1"), [(self.UP_AT, "joy", UP | RIGHT), (680, "joy", 0)], list(range(604, 614)) + [650], "shots_jp_door_walk")
        self.assertEqual([s.at("cur_screen") for s in walk.shots], [0] * 11, "not entered")
        self.assertTrue(any(s.at("hero_y") != 144 for s in walk.shots[:10]), "pressed beside the door: a jump")
        away = tf.Run(self.args(screen=0, hero="100,144,0,255,0,0,1"), [(self.UP_AT, "joy", UP | RIGHT), (680, "joy", 0)], list(range(604, 614)) + [650], "shots_jp_door_away")
        self.assertTrue(any(s.at("hero_y") != 144 for s in away.shots[:10]), "the control: Up and Right jump when nothing is under him")

    PERSON = "--defsym NPCS=1 --defsym NPC_EXTRA=0x37 --defsym NPC_EXTRA_X=100 --defsym NPC_EXTRA_Y=144 --defsym NPC_EXTRA_SCRIPT=2"

    def test_up_at_a_person_talks_and_up_held_while_walking_up_to_him_does_not_talk(self) -> None:
        """Eolis screen 4 with the test build's man (entity $37, stands, script 2: one message) at x 100, y 144: his box takes a hero from x 89 to 139. Up pressed there starts the script
        (the text box is open: the program is polling as a menu) and he stays on the ground. Up and Right held from x 88: pressed away from him,
        it is a jump and no talk. The control without him jumps."""
        stand = tf.Run(self.args(screen=4, hero="100,144,0,255,0,0,1", defs=self.PERSON), [(self.UP_AT, "joy", UP)], [650, 700], "shots_jp_person")
        for s in stand.shots:
            self.assertEqual((s.at("hero_y"), s.at("hero_x", 18) & 1, s.raw("input_state", 396)[IN_MODE]), (144, 0, 0), "talking: the text box is open, no jump")
        walk = tf.Run(self.args(screen=4, hero="88,144,0,255,0,0,1", defs=self.PERSON), [(self.UP_AT, "joy", UP | RIGHT), (680, "joy", 0)], list(range(604, 614)) + [650], "shots_jp_person_walk")
        self.assertTrue(any(s.at("hero_y") != 144 for s in walk.shots[:10]), "pressed away from him: a jump")
        self.assertEqual({s.raw("input_state", 396)[IN_MODE] for s in walk.shots}, {1}, "and no talk (Up was pressed away from him)")
        control = tf.Run(self.args(screen=4, hero="88,144,0,255,0,0,1", defs="--defsym NPCS=1"), [(self.UP_AT, "joy", UP | RIGHT), (680, "joy", 0)], list(range(604, 614)) + [650], "shots_jp_person_control")
        self.assertTrue(any(s.at("hero_y") != 144 for s in control.shots[:10]), "the control: without him the same sticks jump")

    def test_up_on_a_ladder_climbs_a_little_at_a_time_and_does_not_jump(self) -> None:
        """Mist screen 0: the ladder in column 2; he hangs on it at y 170. Up held: 5/8 of a pixel a frame (a jump would start with 8)."""
        run = tf.Run(["AREA=2", "SCREEN=0", "CAMERA=40", "HERO=32,170,0,255,0,0,1", f"VIEWER_DEFS={self.DEFS}"], [(self.UP_AT, "joy", UP), (640, "joy", 0)],
                     [600] + list(range(604, 616)) + [630], "shots_jp_ladder")
        ys = self.ys(run)
        self.assertEqual(ys[0], 170, "he hangs on the ladder")
        steps = [a - b for a, b in zip(ys, ys[1:])]
        self.assertTrue(all(0 <= d <= 1 for d in steps[:-1]), f"one pixel at most a frame (a jump is 8, 4, 4 ...): {ys}")
        self.assertTrue(150 < ys[-1] < 158, f"about 5/8 of a pixel for each of the {630 - 603} frames: {ys}")
        self.assertEqual([s.at("hero_x", 18) & 1 for s in run.shots], [0] * len(run.shots), "never jumping")

    # ------------------------------------------------------------------------------------------------------ menus: the player menu, the Esc menu, the title
    def player_menu(self, choose: list, captures: list, name: str):
        """Tab opens the player menu (the cursor on the first list); then `choose` (pokes)."""
        pokes = [(600, "key", key(K_TAB)), (604, "key", key(K_TAB, False))] + choose
        return tf.Run(self.args(hero="144,144,0,255,0,0,1", hud="80,80,0,0,0"), pokes, captures, name)

    @staticmethod
    def mode(shot) -> int:
        return shot.raw("input_state", 396)[IN_MODE]

    def test_in_the_player_menu_fire_chooses_and_alternate_goes_back(self) -> None:
        """The first list is the weapons, and he has none: fire opens its box (NO WEAPON), Alternate leaves it and the menu with it (`player_menu`); Alternate in the top menu
        closes it. The menu is open when the mode says menu (0); the picture changes when fire is pressed, so fire is not "back" (it used to be)."""
        run = self.player_menu([(650, "joy", FIRE), (654, "joy", 0), (690, "key", key(K_ALT)), (694, "key", key(K_ALT, False))], [640, 680, 720], "shots_jp_menu_fire")
        top, chosen, closed = run.shots
        self.assertEqual((self.mode(top), self.mode(chosen), self.mode(closed)), (0, 0, 1), "open; fire chose (a box, the menu goes on); Alternate left the box and the menu")
        self.assertNotEqual(top.rows, chosen.rows, "fire opened a box")
        run = self.player_menu([(650, "key", key(K_ALT)), (654, "key", key(K_ALT, False))], [640, 680], "shots_jp_menu_alt")
        self.assertEqual((self.mode(run.shots[0]), self.mode(run.shots[1])), (0, 1), "Alternate in the top menu closes it")

    def test_in_the_player_menu_space_chooses_too(self) -> None:
        run = self.player_menu([(650, "key", key(K_SPACE)), (654, "key", key(K_SPACE, False)), (690, "key", key(K_ALT)), (694, "key", key(K_ALT, False))], [640, 680, 720], "shots_jp_menu_space")
        top, chosen, closed = run.shots
        self.assertEqual((self.mode(top), self.mode(chosen), self.mode(closed)), (0, 0, 1))
        self.assertNotEqual(top.rows, chosen.rows)

    def test_the_menu_arrow_keys_and_the_stick_move_the_cursor(self) -> None:
        run = self.player_menu([(650, "joy", DOWN), (654, "joy", 0), (680, "key", key(K_DOWN)), (684, "key", key(K_DOWN, False))], [640, 670, 700], "shots_jp_menu_cursor")
        top, stick, key_ = run.shots
        self.assertNotEqual(top.rows, stick.rows, "the stick's Down moved the cursor")
        self.assertNotEqual(stick.rows, key_.rows, "and so did the Down arrow")

    def test_fire_held_when_a_menu_opens_and_closes_is_no_choice_and_no_attack(self) -> None:
        """Fire down (the stroke is over by VBL 625), Tab opens the menu (nothing is chosen by the fire that is still down), Alternate closes it, back in the game fire is still down:
        no stroke. Fire let go and pressed again strikes."""
        pokes = [(595, "joy", FIRE), (620, "key", key(K_TAB)), (624, "key", key(K_TAB, False)), (650, "key", key(K_ALT)), (654, "key", key(K_ALT, False)), (700, "joy", 0), (720, "joy", FIRE)]
        run = tf.Run(self.args(hero="144,144,0,255,0,0,1", hud="80,80,0,0,0"), pokes, [600, 640, 668, 690, 710, 724], "shots_jp_menu_fire_held")
        stroke, menu, back, still, off, again = run.shots
        self.assertNotEqual(stroke.at("hero_x", 18) & 0x80, 0, "the first stroke")
        self.assertEqual(self.mode(menu), 0, "the menu is open: the fire that was down chose nothing")
        self.assertEqual((self.mode(back), back.at("hero_x", 18) & 0x80, still.at("hero_x", 18) & 0x80), (1, 0, 0), "closed, fire still down: no stroke")
        self.assertEqual(off.at("hero_x", 18) & 0x80, 0)
        self.assertNotEqual(again.at("hero_x", 18) & 0x80, 0, "pressed again: a stroke")

    def test_in_the_esc_menu_alternate_goes_back_and_fire_chooses(self) -> None:
        """Esc opens the three-line box (src/save.s), the cursor on Continue; Alternate is B and closes it; the arrow keys move the cursor (down, up) and fire chooses Continue (A)."""
        import test_esc as te

        def run(pokes, name: str):
            return tf.Run(["ALL=1", "AREA=0", "SCREEN=1", "HERO=40,144,0,255,0,0,1", f"VIEWER_DEFS=--defsym FLOW=1 {self.DEFS}"], pokes, [640, 700], name)

        back = run(te.esc(600) + te.key(650, K_ALT), "shots_jp_esc_alt")
        self.assertEqual((back.shots[0].raw("input_state", 396)[IN_MODE], back.shots[1].raw("input_state", 396)[IN_MODE]), (0, 1), "open, then closed by Alternate")
        chose = run(te.esc(600) + te.key(615, K_DOWN) + te.key(630, K_UP) + [(650, "joy", FIRE), (654, "joy", 0)], "shots_jp_esc_fire")
        self.assertEqual((chose.shots[0].raw("input_state", 396)[IN_MODE], chose.shots[1].raw("input_state", 396)[IN_MODE]), (0, 1), "open, the arrow keys down and up, then Continue chosen with fire")

    def test_on_the_title_fire_chooses_new_game(self) -> None:
        run = tf.Run(["ALL=1", "AREA=0", "SCREEN=1", f"VIEWER_DEFS=--defsym NEWGAME=1 --defsym MENU=1 --defsym NPCS=1 --defsym TITLE=3 --defsym HERO_X=1 --defsym JOYPAD=1"],
                     [(480, "joy", FIRE), (484, "joy", 0)], [2300], "shots_jp_title")
        (shot,) = run.shots
        self.assertEqual((shot.at("cur_area"), shot.at("cur_screen"), shot.at("hero_x"), shot.at("hero_y")), (0, 0, 16, 144), "fire chose the new game: Eolis screen 0")
        self.assertEqual(shot.raw("input_state", 396)[IN_MODE], 1, "and the main loop is polling as the game")


if __name__ == "__main__":
    unittest.main()
