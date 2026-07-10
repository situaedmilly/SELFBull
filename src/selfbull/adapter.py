"""selfbull.adapter — SELFBULL-001 · the Webull broker-surface adapter, Phase 1.

No HTTP call exists anywhere in this module. No credential value is ever
read into a variable that gets logged or returned — only presence booleans
and an at-most-4-character App Key ID preview leave `check_credentials()`.

This module imports nothing from `selfquant` or `rbhcb`. It carries no
governor, no Constitution, no gate ladder — SELFQUANT alone judges whether
a `PreparedOrderIntent` may ever advance. SELFBull's own kill switch here is
a *second, independent* refusal layer, never a replacement for that
judgment.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from selfbull.audit import log_event
from selfbull.contracts import (
    BrokerCapabilitySnapshot,
    PreparedOrderIntent,
    TransportStatus,
    WebullCredentialCheck,
    WebullCredentialConfig,
    WebullInstrumentType,
    WebullOrderSide,
    WebullOrderTIF,
    WebullOrderType,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SENTINEL = REPO_ROOT / "selfbull" / "STOP"
STOP_ENV_VAR = "SELFBULL_STOP"

# Phase 1 read-plane method names. None performs a network call.
READ_ONLY_METHODS = frozenset({"get_account_list", "get_account_balance", "get_quote"})

PHASE1_CAPABILITIES: List[str] = [
    "config_shape_validation",
    "credential_presence_check",
    "paper_order_representation",
    "audit_safe_event_records",
    "live_transport_refusal",
    "broker_capability_discovery",
]


class AdapterQuarantineError(RuntimeError):
    """Raised whenever a caller reaches for a surface Phase 1 does not
    implement — read access before a gate clears, or any live-transport verb."""


def kill_switch_active() -> bool:
    """SELFBull's own, independent kill switch. Checked before every
    adapter action. Separate from — never a substitute for — SELFQUANT's
    kill switches."""
    if STOP_SENTINEL.exists():
        return True
    return os.environ.get(STOP_ENV_VAR, "").strip().lower() in ("1", "true", "yes")


def check_credentials(config: Optional[WebullCredentialConfig] = None) -> WebullCredentialCheck:
    """Presence-only check. Reads the two env vars NAMED by `config`,
    returns only present/missing plus an at-most-4-char App Key ID preview.
    The App Key Secret gets no preview at all."""
    cfg = config or WebullCredentialConfig()
    app_key_id = os.environ.get(cfg.app_key_id_env)
    app_key_secret = os.environ.get(cfg.app_key_secret_env)
    prefix = None
    if app_key_id:
        prefix = f"{app_key_id[:4]}…" if len(app_key_id) > 4 else app_key_id
    return WebullCredentialCheck(
        app_key_id_present=bool(app_key_id),
        app_key_secret_present=bool(app_key_secret),
        app_key_id_prefix=prefix,
    )


def validate_config_shape(config: Optional[WebullCredentialConfig] = None) -> List[str]:
    """Shape-only validation of the credential config — env var NAMES are
    well-formed and distinct. Never inspects a secret value."""
    cfg = config or WebullCredentialConfig()
    errors: List[str] = []
    if not cfg.app_key_id_env or not isinstance(cfg.app_key_id_env, str):
        errors.append("app_key_id_env must be a non-empty string")
    if not cfg.app_key_secret_env or not isinstance(cfg.app_key_secret_env, str):
        errors.append("app_key_secret_env must be a non-empty string")
    if cfg.app_key_id_env == cfg.app_key_secret_env:
        errors.append("app_key_id_env and app_key_secret_env must not be the same variable")
    if cfg.environment not in ("sandbox", "production"):
        errors.append(f"environment must be 'sandbox' or 'production', got {cfg.environment!r}")
    return errors


class WebullAdapter:
    """The Phase 1 broker-surface adapter. Read methods raise
    NotImplementedError. The order path either represents a simulated
    intent or refuses — there is no method here, public or private, that
    can place, cancel, replace, or transfer a real order."""

    def __init__(self, config: Optional[WebullCredentialConfig] = None):
        self.config = config or WebullCredentialConfig()
        self.live_transport_enabled = False   # Phase 1: always False, no setter exposed

    # ── Read-only plane (Phase 1: inert stubs, no network) ───────────────
    def get_account_list(self):
        raise NotImplementedError(
            "Phase 1 stub — no network call implemented. Requires a "
            "separately authorized Phase 2 before any HTTP call exists."
        )

    def get_account_balance(self, account_id: str):
        raise NotImplementedError(
            "Phase 1 stub — no network call implemented. Requires a "
            "separately authorized Phase 2 before any HTTP call exists."
        )

    def get_quote(self, symbol: str):
        raise NotImplementedError(
            "Phase 1 stub — no network call implemented. Requires a "
            "separately authorized Phase 2 before any HTTP call exists."
        )

    # ── Prepared (paper) order representation ────────────────────────────
    def create_prepared_order_intent(
        self,
        *,
        instrument: str,
        asset_class: WebullInstrumentType,
        side: WebullOrderSide,
        order_type: WebullOrderType,
        quantity: float,
        time_in_force: WebullOrderTIF = WebullOrderTIF.DAY,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None,
        source_decision_id: Optional[str] = None,
        human_approval_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        log: bool = True,
    ) -> PreparedOrderIntent:
        """Represent an order intent as a local, simulated object. Never
        touches the network. `human_approval_id` is recorded as evidence
        only — it never flips `execution_authority`, which is always False
        and not settable via this or any other constructor."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        status = TransportStatus.BLOCKED if kill_switch_active() else TransportStatus.SIMULATED
        intent = PreparedOrderIntent(
            broker="webull",
            instrument=instrument,
            asset_class=asset_class,
            side=side,
            order_type=order_type,
            quantity=quantity,
            time_in_force=time_in_force,
            transport_status=status,
            created_at=ts,
            limit_price=limit_price,
            stop_price=stop_price,
            extended_hours=extended_hours,
            client_order_id=client_order_id,
            source_decision_id=source_decision_id,
            human_approval_id=human_approval_id,
        )
        if log:
            log_event({
                "timestamp": ts, "adapter": "webull", "event": "prepared_order_intent_created",
                "intent_id": intent.intent_id, "instrument": instrument, "side": side.value,
                "quantity": quantity, "transport_status": status.value,
                "execution_authority": intent.execution_authority,
            })
        return intent

    # ── Live transport verbs: no implementation exists — refuse always ──
    def submit(self, *_args, **_kwargs):
        raise AdapterQuarantineError(
            "SELFBull has no submit-order transport in Phase 1. Refused by construction."
        )

    def cancel(self, *_args, **_kwargs):
        raise AdapterQuarantineError(
            "SELFBull has no cancel-order transport in Phase 1. Refused by construction."
        )

    def replace(self, *_args, **_kwargs):
        raise AdapterQuarantineError(
            "SELFBull has no replace-order transport in Phase 1. Refused by construction."
        )

    def transfer(self, *_args, **_kwargs):
        raise AdapterQuarantineError(
            "SELFBull has no fund-transfer transport in Phase 1. Refused by construction."
        )

    # ── Broker capability discovery (Phase 2 of the interface contract) ──
    def build_capability_snapshot(
        self, *, adapter_version: str = "0.1.0", timestamp: Optional[str] = None,
    ) -> BrokerCapabilitySnapshot:
        creds = check_credentials(self.config)
        return BrokerCapabilitySnapshot(
            broker="webull",
            adapter_version=adapter_version,
            observed_at=timestamp or datetime.now(timezone.utc).isoformat(),
            environment=self.config.environment,
            capabilities=list(PHASE1_CAPABILITIES),
            live_transport_available=False,
            live_transport_enabled=self.live_transport_enabled,
            kill_switch_active=kill_switch_active(),
            credential_state=creds.to_json_dict(),
            evidence={"phase": 1, "network_call": False},
        )
