## 1. Value transformation and presentation

- [x] 1.1 Add recursive `after_unknown` resolution for scalar, object, list, and marker-only nested values while preserving deterministic key order.
- [x] 1.2 Add one report-value formatter that preserves display sentinels, renders dicts and lists as compact JSON, normalizes scalar line endings, and escapes Markdown table delimiters.
- [x] 1.3 Apply sensitivity masking before presentation and pass canonical display values to every normal and critical resource-details table branch.

## 2. Regression coverage

- [x] 2.1 Convert the D3, D4, and D5 strict expected-failure tests into passing assertions for Markdown-safe scalar cells, JSON structures, and nested unknown object properties.
- [x] 2.2 Add list-shaped nested-unknown and sensitive structured-value regression cases, including values with pipes or line breaks.
- [x] 2.3 Refresh the kitchen-sink Markdown snapshot to record the intentional presentation change.

## 3. Verification

- [x] 3.1 Run `poe style`.
- [x] 3.2 Run `poe lint:all`.
- [x] 3.3 Run `poe test`.
- [x] 3.4 Run `poe pytest:integration` and confirm the rendered report contains valid, stable table rows without plaintext sensitive values.
- [x] 3.5 Run `pre-commit run --all-files`.

## 4. Documentation

- [x] 4.1 Update `docs/studies/2026-08-15-capability-and-market-analysis.md` to record D3, D4, and D5 as resolved and reflect the resulting P0 status.

## 5. Review remediation

- [x] 5.1 Emit rendered Markdown literally to stdout so JSON lists cannot be consumed as Rich markup.
- [x] 5.2 Retain concrete values when nested `after_unknown` container markers do not match their shape.
- [x] 5.3 Strengthen regressions for stdout JSON lists, mismatched markers, JSON nulls, and list-element replacement.
- [x] 5.4 Materialize nested marker-only containers and trim trailing false list markers without weakening shape-mismatch retention.
- [x] 5.5 Keep structured values containing pipes valid JSON while preserving Markdown table structure.
- [x] 5.6 Prove byte-identical stdout/file reports and consolidate the duplicated fixture CLI helper.
- [x] 5.7 Remove vestigial sentinel formatting and resolver aliases.
- [x] 5.8 Update current documentation to describe literal Typer stdout output and the removed Rich dependency.
