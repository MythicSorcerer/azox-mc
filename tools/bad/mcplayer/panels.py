# FILE: panels.py
"""
Textual panels: Player list, Info, Inventory, Ender, Armor, Attributes, Pos, Raw
"""
from textual.app import ComposeResult
from textual.widgets import Label, Button, ListView, ListItem, DataTable, Log
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.message import Message
from textual.widget import Widget
from typing import Optional

import copy
from nbtcore import read_nbt, safe_root, save_nbt, find_next_free_slot, list_players
from nbtlib import Compound, List as NbtList, Byte, String, Int, Double, Float


class PlayerSelected(Message):
    def __init__(self, uuid: str, name: str, path: str) -> None:
        self.uuid = uuid
        self.name = name
        self.path = path
        super().__init__()


class CopyInventoryRequest(Message):
    def __init__(self, target_uuid: str) -> None:
        self.target_uuid = target_uuid
        super().__init__()


class PlayerListPanel(Widget):
    def compose(self) -> ComposeResult:
        yield Label("Players")
        self.listview = ListView()
        yield self.listview
        yield Button("Refresh", id="players_refresh")

    def on_mount(self) -> None:
        self.refresh_players()

    def refresh_players(self):
        self.listview.clear()
        for name, uuid, path in list_players():
            item = ListItem(Label(f"{name} ({uuid})"))
            item.data = (uuid, name, path)
            self.listview.append(item)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "players_refresh":
            self.refresh_players()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not item or not hasattr(item, 'data'):
            return
        uuid, name, path = item.data
        self.post_message(PlayerSelected(uuid, name, path))


