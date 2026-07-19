# SELFBULL-004B Webull MCP 1.1.6 Snapshot Formatter Contract

> Status: design-only contract derived from one fresh governed SPY capture and
> read-only inspection of the installed `webull-openapi-mcp` 1.1.6 package.
> This document does not authorize parser implementation, another broker
> request, fixture creation, derivative approval, ledger integration, SDK
> transport, or execution.

## 0. Purpose

Define the smallest exact formatter contract that a future SELFBULL parser may
admit for the captured `get_stock_snapshot` response shape.

This contract narrows the general receipt-admission doctrine in
`SELFBULL-004B-SNAPSHOT-RECEIPT-ADMISSION-DESIGN.md`. It does not broaden the
one-tool MCP aperture.

## 1. Evidence boundary

### 1.1 Fresh capture facts

The separately authorized capture proved only these safe facts:

- source package: `webull-openapi-mcp`,
- source package version: `1.1.6`,
- visible MCP tools: exactly `get_stock_snapshot`,
- canonical caller field: `symbol`,
- admitted MCP field: `symbols`,
- admitted `symbols` value type: string,
- optional arguments forwarded: no,
- broker requests executed: exactly one,
- requested symbol: SPY,
- result container: `CallToolResult`,
- formatted content path: `structuredContent.result`,
- formatted content type: string,
- formatter family: key/value text,
- formatted line count: seven,
- symbol match: true,
- secret-pattern detection: false,
- identity-pattern detection: false,
- authentication, entitlement, protocol, and timeout errors: absent,
- raw output committed: false,
- raw chamber destroyed: true,
- fixture admitted: false,
- execution authority: false.

Captured shape classification:

```text
webull-openapi-mcp-1.1.6.CallToolResult.structuredContent.result.key_value_text.labels-e3c9e5223680
```

No price, timestamp, size, volume, ratio, fundamental, request identifier, or
raw formatter line survives in this document.

### 1.2 Installed source facts

The installed package supplies the structural vocabulary without requiring
reconstruction of destroyed evidence.

Pinned source identity:

```text
webull-openapi-mcp=1.1.6
tools/market_data/stock.py
  sha256=b58d4bda3169f93a4d87ddb021c14e29e1fab8cf1d3df738a93e7c0de68fbab5
formatters.py
  sha256=f0cd28003934a07cef23e1b07f70864563b6823469cb0f404974ba748f59555d
```

The source proves:

- `get_stock_snapshot` accepts `symbols: str`,
- `category` defaults to `US_STOCK`,
- `extend_hour_required` defaults to `false`,
- `overnight_required` defaults to `false`,
- the tool splits the comma-delimited symbol string before SDK transport,
- the returned text is `prepend_disclaimer(format_stock_snapshot(data))`,
- missing or null formatter fields render as the literal sentinel `N/A`,
- the US disclaimer precedes formatter content and ends with a blank line.

### 1.3 Non-reconstruction law

**NO RECONSTRUCTION FROM DESTROYED EVIDENCE.**

The prior raw response remains destroyed. This document derives line labels
and ordering from pinned package source, while the fresh capture establishes
that the live result used the seven-line key/value family. The two evidence
planes are complementary and must not impersonate one another.

Package source cannot prove the values returned in the capture. The capture
cannot prove source lines that were not preserved in its sanitized receipt.

## 2. Exact invocation contract

The only invocation contract associated with this formatter shape is:

```json
{
  "canonical_intent": {"symbol": "SPY"},
  "admitted_arguments": {"symbols": "SPY"},
  "optional_arguments_forwarded": false
}
```

The package-default effective values are:

```json
{
  "category": "US_STOCK",
  "extend_hour_required": false,
  "overnight_required": false
}
```

Callers may not supply those optional fields under this shape. A future parser
may validate receipt facts about their omission; it does not own invocation.

The contract admits one requested symbol and one formatted snapshot block.
Comma-delimited input, multiple symbols, repeated symbol blocks, or symbol
mismatch fail closed.

