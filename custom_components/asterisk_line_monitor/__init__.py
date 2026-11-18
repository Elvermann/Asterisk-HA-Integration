"""Asterisk Line Monitor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SHOW_CALL_DETAILS, DOMAIN
from .coordinator import AsteriskCoordinator


def _remove_optional_call_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Permanently remove optional call-detail entities when the feature is disabled."""
    registry = er.async_get(hass)
    suffixes = ("_call_peer", "_call_duration")
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.endswith(suffixes):
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Asterisk Line Monitor from a config entry."""
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
