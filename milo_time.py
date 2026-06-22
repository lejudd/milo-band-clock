import asyncio
from datetime import datetime
import sys
from bleak import BleakClient, BleakScanner

# Explicit UUIDs from your original script
WRITE_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff7-0000-1000-8000-00805f9b34fb"

def notification_handler(sender, data):
    print(f"[Band Response] {data.hex().upper()}")

async def select_milo_device():
    """Scans for BLE devices and prompts the user to select their MILO tracker."""
    print("Searching for MILO trackers and nearby BLE devices... (Scanning for 5 seconds)")
    
    devices = await BleakScanner.discover(timeout=5.0)
    if not devices:
        print("No Bluetooth devices found. Make sure Bluetooth is turned on.")
        sys.exit(1)
        
    milo_devices = []
    other_devices = []
    
    for d in devices:
        name = d.name if d.name else "Unknown Device"
        if "milo" in name.lower():
            milo_devices.append(d)
        else:
            other_devices.append(d)
            
    all_selectable = milo_devices + other_devices
    
    print("\n--- Discovered Bluetooth Devices ---")
    for index, d in enumerate(all_selectable):
        prefix = "[MILO MATCH] " if d in milo_devices else ""
        print(f"{index + 1}: {prefix}{d.name} ({d.address})")
    print("------------------------------------\n")
    
    while True:
        try:
            choice = input("Enter the number of your MILO device: ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(all_selectable):
                selected_device = all_selectable[choice_idx]
                print(f"\nSelected: {selected_device.name} [{selected_device.address}]")
                return selected_device.address
            else:
                print(f"Please enter a number between 1 and {len(all_selectable)}.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

def generate_milo_time_packet():
    """Generates the exact 16-byte BCD time packet from your original script."""
    # Get fresh computer local time at the exact moment of execution
    now = datetime.now()
    print(f"Generating precise time payload: {now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    
    # Extract structural digits matching your Java getTime() pattern
    year = now.year - 2000
    month = now.month
    day = now.day
    hour = now.hour
    minute = now.minute
    second = now.second

    # Initialize empty 16-byte layout array
    packet = [0] * 16
    packet[0] = 1 # TYPE_SET_DATE_TIME_CODE is explicitly 1
    
    # Apply your math translation: time[i3] + ((time[i3] / 10) * 6)
    packet[1] = year + (year // 10) * 6
    packet[2] = month + (month // 10) * 6
    packet[3] = day + (day // 10) * 6
    packet[4] = hour + (hour // 10) * 6
    packet[5] = minute + (minute // 10) * 6
    packet[6] = second + (second // 10) * 6

    # Calculate 8-bit rolling summation checksum matching (b & UByte.MAX_VALUE)
    checksum = sum(packet[:15]) & 0xFF
    packet[15] = checksum

    return bytes(packet)

async def main():
    # 1. Dynamically select device address via BLE list
    device_address = await select_milo_device()
    
    # 2. Establish connection to the selected tracker
    print(f"Connecting to Milo Band at {device_address}...")
    async with BleakClient(device_address) as client:
        if not client.is_connected:
            print("Link failed.")
            return

        # Explicitly subscribe to notification channels first
        await client.start_notify(NOTIFY_UUID, notification_handler)
        
        # Mandatory wake handshake (0x01)
        print("Sending initial wake handshake...")
        wake_handshake = bytes([0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x01])
        await client.write_gatt_char(WRITE_UUID, wake_handshake, response=False)
        await asyncio.sleep(1.0)

        # 3. Generate and transmit the true math-mapped time packet right when ready
        time_packet = generate_milo_time_packet()
        print(f"Sending compiled time payload: {time_packet.hex().upper()}")
        await client.write_gatt_char(WRITE_UUID, time_packet, response=False)
        
        # Keep connection open long enough for the band's screen memory block to flip
        print("Waiting for clock confirmation...")
        await asyncio.sleep(3.0)

        await client.stop_notify(NOTIFY_UUID)
        print("Sync execution complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
