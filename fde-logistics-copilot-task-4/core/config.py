"""Central configuration for the Logistics Operations Copilot.

Every tunable value lives here so that a Forward Deployment Engineer can
re-point the copilot at a new client by editing configuration instead of
editing business logic.  Values may be overridden with environment
variables (see ``.env.example``), which keeps the prototype runnable with
zero setup while remaining container/12-factor friendly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Final

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
LOG_DIR: Final[Path] = Path(os.getenv("COPILOT_LOG_DIR", str(BASE_DIR / "logs")))
LOG_FILE: Final[Path] = LOG_DIR / os.getenv("COPILOT_LOG_FILE", "copilot.log")

# --------------------------------------------------------------------------
# Application metadata
# --------------------------------------------------------------------------
APP_NAME: Final[str] = "Logistics Operations Copilot"
APP_VERSION: Final[str] = "1.0.0"
CLIENT_NAME: Final[str] = os.getenv("COPILOT_CLIENT_NAME", "Demo Logistics Pvt. Ltd.")
ENVIRONMENT: Final[str] = os.getenv("COPILOT_ENV", "local")
LOG_LEVEL: Final[str] = os.getenv("COPILOT_LOG_LEVEL", "INFO").upper()

# --------------------------------------------------------------------------
# Agent routing
# --------------------------------------------------------------------------
# ``rule_based`` is the deterministic router that ships with the prototype.
# ``llm`` is reserved for a future LLM-backed router (see docs/HLD.md); the
# tool contracts do not change when the router is swapped.
AGENT_MODE: Final[str] = os.getenv("COPILOT_AGENT_MODE", "rule_based")

# Shipment identifiers look like ``SH1024``.  Clients using different
# identifier formats only need to change this pattern (see
# client-customization.md, section "Shipment identifier differences").
SHIPMENT_ID_PATTERN: Final[str] = os.getenv(
    "COPILOT_SHIPMENT_ID_PATTERN", r"\b([A-Za-z]{2,4}-?\d{3,8})\b"
)

# --------------------------------------------------------------------------
# Pricing rules (prototype)
# --------------------------------------------------------------------------
# In production these values come from the client's pricing engine / rate
# card service.  They are kept here as named constants so the formula stays
# readable and auditable instead of being scattered as magic numbers.
CURRENCY: Final[str] = os.getenv("COPILOT_CURRENCY", "USD")
BASE_CHARGE: Final[float] = 50.0
WEIGHT_RATE_PER_KG: Final[float] = 10.0
DISTANCE_RATE_PER_KM: Final[float] = 0.50

PRIORITY_MULTIPLIERS: Final[Dict[str, float]] = {
    "standard": 1.0,
    "express": 1.5,
    "urgent": 2.0,
}
DEFAULT_PRIORITY: Final[str] = "standard"

# Defensive guard rails so an obvious typo (5000 kg parcel) is caught early.
MAX_WEIGHT_KG: Final[float] = 10_000.0
MAX_DISTANCE_KM: Final[float] = 20_000.0

# --------------------------------------------------------------------------
# Escalation
# --------------------------------------------------------------------------
# The assignment requires this exact phrase in every escalation response.
ESCALATION_PHRASE: Final[str] = "Escalated to Operations Team"
ESCALATION_TICKET_PREFIX: Final[str] = os.getenv("COPILOT_ESCALATION_PREFIX", "ESC")
ESCALATION_QUEUE: Final[str] = os.getenv("COPILOT_ESCALATION_QUEUE", "operations-team")

# --------------------------------------------------------------------------
# API layer (optional production interface)
# --------------------------------------------------------------------------
API_TITLE: Final[str] = f"{APP_NAME} API"
API_PREFIX: Final[str] = "/api/v1"
API_HOST: Final[str] = os.getenv("COPILOT_API_HOST", "0.0.0.0")
API_PORT: Final[int] = int(os.getenv("COPILOT_API_PORT", "8000"))
MAX_QUERY_LENGTH: Final[int] = int(os.getenv("COPILOT_MAX_QUERY_LENGTH", "500"))
