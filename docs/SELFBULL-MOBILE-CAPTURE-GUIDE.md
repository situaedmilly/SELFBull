# SELFBULL Mobile Capture Guide — manual browser observation

How to capture Webull **browser** readings by hand from Claude Code Mobile
(or any terminal) and turn them into validated observation envelopes.
Everything here runs offline: no network, no login, no credentials, no
orders, no trade advice.

## The 60-second loop

1. Look at the Webull web interface and note the values you can actually
   see (never guess a field you can't see — leave it blank).
2. Record one observation directly from the command line:

```sh
python3 -m selfbull.manual_capture single \
  --timestamp-et "2026-07-10 09:35:00" \
  --symbol SPY \
  --last-price 632.14 \
  --source webull_browser_manual \
  --notes "Opening range observation"
```

3. Read the receipt. A `valid` record is appended to
   `data/manual_observations.jsonl` (local only, gitignored). A rejected
   record prints its errors and writes nothing.

Add any optional fields you observed as extra flags — underscores become
hyphens (`--day-high 633.20 --bid 632.13 --ask 632.15 --volume 4200000
--session core` …). Skip what you didn't see; missing fields become `null`.

## Batch capture with a CSV

Keep a CSV with this exact header (copy it from
`data/examples/manual_frequency_capture.csv`):

```
timestamp_et,symbol,last_price,day_open,day_high,day_low,previous_close,volume,relative_volume,bid,ask,spread,implied_volatility,expected_move,call_wall,put_wall,largest_call_volume_strike,largest_put_volume_strike,session,source,notes
```

Then:

```sh
# Check the rows without writing anything:
python3 -m selfbull.manual_capture validate --file my_capture.csv

# Rehearse the ingest (builds receipts, writes nothing):
python3 -m selfbull.manual_capture ingest --file my_capture.csv --dry-run

# Append the rows to the local store:
python3 -m selfbull.manual_capture ingest --file my_capture.csv
```

A batch with **any** invalid row writes **zero** rows — fix the reported
row and re-run. Repeated ingests append; nothing already stored is ever
rewritten. Add `--json` to any command for machine-readable output.

## Field-by-field capture tips

| Field | Tip |
|---|---|
| `timestamp_et` | The moment you looked, Eastern Time, `YYYY-MM-DD HH:MM:SS`. Don't backfill from memory hours later without saying so in `notes`. |
| `symbol` | As displayed; case doesn't matter (normalized to uppercase). |
| `last_price` | The number on screen right now. |
| `bid` / `ask` / `spread` | Enter bid and ask; spread may be left blank (derived as `ask - bid`). If you type a spread that contradicts bid/ask, the record is flagged `conflicted`, your value is kept as evidence, and it is not stored. |
| `day_open/high/low`, `previous_close` | Only if visible. A last price outside the day range flags the record `conflicted` — re-read the screen. |
| `volume`, `relative_volume` | Plain numbers, no commas or "M"/"K" suffixes (write `4200000`, not `4.2M`). |
| `implied_volatility`, `expected_move` | Copy the displayed number; note its units in `notes` if ambiguous. |
| `call_wall`, `put_wall`, `largest_*_volume_strike` | Strike prices from the options view, if you have it open. |
| `session` | `pre`, `core`, `post` — whatever describes the moment. |
| `source` | Always `webull_browser_manual` in this mode. |
| `notes` | Free text. What you saw, screen quirks, anything a future reader needs. |

**Golden rule: blank beats guessed.** The validator treats blank as
"not observed" (`null`). A fabricated `0` or approximate value poisons the
record permanently.

## What the errors mean

- `… is required and was not supplied` — fill in the required field; a
  missing timestamp is never auto-filled with "now".
- `… materially in the future` — check the date/time you typed.
- `supplied spread … contradicts calculated spread …` — bid, ask, and
  spread don't agree; re-read the screen and keep whichever pair you trust.
- `… outside day range` — last/open vs high/low disagree on screen order.
- `source must be 'webull_browser_manual'` — this CLI only ingests manual
  browser observations; API-derived data (none exists yet) will use a
  different source label and a different path.

## What this tool will never do

Contact Webull or any broker, use the network, read or store credentials,
place/cancel/modify orders, recommend a trade, or invent a value you did
not type. The example CSV values are fictional templates, not market data.
