"""Sensor entities for the Samcla integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .coordinator import SamclaCoordinator
from .entity import SamclaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Samcla sensor entities."""

    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            SamclaSensor(coordinator, "connection_status", "Connection status"),
            SamclaSensor(coordinator, "last_command", "Last command"),
            SamclaSensor(coordinator, "firmware_version", "Firmware version"),
        ]
    )


class SamclaSensor(SamclaEntity, SensorEntity):
    """A generic Samcla sensor."""

    def __init__(self, coordinator: SamclaCoordinator, key: str, name: str) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._key = key

    @property
    def native_value(self) -> str | bool:
        """Return the current value."""

        if self._key == "connection_status":
            return self.coordinator.data.connected
        if self._key == "last_command":
            return self.coordinator.data.last_command
        return self.coordinator.data.firmware_version
