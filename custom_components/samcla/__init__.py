"""The Samcla Smart Home integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .api import SamclaApiClient
from .const import CONF_PIN, DOMAIN
from .coordinator import SamclaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


@dataclass(slots=True)
class SamclaRuntimeData:
    """Runtime data for the integration."""

    api_client: SamclaApiClient
    coordinator: SamclaCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samcla from a config entry."""

    api_client = SamclaApiClient(
        host=cast(str, entry.data[CONF_HOST]),
        port=cast(int, entry.data[CONF_PORT]),
        pin=cast(str | None, entry.data.get(CONF_PIN)),
    )
    coordinator = SamclaCoordinator(hass=hass, api_client=api_client, entry=entry)

    entry.runtime_data = SamclaRuntimeData(api_client=api_client, coordinator=coordinator)  # type: ignore[attr-defined]

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Samcla config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None  # type: ignore[assignment]
    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""

    await hass.config_entries.async_reload(entry.entry_id)
