"""Switch platform for the Aromadd Diffuser (power + fan)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aromadd_device import AromaddDevice
from .const import CONTROL_FAN, CONTROL_POWER, DOMAIN, MANUFACTURER, MODEL


@dataclass(frozen=True, kw_only=True)
class AromaddSwitchDescription(SwitchEntityDescription):
    """Describes an Aromadd switch."""

    control: str
    setter: Callable[[AromaddDevice, bool], Awaitable[None]]


SWITCHES: tuple[AromaddSwitchDescription, ...] = (
    AromaddSwitchDescription(
        key=CONTROL_POWER,
        translation_key=CONTROL_POWER,
        icon="mdi:air-purifier",
        control=CONTROL_POWER,
        setter=lambda device, on: device.async_set_power(on),
    ),
    AromaddSwitchDescription(
        key=CONTROL_FAN,
        translation_key=CONTROL_FAN,
        icon="mdi:fan",
        control=CONTROL_FAN,
        setter=lambda device, on: device.async_set_fan(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aromadd switches from a config entry."""
    device: AromaddDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AromaddSwitch(entry, device, description) for description in SWITCHES
    )


class AromaddSwitch(SwitchEntity):
    """A switch backed by one Aromadd BLE control.

    Each command is confirmed by the device's state-report notification, so the
    reported state reflects what the diffuser acknowledged. Changes made with
    the physical button or the phone app while HA isn't connected are not pushed.
    """

    _attr_has_entity_name = True
    entity_description: AromaddSwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        device: AromaddDevice,
        description: AromaddSwitchDescription,
    ) -> None:
        """Initialise the switch entity."""
        self._device = device
        self.entity_description = description
        address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the last confirmed state for this control."""
        return self._device.state(self.entity_description.control)

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
        """Turn this control on."""
        await self.entity_description.setter(self._device, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn this control off."""
        await self.entity_description.setter(self._device, False)
        self.async_write_ha_state()
