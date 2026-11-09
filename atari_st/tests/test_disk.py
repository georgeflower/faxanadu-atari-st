"""The game's disk (`make disk`): every package that a door, an edge or a temple can ask for is on it, and it all fits 720 KB.

No Hatari. The assets are built the way the Makefile builds them for the disk (ALL, DISK_WORLD) into a temporary directory (about 7 s); each package file
is unpacked and its doors and edges are read, the temples' table is read from src/flow.s, and every file name the program would make
(`A<area>P<palette>.DAT`, as `load_package` does) must be among the files. The program itself is not built here: its size is a budget.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"

import build_assets as ba  # noqa: E402
import lz  # noqa: E402
import make_disk  # noqa: E402

PRG_BUDGET = 106_000          # FAXANADU.PRG (the program, packed songs and tables): about 100,000 bytes now; the build itself stops when the disk is full
BUILDING_AREA = 4
FIXED = ("TITLE.DAT", "INTRO.DAT", "OUTRO.DAT", "TOWN.DAT")
TEMPLE_PALETTE, KING_PALETTE = 18, 17          # src/flow.s: temple_enter (moveq #18) and the ending's room (A4P17)


def makefile_world() -> list[int]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    return [int(v) for v in re.search(r"^DISK_WORLD\s*:?=\s*(\S+)", text, re.M).group(1).split(",")]


def flow_table(name: str) -> list[int]:
    """The .byte line after `name:` in src/flow.s."""
    text = (ROOT / "src" / "flow.s").read_text(encoding="utf-8")
    line = re.search(rf"^{name}:[^\n]*\n\s*\.byte ([^\n|]+)", text, re.M).group(1)
    return [int(v) for v in line.split(",")]


class Package:
    """A package file read back: its area and palette (from the name), the header numbers, the doors, the edges and the screens' ROM numbers."""

    def __init__(self, name: str, blob: bytes):
        self.name = name
        self.area, self.palette = int(name[1]), int(name[3:5])
        data = lz.unpack(blob)
        n = len(ba.PACKAGE_PARTS)
        offsets = [int.from_bytes(data[4 * i:4 * i + 4], "big") for i in range(n)] + [len(data)]
        self.header = {h: int.from_bytes(data[4 * n + 2 * i:4 * n + 2 * i + 2], "big") for i, h in enumerate(ba.HEADER_WORDS)}
        part = {p: data[offsets[i]:offsets[i + 1]] for i, p in enumerate(ba.PACKAGE_PARTS)}
        d, e = part["doors"], part["edges"]
        self.doors = [tuple(d[i:i + ba.DOOR_BYTES]) for i in range(0, self.header["door_count"] * ba.DOOR_BYTES, ba.DOOR_BYTES)]
        self.edges = [tuple(e[i:i + ba.EDGE_BYTES]) for i in range(0, self.header["edge_count"] * ba.EDGE_BYTES, ba.EDGE_BYTES)]
        self.screen_ids = list(part["screen_ids"])
        self.screens = self.header["screen_count"]


