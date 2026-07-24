"""Public API client interface for Samcla."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import SamclaConnectionError


@dataclass(slots=True)
class SamclaApiClient:
    """Thin client interface for the SAMCLA TCP/SSL protocol."""

    host: str
    port: int
    pin: str | None = None

    async def connect(self) -> None:
        """Open a connection to the hub."""

        raise NotImplementedError("Protocol implementation pending")

    async def disconnect(self) -> None:
        """Close the current connection."""

        raise NotImplementedError("Protocol implementation pending")

    async def get_status(self) -> dict[str, object]:
        """Return a status payload from the hub."""

        raise NotImplementedError("Protocol implementation pending")

    async def send_command(self, command: str) -> str:
        """Send a raw command to the hub."""

        raise NotImplementedError("Protocol implementation pending")

    async def start_sequential(self, duration: int | None = None) -> str:
        """Start a sequential irrigation cycle."""

        raise NotImplementedError("Protocol implementation pending")

    async def start_simultaneous(self, duration: int | None = None) -> str:
        """Start a simultaneous irrigation cycle."""

        raise NotImplementedError("Protocol implementation pending")

    async def stop_irrigation(self) -> str:
        """Stop the currently running irrigation cycle."""

        raise NotImplementedError("Protocol implementation pending")
