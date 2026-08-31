"""Domain exceptions for the Operations Copilot.

A small, explicit exception hierarchy keeps error handling predictable:
the agent and the API layer can map any ``CopilotError`` onto a clean user
message and an appropriate HTTP status code, while unexpected exceptions
are logged and surfaced as generic failures.
"""

from __future__ import annotations


class CopilotError(Exception):
    """Base class for every error raised by the copilot."""


class ValidationError(CopilotError, ValueError):
    """Raised when user supplied input fails validation.

    Also subclasses :class:`ValueError` so that callers written against
    plain Python semantics (``except ValueError``) keep working.
    """


class ShipmentNotFoundError(CopilotError):
    """Raised when a shipment identifier is not present in the data source."""


class PolicyNotFoundError(CopilotError):
    """Raised when no policy matches the requested topic."""


class ToolExecutionError(CopilotError):
    """Raised when a tool fails for an unexpected, non-validation reason."""
