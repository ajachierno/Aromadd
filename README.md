# Aromadd Diffuser — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration to control an
**Aromadd U5 Pro** essential-oil diffuser over **Bluetooth Low Energy (BLE)**.

It exposes the diffuser as a single **switch** entity (on / off).

> [!IMPORTANT]
> Aromadd diffusers use a **proprietary BLE protocol** spoken only by the official
> Aromadd app — there is no public API or documented command set. This integration
> ships with the connection logic fully working but with **placeholder command bytes**.
> You must capture the real on/off commands from your own device **once** and paste
> them into `const.py`. See **[CAPTURE_GUIDE.md](CAPTURE_GUIDE.md)** for exact steps.
> Until then, the switch appears and connects, but won't actually toggle the diffuser.

## Features

- On/off control of the Aromadd U5 Pro over BLE
- Automatic Bluetooth discovery (the device shows up in *Settings → Devices & Services*)
- Connects, sends the command, and disconnects so the Aromadd app can still reconnect
- Optimistic state (the device does not report power state over BLE)

## Requirements

- Home Assistant **2024.8.0** or newer
- A working Bluetooth adapter recognised by Home Assistant (built-in, USB dongle,
  or an [ESPHome Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth) within
  range of the diffuser)
- The diffuser powered on and **not currently connected in the Aromadd phone app**
  (most BLE devices allow only one connection at a time)

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

After installing and restarting:

1. The diffuser is usually **auto-discovered** — look for an "Aromadd Diffuser"
   discovery card in **Settings → Devices & Services**, and click **Configure**.
2. If it isn't discovered automatically, click **+ Add Integration**, search for
   **Aromadd Diffuser**, and pick your device from the list of nearby Bluetooth
   devices (close the Aromadd phone app first so the device is connectable).

## Making it actually control the diffuser

The connection layer works out of the box, but the **command bytes are placeholders**.
To enable real control:

1. Follow **[CAPTURE_GUIDE.md](CAPTURE_GUIDE.md)** to record an Android HCI snoop log
   while toggling the diffuser on and off in the Aromadd app.
2. Read the write characteristic UUID and the on/off byte sequences out of the log.
3. Edit `custom_components/aromadd/const.py`:
   - `WRITE_CHARACTERISTIC_UUID`
   - `CMD_POWER_ON`
   - `CMD_POWER_OFF`
4. Restart Home Assistant.

If you send the snoop log to whoever set this up for you, they can fill these in for you.

## Project layout

```
custom_components/aromadd/
├── __init__.py          # setup / teardown, keeps the BLE device fresh
├── aromadd_device.py    # BLE connect → write → disconnect logic
├── config_flow.py       # discovery + manual device picker
├── const.py             # DOMAIN + the 3 values you must fill in
├── manifest.json        # integration metadata + Bluetooth matchers
├── switch.py            # the on/off switch entity
├── strings.json
└── translations/en.json
```

## Limitations & notes

- **On/off only** for now. Mist intensity, LED, and timers can be added later once
  their command bytes are captured the same way.
- State is **optimistic** — Home Assistant assumes the command worked because the
  device doesn't broadcast its power state.
- BLE range applies. Use a Bluetooth proxy if the diffuser is far from your HA host.

## Disclaimer

This is an unofficial, community integration and is not affiliated with or endorsed
by Aromadd. Use at your own risk. Licensed under the MIT License.