## 3. MCP envelope contract

The parser may reach formatter text only through this exact sequence:

```text
CallToolResult
-> structuredContent
-> result
-> string
```

Required envelope conditions:

- result container type is exactly `CallToolResult`,
- `structuredContent` is present and mapping-like,
- `structuredContent.result` is present and a string,
- the MCP error flag is absent or false,
- no additional result container may substitute for this path,
- text content outside `structuredContent.result` is non-authoritative,
- `_meta` is never a source of market facts.

Missing, duplicated, aliased, or differently typed containers fail closed.

## 4. Captured formatter shape

### 4.1 Provisional implementation-target identity

The smallest source-derived parser target is:

```text
004B.womcp-1.1.6.stock-snapshot.us-default.single-symbol.fundamentals.v1
```

It becomes valid for a future capture only when all source hashes, package
version, envelope conditions, argument facts, and anchored line-layout
conditions in this document match.

The captured classifier identifier remains evidence about the capture. It is
not interchangeable with the parser contract identifier.

The seven-line capture receipt did not retain a value-free line-label skeleton.
It therefore does not by itself prove which one-line conditional section was
present. This target is selected from source and default invocation intent; it
is not retrospectively attributed to the destroyed response.

### 4.2 Seven-line structural candidates

The source and capture jointly prove the following common six-line prefix:

```text
1  <US DISCLAIMER LINE>
2  <EMPTY LINE>
3  === Stock Snapshot ===
4  <SYMBOL>  Price:<VALUE>  PreClose:<VALUE>  Change:<VALUE>  Change%:<VALUE>
5  Open:<VALUE>  High:<VALUE>  Low:<VALUE>  Close:<VALUE>  Vol:<VALUE>
6  Bid:<VALUE> x <SIZE>  Ask:<VALUE> x <SIZE>
```

The skeleton contains labels and placeholders only. It does not reproduce the
destroyed broker response.

The source defines two possible one-line additions relevant to a seven-line
single-symbol result:

```text
FUNDAMENTALS CANDIDATE
7  Turnover:<VALUE>  EPS:<VALUE>  EPS(TTM):<VALUE>  Lot Size:<VALUE>  BPS:<VALUE>

EXTENDED-HOURS CANDIDATE
7  ExtHr Price:<VALUE>  High:<VALUE>  Low:<VALUE>  Change:<VALUE> (<VALUE>)  Vol:<VALUE>
```

The captured request omitted the extended-hours argument, whose source-defined
default is false. That makes the fundamentals candidate the intended parser
target, but it does not convert the destroyed line into proven fundamentals
evidence. Only an exact anchored match during a future fresh capture may select
the fundamentals contract identity.

An extended-hours line under an omitted/false extended-hours receipt is a
contract contradiction and must return `OPTIONAL_SECTION_UNSUPPORTED`.

The seven-line receipt rules out the source-defined two-line overnight branch
for a one-symbol result, but it does not admit any value from either candidate.

### 4.3 Shapes not admitted

The following source-supported variants remain outside this contract:

- base layout without the fundamentals line,
- extended-hours line,
- overnight price line,
- overnight bid/ask line,
- combined conditional layouts,
- more than one symbol block,
- no-data response,
- error prose,
- non-US disclaimer variants,
- any package or source-hash drift.

Source support alone is not live admission evidence.

## 5. Parser law

The future parser is a versioned, anchored parser for this single shape. It is
not a generic key/value parser.

Required parsing sequence:

```text
verify transport receipt
-> verify raw witness reference
-> verify MCP envelope (extract structuredContent.result)
-> scan complete formatter text for secret patterns
-> scan complete formatter text for identity patterns
-> verify package version and source hashes
-> split lines without discarding the empty disclaimer separator
-> require exactly seven lines
-> verify disclaimer class and exact stock-snapshot header
-> match each data line with one anchored shape-specific pattern
-> require exactly one symbol block
-> prove returned symbol equals the separately supplied expected symbol
-> classify every formatter field
-> construct a scrubbed derivative candidate or controlled refusal
```

