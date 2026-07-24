"""Base entity for Samcla."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import SamclaCoordinator


class SamclaEntity(Entity):
    """Base entity for Samcla entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SamclaCoordinator) -> None:
        """Initialize the entity."""

        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="Samcla Hub",
            manufacturer="SAMCLA",
            model="Smart Home Hub",
            sw_version=self.coordinator.data.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""

        return self.coordinator.last_update_success
