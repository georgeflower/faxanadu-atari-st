#!/usr/bin/env python3
"""The interaction-script interpreter (bank 12 `IScriptAction_*`) as the ROM does it, in Python: every script of the Europe ROM can be run on a player state with a rule for
what the buttons do, and the result (the actions run, the state after) is what `tools/refnes/iscriptprobe.mjs` finds in the ROM itself (`tests/test_iscript_model.py`)
and what the 68000 interpreter (src/town.s) is checked against.

State: gold (24 bit), power, magic, title, next title, spawn point, special items, quests, the five inventories (weapons, armour, shields, magic: 4 entries, items: 8) with what
is selected in each. The ROM's names are used in the comments.

Buttons (`policy`): "A" presses A whenever a script waits (every question is a yes, the first entry of every shop or sell menu is chosen, the Buy of the buy-or-sell menu);
"BA" presses B first: a message that can be skipped and a question end the script, so does every menu; a message that cannot be skipped goes on with A.

`run` returns the actions run (the ROM address of each, as `IScripts_InvokeNextAction` fetches them; an action that ends the script by itself, as B in a message does,
adds nothing), the messages shown, in order, and the state. Nothing is timed: the model does what a script does, not how long it takes.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import iscripts as isc

SPECIAL_IDS = (0x80, 0x81, 0x82, 0x83, 0x92, 0x8A, 0x93, 0x94)          # SPECIAL_ITEM_IDS: the id of each special item, the bit of each is 0x80 >> index
CAPACITY = (4, 4, 4, 4, 8)                                                # MAX_INVENTORY_SLOTS: weapons, armour, shields, magic, items
QUEST_BITS = (1, 2, 4)                                                    # ISCRIPTS_QUEST_BITS
NOT_ENOUGH, CANNOT_CARRY, BUY_OR_SELL, NOTHING_TO_SELL, WHICH_SELL, WHAT_WOULD = 3, 6, 0x10, 0x12, 0x13, 0x14
PASSWORD_MESSAGES = ()


@dataclass
class State:
    gold: int = 0
    power: int = 80                                   # Player_HP_U
    magic: int = 80                                   # Player_MP
    title: int = 0                                    # PlayerTitle
    next_title: int = 0                               # NextPlayerTitle
    spawn: int = 0                                    # TempleSpawnPoint
    special: int = 0                                  # SpecialItems
    quests: int = 0                                   # Quests
    lists: list = field(default_factory=lambda: [[], [], [], [], []])           # WeaponInventory, ArmorInventory, ShieldInventory, MagicInventory, ItemInventory (the first Number... entries)
    selected: list = field(default_factory=lambda: [0xFF] * 5)                   # SelectedWeapon, SelectedArmor, SelectedShield, SelectedMagic, SelectedItem

    def copy(self) -> "State":
        return copy.deepcopy(self)

    def key(self) -> dict:
        return {"gold": self.gold, "power": self.power, "magic": self.magic, "title": self.title, "next_title": self.next_title, "spawn": self.spawn, "special": self.special,
                "quests": self.quests, "lists": [list(x) for x in self.lists], "selected": list(self.selected)}


PRESETS = {                                                               # the states the checks start from (the tests of the ROM's interpreter and of the 68000's)
    "fresh": State(gold=0, power=40, magic=10, selected=[0xFF, 0, 0, 0xFF, 0xFF]),
    "rich": State(gold=9000, power=30, magic=20, title=3, next_title=5, spawn=2, lists=[[0], [1], [0, 1], [0, 1], [0x10]], selected=[0, 1, 0, 0, 0xFF]),
    "elixir": State(gold=500, power=60, magic=40, special=0x08, selected=[0xFF, 0, 0, 0xFF, 0xFF]),               # the Elixir: a spring takes it (CONSUME_ITEM)
    "mid": State(gold=1500, power=80, magic=80, title=4, next_title=4, spawn=7, special=0x80, quests=1, lists=[[], [], [], [], [0x07, 0x10, 0x12]], selected=[0xFF, 0, 0, 0xFF, 0x10]),
    "full": State(gold=100, power=50, magic=60, title=15, next_title=15, spawn=1, special=0xFF, quests=7, lists=[[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [7, 8, 9, 0x10, 0x12, 0x13, 0x14, 0x15]],
                  selected=[1, 2, 2, 3, 0x13]),
}


# ---------------------------------------------------------------------------------------------------------------------------------------- the player's things
def category(item: int) -> int:
    """Player_GetInventoryIndexForItem: the ids $00-$1F are weapons, $20 armour, $40 shields, $60 spells, $80 and up items."""
    return min(item >> 5, 4)


def lacks(s: State, item: int) -> bool:
    """Player_LacksItem: a special item by its bit; any other when it is not the one selected in its category and not in its list."""
    if item in SPECIAL_IDS:
        return not s.special & (0x80 >> SPECIAL_IDS.index(item))
    c = category(item)
    index = item & 0x1F
    if s.selected[c] == index:
        return False
    return index not in s.lists[c]


def owns_for_shop(s: State, item: int) -> bool:
    """Shop_GetPlayerHasSelectedItem: what the shop will not sell twice: an equipment item he wears or has, a special item he has. An item of the pack that is not special (a potion, a
    key) is sold again and again as long as the pack has room."""
    if item < 0x80 or item in SPECIAL_IDS:
        return not lacks(s, item)
    return False


def add_item(s: State, item: int) -> None:
    """Player_AddToInventory: a special item sets its bit; the others go to the end of their list, a full list losing its last entry first."""
    if item in SPECIAL_IDS:
        s.special |= 0x80 >> SPECIAL_IDS.index(item)
        return
    c = category(item)
    if len(s.lists[c]) == CAPACITY[c]:
        s.lists[c].pop()
    s.lists[c].append(item & 0x1F)


def remove_item(s: State, item: int) -> None:
    """Player_RemoveItem: a special item clears its bit; the others leave their list (the entries after it move up). What is selected stays selected."""
    if item in SPECIAL_IDS:
        s.special &= ~(0x80 >> SPECIAL_IDS.index(item)) & 255
        return
    c = category(item)
    index = item & 0x1F
    if index in s.lists[c]:
        s.lists[c].remove(index)


# ---------------------------------------------------------------------------------------------------------------------------------------- the interpreter
class Script:
    def __init__(self, rom):
        self.blob = isc.script_blob(rom)
        self.pointers = isc.script_pointers(rom)

    def byte(self, address: int) -> int:
        return self.blob[address - isc.BLOB_START]

    def word(self, address: int) -> int:
        return self.byte(address) | self.byte(address + 1) << 8

    def shop(self, address: int) -> list[tuple[int, int]]:
        return isc.shop_list(self.blob, address)


def run(script: Script, ident: int, state: State, policy: str = "A", limit: int = 400) -> tuple[list[int], list[int], State]:
    s = state.copy()
    actions: list[int] = []
    messages: list[int] = []
    pointer = script.pointers[0x1F if ident == 0xFF else ident]
    pc = pointer + 1                                  # the first byte is the entity byte
    b_first = policy == "BA"

    def message(m: int, kind: str) -> bool:
        """Shows message m; True when the script goes on. kind: 'unskippable', 'question' or 'skippable'."""
        messages.append(m)
        if b_first and kind != "unskippable":
            return False                              # B at any moment ends it (a question's B is "no", which ends the script)
        return True

    def final(m: int) -> None:
        messages.append(m)                            # IScripts_ShowFinalMessage: the message, A, the script ends

    for _ in range(limit):
        actions.append(pc)
        op = script.byte(pc)
        at = pc + 1
        if op == 0x00:                                                          # END
            break
        if op in (0x01, 0x02, 0x03):                                           # the messages
            if not message(script.byte(at), ("unskippable", "question", "skippable")[op - 1]):
                break
            pc = at + 1
        elif op == 0x04:                                                        # CHECK_UPDATE_TITLE
            if s.next_title != s.title:
                s.title = s.next_title
                pc = script.word(at)
            else:
                pc = at + 2
        elif op == 0x05:                                                        # PAY_GOLD
            price = script.word(at)
            if s.gold < price:
                final(NOT_ENOUGH)
                break
            s.gold -= price
            pc = at + 2
        elif op == 0x06:                                                        # SET_SPAWN
            if script.byte(at) >= s.spawn:
                s.spawn = script.byte(at)
            pc = at + 1
        elif op == 0x07:                                                        # ADD_ITEM
            add_item(s, script.byte(at))
            pc = at + 1
        elif op == 0x08:                                                        # OPEN_SHOP
            messages.append(WHAT_WOULD)
            if b_first:
                break
            entries = script.shop(script.word(at))
            item, price = entries[0]
            if owns_for_shop(s, item):
                final(CANNOT_CARRY)
                break
            c = category(item)
            if item not in SPECIAL_IDS and len(s.lists[c]) == CAPACITY[c]:
                final(CANNOT_CARRY)
                break
            if s.gold < price:
                final(NOT_ENOUGH)
                break
            add_item(s, item)
            s.gold -= price
            pc = at + 2
        elif op == 0x09:                                                        # ADD_GOLD
            s.gold = min(s.gold + script.word(at), 0xFFFFFF)
            pc = at + 2
        elif op == 0x0A:                                                        # ADD_MP
            n = script.byte(at) or 256
            if s.magic < 80:
                s.magic = min(s.magic + n, 80)
            pc = at + 1
        elif op == 0x13:                                                        # ADD_HP
            n = script.byte(at) or 256
            if s.power < 80:
                s.power = min(s.power + n, 80)
            pc = at + 1
        elif op == 0x0B:                                                        # IF_QUEST
            pc = script.word(at + 1) if s.quests & QUEST_BITS[script.byte(at) - 1] else at + 3
        elif op == 0x0C:                                                        # IF_RANK_AT_LEAST
            pc = script.word(at + 1) if script.byte(at) <= s.title else at + 3
        elif op == 0x0D:                                                        # IF_GOLD
            pc = script.word(at) if s.gold else at + 2
        elif op == 0x0E:                                                        # SET_QUEST
            s.quests |= QUEST_BITS[script.byte(at) - 1]
            pc = at + 1
        elif op == 0x0F:                                                        # BUY_SELL_MENU
            messages.append(BUY_OR_SELL)
            if b_first:
                break
            pc = script.word(at)                                                # (A on Buy)
        elif op == 0x10:                                                        # CONSUME_ITEM
            remove_item(s, script.byte(at))
            pc = at + 1
        elif op == 0x11:                                                        # SELL_MENU: the items in the pack that the list names, the last first, at half the price
            entries = dict(script.shop(script.word(at)))
            sellable = [0x80 | i for i in reversed(s.lists[4]) if (0x80 | i) in entries]
            if not sellable:
                final(NOTHING_TO_SELL)
                break
            messages.append(WHICH_SELL)
            if b_first:
                break
            item = sellable[0]
            remove_item(s, item)
            s.gold = min(s.gold + entries[item] // 2, 0xFFFFFF)
            pc = at + 2
        elif op == 0x12:                                                        # IF_HAS_ITEM
            pc = script.word(at + 1) if not lacks(s, script.byte(at)) else at + 3
        elif op == 0x14:                                                        # SHOW_PASSWORD
            pc = at
        elif op == 0x15:                                                        # FINISH_GAME
            break
        elif op == 0x17:                                                        # JUMP
            pc = script.word(at)
        else:
            raise ValueError(f"action {op:#x} at {pc:#x}")
    else:
        raise RuntimeError("the script does not end")
    return actions, messages, s
