# OURSELF Signal Boot

Before repository inspection or mutation:
1. Scan the incoming WORKFLOWEXECUTIONSPEECH for exact `*_SIGNAL` markers.
2. Resolve by priority: `STOP_SIGNAL`, `AUTHORITY_SIGNAL`, `OPERATING_SIGNAL`, `OBJECTIVE_SIGNAL`, `INSPECTION_SIGNAL`, `MUTATION_SIGNAL`, `VERIFICATION_SIGNAL`, `SEAL_SIGNAL`, `FOUNDATION_SIGNAL`.
3. Announce `CONTROLLING_SIGNAL: <name>` before reading project files.
4. No known marker: return `UNCLASSIFIED_SIGNAL` and stop before inspection.
5. Unknown marker: return `UNKNOWN_SIGNAL` and fail closed.
6. `STOP_SIGNAL` overrides all signals. `SEAL_SIGNAL` and `FOUNDATION_SIGNAL` never grant mutation authority.

Use `OPERATING_SIGNAL` for session-posture, context-budget, archaeology-limit, or execution-mode shifts.
Canonical contract: `situaedmilly/self-protocol-suite/specifications/WORKFLOW-EXECUTION-SIGNAL-HIERARCHY-v1.md`.
