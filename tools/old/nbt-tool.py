#!/usr/bin/env python3
"""
Minecraft NBT Player Data Tool
View and edit player data in a human-readable format
"""

import os
import sys
import json
import argparse
from pathlib import Path
import struct
import gzip

# Paths (absolute from /opt/minecraft)
MINECRAFT_DIR = Path("/opt/minecraft")
USERCACHE_PATH = MINECRAFT_DIR / "server/usercache.json"
PLAYERDATA_DIR = MINECRAFT_DIR / "server/world/playerdata"


class NBTReader:
    """Simple NBT parser for Minecraft player data"""
    
    TAG_End = 0
    TAG_Byte = 1
    TAG_Short = 2
    TAG_Int = 3
    TAG_Long = 4
    TAG_Float = 5
    TAG_Double = 6
    TAG_Byte_Array = 7
    TAG_String = 8
    TAG_List = 9
    TAG_Compound = 10
    TAG_Int_Array = 11
    TAG_Long_Array = 12
    
    def __init__(self, data):
        self.data = data
        self.pos = 0
    
    def read_byte(self):
        val = struct.unpack('>b', self.data[self.pos:self.pos+1])[0]
        self.pos += 1
        return val
    
    def read_ubyte(self):
        val = struct.unpack('>B', self.data[self.pos:self.pos+1])[0]
        self.pos += 1
        return val
    
    def read_short(self):
        val = struct.unpack('>h', self.data[self.pos:self.pos+2])[0]
        self.pos += 2
        return val
    
    def read_int(self):
        val = struct.unpack('>i', self.data[self.pos:self.pos+4])[0]
        self.pos += 4
        return val
    
    def read_long(self):
        val = struct.unpack('>q', self.data[self.pos:self.pos+8])[0]
        self.pos += 8
        return val
    
    def read_float(self):
        val = struct.unpack('>f', self.data[self.pos:self.pos+4])[0]
        self.pos += 4
        return val
    
    def read_double(self):
        val = struct.unpack('>d', self.data[self.pos:self.pos+8])[0]
        self.pos += 8
        return val
    
    def read_string(self):
        length = self.read_short()
        val = self.data[self.pos:self.pos+length].decode('utf-8')
        self.pos += length
        return val
    
    def read_tag(self, tag_type):
        if tag_type == self.TAG_End:
            return None
        elif tag_type == self.TAG_Byte:
            return self.read_byte()
        elif tag_type == self.TAG_Short:
            return self.read_short()
        elif tag_type == self.TAG_Int:
            return self.read_int()
        elif tag_type == self.TAG_Long:
            return self.read_long()
        elif tag_type == self.TAG_Float:
            return self.read_float()
        elif tag_type == self.TAG_Double:
            return self.read_double()
        elif tag_type == self.TAG_Byte_Array:
            length = self.read_int()
            return [self.read_byte() for _ in range(length)]
        elif tag_type == self.TAG_String:
            return self.read_string()
        elif tag_type == self.TAG_List:
            list_type = self.read_ubyte()
            length = self.read_int()
            return [self.read_tag(list_type) for _ in range(length)]
        elif tag_type == self.TAG_Compound:
            return self.read_compound()
        elif tag_type == self.TAG_Int_Array:
            length = self.read_int()
            return [self.read_int() for _ in range(length)]
        elif tag_type == self.TAG_Long_Array:
            length = self.read_int()
            return [self.read_long() for _ in range(length)]
    
    def read_compound(self):
        compound = {}
        while True:
            tag_type = self.read_ubyte()
            if tag_type == self.TAG_End:
                break
            name = self.read_string()
            compound[name] = self.read_tag(tag_type)
        return compound
    
    def read_root(self):
        tag_type = self.read_ubyte()
        if tag_type != self.TAG_Compound:
            raise ValueError("Root tag must be compound")
        name = self.read_string()
        return self.read_compound()


