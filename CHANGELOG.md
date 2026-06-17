# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Mist intensity control (same frame format, payload to be captured).
- LED light control.
- Run-time / timer modes (1H / 3H / 6H / ON).

## [0.1.0] - 2026-06-16

First public release. Bluetooth LE control of the Aromadd U5 Pro diffuser.

### Added
- `switch` entity for on/off control of the Aromadd U5 Pro.
- Device-confirmed state: each command is verified against the diffuser's own
  state-report notification (`53 08 01` / `53 08 00`) rather than assumed.
- Automatic Bluetooth discovery plus a manual device-picker config flow.
- Connect → write → confirm → disconnect handling so the official Aromadd app can
  still reconnect.
- Reverse-engineered BLE protocol from an HCI snoop log:
  frame `A5 AA AC | XOR(payload) | <payload> | C5 CC CA`; commands written to GATT
  handle `0x0012`, state reported via notifications on handle `0x0017`.
- HACS packaging: `hacs.json`, brand assets, and a `validate.yaml` workflow running
  the HACS Action and hassfest.

### Known limitations
- On/off only; mist level, LED, and timers are not yet implemented.
- Changes made with the physical button or phone app while Home Assistant is not
  connected are not pushed back to HA.

[Unreleased]: https://github.com/ajachierno/Aromadd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ajachierno/Aromadd/releases/tag/v0.1.0
