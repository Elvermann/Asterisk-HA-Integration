"""Binary sensors for the three epcan numbers and AMI connection."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LINE_DEFINITIONS
from .coordinator import AsteriskCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: AsteriskCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [AsteriskAmiConnected(coordinator, entry)]
    entities.extend(AsteriskLineBusy(coordinator, entry, number) for number in LINE_DEFINITIONS)
    async_add_entities(entities)


class AsteriskBaseEntity(CoordinatorEntity[AsteriskCoordinator]):
    """Common entity base for the monitor device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Asterisk Line Monitor",
            manufacturer="Asterisk",
            model="AMI line monitor",
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))


class AsteriskAmiConnected(AsteriskBaseEntity, BinarySensorEntity):
    """AMI connection state."""

    _attr_name = "AMI verbunden"
    _attr_icon = "mdi:lan-connect"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))


class AsteriskLineBusy(AsteriskBaseEntity, BinarySensorEntity):
    """Whether a provider line is currently occupied."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_icon = "mdi:phone-in-talk"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, number: str) -> None:
        super().__init__(coordinator, entry)
        self._number = number
        # Entity name is deliberately just the public phone number.
        self._attr_name = number
        self._attr_unique_id = f"{entry.entry_id}_{number}_busy"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["lines"][self._number]["busy"])

    @property
    def extra_state_attributes(self):
        details = self.coordinator.data["lines"][self._number]
        if self.coordinator.show_call_details:
            return details
        return {"busy": details["busy"], "active_calls": details["active_calls"]}
