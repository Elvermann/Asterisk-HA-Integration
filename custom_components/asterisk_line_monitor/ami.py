"""Minimal asynchronous, read-only Asterisk Manager Interface client."""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from typing import Any

_LOGGER = logging.getLogger(__name__)
Message = dict[str, str]
EventCallback = Callable[[Message], Awaitable[None]]
ConnectionCallback = Callable[[bool], Awaitable[None]]


def _parse_message(raw: bytes) -> Message:
    message: Message = {}
    text = raw.decode("utf-8", errors="replace")
    for line in text.split("\r\n"):
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        # AMI events occasionally contain repeated headers; retain the first.
        message.setdefault(key, value)
    return message


def _make_action(**fields: str) -> bytes:
    return ("\r\n".join(f"{key}: {value}" for key, value in fields.items()) + "\r\n\r\n").encode()


class AmiClient:
    """Connect to AMI, authenticate, and forward events without write actions."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        on_event: EventCallback,
        on_connection: ConnectionCallback,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.on_event = on_event
        self.on_connection = on_connection
        self._stop = asyncio.Event()
        self._writer: asyncio.StreamWriter | None = None

    async def stop(self) -> None:
        self._stop.set()
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def show_outbound_registrations(self) -> bool:
        """Request a read-only snapshot of configured PJSIP outbound registrations."""
        writer = self._writer
        if writer is None or writer.is_closing():
            return False
        writer.write(_make_action(Action="PJSIPShowRegistrationsOutbound"))
        await writer.drain()
        return True

    async def run(self) -> None:
        backoff = 5
        while not self._stop.is_set():
            try:
                await self._run_connection()
                backoff = 5
            except asyncio.CancelledError:
                raise
            except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError) as err:
                _LOGGER.warning("AMI connection lost: %s", err)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected AMI client error")
            finally:
                if self._writer is not None:
                    self._writer.close()
                    try:
                        await self._writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass
                    self._writer = None
                await self.on_connection(False)

            if not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 60)

    async def _run_connection(self) -> None:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=10
        )
        self._writer = writer
        sock = writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except OSError:
                pass

        greeting = await asyncio.wait_for(reader.readline(), timeout=10)
        if not greeting.startswith(b"Asterisk Call Manager/"):
            raise ConnectionError(f"Unexpected AMI greeting: {greeting!r}")

        writer.write(
            _make_action(
                Action="Login",
                Username=self.username,
                Secret=self.password,
                Events="on",
                **{"Application": "Home Assistant Asterisk Line Monitor"},
            )
        )
        await writer.drain()

        login_response: Message | None = None
        # Login response comes first; a successful login then starts event delivery.
        while login_response is None:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            message = _parse_message(raw)
            if message.get("Response"):
                login_response = message
            elif message.get("Event"):
                await self.on_event(message)

        if login_response.get("Response", "").lower() != "success":
            raise PermissionError(login_response.get("Message", "AMI login rejected"))

        _LOGGER.info("Connected and authenticated to Asterisk AMI at %s:%s", self.host, self.port)
        await self.on_connection(True)

        while not self._stop.is_set():
            raw = await reader.readuntil(b"\r\n\r\n")
            message = _parse_message(raw)
            if message.get("Event"):
                await self.on_event(message)
            # Only read-only list queries are issued; action responses are intentionally ignored.
