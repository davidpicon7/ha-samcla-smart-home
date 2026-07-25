"""SAMCLA TCP/TLS protocol client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import ssl
from typing import TYPE_CHECKING

from .const import (
    AP_CONNECT_DELAY,
    BIT_IO_EVEON,
    BIT_IO_LIMIT_EXCEED,
    BIT_IO_NOPROG,
    CLOUD_PORT,
    CMD_IRRIGSEQ,
    CMD_IRRIGSIM,
    CMD_PUSH_CHECKJOB,
    CMD_PUTJOB,
    CMD_STATS,
    CMD_STOPCYCLE,
    LINE_ERR,
    LINE_INVALID_PIN,
    LINE_OK,
    LINE_READY,
    LOCAL_AP_PAYLOAD_PREFIX,
    SAMCLA_AP_HOST,
    SIMULTANEOUS_PLACEHOLDER_SUFFIX,
    SOCKET_TIMEOUT,
    VALID_VALVE_COUNTS,
)
from .exceptions import SamclaAuthError, SamclaCommandError, SamclaConnectionError, SamclaError
from .models import SamclaDeviceStatus

if TYPE_CHECKING:
    from asyncio import StreamReader, StreamWriter

_LOGGER = logging.getLogger(__name__)


def _create_ssl_context() -> ssl.SSLContext:
    """Build a TLS 1.2 client context matching the Android app."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context


def _encode_duration(seconds: int) -> str:
    """Convert seconds to the 4-digit hex duration field used by the hub."""

    if seconds < 10:
        return "0000"
    tenths = seconds // 10
    return f"{tenths & 0xFFFF:04x}"


def _normalize_payload(raw: str, *, host: str) -> str:
    """Strip transport-specific prefixes from a hub payload."""

    payload = raw.strip()
    prefix = f"{LOCAL_AP_PAYLOAD_PREFIX};"
    if host == SAMCLA_AP_HOST and payload.startswith(prefix):
        return payload[len(prefix) :]
    return payload


def _extract_payload_line(lines: list[str]) -> str | None:
    """Return the last payload line before a terminal OK, matching the Android client."""

    for line in reversed(lines):
        if line in {LINE_OK, LINE_ERR}:
            continue
        return line
    return None


def _parse_device_status(raw_payload: str) -> SamclaDeviceStatus:
    """Parse a semicolon-delimited hex status payload."""

    parts = raw_payload.split(";")
    if len(parts) < 4:
        msg = f"Unexpected payload format: {raw_payload!r}"
        raise SamclaCommandError(msg)

    try:
        battery = int(parts[1], 16)
        io_byte = int(parts[2], 16)
        firmware = int(parts[3], 16)
    except ValueError as err:
        msg = f"Invalid hex fields in payload: {raw_payload!r}"
        raise SamclaCommandError(msg) from err

    return SamclaDeviceStatus(
        battery=battery,
        io_byte=io_byte,
        firmware=firmware,
        raw_payload=raw_payload,
        programmed_on_box=(io_byte & BIT_IO_NOPROG) == 0,
        is_irrigating=bool(io_byte & BIT_IO_EVEON),
        limit_exceeded=bool(io_byte & BIT_IO_LIMIT_EXCEED),
    )


def _validate_valve_count(valve_count: int) -> None:
    """Ensure the configured valve count matches supported hardware."""

    if valve_count not in VALID_VALVE_COUNTS:
        msg = f"Unsupported valve count {valve_count}; expected one of {VALID_VALVE_COUNTS}"
        raise SamclaError(msg)


def _build_stop_payload(valve_count: int) -> str:
    """Build a zero-duration sequential payload that stops irrigation."""

    _validate_valve_count(valve_count)
    return ";".join(["0000"] * valve_count)


def _build_sequential_payload(durations: list[int], valve_count: int) -> str:
    """Build a sequential irrigation payload for the configured valve count."""

    _validate_valve_count(valve_count)
    fields = [_encode_duration(duration) for duration in durations[:valve_count]]
    if len(fields) < valve_count:
        fields.extend(["0000"] * (valve_count - len(fields)))
    return ";".join(fields)


