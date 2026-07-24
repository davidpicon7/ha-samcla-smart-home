"""Number entities for the Samcla integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .coordinator import SamclaCoordinator
from .entity import SamclaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Samcla number entities."""

    coordinator = entry.runtime_data.coordinator
    async_add_entities([SamclaDurationNumber(coordinator)])


class SamclaDurationNumber(SamclaEntity, NumberEntity):
    """Expose a default irrigation duration."""

    _attr_native_min_value = 1
    _attr_native_max_value = 3600
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator: SamclaCoordinator) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_default_duration"
        self._attr_name = "Default irrigation duration"

    @property
    def native_value(self) -> int:
        """Return the current value."""

        return self.coordinator.data.default_duration

    async def async_set_native_value(self, value: float) -> None:
        """Handle updates to the value."""

        self.coordinator.data.default_duration = int(value)
        self.async_write_ha_state()