No search-based extraction, unordered label collection, fallback prose
parsing, fuzzy heading match, best-effort coercion, or generic schema inference
is permitted.

Whitespace may be normalized only where the package source intentionally uses
fixed-width padding. Labels, ordering, separators, `x` size delimiters,
parentheses, and line boundaries remain exact.

The pinned US disclaimer contains source-defined risk and investment-advice
language. It must be verified as a non-market prefix and excluded from market
field extraction. Its vetted vocabulary does not authorize equivalent words
inside market-data lines. Secret and identity scans still cover the complete
result, including the disclaimer.

## 6. Missing-value and numeric law

The package formatter renders missing or null fields as `N/A`.

Parser rules:

- `N/A` means missing, not zero,
- an empty token is not equivalent to `N/A`,
- `NaN`, infinity, signed infinity, and malformed decimals are invalid,
- price and quote values must be finite non-negative decimals,
- volume and quote sizes must be finite non-negative whole numbers when
  admitted,
- ratios and fundamental values receive no semantic admission merely because
  they parse numerically,
- duplicate labels or multiple values for one field are ambiguous,
- broker formatting is preserved until explicit field mapping completes.

Required factual candidate fields for the first real parser are:

- symbol,
- last price from `Price`,
- bid,
- ask,
- volume from `Vol`.

If any required factual candidate is `N/A` or invalid, return a controlled
refusal. Do not create a partial derivative under this first shape.

Spread may be derived only after independently admitting bid and ask. It must
equal ask minus bid and remains factual arithmetic, not interpretation.

## 7. Recognized but non-admitted fields

The parser must recognize the following labels to prove exact layout, but the
first derivative contract does not admit their values:

- `PreClose`,
- `Change`,
- `Change%`,
- `Open`,
- `High`,
- `Low`,
- `Close`,
- bid size,
- ask size,
- `Turnover`,
- `EPS`,
- `EPS(TTM)`,
- `Lot Size`,
- `BPS`.

They must be recorded categorically as recognized-but-not-admitted field
names. They may not silently disappear, enter `market_fields`, or acquire
semantic meaning through normalization.

Admission of any such field requires a separate contract revision and human
review.

## 8. Temporal truth

Although the upstream snapshot data model mentions `last_trade_time`, the
version `1.1.6` formatter source does not emit it in this shape.

Therefore:

- `observed_at = null`,
- `observed_at_source = UNAVAILABLE`,
- `recorded_at` may contain local capture time only,
- local capture time may not substitute for broker observation time,
- transport completion time may not substitute for broker observation time,
- no timestamp may be inferred from market values, session state, or request
  timing.

The absence of broker observation time must survive normalization and ledger
integration as an explicit epistemic limitation.

## 9. Controlled refusal classes

The implementation must preserve existing categorical failures and add exact
formatter-contract failures equivalent to:

- `SOURCE_HASH_MISMATCH`,
- `DISCLAIMER_MISMATCH`,
- `LINE_COUNT_MISMATCH`,
- `FIELD_LAYOUT_MISMATCH`,
- `MULTI_SYMBOL_RESPONSE`,
- `OPTIONAL_SECTION_UNSUPPORTED`.

Existing required classes remain applicable:

- `UNKNOWN_FORMATTER_SHAPE`,
- `UNSUPPORTED_PACKAGE_VERSION`,
- `STRUCTURED_CONTENT_MISSING`,
- `RESULT_CONTAINER_MISSING`,
- `REQUIRED_FIELD_MISSING`,
- `AMBIGUOUS_FIELD`,
- `VALUE_TYPE_INVALID`,
- `SYMBOL_MISMATCH`,
- `TIMESTAMP_UNAVAILABLE`,
- `SECRET_PATTERN_PRESENT`,
- `IDENTITY_PATTERN_PRESENT`,
- `PARSER_INTERNAL_ERROR`,
- `TRANSPORT_RECEIPT_INVALID`,
- `RAW_REFERENCE_INVALID`.

