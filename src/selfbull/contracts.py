"""selfbull.contracts — SELFBULL-001 · the typed vocabulary, Phase 1.

Two layers live here:

1. Webull-documented vocabulary (order side/type/TIF/instrument/account
   type/market/currency) — copied from the official
   `webull-inc/webull-openapi-python-sdk` source, inspected read-only at
   ~/Projects/_reference/webull-openapi-python-sdk (2026-07-09). Not
   vendored, not a dependency, not imported by this package at runtime.

2. The cross-repo JSON envelopes named in docs/SELFBULL-INTERFACE-CONTRACT.md
   (BrokerCapabilitySnapshot, MarketObservationEnvelope,
   AccountObservationEnvelope, PreparedOrderIntent). These are the only
   objects SELFQUANT will ever see from SELFBull — as JSON, never as a
   shared Python class.

This module holds NO logic beyond serialization helpers, and NO network
call. Standard library only: dataclasses, enum, typing.

Where the SDK does not define a typed response shape (account balance and
position fields are built by request objects only — no response dataclass
exists in the inspected source), this module carries the value as an opaque
dict/list rather than inventing field names.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"


# ─── Webull-documented vocabulary (source: webull-inc/webull-openapi-python-sdk) ───
class WebullOrderSide(str, Enum):
    """webull/trade/common/order_side.py"""
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"


class WebullOrderType(str, Enum):
    """webull/trade/common/order_type.py — NOTE: no LIMIT_ON_OPEN member
    exists in the SDK; an earlier documentation-page draft assumed one."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TRAILING_STOP_LOSS = "TRAILING_STOP_LOSS"
    ENHANCED_LIMIT = "ENHANCED_LIMIT"
    AT_AUCTION = "AT_AUCTION"
    AT_AUCTION_LIMIT = "AT_AUCTION_LIMIT"
    ODD_LOT_LIMIT = "ODD_LOT_LIMIT"
    MARKET_ON_OPEN = "MARKET_ON_OPEN"
    MARKET_ON_CLOSE = "MARKET_ON_CLOSE"


class WebullOrderTIF(str, Enum):
    """webull/trade/common/order_tif.py"""
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"


class WebullOrderStatus(str, Enum):
    """webull/trade/common/order_status.py — NOTE: no WORKING member exists
    in the SDK; SUBMITTED is the correct pre-fill status. Documented here
    for vocabulary completeness; Phase 1 never produces a real order status
    because no order is ever submitted."""
    SUBMITTED = "SUBMITTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    FILLED = "FILLED"
    PARTIAL_FILLED = "PARTIAL_FILLED"


class WebullInstrumentType(str, Enum):
    """webull/trade/common/instrument_type.py — NOTE: no EQUITY member
    exists in the SDK; STOCK is correct. An earlier documentation-page draft
    assumed EQUITY, which is not a real value."""
    STOCK = "STOCK"
    ETF = "ETF"
    UNIT = "UNIT"
    WARRANT = "WARRANT"
    RIGHT = "RIGHT"
    CALL_OPTION = "CALL_OPTION"
    PUT_OPTION = "PUT_OPTION"


class WebullAccountType(str, Enum):
    """webull/trade/common/account_type.py"""
    MARGIN = "MARGIN"
    CASH = "CASH"


class WebullMarket(str, Enum):
    """webull/trade/common/markets.py"""
    US = "US"
    HK = "HK"
    JP = "JP"


class WebullCurrency(str, Enum):
    """webull/trade/common/currency.py"""
    CNH = "CNH"
    CAD = "CAD"
    HKD = "HKD"
    USD = "USD"


class WebullEntrustType(str, Enum):
    """webull/trade/common/order_entrust_type.py"""
    QTY = "QTY"
    AMOUNT = "AMOUNT"


class TransportStatus(str, Enum):
    """Phase 1 has exactly three members. There is no live/submitted
    member — a live-submission status structurally cannot exist yet."""
    SIMULATED = "simulated"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


# ─── Credential shape (local — never transmitted, never logged whole) ───
@dataclass(frozen=True)
class WebullCredentialConfig:
    """Names the two env vars SELFBull reads for the SDK's
    AppKeyCredential(app_key_id, app_key_secret). Holds variable NAMES
    only, never values."""
    app_key_id_env: str = "SELFBULL_WEBULL_APP_KEY_ID"
    app_key_secret_env: str = "SELFBULL_WEBULL_APP_KEY_SECRET"
    environment: str = "sandbox"   # "sandbox" | "production"


