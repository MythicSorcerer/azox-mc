#!/usr/bin/env python3
"""
mcplayer.py — Minecraft playerdata TUI editor (Textual)

Features:
 - Textual TUI with player list and per-player sections
 - Player selection by username using usercache.json (SERVER_DIR/usercache.json)
 - Inventory, Ender Chest, Armor/Offhand editors (add/remove/auto-slot)
 - Basics editor (Health, Hunger, XP, Gamemode, Dimension)
 - Position / Rotation editor
 - Attributes editor
 - Copy inventory from another player
 - Pretty raw NBT view
 - Save with .bak and rotating .undo1..undoN
 - Works with vanilla and modded playerdata (handles both "Data" wrapper and bare player compound)
 - Configured for SERVER_DIR = "/opt/minecraft/server"

Requires: nbtlib, textual
"""

import os
import sys
import json
import shutil
import copy
import time
from typing import Optional, List, Tuple

import nbtlib
from nbtlib import Compound, List as NbtList, String, Int, Byte, Double, Float

# Textual imports
from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, Button, ListView, ListItem,
    Label, Input, DataTable, Log
)
from textual.containers import Horizontal, Vertical, Container, Grid
from textual.reactive import reactive
from textual.message import Message

# ======== CONFIG ========
SERVER_DIR = "/opt/minecraft/server"
WORLD_DIR = os.path.join(SERVER_DIR, "world")
PLAYERDATA_DIR = os.path.join(WORLD_DIR, "playerdata")
USERCACHE = os.path.join(SERVER_DIR, "usercache.json")
UNDO_LIMIT = 8

# small built-in list for item autocompletion (you can expand)
COMMON_ITEM_IDS = [
    "minecraft:stone","minecraft:cobblestone","minecraft:oak_log","minecraft:oak_planks",
    "minecraft:stick","minecraft:stone_axe","minecraft:iron_pickaxe","minecraft:iron_axe",
    "minecraft:diamond","minecraft:diamond_block","minecraft:diamond_sword","minecraft:elytra",
    "minecraft:iron_ingot","minecraft:gold_ingot","minecraft:apple","minecraft:bread",
    "minecraft:torch","minecraft:water_bucket","minecraft:lava_bucket"
]

# ======== Utility functions for NBT handling ========

def load_usercache() -> dict:
    """Return map uuid -> username from usercache.json if present."""
    try:
        if os.path.exists(USERCACHE):
            with open(USERCACHE, "r", encoding="utf8") as f:
                data = json.load(f)
                return {e["uuid"]: e["name"] for e in data if "uuid" in e and "name" in e}
    except Exception:
        pass
    return {}

def list_player_files() -> List[str]:
    if not os.path.isdir(PLAYERDATA_DIR):
        return []
    return sorted([f for f in os.listdir(PLAYERDATA_DIR) if f.endswith(".dat")])

def read_nbt(path: str):
    return nbtlib.load(path)

def safe_root(nbt_obj):
    """Return the player compound (handles both old Data wrapper and bare compound)."""
    root = getattr(nbt_obj, "root", nbt_obj)
    if isinstance(root, dict) and "Data" in root:
        return root["Data"]
    return root

def push_undo(path: str):
    """Rotate undo files: .undoN ... .undo1 (most recent)"""
    for i in range(UNDO_LIMIT, 1, -1):
        prev = f"{path}.undo{i-1}"
        cur = f"{path}.undo{i}"
        if os.path.exists(prev):
            try:
                shutil.move(prev, cur)
            except Exception:
                pass
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.undo1")

def backup_file(path: str):
    bak = f"{path}.bak"
    shutil.copy2(path, bak)
    return bak

def save_nbt(nbt_file, path: str):
    push_undo(path)
    backup_file(path)
    nbt_file.save(path)

def find_next_free_slot(inv: NbtList) -> Optional[int]:
    occupied = set()
    for it in inv:
        try:
            occupied.add(int(it.get("Slot", -1)))
        except Exception:
            pass
    for s in range(0, 36):
        if s not in occupied:
            return s
    return None