@unittest.skipUnless(ROM.is_file(), "needs the ROM (ext/Faxanadu_Europe.nes)")
class DiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp(prefix="diskcheck")
        cls.world = makefile_world()
        out = Path(cls.tmp)
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_assets.py"), "--rom", str(ROM), "--area", "0", "--screen", "1", "--all",
                        "--world", ",".join(map(str, cls.world)), "--out", str(out)], check=True, capture_output=True)
        cls.files = {p.name: p.read_bytes() for p in out.glob("*.DAT")}
        cls.packages = {n: Package(n, b) for n, b in cls.files.items() if n not in FIXED and n[0] == "A"}

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def name(self, area: int, palette: int) -> str:
        return ba.package_name(area, palette)

    def need(self, area: int, palette: int, why: str) -> Package:
        name = self.name(area, palette)
        self.assertTrue(name in self.packages, f"{name} is asked for by {why} and is not on the disk")
        return self.packages[name]

    # ------------------------------------------------------------------------------------------------ what is asked for
    def test_the_disk_world_is_every_area(self) -> None:
        """Areas 0 (the first) and 4 (the buildings, from the doors) and the WORLD of the Makefile are the eight areas of the ROM."""
        self.assertEqual(sorted(set(self.world) | {0, BUILDING_AREA}), list(range(8)))

    def test_the_fixed_files_and_the_first_package_are_there(self) -> None:
        for name in FIXED:
            self.assertIn(name, self.files)
        inc = (Path(self.tmp) / "assets.inc").read_text(encoding="ascii")
        area, palette = (int(re.search(rf"PACKAGE_{k}, (\d+)", inc).group(1)) for k in ("AREA", "PALETTE"))
        self.need(area, palette, "the start of the program")
        self.need(BUILDING_AREA, KING_PALETTE, "the ending (the King's room)")
        self.need(BUILDING_AREA, TEMPLE_PALETTE, "death and the mantra (the temple)")

    def test_every_door_leads_to_a_package_that_is_there(self) -> None:
        """Kind 0 and 1: this area, the door's palette; kind 2: a building (area 4, its palette); kind 3: another area. The screen it leads to must exist."""
        count = 0
        for pkg in self.packages.values():
            for screen, block, kind, dest_screen, start, palette, key, extra in pkg.doors:
                count += 1
                why = f"a door of {pkg.name} (screen {screen}, block {block}, kind {kind})"
                self.assertLess(screen, pkg.screens, why)
                if kind in (ba.DOOR_SAME, ba.DOOR_PALETTE):
                    target = self.need(pkg.area, palette, why)
                    if kind == ba.DOOR_SAME:
                        self.assertEqual(palette, pkg.palette, why)
                elif kind == ba.DOOR_BUILDING:
                    target = self.need(BUILDING_AREA, palette, why)
                elif kind == ba.DOOR_OUTSIDE:
                    target = self.need(extra, palette, why)
                else:
                    self.fail(f"{why}: unknown kind")
                self.assertLess(dest_screen, target.screens, f"{why} leads to screen {dest_screen} of {target.name}, which has {target.screens}")
        self.assertGreater(count, 40, "the doors of all areas were read")

    def test_every_edge_leads_to_a_package_that_is_there(self) -> None:
        count = 0
        for pkg in self.packages.values():
            for screen, area, dest_screen, start, palette in pkg.edges:
                count += 1
                why = f"an edge of {pkg.name} (screen {screen})"
                self.assertLess(screen, pkg.screens, why)
                target = self.need(area, palette, why)
                self.assertLess(dest_screen, target.screens, f"{why} leads to screen {dest_screen} of {target.name}, which has {target.screens}")
        self.assertGreater(count, 3)

    def test_no_door_and_no_edge_of_the_rom_is_left_out(self) -> None:
        """build_assets leaves out a door whose other side has no package; with the whole world every door and edge of every area must be there."""
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        for name, pkg in self.packages.items():
            if pkg.area == BUILDING_AREA:
                continue
            self.assertEqual(len(pkg.doors), len(fm.doors(rom, fm.area(rom, pkg.area))), f"the doors of {name}")
            self.assertEqual(len(pkg.edges), len(fm.edges(rom, pkg.area)), f"the edges of {name}")

    def test_every_temple_spawn_point_has_its_outside_package(self) -> None:
        """src/flow.s temple_enter: the area and screen of each of the 8 spawn points, the palette set of the area; the screens are the ROM's numbers."""
        areas, screens, palettes = flow_table("tt_area"), flow_table("tt_screen"), flow_table("tt_palette")
        self.assertEqual((len(areas), len(screens)), (8, 8))
        for spawn, (area, screen) in enumerate(zip(areas, screens)):
            pkg = self.need(area, palettes[area], f"the temple of spawn point {spawn}")
            self.assertLess(screen, pkg.screens, f"spawn point {spawn}")
            self.assertEqual(pkg.screen_ids[screen], screen, f"spawn point {spawn}: the package holds the ROM's screen numbers")

    def test_the_door_and_package_names_are_8_3_names_the_program_can_make(self) -> None:
        """load_package writes one digit for the area and two for the palette set."""
        for name, pkg in self.packages.items():
            self.assertRegex(name, r"^A[0-7]P\d\d\.DAT$")
            self.assertEqual(name, self.name(pkg.area, pkg.palette))

    # ------------------------------------------------------------------------------------------------ the people of the buildings
    TYPE_PERSON = {0: 0x3A, 1: 0x39, 2: 0x3E, 3: 0x3D, 4: 0x37, 5: 0x3C, 6: 0x3F, 7: 0x40, 8: 0x38, 9: 0x3B}       # building type: the person who stands there (King, Priest, ManInChair, ...)
    NO_PEOPLE = {29, 31, 53, 54, 55, 56, 57, 67}          # the ids whose list in the ROM has no person: the tavern and the hospital of area 2 screen 6, area 6's shops and its second tool shop

    def building_doors(self):
        """(package, screen's ROM number, block, the door's byte 7, the building's palette set) of every door into a building, and the ROM's own record for it."""
        import faxanadu_maps as fm
        import faxanadu_rom as fr

        rom = fr.Rom(ROM)
        out = []
        for name, pkg in sorted(self.packages.items()):
            if pkg.area == BUILDING_AREA:
                continue
            area = fm.area(rom, pkg.area)
            rom_doors = {(d.screen, d.block): d for d in fm.doors(rom, area)}
            for screen, block, kind, dest, start, palette, key, extra in pkg.doors:
                if kind != ba.DOOR_BUILDING:
                    continue
                door = rom_doors[(pkg.screen_ids[screen], block)]
                out.append((pkg, pkg.screen_ids[screen], block, extra, palette, start, key, fm.door_destination(rom, area, door), rom))
        return out

    def test_a_door_into_a_building_carries_the_roms_id_and_the_types_palette(self) -> None:
        """The ROM's destination record of a door: byte 0 is the id (Area_DestScreen: the screen of area 4 whose people and scripts the game uses), byte 1 the type (the
        layout, palette, start position and music tables). The port keeps the id in the door's byte 7 (building_id) and the type's palette and start position. (The first
        version kept the type there, so every shop had another person in it.)"""
        import faxanadu_maps as fm

        seen = {}
        doors = self.building_doors()
        self.assertGreater(len(doors), 60, "the doors of every town")
        for pkg, screen, block, extra, palette, start, key, record, rom in doors:
            why = f"{pkg.name} screen {screen} block {block:#x}"
            self.assertEqual(extra, record[0], f"{why}: building_id is the record's byte 0")
            self.assertEqual(key, record[2], why)
            info = fm.building(rom, record[1])
            self.assertEqual((palette, start), (info["palette"], info["start"]), f"{why}: palette and start position of type {record[1]}")
            self.assertEqual(seen.setdefault(record[0], record[1]), record[1], f"{why}: id {record[0]} has one type")

    def test_the_person_in_every_building_fits_its_type(self) -> None:
        """npc.bin places the people of area 4 by the id: a meat shop has the meat salesman, a temple the priest, and so on, for every door of every town; the ids the ROM
        leaves empty are the ones listed in NO_PEOPLE."""
        import iscripts as isc

        npc = isc.parse_npc_file(isc.npc_file(self.doors_rom()))
        by_id: dict[int, set[int]] = {}
        for area, screen, entity, script, x, y in npc["places"]:
            if area == BUILDING_AREA:
                by_id.setdefault(screen, set()).add(entity)
        empty = set()
        for pkg, screen, block, extra, palette, start, key, record, rom in self.building_doors():
            kind = record[1]
            if extra not in by_id:
                empty.add(extra)
                continue
            self.assertIn(self.TYPE_PERSON[kind], by_id[extra], f"{pkg.name} screen {screen} block {block:#x}: id {extra}, type {kind}")
        self.assertEqual(empty, self.NO_PEOPLE)

    @unittest.skipUnless(shutil.which("node") and (ROOT / "tools" / "refnes" / "node_modules").exists(), "needs node and the jsnes harness")
    def test_the_game_in_jsnes_puts_him_in_the_screen_of_the_doors_id(self) -> None:
        """tools/refnes/buildingprobe.mjs walks the hero into doors of the ROM and reads Area_CurrentScreen (the screen of area 4 the sprites and scripts are placed by), the
        palette and the people the game puts there. One door of each kind in each town (the ROM's whole list, 68 doors, was run by hand): the id is the door's byte 7,
        the palette the type's, and the people (entity, script) are the places of npc.bin."""
        import iscripts as isc

        doors = self.building_doors()
        by_town = {}
        for door in doors:
            pkg, screen, block, extra, palette, start, key, record, rom = door
            by_town.setdefault((pkg.area, screen // 2 if pkg.area == 3 else screen), []).append(door)
        sample = []
        for group in sorted(by_town):
            types = set()
            for door in by_town[group]:
                if door[7][1] not in types and len(sample) < 14:
                    types.add(door[7][1])
                    sample.append(door)
        # a temple, a hospital, a shop and a house from area 3 (Apolune to Dartmoor) and the first town's temple, the King and the martial artist
        wanted = [d for d in doors if d[0].area == 3 and d[7][0] in (11, 12, 14, 18, 23, 27, 36, 44, 63)] + [d for d in doors if d[0].area == 0 and d[7][0] in (2, 5, 6, 7)]
        ids = {d[7][0]: d for d in sample + wanted}
        chosen = [ids[i] for i in sorted(ids)]
        request = [dict(area=pkg.area, region=0 if pkg.area == 3 else {0: 0, 1: 1, 2: 2, 6: 4}[pkg.area], screen=screen, x=(block & 15) * 16, y=(block >> 4) * 16)
                   for pkg, screen, block, *_ in chosen]
        tmp = Path(self.tmp)
        (tmp / "doors.json").write_text(json.dumps(request), encoding="ascii")
        subprocess.run(["node", "buildingprobe.mjs", str(tmp / "doors.json"), str(tmp / "doors_out.json")], cwd=ROOT / "tools" / "refnes", check=True, capture_output=True)
        got = json.loads((tmp / "doors_out.json").read_text(encoding="ascii"))
        npc = isc.parse_npc_file(isc.npc_file(self.doors_rom()))
        self.assertEqual(len(got), len(chosen))
        for door, seen in zip(chosen, got):
            pkg, screen, block, extra, palette, start, key, record, rom = door
            why = f"{pkg.name} screen {screen} block {block:#x} (id {extra}, type {record[1]})"
            self.assertEqual((seen["area"], seen["screen"]), (BUILDING_AREA, extra), f"{why}: the game's Area_CurrentScreen is the door's byte 7")
            self.assertEqual(seen["palette"], palette, why)
            game = sorted((e, v) for e, v in zip(seen["sprites"], seen["values"]) if 0x34 <= e <= 0x45)
            port = sorted((entity, script) for area, scr, entity, script, x, y in npc["places"] if area == BUILDING_AREA and scr == extra and entity != 0x4F)
            self.assertEqual(game, port, f"{why}: the people the game puts there")
        self.assertGreater(len(chosen), 20)

    def doors_rom(self):
        import faxanadu_rom as fr

        return fr.Rom(ROM)

    def test_the_temples_of_the_spawn_points_are_the_roms_ids(self) -> None:
        """src/flow.s tt_dest is DEST_SCREEN_FOR_TEMPLE_SPAWN, the id temple_enter places the temple's guru by; each is a temple door of the ROM."""
        rom = self.doors_rom()
        dest = flow_table("tt_dest")
        self.assertEqual(dest, [rom.byte("DEST_SCREEN_FOR_TEMPLE_SPAWN", i) for i in range(8)])
        temples = {record[0] for _, _, _, _, _, _, _, record, _ in self.building_doors() if record[1] == 1}
        for spawn, ident in enumerate(dest):
            self.assertIn(ident, temples, f"spawn point {spawn}")

    # ------------------------------------------------------------------------------------------------ the disk
    def test_the_disk_fits_720_kb(self) -> None:
        readme = (ROOT / "disk" / "README.TXT").read_bytes()
        files = [("FAXANADU.PRG", bytes(PRG_BUDGET)), ("README.TXT", readme)] + sorted(self.files.items())
        image = make_disk.build_disk(files)                    # raises DiskFull when it does not fit
        names = make_disk.read_disk(image)
        self.assertEqual(sorted(names), sorted(n for n, _ in files))

    def test_the_readme_is_plain_text_a_small_screen_can_show(self) -> None:
        text = (ROOT / "disk" / "README.TXT").read_text(encoding="ascii")
        self.assertTrue(all(len(line) <= 40 for line in text.splitlines()), "lines of 40 characters at most")
        self.assertIn("FAXANADU.PRG", text)


if __name__ == "__main__":
    unittest.main()
