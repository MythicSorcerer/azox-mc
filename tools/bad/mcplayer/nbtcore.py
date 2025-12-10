# FILE: nbtcore.py
"""
Core NBT utilities: load/save, paths, usercache, backups
"""
import os
import json
import shutil
import nbtlib
from typing import List, Tuple, Optional
from nbtlib import List as NbtList, Compound, Byte, String, Int, Double, Float

# Configuration - edit these if your server layout differs
SERVER_DIR = "/opt/minecraft/server"
WORLD_DIR = os.path.join(SERVER_DIR, "world")
PLAYERDATA_DIR = os.path.join(WORLD_DIR, "playerdata")
USERCACHE = os.path.join(SERVER_DIR, "usercache.json")
UNDO_LIMIT = 8

COMMON_ITEM_IDS = [
    "minecraft:stone","minecraft:cobblestone","minecraft:oak_log","minecraft:oak_planks",
    "minecraft:stick","minecraft:stone_axe","minecraft:iron_pickaxe","minecraft:iron_axe",
    "minecraft:diamond","minecraft:diamond_block","minecraft:diamond_sword","minecraft:elytra",
    "minecraft:iron_ingot","minecraft:gold_ingot","minecraft:apple","minecraft:bread",
    "minecraft:torch","minecraft:water_bucket","minecraft:lava_bucket"
]


def load_usercache() -> dict:
    try:
        if os.path.exists(USERCACHE):
            with open(USERCACHE, "r", encoding="utf8") as f:
                data = json.load(f)
                return {e["uuid"]: e["name"] for e in data if "uuid" in e and "name" in e}
    except Exception:
        return {}


def list_player_files() -> List[str]:
    if not os.path.isdir(PLAYERDATA_DIR):
        return []
    return sorted([f for f in os.listdir(PLAYERDATA_DIR) if f.endswith('.dat')])


def list_players() -> List[Tuple[str,str,str]]:
    users = load_usercache()
    files = list_player_files()
    out = []
    for f in files:
        uuid = f[:-4]
        name = users.get(uuid, uuid)
        out.append((name, uuid, os.path.join(PLAYERDATA_DIR, f)))
    return out


def read_nbt(path: str):
    return nbtlib.load(path)


def safe_root(nbt_obj):
    root = getattr(nbt_obj, "root", nbt_obj)
    if isinstance(root, dict) and "Data" in root:
        return root["Data"]
    return root


def push_undo(path: str):
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
            occupied.add(int(it.get('Slot', -1)))
        except Exception:
            pass
    for s in range(0, 36):
        if s not in occupied:
            return s
    return None
