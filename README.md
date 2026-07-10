# SELFBull

**SELFBull is not a trading bot. SELFBull is a broker interface temple.**
The hand does not execute until the crown authorizes.

SELFBull is the quarantined, standalone Webull Open API broker-surface
adapter for the SELF ecosystem. It is a **hand**, not a **crown**: it
understands Webull's documented vocabulary and produces broker-neutral
facts and prepared order intents. It never decides whether an intent may
advance — that judgment belongs entirely to SELFQUANT's Agent Constitution
(`governed_decision()`), which this repository does not import, vendor, or
duplicate.

See `docs/SELFBULL-INTERFACE-CONTRACT.md` for the cross-repo JSON contract
and `docs/SELFBULL-PHASE1-SPEC.md` for exactly what Phase 1 does and does
not do.

## Phase 1, in one line

Offline. Unauthenticated. Non-networked. Non-executing. Independently
testable. Contract-driven. Standard-library only.

## Boundary law

- SELFBull MUST NOT import SELFQUANT.
- SELFQUANT MUST NOT be vendored, copied, or included as a submodule here.
- SELFBull MUST NOT implement a second governor, Constitution,
  execution-authority engine, or gate ladder.
- SELFQUANT remains the sole authority plane. SELFBull is a broker-surface
  organ only.

## Running the tests

```
python3 -m unittest discover -s tests -v
```

No `pytest`, no third-party dependency, no network call — by construction.
