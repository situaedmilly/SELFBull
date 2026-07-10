"""SELFBull — quarantined, non-executing Webull broker-surface adapter.

Phase 1: offline, unauthenticated, non-networked, non-executing,
independently testable, contract-driven. Standard library only.

SELFBull is a broker-surface organ, not a second Constitution. It emits
broker-neutral facts and prepared order intents (see
docs/SELFBULL-INTERFACE-CONTRACT.md); SELFQUANT alone decides whether an
intent may advance. This package imports nothing from SELFQUANT, vendors
nothing from Webull's SDK, and makes no network call anywhere in its source.
"""
from __future__ import annotations

__version__ = "0.1.0"
