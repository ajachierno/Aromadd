"""Constants for the Aromadd Diffuser integration.

================================================================================
 BLE PROTOCOL CONFIGURATION
================================================================================
The Aromadd U5 Pro is controlled over Bluetooth Low Energy (BLE) using a
proprietary protocol that the official Aromadd app speaks. Anthropic's Claude
could not invent these values, so the three constants below are PLACEHOLDERS.

To make the integration actually toggle the device you must replace them with
the real values captured from the device. See CAPTURE_GUIDE.md in the repo root
for exact, step-by-step instructions on producing an HCI snoop log and reading
the values out of it with Wireshark.

You need to discover:
  1. WRITE_CHARACTERISTIC_UUID  -> the GATT characteristic the app writes to.
  2. CMD_POWER_ON               -> the exact bytes sent when you tap "on".
  3. CMD_POWER_OFF              -> the exact bytes sent when you tap "off".

Until the placeholders are replaced, the integration will install, the switch
entity will appear, and the BLE connection will be attempted, but the bytes
sent will be meaningless to the diffuser. A warning is logged on every send.
================================================================================
"""

from __future__ import annotations

DOMAIN = "aromadd"

MANUFACTURER = "Aromadd"
MODEL = "U5 Pro"

# --- REPLACE THESE THREE VALUES (see CAPTURE_GUIDE.md) -----------------------

# GATT characteristic UUID the Aromadd app writes commands to.
# 0000ffe1-... is a common module default (HM-10 style) used here only as a
# best-guess placeholder. Confirm the real UUID from your snoop log.
WRITE_CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Raw command payloads. These are placeholders (a single 0x00 byte) and are
# intentionally identical so it is obvious they have not been configured yet.
# Replace with the real captured byte sequences, e.g.
#   CMD_POWER_ON = bytes.fromhex("a10101005c")
CMD_POWER_ON: bytes = bytes.fromhex("00")
CMD_POWER_OFF: bytes = bytes.fromhex("00")

# -----------------------------------------------------------------------------

# Set automatically: True once the placeholders above have been edited.
COMMANDS_CONFIGURED: bool = (
    CMD_POWER_ON != bytes.fromhex("00") or CMD_POWER_OFF != bytes.fromhex("00")
)