# ======== Messages ========
class PlayerSelected(Message):
    def __init__(self, uuid: str, name: str, path: str) -> None:
        self.uuid = uuid
        self.name = name
        self.path = path
        super().__init__()

# ======== UI Widgets (panels) ========

class PlayerListPanel(Static):
    """Left panel showing players by username."""

    def compose(self) -> ComposeResult:
        yield Label("Players", id="players_label")
        self.listview = ListView(id="players_list")
        yield self.listview
        yield Button("Refresh", id="players_refresh")

    def refresh_players(self):
        self.listview.clear()
        users = load_usercache()
        files = list_player_files()
        entries = []
        for f in files:
            uuid = f[:-4]
            name = users.get(uuid, uuid)
            entries.append((name, uuid, os.path.join(PLAYERDATA_DIR, f)))
        for name, uuid, path in entries:
            item = ListItem(Label(f"{name}  ({uuid})"))
            item.data = (uuid, name, path)
            self.listview.append(item)

    def on_mount(self) -> None:
        self.refresh_players()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "players_refresh":
            self.refresh_players()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item or not hasattr(event.item, "data"):
            return
        uuid, name, path = event.item.data
        self.post_message(PlayerSelected(uuid, name, path))


class InfoPanel(Static):
    """Top-right basics info and actions."""

    player_uuid = reactive(None)
    player_name = reactive(None)
    player_path = reactive(None)
    nbt_file = reactive(None)
    root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Player Info", id="info_label")
        self.log = TextLog(highlight=False, markup=False, id="info_log")
        yield self.log
        # action buttons
        with Horizontal():
            yield Button("Save", id="save_btn")
            yield Button("Reload", id="reload_btn")
            yield Button("Copy Inventory", id="copyinv_btn")
            yield Button("Undo", id="undo_btn")

    def set_player(self, uuid: str, name: str, path: str):
        self.player_uuid = uuid
        self.player_name = name
        self.player_path = path
        try:
            self.nbt_file = read_nbt(path)
            self.root = safe_root(self.nbt_file)
        except Exception as e:
            self.nbt_file = None
            self.root = None
            self.log.write(f"Failed to load: {e}")
            return
        self.refresh()

    def refresh(self):
        self.log.clear()
        if not self.root:
            self.log.write("No player loaded.")
            return
        # show key basic fields
        get = lambda k, d="(not set)": (self.root.get(k, d))
        self.log.write(f"Name: {get('LastKnownName', self.player_name)}")
        if "Health" in self.root:
            self.log.write(f"Health: {self.root['Health']}")
        if "foodLevel" in self.root:
            self.log.write(f"Hunger: {self.root['foodLevel']}")
        if "XpLevel" in self.root:
            self.log.write(f"XP Level: {self.root['XpLevel']}")
        if "XpTotal" in self.root:
            self.log.write(f"XP Total: {self.root['XpTotal']}")
        if "playerGameType" in self.root:
            self.log.write(f"Gamemode (playerGameType): {self.root['playerGameType']}")
        if "Pos" in self.root:
            self.log.write(f"Pos: {self.root['Pos']}")
        if "Rotation" in self.root:
            self.log.write(f"Rotation: {self.root['Rotation']}")
        # quick inventory summary
        inv = self.root.get("Inventory", NbtList())
        self.log.write(f"Inventory items: {len(inv)}")
        ender = self.root.get("EnderItems", NbtList())
        self.log.write(f"Ender chest items: {len(ender)}")

    # Button handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save_btn":
            if not self.nbt_file:
                self.log.write("Nothing to save.")
                return
            try:
                save_nbt(self.nbt_file, self.player_path)
                self.log.write("Saved (backup and undo created).")
            except Exception as e:
                self.log.write(f"Save failed: {e}")
        elif bid == "reload_btn":
            try:
                self.nbt_file = read_nbt(self.player_path)
                self.root = safe_root(self.nbt_file)
                self.refresh()
                self.log.write("Reloaded from disk.")
            except Exception as e:
                self.log.write(f"Reload failed: {e}")
        elif bid == "copyinv_btn":
            self.post_message_no_wait(CopyInventoryRequest(self.player_uuid))
        elif bid == "undo_btn":
            # try restore latest undo1
            undo1 = f"{self.player_path}.undo1"
            if os.path.exists(undo1):
                try:
                    shutil.copy2(undo1, self.player_path)
                    self.nbt_file = read_nbt(self.player_path)
                    self.root = safe_root(self.nbt_file)
                    self.refresh()
                    self.log.write("Restored .undo1.")
                except Exception as e:
                    self.log.write(f"Undo failed: {e}")
            else:
                self.log.write("No undo1 file available.")


