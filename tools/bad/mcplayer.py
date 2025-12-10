#!/usr/bin/env python3
import os
import json
import shutil
import nbtlib
from nbtlib import Compound, List, String, Int, Byte

# === CONFIG ===
SERVER_ROOT = "/opt/minecraft/server/world"
PLAYERDATA = f"{SERVER_ROOT}/playerdata"
USERCACHE = f"{SERVER_ROOT}/usercache.json"

# ======================
# Utility Functions
# ======================

def load_usercache():
    """Load UUID → username mapping."""
    if not os.path.exists(USERCACHE):
        return {}

    with open(USERCACHE, "r") as f:
        try:
            data = json.load(f)
        except:
            return {}

    return {entry["uuid"]: entry["name"] for entry in data}


def safe_root(nbt):
    """Return the correct root tag, handling both old and new formats."""
    if hasattr(nbt, "root"):
        root = nbt.root
    else:
        root = nbt

    # MC 1.20+: player file is just a compound with no "Data"
    if "Data" in root:
        return root["Data"]
    return root


def load_players():
    """Return list of (name, uuid, path) for each player file."""
    usercache = load_usercache()

    players = []
    for file in os.listdir(PLAYERDATA):
        if file.endswith(".dat"):
            uuid = file[:-4]
            name = usercache.get(uuid, uuid)
            players.append((name, uuid, os.path.join(PLAYERDATA, file)))

    return players


def backup(path):
    """Make a .bak copy before saving."""
    shutil.copy(path, path + ".bak")


def load_player_nbt(path):
    nbt = nbtlib.load(path)
    root = safe_root(nbt)
    return nbt, root


def save_nbt(nbt, path):
    backup(path)
    nbt.save(path)


# ======================
# Player Info Functions
# ======================

def show_basic_info(root):
    print("\n--- Player Info ---")
    fields = ["Health", "foodLevel", "XpLevel", "SelectedItemSlot", "Dimension"]
    for key in fields:
        if key in root:
            print(f"{key}: {root[key]}")


def show_inventory(root):
    print("\n--- Inventory ---")
    inv = root.get("Inventory", List[Compound]())

    if len(inv) == 0:
        print("(empty)")
        return

    for item in inv:
        slot = int(item.get("Slot", -1))
        item_id = item.get("id", "unknown")
        count = int(item.get("count", 1))
        print(f"Slot {slot:2d}: {item_id} x{count}")


def add_item(root):
    print("\nAdd new item:")
    slot = int(input("Slot number: "))
    item_id = input("Item ID (minecraft:diamond): ")
    count = int(input("Count: "))

    inv = root.setdefault("Inventory", List[Compound]())

    inv.append(Compound({
        "Slot": Byte(slot),
        "id": String(item_id),
        "count": Int(count)
    }))

    print("Item added.")


def remove_item(root):
    inv = root.get("Inventory", List[Compound]())
    slot = int(input("Remove item from slot: "))

    removed = False
    for item in list(inv):
        if int(item.get("Slot", -1)) == slot:
            inv.remove(item)
            removed = True
            print("Item removed.")
            break

    if not removed:
        print("No item in that slot.")


def set_field(root):
    field = input("Field name (Health, foodLevel, XpLevel, etc): ")
    if field not in root:
        print("Field doesn't exist, creating it.")
    value = input("New value: ")

    # Try to store as int if possible
    if value.isdigit():
        root[field] = Int(int(value))
    else:
        root[field] = String(value)

    print("Field updated.")


# ======================
# Main Menu
# ======================

def main():
    print("=== Minecraft Player Editor ===")
    players = load_players()

    if not players:
        print("No players found.")
        return

    print("\nPlayers:")
    for i, (name, uuid, _) in enumerate(players):
        print(f"{i+1}. {name} ({uuid})")

    sel = int(input("\nSelect player: ")) - 1
    name, uuid, path = players[sel]

    print(f"\nLoading {name} ({uuid})...")
    nbt, root = load_player_nbt(path)

    while True:
        print("\n--- Menu ---")
        print("1. Show basic info")
        print("2. Show inventory")
        print("3. Add item")
        print("4. Remove item")
        print("5. Set field")
        print("6. Save & exit")
        print("7. Exit without saving")
        choice = input("> ")

        if choice == "1":
            show_basic_info(root)
        elif choice == "2":
            show_inventory(root)
        elif choice == "3":
            add_item(root)
        elif choice == "4":
            remove_item(root)
        elif choice == "5":
            set_field(root)
        elif choice == "6":
            save_nbt(nbt, path)
            print("Saved.")
            break
        elif choice == "7":
            print("Exiting without saving.")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()

