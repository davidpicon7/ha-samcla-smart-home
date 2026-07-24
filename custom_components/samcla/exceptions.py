"""Exceptions for the Samcla integration."""

from __future__ import annotations


class SamclaError(Exception):
    """Base exception for Samcla errors."""


class SamclaConnectionError(SamclaError):
    """Raised when the hub cannot be reached."""


class SamclaAuthError(SamclaError):
    """Raised when the Hub PIN is rejected."""