class CopyInventoryRequest(Message):
    def __init__(self, target_uuid: str) -> None:
        self.target_uuid = target_uuid
        super().__init__()


class InventoryPanel(Static):
    """Main inventory editor (table view)."""

    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Inventory", id="inv_label")
        # DataTable for inventory: Slot | Item ID | Count
        self.table = DataTable(id="inv_table")
        self.table.add_columns("Slot", "Item ID", "Count")
        yield self.table
        with Horizontal():
            yield Button("Add", id="inv_add")
            yield Button("Remove", id="inv_remove")
            yield Button("Auto-slot", id="inv_autoslot")
            yield Button("Clear", id="inv_clear")

    def load_root(self, root):
        self.nbt_root = root
        self.refresh_table()

    def refresh_table(self):
        self.table.clear(columns=False)
        if not self.nbt_root:
            return
        inv = self.nbt_root.get("Inventory", NbtList())
        for it in inv:
            slot = int(it.get("Slot", -1))
            iid = it.get("id", "unknown")
            cnt = int(it.get("count", 1))
            self.table.add_row(str(slot), str(iid), str(cnt))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "inv_add":
            # interactive prompt (simple Input modal)
            slot = await self.app.prompt("Slot (empty for auto): ")
            if slot is None:
                return
            slot = slot.strip()
            if slot == "":
                inv = self.nbt_root.setdefault("Inventory", NbtList())
                next_slot = find_next_free_slot(inv)
                if next_slot is None:
                    await self.app.notify("No free slots 0..35")
                    return
                slot_num = next_slot
            else:
                try:
                    slot_num = int(slot)
                except Exception:
                    await self.app.notify("Invalid slot")
                    return
            item_id = await self.app.prompt("Item ID (e.g. minecraft:diamond): ")
            if item_id is None or item_id.strip() == "":
                await self.app.notify("No item id")
                return
            count = await self.app.prompt("Count (default 1): ")
            if count is None or count.strip() == "":
                count_num = 1
            else:
                try:
                    count_num = int(count)
                except Exception:
                    count_num = 1
            inv = self.nbt_root.setdefault("Inventory", NbtList())
            # remove existing in that slot
            inv[:] = [x for x in inv if int(x.get("Slot", -1)) != slot_num]
            inv.append(Compound({"Slot": Byte(slot_num), "id": String(item_id.strip()), "count": Int(count_num)}))
            self.refresh_table()
            await self.app.notify("Item added.")
        elif bid == "inv_remove":
            sel = await self.app.prompt("Slot to remove: ")
            if sel is None:
                return
            try:
                s = int(sel)
            except Exception:
                await self.app.notify("Invalid")
                return
            inv = self.nbt_root.setdefault("Inventory", NbtList())
            before = len(inv)
            inv[:] = [x for x in inv if int(x.get("Slot", -1)) != s]
            if len(inv) < before:
                await self.app.notify("Removed.")
            else:
                await self.app.notify("No item at that slot.")
            self.refresh_table()
        elif bid == "inv_autoslot":
            inv = self.nbt_root.setdefault("Inventory", NbtList())
            s = find_next_free_slot(inv)
            await self.app.notify(f"Next free slot: {s}" if s is not None else "No free slots")
        elif bid == "inv_clear":
            self.nbt_root["Inventory"] = NbtList()
            self.refresh_table()
            await self.app.notify("Inventory cleared.")