@dataclass(frozen=True)
class WebullCredentialCheck:
    """Result of a presence check. Never carries a secret value.
    `app_key_id_prefix` is at most a 4-character preview of the App Key ID
    only — the App Key Secret gets no preview at all, present/missing only."""
    app_key_id_present: bool
    app_key_secret_present: bool
    app_key_id_prefix: Optional[str] = None

    @property
    def both_present(self) -> bool:
        return self.app_key_id_present and self.app_key_secret_present

    def to_json_dict(self) -> dict:
        return {
            "app_key_id_present": self.app_key_id_present,
            "app_key_secret_present": self.app_key_secret_present,
            "app_key_id_prefix": self.app_key_id_prefix,
        }


# ─── Cross-repo envelope: BrokerCapabilitySnapshot ──────────────────────
@dataclass(frozen=True)
class BrokerCapabilitySnapshot:
    broker: str
    adapter_version: str
    observed_at: str
    environment: str
    capabilities: List[str]
    live_transport_available: bool
    live_transport_enabled: bool
    kill_switch_active: bool
    credential_state: Dict[str, Any]
    evidence: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "broker": self.broker,
            "adapter_version": self.adapter_version,
            "observed_at": self.observed_at,
            "environment": self.environment,
            "capabilities": list(self.capabilities),
            "live_transport_available": self.live_transport_available,
            "live_transport_enabled": self.live_transport_enabled,
            "kill_switch_active": self.kill_switch_active,
            "credential_state": dict(self.credential_state),
            "evidence": dict(self.evidence),
        }


# ─── Cross-repo envelope: MarketObservationEnvelope ─────────────────────
@dataclass(frozen=True)
class MarketObservationEnvelope:
    broker: str
    observed_at: str
    instrument: Dict[str, Any]
    source: str
    quote: Optional[Dict[str, Any]] = None
    session: Optional[str] = None
    freshness: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "broker": self.broker,
            "observed_at": self.observed_at,
            "instrument": dict(self.instrument),
            "quote": self.quote,
            "session": self.session,
            "source": self.source,
            "freshness": self.freshness,
            "evidence": dict(self.evidence),
        }


# ─── Cross-repo envelope: AccountObservationEnvelope ────────────────────
@dataclass(frozen=True)
class AccountObservationEnvelope:
    broker: str
    observed_at: str
    account_ref: Dict[str, Any]
    restrictions: List[str] = field(default_factory=list)
    balances: Optional[Dict[str, Any]] = None
    positions: Optional[List[Any]] = None
    open_orders: Optional[List[Any]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "broker": self.broker,
            "observed_at": self.observed_at,
            "account_ref": dict(self.account_ref),
            "balances": self.balances,
            "positions": self.positions,
            "open_orders": self.open_orders,
            "restrictions": list(self.restrictions),
            "evidence": dict(self.evidence),
        }


# ─── Cross-repo envelope: PreparedOrderIntent ───────────────────────────
@dataclass(frozen=True)
class PreparedOrderIntent:
    """A *request* to prepare an order — never an order until SELFQUANT
    governs it and a future transport gate independently clears.

    `execution_authority` is NOT a constructor parameter (see `init=False`
    below) — there is no public way to construct one with `True`. Frozen,
    so it also cannot be mutated after construction."""
    broker: str
    instrument: str
    asset_class: WebullInstrumentType
    side: WebullOrderSide
    order_type: WebullOrderType
    quantity: float
    time_in_force: WebullOrderTIF
    transport_status: TransportStatus
    created_at: str
    intent_id: str = field(default_factory=lambda: f"intent-{uuid.uuid4()}")
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    extended_hours: bool = False
    client_order_id: Optional[str] = None
    source_decision_id: Optional[str] = None
    human_approval_id: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    execution_authority: bool = field(default=False, init=False)

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "intent_id": self.intent_id,
            "broker": self.broker,
            "created_at": self.created_at,
            "instrument": self.instrument,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "extended_hours": self.extended_hours,
            "client_order_id": self.client_order_id,
            "source_decision_id": self.source_decision_id,
            "human_approval_id": self.human_approval_id,
            "execution_authority": self.execution_authority,
            "transport_status": self.transport_status.value,
            "evidence": dict(self.evidence),
        }
