"""Public API client interface for Samcla."""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass

from .exceptions import SamclaAuthError, SamclaConnectionError


@dataclass(slots=True)
class SamclaApiClient:
    """Thin client interface for the SAMCLA TCP/SSL protocol."""

    host: str
    port: int
    pin: str | None = None

    def __post_init__(self) -> None:
        """Initialize connection state."""

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        """Open a connection to the hub."""

        if self._writer is not None and not self._writer.is_closing():
            return

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=context),
                timeout=5,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise SamclaConnectionError(f"Unable to connect to {self.host}:{self.port}") from err

    async def disconnect(self) -> None:
        """Close the current connection."""

        if self._writer is None:
            return

        self._writer.close()
        try:
            await asyncio.wait_for(self._writer.wait_closed(), timeout=2)
        except (OSError, asyncio.TimeoutError):
            pass

        self._writer = None
        self._reader = None

    async def get_status(self) -> dict[str, object]:
        """Return a status payload from the hub."""

        payload = await self._send_command("SSH100_STATS")
        if payload:
            parts = [part.strip() for part in payload.split(";") if part.strip()]
            return {
                "last_command": "idle",
                "firmware_version": parts[1] if len(parts) > 1 else payload,
                "is_irrigating": False,
                "irrigation_mode": "sequential",
                "default_duration": 60,
            }

        return {
            "last_command": "idle",
            "firmware_version": "unknown",
            "is_irrigating": False,
            "irrigation_mode": "sequential",
            "default_duration": 60,
        }

    async def send_command(self, command: str) -> str:
        """Send a raw command to the hub."""

        return await self._send_command(command)

    async def start_sequential(self, duration: int | None = None) -> str:
        """Start a sequential irrigation cycle."""

        encoded_duration = self._encode_duration(duration)
        return await self._send_command(f"SSH100_IRRIGSEQ {encoded_duration}")

    async def start_simultaneous(self, duration: int | None = None) -> str:
        """Start a simultaneous irrigation cycle."""

        encoded_duration = self._encode_duration(duration)
        return await self._send_command(f"SSH100_IRRIGSIM {encoded_duration}")

    async def stop_irrigation(self) -> str:
        """Stop the currently running irrigation cycle."""

        return await self._send_command("SSH100_SBP_STOPCYCLE")

    async def _send_command(self, command: str) -> str:
        """Send a command and return the hub response payload."""

        await self.connect()
        assert self._reader is not None
        assert self._writer is not None

        await self._wait_for_ready()

        command_payload = command
        if self.pin:
            command_payload = f"{command_payload} {self.pin}"

        self._writer.write(f"{command_payload}\n".encode("utf-8"))
        await self._writer.drain()

        payload: str | None = None
        while True:
            try:
                line = await asyncio.wait_for(self._reader.readline(), timeout=5)
            except (OSError, asyncio.TimeoutError) as err:
                raise SamclaConnectionError("Timed out while waiting for a hub response") from err

            if not line:
                break

            line_text = line.decode("utf-8", errors="replace").strip()
            if not line_text:
                continue

            if line_text == "OK":
                return payload or ""
            if line_text == "ERR":
                raise SamclaConnectionError("Hub returned an error response")
            if line_text == "INVALIDPIN":
                raise SamclaAuthError("The hub rejected the configured PIN")
            if "READY" in line_text.upper():
                continue

            payload = line_text

        return payload or ""

    async def _wait_for_ready(self) -> None:
        """Wait until the hub sends a ready prompt."""

        assert self._reader is not None

        while True:
            try:
                line = await asyncio.wait_for(self._reader.readline(), timeout=5)
            except (OSError, asyncio.TimeoutError) as err:
                raise SamclaConnectionError("Timed out waiting for hub READY prompt") from err

            if not line:
                raise SamclaConnectionError("The hub closed the connection before sending READY")

            line_text = line.decode("utf-8", errors="replace").strip()
            if not line_text:
                continue
            if "READY" in line_text.upper():
                return

    @staticmethod
    def _encode_duration(duration: int | None) -> str:
        """Encode a duration in tenths of seconds as hexadecimal."""

        seconds = max(1, int(duration or 60))
        return f"{seconds * 10:X}"