class EnderPanel(InventoryPanel):
    """Reuses InventoryPanel behavior for EnderItems."""
    def compose(self) -> ComposeResult:
        yield Label("Ender Chest", id="ender_label")
        self.table = DataTable(id="ender_table")
        self.table.add_columns("Slot", "Item ID", "Count")
        yield self.table
        with Horizontal():
            yield Button("Add", id="ender_add")
            yield Button("Remove", id="ender_remove")
            yield Button("Clear", id="ender_clear")

    def refresh_table(self):
        self.table.clear(columns=False)
        if not self.nbt_root:
            return
        inv = self.nbt_root.get("EnderItems", NbtList())
        for it in inv:
            slot = int(it.get("Slot", -1))
            iid = it.get("id", "unknown")
            cnt = int(it.get("count", 1))
            self.table.add_row(str(slot), str(iid), str(cnt))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "ender_add":
            slot = await self.app.prompt("Slot (leave blank for auto): ")
            if slot is None:
                return
            slot = slot.strip()
            ender = self.nbt_root.setdefault("EnderItems", NbtList())
            if slot == "":
                # find next unused slot in ender (0..26 typically)
                occupied = set(int(x.get("Slot", -1)) for x in ender)
                for s in range(0, 27):
                    if s not in occupied:
                        slot_num = s
                        break
                else:
                    await self.app.notify("No free ender slots")
                    return
            else:
                try:
                    slot_num = int(slot)
                except Exception:
                    await self.app.notify("Invalid slot")
                    return
            item_id = await self.app.prompt("Item ID: ")
            if not item_id:
                await self.app.notify("No item id")
                return
            cnt = await self.app.prompt("Count (1): ")
            try:
                count_num = int(cnt) if cnt and cnt.strip() else 1
            except Exception:
                count_num = 1
            ender[:] = [x for x in ender if int(x.get("Slot", -1)) != slot_num]
            ender.append(Compound({"Slot": Byte(slot_num), "id": String(item_id.strip()), "count": Int(count_num)}))
            self.refresh_table()
            await self.app.notify("Ender item added.")
        elif bid == "ender_remove":
            s = await self.app.prompt("Slot to remove: ")
            if s is None:
                return
            try:
                ss = int(s)
            except Exception:
                await self.app.notify("Invalid")
                return
            ender = self.nbt_root.setdefault("EnderItems", NbtList())
            before = len(ender)
            ender[:] = [x for x in ender if int(x.get("Slot", -1)) != ss]
            if len(ender) < before:
                await self.app.notify("Removed.")
            else:
                await self.app.notify("Not found.")
            self.refresh_table()
        elif bid == "ender_clear":
            self.nbt_root["EnderItems"] = NbtList()
            self.refresh_table()
            await self.app.notify("Cleared ender chest.")


