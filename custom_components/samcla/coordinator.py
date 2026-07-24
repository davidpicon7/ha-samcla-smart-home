"""Coordinator for Samcla state updates."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SamclaApiClient
from .models import SamclaCoordinatorData

_LOGGER = logging.getLogger(__name__)


class SamclaCoordinator(DataUpdateCoordinator[SamclaCoordinatorData]):
    """Coordinate Samcla state updates."""

    def __init__(self, hass: HomeAssistant, api_client: SamclaApiClient, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.api_client = api_client
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="samcla",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> SamclaCoordinatorData:
        """Fetch data from the API client."""

        try:
            await self.api_client.connect()
            status = await self.api_client.get_status()
            return SamclaCoordinatorData(
                connected=True,
                last_command=str(status.get("last_command", "idle")),
                firmware_version=str(status.get("firmware_version", "unknown")),
                is_irrigating=bool(status.get("is_irrigating", False)),
                irrigation_mode=str(status.get("irrigation_mode", "sequential")),
                default_duration=int(status.get("default_duration", 60)),
            )
        except NotImplementedError as err:
            return SamclaCoordinatorData()
        except Exception as err:
            raise UpdateFailed(f"Unable to update Samcla data: {err}") from err
        finally:
            await self.api_client.disconnect()
