"""Binary sensors for dynamically discovered provider lines and AMI."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AsteriskCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: AsteriskCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [AsteriskAmiConnected(coordinator, entry)]
    added_lines: set[str] = set()
    for number in coordinator.line_numbers:
        entities.extend(_line_entities(coordinator, entry, number))
        added_lines.add(number)
    async_add_entities(entities)

    def add_dynamic_line(number: str) -> None:
        if number not in added_lines:
            added_lines.add(number)
            async_add_entities(_line_entities(coordinator, entry, number))

    coordinator.set_line_entity_adder(add_dynamic_line)


def _line_entities(coordinator: AsteriskCoordinator, entry: ConfigEntry, number: str):
    return [
        AsteriskLineBusy(coordinator, entry, number),
        AsteriskLineRegistered(coordinator, entry, number),
    ]


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
        details = self.coordinator.data.get("lines", {}).get(self._number, {})
        return bool(details.get("busy"))

    @property
    def extra_state_attributes(self):
        details = self.coordinator.data.get("lines", {}).get(self._number, {})
        if self.coordinator.show_call_details:
            return details
        return {"busy": details.get("busy", False), "active_calls": details.get("active_calls", 0)}



class AsteriskLineRegistered(AsteriskBaseEntity, BinarySensorEntity):
    """Whether at least one outbound registration for a public line is registered."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:account-check"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, number: str) -> None:
        super().__init__(coordinator, entry)
        self._number = number
        self._attr_name = f"{number} Registrierung"
        self._attr_unique_id = f"{entry.entry_id}_{number}_registered"

    @property
    def is_on(self) -> bool:
        line = self.coordinator.data.get("lines", {}).get(self._number, {})
        return bool(line.get("registered"))

    @property
    def extra_state_attributes(self):
        line = self.coordinator.data.get("lines", {}).get(self._number, {})
        return {
            "rufnummer": self._number,
            "registrierungsstatus": line.get("registration_status", "Unknown"),
            "registrierungen": line.get("registrations", []),
        }
