"""Typed data models for Samcla."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SamclaDeviceStatus:
    """Parsed status payload from the hub."""

    battery: int = 0
    io_byte: int = 0
    firmware: int = 0
    raw_payload: str = ""
    programmed_on_box: bool = False
    is_irrigating: bool = False
    limit_exceeded: bool = False


@dataclass(slots=True)
class SamclaCoordinatorData:
    """State exposed by the coordinator."""

    connected: bool = False
    last_command: str = "idle"
    firmware_version: str = "unknown"
    is_irrigating: bool = False
    irrigation_mode: str = "sequential"
    default_duration: int = 60
    battery: int = 0
    programmed_on_box: bool = False