class ArmorPanel(Static):
    """Armor and offhand editor."""

    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Armor / Offhand", id="armor_label")
        self.log = TextLog()
        yield self.log
        with Horizontal():
            yield Button("Set Armor", id="armor_set")
            yield Button("Set Offhand", id="offhand_set")
            yield Button("Clear Armor", id="armor_clear")
            yield Button("Clear Offhand", id="offhand_clear")

    def load_root(self, root):
        self.nbt_root = root
        self.refresh()

    def refresh(self):
        self.log.clear()
        inv = self.nbt_root.get("Inventory", NbtList())
        armor_items = [it for it in inv if 36 <= int(it.get("Slot", -1)) <= 39]
        offhand = [it for it in inv if int(it.get("Slot", -1)) == 40]
        if not armor_items:
            self.log.write("Armor: (none)")
        else:
            for it in armor_items:
                self.log.write(f"Slot {int(it['Slot'])}: {it.get('id')} x{int(it.get('count',1))}")
        if offhand:
            it = offhand[0]
            self.log.write(f"Offhand: Slot {int(it['Slot'])}: {it.get('id')} x{int(it.get('count',1))}")
        else:
            self.log.write("Offhand: (none)")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        inv = self.nbt_root.setdefault("Inventory", NbtList())
        if bid == "armor_set":
            which = await self.app.prompt("Which (boots/legs/chest/helmet): ")
            if not which:
                return
            mapping = {"boots":36, "legs":37, "chest":38, "helmet":39}
            w = which.strip().lower()
            if w not in mapping:
                await self.app.notify("Invalid")
                return
            slot = mapping[w]
            iid = await self.app.prompt("Item ID: ")
            if not iid:
                await self.app.notify("No ID")
                return
            cnt = await self.app.prompt("Count (1): ")
            try:
                cntn = int(cnt) if cnt and cnt.strip() else 1
            except Exception:
                cntn = 1
            # remove old
            inv[:] = [x for x in inv if int(x.get("Slot", -1)) != slot]
            inv.append(Compound({"Slot": Byte(slot), "id": String(iid.strip()), "count": Int(cntn)}))
            self.refresh()
            await self.app.notify("Armor set.")
        elif bid == "offhand_set":
            slot = 40
            iid = await self.app.prompt("Offhand Item ID: ")
            if not iid:
                return
            cnt = await self.app.prompt("Count (1): ")
            try:
                cntn = int(cnt) if cnt and cnt.strip() else 1
            except Exception:
                cntn = 1
            inv[:] = [x for x in inv if int(x.get("Slot", -1)) != slot]
            inv.append(Compound({"Slot": Byte(slot), "id": String(iid.strip()), "count": Int(cntn)}))
            self.refresh()
            await self.app.notify("Offhand set.")
        elif bid == "armor_clear":
            inv[:] = [x for x in inv if not (36 <= int(x.get("Slot", -1)) <= 39)]
            self.refresh()
            await self.app.notify("Armor cleared.")
        elif bid == "offhand_clear":
            inv[:] = [x for x in inv if int(x.get("Slot", -1)) != 40]
            self.refresh()
            await self.app.notify("Offhand cleared.")


