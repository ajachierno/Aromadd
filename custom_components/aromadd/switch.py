"""Switch platform for the Aromadd Diffuser (on/off)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
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
    """On/off switch for the Aromadd diffuser.

    Each command is confirmed by the device's state-report notification, so the
    reported state reflects what the diffuser acknowledged. State is only known
    after the first command (or if the diffuser is toggled from this entity);
    changes made with the physical button or the phone app are not pushed.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:air-purifier"

    def __init__(self, entry: ConfigEntry, device: AromaddDevice) -> None:
        """Initialise the switch entity."""
        self._device = device
        address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the last confirmed power state."""
        return self._device.is_on

    async def async_added_to_hass(self) -> None:
        """Register for state-change callbacks from the device."""
        self.async_on_remove(
            self._device.register_callback(self._handle_device_update)
        )

    @callback
    def _handle_device_update(self) -> None:
        """Update HA state when the device reports a change."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the diffuser on."""
        await self._device.async_turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the diffuser off."""
        await self._device.async_turn_off()
        self.async_write_ha_state()
