"""Typed data models for Samcla."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SamclaCoordinatorData:
    """State exposed by the coordinator."""

    connected: bool = False
    last_command: str = "idle"
    firmware_version: str = "unknown"
    is_irrigating: bool = False
    irrigation_mode: str = "sequential"
    default_duration: int = 60