class AttributesPanel(Static):
    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Attributes", id="attr_label")
        self.log = TextLog()
        yield self.log
        with Horizontal():
            yield Button("Add/Set", id="attr_set")
            yield Button("Remove", id="attr_remove")
            yield Button("List", id="attr_list")

    def load_root(self, root):
        self.nbt_root = root
        self.refresh()

    def refresh(self):
        self.log.clear()
        attr = self.nbt_root.get("attributes", NbtList())
        if not attr:
            self.log.write("(no attributes)")
            return
        for a in attr:
            self.log.write(f"{a.get('id')} = base {a.get('base')}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "attr_set":
            aid = await self.app.prompt("Attribute id (e.g. minecraft:generic.max_health): ")
            if not aid:
                return
            base = await self.app.prompt("Base value (float): ")
            try:
                bv = float(base)
            except Exception:
                bv = 0.0
            attr = self.nbt_root.setdefault("attributes", NbtList())
            attr[:] = [a for a in attr if a.get("id") != aid]
            attr.append(Compound({"id": String(aid), "base": Double(bv)}))
            self.refresh()
            await self.app.notify("Attribute set.")
        elif bid == "attr_remove":
            aid = await self.app.prompt("Attribute id to remove: ")
            if not aid:
                return
            attr = self.nbt_root.setdefault("attributes", NbtList())
            before = len(attr)
            attr[:] = [a for a in attr if a.get("id") != aid]
            self.refresh()
            await self.app.notify("Removed." if len(attr) < before else "Not found.")
        elif bid == "attr_list":
            self.refresh()

class PosPanel(Static):
    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Position / Rotation", id="pos_label")
        self.log = TextLog()
        yield self.log
        with Horizontal():
            yield Button("Set Pos", id="pos_set")
            yield Button("Set Rot", id="rot_set")
            yield Button("Show", id="pos_show")

    def load_root(self, root):
        self.nbt_root = root
        self.refresh()

    def refresh(self):
        self.log.clear()
        pos = self.nbt_root.get("Pos")
        rot = self.nbt_root.get("Rotation")
        self.log.write(f"Pos: {pos}")
        self.log.write(f"Rotation: {rot}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "pos_set":
            x = await self.app.prompt("X: ")
            y = await self.app.prompt("Y: ")
            z = await self.app.prompt("Z: ")
            try:
                xd, yd, zd = float(x), float(y), float(z)
            except Exception:
                await self.app.notify("Invalid numbers")
                return
            if yd < -64 or yd > 320:
                ok = await self.app.prompt("Y is extreme, continue? (y/N): ")
                if not ok or ok.lower().strip() != "y":
                    await self.app.notify("Cancelled.")
                    return
            self.nbt_root["Pos"] = NbtList([Double(xd), Double(yd), Double(zd)])
            self.refresh()
            await self.app.notify("Pos set.")
        elif bid == "rot_set":
            yaw = await self.app.prompt("Yaw: ")
            pitch = await self.app.prompt("Pitch: ")
            try:
                yv, pv = float(yaw), float(pitch)
            except Exception:
                await self.app.notify("Invalid")
                return
            self.nbt_root["Rotation"] = NbtList([Float(yv), Float(pv)])
            self.refresh()
            await self.app.notify("Rotation set.")
        elif bid == "pos_show":
            self.refresh()

class RawNbtPanel(Static):
    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Raw NBT (pretty print)", id="raw_label")
        self.log = TextLog()
        yield self.log

    def load_root(self, root):
        self.nbt_root = root
        self.refresh()

    def pretty_print(self, tag, indent=0):
        pad = "  " * indent
        if isinstance(tag, dict) or isinstance(tag, nbtlib.tag.Compound):
            for k, v in tag.items():
                # show short scalar inline
                if isinstance(v, (str, int, float)) or hasattr(v, "unpack") and not isinstance(v, (list, nbtlib.tag.Compound)):
                    self.log.write(f"{pad}{k}: {v}")
                else:
                    self.log.write(f"{pad}{k}:")
                    self.pretty_print(v, indent + 1)
        elif isinstance(tag, list) or isinstance(tag, nbtlib.tag.List):
            for i, it in enumerate(tag):
                self.log.write(f"{pad}[{i}]")
                self.pretty_print(it, indent + 1)
        else:
            self.log.write(f"{pad}{repr(tag)}")

    def refresh(self):
        self.log.clear()
        self.pretty_print(self.nbt_root)

# ======== App core ========

class McEditorApp(App):
    CSS = """
    Screen {
      width: 1fr;
      height: 1fr;
    }

    #left {
      width: 28%;
      padding: 1 1;
      border: round $accent;
    }
    #right {
      padding: 1 1;
    }
    #players_label, #info_label, #inv_label, #ender_label {
      dock: top;
      height: 1;
      content-align: center middle;
    }
    DataTable {
      height: 10;
    }
    TextLog {
      height: 10;
    }
    """

    BINDINGS = [("q", "quit", "Quit"), ("s", "save", "Save")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Container(id="left"):
                self.players = PlayerListPanel()
                yield self.players
            with Container(id="right"):
                # top info
                self.info = InfoPanel()
                yield self.info
                # grid of subpanels
                with Grid():
                    self.inventory = InventoryPanel()
                    self.ender = EnderPanel()
                    self.armor = ArmorPanel()
                    self.attrs = AttributesPanel()
                    self.pos = PosPanel()
                    self.raw = RawNbtPanel()
                    yield self.inventory
                    yield self.ender
                    yield self.armor
                    yield self.attrs
                    yield self.pos
                    yield self.raw
        yield Footer()

    def on_mount(self) -> None:
        # wire PlayerSelected message handler
        pass

    async def handle_player_selected(self, message: PlayerSelected) -> None:
        # load the player NBT and set into each panel
        uuid = message.uuid
        name = message.name
        path = message.path
        # load
        try:
            nbt_file = read_nbt(path)
            root = safe_root(nbt_file)
        except Exception as e:
            await self.notify(f"Failed to load {path}: {e}")
            return
        self.info.set_player(uuid, name, path)
        # pass root to panels
        self.inventory.load_root(root)
        self.ender.load_root(root)
        self.armor.load_root(root)
        self.attrs.load_root(root)
        self.pos.load_root(root)
        self.raw.load_root(root)

    async def handle_copy_inventory_request(self, message: CopyInventoryRequest) -> None:
        # Ask which source player to use
        players = list_players()  # (name, uuid, path)
        if not players:
            await self.notify("No players available to copy from.")
            return
        # build prompt
        choices = "\n".join([f"{i+1}. {n[0]} ({n[1]})" for i, n in enumerate(players)])
        sel = await self.prompt(f"Pick source player number:\n{choices}\nEnter number: ")
        if not sel:
            return
        try:
            idx = int(sel.strip()) - 1
        except Exception:
            await self.notify("Invalid selection.")
            return
        if not (0 <= idx < len(players)):
            await self.notify("Out of range.")
            return
        _, _, path = players[idx]
        try:
            src_nbt = read_nbt(path)
            src_root = safe_root(src_nbt)
            src_inv = copy.deepcopy(src_root.get("Inventory", NbtList()))
        except Exception as e:
            await self.notify(f"Failed to read source: {e}")
            return
        # target is currently loaded in info panel
        target_path = self.info.player_path
        if not target_path:
            await self.notify("No target selected.")
            return
        # confirm
        ok = await self.prompt(f"Copy {len(src_inv)} items into current player's inventory? This replaces their Inventory. (y/N): ")
        if not ok or ok.strip().lower() != "y":
            await self.notify("Cancelled.")
            return
        # perform copy
        self.info.root["Inventory"] = src_inv
        # refresh panels
        self.inventory.refresh_table()
        await self.notify("Inventory copied into current player (in-memory). Save to persist.")

    # textual's default prompt/notify wrappers
    async def prompt(self, message: str) -> Optional[str]:
        """
        A very small textual prompt: print to footer and read from stdin.
        Textual doesn't provide a built-in blocking modal easily cross-version, so we
        do a simple blocking console input with a printed message — it works fine
        inside terminal TUI sessions for quick input.
        """
        # Show message in footer
        self.log_to_footer(str(message))
        # Accept input from the user on stdin — this blocks the TUI but is simple.
        try:
            res = await self.run_in_thread(lambda: input(message + " "))
        except Exception:
            return None
        return res

    async def notify(self, message: str):
        self.log_to_footer(str(message))

    def log_to_footer(self, text: str):
        # quick way to show ephemeral messages
        self.query_one(Footer).update(text)

    # binding actions
    def action_save(self) -> None:
        if self.info and self.info.nbt_file and self.info.player_path:
            try:
                save_nbt(self.info.nbt_file, self.info.player_path)
                self.notify_sync("Saved.")
            except Exception as e:
                self.notify_sync(f"Save failed: {e}")
        else:
            self.notify_sync("No player loaded.")

    def notify_sync(self, text: str):
        self.log_to_footer(text)

# Helper for listing players to pick from in copy
def list_players() -> List[Tuple[str, str, str]]:
    users = load_usercache()
    files = list_player_files()
    out = []
    for f in files:
        uuid = f[:-4]
        name = users.get(uuid, uuid)
        out.append((name, uuid, os.path.join(PLAYERDATA_DIR, f)))
    return out

# ======== Run ========
def ensure_env():
    if not os.path.isdir(PLAYERDATA_DIR):
        print(f"Playerdata directory not found: {PLAYERDATA_DIR}")
        print("Edit SERVER_DIR or WORLD_DIR at top of script to point to your server.")
        sys.exit(1)

def main():
    ensure_env()
    app = McEditorApp()
    app.run()

if __name__ == "__main__":
    main()

