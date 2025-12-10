#!/usr/bin/env python3
"""
Interactive Minecraft NBT Player Data Tool
"""

import sys
import json
from pathlib import Path

# Import the library
sys.path.insert(0, str(Path(__file__).parent))
import nbt_lib as nbt


def clear_screen():
    """Clear the terminal screen"""
    print("\033[2J\033[H", end='')


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def select_player():
    """Interactive player selection"""
    players = nbt.list_players()
    
    if not players:
        print("No player data found!")
        return None
    
    print_header("SELECT PLAYER")
    
    for i, (name, uuid, _) in enumerate(players, 1):
        print(f"  {i}. {name:20s} ({uuid})")
    
    print(f"\n  0. Exit")
    
    while True:
        try:
            choice = input("\nSelection: ").strip()
            if not choice:
                continue
            
            choice = int(choice)
            if choice == 0:
                return None
            if 1 <= choice <= len(players):
                return players[choice - 1][1]  # Return UUID
            
            print("Invalid selection!")
        except ValueError:
            print("Please enter a number!")
        except KeyboardInterrupt:
            return None


def display_main_stats(data, player_name):
    """Display main player statistics"""
    clear_screen()
    print_header(f"PLAYER: {player_name}")
    
    print("MAIN STATS:")
    print("-" * 60)
    
    if 'Health' in data:
        print(f"  Health:       {data['Health']:.1f} / 20.0")
    if 'foodLevel' in data:
        print(f"  Food:         {data['foodLevel']} / 20")
    if 'XpLevel' in data:
        print(f"  XP Level:     {data['XpLevel']}")
    if 'Pos' in data:
        pos = data['Pos']
        print(f"  Position:     X={pos[0]:.2f}, Y={pos[1]:.2f}, Z={pos[2]:.2f}")
    if 'Dimension' in data:
        print(f"  Dimension:    {data['Dimension']}")
    if 'playerGameType' in data:
        modes = {0: 'Survival', 1: 'Creative', 2: 'Adventure', 3: 'Spectator'}
        print(f"  Game Mode:    {modes.get(data['playerGameType'], 'Unknown')}")
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View field")
    print("  [w]rite  - Edit field")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def display_secondary_stats(data, player_name):
    """Display secondary/extra statistics"""
    clear_screen()
    print_header(f"PLAYER: {player_name} - EXTRA STATS")
    
    print("SECONDARY STATS:")
    print("-" * 60)
    
    if 'AbsorptionAmount' in data:
        print(f"  Absorption:      {data['AbsorptionAmount']:.1f}")
    if 'foodSaturationLevel' in data:
        print(f"  Saturation:      {data['foodSaturationLevel']:.1f}")
    if 'Rotation' in data:
        rot = data['Rotation']
        print(f"  Rotation:        Yaw={rot[0]:.2f}°, Pitch={rot[1]:.2f}°")
    if 'Score' in data:
        print(f"  Score:           {data['Score']}")
    if 'SelectedItemSlot' in data:
        print(f"  Selected Slot:   {data['SelectedItemSlot']}")
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View field")
    print("  [w]rite  - Edit field")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def display_inventory(data, player_name):
    """Display player inventory"""
    clear_screen()
    print_header(f"PLAYER: {player_name} - INVENTORY")
    
    inventory = data.get('Inventory', [])
    
    if not inventory:
        print("  Inventory is empty!\n")
    else:
        print(f"  Total items: {len(inventory)}\n")
        
        for i, item in enumerate(inventory):
            slot = item.get('Slot', -1)
            item_id = item.get('id', 'unknown')
            count = item.get('count', 1)
            
            print(f"  [{i}] Slot {slot:2d}: {count:2d}x {item_id}")
            
            if 'components' in item:
                comps = item['components']
                if 'minecraft:custom_name' in comps:
                    print(f"       └─ Name: {comps['minecraft:custom_name']}")
                if 'minecraft:enchantments' in comps:
                    print(f"       └─ Enchanted")
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View item details")
    print("  [g]ive   - Give item (using /give command)")
    print("  [c]lear  - Clear inventory")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def display_enderchest(data, player_name):
    """Display player ender chest"""
    clear_screen()
    print_header(f"PLAYER: {player_name} - ENDER CHEST")
    
    enderchest = data.get('EnderItems', [])
    
    if not enderchest:
        print("  Ender chest is empty!\n")
    else:
        print(f"  Total items: {len(enderchest)}\n")
        
        for i, item in enumerate(enderchest):
            slot = item.get('Slot', -1)
            item_id = item.get('id', 'unknown')
            count = item.get('count', 1)
            
            print(f"  [{i}] Slot {slot:2d}: {count:2d}x {item_id}")
            
            if 'components' in item:
                comps = item['components']
                if 'minecraft:custom_name' in comps:
                    print(f"       └─ Name: {comps['minecraft:custom_name']}")
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View item details")
    print("  [g]ive   - Give item (using /give command)")
    print("  [c]lear  - Clear ender chest")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def display_attributes(data, player_name):
    """Display player attributes"""
    clear_screen()
    print_header(f"PLAYER: {player_name} - ATTRIBUTES")
    
    attributes = data.get('attributes', [])
    
    if not attributes:
        print("  No custom attributes found.\n")
    else:
        for attr in attributes:
            name = attr.get('Name', 'unknown')
            base = attr.get('Base', 0)
            print(f"  {name}: {base}")
            
            if 'Modifiers' in attr:
                for mod in attr['Modifiers']:
                    mod_name = mod.get('Name', 'unknown')
                    amount = mod.get('Amount', 0)
                    print(f"    └─ {mod_name}: {amount}")
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View full attributes")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def display_other(data, player_name):
    """Display all other data"""
    clear_screen()
    print_header(f"PLAYER: {player_name} - ALL DATA")
    
    # Skip the major categories
    skip_keys = {'Health', 'foodLevel', 'XpLevel', 'Pos', 'Dimension', 'playerGameType',
                 'AbsorptionAmount', 'foodSaturationLevel', 'Rotation', 'Score', 'SelectedItemSlot',
                 'Inventory', 'EnderItems', 'attributes'}
    
    print("OTHER DATA:")
    print("-" * 60)
    
    for key, value in data.items():
        if key not in skip_keys:
            for line in nbt.format_value(key, value):
                print(line)
    
    print("\n" + "=" * 60)
    print("\nActions:")
    print("  [r]ead   - View specific field")
    print("  [w]rite  - Edit field")
    print("  [b]ack   - Return to menu")
    
    return input("\nChoice: ").strip().lower()