class InfoPanel(Widget):
    player_uuid = reactive(None)
    player_name = reactive(None)
    player_path = reactive(None)
    nbt_file = reactive(None)
    root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label('Player Info')
        self.log = Log()
        yield self.log
        with Horizontal():
            yield Button('Save', id='save_btn')
            yield Button('Reload', id='reload_btn')
            yield Button('Copy Inventory', id='copyinv_btn')
            yield Button('Undo', id='undo_btn')

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
            self.log.write('No player loaded.')
            return
        get = lambda k, d='(not set)': self.root.get(k, d)
        self.log.write(f"Name: {get('LastKnownName', self.player_name)}")
        if 'Health' in self.root:
            self.log.write(f"Health: {self.root['Health']}")
        if 'foodLevel' in self.root:
            self.log.write(f"Hunger: {self.root['foodLevel']}")
        if 'XpLevel' in self.root:
            self.log.write(f"XP Level: {self.root['XpLevel']}")
        if 'Pos' in self.root:
            self.log.write(f"Pos: {self.root['Pos']}")
        inv = self.root.get('Inventory', NbtList())
        self.log.write(f"Inventory items: {len(inv)}")
        ender = self.root.get('EnderItems', NbtList())
        self.log.write(f"Ender chest items: {len(ender)}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == 'save_btn':
            if not self.nbt_file:
                self.log.write('Nothing to save')
                return
            try:
                save_nbt(self.nbt_file, self.player_path)
                self.log.write('Saved (backup/undo).')
            except Exception as e:
                self.log.write(f"Save failed: {e}")
        elif bid == 'reload_btn':
            try:
                self.nbt_file = read_nbt(self.player_path)
                self.root = safe_root(self.nbt_file)
                self.refresh()
                self.log.write('Reloaded')
            except Exception as e:
                self.log.write(f"Reload failed: {e}")
        elif bid == 'copyinv_btn':
            self.post_message(CopyInventoryRequest(self.player_uuid))
        elif bid == 'undo_btn':
            undo1 = f"{self.player_path}.undo1"
            if os.path.exists(undo1):
                try:
                    shutil.copy2(undo1, self.player_path)
                    self.nbt_file = read_nbt(self.player_path)
                    self.root = safe_root(self.nbt_file)
                    self.refresh()
                    self.log.write('Restored .undo1')
                except Exception as e:
                    self.log.write(f"Undo failed: {e}")
            else:
                self.log.write('No undo1 file')


class InventoryPanel(Widget):
    nbt_root = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label('Inventory')
        self.table = DataTable()
        self.table.add_columns('Slot','Item ID','Count')
        yield self.table
        with Horizontal():
            yield Button('Add', id='inv_add')
            yield Button('Remove', id='inv_remove')
            yield Button('Auto-slot', id='inv_autoslot')
            yield Button('Clear', id='inv_clear')

    def load_root(self, root):
        self.nbt_root = root
        self.refresh_table()

    def refresh_table(self):
        self.table.clear(columns=False)
        if not self.nbt_root:
            return
        inv = self.nbt_root.get('Inventory', NbtList())
        for it in inv:
            slot = int(it.get('Slot',-1))
            iid = it.get('id','unknown')
            cnt = int(it.get('count',1))
            self.table.add_row(str(slot), str(iid), str(cnt))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == 'inv_add':
            slot = await self.app.prompt('Slot (empty for auto): ')
            if slot is None:
                return
            slot = slot.strip()
            if slot == '':
                inv = self.nbt_root.setdefault('Inventory', NbtList())
                next_slot = find_next_free_slot(inv)
                if next_slot is None:
                    await self.app.notify('No free slots 0..35')
                    return
                slot_num = next_slot
            else:
                try:
                    slot_num = int(slot)
                except Exception:
                    await self.app.notify('Invalid slot')
                    return
            item_id = await self.app.prompt('Item ID (minecraft:diamond): ')
            if item_id is None or item_id.strip() == '':
                await self.app.notify('No item id')
                return
            count = await self.app.prompt('Count (default 1): ')
            if count is None or count.strip() == '':
                count_num = 1
            else:
                try:
                    count_num = int(count)
                except Exception:
                    count_num = 1
            inv = self.nbt_root.setdefault('Inventory', NbtList())
            inv[:] = [x for x in inv if int(x.get('Slot',-1)) != slot_num]
            inv.append(Compound({'Slot': Byte(slot_num), 'id': String(item_id.strip()), 'count': Int(count_num)}))
            self.refresh_table()
            await self.app.notify('Item added.')
        elif bid == 'inv_remove':
            sel = await self.app.prompt('Slot to remove: ')
            if sel is None:
                return
            try:
                s = int(sel)
            except Exception:
                await self.app.notify('Invalid')
                return
            inv = self.nbt_root.setdefault('Inventory', NbtList())
            before = len(inv)
            inv[:] = [x for x in inv if int(x.get('Slot',-1)) != s]
            if len(inv) < before:
                await self.app.notify('Removed')
            else:
                await self.app.notify('No item at that slot')
            self.refresh_table()
        elif bid == 'inv_autoslot':
            inv = self.nbt_root.setdefault('Inventory', NbtList())
            s = find_next_free_slot(inv)
            await self.app.notify(f'Next free slot: {s}' if s is not None else 'No free slots')
        elif bid == 'inv_clear':
            self.nbt_root['Inventory'] = NbtList()
            self.refresh_table()
            await self.app.notify('Inventory cleared')


class EnderPanel(InventoryPanel):
    def compose(self) -> ComposeResult:
        yield Label('Ender Chest')
        self.table = DataTable()
        self.table.add_columns('Slot','Item ID','Count')
        yield self.table
        with Horizontal():
            yield Button('Add', id='ender_add')
            yield Button('Remove', id='ender_remove')
            yield Button('Clear', id='ender_clear')

    def refresh_table(self):
        self.table.clear(columns=False)
        if not self.nbt_root:
            return
        inv = self.nbt_root.get('EnderItems', NbtList())
        for it in inv:
            slot = int(it.get('Slot',-1))
            iid = it.get('id','unknown')
            cnt = int(it.get('count',1))
            self.table.add_row(str(slot), str(iid), str(cnt))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == 'ender_add':
            slot = await self.app.prompt('Slot (leave blank for auto): ')
            if slot is None:
                return
            slot = slot.strip()
            ender = self.nbt_root.setdefault('EnderItems', NbtList())
            if slot == '':
                occupied = set(int(x.get('Slot',-1)) for x in ender)
                for s in range(0,27):
                    if s not in occupied:
                        slot_num = s
                        break
                else:
                    await self.app.notify('No free ender slots')
                    return
            else:
                try:
                    slot_num = int(slot)
                except Exception:
                    await self.app.notify('Invalid slot')
                    return
            item_id = await self.app.prompt('Item ID: ')
            if not item_id:
                await self.app.notify('No item id')
                return
            cnt = await self.app.prompt('Count (1): ')
            try:
                count_num = int(cnt) if cnt and cnt.strip() else 1
            except Exception:
                count_num = 1
            ender[:] = [x for x in ender if int(x.get('Slot',-1)) != slot_num]
            ender.append(Compound({'Slot': Byte(slot_num), 'id': String(item_id.strip()), 'count': Int(count_num)}))
            self.refresh_table()
            await self.app.notify('Ender item added')
        elif bid == 'ender_remove':
            s = await self.app.prompt('Slot to remove: ')
            if s is None:
                return
            try:
                ss = int(s)
            except Exception:
                await self.app.notify('Invalid')
                return
            ender = self.nbt_root.setdefault('EnderItems', NbtList())
            before = len(ender)
            ender[:] = [x for x in ender if int(x.get('Slot',-1)) != ss]
            if len(ender) < before:
                await self.app.notify('Removed')
            else:
                await self.app.notify('Not found')
            self.refresh_table()
        elif bid == 'ender_clear':
            self.nbt_root['EnderItems'] = NbtList()
            self.refresh_table()
            await self.app.notify('Cleared ender chest')


# Panels: ArmorPanel, AttributesPanel, PosPanel, RawNbtPanel (omitted here for brevity)
# They are present in the canvas document as full implementations.
