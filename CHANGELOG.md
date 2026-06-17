# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Mist intensity / fan-speed levels (capture changing the level to map values).
- LED light control.
- Device on-board schedules (opcode 0x5716) once the field layout is mapped from
  targeted captures; HA automations against the switches are recommended meanwhile.

## [0.2.1] - 2026-06-17

### Fixed
- **Critical:** removed the invalid Bluetooth `local_name` matcher `"U5*"`. A
  wildcard in the first three characters is rejected by Home Assistant and caused
  the core `bluetooth` component to fail to set up, cascading to every
  Bluetooth-dependent integration (esphome, bluetooth_adapters, bermuda, bedjet,
  ibeacon, etc.). Remaining matchers (`"U5 Pro*"`, `"Aromadd*"`) are valid.

## [0.2.0] - 2026-06-16

### Added
- **Fan** switch (opcode 0x5703): ON payload `570310`, OFF payload `570300`,
  confirmed via state report `5303 xx`. Separate from the main Power switch.

### Changed
- Refactored the BLE device layer to handle multiple controls; the switch
  platform is now description-driven (Power + Fan).

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

[Unreleased]: https://github.com/ajachierno/Aromadd/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.1
[0.2.0]: https://github.com/ajachierno/Aromadd/releases/tag/v0.2.0
[0.1.0]: https://github.com/ajachierno/Aromadd/releases/tag/v0.1.0
