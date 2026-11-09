"""Which song plays when: the ROM's rules (Areas_DefaultMusic, Area_Music_Outside, the palette-to-song table of Player_CheckHandleEnterDoor) against the port's.

The port keeps one song for each package (`faxanadu_maps.music_for`, `PKG_MUSIC`) and starts it when a package is loaded, unless the package he leaves has the same song.
The ROM keeps the area's song in a variable (D) and starts a song at an in-area door only when the new palette's song is in its table and is not D. The first class shows that
the two rules are the same for every in-area door of the game's data; the second plays doors and the Start press in the ROM (jsnes, tools/refnes/musicprobe.mjs).
The port's side is in Hatari: tests/test_flow.py (the door), tests/test_splash68.py (the Start blip).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"
REFNES = ROOT / "tools" / "refnes"
IN_AREA_DOORS = (0, 1, 2, 5, 6, 7)        # the towns' (area 3) doors all lead into buildings


def rom_door_song(rom, palette: int, current: int) -> int:
    """Player_CheckHandleEnterDoor for a door that stays in the area: the song after it, when D is `current` and the door leads to `palette` (the song changes only for a
    palette that is in Palette_ARRAY_PRG15_MIRROR__e569 and whose song is another one)."""
    for i in range(7):
        if rom.byte("Palette_ARRAY_PRG15_MIRROR__e569", i) == palette:
            song = rom.byte("Music_ARRAY_PRG15_MIRROR__e570", i)
            return song if song != current else current
    return current


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class DoorRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        cls.fm, cls.rom = fm, fr.Rom(ROM)

    def in_area_doors(self):
        """(area, source palette, door, destination palette) for every palette set an area can be in (the area's own, then what its doors lead to)."""
        fm, rom = self.fm, self.rom
        for ai in IN_AREA_DOORS:
            a = fm.area(rom, ai)
            doors = [(d, fm.door_destination(rom, a, d)[1]) for d in fm.doors(rom, a) if d.destination < 0x20]
            seen, todo = set(), [a.palette_index]
            while todo:
                p = todo.pop()
                if p in seen:
                    continue
                seen.add(p)
                for d, dest in doors:
                    yield ai, p, d, dest
                    todo.append(dest)

    def test_the_areas_song_is_the_song_of_its_first_package(self) -> None:
        """A new area starts with AREA_TO_MUSIC_TABLE[area] (Game_EnterAreaHandler); the port starts the song of the package it loads, which is the same one."""
        for ai in IN_AREA_DOORS:
            a = self.fm.area(self.rom, ai)
            self.assertEqual(self.fm.music_for(self.rom, ai, a.palette_index), self.rom.byte("AREA_TO_MUSIC_TABLE", ai), f"area {ai}")

    def test_the_roms_variable_follows_the_package_at_every_door_and_a_song_restarts_in_the_port_exactly_when_it_does_in_the_rom(self) -> None:
        """For every in-area door, from every palette set it can be taken in: D (the area's song) is the package's song before it, so D after it is the next package's song,
        and the song is started anew in the ROM (D changes) exactly when the next package's song is another one (the port's rule)."""
        fm, rom = self.fm, self.rom
        same = changed = 0
        for ai, source, door, dest in self.in_area_doors():
            before, after = fm.music_for(rom, ai, source), fm.music_for(rom, ai, dest)
            d_after = rom_door_song(rom, dest, before)
            where = f"area {ai} screen {door.screen} block {door.block}: palette {source} to {dest}"
            self.assertEqual(d_after, after, where)
            self.assertEqual(d_after != before, after != before, where)
            same, changed = same + (after == before), changed + (after != before)
        self.assertGreater(same, 10)
        self.assertGreater(changed, 3)

    def test_the_doors_the_roms_song_does_not_restart_are_in_dartmoor_and_branch(self) -> None:
        """The doors between two palette sets with one song (Dartmoor 13 and 14, song 6; Branch 8 and 9, song 4) are the ones where the port used to start the song anew."""
        keep = {(ai, source, dest) for ai, source, door, dest in self.in_area_doors()
                if source != dest and self.fm.music_for(self.rom, ai, source) == self.fm.music_for(self.rom, ai, dest)}
        self.assertEqual(keep, {(6, 13, 14), (6, 14, 13), (5, 8, 9), (5, 9, 8)})


@unittest.skipUnless(ROM.is_file() and shutil.which("node") and (REFNES / "node_modules" / "jsnes").is_dir() and (ROOT / "build" / "refnes" / "ram_labels.json").is_file(),
                     "needs the ROM, node, the jsnes harness and the RAM labels")
class RomSongTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        cls.fm, cls.rom = fm, fr.Rom(ROM)

    def probe(self, *args) -> list:
        out = subprocess.run(["node", "musicprobe.mjs", *map(str, args)], cwd=REFNES, check=True, capture_output=True, text=True).stdout
        return json.loads(next(line for line in out.splitlines() if line.startswith("RESULT "))[7:])

    def door_songs(self, area: int, screen: int, block: int, current: int) -> list[int]:
        """The songs the ROM starts in the 60 frames after Up at a door (a song is asked for by writing it without the 'playing' bit 7), D being `current` before."""
        log = self.probe("door", area, 0, screen, block, 0, current)
        return [m for frame, m, d, o in log if 0 < frame < 60 and not m & 0x80]

    def test_a_door_starts_a_song_when_the_rom_model_says_so(self) -> None:
        """Four doors in Dartmoor (two between palettes 13 and 14 of the same song, 6: the ROM goes on with it), one in Trunk (a door to its own palette, 6, whose song is 3), the
        area's song D being the one before or another: what the ROM does equals `rom_door_song`."""
        fm, rom = self.fm, self.rom
        cases = [(6, 12, 72, 2), (6, 12, 72, 6), (6, 20, 158, 2), (6, 20, 158, 6), (1, 13, 144, 6), (1, 13, 144, 3)]
        for area, screen, block, current in cases:
            a = fm.area(rom, area)
            door = next(d for d in fm.doors(rom, a) if (d.screen, d.block) == (screen, block))
            palette = fm.door_destination(rom, a, door)[1]
            want = rom_door_song(rom, palette, current)
            with self.subTest(area=area, screen=screen, block=block, current=current):
                self.assertEqual(self.door_songs(area, screen, block, current), [want] if want != current else [])

    def test_start_on_the_title_sets_song_8_and_the_intro_sets_0_five_frames_later(self) -> None:
        """The Start press: Music_Current is 8 for five frames (the title's note sounds for the first, the song's first frame is silent, its note is heard for four) and then 0.
        The recording of song 8 has the same first frames (the port plays them: tests/test_splash68.py)."""
        log = self.probe("start")
        songs = [m & 0x7F for _, m, _ in log]
        self.assertEqual(songs[:6], [8, 8, 8, 8, 8, 0])
        audible = [i for i, _, c in log if c[0][1]]
        self.assertEqual(audible[:4], [2, 3, 4, 5])
        self.assertEqual(audible[4:], [], "nothing after the fourth frame")
        rec = ROOT / "build" / "refnes" / "sound" / "m8.json"
        if rec.is_file():
            state = json.loads(rec.read_text())["state"]
            self.assertEqual([bool(s[0][1]) for s in state[:6]], [False, True, True, True, True, True], "the recorded song: silent, then its first note")


if __name__ == "__main__":
    unittest.main()
