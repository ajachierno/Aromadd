"""Constants for the Aromadd Diffuser integration.

================================================================================
 BLE PROTOCOL  (reverse-engineered from Aromadd U5 Pro HCI snoop logs)
================================================================================
The Aromadd app frames every command like this:

    A5 AA AC | XOR(payload) | <payload bytes> | C5 CC CA
    \_______/  \__________/   \____________/   \_______/
     header     1-byte cksum     command         footer

The checksum is a simple XOR of all payload bytes. Commands are written to the
GATT characteristic at value handle 0x0012; the device reports its state back
via notifications on the characteristic at value handle 0x0017.

Controls (opcode 0x57 = set, the device echoes opcode 0x53 = state report):

    Power   payload 57 08 01 -> ON    / 57 08 00 -> OFF   (report 53 08 xx)
    Fan     payload 57 03 10 -> ON    / 57 03 00 -> OFF   (report 53 03 xx)

State report value is treated as "on" when non-zero.
================================================================================
"""

from __future__ import annotations

DOMAIN = "aromadd"

MANUFACTURER = "Aromadd"
MODEL = "U5 Pro"

# --- BLE framing -------------------------------------------------------------
FRAME_HEADER = bytes.fromhex("a5aaac")
FRAME_FOOTER = bytes.fromhex("c5ccca")

# --- GATT (value handles observed on the U5 Pro) -----------------------------
WRITE_HANDLE = 0x0012  # characteristic the app writes commands to
NOTIFY_HANDLE = 0x0017  # characteristic the device reports state on

# --- Command payloads (inner bytes, before framing) --------------------------
PAYLOAD_POWER_ON = bytes.fromhex("570801")
PAYLOAD_POWER_OFF = bytes.fromhex("570800")
PAYLOAD_FAN_ON = bytes.fromhex("570310")
PAYLOAD_FAN_OFF = bytes.fromhex("570300")

# --- Device state-report payload prefixes (followed by an on/off byte) -------
REPORT_POWER_PREFIX = bytes.fromhex("5308")
REPORT_FAN_PREFIX = bytes.fromhex("5303")

# Logical control keys
CONTROL_POWER = "power"
CONTROL_FAN = "fan"
