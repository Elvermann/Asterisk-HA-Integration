"""Sensors for epcan lines, active calls and dynamically discovered PJSIP clients."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SHOW_CALL_DETAILS, DOMAIN, KNOWN_CLIENTS
from .coordinator import AsteriskCoordinator


def _client_entities(coordinator: AsteriskCoordinator, entry: ConfigEntry, endpoint: str) -> list[SensorEntity]:
    """Create the always-on status sensor and optional call-detail sensors."""
    entities: list[SensorEntity] = [AsteriskClientStatus(coordinator, entry, endpoint)]
    if entry.options.get(CONF_SHOW_CALL_DETAILS, True):
        entities.extend([AsteriskClientCallPeer(coordinator, entry, endpoint), AsteriskClientCallDuration(coordinator, entry, endpoint)])
    return entities


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up fixed and dynamically discovered client sensors."""
    coordinator: AsteriskCoordinator = hass.data[DOMAIN][entry.entry_id]
    added_clients: set[str] = set()
    entities: list[SensorEntity] = [AsteriskActiveCalls(coordinator, entry), AsteriskPjsipRegistrations(coordinator, entry)]
    for endpoint in coordinator.client_endpoints:
        entities.extend(_client_entities(coordinator, entry, endpoint))
        added_clients.add(endpoint)
    async_add_entities(entities)

    def add_dynamic_client(endpoint: str) -> None:
        if endpoint not in added_clients:
            added_clients.add(endpoint)
            async_add_entities(_client_entities(coordinator, entry, endpoint))

    coordinator.set_client_entity_adder(add_dynamic_client)

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_line_"
    restored = {
        entity.unique_id[len(prefix):]
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
        and entity.domain == "sensor"
        and entity.unique_id.startswith(prefix)
        and entity.unique_id.endswith("_status")
    }
    added_status: set[str] = set()

    def add_line_status(number: str) -> None:
        if number not in added_status:
            added_status.add(number)
            async_add_entities([AsteriskLineStatus(coordinator, entry, number)])

    coordinator.set_line_status_entity_adder(add_line_status, restored)


class AsteriskPjsipRegistrations(CoordinatorEntity[AsteriskCoordinator], SensorEntity):
    """Central overview of outgoing PJSIP registrations."""

    _attr_has_entity_name = True
    _attr_name = "PJSIP Registrierungen"
    _attr_icon = "mdi:account-network"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pjsip_registrations"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Asterisk Line Monitor", manufacturer="Asterisk", model="AMI line monitor")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("registrations", {}))

    @property
    def extra_state_attributes(self):
        registrations = self.coordinator.data.get("registrations", {})
        return {"registrierungen": [
            {"objekt": item.get("object_name"), "rufnummer": item.get("number"),
             "endpoint": item.get("endpoint"), "status": item.get("status"),
             "server_uri": item.get("server_uri"), "naechste_registrierung": _safe_int(item.get("next_reg"))}
            for item in registrations.values()
        ]}


