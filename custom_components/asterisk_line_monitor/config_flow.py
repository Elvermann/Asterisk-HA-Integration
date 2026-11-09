"""Config and options flows for Asterisk Line Monitor."""

from __future__ import annotations

import asyncio

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

from .ami import _make_action, _parse_message
from .const import CONF_SHOW_CALL_DETAILS, DEFAULT_PORT, DEFAULT_SHOW_CALL_DETAILS, DOMAIN


async def _validate_ami(host: str, port: int, username: str, password: str) -> None:
    """Validate an AMI login without enabling event delivery."""
    reader = None
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=8)
        greeting = await asyncio.wait_for(reader.readline(), timeout=8)
        if not greeting.startswith(b"Asterisk Call Manager/"):
            raise ValueError("invalid_greeting")
        writer.write(_make_action(Action="Login", Username=username, Secret=password, Events="off"))
        await writer.drain()
        response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=8)
        message = _parse_message(response)
        if message.get("Response", "").lower() != "success":
            raise PermissionError("invalid_auth")
    except PermissionError:
        raise
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, ValueError) as err:
        raise ConnectionError("cannot_connect") from err
    finally:
        if writer is not None:
            try:
                writer.write(_make_action(Action="Logoff"))
                await writer.drain()
            except (ConnectionError, OSError):
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial configuration for Asterisk AMI."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await _validate_ami(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            except PermissionError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_USERNAME]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Asterisk ({user_input[CONF_HOST]})", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_HOST, default="192.168.178.124"): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Required(CONF_USERNAME, default="ha_line_monitor"): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow for this config entry."""
        return AsteriskLineMonitorOptionsFlow()


class AsteriskLineMonitorOptionsFlow(config_entries.OptionsFlowWithReload):
    """Manage optional call-detail entities and reload when changed."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema({
            vol.Optional(CONF_SHOW_CALL_DETAILS, default=self.config_entry.options.get(CONF_SHOW_CALL_DETAILS, DEFAULT_SHOW_CALL_DETAILS)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
