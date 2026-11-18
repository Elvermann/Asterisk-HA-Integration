"""Binary sensors for dynamic provider-line registration and AMI state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AsteriskCoordinator


def _line_device_info(entry: ConfigEntry, number: str) -> DeviceInfo:
    """Return a dedicated Home Assistant device for one discovered provider line."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}:line:{number}")},
        name=number,
        manufacturer="Asterisk",
        model="epcan Providerleitung",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up AMI and dynamically discovered provider-line registration entities."""
    coordinator: AsteriskCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [AsteriskAmiConnected(coordinator, entry)]
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    restored = {
        entity.unique_id[len(prefix):-len("_registered")]
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
        and entity.domain == "binary_sensor"
        and entity.unique_id.startswith(prefix)
        and entity.unique_id.endswith("_registered")
    }
    added_lines: set[str] = set()
    for number in sorted(set(coordinator.line_numbers) | restored):
        entities.append(AsteriskLineRegistered(coordinator, entry, number))
        added_lines.add(number)
    async_add_entities(entities)

    def add_dynamic_line(number: str) -> None:
        if number not in added_lines:
            added_lines.add(number)
            async_add_entities([AsteriskLineRegistered(coordinator, entry, number)])

    coordinator.set_line_entity_adder(add_dynamic_line)


class AsteriskBaseEntity(CoordinatorEntity[AsteriskCoordinator]):
    """Common entity base for the integration overview device."""

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


class AsteriskLineRegistered(CoordinatorEntity[AsteriskCoordinator], BinarySensorEntity):
    """Whether at least one outbound registration for a public line is registered."""

    _attr_has_entity_name = True
    _attr_name = "Registrierung"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:account-check"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, number: str) -> None:
        super().__init__(coordinator)
        self._number = number
        self._attr_unique_id = f"{entry.entry_id}_{number}_registered"
        self._attr_device_info = _line_device_info(entry, number)

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))

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
