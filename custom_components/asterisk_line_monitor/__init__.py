"""Asterisk Line Monitor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_SHOW_CALL_DETAILS, DOMAIN
from .coordinator import AsteriskCoordinator


def _remove_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove legacy line occupancy and obsolete epcan client entities."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    obsolete_prefix = f"{entry.entry_id}_client_epcan_"
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id.endswith("_busy") or entity.unique_id.startswith(obsolete_prefix):
            entity_registry.async_remove(entity.entity_id)

    obsolete_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}:client:epcan")}
    )
    if obsolete_device is not None:
        device_registry.async_remove_device(obsolete_device.id)


def _remove_optional_call_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Permanently remove optional call-detail entities when the feature is disabled."""
    registry = er.async_get(hass)
    suffixes = ("_call_peer", "_call_duration")
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.endswith(suffixes):
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Asterisk Line Monitor from a config entry."""
    _remove_obsolete_entities(hass, entry)
    show_call_details = entry.options.get(CONF_SHOW_CALL_DETAILS, True)
    if not show_call_details:
        _remove_optional_call_entities(hass, entry)

    coordinator = AsteriskCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor", "sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    coordinator: AsteriskCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.clear_client_entity_adder()
    coordinator.clear_line_entity_adder()
    coordinator.clear_line_status_entity_adder()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["binary_sensor", "sensor"])
    await coordinator.async_stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
