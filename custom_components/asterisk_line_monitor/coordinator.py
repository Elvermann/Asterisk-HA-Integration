"""AMI event coordinator for provider lines and dynamic PJSIP clients."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ami import AmiClient, Message
from .const import DOMAIN, INBOUND_ENDPOINT, KNOWN_CLIENTS

_LOGGER = logging.getLogger(__name__)
_CHANNEL_SUFFIX = re.compile(r"^[0-9A-Fa-f]+$")


def _endpoint_from_channel(channel: str) -> str | None:
    """Extract a PJSIP endpoint name from a channel name."""
    if not channel.startswith("PJSIP/"):
        return None
    value = channel.partition("/")[2]
    if "-" in value:
        possible_name, suffix = value.rsplit("-", 1)
        if suffix and _CHANNEL_SUFFIX.fullmatch(suffix):
            value = possible_name
    return value or None


def _endpoint_from_device(device: str) -> str | None:
    """Extract an endpoint from a device-state name such as PJSIP/1001."""
    if device.startswith("PJSIP/"):
        return _endpoint_from_channel(device)
    return None


def _endpoint_from_registration_name(object_name: str) -> str | None:
    """Map epcan-reg-N registration objects to their epcan-N endpoint."""
    match = re.fullmatch(r"epcan-reg-(\\d+)", (object_name or "").strip())
    return f"epcan-{match.group(1)}" if match else None


def _clean_number(value: str) -> str:
    """Remove common PJSIP dial-string decoration but preserve phone symbols."""
    value = (value or "").strip().strip('"<>')
    if not value:
        return ""
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    value = value.split(",", 1)[0]
    value = value.split("@", 1)[0]
    value = value.split(";", 1)[0]
    return value.strip().strip('"<>') 


def _is_usable_peer(value: str) -> bool:
    """Reject unknown values and Asterisk feature-code strings as remote parties."""
    value = (value or "").strip().strip('"<>')
    if not value or value.lower() in {"unknown", "<unknown>", "anonymous", "restricted", "unavailable", "s"}:
        return False
    if value.startswith(("*", "#")):
        return False
    return any(character.isdigit() for character in value)


def _dialed_number(event: Message) -> str:
    """Best-effort destination number from a DialBegin AMI event."""
    for key in ("DialString", "DestExten", "DestConnectedLineNum", "DestCallerIDNum"):
        number = _clean_number(event.get(key, ""))
        if _is_usable_peer(number):
            return number
    return ""


class AsteriskCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Maintain active provider calls, client states and remote call parties."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._entry = entry
        self._connected = False
        self._provider_channels: dict[str, dict[str, Any]] = {}
        self._clients: dict[str, dict[str, Any]] = {}
        self._registrations: dict[str, dict[str, str]] = {}
        self._registration_scan: dict[str, dict[str, str]] = {}
        self._provider_endpoint_to_number: dict[str, str] = {}
        self._line_entity_adder: Callable[[str], None] | None = None
        self._announced_line_entities: set[str] = set()
        self._client_entity_adder: Callable[[str], None] | None = None
        self._announced_client_entities: set[str] = set()
        self._registration_query_pending = False
        self._registration_query_started = 0.0
        for endpoint in KNOWN_CLIENTS:
            self._ensure_client(endpoint)
        self._client = AmiClient(
            host=entry.data["host"],
            port=entry.data["port"],
            username=entry.data["username"],
            password=entry.data["password"],
            on_event=self._handle_event,
            on_connection=self._handle_connection,
        )
        self._task: asyncio.Task | None = None
        self._timer_task: asyncio.Task | None = None
        self._registration_task: asyncio.Task | None = None
        self.async_set_updated_data(self._snapshot())

    @property
    def client_endpoints(self) -> list[str]:
        return sorted(self._clients)

    @property
    def line_numbers(self) -> list[str]:
        return sorted({item["number"] for item in self._registrations.values()})

    @property
    def show_call_details(self) -> bool:
        return bool(self._entry.options.get("show_call_details", True))

    def set_line_entity_adder(self, callback: Callable[[str], None]) -> None:
        self._line_entity_adder = callback
        for number in self.line_numbers:
            self._announce_line_entity(number)

    def clear_line_entity_adder(self) -> None:
        self._line_entity_adder = None
        self._announced_line_entities.clear()

    def _announce_line_entity(self, number: str) -> None:
        if self._line_entity_adder and number not in self._announced_line_entities:
            self._announced_line_entities.add(number)
            self._line_entity_adder(number)

    def set_client_entity_adder(self, callback: Callable[[str], None]) -> None:
        self._client_entity_adder = callback
        for endpoint in self.client_endpoints:
            self._announce_client_entity(endpoint)

    def clear_client_entity_adder(self) -> None:
        self._client_entity_adder = None
        self._announced_client_entities.clear()

    def _announce_client_entity(self, endpoint: str) -> None:
        if self._client_entity_adder and endpoint not in self._announced_client_entities:
            self._announced_client_entities.add(endpoint)
            self._client_entity_adder(endpoint)

    def _ensure_client(self, endpoint: str) -> dict[str, Any] | None:
        endpoint = endpoint.strip()
        if not endpoint or self._is_provider_endpoint(endpoint):
            return None
        if endpoint not in self._clients:
            self._clients[endpoint] = {
                "contact_status": "Unknown",
                "contact_uri": "",
                "aor": "",
                "roundtrip_usec": None,
                "device_state": "UNKNOWN",
                "channels": {},
            }
        self._announce_client_entity(endpoint)
        return self._clients[endpoint]

    async def async_start(self) -> None:
        self._task = self.hass.async_create_task(self._client.run())
        self._timer_task = self.hass.async_create_task(self._refresh_durations())
        self._registration_task = self.hass.async_create_task(self._refresh_registrations())

    async def async_stop(self) -> None:
        await self._client.stop()
        tasks = [task for task in (self._task, self._timer_task, self._registration_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _refresh_durations(self) -> None:
        while True:
            await asyncio.sleep(1)
            if self._connected and (
                self._provider_channels or any(client["channels"] for client in self._clients.values())
            ):
                self.async_set_updated_data(self._snapshot())

    async def _refresh_registrations(self) -> None:
        """Reconcile registration state periodically in case an AMI event was missed."""
        while True:
            await asyncio.sleep(30)
            if self._connected:
                now = asyncio.get_running_loop().time()
                if self._registration_query_pending and now - self._registration_query_started > 20:
                    self._registration_query_pending = False
                if not self._registration_query_pending:
                    await self._request_registration_snapshot()

    async def _request_registration_snapshot(self) -> None:
        if not self._connected or self._registration_query_pending:
            return
        self._registration_query_pending = True
        self._registration_query_started = asyncio.get_running_loop().time()
        self._registration_scan = {}
        try:
            sent = await self._client.show_outbound_registrations()
            if not sent:
                self._registration_query_pending = False
        except (OSError, ConnectionError):
            self._registration_query_pending = False
            _LOGGER.debug("Could not request outbound PJSIP registrations", exc_info=True)

    def _is_provider_endpoint(self, endpoint: str) -> bool:
        return endpoint == INBOUND_ENDPOINT or endpoint.startswith("epcan-") or endpoint in self._provider_endpoint_to_number

    def _line_from_channel(self, channel: str) -> tuple[str | None, str | None]:
        """Resolve provider channels using Endpoint from outbound registration details."""
        endpoint = _endpoint_from_channel(channel)
        if endpoint == INBOUND_ENDPOINT:
            return None, "inbound"
        number = self._provider_endpoint_to_number.get(endpoint or "")
        return (number, "outbound") if number else (None, None)

    def _apply_registration_snapshot(self) -> None:
        """Commit one complete AMI registration list and announce newly found lines."""
        self._registrations = dict(self._registration_scan)
        self._provider_endpoint_to_number = {
            item["endpoint"]: item["number"]
            for item in self._registrations.values()
            if item.get("endpoint")
        }
        for number in self.line_numbers:
            self._announce_line_entity(number)

    async def _handle_connection(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._provider_channels.clear()
            self._registrations.clear()
            self._registration_scan.clear()
            self._provider_endpoint_to_number.clear()
            self._registration_query_pending = False
            for client in self._clients.values():
                client["channels"].clear()
                client["contact_status"] = "Unknown"
                client["device_state"] = "UNKNOWN"
                client["roundtrip_usec"] = None
        else:
            self._registration_query_pending = False
            await self._request_registration_snapshot()
        self.async_set_updated_data(self._snapshot())

    async def _handle_event(self, event: Message) -> None:
        name = event.get("Event", "")
        uniqueid = event.get("Uniqueid", "")
        changed = False

        if name == "OutboundRegistrationDetail":
            object_name = event.get("ObjectName", "").strip()
            number = _clean_number(event.get("ContactUser", ""))
            if object_name and _is_usable_peer(number):
                self._registration_scan[object_name] = {
                    "object_name": object_name,
                    "number": number,
                    # Asterisk's Endpoint field is empty unless the registration
                    # explicitly configures endpoint=. Our provider uses the
                    # consistent epcan-reg-N -> epcan-N object naming convention.
                    "endpoint": event.get("Endpoint", "").strip()
                    or _endpoint_from_registration_name(object_name)
                    or "",
                    "status": event.get("Status", "Unknown").strip(),
                    "server_uri": event.get("ServerUri", "").strip(),
                    "client_uri": event.get("ClientUri", "").strip(),
                    "next_reg": event.get("NextReg", "").strip(),
                }

        elif name == "OutboundRegistrationDetailComplete":
            self._apply_registration_snapshot()
            self._registration_query_pending = False
            changed = True

        elif name == "ContactStatus":
            endpoint = event.get("EndpointName", "")
            client = self._ensure_client(endpoint)
            if client is not None:
                client["contact_status"] = event.get("ContactStatus", "Unknown")
                client["contact_uri"] = event.get("URI", "")
                client["aor"] = event.get("AOR", "")
                client["roundtrip_usec"] = _safe_int(event.get("RoundtripUsec"))
                changed = True

        elif name == "DeviceStateChange":
            endpoint = _endpoint_from_device(event.get("Device", ""))
            client = self._ensure_client(endpoint or "")
            if client is not None:
                client["device_state"] = event.get("State", "UNKNOWN").upper()
                changed = True

        elif name == "Newchannel":
            channel = event.get("Channel", "")
            line, direction = self._line_from_channel(channel)
            if direction:
                key = uniqueid or channel
                self._provider_channels[key] = self._new_channel_record(
                    channel=channel, line=line, direction=direction,
                    extension=event.get("Exten", ""), context=event.get("Context", ""),
                    caller=event.get("CallerIDNum", ""), state=event.get("ChannelStateDesc", "Down"),
                    linkedid=event.get("Linkedid", ""),
                )
                self._apply_extension(self._provider_channels[key], event.get("Exten", ""), event.get("Context", ""))
                changed = True
            else:
                endpoint = _endpoint_from_channel(channel)
                client = self._ensure_client(endpoint or "")
                if client is not None:
                    key = uniqueid or channel
                    client["channels"][key] = self._new_channel_record(
                        channel=channel, line=None, direction="client",
                        extension=event.get("Exten", ""), context=event.get("Context", ""),
                        caller=event.get("CallerIDNum", ""), state=event.get("ChannelStateDesc", "Down"),
                        linkedid=event.get("Linkedid", ""),
                    )
                    changed = True

        elif name == "Newstate":
            state = event.get("ChannelStateDesc", "Unknown")
            if uniqueid in self._provider_channels:
                record = self._provider_channels[uniqueid]
                record["state"] = state
                if state.lower() == "up" and record.get("answered_monotonic") is None:
                    record["answered_monotonic"] = asyncio.get_running_loop().time()
                changed = True
            else:
                changed = self._update_client_channel(uniqueid, state=state)

        elif name == "Newexten":
            extension = event.get("Exten") or event.get("Extension", "")
            context = event.get("Context", "")
            if uniqueid in self._provider_channels:
                self._apply_extension(self._provider_channels[uniqueid], extension, context)
                changed = True
            else:
                changed = self._update_client_channel(uniqueid, extension=extension, context=context)

        elif name == "DialBegin":
            changed = self._handle_dial_begin(event)

        elif name == "NewConnectedLine":
            connected_num = _clean_number(event.get("ConnectedLineNum", ""))
            connected_name = (event.get("ConnectedLineName", "") or "").strip()
            updates: dict[str, Any] = {}
            if _is_usable_peer(connected_num):
                updates["peer"] = connected_num
            if connected_name and connected_name.lower() not in {"unknown", "<unknown>"}:
                updates["peer_name"] = connected_name
            if updates:
                changed = self._update_client_channel(uniqueid, **updates)

        elif name == "DialEnd":
            dial_status = event.get("DialStatus", "")
            dest_uniqueid = event.get("DestUniqueid", "")
            if dest_uniqueid:
                changed = self._update_client_channel(dest_uniqueid, dial_status=dial_status) or changed
            if uniqueid:
                changed = self._update_client_channel(uniqueid, dial_status=dial_status) or changed

        elif name == "Hangup" and uniqueid:
            if self._provider_channels.pop(uniqueid, None) is not None:
                changed = True
            for client in self._clients.values():
                if client["channels"].pop(uniqueid, None) is not None:
                    changed = True

        if changed:
            self.async_set_updated_data(self._snapshot())

    def _handle_dial_begin(self, event: Message) -> bool:
        """Pair source/destination channels and set per-client conversation details."""
        source_channel = event.get("Channel", "")
        dest_channel = event.get("DestChannel", "")
        source_uid = event.get("Uniqueid", "")
        dest_uid = event.get("DestUniqueid", "")
        source_endpoint = _endpoint_from_channel(source_channel)
        dest_endpoint = _endpoint_from_channel(dest_channel)
        source_line, source_direction = self._line_from_channel(source_channel)
        dest_line, dest_direction = self._line_from_channel(dest_channel)
        source_provider = source_direction is not None
        dest_provider = dest_direction is not None
        changed = False

        if source_provider and source_uid:
            record = self._provider_channels.setdefault(
                source_uid,
                self._new_channel_record(
                    channel=source_channel, line=source_line,
                    direction=source_direction or "inbound",
                    extension=event.get("Exten", ""), context=event.get("Context", ""),
                    caller=event.get("CallerIDNum", ""), state=event.get("ChannelStateDesc", "Dialing"),
                    linkedid=event.get("Linkedid", ""),
                ),
            )
            if source_line:
                record["line"] = source_line
            changed = True

        if dest_provider and dest_uid:
            record = self._provider_channels.setdefault(
                dest_uid,
                self._new_channel_record(
                    channel=dest_channel, line=dest_line,
                    direction=dest_direction or "outbound",
                    extension=event.get("DestExten", ""), context=event.get("DestContext", ""),
                    caller=event.get("DestCallerIDNum", ""), state=event.get("DestChannelStateDesc", "Dialing"),
                    linkedid=event.get("DestLinkedid", ""),
                ),
            )
            if dest_line:
                record["line"] = dest_line
            changed = True

        source_client = self._ensure_client(source_endpoint or "") if source_endpoint and not source_provider else None
        dest_client = self._ensure_client(dest_endpoint or "") if dest_endpoint and not dest_provider else None
        if source_client is not None and source_uid:
            source_client["channels"].setdefault(
                source_uid,
                self._new_channel_record(
                    channel=source_channel, line=None, direction="client",
                    extension=event.get("Exten", ""), context=event.get("Context", ""),
                    caller=event.get("CallerIDNum", ""), state=event.get("ChannelStateDesc", "Dialing"),
                    linkedid=event.get("Linkedid", ""),
                ),
            )
            changed = True
        if dest_client is not None and dest_uid:
            dest_client["channels"].setdefault(
                dest_uid,
                self._new_channel_record(
                    channel=dest_channel, line=None, direction="client",
                    extension=event.get("DestExten", ""), context=event.get("DestContext", ""),
                    caller=event.get("DestCallerIDNum", ""), state=event.get("DestChannelStateDesc", "Dialing"),
                    linkedid=event.get("DestLinkedid", ""),
                ),
            )
            changed = True

        provider_line = source_line or dest_line
        if source_uid in self._provider_channels:
            provider_line = self._provider_channels[source_uid].get("line") or provider_line
        if dest_uid in self._provider_channels:
            provider_line = self._provider_channels[dest_uid].get("line") or provider_line

        dialed_number = _dialed_number(event)

        if source_client is not None and source_uid:
            record = source_client["channels"][source_uid]
            if dest_client is not None:
                record.update(peer=dest_endpoint, peer_name=KNOWN_CLIENTS.get(dest_endpoint or "", f"PJSIP {dest_endpoint}"), direction="intern")
            elif dest_provider:
                record.update(peer=dialed_number or "Unbekannt", peer_name="", direction="ausgehend", line=provider_line)
            elif dest_endpoint:
                record.update(peer=dest_endpoint, peer_name=KNOWN_CLIENTS.get(dest_endpoint, ""), direction="ausgehend")
            changed = True

        if dest_client is not None and dest_uid:
            record = dest_client["channels"][dest_uid]
            if source_provider:
                caller_number = event.get("CallerIDNum", "")
                caller_name = event.get("CallerIDName", "")
                record.update(
                    peer=caller_number or caller_name or "Unbekannt",
                    peer_name=caller_name, direction="eingehend", line=provider_line,
                )
            elif source_endpoint:
                record.update(peer=source_endpoint, peer_name=KNOWN_CLIENTS.get(source_endpoint, f"PJSIP {source_endpoint}"), direction="intern")
            changed = True
        return changed

    def _update_client_channel(self, uniqueid: str, **updates: Any) -> bool:
        if not uniqueid:
            return False
        changed = False
        for client in self._clients.values():
            record = client["channels"].get(uniqueid)
            if record is not None:
                record.update({key: value for key, value in updates.items() if value is not None})
                if str(updates.get("state", "")).lower() == "up" and record.get("answered_monotonic") is None:
                    record["answered_monotonic"] = asyncio.get_running_loop().time()
                changed = True
        return changed

    @staticmethod
    def _new_channel_record(
        *, channel: str, line: str | None, direction: str, extension: str,
        context: str, caller: str, state: str, linkedid: str = "",
    ) -> dict[str, Any]:
        return {
            "channel": channel, "line": line, "direction": direction,
            "extension": extension, "context": context, "caller": caller,
            "peer": "", "peer_name": "", "state": state, "dial_status": "",
            "linkedid": linkedid, "started": datetime.now(timezone.utc).isoformat(),
            "started_monotonic": asyncio.get_running_loop().time(),
            "answered_monotonic": asyncio.get_running_loop().time() if str(state).lower() == "up" else None,
        }

    def _apply_extension(self, record: dict[str, Any], extension: str, context: str) -> None:
        if context == "from-epcan" and extension:
            record["extension"] = extension
            if extension in self.line_numbers:
                record["line"] = extension
            record["direction"] = "inbound"

    @staticmethod
    def _client_status(client: dict[str, Any]) -> str:
        states = [str(record.get("state", "")).lower() for record in client["channels"].values()]
        if any(state in {"up", "busy"} for state in states):
            return "telefoniert"
        if any(state in {"ring", "ringing", "pre-ring"} for state in states):
            return "klingelt"
        if states:
            return "wählt"
        device_state = client.get("device_state", "UNKNOWN").upper()
        if device_state in {"INUSE", "BUSY", "ONHOLD", "RINGINUSE"}:
            return "telefoniert"
        if device_state == "RINGING":
            return "klingelt"
        if device_state == "NOT_INUSE":
            return "online"
        if device_state == "UNAVAILABLE":
            return "offline"
        contact_status = client.get("contact_status", "Unknown").lower()
        if contact_status == "reachable":
            return "online"
        if contact_status in {"unreachable", "removed"}:
            return "offline"
        return "unbekannt"

    @staticmethod
    def _current_call(client: dict[str, Any], now: float) -> dict[str, Any] | None:
        records = list(client["channels"].values())
        if not records:
            return None
        priority = {"up": 0, "busy": 0, "ringing": 1, "ring": 1, "pre-ring": 1, "dialing": 2}
        records.sort(key=lambda item: priority.get(str(item.get("state", "")).lower(), 3))
        return AsteriskCoordinator._call_snapshot(records[0], now)

    def _snapshot(self) -> dict[str, Any]:
        now = asyncio.get_running_loop().time()
        lines: dict[str, dict[str, Any]] = {}
        for number in self.line_numbers:
            calls = [self._call_snapshot(record, now) for record in self._provider_channels.values() if record.get("line") == number]
            registrations = [item for item in self._registrations.values() if item["number"] == number]
            lines[number] = {
                "busy": bool(calls),
                "active_calls": len(calls),
                "calls": calls,
                "registered": any(item.get("status", "").lower() == "registered" for item in registrations),
                "registration_status": ", ".join(sorted({item.get("status", "Unknown") for item in registrations})) or "Unknown",
                "registrations": [
                    {"object_name": item["object_name"], "endpoint": item.get("endpoint") or None,
                     "status": item.get("status", "Unknown"), "server_uri": item.get("server_uri") or None,
                     "next_reg": _safe_int(item.get("next_reg"))}
                    for item in registrations
                ],
            }
        all_calls = [{"uniqueid": uniqueid, **self._call_snapshot(record, now)} for uniqueid, record in self._provider_channels.items()]
        clients: dict[str, dict[str, Any]] = {}
        for endpoint, client in self._clients.items():
            channels = [self._call_snapshot(record, now) for record in client["channels"].values()]
            clients[endpoint] = {
                "status": self._client_status(client),
                "contact_status": client.get("contact_status", "Unknown"),
                "contact_uri": client.get("contact_uri", ""),
                "aor": client.get("aor", ""),
                "roundtrip_usec": client.get("roundtrip_usec"),
                "device_state": client.get("device_state", "UNKNOWN"),
                "active_channels": len(channels),
                "channels": channels,
                "current_call": self._current_call(client, now),
            }
        return {
            "connected": self._connected,
            "active_calls": len(self._provider_channels),
            "lines": lines,
            "registrations": self._registrations,
            "calls": all_calls,
            "clients": clients,
        }

    @staticmethod
    def _call_snapshot(record: dict[str, Any], now: float) -> dict[str, Any]:
        return {
            "channel": record.get("channel"), "line": record.get("line"),
            "direction": record.get("direction"), "caller": record.get("caller"),
            "peer": record.get("peer"), "peer_name": record.get("peer_name"),
            "extension": record.get("extension"), "context": record.get("context"),
            "state": record.get("state"), "dial_status": record.get("dial_status"),
            "linkedid": record.get("linkedid"), "started": record.get("started"),
            "duration": max(0, int(now - record["answered_monotonic"])) if record.get("answered_monotonic") is not None else 0,
            "setup_duration": max(0, int(now - record.get("started_monotonic", now))),
        }


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None