class NBTWriter:
    """Simple NBT writer for Minecraft player data"""
    
    def __init__(self):
        self.data = bytearray()
    
    def write_byte(self, val):
        self.data.extend(struct.pack('>b', val))
    
    def write_ubyte(self, val):
        self.data.extend(struct.pack('>B', val))
    
    def write_short(self, val):
        self.data.extend(struct.pack('>h', val))
    
    def write_int(self, val):
        self.data.extend(struct.pack('>i', val))
    
    def write_long(self, val):
        self.data.extend(struct.pack('>q', val))
    
    def write_float(self, val):
        self.data.extend(struct.pack('>f', val))
    
    def write_double(self, val):
        self.data.extend(struct.pack('>d', val))
    
    def write_string(self, val):
        encoded = val.encode('utf-8')
        self.write_short(len(encoded))
        self.data.extend(encoded)
    
    def write_tag(self, val):
        if isinstance(val, bool):
            return NBTReader.TAG_Byte, lambda: self.write_byte(1 if val else 0)
        elif isinstance(val, int):
            if -128 <= val <= 127:
                return NBTReader.TAG_Byte, lambda: self.write_byte(val)
            elif -32768 <= val <= 32767:
                return NBTReader.TAG_Short, lambda: self.write_short(val)
            elif -2147483648 <= val <= 2147483647:
                return NBTReader.TAG_Int, lambda: self.write_int(val)
            else:
                return NBTReader.TAG_Long, lambda: self.write_long(val)
        elif isinstance(val, float):
            return NBTReader.TAG_Double, lambda: self.write_double(val)
        elif isinstance(val, str):
            return NBTReader.TAG_String, lambda: self.write_string(val)
        elif isinstance(val, list):
            if len(val) == 0:
                return NBTReader.TAG_List, lambda: (self.write_ubyte(NBTReader.TAG_End), self.write_int(0))
            first_type, _ = self.write_tag(val[0])
            return NBTReader.TAG_List, lambda: self.write_list(val, first_type)
        elif isinstance(val, dict):
            return NBTReader.TAG_Compound, lambda: self.write_compound(val)
        else:
            raise ValueError(f"Unsupported type: {type(val)}")
    
    def write_list(self, lst, item_type):
        self.write_ubyte(item_type)
        self.write_int(len(lst))
        for item in lst:
            _, writer = self.write_tag(item)
            writer()
    
    def write_compound(self, compound):
        for name, val in compound.items():
            tag_type, writer = self.write_tag(val)
            self.write_ubyte(tag_type)
            self.write_string(name)
            writer()
        self.write_ubyte(NBTReader.TAG_End)
    
    def write_root(self, compound, name=""):
        self.write_ubyte(NBTReader.TAG_Compound)
        self.write_string(name)
        self.write_compound(compound)
        return bytes(self.data)


