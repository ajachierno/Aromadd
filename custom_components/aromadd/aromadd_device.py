"""BLE communication layer for the Aromadd Diffuser.

Connects to the diffuser, resolves the control characteristics from the live
GATT table, sends a framed command, waits briefly for the device's state-report
notification to confirm the result, then disconnects so the official Aromadd app
can reconnect.
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
    NOTIFY_HANDLE,
    PAYLOAD_FAN_OFF,
    PAYLOAD_FAN_ON,
    PAYLOAD_POWER_OFF,
    PAYLOAD_POWER_ON,
    REPORT_FAN_PREFIX,
    REPORT_POWER_PREFIX,
    WRITE_HANDLE,
)

_LOGGER = logging.getLogger(__name__)

# How long to wait for the device to confirm a command via notification before
# falling back to assuming the command worked.
CONFIRM_TIMEOUT = 4.0

# Bluetooth SIG base UUID suffix; characteristics/services NOT ending in this are
# vendor-specific (the Aromadd control service is one of these).
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
    """Wrap a payload in the Aromadd frame: header + XOR checksum + payload + footer."""
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


def _is_vendor(uuid: str | None) -> bool:
    """True if a UUID is vendor-specific (not a standard Bluetooth SIG UUID)."""
    return bool(uuid) and not uuid.lower().endswith(_SIG_BASE_SUFFIX)


def _resolve_characteristics(
    client: BleakClient,
) -> tuple[BleakGATTCharacteristic | None, BleakGATTCharacteristic | None]:
    """Find the write and notify characteristics from the connected GATT table.

    Handle numbers can differ between BLE stacks, so we don't trust the captured
    handles blindly. We try the handle hints first, then fall back to scanning
    for writable / notifiable characteristics, preferring the vendor service.
    """
    services = client.services

    write_char = services.get_characteristic(WRITE_HANDLE)
    notify_char = services.get_characteristic(NOTIFY_HANDLE)

    writable: list[BleakGATTCharacteristic] = []
    notifiable: list[BleakGATTCharacteristic] = []
    for service in services:
        for char in service.characteristics:
            props = char.properties
            if "write" in props or "write-without-response" in props:
                writable.append(char)
            if "notify" in props or "indicate" in props:
                notifiable.append(char)

    def _prefer_vendor(
        chars: list[BleakGATTCharacteristic],
    ) -> BleakGATTCharacteristic | None:
        if not chars:
            return None
        vendor = [c for c in chars if _is_vendor(c.uuid) or _is_vendor(c.service_uuid)]
        return (vendor or chars)[0]

    if write_char is None:
        write_char = _prefer_vendor(writable)
    if notify_char is None:
        notify_char = _prefer_vendor(notifiable)

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "GATT chars: writable=%s notifiable=%s -> write=%s notify=%s",
            [c.uuid for c in writable],
            [c.uuid for c in notifiable],
            write_char.uuid if write_char else None,
            notify_char.uuid if notify_char else None,
        )

    return write_char, notify_char


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
        """Connect, send a command, confirm via notification, then disconnect."""
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
                self.address,
                control,
                "on" if turn_on else "off",
            )
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._ble_device.name or self._ble_device.address,
            )
            try:
                write_char, notify_char = _resolve_characteristics(client)
                if write_char is None:
                    raise RuntimeError(
                        "Could not find a writable characteristic on the Aromadd "
                        "device; the GATT layout was not as expected."
                    )

                if notify_char is not None:
                    try:
                        await client.start_notify(notify_char, _on_notify)
                    except Exception as err:  # noqa: BLE001 - best-effort
                        _LOGGER.debug("Could not subscribe to notifications: %s", err)

                await client.write_gatt_char(write_char, frame, response=True)
                _LOGGER.debug("Wrote %s to %s", frame.hex(), write_char.uuid)

                if notify_char is not None:
                    try:
                        await asyncio.wait_for(confirmed.wait(), timeout=CONFIRM_TIMEOUT)
                        _LOGGER.debug(
                            "Confirmed %s state: %s", control, self._states[control]
                        )
                    except asyncio.TimeoutError:
                        self._states[control] = turn_on
                        _LOGGER.debug(
                            "No confirmation for %s; assuming %s", control, turn_on
                        )
                else:
                    self._states[control] = turn_on
            finally:
                if notify_char is not None:
                    try:
                        await client.stop_notify(notify_char)
                    except Exception:  # noqa: BLE001
                        pass
                await client.disconnect()

        self._notify_listeners()
