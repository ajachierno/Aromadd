"""Constants for the Aromadd Diffuser integration.

================================================================================
 BLE PROTOCOL  (reverse-engineered from an Aromadd U5 Pro HCI snoop log)
================================================================================
The Aromadd app frames every command like this:

    A5 AA AC | XOR(payload) | <payload bytes> | C5 CC CA
    \_______/  \__________/   \____________/   \_______/
     header     1-byte cksum     command         footer

The checksum is a simple XOR of all payload bytes. Commands are written to the
GATT characteristic at value handle 0x0012; the device reports its state back
via notifications on the characteristic at value handle 0x0017.

Power control:
    payload 57 08 01  -> ON     (full frame a5aaac5e570801c5ccca)
    payload 57 08 00  -> OFF    (full frame a5aaac5f570800c5ccca)
The device replies with a state report payload 53 08 01 (on) / 53 08 00 (off),
which this integration uses to confirm the real power state.
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

# --- Device state report (payload prefix + on/off byte) ----------------------
REPORT_POWER_PREFIX = bytes.fromhex("5308")
