"""BLE communication layer for the Aromadd Diffuser."""

from __future__ import annotations

import asyncio
import logging

from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .const import (
    CMD_POWER_OFF,
    CMD_POWER_ON,
    COMMANDS_CONFIGURED,
    WRITE_CHARACTERISTIC_UUID,
)

_LOGGER = logging.getLogger(__name__)


class AromaddDevice:
    """Thin wrapper that connects to the diffuser and writes a command.

    The Aromadd U5 Pro is a write-only target for our purposes: we connect,
    write the on/off payload, then disconnect again so the official app (and
    other BLE clients) can reconnect. State is tracked optimistically by the
    switch entity because the device does not advertise a readable power state.
    """

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialise with the discovered BLEDevice."""
        self._ble_device = ble_device
        self._lock = asyncio.Lock()

    @property
    def address(self) -> str:
        """Return the BLE MAC address of the device."""
        return self._ble_device.address

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the cached BLEDevice (called when HA rediscovers it)."""
        self._ble_device = ble_device

    async def async_turn_on(self) -> None:
        """Turn the diffuser on."""
        await self._send(CMD_POWER_ON, "on")

    async def async_turn_off(self) -> None:
        """Turn the diffuser off."""
        await self._send(CMD_POWER_OFF, "off")

    async def async_disconnect(self) -> None:
        """No persistent connection is held; nothing to tear down."""
        return

    async def _send(self, payload: bytes, action: str) -> None:
        """Connect, write a single command, then disconnect."""
        if not COMMANDS_CONFIGURED:
            _LOGGER.warning(
                "Aromadd command bytes are still placeholders; sending '%s' "
                "will not actually control the diffuser. Edit const.py with "
                "the values from CAPTURE_GUIDE.md to enable real control",
                action,
            )

        async with self._lock:
            _LOGGER.debug("Connecting to Aromadd %s to send '%s'", self.address, action)
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self._ble_device.name or self._ble_device.address,
            )
            try:
                await client.write_gatt_char(
                    WRITE_CHARACTERISTIC_UUID, payload, response=False
                )
                _LOGGER.debug(
                    "Wrote %s to %s (%s)",
                    payload.hex(),
                    WRITE_CHARACTERISTIC_UUID,
                    action,
                )
            finally:
                await client.disconnect()
