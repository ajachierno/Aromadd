# Capturing the Aromadd BLE on/off commands

This integration knows **how** to connect to your Aromadd U5 Pro over Bluetooth,
but it doesn't know **what bytes** to send to turn it on or off — that protocol is
private to the Aromadd app. You only have to capture it once.

The easiest method is an **Android HCI snoop log**: Android can record every
Bluetooth packet your phone sends, and you toggle the diffuser in the Aromadd app
while it records. Then you open the log in Wireshark and read the values out.

You'll end up with three values to paste into
`custom_components/aromadd/const.py`:

| Constant in `const.py`       | What it is                                            |
|------------------------------|-------------------------------------------------------|
| `WRITE_CHARACTERISTIC_UUID`  | The GATT characteristic the app writes commands to    |
| `CMD_POWER_ON`               | The exact bytes sent when you tap **on**              |
| `CMD_POWER_OFF`              | The exact bytes sent when you tap **off**             |

---

## What you need

- An **Android** phone with the Aromadd app installed and paired to the diffuser
  (iPhone can't export a snoop log easily — borrow an Android phone if needed).
- A computer with **[Wireshark](https://www.wireshark.org/)** installed (free).
- The diffuser powered on and within Bluetooth range of the phone.

---

## Step 1 — Enable Developer Options on the phone

1. Open **Settings → About phone**.
2. Tap **Build number** seven times until it says "You are now a developer".
3. Go back to **Settings → System → Developer options**.

## Step 2 — Turn on Bluetooth HCI snoop log

1. In **Developer options**, find **Enable Bluetooth HCI snoop log**.
2. Set it to **Enabled** (on some phones the options are *Disabled / Filtered / Full*
   — choose **Full** / **Enabled**).
3. **Toggle Bluetooth off and back on** (or reboot) so logging actually starts.

## Step 3 — Record a clean on/off sequence

Do this slowly and deliberately so the log is easy to read:

1. Open the **Aromadd app** and connect to the diffuser.
2. Wait ~5 seconds (so the connect chatter is separated from your taps).
3. Tap **ON**. Wait ~5 seconds. Confirm the diffuser actually turned on.
4. Tap **OFF**. Wait ~5 seconds. Confirm it turned off.
5. Close the app.

> Tip: do *only* on then off, nothing else. Avoid changing mist level, light, or
> timers during the capture — that keeps the log small and unambiguous.

## Step 4 — Get the log off the phone

The log file is usually at one of:

- `/sdcard/btsnoop_hci.log`
- `/sdcard/Android/data/btsnoop_hci.log`
- Inside a **bug report**: run *Developer options → Take bug report → Full report*,
  then find `btsnoop_hci.log` (or `FS/data/misc/bluetooth/logs/btsnoop_hci.log`)
  inside the generated zip.

Copy that file to your computer. If your phone has no obvious file, the bug-report
method always works.

## Step 5 — Read the values in Wireshark

1. Open `btsnoop_hci.log` in **Wireshark**.
2. In the filter bar, type:
   ```
   btatt.opcode == 0x52 || btatt.opcode == 0x12
   ```
   (`0x52` = Write Command, `0x12` = Write Request — the app uses one of these to
   send commands.) Press Enter.
3. You should see a small number of packets lined up with your ON and OFF taps
   (use the time column / ordering). Click the packet that lines up with your **ON** tap.
4. In the packet details pane, expand **Bluetooth Attribute Protocol**:
   - **Handle / UUID** → this is your write characteristic. If a 128-bit UUID is
     shown (e.g. `0000ffe1-0000-1000-8000-00805f9b34fb`), that's
     `WRITE_CHARACTERISTIC_UUID`. (If only a 16-bit handle shows, look at an earlier
     "Read By Type Response" / service-discovery packet, or right-click → the UUID is
     usually listed there.)
   - **Value** → the bytes are your command. Example: `a1 01 01 00 5c`.
5. Repeat for the packet aligned with your **OFF** tap to get the off bytes.

## Step 6 — Put the values into `const.py`

Edit `custom_components/aromadd/const.py`. Convert the byte values to a hex string
(no spaces) and use `bytes.fromhex(...)`:

```python
WRITE_CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"  # your UUID

CMD_POWER_ON  = bytes.fromhex("a1010100 5c".replace(" ", ""))  # your ON bytes
CMD_POWER_OFF = bytes.fromhex("a1010000 5b".replace(" ", ""))  # your OFF bytes
```

(Simplest is just `bytes.fromhex("a10101005c")` with no spaces.)

Then **restart Home Assistant**. The switch will now actually control the diffuser.

---

## Don't want to do the Wireshark part?

Just complete **Steps 1–4** and send the `btsnoop_hci.log` file to whoever set up
this integration for you. The three values can be extracted from the log directly.

## Troubleshooting

- **No packets match the filter:** the app may use Write Request only — try the
  filter `btatt` alone and look for "Sent Write" rows around your taps.
- **Multiple identical packets:** the app sometimes sends keep-alives. The command
  is the packet whose timing matches your tap and whose value *changes* between
  on and off.
- **UUID looks like `0xffe1` (16-bit):** expand it to the full
  `0000ffe1-0000-1000-8000-00805f9b34fb` form when pasting into `const.py`.
- **Can't connect from HA after editing:** make sure the Aromadd phone app is fully
  closed — the diffuser usually allows only one BLE connection at a time.

---

## Appendix — decoded opcodes & adding more controls

All controls share the same frame (`A5AAAC | XOR | payload | C5CCCA`). Known opcodes:

| Opcode (set) | Meaning | Values seen | State report |
|--------------|---------|-------------|--------------|
| `57 08`      | Power   | `01` on / `00` off | `53 08 xx` |
| `57 03`      | Fan     | `10` on / `00` off | `53 03 xx` |
| `57 16`      | Schedule (on-board timer) | variable-length record list | `53 09 …` summary |
| `57 17`      | Set clock | `YYYY(2) MM DD HH MM SS 02` | — |
| `52 xx`      | Query (read settings/info) | — | `52 xx …` |

To add a new control (e.g. fan speed or LED), capture a snoop log while changing
**only that one setting** to a few **known** values, then read the `57 xx …` write
payloads. Send me the log and I can wire it in.

### About schedules (`0x57 16`)

The schedule write is captured, but its field layout (start time, duration,
day-of-week mask, level) sits in repeating ~9-byte records and can't be mapped
reliably from a single capture of an unknown schedule. To decode it safely, capture
logs where you set **one** schedule at a time with known values, e.g.:

1. A schedule that turns on at **08:00** for **30 minutes**, weekdays only.
2. Then change just the time to **09:15** and re-capture.
3. Then change just the duration to **60 minutes** and re-capture.

Comparing those isolates which bytes encode each field. In the meantime, the
recommended approach is to schedule the Home Assistant `switch` entities with HA
automations, which is more flexible than the device's built-in timer.