def handle_read(data):
    """Handle reading a specific field"""
    field = input("\nEnter field name: ").strip()
    
    if field in data:
        print(f"\n{field}:")
        for line in nbt.format_value(field, data[field]):
            print(line)
    else:
        print(f"\nField '{field}' not found!")
    
    input("\nPress Enter to continue...")


def handle_write(data, dat_file):
    """Handle writing a field"""
    field = input("\nEnter field name: ").strip()
    
    if field not in data:
        print(f"\nField '{field}' not found!")
        input("\nPress Enter to continue...")
        return
    
    old_value = data[field]
    print(f"\nCurrent value: {old_value}")
    print(f"Type: {type(old_value).__name__}")
    
    new_value_str = input("\nEnter new value: ").strip()
    
    try:
        if isinstance(old_value, int):
            new_value = int(new_value_str)
        elif isinstance(old_value, float):
            new_value = float(new_value_str)
        elif isinstance(old_value, str):
            new_value = new_value_str
        else:
            print(f"\nCannot edit field of type {type(old_value).__name__}")
            input("\nPress Enter to continue...")
            return
        
        data[field] = new_value
        backup = nbt.save_player_data(data, dat_file)
        
        print(f"\n✓ Updated {field}: {old_value} → {new_value}")
        print(f"✓ Backup: {backup}")
    except ValueError as e:
        print(f"\nError: {e}")
    
    input("\nPress Enter to continue...")


