"""BLE communication layer for the Aromadd Diffuser.

Connects to the diffuser, sends a framed command, waits briefly for the
device's state-report notification to confirm the result, then disconnects so
the official Aromadd app can reconnect.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .const import (
    FRAME_FOOTER,
    FRAME_HEADER,
    NOTIFY_HANDLE,
    PAYLOAD_POWER_OFF,
    PAYLOAD_POWER_ON,
    REPORT_POWER_PREFIX,
    WRITE_HANDLE,
)

_LOGGER = logging.getLogger(__name__)

# How long to wait for the device to confirm a command via notification before
# falling back to assuming the command worked.
CONFIRM_TIMEOUT = 4.0


def build_frame(payload: bytes) -> bytes:
    """Wrap a payload in the Aromadd frame: header + XOR checksum + payload + footer."""
    checksum = 0
    for byte in payload:
        checksum ^= byte
    return FRAME_HEADER + bytes([checksum]) + payload + FRAME_FOOTER


def _parse_power_report(data: bytes) -> bool | None:
    """Return True/False if data is a power state report, else None."""
    if len(data) < 6 or data[:3] != FRAME_HEADER or data[-3:] != FRAME_FOOTER:
        return None
    payload = data[4:-3]
    if payload[: len(REPORT_POWER_PREFIX)] == REPORT_POWER_PREFIX and len(
        payload
    ) > len(REPORT_POWER_PREFIX):
        return bool(payload[len(REPORT_POWER_PREFIX)])
    return None


class AromaddDevice:
    """Manage BLE control of a single Aromadd diffuser."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialise with the discovered BLEDevice."""
        self._ble_device = ble_device
        self._lock = asyncio.Lock()
        self._is_on: bool | None = None
        self._callbacks: list[Callable[[], None]] = []

    @property
    def address(self) -> str:
        """Return the BLE MAC address of the device."""
        return self._ble_device.address

    @property
    def is_on(self) -> bool | None:
        """Return the last known power state (None until first command)."""
        return self._is_on

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

    async def async_turn_on(self) -> None:
        """Turn the diffuser on."""
        await self._set_power(True)

    async def async_turn_off(self) -> None:
        """Turn the diffuser off."""
        await self._set_power(False)

    async def async_disconnect(self) -> None:
        """No persistent connection is held; nothing to tear down."""
        return

    async def _set_power(self, turn_on: bool) -> None:
        """Connect, send the power command, confirm via notification, disconnect."""
        payload = PAYLOAD_POWER_ON if turn_on else PAYLOAD_POWER_OFF
        frame = build_frame(payload)
        confirmed = asyncio.Event()

        def _on_notify(_char: BleakGATTCharacteristic, data: bytearray) -> None:
            state = _parse_power_report(bytes(data))
            if state is not None:
                self._is_on = state
                confirmed.set()

        async with self._lock:
            _LOGGER.debug(
                "Connecting to Aromadd %s to turn %s",
                self.address,
                "on" if turn_on else "off",
            )
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._ble_device.name or self._ble_device.address,
            )
            try:
                try:
                    await client.start_notify(NOTIFY_HANDLE, _on_notify)
                except Exception as err:  # noqa: BLE001 - notifications are best-effort
                    _LOGGER.debug("Could not subscribe to notifications: %s", err)

                await client.write_gatt_char(WRITE_HANDLE, frame, response=True)
                _LOGGER.debug("Wrote %s to handle 0x%04x", frame.hex(), WRITE_HANDLE)

                try:
                    await asyncio.wait_for(confirmed.wait(), timeout=CONFIRM_TIMEOUT)
                    _LOGGER.debug("Confirmed power state: %s", self._is_on)
                except asyncio.TimeoutError:
                    # No confirmation - assume the command took effect.
                    self._is_on = turn_on
                    _LOGGER.debug("No confirmation notification; assuming %s", turn_on)
            finally:
                try:
                    await client.stop_notify(NOTIFY_HANDLE)
                except Exception:  # noqa: BLE001
                    pass
                await client.disconnect()

        self._notify_listeners()
