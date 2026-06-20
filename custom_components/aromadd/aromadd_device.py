"""BLE communication layer for the Aromadd Diffuser.

Resolves the control characteristics from the live GATT table, sends a framed
command, waits for the device's state-report notification to confirm, then
disconnects so the official Aromadd app can reconnect.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .const import (
    CONTROL_FAN,
    CONTROL_POWER,
    FRAME_FOOTER,
    FRAME_HEADER,
    PAYLOAD_FAN_OFF,
    PAYLOAD_FAN_ON,
    PAYLOAD_POWER_OFF,
    PAYLOAD_POWER_ON,
    REPORT_FAN_PREFIX,
    REPORT_POWER_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

# Per-write wait for the device to confirm via notification.
CONFIRM_TIMEOUT = 2.5

_SIG_BASE_SUFFIX = "-0000-1000-8000-00805f9b34fb"

_COMMANDS: dict[str, tuple[bytes, bytes, bytes]] = {
    CONTROL_POWER: (PAYLOAD_POWER_ON, PAYLOAD_POWER_OFF, REPORT_POWER_PREFIX),
    CONTROL_FAN: (PAYLOAD_FAN_ON, PAYLOAD_FAN_OFF, REPORT_FAN_PREFIX),
}

_REPORT_PREFIXES: dict[bytes, str] = {
    REPORT_POWER_PREFIX: CONTROL_POWER,
    REPORT_FAN_PREFIX: CONTROL_FAN,
}


def build_frame(payload: bytes) -> bytes:
    """Wrap a payload: header + XOR checksum + payload + footer."""
    checksum = 0
    for byte in payload:
        checksum ^= byte
    return FRAME_HEADER + bytes([checksum]) + payload + FRAME_FOOTER


def _parse_report(data: bytes) -> tuple[str, bool] | None:
    """Return (control_key, is_on) for a recognised state report, else None."""
    if len(data) < 6 or data[:3] != FRAME_HEADER or data[-3:] != FRAME_FOOTER:
        return None
    payload = data[4:-3]
    for prefix, control in _REPORT_PREFIXES.items():
        if payload[: len(prefix)] == prefix and len(payload) > len(prefix):
            return control, bool(payload[len(prefix)])
    return None


def _short_uuid(uuid: str | None) -> int | None:
    """Return the 16-bit value of a standard-base UUID, else None (128-bit custom)."""
    if not uuid:
        return None
    u = uuid.lower()
    if u.endswith(_SIG_BASE_SUFFIX):
        try:
            return int(u[:8], 16) & 0xFFFF
        except ValueError:
            return None
    return None  # fully custom 128-bit


def _is_vendor(uuid: str | None) -> bool:
    """True if a characteristic UUID is vendor-specific.

    Covers fully custom 128-bit UUIDs and the 0xFFxx proprietary range (e.g. the
    FFF0 service's FFF1..FFF4 characteristics) expressed in standard base form.
    """
    short = _short_uuid(uuid)
    if short is None:
        return True  # 128-bit custom
    return short >= 0xFF00


def _control_candidates(
    client: BleakClient,
) -> tuple[list[BleakGATTCharacteristic], list[BleakGATTCharacteristic]]:
    """Return (write_candidates, notify_candidates), vendor characteristics first."""
    writable: list[BleakGATTCharacteristic] = []
    notifiable: list[BleakGATTCharacteristic] = []
    for service in client.services:
        for char in service.characteristics:
            props = char.properties
            if "write" in props or "write-without-response" in props:
                writable.append(char)
            if "notify" in props or "indicate" in props:
                notifiable.append(char)

    def _rank(chars: list[BleakGATTCharacteristic]) -> list[BleakGATTCharacteristic]:
        vendor = [c for c in chars if _is_vendor(c.uuid)]
        vendor.sort(key=lambda c: (_short_uuid(c.uuid) or 0x10000))
        # If vendor (0xFFxx / custom) characteristics exist, use only those.
        # Standard GATT characteristics like Service Changed (0x2a05) can hang
        # for ~30s on subscribe and are never the diffuser's control channel.
        if vendor:
            return vendor
        return chars

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "GATT writable=%s notifiable=%s",
            [(c.uuid, c.handle) for c in writable],
            [(c.uuid, c.handle) for c in notifiable],
        )

    return _rank(writable), _rank(notifiable)


class AromaddDevice:
    """Manage BLE control of a single Aromadd diffuser."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialise with the discovered BLEDevice."""
        self._ble_device = ble_device
        self._lock = asyncio.Lock()
        self._states: dict[str, bool | None] = {
            CONTROL_POWER: None,
            CONTROL_FAN: None,
        }
        self._callbacks: list[Callable[[], None]] = []
        # Cache the write characteristic that actually worked, to skip retries.
        self._known_write_uuid: str | None = None

    @property
    def address(self) -> str:
        """Return the BLE MAC address of the device."""
        return self._ble_device.address

    def state(self, control: str) -> bool | None:
        """Return the last known state for a control (None until first command)."""
        return self._states.get(control)

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the cached BLEDevice (called when HA rediscovers it)."""
        self._ble_device = ble_device

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for state changes; returns an unregister func."""
        self._callbacks.append(callback)

        def _unregister() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return _unregister

    def _notify_listeners(self) -> None:
        for callback in self._callbacks:
            callback()

    async def async_set_power(self, turn_on: bool) -> None:
        """Turn the diffuser on or off."""
        await self._set(CONTROL_POWER, turn_on)

    async def async_set_fan(self, turn_on: bool) -> None:
        """Turn the fan on or off."""
        await self._set(CONTROL_FAN, turn_on)

    async def async_disconnect(self) -> None:
        """No persistent connection is held; nothing to tear down."""
        return

    async def _set(self, control: str, turn_on: bool) -> None:
        """Connect, send the command (auto-finding the right characteristic), confirm."""
        on_payload, off_payload, _ = _COMMANDS[control]
        frame = build_frame(on_payload if turn_on else off_payload)
        confirmed = asyncio.Event()

        def _on_notify(_char: BleakGATTCharacteristic, data: bytearray) -> None:
            parsed = _parse_report(bytes(data))
            if parsed is None:
                return
            reported_control, is_on = parsed
            self._states[reported_control] = is_on
            if reported_control == control:
                confirmed.set()

        async with self._lock:
            _LOGGER.debug(
                "Connecting to Aromadd %s to set %s %s",
                self.address, control, "on" if turn_on else "off",
            )
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._ble_device.name or self._ble_device.address,
            )
            subscribed: list[BleakGATTCharacteristic] = []
            try:
                write_chars, notify_chars = _control_candidates(client)
                if not write_chars:
                    raise RuntimeError("No writable characteristic found on device")

                for ch in notify_chars:
                    try:
                        await client.start_notify(ch, _on_notify)
                        subscribed.append(ch)
                    except Exception as err:  # noqa: BLE001 - best-effort
                        _LOGGER.debug("notify subscribe failed on %s: %s", ch.uuid, err)

                # Prefer a previously-successful write characteristic.
                ordered = sorted(
                    write_chars, key=lambda c: c.uuid != self._known_write_uuid
                )

                for ch in ordered:
                    confirmed.clear()
                    try:
                        await client.write_gatt_char(ch, frame, response=True)
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("write failed on %s: %s", ch.uuid, err)
                        continue
                    _LOGGER.debug("Wrote %s to %s", frame.hex(), ch.uuid)
                    try:
                        await asyncio.wait_for(confirmed.wait(), timeout=CONFIRM_TIMEOUT)
                        self._known_write_uuid = ch.uuid
                        _LOGGER.debug(
                            "Confirmed %s via %s -> %s",
                            control, ch.uuid, self._states[control],
                        )
                        break
                    except asyncio.TimeoutError:
                        _LOGGER.debug("No confirmation from %s, trying next", ch.uuid)
                else:
                    self._states[control] = turn_on
                    _LOGGER.debug("No confirmation for %s; assuming %s", control, turn_on)
            finally:
                for ch in subscribed:
                    try:
                        await client.stop_notify(ch)
                    except Exception:  # noqa: BLE001
                        pass
                await client.disconnect()

        self._notify_listeners()
