# Aromadd Diffuser — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration to control an
**Aromadd U5 Pro** essential-oil diffuser over **Bluetooth Low Energy (BLE)**.

It exposes the diffuser as a single **switch** entity (on / off).

> [!NOTE]
> The BLE protocol was reverse-engineered from a real U5 Pro HCI snoop log, so
> **on/off works out of the box** — no extra configuration needed. Each command is
> confirmed by the device's own state-report notification rather than just assumed.
> See [`CAPTURE_GUIDE.md`](CAPTURE_GUIDE.md) if you want to capture additional
> commands (mist level, LED, timers) the same way.

## Features

- Confirmed on/off control of the Aromadd U5 Pro over BLE
- Automatic Bluetooth discovery (the device shows up in *Settings → Devices & Services*)
- Connects, sends the command, reads back the device's state report, then disconnects
  so the Aromadd phone app can still reconnect

## How it works (protocol)

Commands are framed as:

```
A5 AA AC | XOR(payload) | <payload> | C5 CC CA
```

- Written to the GATT characteristic at value handle `0x0012`
- The device reports state via notifications on value handle `0x0017`

| Action | Payload     | Full frame                   |
|--------|-------------|------------------------------|
| ON     | `57 08 01`  | `a5aaac5e570801c5ccca`       |
| OFF    | `57 08 00`  | `a5aaac5f570800c5ccca`       |

The diffuser replies with `53 08 01` (on) / `53 08 00` (off), which the integration
uses to confirm the real power state.

## Requirements

- Home Assistant **2024.8.0** or newer
- A Bluetooth adapter recognised by Home Assistant (built-in, USB dongle, or an
  [ESPHome Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth) in range of
  the diffuser)
- The diffuser powered on and **not currently connected in the Aromadd phone app**
  (it allows only one BLE connection at a time)

## Installation

### Option A — HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/ajachierno/Aromadd` as an **Integration**.
3. Search for **Aromadd Diffuser** in HACS and install it.
4. Restart Home Assistant.

### Option B — Manual

1. Copy the `custom_components/aromadd` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. The diffuser is usually **auto-discovered** — look for an "Aromadd Diffuser"
   discovery card in **Settings → Devices & Services** and click **Configure**.
2. If it isn't discovered automatically, click **+ Add Integration**, search for
   **Aromadd Diffuser**, and pick your device from the list of nearby Bluetooth
   devices (close the Aromadd phone app first so the device is connectable).

That's it — a switch entity appears that turns your diffuser on and off.

## Project layout

```
custom_components/aromadd/
├── __init__.py          # setup / teardown, keeps the BLE device fresh
├── aromadd_device.py    # BLE connect → write → confirm → disconnect logic
├── config_flow.py       # discovery + manual device picker
├── const.py             # domain + the decoded BLE protocol constants
├── manifest.json        # integration metadata + Bluetooth matchers
├── switch.py            # the on/off switch entity
├── strings.json
└── translations/en.json
```

## Limitations & notes

- **On/off only** for now. Mist intensity, LED, and timers use the same framing and
  can be added once their payloads are captured (see `CAPTURE_GUIDE.md`).
- State is confirmed at the moment a command is sent. Changes made with the physical
  button or the phone app while HA isn't connected are not pushed back to HA.
- BLE range applies. Use a Bluetooth proxy if the diffuser is far from your HA host.
- Handles (`0x0012` / `0x0017`) are taken from the U5 Pro. If a future firmware moves
  them, update `WRITE_HANDLE` / `NOTIFY_HANDLE` in `const.py`.

## Disclaimer

Unofficial community integration, not affiliated with or endorsed by Aromadd.
Use at your own risk. Licensed under the MIT License.
