"""Switch platform for the Aromadd Diffuser (on/off)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aromadd_device import AromaddDevice
from .const import DOMAIN, MANUFACTURER, MODEL


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aromadd switch from a config entry."""
    device: AromaddDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AromaddSwitch(entry, device)])


class AromaddSwitch(SwitchEntity):
    """Optimistic on/off switch for the Aromadd diffuser.

    The diffuser does not expose a readable power state over BLE, so the
    entity assumes its state succeeded (assumed_state). Home Assistant shows
    separate on/off controls accordingly.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_assumed_state = True
    _attr_icon = "mdi:air-purifier"

    def __init__(self, entry: ConfigEntry, device: AromaddDevice) -> None:
        """Initialise the switch entity."""
        self._device = device
        address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = entry.entry_id
        self._attr_is_on = False
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the diffuser on."""
        await self._device.async_turn_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the diffuser off."""
        await self._device.async_turn_off()
        self._attr_is_on = False
        self.async_write_ha_state()