def _build_simultaneous_payload(duration_seconds: int, valve_mask: int) -> str:
    """Build a simultaneous irrigation payload."""

    duration_field = _encode_duration(duration_seconds)
    mask_field = f"{valve_mask & 0xFFFF:04x}"
    return f"{duration_field};{mask_field};{SIMULTANEOUS_PLACEHOLDER_SUFFIX}"


@dataclass(slots=True)
class SamclaApiClient:
    """Async client for the SAMCLA line-oriented TLS protocol."""

    host: str
    port: int
    pin: str | None = None
    device_psn: str = ""
    hub_psn: str | None = None
    hub_mac_rf: str | None = None
    valve_count: int = 4

    async def connect(self) -> None:
        """Validate client configuration.

        The Android app opens a fresh TLS socket per command, so there is no
        persistent connection to keep alive between coordinator updates.
        """

        self._require_device_psn()

    async def disconnect(self) -> None:
        """No-op: each command manages its own TLS session."""

    async def get_status(self) -> dict[str, object]:
        """Return a parsed status payload from the hub."""

        command = f"{CMD_STATS} {self.device_psn}"
        raw = await self.send_command(command)
        status = _parse_device_status(_normalize_payload(raw, host=self.host))
        return {
            "battery": status.battery,
            "firmware_version": str(status.firmware),
            "io_byte": status.io_byte,
            "is_irrigating": status.is_irrigating,
            "programmed_on_box": status.programmed_on_box,
            "limit_exceeded": status.limit_exceeded,
            "raw_payload": status.raw_payload,
            "last_command": command,
        }

    async def send_command(self, command: str) -> str:
        """Send a raw command and return the hub payload line."""

        if self._uses_cloud_relay():
            return await self._execute_cloud_command(command)
        return await self._execute_local_command(command)

    async def start_sequential(
        self,
        duration: int | None = None,
        *,
        durations: list[int] | None = None,
    ) -> str:
        """Start a sequential irrigation cycle."""

        if durations is None:
            if duration is None:
                msg = "Either duration or durations must be provided"
                raise SamclaError(msg)
            durations = [duration]

        payload = _build_sequential_payload(durations, self.valve_count)
        command = f"{CMD_IRRIGSEQ} {self.device_psn} {payload}"
        raw = await self.send_command(command)
        return _normalize_payload(raw, host=self.host)

    async def start_simultaneous(
        self,
        duration: int | None = None,
        *,
        valve_mask: int = 1,
    ) -> str:
        """Start a simultaneous irrigation cycle."""

        if duration is None:
            msg = "Duration must be provided for simultaneous irrigation"
            raise SamclaError(msg)

        payload = _build_simultaneous_payload(duration, valve_mask)
        command = f"{CMD_IRRIGSIM} {self.device_psn} {payload}"
        raw = await self.send_command(command)
        return _normalize_payload(raw, host=self.host)

    async def stop_irrigation(self) -> str:
        """Stop the currently running irrigation cycle."""

        payload = _build_stop_payload(self.valve_count)
        command = f"{CMD_IRRIGSEQ} {self.device_psn} {payload}"
        raw = await self.send_command(command)
        return _normalize_payload(raw, host=self.host)

    async def stop_cycle(self) -> str:
        """Send the dedicated stop-cycle command."""

        command = f"{CMD_STOPCYCLE} {self.device_psn}"
        raw = await self.send_command(command)
        return _normalize_payload(raw, host=self.host)

    def _uses_cloud_relay(self) -> bool:
        """Return True when commands must go through the cloud relay."""

        return (
            self.port == CLOUD_PORT
            and bool(self.pin)
            and bool(self.hub_psn)
            and bool(self.hub_mac_rf)
        )

    def _require_device_psn(self) -> None:
        """Ensure the target device PSN is configured."""

        if not self.device_psn:
            msg = "device_psn must be configured before communicating with the hub"
            raise SamclaError(msg)

    def _cloud_credentials(self) -> tuple[str, str, str]:
        """Return cloud relay credentials."""

        if not self.pin or not self.hub_psn or not self.hub_mac_rf:
            msg = "Cloud relay requires pin, hub_psn, and hub_mac_rf"
            raise SamclaError(msg)
        return self.hub_psn, self.pin, self.hub_mac_rf

    async def _execute_local_command(self, command: str) -> str:
        """Run a single local TLS exchange."""

        if self.host == SAMCLA_AP_HOST:
            await asyncio.sleep(AP_CONNECT_DELAY)

        lines = await self._exchange(command)
        return self._finalize_exchange(lines)

    async def _execute_cloud_command(self, device_command: str) -> str:
        """Run the two-phase cloud PUTJOB / PUSH_CHECKJOB exchange."""

        hub_psn, pin, hub_mac_rf = self._cloud_credentials()
        put_command = f"{CMD_PUTJOB} {hub_psn}{pin} {hub_mac_rf} {device_command}"
        check_command = f"{CMD_PUSH_CHECKJOB} {hub_psn}{pin} {hub_mac_rf}"

        put_lines = await self._exchange(put_command)
        intermediate = self._finalize_exchange(put_lines, allow_empty=True)
        poll_command = f"{check_command} {intermediate}" if intermediate else check_command

        check_lines = await self._exchange(poll_command)
        payload = self._finalize_exchange(check_lines)
        if intermediate:
            return f"{intermediate};{payload}"
        return payload

    async def _exchange(self, command: str) -> list[str]:
        """Open TLS, wait for READY, send the command, and collect response lines."""

        ssl_context = _create_ssl_context()
        reader: StreamReader
        writer: StreamWriter

        try:
            async with asyncio.timeout(SOCKET_TIMEOUT):
                reader, writer = await asyncio.open_connection(
                    self.host,
                    self.port,
                    ssl=ssl_context,
                    server_hostname=self.host,
                )
        except TimeoutError as err:
            msg = f"Timed out connecting to {self.host}:{self.port}"
            raise SamclaConnectionError(msg) from err
        except OSError as err:
            msg = f"Unable to connect to {self.host}:{self.port}: {err}"
            raise SamclaConnectionError(msg) from err

        lines: list[str] = []
        command_sent = False

        try:
            while True:
                try:
                    async with asyncio.timeout(SOCKET_TIMEOUT):
                        raw_line = await reader.readline()
                except TimeoutError as err:
                    msg = f"Timed out waiting for hub response to {command!r}"
                    raise SamclaConnectionError(msg) from err

                if not raw_line:
                    break

                line = raw_line.decode(errors="replace").strip()
                if not line:
                    continue

                lines.append(line)
                _LOGGER.debug("Samcla line: %s", line)

                if line == LINE_INVALID_PIN:
                    raise SamclaAuthError("Hub rejected the configured PIN")

                if LINE_READY in line and not command_sent:
                    writer.write(f"{command}\n".encode())
                    await writer.drain()
                    command_sent = True
                    continue

                if line == LINE_ERR:
                    msg = f"Hub returned ERR for command {command!r}"
                    raise SamclaCommandError(msg)

                if line == LINE_OK:
                    break
        finally:
            writer.close()
            await writer.wait_closed()

        if not command_sent:
            msg = f"Hub did not send READY before closing connection for {command!r}"
            raise SamclaConnectionError(msg)

        return lines

    def _finalize_exchange(self, lines: list[str], *, allow_empty: bool = False) -> str:
        """Extract the payload line from a completed hub exchange."""

        payload = _extract_payload_line(lines)
        if payload is None:
            if allow_empty:
                return ""
            msg = "Hub completed the exchange without returning a payload"
            raise SamclaCommandError(msg)
        return payload