Every refusal is value-free. It must not reproduce formatter text, market
values, package paths, exception strings, request identifiers, or credential
material. Refusal never authorizes another broker request.

## 10. Derivative mapping boundary

The future successful mapping is limited to:

```text
formatter symbol -> instrument_symbol
Price            -> last_price
Bid              -> bid
Ask              -> ask
Vol              -> volume
Ask - Bid        -> spread
no formatter time -> observed_at=null
local capture time -> recorded_at
```

The derivative must retain:

- source package and version,
- canonical formatter-shape identity,
- transport receipt identity,
- raw witness reference identity,
- all recognized broker field names,
- admitted field names,
- recognized-but-not-admitted field names,
- null field names,
- `human_review_status = PENDING`,
- `sha256_registration = null`,
- `fixture_admitted = false`,
- `execution_authority = false`.

The parser may not approve, hash, register, persist, or admit the candidate as
a fixture.

## 11. Privacy and authority boundary

Before parsing any line, scan the complete formatter result for:

- app-key and app-secret markers,
- bearer, access-token, and refresh-token markers,
- authorization and signature markers,
- account identifiers,
- request and trace identifiers,
- session identifiers,
- profile and home-directory paths.

Any match returns a categorical refusal without reproducing the match.

The parser has no authority to:

- start MCP,
- authenticate,
- read token custody,
- invoke a broker,
- request another symbol,
- expose account or watchlist data,
- call trading or order tools,
- call the SELFBULL SDK transport,
- poll or stream,
- create a fixture,
- write to the snapshot ledger,
- normalize into canonical observation state,
- generate analysis, recommendation, or execution intent.

`execution_authority` remains `false` in every output.

## 12. Smallest future implementation delta

The future implementation may modify only:

- `src/selfbull/snapshot_receipt_admission.py`,
- `tests/test_snapshot_receipt_admission.py`.

It may:

- register the exact `1.1.6` formatter contract,
- validate source identity supplied by the capture boundary,
- add the required controlled failure classes,
- parse fictional seven-line inputs matching this document,
- build a pending scrubbed derivative candidate.

It may not import the installed Webull package at runtime, inspect package
paths during admission, start MCP, issue requests, or embed the destroyed live
response in tests. Source version and hashes must arrive as explicit custody
metadata from a separately governed capture boundary.

## 13. Offline test requirements

Before any future broker capture, fictional tests must prove:

1. exact seven-line shape succeeds,
2. exact symbol match is required,
3. admitted fields map exactly,
4. recognized-but-not-admitted fields remain categorical,
5. missing required values refuse,
6. malformed numeric values refuse,
7. reordered lines refuse,
8. duplicate labels refuse,
9. changed header refuses,
10. changed disclaimer class refuses,
11. base-only layout refuses,
12. extended-hours layout refuses when the receipt proves the option was not
    forwarded,
13. overnight layout refuses,
14. multi-symbol layout refuses,
15. package-version drift refuses,
16. source-hash drift refuses,
17. secret and identity patterns refuse without reproduction,
18. `observed_at` remains null,
19. no raw text enters receipts or derivatives,
20. no broker, credential, token, MCP, SDK, fixture, or ledger path executes.

## 14. Admission sequence

This design preserves the governing sequence:

```text
formatter contract design
-> independent design review
-> design commit
-> bounded offline parser implementation
-> independent implementation review
-> fresh separately authorized capture
-> scrubbed derivative candidate
-> human review
-> SHA-256 registration
-> separate golden-fixture admission
-> additive normalizer and ledger integration
```

No earlier step grants authority for a later step.

## 15. Rollback

Before commit, rollback is removal of this one document. After an isolated
future commit, rollback is a revert of that commit.

The design changes no runtime behavior and creates no broker-side state.

## 16. Next lawful gate

The next gate is an independent, read-only review of this document. It must
stop before parser implementation, fixture creation, or another broker
request.
