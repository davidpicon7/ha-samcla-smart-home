"""Binary sensor entities for the Samcla integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .coordinator import SamclaCoordinator
from .entity import SamclaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Samcla binary sensors."""

    coordinator = entry.runtime_data.coordinator
    async_add_entities([SamclaIrrigatingBinarySensor(coordinator)])


class SamclaIrrigatingBinarySensor(SamclaEntity, BinarySensorEntity):
    """Indicate whether irrigation is currently running."""

    def __init__(self, coordinator: SamclaCoordinator) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_irrigating"
        self._attr_name = "Irrigating"

    @property
    def is_on(self) -> bool:
        """Return whether irrigation is active."""

        return self.coordinator.data.is_irrigating
