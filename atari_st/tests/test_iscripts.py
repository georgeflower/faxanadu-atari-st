"""The interaction scripts, messages, portraits and town people (tools/iscripts.py): sizes, hashes, the scripts walked to their ends, the files round-tripped and the pictures
compared with an independent drawing from the ROM's own tables. Needs the ROM, no emulator."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ROM = ROOT.parent / "ext" / "Faxanadu_Europe.nes"


def rgb_of(word: int) -> tuple[int, int, int]:
    return (word >> 8) & 7, (word >> 4) & 7, word & 7


@unittest.skipUnless(ROM.is_file(), "needs the ROM")
class IScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import faxanadu_rom as fr
        import iscripts

        cls.rom = fr.Rom(ROM)
        cls.isc = iscripts
        cls.files = iscripts.build(cls.rom)
        cls.data = iscripts.parse_iscript_file(cls.files["iscript.bin"])

    # ------------------------------------------------------------------------------------------------------------------------ scripts
    def test_the_blob_and_the_messages_have_the_sizes_and_hashes_of_the_spec(self) -> None:
        isc = self.isc
        self.assertEqual(len(self.data["blob"]), 1581)
        self.assertEqual(isc.sha1(self.data["blob"]), "38aeaf4e6dea2f10b73310befbc0ca20ccb65064")
        self.assertEqual(len(self.data["messages"]), 12474)
        self.assertEqual(isc.sha1(self.data["messages"]), "cff9ea4974bf6f1bc32bcf729679e29ed2b42c2c")
        self.assertEqual(len(self.data["offsets"]), 152)
        self.assertEqual(len(self.data["message_offsets"]), 193)

    def test_the_tables_are_where_the_disassembly_has_them(self) -> None:
        label = self.rom.label
        self.assertEqual(label("ISCRIPT_ADDRS_L").addr + 0x4B, self.isc.TABLE_L)       # the US labels, the Europe tables are $4B further
        self.assertEqual(label("ISCRIPT_ADDRS_U").addr + 0x4B, self.isc.TABLE_U)
        self.assertEqual(label("SPRITE_TILES_PORTRAITS_ADDRS_INDEX").addr, self.isc.PORTRAIT_TILE_INDEX)
        self.assertEqual(label("SPRITE_TILES_PORTRAITS_START").addr, self.isc.PORTRAIT_TILES)
        self.assertEqual(label("TILEINFO_PORTRAITS_ADDRS").addr, self.isc.PORTRAIT_FRAME_TABLE)
        self.assertEqual(label("PALETTE_SPRITES_PORTRAIT").addr, 0x8000 + self.isc.PORTRAIT_PALETTE_ENTRY)
        self.assertEqual(label("PALETTE_SPRITES_INSIDE").addr, 0x8000 + self.isc.INSIDE_PALETTE_ENTRY)

    def test_every_pointer_is_inside_the_blob_and_the_ids_are_where_the_spec_says(self) -> None:
        pointers = self.isc.script_pointers(self.rom)
        self.assertTrue(all(0xA0E6 <= p <= 0xA712 for p in pointers))
        offsets = self.data["offsets"]
        self.assertEqual(offsets, [p - 0xA0E6 for p in pointers])
        self.assertEqual(offsets[0x1F], 0, "the first script, 'remember your mantra'")
        self.assertEqual(pointers[0x97], 0xA70F, "the last one")
        for unused in (0x1E, 0x2D, 0x3E, 0x4D, 0x59, 0x6A):
            self.assertEqual(pointers[unused], 0xA0EA, "unused ids point at the intro script")
        self.assertEqual(self.data["blob"][0:4], bytes([0x00, 0x01, 0x24, 0x00]))
        self.assertEqual(self.data["blob"][offsets[0]:offsets[0] + 4], bytes([0x00, 0x01, 0x26, 0x00]))

    def test_the_scripts_of_the_first_town_are_the_bytes_of_the_spec(self) -> None:
        blob, offsets = self.data["blob"], self.data["offsets"]

        def script(ident: int, length: int) -> bytes:
            return blob[offsets[ident]:offsets[ident] + length]

        self.assertEqual(script(0x08, 13), bytes.fromhex("800da5a30135 09dc05 00 0336 00".replace(" ", "")))
        self.assertEqual(script(0x0B, 13), bytes.fromhex("8802070532 00 131e 0a1e 0302 00".replace(" ", "")))
        self.assertEqual(script(0x0D, 18), bytes.fromhex("89030f0fd1a3 11 79a4 0302 00 08 79a4 0302 00".replace(" ", "")))
        self.assertEqual(script(0x0F, 9), bytes.fromhex("820219 05c800 1328 00".replace(" ", "")))
        self.assertEqual(script(0x15, 15), bytes.fromhex("84031a021c05fa00 13500a50 031b 00".replace(" ", "")))
        self.assertEqual(self.isc.shop_list(blob, 0xA479), [(0x00, 400), (0x90, 160), (0x92, 320), (0x60, 400)])
        self.assertEqual(self.isc.shop_list(blob, 0xA5C5), [(0x87, 100)])

    def test_every_script_walks_to_an_end_and_uses_only_what_exists(self) -> None:
        isc, blob = self.isc, self.data["blob"]
        lists, used = set(), set()
        for ident, offset in enumerate(self.data["offsets"]):
            seen = isc.walk(blob, offset)
            self.assertTrue(any(op in isc.ENDS for op, _ in seen.values()), f"script {ident:#x} has no end")
            self.assertIn(blob[offset], [0] + list(range(0x80, 0x8B)), "the entity byte")
            for op, values in seen.values():
                used.add(op)
                if op in (1, 2, 3):
                    self.assertTrue(1 <= values[0] <= 193, f"message {values[0]}")
                if op == 0x16:
                    self.assertTrue(1 <= values[0] <= 193)
                if op in isc.LIST_OPS:
                    lists.add(values[0])
                if op == 7:
                    self.assertTrue(values[0] in (0x80, 0x81, 0x82, 0x83) or (values[0] >> 5) <= 4)
        self.assertEqual(len(lists), 17, "the shop lists")
        for address in lists:
            for item, price in isc.shop_list(blob, address):
                self.assertTrue(item >> 5 <= 4 and price % 10 == 0 and 0 < price < 20000)
        self.assertLessEqual(used, set(isc.OPERANDS))
        self.assertTrue({0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 17, 18, 19, 20} <= used or {0, 1, 2, 3, 4, 5, 7, 8, 9, 0x0A, 0x11, 0x12, 0x13, 0x14} <= used)

    def test_the_highest_message_a_script_uses_is_c1(self) -> None:
        top = 0
        for offset in self.data["offsets"]:
            for op, values in self.isc.walk(self.data["blob"], offset).values():
                if op in (1, 2, 3, 0x16):
                    top = max(top, values[0])
        self.assertEqual(top, 0xC1)

    # ------------------------------------------------------------------------------------------------------------------------ messages
    def test_193_messages_each_ended_by_ff_and_the_same_text_as_the_text_tool(self) -> None:
        import faxanadu_text as ft

        block, offsets = self.data["messages"], self.data["message_offsets"]
        self.assertEqual(offsets[0], 0)
        self.assertEqual(block.count(0xFF), 193)
        self.assertEqual(block[-1], 0xFF)
        for n in range(193):
            end = block.index(0xFF, offsets[n])
            if n < 192:
                self.assertEqual(end + 1, offsets[n + 1])
            text = "".join({0xFE: "\n", 0xFD: " ", 0xFC: "\n", 0xFB: "{rank}"}.get(b) or chr(b) for b in block[offsets[n]:end])
            self.assertEqual(text, ft.message(self.rom, n + 1), f"message {n + 1}")

    # -------------------------------------------------------------------------------------------------------------------------- items
    def test_item_pictures_are_the_rom_tiles_of_every_item(self) -> None:
        tiles, pictures = self.data["item_tiles"], self.data["item_pictures"]
        self.assertEqual(len(pictures), 39)
        self.assertTrue(all(0 <= n < len(tiles) for row in pictures for n in row))
        red_potion = pictures[17 + 16]                       # item id $90: tiles $2C-$2F of the pack's pictures
        self.assertEqual([tiles[n] for n in red_potion], [bytes(self.rom.cpu(10, 0x8500 + 16 * t, 16)) for t in (0x2C, 0x2D, 0x2E, 0x2F)])
        hand_dagger = pictures[0]
        self.assertEqual([tiles[n] for n in hand_dagger], [bytes(self.rom.cpu(10, 0x8500 + 16 * t, 16)) for t in (0x4A, 0x4B, 0x8F, 0x4C)])

    def test_item_colours_are_the_huds_palette_in_each_building_set(self) -> None:
        import st_convert as sc

        for k, s in enumerate(self.isc.BUILDING_SETS):
            plan = sc.plan_for_set(self.rom, s)
            bg, _ = sc.palette_set(self.rom, s)
            row = bg[sc.ui_palette_row(self.rom, s)]
            self.assertEqual(self.data["item_colours"][k], [plan.slot[c & 0x3F] for c in row])
            self.assertEqual(self.data["item_colours"][k][0], 0)

    # ----------------------------------------------------------------------------------------------------------------------- palettes
    def test_building_palettes_keep_every_colour_the_package_uses_and_approximate_nothing(self) -> None:
        import st_convert as sc

        for entry in (self.isc.PORTRAIT_PALETTE_ENTRY, self.isc.INSIDE_PALETTE_ENTRY):
            for s, (colours, slots, approximated) in zip(self.isc.BUILDING_SETS, self.isc.building_palettes(self.rom, entry)):
                plan = sc.plan_for_set(self.rom, s)
                bg, outside = sc.palette_set(self.rom, s)
                self.assertEqual(approximated, [])
                self.assertEqual(len(colours), 16)
                for nes in [c for row in bg for c in row] + [c for row in outside[:2] for c in row]:
                    self.assertEqual(colours[plan.slot[nes & 0x3F]], plan.colours[plan.slot[nes & 0x3F]], f"set {s:#x} colour {nes:#x}")
                sprite = self.isc.sprite_palettes_at(self.rom, entry)
                for p in range(4):
                    for c in (1, 2, 3):
                        self.assertEqual(colours[slots[4 * p + c]], sc.st_rgb(sprite[p][c]))
                    self.assertEqual(slots[4 * p], 0)

    # --------------------------------------------------------------------------------------------------------------------- portraits
    def test_portraits_have_the_counts_of_the_spec_and_round_trip(self) -> None:
        isc = self.isc
        parsed = isc.parse_portrait_file(self.files["portraits.bin"])
        self.assertEqual([len(p["tiles"]) for p in parsed["portraits"]], [23, 18, 31, 18, 24, 27, 27, 29, 37, 21, 39])
        for original, again in zip(isc.portraits(self.rom), parsed["portraits"]):
            self.assertEqual(original["tiles"], again["tiles"])
            self.assertEqual(original["frames"], again["frames"])
            self.assertEqual(len(again["frames"]), 5)
            cols, rows, x, y, cells = again["frames"][0]
            self.assertEqual((cols, rows, x, y, len(cells)), (6, 8, 0, 0, 48))
            for cell in [c for f in again["frames"] for c in f[4] if c]:
                self.assertTrue(cell[0] < len(again["tiles"]) and cell[1] & 3 <= 3)
        # the eyes and the mouth fill holes of the base picture
        for p in parsed["portraits"]:
            filled = {(8 * (i % 6), 8 * (i // 6)) for i, c in enumerate(p["frames"][0][4]) if c}
            for cols, rows, x, y, cells in p["frames"][1:]:
                for i, c in enumerate(cells):
                    if c:
                        self.assertNotIn((x + 8 * (i % cols), y + 8 * (i // cols)), filled)

    def test_portrait_pictures_equal_the_game_in_every_building_palette(self) -> None:
        """Compose the file's frames through its slot maps and palette words, and compare each pixel's colour with the ROM's own sprite drawing (`faxanadu_sprites.place`/`sprite_layer`)."""
        import faxanadu_sprites as fs
        import st_convert as sc

        isc = self.isc
        parsed = isc.parse_portrait_file(self.files["portraits.bin"])
        nes = isc.sprite_palettes_at(self.rom, isc.PORTRAIT_PALETTE_ENTRY)
        for pid, p in enumerate(parsed["portraits"]):
            tiles = {k: t for k, t in enumerate(p["tiles"])}
            for k in (0, 4, 9):                                 # a few building types keep this fast
                slots, words = parsed["slots"][k], parsed["palettes"][k]
                for f in range(5):
                    cols, rows, x, y, cells = p["frames"][f]
                    layer = {}
                    for i, c in enumerate(cells):
                        if c is None:
                            continue
                        for py, row in enumerate(fs.tile_pixels(tiles[c[0]], bool(c[1] & 0x40))):
                            for px, v in enumerate(row):
                                if v:
                                    layer[(x + 8 * (i % cols) + px, y + 8 * (i // cols) + py)] = slots[4 * (c[1] & 3) + v]
                    app = fs.appearance(self.rom, pid * 5 + f, "TILEINFO_PORTRAITS_ADDRS")
                    expected = fs.sprite_layer(fs.place(app, 0, 0, 0), tiles, nes)
                    self.assertEqual(len(layer), len(expected))
                    for (ex, ey), colour in expected.items():
                        slot = layer[(ex, ey - 32 - 1 + 0)]            # place adds the HUD's 32 lines, sprite_layer one more
                        self.assertEqual(rgb_of(words[slot]), sc.st_rgb(colour), f"portrait {pid} frame {f} pixel {ex},{ey}")

    # ---------------------------------------------------------------------------------------------------------------------------- people
    def test_the_people_have_art_bounds_and_round_trip(self) -> None:
        isc = self.isc
        parsed = isc.parse_npc_file(self.files["npc.bin"])
        kinds = parsed["kinds"]
        self.assertEqual([k["entity"] for k in kinds], list(range(0x34, 0x46)))
        self.assertEqual([k["frames"] for k in kinds], [3, 3, 3, 2, 2, 2, 4, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2])
        self.assertEqual(kinds[0x3A - 0x34]["bounds"], (0, 0, 48, 32))
        self.assertEqual(kinds[0x34 - 0x34]["bounds"], (248, 0, 32, 32))
        self.assertEqual(kinds[0x37 - 0x34]["bounds"], (0, 0, 40, 48))
        self.assertEqual(sum(len(k["tiles"]) for k in kinds), 228)
        for k in kinds:
            self.assertEqual(len(k["poses"]), 2 * k["frames"])
            for pose in k["poses"]:
                self.assertTrue(pose and all(t < len(k["tiles"]) for _, _, t, _ in pose))
        self.assertEqual(parsed["slots"][0][0], 0)
        self.assertEqual(len(parsed["slots"]), 28)
        self.assertEqual(len(parsed["palettes"]), 10)

    def test_people_pictures_equal_the_game_inside_and_outside(self) -> None:
        import faxanadu_sprites as fs
        import st_convert as sc

        isc = self.isc
        parsed = isc.parse_npc_file(self.files["npc.bin"])
        inside = isc.sprite_palettes_at(self.rom, isc.INSIDE_PALETTE_ENTRY)
        for kind in parsed["kinds"]:
            ent = kind["entity"]
            tiles = fs.entity_tiles(self.rom, ent)
            for f in range(kind["frames"]):
                app = fs.appearance(self.rom, self.rom.byte("SPRITE_APPEARANCE_PHASE_OFFSETS", ent) + f, "TILEINFO_ENTITY_ADDRS")
                for mirrored in (0, 1):
                    pose = kind["poses"][2 * f + mirrored]
                    for set_number, nes, words in ((0x11 + 3, inside, parsed["palettes"][3]), (0x1A, inside, parsed["palettes"][9]), (0x00, None, None), (0x0B, None, None)):
                        slots = parsed["slots"][set_number]
                        if nes is None:
                            nes = sc.palette_set(self.rom, set_number)[1]
                            plan = sc.plan_for_set(self.rom, set_number)
                            rgb = lambda slot: plan.colours[slot]
                        else:
                            rgb = lambda slot, w=words: rgb_of(w[slot])
                        layer = {}
                        for dx, dy, tile, attr in pose:
                            for py, row in enumerate(fs.tile_pixels(tiles[tile], bool(attr & 0x40))):
                                for px, v in enumerate(row):
                                    if v:
                                        layer[(dx + px, dy + py)] = slots[4 * (attr & 3) + v]
                        expected = fs.sprite_layer(fs.place(app, sc.ANIM_BASE, sc.ANIM_BASE, 0x40 if mirrored else 0), tiles, nes)
                        self.assertEqual(len(layer), len(expected))
                        for (ex, ey), colour in expected.items():
                            self.assertEqual(rgb(layer[(ex - sc.ANIM_BASE + sc.ST_LEFT, ey - sc.ANIM_BASE)]), sc.st_rgb(colour), f"entity {ent:#x} frame {f} set {set_number:#x}")

    def test_placements_of_eolis_and_its_buildings(self) -> None:
        places = self.isc.parse_npc_file(self.files["npc.bin"])["places"]
        self.assertEqual(places, sorted(places, key=lambda r: (r[0], r[1])))
        eolis = [r for r in places if r[0] == 0]
        self.assertEqual(eolis, [(0, 0, 0x4F, 0x00, 64, 0), (0, 1, 0x34, 0x01, 192, 144), (0, 2, 0x45, 0x03, 112, 144), (0, 3, 0x3D, 0x06, 64, 128), (0, 6, 0x44, 0x05, 48, 144),
                                 (0, 7, 0x42, 0x07, 160, 144)])
        buildings = {r[1]: (r[2], r[3], r[4], r[5]) for r in places if r[0] == 4 and r[1] < 8}
        self.assertEqual(buildings, {0: (0x40, 0x0B, 64, 128), 1: (0x45, 0x0A, 144, 128), 2: (0x39, 0x04, 32, 128), 3: (0x3C, 0x0C, 64, 128), 4: (0x37, 0x0D, 48, 112),
                                     5: (0x3B, 0x0E, 16, 112), 6: (0x38, 0x0F, 112, 128), 7: (0x3A, 0x08, 32, 112)})
        self.assertIn((4, 12, 0x3E, 0x15, 32, 128), places, "the first hospital: Apolune")
        self.assertIn((1, 37, 0x3B, 0x25, 176, 64), places, "the spring of the sky")
        self.assertTrue(all(r[2] in range(0x34, 0x46) or r[2] == 0x4F for r in places))

    # --------------------------------------------------------------------------------------------------------------------------- files
    def test_the_files_round_trip_and_the_headers_point_at_their_parts(self) -> None:
        isc = self.isc
        data = self.files["iscript.bin"]
        o = self.data["offsets_at"]
        self.assertEqual(o, sorted(o))
        self.assertTrue(all(v % 2 == 0 for v in o))
        self.assertEqual(data[o[1]:o[1] + 1581], self.data["blob"])
        self.assertEqual(int.from_bytes(data[o[0] + 2 * 0x1F:o[0] + 2 * 0x1F + 2], "big"), 0)
        self.assertEqual(self.data["offsets"], isc.script_offsets(self.rom))
        block, offsets = isc.messages(self.rom)
        self.assertEqual((self.data["messages"], self.data["message_offsets"]), (block, offsets))
        text = isc.equates(self.files)
        self.assertIn(f"ISCRIPT_BLOB, {o[1]}", text)
        self.assertIn("ISCRIPT_BASE, 41190", text)
        for name, blob in self.files.items():
            self.assertEqual(len(blob) % 2, 0, name)
        self.assertLess(sum(len(b) for b in self.files.values()), 40000, "memory")


if __name__ == "__main__":
    unittest.main()