class AsteriskLineStatus(CoordinatorEntity[AsteriskCoordinator], SensorEntity):
    """Per-line text sensor, created after the first observed call."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:phone"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, number: str) -> None:
        super().__init__(coordinator)
        self._number = number
        self._attr_name = f"{number} Gespräch"
        self._attr_unique_id = f"{entry.entry_id}_line_{number}_status"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Asterisk Line Monitor", manufacturer="Asterisk", model="AMI line monitor")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))

    @property
    def line(self) -> dict:
        return self.coordinator.data.get("lines", {}).get(self._number, {})

    @property
    def current_call(self) -> dict:
        calls = self.line.get("calls", [])
        return max(calls, key=lambda call: call.get("setup_duration", 0)) if calls else {}

    @property
    def native_value(self) -> str:
        call = self.current_call
        if not call:
            return "Frei"
        peer = str(call.get("peer") or "").strip()
        return peer if peer and peer.lower() not in {"unbekannt", "unknown"} else "Belegt"

    @property
    def extra_state_attributes(self):
        call = self.current_call
        return {"rufnummer": self._number, "gegenstelle": call.get("peer"),
                "gegenstellenname": call.get("peer_name"), "richtung": call.get("direction"),
                "gespraechsdauer": call.get("duration", 0),
                "registrierungsstatus": self.line.get("registration_status", "Unknown")}


class AsteriskActiveCalls(CoordinatorEntity[AsteriskCoordinator], SensorEntity):
    """Number of active provider call legs."""
    _attr_has_entity_name = True
    _attr_name = "Aktive epcan Gespräche"
    _attr_icon = "mdi:phone-log"
    _attr_native_unit_of_measurement = "Gespräche"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_calls"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Asterisk Line Monitor", manufacturer="Asterisk", model="AMI line monitor")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data["active_calls"])

    @property
    def extra_state_attributes(self):
        if self.coordinator.show_call_details:
            return {"active_calls": self.coordinator.data["calls"], "line_states": self.coordinator.data["lines"]}
        return {"line_states": {number: {"busy": details["busy"], "active_calls": details["active_calls"]} for number, details in self.coordinator.data["lines"].items()}}


class AsteriskClientBase(CoordinatorEntity[AsteriskCoordinator], SensorEntity):
    """Base class for entities attached to one PJSIP client device."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, endpoint: str) -> None:
        super().__init__(coordinator)
        self._endpoint = endpoint
        label = KNOWN_CLIENTS.get(endpoint, f"PJSIP {endpoint}")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{entry.entry_id}:client:{endpoint}")}, name=label, manufacturer="Asterisk", model=f"PJSIP-Endgerät ({endpoint})", via_device=(DOMAIN, entry.entry_id))

    @property
    def client(self) -> dict:
        return self.coordinator.data["clients"].get(self._endpoint, {})

    @property
    def current_call(self) -> dict:
        return self.client.get("current_call") or {}

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("connected"))


class AsteriskClientStatus(AsteriskClientBase):
    """Online/offline/ringing/in-call state for one PJSIP client."""
    _attr_name = "Status"
    _attr_icon = "mdi:phone-account"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, endpoint: str) -> None:
        super().__init__(coordinator, entry, endpoint)
        self._attr_unique_id = f"{entry.entry_id}_client_{endpoint}_status"

    @property
    def native_value(self) -> str:
        return self.client.get("status", "unbekannt")

    @property
    def extra_state_attributes(self):
        client = self.client
        attrs = {"endpoint": self._endpoint, "aor": client.get("aor"), "contact_uri": client.get("contact_uri"), "contact_status": client.get("contact_status"), "device_state": client.get("device_state"), "roundtrip_usec": client.get("roundtrip_usec"), "active_channels": client.get("active_channels", 0)}
        if self.coordinator.show_call_details:
            attrs["channels"] = client.get("channels", [])
            attrs["current_call"] = client.get("current_call")
        return attrs


class AsteriskClientCallPeer(AsteriskClientBase):
    """Current conversation partner for one PJSIP client."""
    _attr_name = "Gesprächspartner"
    _attr_icon = "mdi:account-voice"

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, endpoint: str) -> None:
        super().__init__(coordinator, entry, endpoint)
        self._attr_unique_id = f"{entry.entry_id}_client_{endpoint}_call_peer"

    @property
    def native_value(self) -> str:
        call = self.current_call
        peer = str(call.get("peer") or "").strip()
        peer_name = str(call.get("peer_name") or "").strip()
        if not call:
            return "Kein Gespräch"
        if peer_name and peer and peer_name != peer:
            return f"{peer_name} ({peer})"
        return peer or "Gegenstelle unbekannt"

    @property
    def extra_state_attributes(self):
        call = self.current_call
        return {"richtung": call.get("direction"), "leitung": call.get("line"), "kanal": call.get("channel"), "zustand": call.get("state"), "linkedid": call.get("linkedid")}


class AsteriskClientCallDuration(AsteriskClientBase):
    """Elapsed duration of the currently active client call."""
    _attr_name = "Gesprächsdauer"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: AsteriskCoordinator, entry: ConfigEntry, endpoint: str) -> None:
        super().__init__(coordinator, entry, endpoint)
        self._attr_unique_id = f"{entry.entry_id}_client_{endpoint}_call_duration"

    @property
    def native_value(self) -> int:
        return int(self.current_call.get("duration", 0))

    @property
    def extra_state_attributes(self):
        call = self.current_call
        return {"gespraechspartner": call.get("peer"), "richtung": call.get("direction"), "leitung": call.get("line"), "zustand": call.get("state")}