def load_usercache():
    """Load the usercache.json file"""
    try:
        with open(USERCACHE_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def get_player_name(uuid):
    """Get player name from UUID"""
    usercache = load_usercache()
    # Try with and without dashes
    uuid_str = str(uuid).replace('-', '').lower()
    for entry in usercache:
        cache_uuid = entry.get('uuid', '').replace('-', '').lower()
        if cache_uuid == uuid_str:
            return entry.get('name', 'Unknown')
    return 'Unknown'


def get_player_uuid(name):
    """Get UUID from player name (returns with dashes for filename)"""
    usercache = load_usercache()
    for entry in usercache:
        if entry.get('name', '').lower() == name.lower():
            return entry.get('uuid', '').lower()
    return None


def list_players():
    """List all players with data files"""
    if not PLAYERDATA_DIR.exists():
        print(f"Error: Player data directory not found: {PLAYERDATA_DIR}")
        return
    
    players = []
    for dat_file in PLAYERDATA_DIR.glob('*.dat'):
        uuid = dat_file.stem
        name = get_player_name(uuid)
        players.append((name, uuid))
    
    if not players:
        print("No player data found.")
        return
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║           MINECRAFT PLAYER DATA                ║")
    print("╠════════════════════════════════════════════════════╣")
    for name, uuid in sorted(players):
        print(f"║ {name:16s} {uuid:32s} ║")
    print("╚════════════════════════════════════════════════════╝\n")


def format_value(key, value, indent=0):
    """Format a value for human-readable display"""
    prefix = "  " * indent
    
    if isinstance(value, dict):
        lines = [f"{prefix}{key}:"]
        for k, v in value.items():
            lines.extend(format_value(k, v, indent + 1))
        return lines
    elif isinstance(value, list):
        if len(value) == 0:
            return [f"{prefix}{key}: []"]
        elif isinstance(value[0], (int, float)) and len(value) <= 3:
            return [f"{prefix}{key}: [{', '.join(str(x) for x in value)}]"]
        else:
            lines = [f"{prefix}{key}: ["]
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    lines.append(f"{prefix}  [{i}]:")
                    for k, v in item.items():
                        lines.extend(format_value(k, v, indent + 2))
                else:
                    lines.append(f"{prefix}  {item}")
            lines.append(f"{prefix}]")
            return lines
    else:
        return [f"{prefix}{key}: {value}"]


def view_player(identifier):
    """View player data in human-readable format"""
    # Find the player file
    dat_file = None
    if identifier.endswith('.dat'):
        dat_file = PLAYERDATA_DIR / identifier
    else:
        # Try as UUID (with or without dashes)
        uuid_clean = identifier.replace('-', '').lower()
        dat_file = PLAYERDATA_DIR / f"{uuid_clean}.dat"
        if not dat_file.exists():
            # Try as username - get UUID from usercache
            uuid = get_player_uuid(identifier)
            if uuid:
                dat_file = PLAYERDATA_DIR / f"{uuid}.dat"
    
    if not dat_file or not dat_file.exists():
        print(f"Error: Player data not found for '{identifier}'")
        print(f"Looking for: {dat_file}")
        print(f"\nAvailable files in {PLAYERDATA_DIR}:")
        if PLAYERDATA_DIR.exists():
            for f in sorted(PLAYERDATA_DIR.glob('*.dat')):
                print(f"  {f.name}")
        return None
    
    # Read and parse NBT data
    with gzip.open(dat_file, 'rb') as f:
        data = f.read()
    
    reader = NBTReader(data)
    nbt_data = reader.read_root()
    
    # Display formatted data
    name = get_player_name(dat_file.stem)
    print(f"\n╔════════════════════════════════════════════════════╗")
    print(f"║ Player: {name:42s} ║")
    print(f"║ UUID: {dat_file.stem:44s} ║")
    print(f"╚════════════════════════════════════════════════════╝\n")
    
    # Key stats
    if 'Health' in nbt_data:
        print(f"Health: {nbt_data['Health']:.1f}/20.0")
    if 'foodLevel' in nbt_data:
        print(f"Food Level: {nbt_data['foodLevel']}/20")
    if 'XpLevel' in nbt_data:
        print(f"XP Level: {nbt_data['XpLevel']}")
    if 'Score' in nbt_data:
        print(f"Score: {nbt_data['Score']}")
    if 'Pos' in nbt_data:
        pos = nbt_data['Pos']
        print(f"Position: X={pos[0]:.2f}, Y={pos[1]:.2f}, Z={pos[2]:.2f}")
    if 'Dimension' in nbt_data:
        print(f"Dimension: {nbt_data['Dimension']}")
    if 'playerGameType' in nbt_data:
        modes = {0: 'Survival', 1: 'Creative', 2: 'Adventure', 3: 'Spectator'}
        print(f"Game Mode: {modes.get(nbt_data['playerGameType'], 'Unknown')}")
    
    print("\n" + "="*60 + "\n")
    
    # Full data
    for key, value in nbt_data.items():
        for line in format_value(key, value):
            print(line)
    
    print()
    return nbt_data, dat_file


def edit_player(identifier, field, value):
    """Edit a player data field"""
    result = view_player(identifier)
    if not result:
        return
    
    nbt_data, dat_file = result
    
    # Parse the field path (support nested fields like "Inventory.Count")
    keys = field.split('.')
    target = nbt_data
    for key in keys[:-1]:
        if key not in target:
            print(f"Error: Field path '{field}' not found")
            return
        target = target[key]
    
    final_key = keys[-1]
    if final_key not in target:
        print(f"Error: Field '{final_key}' not found")
        return
    
    # Convert value to appropriate type
    old_value = target[final_key]
    try:
        if isinstance(old_value, int):
            new_value = int(value)
        elif isinstance(old_value, float):
            new_value = float(value)
        elif isinstance(old_value, str):
            new_value = str(value)
        else:
            print(f"Error: Cannot edit field of type {type(old_value)}")
            return
    except ValueError:
        print(f"Error: Invalid value '{value}' for field type {type(old_value)}")
        return
    
    # Update the value
    target[final_key] = new_value
    
    # Write back to file
    writer = NBTWriter()
    nbt_bytes = writer.write_root(nbt_data)
    
    # Create backup
    backup_file = dat_file.with_suffix('.dat.bak')
    with open(dat_file, 'rb') as f:
        with open(backup_file, 'wb') as b:
            b.write(f.read())
    
    # Write new data
    with gzip.open(dat_file, 'wb') as f:
        f.write(nbt_bytes)
    
    print(f"\n✓ Updated {field}: {old_value} → {new_value}")
    print(f"✓ Backup created: {backup_file}")


def main():
    parser = argparse.ArgumentParser(
        description='View and edit Minecraft player NBT data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s list                          # List all players
  %(prog)s view Steve                    # View Steve's data
  %(prog)s view a1b2c3d4-...             # View by UUID
  %(prog)s edit Steve Health 20.0        # Set Steve's health to full
  %(prog)s edit Steve XpLevel 100        # Set XP level to 100
  %(prog)s edit Steve playerGameType 1   # Set to Creative mode
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    subparsers.add_parser('list', help='List all players')
    
    # View command
    view_parser = subparsers.add_parser('view', help='View player data')
    view_parser.add_argument('player', help='Player name or UUID')
    
    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit player data')
    edit_parser.add_argument('player', help='Player name or UUID')
    edit_parser.add_argument('field', help='Field to edit (e.g., Health, XpLevel)')
    edit_parser.add_argument('value', help='New value')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'list':
        list_players()
    elif args.command == 'view':
        view_player(args.player)
    elif args.command == 'edit':
        edit_player(args.player, args.field, args.value)


if __name__ == '__main__':
    main()
