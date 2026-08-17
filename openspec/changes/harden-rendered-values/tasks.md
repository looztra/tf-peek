## 1. Value transformation and presentation

- [ ] 1.1 Add recursive `after_unknown` resolution for scalar, object, list, and marker-only nested values while preserving deterministic key order.
- [ ] 1.2 Add one report-value formatter that preserves display sentinels, renders dicts and lists as compact JSON, normalizes scalar line endings, and escapes Markdown table delimiters.
- [ ] 1.3 Apply sensitivity masking before presentation and pass canonical display values to every normal and critical resource-details table branch.

## 2. Regression coverage

- [ ] 2.1 Convert the D3, D4, and D5 strict expected-failure tests into passing assertions for Markdown-safe scalar cells, JSON structures, and nested unknown object properties.
- [ ] 2.2 Add list-shaped nested-unknown and sensitive structured-value regression cases, including values with pipes or line breaks.
- [ ] 2.3 Refresh the kitchen-sink Markdown snapshot to record the intentional presentation change.

## 3. Verification

- [ ] 3.1 Run `poe style`.
- [ ] 3.2 Run `poe lint:all`.
- [ ] 3.3 Run `poe test`.
- [ ] 3.4 Run `poe pytest:integration` and confirm the rendered report contains valid, stable table rows without plaintext sensitive values.
- [ ] 3.5 Run `pre-commit run --all-files`.

## 4. Documentation

- [ ] 4.1 Update `docs/studies/2026-08-15-capability-and-market-analysis.md` to record D3, D4, and D5 as resolved and reflect the resulting P0 status.
