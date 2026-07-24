"""Select entities for the Samcla integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .coordinator import SamclaCoordinator
from .entity import SamclaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Samcla select entities."""

    coordinator = entry.runtime_data.coordinator
    async_add_entities([SamclaModeSelect(coordinator)])


class SamclaModeSelect(SamclaEntity, SelectEntity):
    """Select the irrigation mode."""

    _attr_options = ["sequential", "simultaneous"]

    def __init__(self, coordinator: SamclaCoordinator) -> None:
        """Initialize the select entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_irrigation_mode"
        self._attr_name = "Irrigation mode"

    @property
    def current_option(self) -> str:
        """Return the current option."""

        return self.coordinator.data.irrigation_mode

    async def async_select_option(self, option: str) -> None:
        """Handle selection changes."""

        self.coordinator.data.irrigation_mode = option
        self.async_write_ha_state()