def handle_give_item(data, dat_file):
    """Handle giving an item using /give command format"""
    print("\nEnter /give command (e.g., give @a diamond_sword[...])")
    print("Or just the item spec (e.g., diamond_sword[...])")
    give_cmd = input("\nCommand: ").strip()
    
    if not give_cmd:
        return
    
    try:
        item_id, count, components = nbt.parse_give_command(give_cmd)
        
        print(f"\nParsed item:")
        print(f"  ID: {item_id}")
        print(f"  Count: {count}")
        if components:
            print(f"  Components: {json.dumps(components, indent=2)}")
        
        confirm = input("\nAdd this item? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        # Create item
        item = {
            'id': item_id,
            'count': count
        }
        
        if components:
            item['components'] = components
        
        # Find empty slot
        inventory = data.get('Inventory', [])
        used_slots = {item.get('Slot', -1) for item in inventory}
        
        empty_slot = None
        for slot in range(36):
            if slot not in used_slots:
                empty_slot = slot
                break
        
        if empty_slot is None:
            print("\nError: Inventory is full!")
            input("\nPress Enter to continue...")
            return
        
        item['Slot'] = empty_slot
        inventory.append(item)
        data['Inventory'] = inventory
        
        backup = nbt.save_player_data(data, dat_file)
        
        print(f"\n✓ Gave {count}x {item_id} (slot {empty_slot})")
        print(f"✓ Backup: {backup}")
        
    except Exception as e:
        print(f"\nError parsing command: {e}")
    
    input("\nPress Enter to continue...")


def handle_clear_inventory(data, dat_file):
    """Clear player inventory"""
    confirm = input("\nAre you sure you want to clear inventory? (yes/no): ").strip().lower()
    if confirm == 'yes':
        data['Inventory'] = []
        backup = nbt.save_player_data(data, dat_file)
        print(f"\n✓ Inventory cleared")
        print(f"✓ Backup: {backup}")
        input("\nPress Enter to continue...")


def handle_clear_enderchest(data, dat_file):
    """Clear player ender chest"""
    confirm = input("\nAre you sure you want to clear ender chest? (yes/no): ").strip().lower()
    if confirm == 'yes':
        data['EnderItems'] = []
        backup = nbt.save_player_data(data, dat_file)
        print(f"\n✓ Ender chest cleared")
        print(f"✓ Backup: {backup}")
        input("\nPress Enter to continue...")


def player_menu(uuid):
    """Main menu for a selected player"""
    while True:
        # Reload data each time to show updates
        data, dat_file, player_name = nbt.load_player_data(uuid)
        
        if data is None:
            print("Error loading player data!")
            return
        
        clear_screen()
        print_header(f"SELECTED PLAYER: {player_name}")
        
        print("SECTIONS:")
        print("  1. Main Stats")
        print("  2. Secondary Stats")
        print("  3. Inventory")
        print("  4. Ender Chest")
        print("  5. Attributes")
        print("  6. Other Data")
        print("\n  0. Back to player selection")
        
        try:
            choice = input("\nSelection: ").strip()
            
            if choice == '0':
                return
            elif choice == '1':
                action = display_main_stats(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'w':
                    handle_write(data, dat_file)
                elif action == 'b':
                    continue
            elif choice == '2':
                action = display_secondary_stats(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'w':
                    handle_write(data, dat_file)
                elif action == 'b':
                    continue
            elif choice == '3':
                action = display_inventory(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'g':
                    handle_give_item(data, dat_file)
                elif action == 'c':
                    handle_clear_inventory(data, dat_file)
                elif action == 'b':
                    continue
            elif choice == '4':
                action = display_enderchest(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'g':
                    handle_give_item(data, dat_file)
                elif action == 'c':
                    handle_clear_enderchest(data, dat_file)
                elif action == 'b':
                    continue
            elif choice == '5':
                action = display_attributes(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'b':
                    continue
            elif choice == '6':
                action = display_other(data, player_name)
                if action == 'r':
                    handle_read(data)
                elif action == 'w':
                    handle_write(data, dat_file)
                elif action == 'b':
                    continue
        
        except KeyboardInterrupt:
            return


def main():
    """Main application loop"""
    try:
        while True:
            uuid = select_player()
            if uuid is None:
                print("\nGoodbye!")
                break
            
            player_menu(uuid)
    
    except KeyboardInterrupt:
        print("\n\nGoodbye!")


if __name__ == '__main__':
    main()
