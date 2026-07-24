"""Buttons for the Samcla integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .coordinator import SamclaCoordinator
from .entity import SamclaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Samcla buttons."""

    coordinator = entry.runtime_data.coordinator
    entities = [
        SamclaButton(coordinator, "start_irrigation", "Start irrigation"),
        SamclaButton(coordinator, "stop_irrigation", "Stop irrigation"),
        SamclaButton(coordinator, "refresh_status", "Refresh status"),
    ]
    async_add_entities(entities)


class SamclaButton(SamclaEntity, ButtonEntity):
    """A generic Samcla button."""

    def __init__(self, coordinator: SamclaCoordinator, key: str, name: str) -> None:
        """Initialize the button."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._key = key

    async def async_press(self) -> None:
        """Handle button press."""

        if self._key == "refresh_status":
            await self.coordinator.async_request_refresh()
