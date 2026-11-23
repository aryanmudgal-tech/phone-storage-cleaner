#!/usr/bin/env python3
"""Check that the iPhone is reachable over USB and show its storage summary."""
import sys

from mobiledevice import MD, Device, usb_devices


def gb(n):
    return f"{n / 1e9:.1f} GB"


def main():
    handles = usb_devices()
    if not handles:
        sys.exit("No iPhone found over USB. Plug it in and unlock it.")
    for handle in handles:
        try:
            with Device(handle) as device:
                print("Name:      ", device.value("DeviceName"))
                print("Model:     ", device.value("ProductType"))
                print("iOS:       ", device.value("ProductVersion"))
                usage = device.value(domain="com.apple.disk_usage") or {}
                for key in sorted(usage):
                    value = usage[key]
                    if isinstance(value, int):
                        print(f"  {key:28}", gb(value))
        except PermissionError as error:
            print(f"Phone found but {error}. Unlock it and tap Trust when asked.")
            code = MD.AMDevicePair(handle)
            print(f"Pair request sent (0x{code & 0xFFFFFFFF:08x}).")


if __name__ == "__main__":
    main()
