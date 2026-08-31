"""Shared pytest configuration.

Adds the project root to ``sys.path`` so the suite runs with a bare
``pytest`` from anywhere, and resets in-process state between tests so
monitoring and escalation counters never leak across cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from monitoring.metrics import metrics  # noqa: E402
from tools.escalation import reset_escalations  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    """Reset metrics and escalations before every test."""
    metrics.reset()
    reset_escalations()
    yield
    metrics.reset()
    reset_escalations()
